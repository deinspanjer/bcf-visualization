"""Behaviour of the submission handler, driven by a recorded payload.

Zero inference. ``process_stage2_response`` takes a plain dict and returns
a routing outcome, so the whole locate -> verify -> pre-fill -> route path
is exercised with no transport, no subprocess, and no MCP.

Every write here goes to a tmp_path proposals file. The trusted corpus is
never touched, and no module under test can reach it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import EPUB  # noqa: E402
from scripts.data_paths import DERIVED, MANUAL  # noqa: E402
from scripts.mechanical_verifier import (  # noqa: E402
    _build_prose_loader,
    build_obtained_perks_index,
)
from scripts.perk_name_resolver import (  # noqa: E402
    build_directory_match_index,
    load_perk_aliases,
)
from scripts.stage2_proposals_io import load_agent_proposals_doc  # noqa: E402
from scripts.stage2_response import (  # noqa: E402
    DuplicateSlotIndexError,
    Stage2RunContext,
    process_stage2_response,
)

FIXTURE = ROOT / "tests" / "fixtures" / "stage2_submission_sample.json"
CHAPTER = "92"


@pytest.fixture(scope="module")
def sample_submission() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def ctx(tmp_path: Path) -> Stage2RunContext:
    chapters_doc = json.loads((DERIVED / "chapters.json").read_text())
    classifications_doc = json.loads(
        (MANUAL / "section_classifications.json").read_text()
    )
    perk_directory = json.loads((DERIVED / "perk_directory.json").read_text())
    obtained = json.loads((DERIVED / "obtained_perks.json").read_text())
    candidate_doc = json.loads((DERIVED / "candidate_rolls.json").read_text())

    by_chapter: dict[str, dict[int, dict]] = {}
    for cand in candidate_doc["candidates"]:
        chapter = str(cand["chapter_num"])
        by_chapter.setdefault(chapter, {})[int(cand["slot_index"])] = cand

    return Stage2RunContext(
        prose_loader=_build_prose_loader(EPUB, chapters_doc, classifications_doc),
        directory_index=build_directory_match_index(
            perk_directory["perks"], load_perk_aliases(MANUAL / "perk_aliases.json")
        ),
        obtained_perks_index=build_obtained_perks_index(obtained),
        candidates_by_chapter=by_chapter,
        run_id="test-run",
        model="test-model",
        proposals_path=tmp_path / "agent_proposals.json",
    )


def _by_slot(outcome) -> dict[int, tuple[dict, dict]]:
    return {
        entry["slot_index"]: (roll, entry)
        for roll, entry in zip(outcome.rolls, outcome.per_roll)
    }


# ---------------------------------------------------------------------------
# slot mapping
# ---------------------------------------------------------------------------

def test_slot_index_not_positional(ctx, sample_submission) -> None:
    """Mapping follows the explicit slot_index, never list order."""
    rolls = list(sample_submission["rolls"])
    shuffled = list(reversed(rolls))
    assert [r["slot_index"] for r in shuffled] != [r["slot_index"] for r in rolls]

    in_order = process_stage2_response(CHAPTER, rolls, ctx=ctx)
    reversed_outcome = process_stage2_response(CHAPTER, shuffled, ctx=ctx)

    a, b = _by_slot(in_order), _by_slot(reversed_outcome)
    assert set(a) == set(b)
    for slot in a:
        assert a[slot][0]["outcome"] == b[slot][0]["outcome"]
        assert a[slot][0]["constellation"] == b[slot][0]["constellation"]
        assert a[slot][0]["evidence_quotes"] == b[slot][0]["evidence_quotes"]

    # The hit landed on slot 1, the miss on slot 2 -- not the other way round.
    assert a[1][0]["outcome"] == "hit"
    assert a[1][0]["constellation"] == "Size"
    assert a[2][0]["outcome"] == "miss"
    assert a[2][0]["constellation"] == "Knowledge"


def test_duplicate_slot_index_rejects_whole_submission(ctx) -> None:
    """A duplicate is rejected, never resolved last-one-wins."""
    rolls = [
        {"slot_index": 1, "outcome": "hit", "constellation": "Size"},
        {"slot_index": 1, "outcome": "miss", "constellation": "Knowledge"},
    ]
    with pytest.raises(DuplicateSlotIndexError, match="more than once"):
        process_stage2_response(CHAPTER, rolls, ctx=ctx)

    # Nothing was written -- the rejection is atomic.
    assert not (ctx.proposals_path or Path("/nonexistent")).exists()


def test_missing_slot_index_is_rejected(ctx) -> None:
    with pytest.raises(DuplicateSlotIndexError):
        process_stage2_response(CHAPTER, [{"outcome": "hit"}], ctx=ctx)


# ---------------------------------------------------------------------------
# evidence-not-found
# ---------------------------------------------------------------------------

def test_unverified_quote_becomes_evidence_not_found(ctx, sample_submission) -> None:
    """An unlocatable quote is preserved, not dropped and not positioned."""
    outcome = process_stage2_response(
        CHAPTER, sample_submission["rolls"], ctx=ctx
    )
    _roll, sidecar = _by_slot(outcome)[2]

    unlocated = sidecar["unlocated_quotes"]
    assert len(unlocated) == 1
    assert "wondrous device" in unlocated[0]["text"]
    # The model's text survives for Dre's judgment...
    assert unlocated[0].get("mention_word_position") is None
    # ...and never reaches the roll's real evidence.
    roll, _ = _by_slot(outcome)[2]
    for quote in roll["evidence_quotes"]:
        assert "wondrous device" not in quote["text"]
        assert isinstance(quote["mention_word_position"], int)

    # The roll is still written, with its gap marked.
    assert roll["outcome"] == "miss"
    assert "evidence_quotes:partial" in sidecar["unfilled_fields"]


def test_located_quotes_carry_derived_positions(ctx, sample_submission) -> None:
    outcome = process_stage2_response(CHAPTER, sample_submission["rolls"], ctx=ctx)
    roll, sidecar = _by_slot(outcome)[1]

    assert len(roll["evidence_quotes"]) == 2
    for quote in roll["evidence_quotes"]:
        assert isinstance(quote["mention_word_position"], int)
        assert quote["mention_chapter_num"] == CHAPTER
    # Positions are derived by locating text, so verification agrees by
    # construction rather than by luck.
    assert sidecar["verify_status"] == "pass"
    assert all(tier in (1, 2) for tier in sidecar["quote_tiers"])


# ---------------------------------------------------------------------------
# partial output is correct output
# ---------------------------------------------------------------------------

def test_quoteless_roll_accepted(ctx) -> None:
    """WoG-backed and evidence-not-found rolls survive to proposals."""
    rolls = [
        {
            "slot_index": 1,
            "outcome": "miss",
            "constellation": "Capstone",
            "perks": [],
            "evidence_quotes": [],
            "curator_note": "WoG: missed Capstone roll, no narrative evidence.",
        }
    ]
    outcome = process_stage2_response(CHAPTER, rolls, ctx=ctx)
    roll, sidecar = _by_slot(outcome)[1]

    assert roll["evidence_quotes"] == []
    assert roll["constellation"] == "Capstone"
    assert roll["curator_note"].startswith("WoG")
    assert sidecar["verify_status"] == "no_evidence"
    assert "evidence_quotes" in sidecar["unfilled_fields"]

    doc = load_agent_proposals_doc(ctx.proposals_path)
    assert CHAPTER in doc["agent_proposals"]


def test_empty_rolls_array_is_a_valid_outcome(ctx) -> None:
    outcome = process_stage2_response(CHAPTER, [], ctx=ctx)

    # Stage 1 slots still appear, marked unanswered -- a blank chapter
    # captures none of the value.
    assert outcome.rolls
    assert all(entry["answered_by_model"] is False for entry in outcome.per_roll)
    doc = load_agent_proposals_doc(ctx.proposals_path)
    assert doc["agent_proposals"][CHAPTER]["curated_by"] == "agent"


def test_unanswered_slots_are_written_not_dropped(ctx, sample_submission) -> None:
    only_one = [sample_submission["rolls"][0]]
    outcome = process_stage2_response(CHAPTER, only_one, ctx=ctx)

    by_slot = _by_slot(outcome)
    assert by_slot[1][1]["answered_by_model"] is True
    assert by_slot[2][1]["answered_by_model"] is False


# ---------------------------------------------------------------------------
# D-17 pre-fill richness
# ---------------------------------------------------------------------------

def test_proposal_is_fully_prefilled(ctx, sample_submission) -> None:
    """Review must be confirm-or-correct, never start-from-blank."""
    outcome = process_stage2_response(CHAPTER, sample_submission["rolls"], ctx=ctx)
    roll, sidecar = _by_slot(outcome)[1]

    assert roll["perks"], "bundle grouping must survive to the proposal"
    assert roll["outcome"] == "hit"
    assert roll["constellation"] == "Size"
    assert roll["evidence_quotes"]
    for quote in roll["evidence_quotes"]:
        assert quote["text"]
        assert isinstance(quote["mention_word_position"], int)

    # Per-field evidenced/not-found record exists for every roll.
    for entry in outcome.per_roll:
        assert "unfilled_fields" in entry
        assert "verify_status" in entry

    # The written file carries the same richness the outcome reports.
    doc = load_agent_proposals_doc(ctx.proposals_path)
    written = doc["agent_proposals"][CHAPTER]
    assert written["rolls"] == outcome.rolls
    assert written["_stage2"]["per_roll"] == outcome.per_roll
    assert written["_stage2"]["model"] == "test-model"
    assert written["_stage2"]["tool_surface_version"]


def test_constellation_is_mechanically_derived(ctx) -> None:
    """The code-derived constellation beats a disagreeing model claim."""
    rolls = [
        {
            "slot_index": 2,
            "outcome": "miss",
            "constellation": "Magic",  # wrong on purpose
            "evidence_quotes": [
                {
                    "text": "I felt the Forge fail to connect to a massive mote "
                    "from the Knowledge constellation"
                }
            ],
        }
    ]
    outcome = process_stage2_response(CHAPTER, rolls, ctx=ctx)
    roll, sidecar = _by_slot(outcome)[2]

    assert roll["constellation"] == "Knowledge"
    assert sidecar["constellation_check"] == "mechanical_overrides"


def test_self_report_is_carried_but_never_routes(ctx) -> None:
    """Self-reported confidence is metadata only (D-13 TIGHTENED)."""
    confident_but_wrong = [
        {
            "slot_index": 1,
            "outcome": "hit",
            "constellation": "Size",
            "evidence_quotes": [{"text": "a quote that does not exist in this prose"}],
            "self_reported_confidence": "high",
        }
    ]
    outcome = process_stage2_response(CHAPTER, confident_but_wrong, ctx=ctx)
    _roll, sidecar = _by_slot(outcome)[1]

    # Carried verbatim...
    assert sidecar["self_reported_confidence"] == "high"
    # ...and it bought the roll nothing: the quote still failed to locate.
    assert len(sidecar["unlocated_quotes"]) == 1
    assert sidecar["verify_status"] in ("no_evidence", "fail")


# ---------------------------------------------------------------------------
# the corpus is unreachable from here
# ---------------------------------------------------------------------------

def test_proposals_are_not_the_corpus(ctx, sample_submission) -> None:
    process_stage2_response(CHAPTER, sample_submission["rolls"], ctx=ctx)

    assert ctx.proposals_path.exists()
    assert "derived" not in str(MANUAL)
    # The proposals file is not the corpus file, by path and by content.
    corpus = MANUAL / "chapter_roll_overrides.json"
    assert ctx.proposals_path != corpus
    doc = json.loads(ctx.proposals_path.read_text())
    assert "agent_proposals" in doc
    assert "chapter_roll_overrides" not in doc


def test_read_tool_handlers_are_side_effect_free(ctx) -> None:
    """Read tools serve information and record nothing the gate consults."""
    before = json.dumps(ctx.candidates_by_chapter, sort_keys=True)

    span = ctx.prose_span(CHAPTER, 1000, 1100)
    checked = ctx.check_quote(
        CHAPTER,
        "I felt the Forge fail to connect to a massive mote from the "
        "Knowledge constellation",
    )

    assert span
    assert checked["found"] is True
    # No destination, no routing decision in a read-tool response.
    assert set(checked) == {"found", "tier", "word_position", "occurrence_count"}
    assert "destination" not in checked
    # Read tools never mutate pipeline state or write proposals.
    assert json.dumps(ctx.candidates_by_chapter, sort_keys=True) == before
    assert not ctx.proposals_path.exists()
    # The read-set is recorded as audit metadata only.
    assert len(ctx.read_set) == 2
    assert all("response_sha256" in entry for entry in ctx.read_set)
