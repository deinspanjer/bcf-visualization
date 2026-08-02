from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_candidate_rolls import assemble_all_candidates  # noqa: E402


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
        _obtained_perk("9001", 1, "Altmode", 100, "Testing"),
        _obtained_perk("9001", 2, "Laser Sword", 0, None),
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
    assert "Altmode" in hit["perks"] and "Laser Sword" in hit["perks"]
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
