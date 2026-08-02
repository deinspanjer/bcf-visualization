from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_candidate_rolls import assemble_all_candidates, assemble_candidate  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders — small synthetic docs, never live repo data / epub.
# ---------------------------------------------------------------------------

def _row(
    roll_number: int,
    chapter_num: str,
    slot_index: int,
    predicted_word_in_chapter: int,
    evidence_kind: str = "forward_ref",
    matching_anchor_kinds: list[str] | None = None,
    matching_events: list[dict] | None = None,
) -> dict:
    return {
        "roll_number": roll_number,
        "chapter_num": chapter_num,
        "slot_index": slot_index,
        "evidence_kind": evidence_kind,
        "matching_anchor_kinds": matching_anchor_kinds or [],
        "matching_events": matching_events or [],
        "predicted_word_in_chapter": predicted_word_in_chapter,
    }


def _obtained_perk(
    chapter_num: str, epub_sequence: int, perk_name: str,
    cost: int, constellation: str | None,
) -> dict:
    return {
        "epub_sequence": epub_sequence,
        "chapter_num": chapter_num,
        "chapter_full_title": "Synthetic Chapter",
        "perk_name": perk_name,
        "classification": None,
        "jump": None,
        "cost": cost,
        "cost_text": f"{cost} CP" if cost else "free",
        "cost_unit": "CP" if cost else None,
        "free": cost == 0,
        "perk_text": "",
        "constellation": constellation,
    }


def _unit(
    chapter_num: str,
    paid_name: str,
    constellation: str | None,
    free_names: tuple[str, ...] = (),
    cost: int = 100,
) -> dict:
    return {
        "chapter_num": chapter_num,
        "paid": [{
            "perk_name": paid_name, "constellation": constellation,
            "cost": cost, "free": False,
        }],
        "free_perks": [
            {"perk_name": n, "cost": 0, "free": True} for n in free_names
        ],
        "epub_sequence": 1,
        "jump": None,
    }


def _build_word_index(html: str) -> list[int]:
    """Naive whitespace-tokenized char-offset index for a plain (no-HTML-
    tags) synthetic prose string — good enough for a synthetic fixture,
    since the real tokenizer (cp_word_index._chapter_word_index) requires
    section-classification bookkeeping this test has no need to fabricate.
    """
    offsets: list[int] = []
    pos = 0
    for word in html.split():
        idx = html.index(word, pos)
        offsets.append(idx)
        pos = idx + len(word)
    return offsets


# ---------------------------------------------------------------------------
# Task 2 (TDD): full-corpus wiring — cursor reset per chapter, a chapter
# with zero obtained perks yields a fully-unfilled candidate (never an
# error), and the free-perk forward search finds a hyphen/space variant.
# Deterministic re-run proves the sorted, non-dict/set-order-dependent
# output ordering.
# ---------------------------------------------------------------------------

def test_assemble_all_candidates_walks_full_synthetic_corpus_deterministically() -> None:
    obtained_perks = [
        _obtained_perk("9001", 1, "Synthetic Test Perk", 100, "Testing"),
        _obtained_perk("9001", 2, "Altmode", 0, None),
    ]
    rows = [
        _row(9001, "9001", 1, 0, matching_anchor_kinds=["acquisition"]),
        # Chapter "8999" has a predicted roll but zero obtained perks at
        # all — merge_paid_units never produces a unit for it, and the
        # row carries no "miss" anchor, so it must come back fully
        # unfilled rather than raising.
        _row(9002, "8999", 1, 0),
    ]

    html_9001 = "I felt my power connect. It also gave me an alt-mode chassis."
    prose_by_chapter = {"9001": (html_9001, _build_word_index(html_9001))}

    def prose_loader(chapter_num: str) -> tuple[str, list[int]]:
        return prose_by_chapter.get(chapter_num, ("", []))

    candidates = assemble_all_candidates(rows, obtained_perks, prose_loader)

    assert len(candidates) == 2
    by_key = {(c["chapter_num"], c["roll_number"]): c for c in candidates}

    hit = by_key[("9001", 9001)]
    assert hit["outcome"] == "hit"
    assert "Synthetic Test Perk" in hit["perks"] and "Altmode" in hit["perks"]
    assert hit["constellation"] == "Testing"
    quote_texts = [q["text"] for q in hit["evidence_quotes"]]
    assert any("alt-mode" in t.lower() for t in quote_texts), quote_texts

    unfilled = by_key[("8999", 9002)]
    assert unfilled["outcome"] is None
    assert unfilled["perks"] == []
    assert unfilled["constellation"] is None
    assert {"outcome", "constellation", "perks"} <= set(
        unfilled["_derivation"]["unfilled_fields"]
    )

    # Deterministic re-run: same inputs -> byte-identical (order-stable)
    # output, per plan success criterion "re-running produces
    # byte-identical output."
    again = assemble_all_candidates(rows, obtained_perks, prose_loader)
    assert json.dumps(candidates, sort_keys=True) == json.dumps(again, sort_keys=True)


# ---------------------------------------------------------------------------
# Task 3: synthetic-fixture tests over assemble_candidate directly —
# positional binding, bundle grouping, constellation binding, and D-06
# partial-evidence emission. No epub or data/derived/data/manual file
# access anywhere in this file (test_build_exemplar_index.py convention).
# ---------------------------------------------------------------------------

def test_hit_binds_paid_perk_and_free_ride_alongs_as_one_candidate() -> None:
    row = _row(
        1, "1", 1, 100,
        evidence_kind="direct",
        matching_anchor_kinds=["acquisition"],
    )
    units = [_unit("1", "Paid Perk", "Quality", free_names=("Free A", "Free B"))]

    candidate, cursor = assemble_candidate(row, units, 0)

    assert candidate["perks"] == ["Paid Perk", "Free A", "Free B"]
    assert candidate["outcome"] == "hit"
    assert candidate["constellation"] == "Quality"
    assert candidate["_derivation"]["bundle_source"] == "merge_paid_units:default"
    assert "evidence_for:outcome" not in candidate["_derivation"]["unfilled_fields"]
    assert cursor == 1


def test_two_paid_perks_in_different_constellations_never_merge() -> None:
    units = [
        _unit("1", "Paid Perk One", "Quality"),
        _unit("1", "Paid Perk Two", "Magic"),
    ]
    row1 = _row(1, "1", 1, 100, matching_anchor_kinds=["acquisition"])
    row2 = _row(2, "1", 2, 200, matching_anchor_kinds=["acquisition"])

    cand1, cursor = assemble_candidate(row1, units, 0)
    cand2, cursor = assemble_candidate(row2, units, cursor)

    assert cand1 is not cand2
    assert cand1["perks"] == ["Paid Perk One"]
    assert cand2["perks"] == ["Paid Perk Two"]
    assert cand1["constellation"] == "Quality"
    assert cand2["constellation"] == "Magic"
    assert cursor == 2


def test_miss_with_constellation_reveal_anchor_binds_constellation() -> None:
    row = _row(
        1, "1", 1, 100,
        matching_anchor_kinds=["miss"],
        matching_events=[{
            "anchor_kind": "constellation_reveal",
            "anchor_phrase": "the Knowledge Constellation",
            "anchor_offset": 10,
            "kinds_present": ["constellation_reveal"],
            "hit_count": 1,
        }],
    )
    units = [_unit("1", "Unrelated Paid Perk", "Quality")]

    candidate, cursor = assemble_candidate(row, units, 0)

    assert candidate["outcome"] == "miss"
    assert candidate["constellation"] == "Knowledge"
    assert candidate["perks"] == []
    assert cursor == 0  # unit was NOT consumed


def test_positional_binding_binds_hit_without_local_anchor_evidence() -> None:
    row = _row(
        1, "1", 1, 100,
        evidence_kind="forward_ref",
        matching_anchor_kinds=[],
    )
    units = [_unit("1", "Paid Perk", "Quality", free_names=("Free A",))]

    candidate, cursor = assemble_candidate(row, units, 0)

    assert candidate["outcome"] == "hit"
    assert candidate["perks"] == ["Paid Perk", "Free A"]
    assert candidate["constellation"] == "Quality"
    assert cursor == 1
    assert "evidence_for:outcome" in candidate["_derivation"]["unfilled_fields"]


def test_miss_anchor_skips_unit_consumption_leaves_it_for_next_roll() -> None:
    units = [_unit("1", "Paid Perk", "Quality")]
    row_miss = _row(1, "1", 1, 100, matching_anchor_kinds=["miss"])
    row_anchorless = _row(2, "1", 2, 200, matching_anchor_kinds=[])

    miss_cand, cursor = assemble_candidate(row_miss, units, 0)
    assert miss_cand["outcome"] == "miss"
    assert cursor == 0

    hit_cand, cursor = assemble_candidate(row_anchorless, units, cursor)
    assert hit_cand["outcome"] == "hit"
    assert cursor == 1


def test_units_exhausted_yields_unfilled_not_guessed() -> None:
    units = [_unit("1", "Paid Perk", "Quality")]
    row1 = _row(1, "1", 1, 100, matching_anchor_kinds=[])
    row2 = _row(2, "1", 2, 200, matching_anchor_kinds=[])

    hit_cand, cursor = assemble_candidate(row1, units, 0)
    assert hit_cand["outcome"] == "hit"
    assert cursor == 1

    unfilled_cand, cursor = assemble_candidate(row2, units, cursor)
    assert unfilled_cand["outcome"] is None
    assert unfilled_cand["constellation"] is None
    assert unfilled_cand["perks"] == []
    assert {"outcome", "constellation", "perks"} <= set(
        unfilled_cand["_derivation"]["unfilled_fields"]
    )
    assert cursor == 1  # nothing left to consume, cursor stays put


def test_no_evidence_roll_emits_unfilled_candidate_not_omitted() -> None:
    row = _row(
        1, "1", 1, 100,
        evidence_kind="no_evidence",
        matching_anchor_kinds=[],
    )

    candidate, cursor = assemble_candidate(row, [], 0)

    assert candidate is not None
    assert candidate["outcome"] is None
    assert candidate["_derivation"]["unfilled_fields"]
    assert cursor == 0


def test_partial_bundle_marks_unmatched_free_perk_unfilled() -> None:
    row = _row(1, "1", 1, 0, matching_anchor_kinds=["acquisition"])
    units = [_unit(
        "1", "Paid Perk", "Quality",
        free_names=("Nonexistent Perk Name",),
    )]
    html = "I felt my power connect. The Paid Perk arrived with a flourish."
    word_index = _build_word_index(html)

    candidate, cursor = assemble_candidate(
        row, units, 0, chapter_html=html, word_index=word_index,
    )

    assert candidate["perks"] == ["Paid Perk", "Nonexistent Perk Name"]
    assert candidate["constellation"] == "Quality"
    assert candidate["evidence_quotes"] == []
    assert "evidence_for:Nonexistent Perk Name" in candidate["_derivation"]["unfilled_fields"]


def test_evidence_quote_text_is_always_a_literal_prose_substring() -> None:
    row = _row(1, "1", 1, 0, matching_anchor_kinds=["acquisition"])
    units = [_unit("1", "Paid Perk", "Quality", free_names=("Altmode",))]
    prose_string = (
        "I felt my power connect. It also gave me an alt-mode chassis "
        "that folded neatly into a briefcase."
    )
    word_index = _build_word_index(prose_string)

    candidate, cursor = assemble_candidate(
        row, units, 0, chapter_html=prose_string, word_index=word_index,
    )

    assert candidate["evidence_quotes"], candidate["_derivation"]["unfilled_fields"]
    for quote in candidate["evidence_quotes"]:
        assert quote["text"] in prose_string
