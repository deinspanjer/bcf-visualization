from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_grab import load_overrides, merge_paid_units  # noqa: E402


ROLL_FACTS_JSON = ROOT / "data" / "derived" / "roll_facts.json"
ROLL_VALIDATION_JSON = ROOT / "data" / "derived" / "roll_validation.json"
CHAPTER_FACTS_JSON = ROOT / "data" / "derived" / "chapter_facts.json"


def _perk(
    chapter_num: str,
    name: str,
    *,
    cost: int = 100,
    free: bool = False,
    seq: int = 1,
) -> dict:
    return {
        "epub_sequence": seq,
        "chapter_num": chapter_num,
        "chapter_full_title": f"{chapter_num} Test",
        "perk_name": name,
        "classification": None,
        "jump": "Test Jump",
        "cost": cost,
        "cost_text": "Free" if free else str(cost),
        "free": free,
        "perk_text": "",
        "constellation": "Toolkits",
    }


def test_override_loader_defaults_deferred_roll_fields(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {
            "5": {
                "rolls": [
                    {"perks": ["Same Chapter"], "outcome": "hit"},
                    {
                        "perks": ["Later Chapter"],
                        "outcome": "hit",
                        "mention_chapter_num": "6",
                        "mention_word_position": 123,
                    },
                ],
            },
        },
    }))

    rolls = load_overrides(path)["chapter_roll_overrides"]["5"]["rolls"]

    assert rolls[0]["mention_chapter_num"] == "5"
    assert rolls[0]["mention_word_position"] is None
    assert rolls[0]["display_position_policy"] == "mechanical"
    assert rolls[1]["mention_chapter_num"] == "6"
    assert rolls[1]["mention_word_position"] == 123
    assert rolls[1]["display_position_policy"] == "mention"


def test_merge_paid_units_moves_deferred_hit_to_mechanical_chapter() -> None:
    obtained = [
        _perk("1", "Trigger Perk", cost=100, seq=1),
        _perk("2", "Fashion", cost=200, seq=2),
        _perk("2", "Free Tie", cost=0, free=True, seq=2),
    ]
    overrides = {
        "chapter_roll_overrides": {
            "1": {
                "rolls": [
                    {
                        "perks": [],
                        "outcome": "miss",
                    },
                    {
                        "perks": ["Fashion", "Free Tie"],
                        "outcome": "hit",
                        "mention_chapter_num": "2",
                        "display_position_policy": "mechanical",
                    },
                ],
            },
        },
    }

    with contextlib.redirect_stdout(io.StringIO()):
        units, _stats = merge_paid_units(obtained, overrides)

    assert len(units) == 1
    unit = units[0]
    assert unit["chapter_num"] == "1"
    assert unit["mention_chapter_num"] == "2"
    assert unit["display_position_policy"] == "mechanical"
    assert [p["perk_name"] for p in unit["paid"]] == ["Fashion"]
    assert [p["perk_name"] for p in unit["free_perks"]] == ["Free Tie"]


def test_merge_paid_units_ignores_unassigned_zero_cost_paid_perks() -> None:
    obtained = [
        _perk("1", "Discounted Trigger", cost=0, seq=1),
        _perk("1", "Narrative Hit", cost=100, seq=2),
    ]
    overrides = {
        "chapter_roll_overrides": {
            "1": {
                "rolls": [
                    {
                        "perks": ["Narrative Hit"],
                        "outcome": "hit",
                    },
                ],
            },
        },
    }

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        units, _stats = merge_paid_units(obtained, overrides)

    assert stdout.getvalue() == ""
    assert len(units) == 1
    assert [p["perk_name"] for p in units[0]["paid"]] == ["Narrative Hit"]


def test_chapter_1_fashion_is_deferred_to_chapter_2_roll_facts() -> None:
    rolls = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    fashion = next(
        r for r in rolls
        if any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
    )

    assert fashion["chapter_num"] == "2"
    assert fashion["mechanical_chapter_num"] == "1"
    assert fashion["roll_number"] == 2
    assert fashion["mechanical_cumulative_word_offset"] == 4000
    assert fashion["mention_word_position"] == 879
    assert fashion["display_position_policy"] == "mention"
    assert fashion["display_chapter_num"] == "2"
    assert fashion["display_word_position"] == 879
    assert fashion["display_cumulative_word_offset"] == 5217
    assert fashion["word_position"] == fashion["display_word_position"]
    assert fashion["cumulative_word_offset"] == fashion["display_cumulative_word_offset"]


def test_deferred_roll_validation_counts_mechanical_chapter() -> None:
    checks = {
        row["chapter_num"]: row
        for row in json.loads(ROLL_VALIDATION_JSON.read_text())["chapter_checks"]
    }

    assert checks["1"]["required_paid_roll_count"] == 1
    assert checks["1"]["known_attempt_count"] == 2
    assert checks["1"]["predicted_roll_count"] == 2
    assert checks["1"]["status"] == "ok"
    assert checks["2"]["known_attempt_count"] == 3


def test_chapter_facts_own_deferred_roll_by_mention_chapter() -> None:
    chapters = {
        row["chapter_num"]: row
        for row in json.loads(CHAPTER_FACTS_JSON.read_text())["chapters"]
    }
    ch1_rolls = chapters["1"]["rolls"]
    ch2_rolls = chapters["2"]["rolls"]
    fashion = next(
        r for r in ch2_rolls
        if any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
    )

    assert not any(
        any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
        for r in ch1_rolls
    )
    assert fashion["mechanical_chapter_num"] == "1"
    assert fashion["display_chapter_num"] == "2"
    assert fashion["display_word_position"] == 879
    assert fashion["display_word_position_epub"] == (
        chapters["1"]["total_word_count"] + 879
    )
    assert chapters["2"]["paid_perks_gained"] == 3
    assert chapters["2"]["perks_gained"] == 3
