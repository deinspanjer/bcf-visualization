from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from multi_grab import (  # noqa: E402
    load_overrides as load_multi_grab_overrides,
    merge_paid_units,
    unit_principal_cost,
    unit_total_cost,
)
from predict_rolls import (  # noqa: E402
    CHAPTERS_JSON,
    OBTAINED_JSON,
    OUT as PREDICTED_ROLLS_JSON,
    _load_cp_words_per_chapter,
    _simulate,
)
from cp_epub_map import build_map, cp_to_epub  # noqa: E402
from regime_simulator import load_regime_transitions  # noqa: E402
from data_paths import DERIVED  # noqa: E402


ROLL_FACTS_JSON = DERIVED / "roll_facts.json"
CHAPTER_FACTS_JSON = DERIVED / "chapter_facts.json"


def _simulation_inputs() -> tuple[list[dict], dict[str, list[dict]], dict[str, int]]:
    chapters = sorted(
        json.loads(CHAPTERS_JSON.read_text())["chapters"],
        key=lambda c: tuple(c["sort_key"]),
    )
    obtained = sorted(
        json.loads(OBTAINED_JSON.read_text())["perks"],
        key=lambda p: p.get("epub_sequence", 0),
    )
    units, _stats = merge_paid_units(obtained, load_multi_grab_overrides())

    paid_by_chapter: dict[str, list[dict]] = {}
    for unit in units:
        paid_by_chapter.setdefault(unit["chapter_num"], []).append({
            "cost": unit_total_cost(unit),
            "principal_cost": unit_principal_cost(unit),
        })

    return chapters, paid_by_chapter, _load_cp_words_per_chapter()


def _simulated_rolls() -> tuple[list[dict], dict[str, int]]:
    chapters, paid_by_chapter, cp_words = _simulation_inputs()
    predicted, chapter_starts, _chapter_ends, _total_words = _simulate(
        chapters,
        paid_by_chapter,
        cp_words,
        load_regime_transitions(),
    )
    cp_map = build_map()
    slot_counter: dict[str, int] = {}
    for p in predicted:
        p.epub_offset = cp_to_epub(cp_map, p.cp_offset)
        slot_counter[p.chapter_num] = slot_counter.get(p.chapter_num, 0) + 1
        p.slot_index = slot_counter[p.chapter_num]
    return [asdict(roll) for roll in predicted], chapter_starts


def test_predicted_rolls_match_global_cp_simulator_and_regimes() -> None:
    expected, _chapter_starts = _simulated_rolls()
    actual = json.loads(PREDICTED_ROLLS_JSON.read_text())["predicted"]

    assert actual == expected


def test_canonical_roll_facts_preserve_mechanical_and_display_positions() -> None:
    predicted, chapter_starts = _simulated_rolls()
    predicted_by_position = {
        int(roll["cp_offset"]): roll
        for roll in predicted
    }

    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    chapter_facts = json.loads(CHAPTER_FACTS_JSON.read_text())["chapters"]
    chapter_fact_rolls = [
        roll | {"chapter_num": chapter["chapter_num"]}
        for chapter in chapter_facts
        for roll in chapter.get("rolls", [])
    ]

    for source_name, rolls in (
        ("roll_facts", roll_facts),
        ("chapter_facts", chapter_fact_rolls),
    ):
        for roll in rolls:
            if roll.get("source_kind") == "trigger":
                continue
            roll_number = roll.get("roll_number")
            if roll_number is None:
                continue
            if roll.get("mechanical_cumulative_word_offset") is None:
                continue
            if roll.get("predicted_word_position_epub") != roll.get(
                "mechanical_cumulative_word_offset"
            ):
                continue
            predicted_roll = predicted_by_position.get(
                int(roll["predicted_word_position_epub"])
            )
            if predicted_roll is None:
                continue
            mechanical_chapter_num = str(
                roll.get("mechanical_chapter_num") or roll["chapter_num"]
            )
            expected_global = int(predicted_roll["cp_offset"])
            expected_local = (
                expected_global - int(chapter_starts[mechanical_chapter_num])
            )

            assert roll["mechanical_cumulative_word_offset"] == expected_global, (
                f"{source_name} {roll.get('roll_key')} mechanical global position"
            )
            assert roll["mechanical_word_position"] == expected_local, (
                f"{source_name} {roll.get('roll_key')} mechanical local position"
            )
            assert roll["cumulative_word_offset"] == roll["display_cumulative_word_offset"], (
                f"{source_name} {roll.get('roll_key')} display alias global"
            )
            assert roll["word_position"] == roll["display_word_position"], (
                f"{source_name} {roll.get('roll_key')} display alias local"
            )
