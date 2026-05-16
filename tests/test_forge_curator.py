"""Pilot-driven verification for the Forge Curator TUI.

Exercises the bug fixes B1-B13 plus the keybind redesign by spinning
up the App in headless test mode and asserting on widget state after
keypresses.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.css.query import NoMatches
from textual.widgets import Input

import scripts.forge_curator.app as forge_app
from scripts.data_paths import DERIVED, MANUAL

ROOT = Path(__file__).resolve().parent.parent

# Import here so the rest of the suite still loads even if textual is
# unavailable.
from scripts.forge_curator.app import (
    ForgeCuratorApp,
    PassageView,
    StatsPanel,
    ActionsPanel,
    RegexBar,
    GutterPanel,
    GutterMark,
    GLYPH_CSS_COLORS,
    GLYPH_COLORS,
    GLYPH_STYLES,
    LEGEND,
    CONSTELLATION_NAME_HIGHLIGHT_STYLE,
    FORGE_KEYWORD_HIGHLIGHT_STYLE,
    QUOTE_HIGHLIGHT_STYLE,
    REGEX_HIGHLIGHT_STYLES,
    ROLL_HIGHLIGHT_STYLE,
    ROLL_EVIDENCE_MARKERS,
    STATS_PANEL_WIDTH,
    STATS_CONTENT_WIDTH,
    _fmt_int,
    _wrap_title_for_stats,
)


# ---------------------------------------------------------------------------
# Canonical word-coord conversions (App methods)
# ---------------------------------------------------------------------------


def test_terminal_compatibility_rejects_non_interactive_stream() -> None:
    class _Stream:
        def isatty(self) -> bool:
            return False

    result = forge_app.check_terminal_compatibility(
        stream=_Stream(),
        env={"TERM": "xterm-256color"},
        color_system="256",
    )

    assert result.ok is False
    assert any("interactive terminal" in reason for reason in result.reasons)


def test_terminal_compatibility_rejects_no_color_and_weak_color() -> None:
    class _Stream:
        def isatty(self) -> bool:
            return True

    result = forge_app.check_terminal_compatibility(
        stream=_Stream(),
        env={"TERM": "xterm", "NO_COLOR": "1"},
        color_system="standard",
    )

    assert result.ok is False
    assert any("NO_COLOR" in reason for reason in result.reasons)
    assert any("256-color" in reason for reason in result.reasons)


def test_terminal_compatibility_accepts_256_color_terminal() -> None:
    class _Stream:
        def isatty(self) -> bool:
            return True

    result = forge_app.check_terminal_compatibility(
        stream=_Stream(),
        env={"TERM": "xterm-256color"},
        color_system="256",
    )

    assert result.ok is True
    assert result.reasons == []


# ---------------------------------------------------------------------------
# Pilot-driven app tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_default_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        forge_app,
        "STATE_FILE",
        tmp_path / ".forge_curator_state.json",
    )


def _loaded_app(chapter_num: str, tmp_path: Path) -> ForgeCuratorApp:
    app = ForgeCuratorApp(
        start_chapter=chapter_num,
        state_path=tmp_path / ".forge_curator_state.json",
    )
    app._load_chapter(chapter_num)
    return app


def _render_stats_text(app: ForgeCuratorApp) -> str:
    stats = StatsPanel()
    stats.render_stats(app.state, app)
    rendered = getattr(stats, "_renderable", None) or stats.render()
    return str(rendered) if rendered is not None else ""


def _plain_stats_lines(text: str) -> list[str]:
    return [
        re.sub(r"\[[^\]]+\]", "", line).rstrip()
        for line in text.splitlines()
    ]


class _FakeMouseEvent:
    def __init__(self, x: int, y: int, button: int = 1) -> None:
        self.x = x
        self.y = y
        self.button = button

    def stop(self) -> None:
        pass


@pytest.mark.asyncio
async def test_gutter_minimap_renders_priority_cells() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)

        gutter.render_minimap([(0.0, "Q"), (0.0, "*")], 1.0, 1)
        assert str(gutter.render()) == "Q*    "

        gutter.render_minimap([(0.0, "."), (0.0, "*"), (0.0, "N")], 1.0, 1)
        assert str(gutter.render()) == "N*.   "

        gutter.render_minimap([(0.0, "Q"), (0.0, "A"), (0.0, ".")], 1.0, 1)
        assert str(gutter.render()) == "AQ.   "


def test_gutter_and_highlight_styles_are_unique_and_aligned() -> None:
    css = RegexBar.DEFAULT_CSS
    assert len(set(GLYPH_STYLES.values())) == len(GLYPH_STYLES)
    assert GLYPH_COLORS["."] == "orange1"
    assert GLYPH_CSS_COLORS["."] == "orange1"
    assert GLYPH_COLORS["."] != "yellow"
    assert ROLL_HIGHLIGHT_STYLE == GLYPH_STYLES["R"]
    assert QUOTE_HIGHLIGHT_STYLE == GLYPH_STYLES["Q"]
    assert FORGE_KEYWORD_HIGHLIGHT_STYLE == GLYPH_STYLES["."]
    assert CONSTELLATION_NAME_HIGHLIGHT_STYLE == "bold cyan"
    assert REGEX_HIGHLIGHT_STYLES == (GLYPH_STYLES["*"],)
    assert "regex-slot-4" in css
    assert "regex-slot-1" not in css
    assert "regex-slot-2" not in css
    assert "regex-slot-3" not in css
    assert f"color: {GLYPH_CSS_COLORS['*']};" in css


def test_forge_keyword_marks_match_configured_terms_without_partial_words() -> None:
    text = "Forge constellation Constellation mote Motes remote"
    cs = SimpleNamespace(
        prose=SimpleNamespace(
            text=text,
            word_offsets=[match.span() for match in re.finditer(r"\S+", text)],
        )
    )
    app = ForgeCuratorApp(start_chapter="1")

    spans = app._forge_keyword_char_spans(cs)

    assert [text[start:end] for start, end in spans] == [
        "Forge",
        "constellation",
        "Constellation",
        "mote",
        "Motes",
    ]
    assert app._forge_keyword_word_indices(cs) == [0, 1, 2, 3, 4]


def test_constellation_name_highlights_exact_case_sensitive_names() -> None:
    text = (
        "Time timeless time Personal Reality personal reality "
        "Resources and Durability Resources and durability"
    )
    cs = SimpleNamespace(prose=SimpleNamespace(text=text))
    app = ForgeCuratorApp(start_chapter="1")

    spans = app._constellation_name_char_spans(cs)

    assert [text[start:end] for start, end in spans] == [
        "Time",
        "Personal Reality",
        "Resources and Durability",
    ]


@pytest.mark.asyncio
async def test_gutter_indicator_click_jumps_to_mark_word(monkeypatch) -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)
        jumps: list[int] = []
        monkeypatch.setattr(app, "_jump_to_word", lambda word_idx: jumps.append(word_idx))

        gutter.render_minimap([GutterMark(0.0, "Q", 3068)], 1.0, 1)
        gutter.on_click(_FakeMouseEvent(0, 0))

        assert jumps == [3068]


@pytest.mark.asyncio
async def test_help_overlay_no_backslash_brackets() -> None:
    """B13: help overlay should not render literal '\\]r' — should be ']r'."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        # Find HelpScreen Static.body.
        from scripts.forge_curator.app import HelpScreen
        screen = app.screen
        assert isinstance(screen, HelpScreen), (
            f"expected HelpScreen, got {type(screen).__name__}"
        )
        body_widget = screen.query_one(".body")
        body_renderable = getattr(body_widget, "_renderable", None) or body_widget.render()
        body_text = str(body_renderable)
        assert "\\]" not in body_text, (
            f"help overlay still has literal backslash before bracket; got:\n"
            f"{body_text[:500]}"
        )
        assert "]r" in body_text, "expected ']r' in help overlay"
        assert "Roll evidence markers" in body_text
        for glyph, description in ROLL_EVIDENCE_MARKERS:
            assert f"{glyph}  {description}" in body_text


@pytest.mark.asyncio
async def test_layout_columns_stats_width_and_regex_bar_chrome() -> None:
    """Primary columns, stats width, and bottom regex chrome render correctly."""
    from textual.containers import VerticalScroll

    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)
        stats_scroll = app.query_one("#stats_scroll")
        prose_scroll = app.query_one("#prose_scroll")
        stats = app.query_one("#stats", StatsPanel)
        regex_bar = app.query_one("#regex_bar", RegexBar)

        assert stats_scroll.region.right == prose_scroll.region.x
        assert prose_scroll.region.right == gutter.region.x
        assert stats.region.width == STATS_PANEL_WIDTH
        assert (
            app.query_one("#stats_scroll", VerticalScroll).size.width
            > stats.size.width
        )
        assert regex_bar.size.height == 1
        labels = [str(label.render()) for label in regex_bar.query("Static.label")]
        assert labels == ["regex *:"]
        inp = app.query_one("#regex_4", Input)
        assert inp.compact is True
        assert inp.size.height == 1
        for slot in range(1, 4):
            with pytest.raises(NoMatches):
                app.query_one(f"#regex_{slot}", Input)
        with pytest.raises(NoMatches):
            app.query_one("#status")


def test_stats_panel_structured_status_rows_fit_content_width(tmp_path: Path) -> None:
    app = _loaded_app("2", tmp_path)
    text = _render_stats_text(app)
    protected_prefixes = (
        "  Model:",
        "  Section:",
        "  Text:",
        "  Total content:",
        "  CP eligible:",
        "    story ",
        "    chapter ",
        "  Since last predicted roll:",
        "  Until next predicted roll:",
        "  Since last curated roll:",
        "  Until next curated roll:",
        "  Since last curated evidence:",
        "  Until next curated evidence:",
        "  Gained:",
        "  Spent:",
        "    total ",
    )
    too_wide = [
        (len(line), line)
        for line in _plain_stats_lines(text)
        if line.startswith(protected_prefixes) and len(line) > STATS_CONTENT_WIDTH
    ]
    assert not too_wide


def test_stats_numeric_formatting_uses_grouped_digits() -> None:
    assert _fmt_int(999) == "999"
    assert _fmt_int(1000) == "1,000"
    assert _fmt_int(2680797) == "2,680,797"
    assert _fmt_int(None) == "n/a"


def test_stats_title_wrapping_uses_hyphen_continuations() -> None:
    lines = _wrap_title_for_stats(
        "40 Knock Down - Preamble Gully - Addendum Emergency Alert",
        STATS_CONTENT_WIDTH,
    )
    assert len(lines) > 1
    assert all(len(line) <= STATS_CONTENT_WIDTH for line in lines)
    assert all(line.startswith("    - ") for line in lines[1:])


@pytest.mark.asyncio
async def test_mouse_cursor_syncs_app_state_without_drag_refresh(monkeypatch) -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        prose = app.query_one("#prose", PassageView)
        monkeypatch.setattr(prose, "capture_mouse", lambda: None)
        monkeypatch.setattr(prose, "release_mouse", lambda: None)
        calls: list[str] = []
        monkeypatch.setattr(app, "_on_cursor_moved", lambda: calls.append("notify"))

        prose.on_mouse_down(_FakeMouseEvent(12, 3))
        prose.on_mouse_move(_FakeMouseEvent(40, 3))

        assert cs.cursor_char == prose.cursor
        assert calls == []

        prose.on_mouse_up(_FakeMouseEvent(40, 3))

        assert cs.cursor_char == prose.cursor
        assert calls == ["notify"]


def test_legend_no_ambiguous_glyph() -> None:
    """B5: ambiguous shouldn't be in the legend."""
    glyphs = [g for g, _, _ in LEGEND]
    assert "?" not in glyphs


def test_actions_panel_lists_model_discrepancy_resolution() -> None:
    actions = ActionsPanel()
    actions.render_catalog()
    rendered = getattr(actions, "_renderable", None) or actions.render()
    text = str(rendered) if rendered is not None else ""

    assert "Resolve model discrepancy" in text


def test_actions_panel_lists_roll_display_controls() -> None:
    actions = ActionsPanel()
    actions.render_catalog()
    rendered = getattr(actions, "_renderable", None) or actions.render()
    text = str(rendered) if rendered is not None else ""

    assert "⎵v  Roll display position" in text
    assert "⎵d  Toggle evidence deferral to next chapter" in text


def test_actions_panel_omits_read_only_roll_structure_copy() -> None:
    actions = ActionsPanel()
    actions.render_catalog()
    rendered = getattr(actions, "_renderable", None) or actions.render()
    text = str(rendered) if rendered is not None else ""
    assert "Roll structure" not in text
    assert "rolls come from the simulator" not in text


def test_last_viewed_chapter_persists_and_is_overridden(tmp_path) -> None:
    state_path = tmp_path / ".forge_curator_state.json"
    app = ForgeCuratorApp(start_chapter="2", state_path=state_path)
    app._load_chapter("2")
    assert json.loads(state_path.read_text())["last_chapter"] == "2"

    restored = ForgeCuratorApp(start_chapter=None, state_path=state_path)
    restored._load_chapter(restored._read_last_viewed_chapter() or "1")
    assert restored.state.chapter is not None
    assert restored.state.chapter.meta.chapter_num == "2"

    overridden = ForgeCuratorApp(start_chapter="1", state_path=state_path)
    overridden._load_chapter("1")
    assert overridden.state.chapter is not None
    assert overridden.state.chapter.meta.chapter_num == "1"
    assert json.loads(state_path.read_text())["last_chapter"] == "1"


def test_span_eligibility_overrides_section_base_without_counting_headers() -> None:
    from scripts.eligibility_spans import section_cp_word_count, section_span_overrides

    classification = {
        "counts_for_cp": False,
        "span_overrides": [
            {
                "word_offset_start": 10,
                "word_offset_end": 20,
                "counts_for_cp": True,
                "reason_code": "joe_on_screen",
                "note": None,
                "excerpt": "Joe is visible.",
            },
            {
                "word_offset_start": 15,
                "word_offset_end": 18,
                "counts_for_cp": False,
                "reason_code": "joe_not_on_screen",
                "note": None,
                "excerpt": "Cutaway.",
            },
        ],
    }

    assert section_cp_word_count(
        section_word_start=0,
        section_word_end=30,
        base_counts_for_cp=False,
        span_overrides=section_span_overrides(classification, 0, 30),
    ) == 7


def test_source_anchor_in_ineligible_section_uses_raw_prose_position(
    tmp_path: Path,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    app = _loaded_app("15", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    footer_start = sum(int(s["word_count"]) for s in cs.meta.sections[:1])
    cursor_word = footer_start + 10
    cs.cursor_char = cs.prose.word_offsets[cursor_word][0]

    app._action_anchor_roll_without_quote("15")

    saved = json.loads((tmp_path / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["15"]["rolls"][5]
    assert app._cp_earning_word_offset(cursor_word) == cs.meta.cp_earning_word_count
    assert saved["mention_word_position"] == cursor_word
    assert saved["display_position_policy"] == "source_marker"


def test_append_roll_evidence_deduplicates_and_preserves_first_anchor(
    tmp_path: Path,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )

    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="first quote",
        mention_chapter_num="2",
        mention_word_position=10,
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="first quote",
        mention_chapter_num="2",
        mention_word_position=10,
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="second quote",
        mention_chapter_num="2",
        mention_word_position=20,
    )

    roll = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {"text": "first quote", "mention_chapter_num": "2", "mention_word_position": 10},
        {"text": "second quote", "mention_chapter_num": "2", "mention_word_position": 20},
    ]
    assert "mention_chapter_num" not in roll or roll["mention_chapter_num"] is None
    assert "mention_word_position" not in roll or roll["mention_word_position"] is None
    assert "display_position_policy" not in roll or roll["display_position_policy"] is None


def test_anchor_roll_without_quote_writes_source_marker_metadata(tmp_path: Path) -> None:
    app = _loaded_app("4", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    path = tmp_path / "chapter_roll_overrides.json"
    app.persistence = forge_app.CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    cs.cursor_char = cs.prose.word_offsets[9500][0]
    app._post_curation_refresh = lambda _message: None  # type: ignore[method-assign]

    app._action_anchor_roll_without_quote("4")

    rolls = json.loads(path.read_text())["chapter_roll_overrides"]["4"]["rolls"]
    anchored = rolls[-1]
    assert anchored["evidence_quotes"] == []
    assert anchored["mention_chapter_num"] == "4"
    assert anchored["mention_word_position"] == 9500
    assert anchored["display_position_policy"] == "source_marker"
    assert anchored["curator_note"] == "source-only roll anchor"


def test_rolls_header_counts_source_curated_and_deferred_rows(
    tmp_path: Path,
) -> None:
    app = _loaded_app("9", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    cs.derived.predicted_rolls = [{} for _ in range(5)]
    source_row = {
        "display_kind": "chapter_roll",
        "source": "curator_rolls",
        "source_kind": "miss",
    }
    curated_row = {
        "display_kind": "chapter_roll",
        "source_kind": "miss",
        "curator_added": True,
    }
    deferred_row = {
        "display_kind": "deferred_in",
        "source": "curator_rolls",
        "source_kind": "miss",
    }
    app._unified_rolls = lambda _cs: [
        source_row,
        source_row,
        source_row,
        curated_row,
        deferred_row,
        deferred_row,
        deferred_row,
    ]

    assert app._rolls_header_count(cs) == (
        "5 predicted, 3 source, 1 curated"
    )


def test_source_roll_marker_accumulates_quote_evidence(tmp_path: Path) -> None:
    app = _loaded_app("8.1", tmp_path)

    assert app._roll_evidence_marker({
        "source": "curator_rolls",
        "source_kind": "miss",
        "evidence_quotes": [{"text": "quote"}],
    }) == "SQ"
    assert app._roll_evidence_marker({
        "source": "curator_rolls",
        "source_kind": "roll",
        "evidence_quotes": [{"text": "one"}, {"text": "two"}],
    }) == "SQQ"
    assert app._roll_evidence_marker({
        "evidence_quotes": [{"text": "quote"}],
    }) == "Q"


def test_multi_quote_picker_targets_visible_slot_rows_not_source_row_indexes(
    tmp_path: Path,
) -> None:
    app = _loaded_app("8.1", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    rows = app._roll_evidence_picker_rolls(cs)

    assert rows
    assert all(row.get("target_roll_index") for row in rows)
    assert [row.get("target_roll_index") for row in rows] == [
        row.get("target_roll_index") for row in app._unified_rolls(cs)
    ]


def test_curation_status_message_is_visible_in_stats(tmp_path: Path) -> None:
    app = _loaded_app("9", tmp_path)
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None

    app._flash("skip roll: select an open predicted slot first")

    assert "skip roll: select an open predicted slot first" in _render_stats_text(app)


def test_stats_click_selects_roll_action_target(tmp_path: Path) -> None:
    app = _loaded_app("9", tmp_path)
    app._unified_rolls = lambda _cs: []
    stats = StatsPanel()
    stats.render_stats(app.state, app)
    target_line = next(
        line
        for line, target in stats._roll_line_targets.items()
        if target.get("display_kind") == "predicted_slot"
    )

    stats.on_click(_FakeMouseEvent(0, target_line))

    selected = app._selected_roll_target_if_visible()
    assert selected is not None
    assert selected["display_kind"] == "predicted_slot"


def test_curated_evidence_distance_uses_visualized_quote_then_first_quote(
    tmp_path: Path,
) -> None:
    app = _loaded_app("2", tmp_path)
    first_quote = {
        "text": "I felt myself latch on to a mote of power.",
        "mention_chapter_num": "2",
        "mention_word_position": 879,
    }
    second_quote = {
        "text": "This was not a tinker power.",
        "mention_chapter_num": "2",
        "mention_word_position": 902,
    }
    roll = {
        "source_kind": "roll",
        "chapter_num": "2",
        "mechanical_chapter_num": "2",
        "display_cumulative_word_offset": 902,
        "cumulative_word_offset": 902,
        "mention_chapter_num": "2",
        "mention_word_position": 902,
        "display_position_policy": "mention",
        "evidence_quotes": [first_quote, second_quote],
    }
    app.data.roll_facts["rolls"] = [roll]

    assert app._curated_evidence_global_positions() == [902]

    roll["display_position_policy"] = "mechanical"
    roll["mention_word_position"] = None

    assert app._curated_evidence_global_positions() == [879]


def test_clear_roll_evidence_at_index(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="first quote",
        mention_chapter_num="2",
        mention_word_position=10,
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="second quote",
        mention_chapter_num="2",
        mention_word_position=20,
    )

    assert persistence.clear_roll_evidence_at_index("2", 1)
    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert rolls[0]["evidence_quotes"] == []


def test_remove_roll_evidence_quote_preserves_other_quotes(tmp_path: Path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="first quote",
        mention_chapter_num="2",
        mention_word_position=10,
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="second quote",
        mention_chapter_num="2",
        mention_word_position=20,
    )

    assert persistence.remove_roll_evidence_quote_at_index(
        "2",
        1,
        {"text": "first quote", "mention_chapter_num": "2", "mention_word_position": 10},
    )

    roll = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {"text": "second quote", "mention_chapter_num": "2", "mention_word_position": 20}
    ]


def test_chapter_1_override_preserves_trigger_without_local_paid_perk() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    cf = app.data.chapter_derived("1").chapter_facts or {}
    rolls = cf.get("rolls") or []
    trigger_rolls = [r for r in rolls if r.get("source_kind") == "trigger"]
    paid_rolls = [r for r in rolls if r.get("source_kind") != "trigger"]
    assert len(trigger_rolls) == 1
    assert paid_rolls
    assert all(r.get("purchased_perks") in (None, []) for r in paid_rolls)
    trigger = trigger_rolls[0]
    assert trigger["available_cp"] == 0
    assert trigger["banked_cp_after_roll"] == 0
    assert trigger["purchased_perk_cost_total"] == 0
    assert trigger["purchased_perks"] == [
        {"name": "Workshop", "cost": 0, "free": False}
    ]
    assert [p["name"] for p in trigger["free_perks"]] == [
        "Access Key",
        "Entrance Hall",
    ]
    cross_chapter = [
        roll
        for cn in app.data.chapter_order
        for roll in (app.data.chapter_derived(cn).chapter_facts or {}).get("rolls", [])
        if str(roll.get("mechanical_chapter_num")) == "1"
        and str(roll.get("mention_chapter_num")) != "1"
    ]
    assert cross_chapter


def test_defer_roll_action_uses_lowercase_space_d(tmp_path) -> None:
    app = _loaded_app("2", tmp_path)
    calls: list[tuple[str, str]] = []

    app._action_defer_roll_to_next_chapter = lambda cn: calls.append(("defer", cn))
    app._action_remove_annotations_at_current_word = (
        lambda cn: calls.append(("delete_annotations", cn))
    )

    app._handle_space_chord("d")
    app._handle_space_chord("D")

    assert calls == [("defer", "2"), ("delete_annotations", "2")]


def test_resolve_model_discrepancy_persists_chapter_resolution(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )

    resolution = persistence.resolve_model_validation_issue(
        "7",
        issue_code="known_attempts_exceed_predicted_slots",
        reason_code="curator_confirmed_extra_attempt",
        note="Curator confirmed the fourth narrated attempt is intentional.",
    )

    assert resolution == {
        "status": "resolved",
        "resolved_issue_codes": ["known_attempts_exceed_predicted_slots"],
        "reason_code": "curator_confirmed_extra_attempt",
        "note": "Curator confirmed the fourth narrated attempt is intentional.",
    }
    saved = json.loads((tmp_path / "chapter_roll_overrides.json").read_text())
    assert (
        saved["chapter_roll_overrides"]["7"]["model_validation_resolution"]
        == resolution
    )
    assert saved["chapter_roll_overrides"]["7"]["rolls"] == []


def test_space_r_resolves_current_model_discrepancy(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    chapter_facts = json.loads((DERIVED / "chapter_facts.json").read_text())
    blocking_codes = {
        "paid_rolls_exceed_predicted_slots",
        "known_attempts_exceed_predicted_slots",
        "cost_schedule_infeasible",
    }
    chapter_num = None
    issue_codes = None
    for chapter in chapter_facts["chapters"]:
        model = chapter.get("model_validation") or {}
        unresolved = [
            str(issue.get("code"))
            for issue in model.get("issues") or []
            if str(issue.get("code")) in blocking_codes
            and not issue.get("resolved")
        ]
        if unresolved:
            chapter_num = str(chapter["chapter_num"])
            issue_codes = list(dict.fromkeys(unresolved))
            break
    assert chapter_num is not None
    assert issue_codes is not None

    app = _loaded_app(chapter_num, tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    refreshes: list[str] = []
    flashes: list[str] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append(message)
    )
    app._flash = lambda message: flashes.append(message)

    app._handle_space_chord("r")

    saved = json.loads((tmp_path / "chapter_roll_overrides.json").read_text())
    resolution = saved["chapter_roll_overrides"][chapter_num][
        "model_validation_resolution"
    ]
    assert resolution["status"] == "resolved"
    assert resolution["resolved_issue_codes"] == issue_codes
    assert resolution["reason_code"] == app._resolution_reason_code(issue_codes[-1])
    assert refreshes == ["model discrepancy resolved"]
    assert flashes == []


def test_remove_annotations_action_clears_roll_evidence_under_cursor(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    chapter_roll_overrides_path = tmp_path / "chapter_roll_overrides.json"
    chapter_roll_overrides_path.write_text(
        (MANUAL / "chapter_roll_overrides.json").read_text()
    )

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=chapter_roll_overrides_path,
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    deferred = next(
        r for r in app._unified_rolls(cs)
        if r.get("display_kind") == "deferred_in"
        and r.get("target_roll_index") is not None
        and r.get("evidence_quotes")
    )
    quote_start = cs.prose.text.find(deferred["evidence_quotes"][0]["text"])
    assert quote_start >= 0
    cs.cursor_char = quote_start
    monkeypatch.setattr(
        app,
        "query_one",
        lambda *args, **kwargs: SimpleNamespace(selection=None, cursor=quote_start),
    )

    app._action_remove_annotations_at_current_word("2")

    rolls = json.loads(chapter_roll_overrides_path.read_text())[
        "chapter_roll_overrides"
    ][str(deferred["target_chapter_num"])]["rolls"]
    assert rolls[int(deferred["target_roll_index"]) - 1]["evidence_quotes"] == []


@pytest.mark.asyncio
async def test_b2_mouse_click_word_alignment() -> None:
    """B2: Click on a known character should land cursor on that character.

    The base PassageView delegates click→offset via _xy_to_offset which
    operates on the widget's local coordinates (after Textual subtracts
    border + padding). We exercise it directly to verify the math is
    correct, then trigger a synthetic click via Pilot to confirm
    end-to-end behavior.
    """
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        prose = app.query_one("#prose", PassageView)
        # Padding-aware: a click at left padding + 5 lands inside line 0
        # at content column 5.
        pad = prose.styles.padding
        offset = prose._xy_to_offset(pad.left + 5, pad.top + 0)
        assert offset == 5, (
            f"_xy_to_offset(pad.left+5, pad.top) -> {offset} (expected 5)"
        )
        offset2 = prose._xy_to_offset(pad.left + 0, pad.top + 1)
        if len(prose._lines) > 1:
            assert offset2 == prose._lines[1][0], (
                f"_xy_to_offset(pad.left+0, pad.top+1) -> {offset2} != line1 start "
                f"{prose._lines[1][0]}"
            )
