from __future__ import annotations

import re
from pathlib import Path

import pytest
from textual.widgets import Input

from scripts.forge_curator.app import PassageView
from scripts.forge_curator.evidence_scorer import EvidenceCandidate
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def _word_offsets(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in re.finditer(r"\S+", text)]


@pytest.mark.asyncio
async def test_gg_then_j_moves_cursor_one_visual_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.press("g", "g")
        prose = app.query_one("#prose", PassageView)
        prose._recompute_lines()
        line0 = next(i for i, (start, end) in enumerate(prose._lines) if start <= 0 <= end)

        await pilot.press("j")
        prose._recompute_lines()
        line1 = next(
            i for i, (start, end) in enumerate(prose._lines)
            if start <= prose.cursor <= end
        )

        assert line1 == line0 + 1


@pytest.mark.asyncio
async def test_roll_chord_jumps_to_next_predicted_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("2")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None

        app._jump_to_word(0)
        await pilot.press("]")
        await pilot.press("R")
        await pilot.pause()

        assert cs.cursor_word_index == 20


@pytest.mark.asyncio
async def test_chapter_and_section_chords_use_fixture_navigation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs0 = app.state.chapter
        assert cs0 is not None
        app._jump_to_word(20)
        await pilot.press("]")
        await pilot.press("]")
        await pilot.pause()
        cs1 = app.state.chapter
        assert cs1 is not None
        assert cs1.meta.chapter_num == "2"
        assert cs1.cursor_word_index == 0

        app._jump_to_word(20)
        await pilot.press("[")
        await pilot.press("[")
        await pilot.pause()
        cs2 = app.state.chapter
        assert cs2 is not None
        assert cs2.meta.chapter_num == "1"
        assert cs2.cursor_word_index == len(cs2.prose.word_offsets) - 1

        cs2.prose.section_break_word_indices = [40]
        app._jump_to_word(0)
        await pilot.press("]")
        await pilot.press("[")
        await pilot.pause()
        assert cs2.section_index_at(cs2.cursor_word_index) == 1


@pytest.mark.asyncio
async def test_star_regex_and_z_motions_search_from_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        prose = app.query_one("#prose", PassageView)

        app._jump_to_word(1)
        await pilot.press("*")
        await pilot.pause()

        hits = cs.regex_hits[3].word_indices
        assert app.active_regex_slot == 3
        assert app.query_one("#regex_4", Input).has_class("active")
        assert hits[:3] == [1, 9, 17]
        assert cs.cursor_word_index == 9

        await pilot.press("v")
        await pilot.press("z")
        await pilot.pause()
        assert prose.visual_mode is True
        assert cs.cursor_word_index == 17

        await pilot.press("Z")
        await pilot.pause()
        assert prose.visual_mode is True
        assert cs.cursor_word_index == 9


@pytest.mark.asyncio
async def test_regex_submit_searches_forward_from_current_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None

        app.state.set_regex(3, r"\bforge\b")
        app._jump_to_word(9)
        inp = app.query_one("#regex_4", Input)
        inp.value = r"\bforge\b"

        app._on_regex_submit(type("Submitted", (), {"input": inp})())

        assert cs.cursor_word_index == 17


@pytest.mark.asyncio
async def test_n_and_upper_n_jump_scored_evidence_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        cs.evidence_candidates = [
            EvidenceCandidate(0, 0, 0, 24, 4, ("forge",)),
            EvidenceCandidate(1, 0, 0, 48, 4, ("motes",)),
        ]

        app._jump_to_word(30)
        await pilot.press("n")
        await pilot.pause()
        assert cs.cursor_word_index == 48

        await pilot.press("N")
        await pilot.pause()
        assert cs.cursor_word_index == 24


@pytest.mark.asyncio
async def test_quote_helper_motions_jump_articles_constellations_and_connection_words(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("1")

    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cs = app.state.chapter
        assert cs is not None
        prose = app.query_one("#prose", PassageView)
        text = (
            "setup words before the Time constellation passed by without "
            "a connection after"
        )
        cs.prose.text = text
        cs.prose.word_offsets = _word_offsets(text)
        prose.set_text(text)
        phrase = "the Time constellation passed by without a connection"
        phrase_start = text.find(phrase)
        assert phrase_start >= 0

        app._jump_to_char(phrase_start - 2)
        await pilot.press("x")
        await pilot.pause()
        assert prose.cursor == phrase_start

        app._jump_to_char(phrase_start + len("the Time constellation"))
        await pilot.press("X")
        await pilot.pause()
        assert prose.cursor == phrase_start

        app._jump_to_char(phrase_start)
        await pilot.press("c")
        await pilot.pause()
        assert prose.visual_mode is False
        assert prose.cursor == phrase_start + len("the Time") - 1

        app._jump_to_char(phrase_start)
        await pilot.press("v")
        await pilot.press("n")
        await pilot.pause()
        assert prose.visual_mode is True
        assert prose.anchor == phrase_start
        assert prose.cursor == phrase_start + len("the Time constellation") - 1
