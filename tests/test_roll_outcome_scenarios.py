from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from derive_roll_outcomes import _build_chapter_slots  # noqa: E402


def _predicted(
    *positions: int,
    chapter_num: str = "1",
    cp_rule_regime: int | None = 1,
) -> list[dict]:
    return [
        {
            "chapter_num": chapter_num,
            "word_position": position,
            "roll_number": index,
            "cp_rule_regime": cp_rule_regime,
            "roll_trigger_cp_threshold": index * 100,
        }
        for index, position in enumerate(positions, start=1)
    ]


def _perk(name: str, *, cost: int = 100, free: bool = False, seq: int = 1) -> dict:
    return {
        "perk_name": name,
        "constellation": "Toolkits",
        "jump": "Fixture Jump",
        "cost": cost,
        "free": free,
        "epub_sequence": seq,
    }


def _unit(
    *paid: dict,
    free_perks: list[dict] | None = None,
    chapter_num: str = "1",
) -> dict:
    return {
        "chapter_num": chapter_num,
        "paid": list(paid),
        "free_perks": free_perks or [],
    }


def test_roll_outcomes_spread_hits_across_predicted_slots() -> None:
    slots, _banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(100, 200, 300, 400, 500),
        [
            _unit(_perk("First Hit", seq=1)),
            _unit(_perk("Second Hit", seq=2)),
        ],
        words=1000,
        transitions=[],
    )

    assert [slot["outcome"] for slot in slots] == [
        "miss",
        "hit",
        "miss",
        "hit",
        "miss",
    ]
    assert [slot["perk"]["name"] for slot in slots if slot["outcome"] == "hit"] == [
        "First Hit",
        "Second Hit",
    ]
    assert all(slot["source"] == "predicted" for slot in slots)


def test_roll_outcomes_make_all_predicted_slots_misses_when_no_hits() -> None:
    slots, _banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(100, 200, 300),
        [],
        words=1000,
        transitions=[],
    )

    assert [slot["outcome"] for slot in slots] == ["miss", "miss", "miss"]
    assert [slot["perk"] for slot in slots] == [None, None, None]
    assert all(slot["banked_cp_after_roll"] == slot["available_cp"] for slot in slots)


def test_roll_outcomes_synthesize_extra_slots_when_hits_exceed_predictions() -> None:
    slots, _banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(450),
        [
            _unit(_perk("First", seq=1)),
            _unit(_perk("Second", seq=2)),
            _unit(_perk("Third", seq=3)),
        ],
        words=900,
        transitions=[],
    )

    assert [slot["outcome"] for slot in slots] == ["hit", "hit", "hit"]
    assert [slot["source"] for slot in slots].count("synthetic") == 2
    assert [slot["rolls_in_chapter"] for slot in slots] == [3, 3, 3]
    assert [slot["sequence_in_chapter"] for slot in slots] == [1, 2, 3]
    assert [slot["perk"]["name"] for slot in slots] == ["First", "Second", "Third"]


def test_roll_outcomes_attach_multi_grab_and_free_perks_to_one_hit_slot() -> None:
    slots, _banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(100, 200),
        [
            _unit(
                _perk("Small Paid", cost=100, seq=1),
                _perk("Large Paid", cost=300, seq=2),
                free_perks=[_perk("Free Rider", cost=0, free=True, seq=3)],
            )
        ],
        words=1000,
        transitions=[],
    )

    hit = next(slot for slot in slots if slot["outcome"] == "hit")
    assert hit["perk"]["name"] == "Large Paid"
    assert [perk["name"] for perk in hit["paid_perks"]] == ["Small Paid", "Large Paid"]
    assert [perk["name"] for perk in hit["free_perks"]] == ["Free Rider"]
    assert hit["rolls_in_chapter"] == 2


def test_roll_outcomes_misses_do_not_debit_banked_cp() -> None:
    slots, banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(2000),
        [],
        words=4000,
        transitions=[],
    )

    assert slots[0]["available_cp"] == 100
    assert slots[0]["banked_cp_after_roll"] == 100
    assert banked == 200


def test_roll_outcomes_hits_debit_paid_cost_and_continue_banking() -> None:
    slots, banked, _shadow = _build_chapter_slots(
        "1",
        _predicted(2000),
        [_unit(_perk("Paid Hit", cost=100))],
        words=4000,
        transitions=[],
    )

    assert slots[0]["available_cp"] == 100
    assert slots[0]["banked_cp_after_roll"] == 0
    assert banked == 100


def test_roll_outcomes_apply_mid_chapter_regime_transition() -> None:
    slots, banked, _shadow = _build_chapter_slots(
        "97",
        _predicted(1000, 3000, chapter_num="97", cp_rule_regime=None),
        [_unit(_perk("Nano-Forge", cost=100), chapter_num="97")],
        words=4000,
        transitions=[
            {
                "chapter_num": "97",
                "new_regime": 3,
                "after_event": {
                    "kind": "perk_acquired",
                    "perk_name": "Nano-Forge",
                },
            }
        ],
    )

    assert [slot["cp_rule_regime"] for slot in slots] == [2, 3]
    assert [slot["available_cp"] for slot in slots] == [50, 133]
    assert slots[1]["banked_cp_after_roll"] == 33
    assert banked == 66


def test_roll_outcomes_carry_regime_three_shadow_after_large_hit() -> None:
    slots, banked, shadow = _build_chapter_slots(
        "98",
        _predicted(3000, chapter_num="98", cp_rule_regime=None),
        [_unit(_perk("Large Hit", cost=600), chapter_num="98")],
        words=6000,
        transitions=[],
    )

    assert slots[0]["cp_rule_regime"] == 3
    assert slots[0]["available_cp"] == 100
    assert slots[0]["banked_cp_after_roll"] == 0
    assert banked == 0
    assert shadow.remaining == 6000
