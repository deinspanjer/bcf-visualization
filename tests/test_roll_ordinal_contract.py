from __future__ import annotations

import json

from scripts.data_paths import DERIVED


def _load_json(name: str) -> dict:
    return json.loads((DERIVED / name).read_text())


def test_manual_source_assignments_use_source_ordinals() -> None:
    data = json.loads((DERIVED.parent / "manual" / "chapter_roll_overrides.json").read_text())

    source_roll_number_paths = []
    for chapter_num, entry in (
        data.get("chapter_roll_overrides") or {}
    ).items():
        for index, roll in enumerate(entry.get("rolls") or [], start=1):
            if isinstance(roll, dict) and "source_roll_number" in roll:
                source_roll_number_paths.append(f"{chapter_num}#{index}")

    assert source_roll_number_paths == []


def test_manual_roll_overrides_do_not_use_legacy_deferral_fields() -> None:
    data = json.loads((DERIVED.parent / "manual" / "chapter_roll_overrides.json").read_text())

    legacy_paths = []
    legacy_fields = {"deferred_to_later_chapter", "source_deferred_to_chapter"}
    for chapter_num, entry in (
        data.get("chapter_roll_overrides") or {}
    ).items():
        for index, roll in enumerate(entry.get("rolls") or [], start=1):
            if not isinstance(roll, dict):
                continue
            for field in legacy_fields & roll.keys():
                legacy_paths.append(f"{chapter_num}#{index}:{field}")

    assert legacy_paths == []


def test_roll_facts_use_explicit_ordinal_families() -> None:
    data = _load_json("roll_facts.json")
    rolls = data["rolls"]

    assert rolls
    assert all("roll_number" not in roll for roll in rolls)

    non_trigger_rolls = [
        roll for roll in rolls
        if roll.get("source_kind") != "trigger"
    ]
    assert [roll["roll_ordinal"] for roll in non_trigger_rolls] == list(
        range(1, len(non_trigger_rolls) + 1)
    )

    for roll in rolls:
        for ordinal, label, prefix in (
            ("predicted_ordinal", "predicted_label", "P"),
            ("source_ordinal", "source_label", "S"),
            ("roll_ordinal", "roll_label", "R"),
            ("chapter_ordinal", "chapter_label", "C"),
        ):
            assert ordinal in roll
            assert label in roll
            if roll[ordinal] is None:
                assert roll[label] is None
            else:
                assert roll[label] == f"{prefix}{roll[ordinal]}"
        assert roll["association_source"] in {"auto", "curated", "none"}


def test_roll_ordinals_follow_mechanical_attempt_order() -> None:
    roll_data = _load_json("roll_facts.json")
    chapter_data = _load_json("chapters.json")
    chapter_order = {
        str(chapter["chapter_num"]): index
        for index, chapter in enumerate(
            sorted(chapter_data["chapters"], key=lambda chapter: tuple(chapter["sort_key"]))
        )
    }

    def owner_key(roll: dict) -> tuple:
        chapter_num = str(roll.get("mechanical_chapter_num") or roll["chapter_num"])
        return (
            chapter_order.get(chapter_num, 10**9),
            int(
                roll.get("mechanical_cumulative_word_offset")
                if roll.get("mechanical_cumulative_word_offset") is not None
                else roll.get("display_cumulative_word_offset")
                if roll.get("display_cumulative_word_offset") is not None
                else 10**12
            ),
            int(roll.get("source_ordinal") or 10**12),
            int(roll.get("source_row_index") or 0),
            str(roll.get("roll_key") or ""),
        )

    non_trigger_rolls = [
        roll for roll in roll_data["rolls"]
        if roll.get("source_kind") != "trigger"
    ]

    assert [roll["roll_ordinal"] for roll in non_trigger_rolls] == [
        roll["roll_ordinal"] for roll in sorted(non_trigger_rolls, key=owner_key)
    ]


def test_chapter_six_keeps_later_source_rolls_on_mechanical_slots() -> None:
    roll_data = _load_json("roll_facts.json")
    by_source = {
        roll["source_ordinal"]: roll
        for roll in roll_data["rolls"]
        if roll.get("source_ordinal") in {20, 21}
    }

    assert by_source[20]["predicted_ordinal"] == 20
    assert by_source[20]["mechanical_chapter_num"] == "6"
    assert by_source[20]["source_chapter_num"] == "6.1"
    assert by_source[21]["predicted_ordinal"] == 21
    assert by_source[21]["mechanical_chapter_num"] == "6"
    assert by_source[21]["source_chapter_num"] == "7"


def test_cross_chapter_direct_manual_row_keeps_explicit_source_identity() -> None:
    roll_data = _load_json("roll_facts.json")
    fashion = next(
        roll for roll in roll_data["rolls"]
        if roll.get("rolled_perk_name") == "Fashion"
        and roll.get("mechanical_chapter_num") == "1"
    )
    source_one_rows = [
        roll for roll in roll_data["rolls"]
        if roll.get("source_ordinal") == 1
    ]
    source_two_rows = [
        roll for roll in roll_data["rolls"]
        if roll.get("source_ordinal") == 2
    ]

    assert fashion["source_ordinal"] == 2
    assert fashion["source_chapter_num"] == "2"
    assert len(source_one_rows) == 1
    assert source_one_rows[0]["outcome"] == "miss"
    assert source_two_rows == [fashion]


def test_chapter_facts_use_r_and_c_for_visible_roll_identity() -> None:
    data = _load_json("chapter_facts.json")
    assert data["chapters"]

    for chapter in data["chapters"]:
        rolls = chapter["rolls"]
        assert all("roll_number" not in roll for roll in rolls)
        for roll in rolls:
            if roll.get("source_kind") == "trigger":
                assert roll["roll_ordinal"] is None
                assert roll["roll_label"] is None
            else:
                assert isinstance(roll["roll_ordinal"], int)
                assert roll["roll_label"] == f"R{roll['roll_ordinal']}"
                assert isinstance(roll["chapter_ordinal"], int)
                assert roll["chapter_label"] == f"C{roll['chapter_ordinal']}"


def test_visualization_predicted_rolls_use_predicted_identity() -> None:
    data = _load_json("visualization_facts.json")
    predicted_rolls = data["predicted_rolls"]

    assert predicted_rolls
    assert all("roll_number" not in roll for roll in predicted_rolls)
    for roll in predicted_rolls:
        assert roll["predicted_label"] == f"P{roll['predicted_ordinal']}"


def test_skipped_predicted_rolls_keep_p_and_x_but_no_r_or_s() -> None:
    data = _load_json("chapter_facts.json")
    skipped = [
        marker
        for chapter in data["chapters"]
        for marker in chapter["skipped_predicted_rolls"]
    ]
    assert skipped
    assert all("roll_number" not in marker for marker in skipped)

    for expected_x, marker in enumerate(skipped, start=1):
        assert marker["predicted_label"] == f"P{marker['predicted_ordinal']}"
        assert marker["skipped_ordinal"] == expected_x
        assert marker["skipped_label"] == f"X{expected_x}"
        assert marker["roll_ordinal"] is None
        assert marker["roll_label"] is None
        assert marker["source_ordinal"] is None
        assert marker["source_label"] is None


def test_predicted_only_roll_outcomes_do_not_claim_source_identity() -> None:
    data = _load_json("roll_facts.json")

    predicted_only = [
        roll for roll in data["rolls"]
        if roll.get("source") == "roll_outcomes"
        and roll.get("source_kind") == "interpolated"
    ]

    assert predicted_only
    for roll in predicted_only:
        assert roll["source_ordinal"] is None
        assert roll["source_label"] is None
        assert roll["association_source"] == "none"


def test_source_ordinals_identify_distinct_source_rows() -> None:
    data = _load_json("roll_facts.json")
    source_rows = [
        roll for roll in data["rolls"]
        if roll.get("source") == "curator_rolls"
        and roll.get("source_kind") in {"roll", "miss"}
        and roll.get("source_ordinal") is not None
    ]

    assert source_rows

    occurrence_by_ordinal: dict[int, set[tuple[str, int, str]]] = {}
    for roll in source_rows:
        occurrence_by_ordinal.setdefault(roll["source_ordinal"], set()).add((
            roll["source_chapter_num"],
            roll["source_chapter_ordinal"],
            roll["source_roll_label"],
        ))

    assert all(
        len(occurrences) == 1
        for occurrences in occurrence_by_ordinal.values()
    )

    unique_source_occurrences = [
        {
            "source_ordinal": source_ordinal,
            "source_chapter_num": next(iter(occurrences))[0],
            "source_chapter_ordinal": next(iter(occurrences))[1],
            "source_roll_label": next(iter(occurrences))[2],
        }
        for source_ordinal, occurrences in occurrence_by_ordinal.items()
    ]

    duplicate_labels = {
        occurrence["source_roll_label"]
        for occurrence in unique_source_occurrences
        if sum(
            1 for candidate in unique_source_occurrences
            if candidate["source_roll_label"] == occurrence["source_roll_label"]
        ) > 1
    }
    assert duplicate_labels
    for label in duplicate_labels:
        rows = [
            occurrence for occurrence in unique_source_occurrences
            if occurrence["source_roll_label"] == label
        ]
        assert len({roll["source_ordinal"] for roll in rows}) == len(rows)
