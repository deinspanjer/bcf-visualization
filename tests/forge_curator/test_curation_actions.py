from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.forge_curator.app import (
    QuoteMoveSourcePicker,
    QuoteMoveTargetPicker,
    RollEvidencePicker,
    SourceLinkPicker,
)
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def _selected_prose(selection: tuple[int, int]) -> SimpleNamespace:
    return SimpleNamespace(
        selection=selection,
        cursor=selection[0],
        anchor=selection[1],
        visual_mode=True,
        visual_line_mode=False,
        selected_text="",
        refresh=lambda: None,
    )


def test_save_quote_action_writes_manual_roll_evidence_and_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[24][0]
    end = cs.prose.word_offsets[27][1]
    refreshes: list[str] = []
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _selected_prose((start, end)))
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_save_quote("1")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {
            "text": cs.prose.text[start:end].strip(),
            "mention_chapter_num": "1",
            "mention_word_position": 24,
        }
    ]
    assert refreshes == [f"roll #1 quote saved ({len(cs.prose.text[start:end].strip())} chars)"]


def test_save_quote_targets_selection_start_not_visual_cursor_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[20][0]
    end = cs.prose.word_offsets[40][0]
    prose = _selected_prose((start, end))
    prose.cursor = end
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    app._post_curation_refresh = lambda _message: None

    app._action_save_quote("2")

    saved = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[0]["evidence_quotes"]
    assert len(saved) == 1


def test_save_quote_exits_visual_mode_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[20][0]
    end = cs.prose.word_offsets[23][1]
    prose = _selected_prose((start, end))
    prose.cursor = end
    prose.anchor = start
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    app._post_curation_refresh = lambda _message: None

    app._action_save_quote("2")

    assert prose.anchor is None
    assert prose.visual_mode is False
    assert prose.visual_line_mode is False


def test_multi_quote_persistence_creates_index_aligned_roll_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence

    persistence.append_roll_evidence_at_indices(
        "2",
        [1, 3],
        text="same quote",
        mention_chapter_num="2",
        mention_word_position=42,
    )

    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert len(rolls) == 3
    assert rolls[0]["evidence_quotes"] == [
        {"text": "same quote", "mention_chapter_num": "2", "mention_word_position": 42}
    ]
    assert rolls[1]["evidence_quotes"] == []
    assert rolls[2]["evidence_quotes"] == [
        {"text": "same quote", "mention_chapter_num": "2", "mention_word_position": 42}
    ]


def test_multi_quote_can_leave_deferred_roll_at_mechanical_visualization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence
    persistence.mark_roll_deferred_to_chapter("1", 1, "2")

    persistence.append_roll_evidence_at_indices(
        "1",
        [1],
        text="later quote",
        mention_chapter_num="2",
        mention_word_position=24,
        display_position_policy=None,
    )

    roll = persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "2"
    assert roll["mention_word_position"] is None
    assert roll["display_position_policy"] == "mechanical"
    assert roll["evidence_quotes"] == [
        {"text": "later quote", "mention_chapter_num": "2", "mention_word_position": 24}
    ]


def test_save_quote_multi_updates_deferred_predicted_target_and_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    monkeypatch.setattr(app, "_selected_quote", lambda _action_name: "chapter quote")
    monkeypatch.setattr(app, "_selected_quote_start_word_index", lambda: 24)
    monkeypatch.setattr(app, "_clear_prose_selection", lambda: None)
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    screens: list[RollEvidencePicker] = []
    app.push_screen = lambda screen: screens.append(screen)

    app._action_save_quote_multi("2")

    assert [type(screen) for screen in screens] == [RollEvidencePicker]
    target = next(
        roll for roll in screens[0]._rolls
        if roll.get("display_kind") == "deferred_in"
        and roll.get("target_chapter_num") == "1"
        and roll.get("target_roll_index") == 1
    )
    screens[0]._on_confirm([screens[0]._rolls.index(target) + 1], None)

    roll = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {
            "text": "chapter quote",
            "mention_chapter_num": "2",
            "mention_word_position": 24,
        }
    ]
    assert refreshes == ["quote saved to rolls ch 1 #1"]
    deferred = app._deferred_predicted_slot_rolls(app.state.chapter)
    assert deferred[0]["evidence_quotes"] == roll["evidence_quotes"]
    assert app._roll_evidence_marker(deferred[0]) == "Q"


def test_delete_annotation_removes_quote_from_open_predicted_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    quote_start = cs.prose.text.find("cursor chapter2 forge")
    assert quote_start >= 0
    quote = cs.prose.text[quote_start:quote_start + len("cursor chapter2 forge")]
    quote_word = 39
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text=quote,
        mention_chapter_num="2",
        mention_word_position=quote_word,
    )
    prose = _selected_prose((quote_start, quote_start + len(quote)))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )
    flashes: list[str] = []
    app._flash = lambda message: flashes.append(message)

    app._action_remove_annotations_at_current_word("2")

    saved = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert saved["evidence_quotes"] == []
    assert refreshes == [("annotation delete: 0 eligibility, 1 roll evidence", False)]


def test_reassign_quote_moves_saved_metadata_without_reselecting_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_source_roll_deferred_to_chapter("1", 2, "2")
    app.persistence.assign_source_roll_at_index("1", 2, 1)
    app.persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
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
            "evidence_quotes": [],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]
    quote_start = cs.prose.text.find("forge motes connection")
    assert quote_start >= 0
    prose = _selected_prose((quote_start, quote_start + len("forge motes connection")))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        assert isinstance(screen, QuoteMoveTargetPicker)
        target = next(
            roll for roll in screen._rolls
            if roll.get("display_kind") == "source_deferred"
            and roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 2
        )
        screen._select(screen._rolls.index(target) + 1)

    app.push_screen = push_screen

    app._action_reassign_roll_quote("2")

    overrides = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert overrides["2"]["rolls"][0]["evidence_quotes"] == []
    assert overrides["1"]["rolls"][1]["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["quote moved to ch 1 #2"]
    assert [type(screen) for screen in screens] == [QuoteMoveTargetPicker]


def test_reassign_quote_requires_source_choice_when_quotes_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    quote_start = cs.prose.text.find("forge motes connection")
    assert quote_start >= 0
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
    prose = _selected_prose((quote_start, quote_start + len("forge motes connection")))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        if isinstance(screen, QuoteMoveSourcePicker):
            source = next(
                candidate for candidate in screen._sources
                if candidate["target_chapter"] == "2"
                and candidate["target_index"] == 2
            )
            screen._select(screen._sources.index(source) + 1)
            return
        assert isinstance(screen, QuoteMoveTargetPicker)
        target = next(
            roll for roll in screen._rolls
            if roll.get("target_chapter_num") == "2"
            and roll.get("target_roll_index") == 1
        )
        screen._select(screen._rolls.index(target) + 1)

    app.push_screen = push_screen

    app._action_reassign_roll_quote("2")

    overrides = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert overrides["2"]["rolls"][0]["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert overrides["2"]["rolls"][1]["evidence_quotes"] == []
    assert refreshes == ["quote moved to ch 2 #1"]
    assert [type(screen) for screen in screens] == [
        QuoteMoveSourcePicker,
        QuoteMoveTargetPicker,
    ]


def test_defer_roll_action_toggles_manual_deferral_and_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    selected_target = app._predicted_slot_rolls(cs)[0]
    app._current_roll_target = lambda: selected_target
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_defer_roll_to_next_chapter("1")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "2"
    assert roll["display_position_policy"] == "mechanical"
    assert refreshes == ["roll #1 evidence deferred to ch 2"]

    app._action_defer_roll_to_next_chapter("1")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "1"
    assert roll["display_position_policy"] == "mechanical"
    assert refreshes[-1] == "roll #1 evidence deferral cleared"


def test_defer_roll_action_on_deferred_row_clears_mechanical_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    target = app._deferred_predicted_slot_rolls(app.state.chapter)[0]
    app._current_roll_target = lambda: target
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_defer_roll_to_next_chapter("2")

    roll = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "1"
    assert roll["mention_word_position"] is None
    assert roll["display_position_policy"] == "mechanical"
    assert refreshes == ["roll #1 evidence deferral cleared"]


def test_defer_roll_action_on_source_roll_projects_source_to_next_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    target = app._roll_slot_rows(cs)[0]
    app._current_roll_target = lambda: target
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_defer_roll_to_next_chapter("1")

    saved = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert saved["source_deferred_to_chapter"] == "2"
    assert refreshes == ["roll #1 source Roll 1 deferred to ch 2"]

    next_app = fixture.loaded_app("2")
    source_rows = next_app._source_roll_picker_rows("2")
    deferred = next(
        row for row in source_rows
        if row.get("source_deferred_from_chapter") == "1"
        and row.get("source_deferred_from_index") == 1
    )
    assert deferred["roll_number"] == 1

    next_app._current_roll_target = lambda: {
        "target_chapter_num": "1",
        "target_roll_index": 1,
    }
    next_refreshes: list[str] = []
    next_app._post_curation_refresh = lambda message: next_refreshes.append(message)

    next_app._action_defer_roll_to_next_chapter("2")

    saved = next_app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert saved["source_deferred_to_chapter"] is None
    assert next_refreshes == ["roll #1 source deferral cleared"]


def test_selected_predicted_slot_actions_write_index_aligned_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    target = {
        "display_kind": "predicted_slot",
        "target_chapter_num": "2",
        "target_roll_index": 2,
    }
    app._selected_roll_target_if_visible = lambda: target
    app._post_curation_refresh = lambda _message, *, full=False: None

    app._select_roll_target(target)
    app._action_set_last_outcome("2", "miss")
    app._handle_space_chord("s")

    saved = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[1]["outcome"] is None
    assert saved[1]["skipped"] is True


def test_source_assignment_persistence_moves_duplicate_source_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence

    persistence.assign_source_roll_at_index("2", 2, 2)
    persistence.assign_source_roll_at_index("1", 1, 2)

    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert rolls["1"]["rolls"][0]["source_roll_number"] == 2
    assert rolls["2"]["rolls"][1]["source_roll_number"] is None


def test_source_assignment_action_links_open_target_to_source_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "predicted_slot"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("roll_number") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert [type(screen) for screen in screens] == [SourceLinkPicker]
    assert saved["source_roll_number"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 2 roll #2 source = Roll 2"]


def test_source_assignment_action_can_target_deferred_predicted_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "deferred_in"
            and roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 1
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("roll_number") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert saved["mention_chapter_num"] == "2"
    assert saved["source_roll_number"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 1 roll #1 source = Roll 2"]


def test_source_assignment_action_copies_deferred_source_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_source_roll_deferred_to_chapter("1", 1, "2")
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "predicted_slot"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_deferred_from_chapter") == "1"
            and roll.get("source_deferred_from_index") == 1
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch2_roll = overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    ch1_roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert ch1_roll["source_deferred_to_chapter"] == "2"
    assert ch2_roll["source_roll_number"] == 1
    assert ch2_roll["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "1",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 2 roll #2 source = Roll 1"]


def test_source_assignment_action_links_projected_source_to_mechanical_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    app.persistence.mark_source_roll_deferred_to_chapter("1", 2, "2")
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
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "source_deferred"
            and roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_deferred_from_chapter") == "1"
            and roll.get("source_deferred_from_index") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch1_roll = overrides["chapter_roll_overrides"]["1"]["rolls"][1]
    assert ch1_roll["source_roll_number"] == 2
    assert ch1_roll["source_deferred_to_chapter"] == "2"
    assert refreshes == ["ch 1 roll #2 source = Roll 2"]
