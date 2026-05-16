from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.widgets import Button, OptionList, Static

from scripts.forge_curator.app import (
    ConstellationPicker,
    PerkPicker,
    RollEvidencePicker,
    RollVisualizationPicker,
    SourceLinkPicker,
)
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def _static_text(widget: Static) -> str:
    return str(getattr(widget, "_renderable", None) or widget.render())


def _rolls(count: int = 1) -> list[dict]:
    return [
        {
            "index": idx,
            "roll_number": idx,
            "outcome": "hit",
        }
        for idx in range(1, count + 1)
    ]


def test_roll_evidence_picker_labels_selected_rolls() -> None:
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda _indices, _display_policy: None,
    )
    button = Button(picker._roll_button_label(1, picker._rolls[0]), name="1")

    assert str(button.label).startswith("( ) #1")

    picker._on_pressed(Button.Pressed(button))
    assert str(button.label).startswith("(x) #1")

    picker._on_pressed(Button.Pressed(button))
    assert str(button.label).startswith("( ) #1")


def test_roll_evidence_picker_keyboard_bindings_toggle_and_confirm() -> None:
    bindings = {binding.key: binding.action for binding in RollEvidencePicker.BINDINGS}

    assert bindings["space"] == "toggle_focused_roll"
    assert bindings["enter"] == "confirm_selection"


def test_roll_evidence_picker_can_leave_display_position_unchanged() -> None:
    selected: list[tuple[list[int], str | None]] = []
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda indices, display_policy: selected.append(
            (indices, display_policy)
        ),
    )

    picker._selected.add(1)
    assert picker._display_position_policy is None
    assert picker._display_position_label() == "Display marker: predicted"

    picker._toggle_display_position_policy()
    assert picker._display_position_policy == "mention"
    assert picker._display_position_label() == "Display marker: quote"

    picker.action_confirm_selection()
    assert selected == [([1], "mention")]


def test_roll_evidence_picker_space_toggles_focused_display_policy() -> None:
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda _indices, _display_policy: None,
    )
    button = Button(picker._display_position_label(), id="display_policy")
    picker.focused = button

    picker.action_toggle_focused_roll()

    assert picker._display_position_policy == "mention"
    assert str(button.label) == "Display marker: quote"


def test_roll_evidence_picker_space_action_toggles_focused_roll() -> None:
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda _indices, _display_policy: None,
    )
    button = Button(picker._roll_button_label(1, picker._rolls[0]), name="1")
    picker.focused = button

    picker.action_toggle_focused_roll()

    assert picker._selected == {1}
    assert str(button.label).startswith("(x) #1")


def test_roll_evidence_picker_label_uses_stable_target_index() -> None:
    picker = RollEvidencePicker(
        rolls=[
            {
                "index": 4,
                "target_roll_index": 3,
                "roll_number": 19,
                "outcome": "hit",
            },
        ],
        on_confirm=lambda _indices, _display_policy: None,
    )

    assert picker._roll_button_label(1, picker._rolls[0]).startswith("( ) #3")


def test_roll_visualization_picker_can_select_quote_mechanical_and_cursor() -> None:
    selected: list[dict] = []
    picker = RollVisualizationPicker(
        roll={
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 100,
            "mention_chapter_num": "3",
            "mention_word_position": 20,
            "display_position_policy": "mention",
            "evidence_quotes": [
                {"text": "first quote", "mention_chapter_num": "2", "mention_word_position": 10},
                {"text": "second quote", "mention_chapter_num": "3", "mention_word_position": 20},
            ],
        },
        cursor_chapter_num="2",
        cursor_word_position=30,
        on_select=selected.append,
    )

    picker._select("quote_1")
    picker._select("mechanical")
    picker._select("cursor")

    assert selected == [
        {
            "mention_chapter_num": "3",
            "mention_word_position": 20,
            "display_position_policy": "mention",
        },
        {
            "mention_chapter_num": "3",
            "mention_word_position": 20,
            "display_position_policy": "mechanical",
        },
        {
            "mention_chapter_num": "2",
            "mention_word_position": 30,
            "display_position_policy": "mention",
        },
    ]


def test_roll_visualization_picker_quote_buttons_use_valid_ids() -> None:
    selected: list[dict] = []
    picker = RollVisualizationPicker(
        roll={
            "mechanical_chapter_num": "2",
            "mechanical_word_position": 100,
            "evidence_quotes": [
                {"text": "first quote", "mention_chapter_num": "2", "mention_word_position": 10},
            ],
        },
        cursor_chapter_num="2",
        cursor_word_position=30,
        on_select=selected.append,
    )

    button = Button("Quote 1", id="quote_0")
    picker._select(button.id)

    assert selected == [
        {
            "mention_chapter_num": "2",
            "mention_word_position": 10,
            "display_position_policy": "mention",
        }
    ]


@pytest.mark.asyncio
async def test_roll_evidence_picker_splits_rolls_into_two_columns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")
    picker = RollEvidencePicker(
        rolls=_rolls(13),
        on_confirm=lambda _indices, _display_policy: None,
    )

    async with app.run_test(size=(180, 50)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        left = picker.query_one("#roll_column_left")
        right = picker.query_one("#roll_column_right")

        assert len(left.query("Button")) == 7
        assert len(right.query("Button")) == 6
        assert picker.query_one("#roll_1", Button).name == "1"
        assert picker.query_one("#roll_13", Button).name == "13"


def test_perk_picker_keyboard_bindings_toggle_and_confirm() -> None:
    bindings = {binding.key: binding.action for binding in PerkPicker.BINDINGS}

    assert bindings["space"] == "toggle_focused_perk"
    assert bindings["enter"] == "confirm_selection"


def test_perk_picker_space_action_toggles_focused_perk() -> None:
    picker = PerkPicker(
        perks=[
            {
                "name": "Fashion",
                "cost": 200,
            },
        ],
        on_confirm=lambda _names: None,
    )
    button = Button("Fashion  200", name="Fashion")
    picker.focused = button

    picker.action_toggle_focused_perk()

    assert picker._selected == {"Fashion"}
    assert "selected" in button.classes


@pytest.mark.asyncio
async def test_constellation_picker_digit_chords_select_constellation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")
    selected: list[str] = []

    async with app.run_test(size=(140, 40)) as pilot:
        app.push_screen(ConstellationPicker(on_select=selected.append))
        await pilot.pause()
        await pilot.press("1")
        await pilot.pause()

    assert selected == ["Alchemy"]

    selected.clear()
    app = fixture.app("1")
    async with app.run_test(size=(140, 40)) as pilot:
        app.push_screen(ConstellationPicker(on_select=selected.append))
        await pilot.pause()
        await pilot.press("0", "0")
        await pilot.pause()

    assert selected == ["Resources and Durability"]


@pytest.mark.asyncio
async def test_source_link_picker_supports_keyboard_only_selection_and_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("2")

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app._action_assign_source_roll("2")
        await pilot.pause()

        targets = app.screen.query_one("#source_link_targets", OptionList)
        sources = app.screen.query_one("#source_link_sources", OptionList)
        summary = app.screen.query_one("#source_link_summary", Static)

        assert app.screen.focused is targets
        assert targets.highlighted == 0
        assert sources.highlighted == 0
        assert "ch 2 #1" in _static_text(summary)
        assert "Roll 2" in _static_text(summary)

        await pilot.press("down", "enter")
        await pilot.pause()
        assert "ch 2 #2" in _static_text(summary)

        await pilot.press("tab", "enter")
        await pilot.pause()
        assert "Roll 2" in _static_text(summary)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, SourceLinkPicker)


@pytest.mark.asyncio
async def test_source_link_picker_keyboard_confirm_assigns_selected_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("2")

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        app._action_assign_source_roll("2")
        await pilot.pause()

        await pilot.press("down", "enter")
        await pilot.press("tab", "enter")
        await pilot.press("tab", "enter")
        await pilot.pause()

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert saved["source_roll_number"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
