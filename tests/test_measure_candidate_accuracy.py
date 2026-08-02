from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from measure_candidate_accuracy import (  # noqa: E402
    compute_accuracy,
    derive_stub_chapters,
    match_candidates_to_curated,
)
from multi_grab import load_overrides  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders — small synthetic docs, never live repo data/epub, except
# the one explicit real-corpus test at the bottom.
# ---------------------------------------------------------------------------

def _curated_roll(
    perks=None,
    outcome: str = "hit",
    word_position: int | None = None,
    evidence_quotes=None,
    source_ordinal: int | None = None,
) -> dict:
    return {
        "perks": perks or [],
        "outcome": outcome,
        "constellation": None,
        "word_position": word_position,
        "mention_chapter_num": None,
        "mention_word_position": None,
        "display_position_policy": "mechanical",
        "evidence_quotes": evidence_quotes or [],
        "curator_note": None,
        "skipped": False,
        "source_ordinal": source_ordinal,
        "curator_added": False,
    }


def _overrides_doc(chapters: dict) -> dict:
    return {"chapter_roll_overrides": chapters}


def _candidate(
    chapter_num: str,
    slot_index: int,
    word_position: int,
    perks=None,
    outcome: str = "hit",
    evidence_kind: str = "direct",
    unfilled_fields=None,
    roll_number: int | None = None,
) -> dict:
    return {
        "roll_number": roll_number if roll_number is not None else slot_index,
        "chapter_num": chapter_num,
        "slot_index": slot_index,
        "word_position": word_position,
        "mention_chapter_num": chapter_num,
        "mention_word_position": word_position,
        "display_position_policy": "mechanical",
        "perks": perks or [],
        "outcome": outcome,
        "constellation": None,
        "evidence_quotes": [],
        "_derivation": {
            "evidence_kind": evidence_kind,
            "matched_anchor_kinds": [],
            "bundle_source": None,
            "unfilled_fields": unfilled_fields or [],
        },
    }


_QUOTE = {"text": "sample", "mention_chapter_num": "5", "mention_word_position": 100}


# ---------------------------------------------------------------------------
# 1. Stub-chapter derivation.
# ---------------------------------------------------------------------------

def test_stub_chapter_with_all_empty_evidence_quotes_is_derived() -> None:
    doc = _overrides_doc({
        "1": {"rolls": [_curated_roll(evidence_quotes=[])]},
        "2": {"rolls": [_curated_roll(evidence_quotes=[_QUOTE])]},
    })
    assert derive_stub_chapters(doc) == {"1"}


# ---------------------------------------------------------------------------
# 2. Matching never relies on roll_number/source_ordinal equality.
# ---------------------------------------------------------------------------

def test_matching_never_relies_on_roll_number_equality() -> None:
    curated_rolls = [
        _curated_roll(word_position=100, source_ordinal=10),
        _curated_roll(word_position=5000, source_ordinal=20),
    ]
    candidates = [
        _candidate("5", slot_index=1, word_position=105, roll_number=999),
        _candidate("5", slot_index=2, word_position=5010, roll_number=10),
    ]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    results = result["curated_results"]

    # curated[0] (source_ordinal=10, word_position=100) matches candidate[0]
    # (roll_number=999, word_position=105) -- different identifiers,
    # matched purely by position proximity.
    assert results[0]["status"] == "matched"
    assert results[0]["matched_candidate_index"] == 0

    # curated[1] (source_ordinal=20, word_position=5000) matches
    # candidate[1] (roll_number=10, word_position=5010). candidate[1]'s
    # roll_number (10) equals curated[0]'s source_ordinal (10), yet
    # curated[0] did NOT pair with candidate[1] -- position proximity,
    # never identifier equality, decides the match.
    assert results[1]["status"] == "matched"
    assert results[1]["matched_candidate_index"] == 1


# ---------------------------------------------------------------------------
# 3. Partial vs full match.
# ---------------------------------------------------------------------------

def test_partial_match_counted_separately_from_full_match() -> None:
    curated_rolls = [_curated_roll(word_position=100)]
    candidates = [
        _candidate("5", slot_index=1, word_position=100, unfilled_fields=["constellation"]),
    ]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    assert result["curated_results"][0]["status"] == "partial"


def test_full_match_has_no_unfilled_fields() -> None:
    curated_rolls = [_curated_roll(word_position=100)]
    candidates = [_candidate("5", slot_index=1, word_position=100)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    assert result["curated_results"][0]["status"] == "matched"


# ---------------------------------------------------------------------------
# 4. Curated roll with no candidate -> missed.
# ---------------------------------------------------------------------------

def test_curated_roll_with_no_candidate_counted_as_missed() -> None:
    curated_rolls = [
        _curated_roll(word_position=100),
        _curated_roll(word_position=200),
    ]
    candidates = [_candidate("5", slot_index=1, word_position=100)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    statuses = [entry["status"] for entry in result["curated_results"]]
    assert statuses.count("missed") == 1
    assert statuses.count("matched") == 1


# ---------------------------------------------------------------------------
# 5. Candidate with no curated roll -> unmatched.
# ---------------------------------------------------------------------------

def test_candidate_with_no_curated_roll_counted_as_unmatched() -> None:
    curated_rolls = [_curated_roll(word_position=100)]
    candidates = [
        _candidate("5", slot_index=1, word_position=100),
        _candidate("5", slot_index=2, word_position=200),
    ]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    assert result["unmatched_candidate_indices"] == [1]


# ---------------------------------------------------------------------------
# 6. Determinism.
# ---------------------------------------------------------------------------

def test_determinism_rerun_produces_identical_totals() -> None:
    doc = _overrides_doc({
        "5": {"rolls": [
            _curated_roll(word_position=100, perks=["A"], evidence_quotes=[_QUOTE]),
            _curated_roll(word_position=500, evidence_quotes=[_QUOTE]),
        ]},
    })
    candidates_doc = {"candidates": [
        _candidate("5", 1, 100, perks=["A"], evidence_kind="direct"),
        _candidate("5", 2, 500, evidence_kind="forward_ref"),
    ]}

    accuracy_1 = compute_accuracy(doc, candidates_doc)
    accuracy_2 = compute_accuracy(doc, candidates_doc)
    assert accuracy_1 == accuracy_2
    by_evidence_class = accuracy_1["by_evidence_class"]
    assert by_evidence_class["direct"]["curated_rolls"] == 1
    assert by_evidence_class["direct"]["matched"] == 1
    assert by_evidence_class["forward_ref"]["curated_rolls"] == 1
    assert by_evidence_class["forward_ref"]["matched"] == 1
    # Both curated rolls in this fixture carry a real word_position, so
    # both land in the "word_position" tier, not "quote_position" or
    # "ordinal".
    assert accuracy_1["position_tier_counts"] == {
        "word_position": 2, "quote_position": 0, "ordinal": 0,
    }


# ---------------------------------------------------------------------------
# 8. Three-tier curated-side position ladder.
# ---------------------------------------------------------------------------

def test_position_tier_word_position_takes_precedence() -> None:
    """A roll with a real word_position uses it, even when evidence_quotes
    with mention_word_position are also present."""
    curated_rolls = [
        _curated_roll(
            word_position=100,
            evidence_quotes=[
                {"text": "x", "mention_chapter_num": "5", "mention_word_position": 9000},
            ],
        ),
    ]
    candidates = [_candidate("5", slot_index=1, word_position=100)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    assert result["curated_results"][0]["position_tier"] == "word_position"


def test_position_tier_falls_back_to_min_quote_position() -> None:
    """No word_position -> minimum mention_word_position among the roll's
    own-chapter evidence_quotes (the connection quote, per
    CURATION-CONVENTIONS.md Sec 2/3, sorts earliest; later quotes about
    the same roll can trail by thousands of words and must not be
    allowed to pull the position later)."""
    curated_rolls = [
        _curated_roll(
            word_position=None,
            evidence_quotes=[
                {"text": "later mention", "mention_chapter_num": "5", "mention_word_position": 900},
                {"text": "connection quote", "mention_chapter_num": "5", "mention_word_position": 100},
            ],
        ),
    ]
    candidates = [_candidate("5", slot_index=1, word_position=100)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    entry = result["curated_results"][0]
    assert entry["position_tier"] == "quote_position"
    assert entry["status"] == "matched"


def test_position_tier_excludes_cross_chapter_quotes() -> None:
    """A quote naming a different chapter than the roll's own chapter
    (~8% of corpus quotes per Sec 3) must never be used for positional
    comparison -- it is a different coordinate space. A roll with only
    cross-chapter quotes falls all the way to ordinal."""
    curated_rolls = [
        _curated_roll(
            word_position=None,
            evidence_quotes=[
                {"text": "wrong chapter", "mention_chapter_num": "6", "mention_word_position": 50},
            ],
        ),
    ]
    candidates = [_candidate("5", slot_index=1, word_position=9999)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    entry = result["curated_results"][0]
    assert entry["position_tier"] == "ordinal"
    # Ordinal-tier comparison is against the candidate's own ordinal rank
    # (0), not its real word_position (9999) -- still a match since both
    # sides are the sole entry (index 0).
    assert entry["status"] == "matched"


def test_position_tier_ordinal_when_no_positional_evidence_at_all() -> None:
    curated_rolls = [_curated_roll(word_position=None, evidence_quotes=[])]
    candidates = [_candidate("5", slot_index=1, word_position=100)]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    assert result["curated_results"][0]["position_tier"] == "ordinal"


def test_quote_position_changes_pairing_versus_ordinal_fallback() -> None:
    """Regression fixture: with two curated rolls and two candidates
    whose word_positions and ordinal ranks would pair candidates
    OPPOSITE to how quote-derived positions pair them, the ladder must
    follow the quote-derived (real) position, not the ordinal rank.

    Curated roll 0 (ordinal 0) has no word_position of its own, but its
    evidence_quotes point near word 900 -- close to candidate 1
    (word_position=910), far from candidate 0 (word_position=50).
    Curated roll 1 (ordinal 1) similarly has evidence pointing near word
    40 -- close to candidate 0, far from candidate 1.

    Under the old ordinal-only fallback, curated[0] (ordinal 0) would
    pair with candidate[0] (ordinal 0) and curated[1] (ordinal 1) with
    candidate[1] (ordinal 1) -- the "Nth-lines-up-with-Nth" degenerate
    behavior this fix corrects. Under the quote-position ladder, the
    pairing must invert: curated[0] pairs with candidate[1], and
    curated[1] pairs with candidate[0].
    """
    curated_rolls = [
        _curated_roll(
            word_position=None,
            evidence_quotes=[
                {"text": "near 900", "mention_chapter_num": "5", "mention_word_position": 900},
            ],
        ),
        _curated_roll(
            word_position=None,
            evidence_quotes=[
                {"text": "near 40", "mention_chapter_num": "5", "mention_word_position": 40},
            ],
        ),
    ]
    candidates = [
        _candidate("5", slot_index=1, word_position=50),
        _candidate("5", slot_index=2, word_position=910),
    ]
    result = match_candidates_to_curated("5", curated_rolls, candidates)
    results = result["curated_results"]
    assert results[0]["position_tier"] == "quote_position"
    assert results[0]["matched_candidate_index"] == 1  # word_position=910
    assert results[1]["position_tier"] == "quote_position"
    assert results[1]["matched_candidate_index"] == 0  # word_position=50


# ---------------------------------------------------------------------------
# 9. Tier counts reported by compute_accuracy.
# ---------------------------------------------------------------------------

def test_compute_accuracy_reports_position_tier_counts() -> None:
    doc = _overrides_doc({
        "5": {"rolls": [
            _curated_roll(word_position=100, evidence_quotes=[_QUOTE]),
            _curated_roll(
                word_position=None,
                evidence_quotes=[
                    {"text": "q", "mention_chapter_num": "5", "mention_word_position": 500},
                ],
            ),
            _curated_roll(word_position=None, evidence_quotes=[]),
        ]},
    })
    candidates_doc = {"candidates": [
        _candidate("5", 1, 100, evidence_kind="direct"),
        _candidate("5", 2, 500, evidence_kind="direct"),
        _candidate("5", 3, 900, evidence_kind="direct"),
    ]}
    accuracy = compute_accuracy(doc, candidates_doc)
    assert accuracy["position_tier_counts"] == {
        "word_position": 1, "quote_position": 1, "ordinal": 1,
    }


# ---------------------------------------------------------------------------
# 7. One real-corpus assertion.
# ---------------------------------------------------------------------------

def test_live_stub_chapters_exclude_104_include_the_rest() -> None:
    doc = load_overrides()
    stubs = derive_stub_chapters(doc)
    assert "104" not in stubs
    for chapter_num in (
        "35.1", "55.1", "97", "100", "103", "106", "109", "112", "114", "116.2",
    ):
        assert chapter_num in stubs
