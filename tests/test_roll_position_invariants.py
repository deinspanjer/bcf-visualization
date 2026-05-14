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
from regime_simulator import load_regime_transitions  # noqa: E402
from data_paths import DERIVED, MANUAL  # noqa: E402


ROLL_FACTS_JSON = DERIVED / "roll_facts.json"
CHAPTER_FACTS_JSON = DERIVED / "chapter_facts.json"
CHAPTER_ROLL_OVERRIDES_JSON = MANUAL / "chapter_roll_overrides.json"
CURATOR_ROLLS_JSON = DERIVED / "rolls.json"


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
    return [asdict(roll) for roll in predicted], chapter_starts


def test_predicted_rolls_match_global_cp_simulator_and_regimes() -> None:
    expected, _chapter_starts = _simulated_rolls()
    actual = json.loads(PREDICTED_ROLLS_JSON.read_text())["predicted"]

    assert actual == expected


def test_curator_roll_numbers_preserve_source_attempt_identity() -> None:
    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    numbered_curator_rolls = [
        roll
        for roll in roll_facts
        if roll.get("source") == "curator_rolls"
        and roll.get("source_kind") != "trigger"
        and roll.get("roll_number") is not None
    ]

    assert [roll["roll_number"] for roll in numbered_curator_rolls[:14]] == list(
        range(1, 15)
    )


def test_canonical_roll_facts_preserve_mechanical_and_display_positions() -> None:
    predicted, chapter_starts = _simulated_rolls()
    predicted_by_position = {
        int(roll["word_position"]): roll
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
            predicted_roll = predicted_by_position[
                int(roll["predicted_word_position_epub"])
            ]
            mechanical_chapter_num = str(
                roll.get("mechanical_chapter_num") or roll["chapter_num"]
            )
            expected_global = int(predicted_roll["word_position"])
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


def test_unpredicted_curator_roll_uses_explicit_curated_anchor() -> None:
    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    overrides = json.loads(CHAPTER_ROLL_OVERRIDES_JSON.read_text())
    expected_anchor = (
        overrides["chapter_roll_overrides"]["4"]["rolls"][4]["mention_word_position"]
    )
    roll = next(r for r in roll_facts if r.get("roll_key") == "curator:0014")

    assert roll["chapter_num"] == "4"
    assert roll["mechanical_chapter_num"] == "4"
    assert roll["source"] == "curator_rolls"
    assert roll["source_kind"] == "miss"
    assert roll["display_position_policy"] == "mention"
    assert roll["mention_word_position"] == expected_anchor
    assert roll["mechanical_word_position"] == expected_anchor
    assert roll["display_word_position"] == expected_anchor
    assert roll["word_position"] == expected_anchor


def test_deferred_source_assignment_is_one_roll_with_two_chapter_projections() -> None:
    _predicted, chapter_starts = _simulated_rolls()
    overrides = json.loads(CHAPTER_ROLL_OVERRIDES_JSON.read_text())[
        "chapter_roll_overrides"
    ]
    source_rolls: dict[tuple[str, int], dict] = {}
    source_seq_by_chapter: dict[str, int] = {}
    for row in json.loads(CURATOR_ROLLS_JSON.read_text())["rolls"]:
        if row.get("kind") not in {"roll", "miss"}:
            continue
        chapter_num = str(row["chapter_num"])
        seq = source_seq_by_chapter.get(chapter_num, 0) + 1
        source_seq_by_chapter[chapter_num] = seq
        source_rolls[(chapter_num, seq)] = row

    scenario = None
    for source_chapter, chapter_override in overrides.items():
        for source_index, source_override in enumerate(
            chapter_override.get("rolls") or [], start=1
        ):
            target_chapter = source_override.get("source_deferred_to_chapter")
            if target_chapter is None:
                continue
            source_row = source_rolls.get((str(source_chapter), source_index))
            if source_row is None or source_row.get("roll_number") is None:
                continue
            source_roll_number = int(source_row["roll_number"])
            target_rolls = overrides.get(str(target_chapter), {}).get("rolls") or []
            target_index = next(
                (
                    idx
                    for idx, target_override in enumerate(target_rolls, start=1)
                    if target_override.get("source_roll_number") == source_roll_number
                ),
                None,
            )
            if target_index is None:
                continue
            quote = next(
                (
                    q for q in source_override.get("evidence_quotes") or []
                    if str(q.get("mention_chapter_num")) == str(source_chapter)
                    and q.get("mention_word_position") is not None
                ),
                None,
            )
            scenario = (
                str(source_chapter),
                source_index,
                str(target_chapter),
                target_index,
                source_roll_number,
                quote,
            )
            break
        if scenario is not None:
            break

    assert scenario is not None
    (
        source_chapter,
        source_index,
        target_chapter,
        target_index,
        source_roll_number,
        quote,
    ) = scenario
    roll_facts = json.loads(ROLL_FACTS_JSON.read_text())["rolls"]
    matches = [
        roll for roll in roll_facts
        if roll.get("roll_number") == source_roll_number
    ]

    assert len(matches) == 1
    roll = matches[0]
    assert roll["source_chapter_num"] == source_chapter
    assert roll["source_roll_index"] == source_index
    assert roll["mechanical_chapter_num"] == target_chapter
    assert roll["roll_sequence_in_chapter"] == target_index
    assert set(roll["visible_chapter_nums"]) >= {source_chapter, target_chapter}
    assert roll["display_chapter_num"] == target_chapter
    if quote is not None:
        assert roll["source_word_position"] == quote["mention_word_position"]
        assert roll["source_cumulative_word_offset"] == (
            chapter_starts[source_chapter] + quote["mention_word_position"]
        )
