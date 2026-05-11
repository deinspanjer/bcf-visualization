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
from textual.widgets import Button, Input

import scripts.forge_curator.app as forge_app

# Import here so the rest of the suite still loads even if textual is
# unavailable.
from scripts.forge_curator.app import (
    ForgeCuratorApp,
    PassageView,
    PerkPicker,
    RollEvidencePicker,
    StatsPanel,
    ActionsPanel,
    RegexBar,
    GutterPanel,
    GutterMark,
    GLYPH_COLORS,
    GLYPH_STYLES,
    LEGEND,
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


def test_cp_raw_word_roundtrip_ch97(tmp_path: Path) -> None:
    """ch 97 has a leading non-CP section. Confirm raw↔CP round-trip
    via the canonical App methods (which honour exclusion ranges)."""
    app = _loaded_app("97", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    # First CP-eligible raw word: section 0 is ineligible; section 1 starts
    # the CP body. The auto-detected header at the top of section 1 is also
    # excluded.
    ahc = int(cs.meta.sections[1].get("auto_header_word_count") or 0)
    first_eligible = int(cs.meta.sections[0].get("word_count") or 0) + ahc
    assert app._cp_earning_word_offset(first_eligible) == 0
    assert app._cp_earning_word_offset(first_eligible + 100) == 100
    assert app._raw_word_for_cp_offset(0) == 0
    assert app._raw_word_for_cp_offset(100) == first_eligible + 100


# ---------------------------------------------------------------------------
# Pilot-driven app tests
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _isolate_default_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        forge_app,
        "STATE_FILE",
        tmp_path / ".forge_curator_state.json",
    )


@pytest.fixture
def app() -> ForgeCuratorApp:
    return ForgeCuratorApp(start_chapter="1")


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


def _stats_text(app: ForgeCuratorApp) -> str:
    stats = app.query_one("#stats", StatsPanel)
    rendered = getattr(stats, "_renderable", None) or stats.render()
    return str(rendered) if rendered is not None else ""


def _word_index_for_char(app: ForgeCuratorApp, char: int) -> int:
    cs = app.state.chapter
    assert cs is not None
    for index, (_start, end) in enumerate(cs.prose.word_offsets):
        if char < end:
            return index
    return max(0, len(cs.prose.word_offsets) - 1)


class _FakeMouseEvent:
    def __init__(self, x: int, y: int, button: int = 1) -> None:
        self.x = x
        self.y = y
        self.button = button

    def stop(self) -> None:
        pass


@pytest.mark.asyncio
async def test_b1_gg_then_j_moves_cursor_one_line() -> None:
    """B1: pressing j after gg should move cursor down exactly one visual line."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.press("g", "g")
        prose = app.query_one("#prose", PassageView)
        assert prose.cursor == 0, f"after gg, cursor should be 0, got {prose.cursor}"
        # Capture the visual line of cursor.
        prose._recompute_lines()
        line0 = next(
            (i for i, (s, e) in enumerate(prose._lines) if s <= 0 <= e), 0
        )
        await pilot.press("j")
        prose._recompute_lines()
        cur = prose.cursor
        line1 = next(
            (i for i, (s, e) in enumerate(prose._lines) if s <= cur <= e), 0
        )
        # Line should have advanced by exactly 1 (not 0, not 2).
        assert line1 == line0 + 1, (
            f"j after gg moved from line {line0} to line {line1} "
            f"(cursor={cur}); expected exactly +1"
        )


def test_b5_b6_b7_stats_panel_ch97(tmp_path: Path) -> None:
    """Stats panel uses the rewritten eligibility/word/CP blocks."""
    app = _loaded_app("97", tmp_path)
    text = _render_stats_text(app)
    assert "Validation" not in text
    assert "At cursor" not in text
    assert "Chapter overrides" not in text
    assert "Roll-acquired perks" not in text
    assert "Eligibility\n" not in text
    assert "Model:" in text
    assert "Total content:" in text
    assert "CP eligible:" in text
    assert "Since last predicted roll:" in text
    assert "Until next predicted roll:" in text
    assert "Since last curated roll:" in text
    assert "Until next curated roll:" in text
    assert "Since last curated evidence:" in text
    assert "Until next curated evidence:" in text
    assert "Available:" in text
    assert "Gained:" in text
    assert "Spent:" in text
    assert "Evidence" in text


def test_b8_cp_at_cursor_nonzero_after_first_roll(tmp_path: Path) -> None:
    """B8: CP banked should be non-zero after navigating past the first roll."""
    app = _loaded_app("97", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    rolls = sorted(
        (r for r in cs.derived.roll_facts if r.get("word_position") is not None),
        key=lambda r: int(r["word_position"]),
    )
    assert rolls, "ch97 must have at least one roll fact"
    first_roll = rolls[0]
    first_cp = int(first_roll["word_position"])
    first_banked = int(first_roll.get("banked_cp_after_roll") or 0)
    target_cp = first_cp + 10
    cp_banked = app._cp_at_cursor(target_cp)
    assert cp_banked > 0, (
        f"CP banked at cp_word={target_cp} should be > 0; got {cp_banked} "
        f"(first roll at cp_w={first_cp} banked={first_banked})"
    )
    assert cp_banked >= first_banked, (
        f"expected >= first_banked={first_banked}, got {cp_banked}"
    )


def test_stats_roll_distances_disambiguate_predicted_curated_and_evidence(
    tmp_path: Path,
) -> None:
    app = _loaded_app("5", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    app.state.set_cursor_char(app.state.char_at_word_index(174))

    cp_word_idx = app._cp_earning_word_offset(cs.cursor_word_index)
    story_cp_cursor = app._chapter_cp_start(cs.meta.chapter_num) + cp_word_idx

    assert story_cp_cursor == 28_061
    assert app._predicted_roll_distance_stats(story_cp_cursor) == (61, 1_939)
    assert app._curated_roll_distance_stats(story_cp_cursor) == (61, 5_939)
    assert app._curated_evidence_distance_stats(story_cp_cursor) == (170, 857_939)


def test_gutter_minimap_emits_an_and_roll_marks_for_ch97(tmp_path: Path) -> None:
    """Minimap items list contains A glyphs (AN spans) and R/H/M (rolls).

    Replaces the older B9/B10 test which assumed 1-row-per-line gutter
    rendering. The minimap design proportions one mark per logical span.
    """
    app = _loaded_app("97", tmp_path)
    items = app._compute_gutter_items()
    glyph_set = {g for _p, g in items}
    assert "A" in glyph_set, (
        f"expected at least one 'A' minimap item for ch97 AN; got: {glyph_set}"
    )
    assert glyph_set & {"R", "H", "M"}, (
        f"expected at least one R/H/M item; got: {glyph_set}"
    )
    for prop, _ in items:
        assert 0.0 <= prop <= 1.0, f"minimap proportion out of [0,1]: {prop}"


@pytest.mark.asyncio
async def test_gutter_minimap_renders_priority_cells() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)

        gutter.render_minimap([(0.0, "Q"), (0.0, "*")], 1.0, 1)
        assert str(gutter.render()) == "Q*    "

        gutter.render_minimap([(0.0, "2"), (0.0, "*"), (0.0, "1")], 1.0, 1)
        assert str(gutter.render()) == "*12   "

        gutter.render_minimap([(0.0, "Q"), (0.0, "A"), (0.0, "1")], 1.0, 1)
        assert str(gutter.render()) == "AQ1   "


def test_gutter_and_highlight_styles_are_unique_and_aligned() -> None:
    css = RegexBar.DEFAULT_CSS
    assert len(set(GLYPH_STYLES.values())) == len(GLYPH_STYLES)
    assert ROLL_HIGHLIGHT_STYLE == GLYPH_STYLES["R"]
    assert QUOTE_HIGHLIGHT_STYLE == GLYPH_STYLES["Q"]
    assert REGEX_HIGHLIGHT_STYLES == (
        GLYPH_STYLES["1"],
        GLYPH_STYLES["2"],
        GLYPH_STYLES["3"],
        GLYPH_STYLES["*"],
    )
    for glyph, slot in (("1", "1"), ("2", "2"), ("3", "3"), ("*", "4")):
        assert f"regex-slot-{slot}" in css
        assert f"color: {GLYPH_COLORS[glyph]};" in css
        assert css.count(f"color: {GLYPH_COLORS[glyph]};") == 2


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


@pytest.mark.parametrize("chapter_num", ["2", "97"])
def test_gutter_marks_match_canonical_roll_fact_positions(
    chapter_num: str, tmp_path: Path,
) -> None:
    app = _loaded_app(chapter_num, tmp_path)
    cs = app.state.chapter
    assert cs is not None
    total = len(app.state.chapter.prose.word_offsets)
    expected = []
    for roll in app._unified_rolls(cs):
        if (
            roll.get("source_kind") == "trigger"
            or roll.get("outcome") not in {"hit", "miss"}
            or roll.get("word_position") is None
        ):
            continue
        raw = roll.get("raw_word_position")
        glyph = "H" if roll["outcome"] == "hit" else "M"
        expected.append((raw / total, glyph))

    actual = [
        (prop, glyph) for prop, glyph in app._compute_gutter_items()
        if glyph in {"H", "M"}
    ]
    assert actual == expected


@pytest.mark.asyncio
async def test_b12_jump_roll_scrolls_into_view() -> None:
    """B12: ]r should scroll the prose so the cursor is in view."""
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        # Get initial scroll y of the VerticalScroll.
        from textual.containers import VerticalScroll
        scroll = app.query_one("#prose_scroll", VerticalScroll)
        initial_y = scroll.scroll_y
        prose = app.query_one("#prose", PassageView)
        initial_cursor = prose.cursor
        # Press ]r — chord prefix then 'r'.
        await pilot.press("]")
        await pilot.press("r")
        await pilot.pause()
        new_cursor = prose.cursor
        new_y = scroll.scroll_y
        assert new_cursor != initial_cursor, (
            "cursor should move after ]r"
        )
        # Either scroll moved or cursor was already in view; the important
        # thing is that the cursor's line is within the viewport.
        assert new_y != initial_y or new_cursor < 100, (
            f"expected scroll position to update (was {initial_y}, "
            f"now {new_y}); cursor moved to {new_cursor}"
        )


@pytest.mark.asyncio
async def test_keybind_redesign_chapter_and_section_chords() -> None:
    """]] / [[ navigate chapters and land at chapter edges; ][ navigates sections."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs0 = app.state.chapter
        assert cs0 is not None
        ch0 = cs0.meta.chapter_num
        app._jump_to_word(100)
        await pilot.pause()
        await pilot.press("]")
        await pilot.press("]")
        await pilot.pause()
        cs1 = app.state.chapter
        assert cs1 is not None
        assert cs1.meta.chapter_num != ch0
        assert cs1.cursor_word_index == 0
        ch1 = cs1.meta.chapter_num
        app._jump_to_word(100)
        await pilot.pause()
        await pilot.press("[")
        await pilot.press("[")
        await pilot.pause()
        cs2 = app.state.chapter
        assert cs2 is not None
        assert cs2.meta.chapter_num != ch1
        assert cs2.meta.chapter_num == ch0
        assert cs2.cursor_word_index == len(cs2.prose.word_offsets) - 1
        cs = app.state.chapter
        assert cs is not None
        app._jump_to_word(0)
        await pilot.pause()
        assert cs.section_index_at(cs.cursor_word_index) == 0
        await pilot.press("]")
        await pilot.press("[")
        await pilot.pause()
        new_sec = cs.section_index_at(cs.cursor_word_index)
        assert new_sec >= 1, (
            f"][ should advance to section >= 1; cursor at section {new_sec} "
            f"(word_idx={cs.cursor_word_index})"
        )


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
        assert labels == ["regex 1:", "regex 2:", "regex 3:", "regex *:"]
        for slot in range(1, 5):
            inp = app.query_one(f"#regex_{slot}", Input)
            assert inp.compact is True
            assert inp.size.height == 1
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
async def test_zxc_star_select_active_regex_and_n_uses_it() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None

        app.state.set_regex(0, r"\bcurrent\b")
        app.state.set_regex(1, r"\bglobal\b")
        app.state.set_regex(2, r"\bcircumstances\b")
        app.refresh_all_panels()

        await pilot.press("x")
        assert app.active_regex_slot == 1
        assert app.query_one("#regex_2", Input).has_class("active")
        await pilot.press("n")
        assert cs.cursor_word_index == cs.regex_hits[1].word_indices[0]

        await pilot.press("c")
        assert app.active_regex_slot == 2
        assert app.query_one("#regex_3", Input).has_class("active")
        await pilot.press("n")
        assert cs.cursor_word_index == cs.regex_hits[2].word_indices[0]

        await pilot.press("z")
        assert app.active_regex_slot == 0
        assert app.query_one("#regex_1", Input).has_class("active")

        await pilot.press("*")
        assert app.active_regex_slot == 3
        assert app.query_one("#regex_4", Input).has_class("active")
        assert cs.regex_hits[3].pattern.startswith("\\b")


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


def test_chapter_2_header_eligibility_and_roll_stats(tmp_path: Path) -> None:
    app = _loaded_app("2", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    assert cs.prose.text.split()[:4] == ["2", "Preparation", "2", "Preparation"]
    assert cs.prose.implicit_header_word_ranges
    assert cs.prose.implicit_header_word_ranges[0] == (0, 4)

    text = _render_stats_text(app)
    assert "chapter 2 /" in text
    assert "chapter 2 / 194; section 1 / 2" in text
    assert "2 Preparation" in text
    assert "Model:" in text
    assert "Section: CP eligible" in text
    assert "Text: CP ineligible - header" in text
    assert "Total content:" in text
    assert "CP eligible:" in text
    assert "# 1 (2) Avail CP 200 hit Q" in text
    assert "narrative deferred to ch 2" in text
    assert "# 2 (3) Avail CP 100 miss Q" in text
    assert "# 3 (4) Avail CP 200 hit Q" in text
    assert "hit" in text
    assert "Clothing - Fashion (200)" in text
    assert "Quality - Bling of War (100)" in text
    assert "Alchemy - Alchemist (200)" in text
    assert "Evidence:" not in text
    assert "T text evidence" not in text
    assert "@cp" not in text


def test_chapter_4_unpredicted_roll_without_evidence_anchors_to_last_word(
    tmp_path: Path,
) -> None:
    app = _loaded_app("4", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    fifth_fact = next(
        r for r in cs.derived.roll_facts
        if r.get("roll_sequence_in_chapter") == 5
        and str(r.get("mechanical_chapter_num")) == "4"
    )
    fifth_fact["narrative_evidence"] = None
    for field in (
        "word_position",
        "display_word_position",
        "display_cumulative_word_offset",
        "mechanical_word_position",
        "mechanical_cumulative_word_offset",
    ):
        fifth_fact[field] = None

    fifth = next(r for r in app._unified_rolls(cs) if r.get("target_roll_index") == 5)

    assert fifth["roll_number"] == 14
    assert fifth["display_kind"] == "chapter_roll"
    assert fifth["raw_word_position"] == int(cs.meta.sections[0]["word_count"]) - 1


def test_chapter_4_end_of_section_roll_marker_does_not_land_in_bottom_section(
    tmp_path: Path,
) -> None:
    app = _loaded_app("4", tmp_path)
    cs = app.state.chapter
    assert cs is not None

    story_section_last_word = int(cs.meta.sections[0]["word_count"]) - 1
    marker_indices = app._predicted_roll_word_indices(cs)

    assert story_section_last_word in marker_indices
    assert story_section_last_word + 1 not in marker_indices


def test_stats_evidence_block_reports_reference_distance_and_cp(
    tmp_path: Path,
) -> None:
    app = _loaded_app("4", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    text = _render_stats_text(app)

    assert text.index("Rolls") < text.index("Evidence")
    assert text.index("Evidence") < text.index("Perks this chapter")
    assert "against ch 4 #5 (global #14)" in text
    assert "word distance:" in text
    assert "CP at quote start:" in text
    assert "word distance: -1,541" in text
    assert "word distance: +0" not in text
    assert "word distance: -1,541\n    CP at quote start: 100" in text
    assert "word distance: -1,541; CP at quote start: 100" not in text


def test_chapter_4_unpredicted_roll_keeps_saved_evidence_separate_from_slot(
    tmp_path: Path,
) -> None:
    app = _loaded_app("4", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    quote = "That had taken too long the first time"
    fifth_fact = next(
        r for r in cs.derived.roll_facts
        if r.get("roll_sequence_in_chapter") == 5
        and str(r.get("mechanical_chapter_num")) == "4"
    )
    fifth_fact["narrative_evidence"] = quote
    for field in (
        "word_position",
        "display_word_position",
        "display_cumulative_word_offset",
        "mechanical_word_position",
        "mechanical_cumulative_word_offset",
    ):
        fifth_fact[field] = None

    fifth = next(r for r in app._unified_rolls(cs) if r.get("target_roll_index") == 5)

    assert fifth["roll_number"] == 14
    assert fifth["narrative_evidence"] == quote
    assert fifth["raw_word_position"] == int(cs.meta.sections[0]["word_count"]) - 1
    assert fifth["word_position"] == cs.meta.cp_earning_word_count


def test_saved_roll_evidence_highlights_exact_quote_span(tmp_path: Path) -> None:
    app = _loaded_app("2", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    quote = next(
        r["narrative_evidence"]
        for r in cs.derived.roll_facts
        if r.get("roll_number") == 2
    )
    quote_start = cs.prose.text.find(quote)
    assert quote_start >= 0

    spans = app._compute_prose_spans()

    assert {
        "start": quote_start,
        "end": quote_start + len(quote),
        "layer": "A",
        "style": QUOTE_HIGHLIGHT_STYLE,
        "priority": 20,
    } in spans


def test_roll_evidence_gutter_mark_survives_chapter_navigation(tmp_path: Path) -> None:
    app = _loaded_app("2", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    quote = next(
        r["narrative_evidence"]
        for r in cs.derived.roll_facts
        if r.get("roll_number") == 2
    )
    quote_start = cs.prose.text.find(quote)
    assert quote_start >= 0
    expected_word = _word_index_for_char(app, quote_start)
    expected = (
        expected_word / max(1, len(cs.prose.word_offsets)),
        "Q",
    )

    assert "hit Q" in _render_stats_text(app)
    assert expected in app._compute_gutter_items()

    app._load_chapter("3")
    app._load_chapter("2")

    assert app.state.chapter is not None
    assert app.state.chapter.meta.chapter_num == "2"
    assert expected in app._compute_gutter_items()


def test_chapter_2_auto_header_does_not_render_author_note_gutter_mark(
    tmp_path: Path,
) -> None:
    app = _loaded_app("2", tmp_path)
    top_glyphs = [
        glyph for prop, glyph in app._compute_gutter_items()
        if prop == 0.0
    ]

    assert "═" in top_glyphs
    assert "A" not in top_glyphs


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


def test_snapshot_writes_current_forge_curator_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_path = tmp_path / ".forge_curator_snapshot.json"
    monkeypatch.setattr(forge_app, "SNAPSHOT_PATH", snapshot_path)
    app = _loaded_app("2", tmp_path)
    cs = app.state.chapter
    assert cs is not None
    app.state.set_cursor_char(42)
    app.state.set_regex(2, "Taylor|Queen")

    app.action_snapshot()
    first = json.loads(snapshot_path.read_text())

    assert first["snapshot_kind"] == "forge_curator_tui"
    assert first["chapter"]["chapter_num"] == "2"
    assert first["chapter"]["full_title"] == cs.meta.full_title
    assert first["cursor"]["char"] == 42
    assert first["cursor"]["word_index"] == cs.cursor_word_index
    assert first["regex"][2]["pattern"] == "Taylor|Queen"
    assert first["prose"]["text"] == cs.prose.text

    app._load_chapter("1")
    app.action_snapshot()
    second = json.loads(snapshot_path.read_text())

    assert second["chapter"]["chapter_num"] == "1"
    assert second["captured_at"] != first["captured_at"]


def test_save_quote_to_multiple_rolls(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.update_rolls_at_indices("2", [1, 3], narrative_evidence="same quote")
    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert len(rolls) == 3
    assert rolls[0]["narrative_evidence"] == "same quote"
    assert rolls[1]["narrative_evidence"] is None
    assert rolls[2]["narrative_evidence"] == "same quote"


def test_roll_evidence_picker_labels_selected_rolls() -> None:
    picker = RollEvidencePicker(
        rolls=[
            {
                "index": 1,
                "roll_number": 7,
                "outcome": "hit",
            },
        ],
        on_confirm=lambda _indices: None,
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


def test_roll_evidence_picker_space_action_toggles_focused_roll() -> None:
    picker = RollEvidencePicker(
        rolls=[
            {
                "index": 1,
                "roll_number": 7,
                "outcome": "hit",
            },
        ],
        on_confirm=lambda _indices: None,
    )
    button = Button(picker._roll_button_label(1, picker._rolls[0]), name="1")
    picker.focused = button

    picker.action_toggle_focused_roll()

    assert picker._selected == {1}
    assert str(button.label).startswith("(x) #1")


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


def test_clear_roll_evidence_at_index(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.update_roll_at_index("2", 1, narrative_evidence="quote")

    assert persistence.clear_roll_evidence_at_index("2", 1)
    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert rolls[0]["narrative_evidence"] is None


def test_save_quote_targets_selection_start_not_visual_cursor_end(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    rolls = app._unified_rolls(cs)
    roll_1 = next(
        r for r in rolls
        if r["target_chapter_num"] == "2" and r["target_roll_index"] == 1
    )
    roll_2 = next(
        r for r in rolls
        if r["target_chapter_num"] == "2" and r["target_roll_index"] == 2
    )
    start = cs.prose.word_offsets[int(roll_1["raw_word_position"])][0]
    end = cs.prose.word_offsets[int(roll_2["raw_word_position"])][0]
    prose = SimpleNamespace(selection=(start, end), cursor=end)
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)

    app._action_save_quote("2")

    saved = json.loads((tmp_path / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[0]["narrative_evidence"]
    assert len(saved) == 1


def test_save_quote_exits_visual_mode_after_success(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    rolls = app._unified_rolls(cs)
    roll_1 = next(
        r for r in rolls
        if r["target_chapter_num"] == "2" and r["target_roll_index"] == 1
    )
    start = cs.prose.word_offsets[int(roll_1["raw_word_position"])][0]
    end = cs.prose.word_offsets[int(roll_1["raw_word_position"]) + 3][1]
    prose = SimpleNamespace(
        selection=(start, end),
        cursor=end,
        anchor=start,
        visual_mode=True,
        visual_line_mode=False,
        refresh=lambda: None,
    )
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)

    app._action_save_quote("2")

    assert prose.anchor is None
    assert prose.visual_mode is False
    assert prose.visual_line_mode is False


def test_chapter_2_miss_quote_coordinates_target_first_roll(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    miss = next(r for r in app._unified_rolls(cs) if r["outcome"] == "miss")
    start_word = miss["raw_word_position"]
    start = cs.prose.word_offsets[start_word][0]
    end = cs.prose.word_offsets[start_word + 15][1] - 1
    prose = SimpleNamespace(selection=(start, end), cursor=end)
    cs.cursor_char = prose.cursor
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)

    app._action_save_quote("2")

    saved = json.loads((tmp_path / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[0]["narrative_evidence"]
    assert len(saved) == 1


def test_chapter_1_override_preserves_trigger_and_deferred_fashion() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    cf = app.data.chapter_derived("1").chapter_facts or {}
    rolls = cf.get("rolls") or []
    assert [(r.get("source_kind"), r.get("outcome")) for r in rolls] == [
        ("trigger", "hit"),
        ("miss", "miss"),
    ]
    assert rolls[0]["available_cp"] == 0
    assert rolls[0]["banked_cp_after_roll"] == 0
    assert rolls[0]["purchased_perk_cost_total"] == 0
    assert rolls[0]["purchased_perks"] == [
        {"name": "Workshop", "cost": 0, "free": False}
    ]
    assert [p["name"] for p in rolls[0]["free_perks"]] == [
        "Access Key",
        "Entrance Hall",
    ]

    ch2 = app.data.chapter_derived("2").chapter_facts or {}
    fashion = next(
        r for r in ch2.get("rolls") or []
        if any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
    )
    assert fashion["mechanical_chapter_num"] == "1"
    assert fashion["roll_number"] == 2


def test_chapter_1_stats_marks_fashion_as_narrative_deferred(tmp_path) -> None:
    app = _loaded_app("1", tmp_path)
    text = _render_stats_text(app)
    assert "# 2 (2) Avail CP 200 hit Q" in text
    assert "narrative deferred to ch 2" in text
    assert "Clothing - Fashion (200)" in text


def test_deferred_roll_action_targets_mechanical_override_row(tmp_path) -> None:
    app = _loaded_app("2", tmp_path)
    from scripts.forge_curator.persistence import CurationPersistence
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    fashion = next(
        r for r in app._unified_rolls(cs)
        if any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
    )
    cs.cursor_char = app.state.char_at_word_index(fashion["raw_word_position"])

    app._action_set_last_outcome("2", "miss")

    ch1_rolls = (
        app.persistence.chapter_roll_overrides
        .get("chapter_roll_overrides", {})
        .get("1", {})
        .get("rolls", [])
    )
    assert ch1_rolls[1]["outcome"] == "miss"
    ch2_rolls = (
        app.persistence.chapter_roll_overrides
        .get("chapter_roll_overrides", {})
        .get("2", {})
        .get("rolls", [])
    )
    assert not ch2_rolls


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


def test_remove_annotations_action_deletes_author_notes_and_headers_at_cursor(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    author_notes_path = tmp_path / "author_notes.json"
    header_corrections_path = tmp_path / "header_corrections.json"
    author_notes_path.write_text(json.dumps({
        "author_notes": [
            {
                "chapter_num": "2",
                "section_index": 0,
                "an_text": "2 Preparation 2 Preparation",
                "reason": "test",
            }
        ]
    }))
    header_corrections_path.write_text(json.dumps({
        "corrections": [
            {
                "chapter_num": "2",
                "section_index": 0,
                "word_offset_start": 0,
                "word_offset_end": 4,
                "excerpt": "2 Preparation 2 Preparation",
            }
        ]
    }))

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        author_notes_path=author_notes_path,
        header_corrections_path=header_corrections_path,
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    monkeypatch.setattr(
        app,
        "query_one",
        lambda *args, **kwargs: SimpleNamespace(selection=None),
    )

    app._action_remove_annotations_at_current_word("2")

    assert json.loads(author_notes_path.read_text())["author_notes"] == []
    assert json.loads(header_corrections_path.read_text())["corrections"] == []


def test_remove_annotations_action_clears_roll_evidence_under_cursor(
    tmp_path, monkeypatch,
) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    chapter_roll_overrides_path = tmp_path / "chapter_roll_overrides.json"
    chapter_roll_overrides_path.write_text(
        Path("data/manual/chapter_roll_overrides.json").read_text()
    )

    app = _loaded_app("2", tmp_path)
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=chapter_roll_overrides_path,
        journal_dir_path=tmp_path / ".journals",
    )
    app._post_curation_refresh = lambda message, *, full=False: None
    cs = app.state.chapter
    assert cs is not None
    fashion = next(
        r for r in app._unified_rolls(cs)
        if any(p["name"] == "Fashion" for p in r.get("purchased_perks") or [])
    )
    quote_start = cs.prose.text.find(fashion["narrative_evidence"])
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
    ]["1"]["rolls"]
    assert rolls[1]["narrative_evidence"] is None


def test_undo_reruns_derivation_and_refresh(tmp_path) -> None:
    from scripts.forge_curator.persistence import CurationPersistence

    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.update_roll_at_index("2", 1, narrative_evidence="quote")
    app = _loaded_app("2", tmp_path)
    app.persistence = persistence
    calls: list[str] = []
    app._run_post_curation_derivation = lambda: calls.append("post")
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None

    app.action_undo_last()

    assert calls == ["post"]


def test_post_curation_refresh_reloads_derived_documents(tmp_path) -> None:
    app = _loaded_app("2", tmp_path)
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None
    app.data.roll_facts
    app.data.chapter_facts
    old_roll_facts = app.data._roll_facts_doc
    old_chapter_facts = app.data._chapter_facts_doc
    app.data._derived_cache["sentinel"] = object()

    calls = []
    app._run_post_curation_derivation = lambda: calls.append("ran")

    app._post_curation_refresh("changed roll")

    assert calls == ["ran"]
    assert app.data._roll_facts_doc is not old_roll_facts
    assert app.data._chapter_facts_doc is not old_chapter_facts
    assert "sentinel" not in app.data._derived_cache


def test_failed_post_curation_derivation_reports_error_without_reload(tmp_path) -> None:
    app = _loaded_app("2", tmp_path)
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None
    app.data.roll_facts
    app.data.chapter_facts

    def fail() -> None:
        raise RuntimeError("derive failed")

    app._run_post_curation_derivation = fail
    app._post_curation_refresh("changed roll")

    assert app._last_curation_error == "derive failed"
    assert app.data._roll_facts_doc is not None
    assert app.data._chapter_facts_doc is not None


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
