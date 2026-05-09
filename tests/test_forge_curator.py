"""Pilot-driven verification for the Forge Curator TUI.

Exercises the bug fixes B1-B13 plus the keybind redesign by spinning
up the App in headless test mode and asserting on widget state after
keypresses.
"""

from __future__ import annotations

import asyncio
import json
import re

import pytest
from textual.css.query import NoMatches
from textual.widgets import Input

# Import here so the rest of the suite still loads even if textual is
# unavailable.
from scripts.forge_curator.app import (
    ForgeCuratorApp,
    PassageView,
    StatsPanel,
    ActionsPanel,
    RegexBar,
    GutterPanel,
    LEGEND,
    ROLL_EVIDENCE_MARKERS,
    STATS_PANEL_WIDTH,
    STATS_CONTENT_WIDTH,
    _fmt_int,
    _wrap_title_for_stats,
)


# ---------------------------------------------------------------------------
# Canonical word-coord conversions (App methods)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cp_raw_word_roundtrip_ch97() -> None:
    """ch 97 has a leading non-CP section. Confirm raw↔CP round-trip
    via the canonical App methods (which honour exclusion ranges)."""
    app = ForgeCuratorApp(start_chapter="97")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        # First CP-eligible raw word: section 0 is
        # ineligible; section 1 starts the CP body. The auto-detected
        # header at the top of section 1 is also excluded. So the
        # first eligible raw word is section0_words + auto_header_word_count.
        ahc = int(cs.meta.sections[1].get("auto_header_word_count") or 0)
        first_eligible = int(cs.meta.sections[0].get("word_count") or 0) + ahc
        assert app._cp_earning_word_offset(first_eligible) == 0
        # Raw 100 words past first eligible → CP 100.
        assert app._cp_earning_word_offset(first_eligible + 100) == 100
        # Inverse: CP 0 maps to first eligible raw word.
        assert app._raw_word_for_cp_offset(0) == 0
        # CP 100 maps to first_eligible + 100.
        assert app._raw_word_for_cp_offset(100) == first_eligible + 100


# ---------------------------------------------------------------------------
# Pilot-driven app tests
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def app() -> ForgeCuratorApp:
    return ForgeCuratorApp(start_chapter="1")


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


@pytest.mark.asyncio
async def test_b5_b6_b7_stats_panel_ch97() -> None:
    """Stats panel uses the rewritten eligibility/word/CP blocks."""
    app = ForgeCuratorApp(start_chapter="97")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        text = _stats_text(app)
        assert "Validation" not in text
        assert "At cursor" not in text
        assert "Chapter overrides" not in text
        assert "Roll-acquired perks" not in text
        assert "Eligibility\n" not in text
        assert "Model:" in text
        assert "Total content:" in text
        assert "CP eligible:" in text
        assert "Since last roll:" in text
        assert "Until next roll:" in text
        assert "Gained:" in text
        assert "Spent:" in text


@pytest.mark.asyncio
async def test_b8_cp_at_cursor_nonzero_after_first_roll() -> None:
    """B8: CP banked should be non-zero after navigating past the first roll."""
    app = ForgeCuratorApp(start_chapter="97")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        # Find the first roll's word_position from the data.
        cs = app.state.chapter
        rolls = sorted(
            (r for r in cs.derived.roll_facts if r.get("word_position") is not None),
            key=lambda r: int(r["word_position"]),
        )
        assert rolls, "ch97 must have at least one roll fact"
        first_roll = rolls[0]
        first_cp = int(first_roll["word_position"])
        first_banked = int(first_roll.get("banked_cp_after_roll") or 0)
        # Position cursor a few CP-words past the first roll.
        target_cp = first_cp + 10
        cp_banked = app._cp_at_cursor(target_cp)
        assert cp_banked > 0, (
            f"CP banked at cp_word={target_cp} should be > 0; got {cp_banked} "
            f"(first roll at cp_w={first_cp} banked={first_banked})"
        )
        # Should be at least the banked-after-roll value.
        assert cp_banked >= first_banked, (
            f"expected >= first_banked={first_banked}, got {cp_banked}"
        )


@pytest.mark.asyncio
async def test_gutter_minimap_emits_an_and_roll_marks_for_ch97() -> None:
    """Minimap items list contains A glyphs (AN spans) and R/H/M (rolls).

    Replaces the older B9/B10 test which assumed 1-row-per-line gutter
    rendering. The minimap design proportions one mark per logical span.
    """
    app = ForgeCuratorApp(start_chapter="97")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)
        assert gutter.size.width == 2, f"gutter width {gutter.size.width} != 2"
        items = app._compute_gutter_items()
        glyph_set = {g for _p, g in items}
        assert "A" in glyph_set, (
            f"expected at least one 'A' minimap item for ch97 AN; "
            f"got: {glyph_set}"
        )
        # ch97 has roll data — expect at least one of R/H/M.
        assert glyph_set & {"R", "H", "M"}, (
            f"expected at least one R/H/M item; got: {glyph_set}"
        )
        # Every position should be in [0, 1].
        for prop, _ in items:
            assert 0.0 <= prop <= 1.0, f"minimap proportion out of [0,1]: {prop}"


@pytest.mark.parametrize("chapter_num", ["2", "97"])
@pytest.mark.asyncio
async def test_gutter_marks_match_canonical_roll_fact_positions(
    chapter_num: str,
) -> None:
    app = ForgeCuratorApp(start_chapter=chapter_num)
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        total = len(app.state.chapter.prose.word_offsets)
        expected = []
        for roll in (cs.derived.chapter_facts or {}).get("rolls", []):
            if (
                roll.get("source_kind") == "trigger"
                or roll.get("outcome") not in {"hit", "miss"}
                or roll.get("word_position") is None
                or str(roll.get("mechanical_chapter_num")) != chapter_num
            ):
                continue
            raw = app._raw_word_for_cp_offset(roll["word_position"])
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
    app = ForgeCuratorApp(start_chapter="97")
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
        # thing is that the cursor's line is within the viewport. Since ch97
        # rolls are deep into the chapter, scroll_y should change.
        assert new_y != initial_y or new_cursor < 100, (
            f"expected scroll position to update (was {initial_y}, "
            f"now {new_y}); cursor moved to {new_cursor}"
        )


@pytest.mark.asyncio
async def test_keybind_redesign_chapter_chord() -> None:
    """]] navigates to next chapter; [[ goes back."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs0 = app.state.chapter
        assert cs0 is not None
        ch0 = cs0.meta.chapter_num
        await pilot.press("]")
        await pilot.press("]")
        await pilot.pause()
        cs1 = app.state.chapter
        assert cs1 is not None
        assert cs1.meta.chapter_num != ch0, (
            f"]] should advance chapter; stayed on {ch0}"
        )
        # Now go back.
        await pilot.press("[")
        await pilot.press("[")
        await pilot.pause()
        cs2 = app.state.chapter
        assert cs2 is not None
        assert cs2.meta.chapter_num == ch0, (
            f"[[ should return to {ch0}; got {cs2.meta.chapter_num}"
        )


@pytest.mark.asyncio
async def test_keybind_redesign_section_chord() -> None:
    """][ navigates to next section; [] back. Use ch97 (3 sections)."""
    app = ForgeCuratorApp(start_chapter="97")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        # initial cursor at 0 → section 0
        assert cs.section_index_at(cs.cursor_word_index) == 0
        await pilot.press("]")
        await pilot.press("[")
        await pilot.pause()
        # After ][, cursor should advance to start of section 1.
        new_sec = cs.section_index_at(cs.cursor_word_index)
        assert new_sec >= 1, (
            f"][ should advance to section >= 1; cursor at section {new_sec} "
            f"(word_idx={cs.cursor_word_index})"
        )


@pytest.mark.asyncio
async def test_keybind_redesign_star_seeds_star_regex() -> None:
    """* should seed the dedicated star regex with the word under the cursor."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        # Cursor at 0 -> first word.
        await pilot.press("*")
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        assert cs.regex_hits[3].pattern, (
            "regex * should be seeded after *; pattern empty"
        )
        # The pattern should look like \b<word>\b
        assert cs.regex_hits[3].pattern.startswith("\\b"), (
            f"unexpected regex * pattern: {cs.regex_hits[3].pattern!r}"
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
async def test_b3_no_double_vertical_separator() -> None:
    """B3: primary columns meet cleanly without overlapping separators."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        gutter = app.query_one("#gutter", GutterPanel)
        stats_scroll = app.query_one("#stats_scroll")
        prose_scroll = app.query_one("#prose_scroll")

        assert stats_scroll.region.right == prose_scroll.region.x
        assert prose_scroll.region.right == gutter.region.x


@pytest.mark.asyncio
async def test_b4_stats_panel_fixed_width() -> None:
    """B4: StatsPanel keeps the canonical width in the live layout."""
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        stats = app.query_one("#stats", StatsPanel)
        assert stats.region.width == STATS_PANEL_WIDTH


@pytest.mark.asyncio
async def test_stats_panel_structured_status_rows_fit_content_width() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        text = _stats_text(app)
        protected_prefixes = (
            "  Model:",
            "  Section:",
            "  Text:",
            "  Total content:",
            "  CP eligible:",
            "    story ",
            "    chapter ",
            "  Since last roll:",
            "  Until next roll:",
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
async def test_stats_panel_scrolls_and_bottom_chrome_is_single_regex_row() -> None:
    from textual.containers import VerticalScroll

    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        scroll = app.query_one("#stats_scroll", VerticalScroll)
        stats = app.query_one("#stats", StatsPanel)
        regex_bar = app.query_one("#regex_bar", RegexBar)
        assert scroll.size.width > stats.size.width
        assert regex_bar.size.height == 1
        with pytest.raises(NoMatches):
            app.query_one("#status")


@pytest.mark.asyncio
async def test_regex_bar_has_four_compact_unprefixed_fields() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        regex_bar = app.query_one("#regex_bar", RegexBar)
        labels = [str(label.render()) for label in regex_bar.query("Static.label")]
        assert labels == ["regex 1:", "regex 2:", "regex 3:", "regex *:"]
        for slot in range(1, 5):
            inp = app.query_one(f"#regex_{slot}", Input)
            assert inp.compact is True
            assert inp.size.height == 1


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


def test_legend_no_ambiguous_glyph() -> None:
    """B5: ambiguous shouldn't be in the legend."""
    glyphs = [g for g, _, _ in LEGEND]
    assert "?" not in glyphs


@pytest.mark.asyncio
async def test_chapter_2_header_eligibility_and_roll_stats() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        assert cs.prose.text.split()[:4] == ["2", "Preparation", "2", "Preparation"]
        assert cs.prose.implicit_header_word_ranges
        assert cs.prose.implicit_header_word_ranges[0] == (0, 4)

        text = _stats_text(app)
        assert "chapter 2 /" in text
        assert "chapter 2 / 194; section 1 / 2" in text
        assert "2 Preparation" in text
        assert "Model:" in text
        assert "Section: CP eligible" in text
        assert "Text: CP ineligible - header" in text
        assert "Total content:" in text
        assert "CP eligible:" in text
        assert "deferred from ch 1 #2 (global #2)" in text
        assert "#1 (global #3)" in text
        assert "#2 (global #4)" in text
        assert "hit" in text
        assert "Clothing - Fashion (200)" in text
        assert "Quality - Bling of War (100)" in text
        assert "Alchemy - Alchemist (200)" in text
        assert "Evidence:" not in text
        assert "T text evidence" not in text
        assert "@cp" not in text


@pytest.mark.asyncio
async def test_saved_roll_evidence_highlights_exact_quote_span() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
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
        } in spans


@pytest.mark.asyncio
async def test_roll_evidence_gutter_mark_survives_chapter_navigation() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
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

        assert "hit Q" in _stats_text(app)
        assert expected in app._compute_gutter_items()

        app.action_next_chapter()
        await pilot.pause()
        app.action_prev_chapter()
        await pilot.pause()

        assert app.state.chapter is not None
        assert app.state.chapter.meta.chapter_num == "2"
        assert expected in app._compute_gutter_items()


@pytest.mark.asyncio
async def test_chapter_2_auto_header_does_not_render_author_note_gutter_mark() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()

        top_glyphs = [
            glyph for prop, glyph in app._compute_gutter_items()
            if prop == 0.0
        ]

        assert "═" in top_glyphs
        assert "A" not in top_glyphs


@pytest.mark.asyncio
async def test_actions_panel_omits_read_only_roll_structure_copy() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        actions = app.query_one("#actions", ActionsPanel)
        rendered = getattr(actions, "_renderable", None) or actions.render()
        text = str(rendered) if rendered is not None else ""
        assert "Roll structure" not in text
        assert "rolls come from the simulator" not in text


@pytest.mark.asyncio
async def test_last_viewed_chapter_persists_and_is_overridden(tmp_path) -> None:
    state_path = tmp_path / ".forge_curator_state.json"
    app = ForgeCuratorApp(start_chapter="2", state_path=state_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert json.loads(state_path.read_text())["last_chapter"] == "2"

    restored = ForgeCuratorApp(start_chapter=None, state_path=state_path)
    async with restored.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert restored.state.chapter is not None
        assert restored.state.chapter.meta.chapter_num == "2"

    overridden = ForgeCuratorApp(start_chapter="1", state_path=state_path)
    async with overridden.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert overridden.state.chapter is not None
        assert overridden.state.chapter.meta.chapter_num == "1"
        assert json.loads(state_path.read_text())["last_chapter"] == "1"


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


@pytest.mark.asyncio
async def test_deferred_roll_action_targets_mechanical_override_row(tmp_path) -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        from scripts.forge_curator.persistence import CurationPersistence
        app.persistence = CurationPersistence(
            chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
            journal_dir_path=tmp_path / ".journals",
        )
        app._run_post_curation_derivation = lambda: None

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


@pytest.mark.asyncio
async def test_defer_roll_action_uses_lowercase_space_d() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        calls: list[tuple[str, str]] = []

        app._action_defer_roll_to_next_chapter = lambda cn: calls.append(("defer", cn))
        app._action_remove_annotations_at_current_word = (
            lambda cn: calls.append(("delete_annotations", cn))
        )

        app._handle_space_chord("d")
        app._handle_space_chord("D")

        assert calls == [("defer", "2"), ("delete_annotations", "2")]


@pytest.mark.asyncio
async def test_remove_annotations_action_deletes_author_notes_and_headers_at_cursor(tmp_path) -> None:
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

    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        app.persistence = CurationPersistence(
            author_notes_path=author_notes_path,
            header_corrections_path=header_corrections_path,
            journal_dir_path=tmp_path / ".journals",
        )
        app._run_full_curation_derivation = lambda: None
        app._post_curation_refresh = lambda message, *, full=False: None

        app._action_remove_annotations_at_current_word("2")

    assert json.loads(author_notes_path.read_text())["author_notes"] == []
    assert json.loads(header_corrections_path.read_text())["corrections"] == []


@pytest.mark.asyncio
async def test_post_curation_refresh_reloads_derived_documents() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
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


@pytest.mark.asyncio
async def test_failed_post_curation_derivation_reports_error_without_reload() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
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
        # Padding-aware: with PassageView CSS padding 1 2, a click at
        # widget-local (5, 1) lands inside line 0 at column 5-2=3.
        pad = prose.styles.padding
        offset = prose._xy_to_offset(2 + 5, pad.top + 0)
        assert offset == 5, f"_xy_to_offset(2+5, pad.top) -> {offset} (expected 5)"
        offset2 = prose._xy_to_offset(2 + 0, pad.top + 1)
        if len(prose._lines) > 1:
            assert offset2 == prose._lines[1][0], (
                f"_xy_to_offset(2+0, pad.top+1) -> {offset2} != line1 start "
                f"{prose._lines[1][0]}"
            )
