from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App
from textual.containers import Container
from textual.widgets import Button, OptionList, Static

from scripts.forge_curator.app import (
    BatchMissQuotePicker,
    ConstellationPicker,
    GlobalRollNumberPrompt,
    PerkPicker,
    QuoteMoveSourcePicker,
    QuoteMoveTargetPicker,
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


def test_roll_evidence_picker_label_names_cross_chapter_target() -> None:
    picker = RollEvidencePicker(
        rolls=[
            {
                "index": 4,
                "target_chapter_num": "67",
                "target_roll_index": 5,
                "visible_chapter_num": "68",
                "roll_label": "R460",
                "predicted_label": "P487",
                "source_label": "S460",
                "outcome": "miss",
            },
        ],
        on_confirm=lambda _indices, _display_policy: None,
    )

    assert (
        picker._roll_button_label(1, picker._rolls[0])
        == "( ) ch 67 #5 (R460/P487/S460)  miss"
    )


def test_roll_evidence_picker_global_roll_button_uses_current_display_policy() -> None:
    selected: list[str | None] = []
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda _indices, _display_policy: None,
        on_global_roll=selected.append,
    )
    picker._display_position_policy = "mention"

    picker._on_pressed(Button.Pressed(Button("Enter roll ordinal", id="global_roll")))

    assert selected == ["mention"]


def test_global_roll_number_prompt_submits_stripped_roll_number() -> None:
    submitted: list[str] = []
    prompt = GlobalRollNumberPrompt(on_submit=submitted.append)

    prompt._submit(" 309 ")

    assert submitted == ["309"]


def test_batch_miss_quote_picker_defaults_to_confident_rows_only() -> None:
    selected: list[list[int]] = []
    picker = BatchMissQuotePicker(
        matches=[
            {
                "id": 1,
                "target_label": "ch 1 #1",
                "source_context": "source S1",
                "quote_text": "The Magic constellation missed a connection.",
                "mention_label": "ch 1:24",
                "distance_label": "+4 words",
                "reason_tags": ["constellation", "miss_language"],
                "default_selected": True,
            },
            {
                "id": 2,
                "target_label": "ch 1 #2",
                "source_context": "source S2",
                "quote_text": "The Time constellation moved nearby.",
                "mention_label": "ch 1:40",
                "distance_label": "+20 words",
                "reason_tags": ["ambiguous"],
                "default_selected": False,
            },
        ],
        on_confirm=selected.append,
    )

    assert picker._selected == {1}

    picker.action_confirm_selection()

    assert selected == [[1]]


def test_batch_miss_quote_picker_label_preserves_full_quote_text() -> None:
    long_quote = (
        "The Magic constellation missed a connection while Joe was trying "
        "to keep the conversation on track and the scene continued with "
        "enough context to judge the match."
    )
    picker = BatchMissQuotePicker(
        matches=[
            {
                "id": 1,
                "target_label": "ch 1 #1",
                "source_context": "roll, R1, constellation Magic",
                "quote_text": long_quote,
                "mention_label": "ch 1:24",
                "distance_label": "+4 words",
                "reason_tags": ["constellation", "miss_language"],
                "default_selected": True,
            },
        ],
        on_confirm=lambda _ids: None,
    )

    label = picker._match_button_label(picker._matches[0])

    assert long_quote in label
    assert "..." not in label


def test_batch_miss_quote_picker_can_widen_and_narrow_focused_match() -> None:
    picker = BatchMissQuotePicker(
        matches=[
            {
                "id": 1,
                "target_label": "ch 1 #1",
                "source_context": "roll, R1, constellation Clothing",
                "quote_text": "the Clothing constellation missed a connection",
                "mention_label": "ch 1:24",
                "distance_label": "+4 words",
                "reason_tags": ["constellation", "miss_language"],
                "default_selected": True,
                "variant_index": 0,
                "quote_variants": [
                    {
                        "label": "focused",
                        "text": "the Clothing constellation missed a connection",
                        "mention_label": "ch 1:24",
                        "distance_label": "+4 words",
                        "record": {
                            "text": "the Clothing constellation missed a connection",
                            "mention_word_position": 24,
                        },
                    },
                    {
                        "label": "sentence",
                        "text": "The second duplicate quipped as the Clothing constellation missed a connection.",
                        "mention_label": "ch 1:20",
                        "distance_label": "+0 words",
                        "record": {
                            "text": "The second duplicate quipped as the Clothing constellation missed a connection.",
                            "mention_word_position": 20,
                        },
                    },
                ],
                "record": {
                    "text": "the Clothing constellation missed a connection",
                    "mention_word_position": 24,
                },
            },
        ],
        on_confirm=lambda _ids: None,
    )
    picker.focused = Button("match", name="1")

    picker.action_widen_focused_match()

    match = picker._matches[0]
    assert match["quote_text"] == (
        "The second duplicate quipped as the Clothing constellation missed a connection."
    )
    assert match["record"]["mention_word_position"] == 20

    picker.action_narrow_focused_match()

    assert match["quote_text"] == "the Clothing constellation missed a connection"
    assert match["record"]["mention_word_position"] == 24


def test_batch_miss_quote_picker_starts_with_scanning_status() -> None:
    picker = BatchMissQuotePicker(on_confirm=lambda _ids: None)

    assert picker._status == "Scanning for miss quote matches..."

    picker.set_matches([])

    assert picker._status == "No likely unquoted miss evidence found"


@pytest.mark.asyncio
async def test_batch_miss_quote_picker_populates_matches_after_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")
    picker = BatchMissQuotePicker(on_confirm=lambda _ids: None)

    async with app.run_test(size=(120, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        assert "Scanning for miss quote matches..." in _static_text(
            picker.query_one("#miss_quote_status", Static)
        )

        picker.set_matches([
            {
                "id": 1,
                "target_label": "ch 1 #1",
                "source_context": "roll, R1, constellation Magic",
                "quote_text": "The Magic constellation missed a connection.",
                "mention_label": "ch 1:24",
                "distance_label": "+4 words",
                "reason_tags": ["constellation", "miss_language"],
                "default_selected": True,
            },
        ])
        await pilot.pause()

        assert "1 match candidate found" in _static_text(
            picker.query_one("#miss_quote_status", Static)
        )
        assert picker.query_one("#miss_quote_1", Button).name == "1"


@pytest.mark.asyncio
async def test_batch_miss_quote_picker_status_line_stays_below_match_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")
    picker = BatchMissQuotePicker(on_confirm=lambda _ids: None)

    async with app.run_test(size=(120, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        child_ids = [
            child.id for child in picker.query_one(Container).children
            if child.id is not None
        ]

        assert child_ids.index("miss_quote_matches") < child_ids.index("miss_quote_status")
        assert child_ids.index("miss_quote_status") < child_ids.index("confirm")


def test_quote_move_target_picker_selects_one_roll() -> None:
    selected: list[dict] = []
    picker = QuoteMoveTargetPicker(
        rolls=[
            {"target_chapter_num": "2", "target_roll_index": 1, "roll_number": 2},
            {"target_chapter_num": "1", "target_roll_index": 1, "roll_number": 1},
        ],
        on_select=selected.append,
    )

    picker._select(2)

    assert selected == [
        {"target_chapter_num": "1", "target_roll_index": 1, "roll_number": 1}
    ]


def test_quote_move_source_picker_selects_quote_owner() -> None:
    selected: list[dict] = []
    picker = QuoteMoveSourcePicker(
        sources=[
            {
                "target_chapter": "2",
                "target_index": 1,
                "quote": {"text": "first"},
            },
            {
                "target_chapter": "2",
                "target_index": 2,
                "quote": {"text": "second"},
            },
        ],
        on_select=selected.append,
    )

    picker._select(2)

    assert selected == [
        {
            "target_chapter": "2",
            "target_index": 2,
            "quote": {"text": "second"},
        }
    ]


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


@pytest.mark.asyncio
async def test_roll_evidence_picker_places_global_roll_next_to_display_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")
    picker = RollEvidencePicker(
        rolls=_rolls(),
        on_confirm=lambda _indices, _display_policy: None,
        on_global_roll=lambda _display_policy: None,
    )

    async with app.run_test(size=(120, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        action_row = picker.query_one("#roll_evidence_actions")

        assert picker.query_one("#display_policy", Button).parent is action_row
        assert picker.query_one("#global_roll", Button).parent is action_row


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
    button = Button("( ) Fashion  200", id="p_1", name="Fashion")
    picker.focused = button

    picker.action_toggle_focused_perk()

    assert picker._selected == {"Fashion"}
    assert "selected" in button.classes
    assert str(button.label) == "(x) Fashion  200"


@pytest.mark.asyncio
async def test_perk_picker_uses_perk_name_from_derived_perks() -> None:
    app = App()
    picker = PerkPicker(
        perks=[
            {
                "perk_name": "Lofty Loft",
                "cost": 100,
            },
            {
                "perk_name": "Underside",
                "cost": 200,
            },
        ],
        on_confirm=lambda _names: None,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        perk_buttons = [
            button for button in app.screen.query(Button)
            if button.id != "confirm"
        ]

    assert [button.name for button in perk_buttons] == [
        "Lofty Loft",
        "Underside",
    ]
    assert [str(button.label) for button in perk_buttons] == [
        "( ) Lofty Loft  100",
        "( ) Underside  200",
    ]


@pytest.mark.asyncio
async def test_perk_picker_marks_initial_selected_perks() -> None:
    app = App()
    picker = PerkPicker(
        perks=[
            {
                "perk_name": "Lofty Loft",
                "cost": 100,
            },
            {
                "perk_name": "Underside",
                "cost": 200,
            },
        ],
        initial_selected=["Lofty Loft"],
        on_confirm=lambda _names: None,
    )

    async with app.run_test(size=(100, 30)) as pilot:
        app.push_screen(picker)
        await pilot.pause()

        perk_buttons = [
            button for button in app.screen.query(Button)
            if button.id != "confirm"
        ]

    assert picker._selected == {"Lofty Loft"}
    assert [str(button.label) for button in perk_buttons] == [
        "(x) Lofty Loft  100",
        "( ) Underside  200",
    ]


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
        assert "S2" in _static_text(summary)

        await pilot.press("down", "enter")
        await pilot.pause()
        assert "ch 2 #2" in _static_text(summary)

        await pilot.press("tab", "enter")
        await pilot.pause()
        assert "S2" in _static_text(summary)

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
    assert saved["source_ordinal"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
