from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.forge_curator_fixture import forge_curator_fixture


def test_roll_slot_rows_merge_assigned_rolls_and_open_predicted_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None

    unified = app._unified_rolls(cs)
    rows = app._roll_slot_rows(cs, unified)

    assert [
        (
            row["display_kind"],
            row["target_roll_index"],
            row["roll_number"],
            row["outcome"],
        )
        for row in rows
    ] == [
        ("chapter_roll", 1, 2, "miss"),
        ("predicted_slot", 2, 3, "open"),
    ]
    assert rows[0]["source"] == "curator_rolls"
    assert rows[1]["mechanical_cumulative_word_offset"] == 120


def test_deferred_predicted_slot_is_first_source_assignment_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    cs = app.state.chapter
    assert cs is not None

    targets = app._source_assignment_target_rows(cs)

    assert targets[0]["display_kind"] == "deferred_in"
    assert targets[0]["source_kind"] == "predicted_slot"
    assert targets[0]["target_chapter_num"] == "1"
    assert targets[0]["target_roll_index"] == 1
    assert targets[0]["visible_chapter_num"] == "2"
    assert targets[0]["mechanical_chapter_num"] == "1"
    assert targets[0]["mention_chapter_num"] == "2"
    assert targets[0]["use_stable_target_identity"] is False
    assert [(row["target_chapter_num"], row["target_roll_index"]) for row in targets] == [
        ("1", 1),
        ("2", 1),
        ("2", 2),
    ]


def test_same_chapter_rolls_remain_current_and_cross_chapter_display_is_deferred(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None

    current = app._unified_rolls(cs)[0]
    assert current["display_kind"] == "chapter_roll"
    assert current["target_chapter_num"] == "2"

    cs.derived.roll_facts = [
        {
            "roll_number": 99,
            "chapter_num": "2",
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "2",
            "display_word_position": 24,
            "display_cumulative_word_offset": 104,
            "mention_chapter_num": "2",
            "mention_word_position": 24,
            "display_position_policy": "mention",
            "source_kind": "miss",
            "source": "curator_rolls",
            "outcome": "miss",
            "available_cp": 100,
            "evidence_quotes": [],
            "word_position": 20,
            "raw_word_position": 24,
        }
    ]

    deferred = app._unified_rolls(cs)
    assert len(deferred) == 1
    assert deferred[0]["display_kind"] == "deferred_in"
    assert deferred[0]["target_chapter_num"] == "1"
    assert deferred[0]["word_position"] == 24


def test_deferred_predicted_slot_projects_explicit_source_roll_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    app.persistence.assign_source_roll_at_index("1", 1, 2)
    cs = app.state.chapter
    assert cs is not None

    deferred = app._deferred_predicted_slot_rolls(cs)

    assert len(deferred) == 1
    assert deferred[0]["target_chapter_num"] == "1"
    assert deferred[0]["target_roll_index"] == 1
    assert deferred[0]["source_roll_number"] == 2
    assert deferred[0]["roll_number"] == 2
    assert deferred[0]["outcome"] == "miss"
    assert deferred[0]["constellation"] == "Magic"


def test_roll_evidence_targets_include_deferred_and_source_only_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    deferred = {
        "display_kind": "deferred_in",
        "target_chapter_num": "1",
        "target_roll_index": 1,
        "word_position": 0,
        "outcome": "miss",
    }
    current = {
        "display_kind": "chapter_roll",
        "target_chapter_num": "2",
        "target_roll_index": 1,
        "word_position": 20,
        "roll_number": 2,
        "outcome": "hit",
    }
    source_only = {
        "display_kind": "chapter_roll",
        "target_chapter_num": "2",
        "target_roll_index": 3,
        "word_position": 40,
        "roll_number": 4,
        "outcome": "miss",
        "mechanical_word_position": None,
        "display_word_position": None,
    }
    skipped = {
        "display_kind": "predicted_slot",
        "target_chapter_num": "2",
        "target_roll_index": 2,
        "word_position": 40,
        "skipped": True,
    }
    app._unified_rolls = lambda _cs: [deferred, current, source_only]
    app._roll_slot_rows = lambda _cs, unified=None: [current, skipped]

    rows = app._roll_evidence_picker_rolls(cs)

    assert rows[0] == deferred
    assert any(row.get("roll_number") == 4 for row in rows)
    assert all(not row.get("skipped") for row in rows)


def test_open_predicted_slot_exposes_saved_quote_for_evidence_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text="open slot quote",
        mention_chapter_num="2",
        mention_word_position=42,
    )
    cs = app.state.chapter
    assert cs is not None

    rows = app._roll_slot_rows(cs)
    open_slot = next(
        row for row in rows
        if row.get("display_kind") == "predicted_slot"
        and row.get("target_chapter_num") == "2"
        and row.get("target_roll_index") == 2
    )

    assert open_slot["evidence_quotes"] == [
        {
            "text": "open slot quote",
            "mention_chapter_num": "2",
            "mention_word_position": 42,
        }
    ]


def test_roll_evidence_picker_groups_source_deferred_targets_with_deferred_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_source_roll_deferred_to_chapter("1", 2, "2")
    app.persistence.assign_source_roll_at_index("1", 2, 2)
    cs = app.state.chapter
    assert cs is not None
    source_projected = dict(cs.derived.roll_facts[0])
    source_projected.update(
        {
            "chapter_num": "1",
            "roll_sequence_in_chapter": 2,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "1",
            "display_word_position": 20,
            "display_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_roll_index": 1,
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]

    rows = app._roll_evidence_picker_rolls(cs)

    assert rows[0]["display_kind"] == "source_deferred"
    assert rows[0]["target_chapter_num"] == "1"
    assert rows[0]["target_roll_index"] == 2
    assert rows[0]["source_roll_number"] == 2


def test_beginning_quote_defaults_to_visible_deferred_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    deferred = {
        "display_kind": "deferred_in",
        "target_chapter_num": "1",
        "target_roll_index": 1,
        "word_position": 0,
        "outcome": "miss",
    }
    current = {
        "display_kind": "chapter_roll",
        "target_chapter_num": "2",
        "target_roll_index": 1,
        "word_position": 20,
        "display_chapter_num": "2",
        "outcome": "miss",
    }
    app._unified_rolls = lambda _cs: [deferred, current]
    app._roll_slot_rows = lambda _cs, unified=None: [current]

    target = app._current_roll_evidence_target(word_idx=1)

    assert target is not None
    assert target["display_kind"] == "deferred_in"
    assert target["target_chapter_num"] == "1"
    assert target["target_roll_index"] == 1


def test_action_target_uses_mechanical_slot_when_visual_marker_is_later(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    cs = app.state.chapter
    assert cs is not None
    chapter_roll = next(
        roll for roll in cs.derived.roll_facts
        if str(roll.get("mechanical_chapter_num")) == "2"
    )
    chapter_roll["display_position_policy"] = "mention"
    chapter_roll["display_word_position"] = 60
    chapter_roll["display_cumulative_word_offset"] = 140
    chapter_roll["mention_word_position"] = 60

    target = app._current_roll_target(word_idx=21)

    assert target is not None
    assert target["display_kind"] == "chapter_roll"
    assert target["target_chapter_num"] == "2"
    assert target["target_roll_index"] == 1


def test_source_link_rows_include_deferred_source_and_normalize_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_source_roll_deferred_to_chapter("1", 1, "2")
    cs = app.state.chapter
    assert cs is not None

    rows = app._source_link_rows(cs, "2")
    deferred_source = next(
        row for row in rows
        if row.get("source_deferred_from_chapter") == "1"
        and row.get("source_deferred_from_index") == 1
    )
    open_target = next(
        row for row in rows
        if row.get("display_kind") == "predicted_slot"
        and row.get("target_chapter_num") == "2"
        and row.get("target_roll_index") == 2
    )

    assert deferred_source["roll_number"] == 1
    assert deferred_source["source_word_position"] == 20
    assert app._is_source_link_source(deferred_source) is True
    assert app._is_source_link_target(open_target) is True
    assert app._normalize_source_link_pair(deferred_source, open_target) == (
        open_target,
        deferred_source,
    )


def test_source_deferred_projection_keeps_mechanical_target_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    source_projected = dict(cs.derived.roll_facts[0])
    source_projected.update(
        {
            "chapter_num": "1",
            "roll_sequence_in_chapter": 1,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "1",
            "display_word_position": 20,
            "display_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_roll_index": 1,
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected]
    app.data.roll_facts["rolls"] = [source_projected]
    app.persistence.assign_source_roll_at_index("1", 1, 2)

    projected = app._unified_rolls(cs)[0]

    assert projected["display_kind"] == "source_deferred"
    assert projected["target_chapter_num"] == "1"
    assert projected["target_roll_index"] == 1
    assert projected["source_roll_number"] == 2
    assert app._is_source_link_source(projected) is False
    assert app._is_source_link_target(projected) is True
