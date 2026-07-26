from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.build_exemplar_index import build_index  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders — small synthetic docs, never live repo data.
# ---------------------------------------------------------------------------

def _overrides_doc(chapters: dict) -> dict:
    return {
        "_purpose": "fixture",
        "chapter_roll_overrides": chapters,
    }


def _chapter_facts_doc(entries: list[dict]) -> dict:
    return {"schema_version": 1, "chapters": entries}


def _cf_entry(chapter_num: str, regime: int) -> dict:
    return {"chapter_num": chapter_num, "point_calculation_regime": regime}


def _roll(perks, outcome="hit", constellation="Quality",
          display_position_policy="mechanical", evidence_quotes=None):
    return {
        "perks": perks,
        "outcome": outcome,
        "constellation": constellation,
        "word_position": None,
        "display_position_policy": display_position_policy,
        "evidence_quotes": evidence_quotes or [],
    }


# ---------------------------------------------------------------------------
# 1. Every curated chapter appears with correct (non-boundary) regime tag.
# ---------------------------------------------------------------------------

def test_non_boundary_chapter_gets_single_regime_tag_from_chapter_facts() -> None:
    overrides = _overrides_doc({
        "1": {"rolls": [_roll(["Perk A"])]},
        "92": {"rolls": [_roll([])]},
    })
    chapter_facts = _chapter_facts_doc([
        _cf_entry("1", 1),
        _cf_entry("92", 2),
    ])

    index = build_index(overrides, chapter_facts, transitions=[])

    by_chapter = {e["chapter_num"]: e for e in index["exemplars"]}
    assert set(by_chapter) == {"1", "92"}
    assert by_chapter["1"]["regime_tags"] == [1]
    assert by_chapter["1"]["is_boundary"] is False
    assert by_chapter["92"]["regime_tags"] == [2]
    assert by_chapter["92"]["is_boundary"] is False


# ---------------------------------------------------------------------------
# 2. Chapter 97 dual-tagged {2, 3}, is_boundary True.
# ---------------------------------------------------------------------------

def test_ch97_boundary_chapter_dual_tagged_regardless_of_buggy_chapter_facts_value() -> None:
    overrides = _overrides_doc({
        "97": {"rolls": [_roll(["Additional Space"]), _roll(["Nano-Forge"])]},
    })
    # chapter_facts.json's point_calculation_regime for ch97 is currently
    # buggy (reads 3 due to build_chapter_facts.py's duplicate
    # regime_for_chapter — RESEARCH.md Pitfall 1). The boundary recipe must
    # be correct regardless of this value.
    chapter_facts = _chapter_facts_doc([_cf_entry("97", 3)])
    transitions = [
        {
            "chapter_num": "97",
            "after_event": {"kind": "perk_acquired", "perk_name": "Nano-Forge"},
            "new_regime": 3,
        }
    ]

    index = build_index(overrides, chapter_facts, transitions)

    ch97 = next(e for e in index["exemplars"] if e["chapter_num"] == "97")
    assert ch97["regime_tags"] == [2, 3]
    assert ch97["is_boundary"] is True


# ---------------------------------------------------------------------------
# 3. Determinism — byte-identical re-run.
# ---------------------------------------------------------------------------

def test_build_index_is_deterministic_across_repeated_calls() -> None:
    overrides = _overrides_doc({
        "97": {"rolls": [_roll(["A"]), _roll(["B"])]},
        "10": {"rolls": [_roll([])]},
        "5": {"rolls": [_roll(["C", "D"])]},
    })
    chapter_facts = _chapter_facts_doc([
        _cf_entry("97", 3),
        _cf_entry("10", 1),
        _cf_entry("5", 1),
    ])
    transitions = [
        {
            "chapter_num": "97",
            "after_event": {"kind": "perk_acquired", "perk_name": "Nano-Forge"},
            "new_regime": 3,
        }
    ]

    first = json.dumps(build_index(overrides, chapter_facts, transitions), sort_keys=True)
    second = json.dumps(build_index(overrides, chapter_facts, transitions), sort_keys=True)

    assert first == second

    # Chapters are ordered deterministically (numeric ascending), not
    # dict-insertion order.
    index = build_index(overrides, chapter_facts, transitions)
    assert [e["chapter_num"] for e in index["exemplars"]] == ["5", "10", "97"]


# ---------------------------------------------------------------------------
# 4. Malformed input raises ValueError loudly.
# ---------------------------------------------------------------------------

def test_missing_top_level_key_raises_value_error() -> None:
    malformed = {"_purpose": "no chapter_roll_overrides key here"}
    chapter_facts = _chapter_facts_doc([])

    with pytest.raises(ValueError, match="chapter_roll_overrides"):
        build_index(malformed, chapter_facts, transitions=[])


def test_curated_chapter_missing_from_chapter_facts_raises_value_error() -> None:
    overrides = _overrides_doc({"42": {"rolls": [_roll([])]}})
    chapter_facts = _chapter_facts_doc([])  # ch 42 absent

    with pytest.raises(ValueError, match="42"):
        build_index(overrides, chapter_facts, transitions=[])


# ---------------------------------------------------------------------------
# 5. Statistics — roll_shape_distribution and evidence_quote_stats.
# ---------------------------------------------------------------------------

def test_statistics_roll_shape_and_evidence_quote_distribution() -> None:
    overrides = _overrides_doc({
        "1": {"rolls": [
            _roll([]),  # 0-perk roll (miss/skip shape)
            _roll(["A", "B"], evidence_quotes=[{"text": "q1"}, {"text": "q2"}]),
        ]},
        "2": {"rolls": [
            _roll(["C"], evidence_quotes=[{"text": "q3"}]),
        ]},
    })
    chapter_facts = _chapter_facts_doc([_cf_entry("1", 1), _cf_entry("2", 1)])

    index = build_index(overrides, chapter_facts, transitions=[])
    stats = index["statistics"]

    assert stats["chapter_count"] == 2
    assert stats["roll_shape_distribution"] == {"0": 1, "1": 1, "2": 1}
    assert stats["evidence_quote_stats"]["min"] == 0
    assert stats["evidence_quote_stats"]["max"] == 2
    assert stats["evidence_quote_stats"]["total"] == 3
    assert stats["boundary_chapters"] == []


def test_cp_ledger_checkpoint_surfaced_from_evidence_quote_and_counted() -> None:
    overrides = _overrides_doc({
        "1": {"rolls": [
            _roll(
                ["A"],
                evidence_quotes=[{
                    "text": "banked reset",
                    "cp_ledger_checkpoint": {
                        "kind": "post_roll_banked_cp_reset",
                        "banked_cp_after_roll": 0,
                    },
                }],
            ),
            _roll(["B"]),
        ]},
    })
    chapter_facts = _chapter_facts_doc([_cf_entry("1", 1)])

    index = build_index(overrides, chapter_facts, transitions=[])
    ch1 = next(e for e in index["exemplars"] if e["chapter_num"] == "1")

    assert ch1["rolls"][0]["cp_ledger_checkpoint"] == {
        "kind": "post_roll_banked_cp_reset",
        "banked_cp_after_roll": 0,
    }
    assert ch1["rolls"][1]["cp_ledger_checkpoint"] is None
    assert index["statistics"]["cp_ledger_checkpoint_usage_count"] == 1
