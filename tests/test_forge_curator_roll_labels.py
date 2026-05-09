from __future__ import annotations

from pathlib import Path

import pytest

from scripts.forge_curator.app import ForgeCuratorApp
from scripts.forge_curator.persistence import CurationPersistence


@pytest.mark.asyncio
async def test_chapter_1_roll_attempt_index_excludes_trigger() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        chapter_state = app.state.chapter
        assert chapter_state is not None

        rolls = app._unified_rolls(chapter_state)
        assert len(rolls) >= 1
        assert rolls[0]["roll_number"] == 1
        assert rolls[0]["index"] == 1

        rendered = app._format_roll_stat_line(rolls[0], "▸")
        assert "#1 (global #1) miss" in rendered
        assert "#2 (global #1)" not in rendered


@pytest.mark.asyncio
async def test_chapter_1_roll_list_includes_deferred_display_roll() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        chapter_state = app.state.chapter
        assert chapter_state is not None

        rolls = app._unified_rolls(chapter_state)

        assert [r["index"] for r in rolls] == [1, 2]
        assert [r["roll_number"] for r in rolls] == [1, 2]
        assert rolls[1]["outcome"] == "hit"
        assert rolls[1]["mechanical_chapter_num"] == "1"
        assert rolls[1]["display_chapter_num"] == "1"
        assert rolls[1]["purchased_perks"][0]["name"] == "Fashion"


@pytest.mark.asyncio
async def test_chapter_2_roll_list_starts_with_deferred_in_roll() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        chapter_state = app.state.chapter
        assert chapter_state is not None

        rolls = app._unified_rolls(chapter_state)

        assert rolls[0]["display_kind"] == "deferred_in"
        assert rolls[0]["target_chapter_num"] == "1"
        assert rolls[0]["target_roll_index"] == 2
        assert rolls[0]["roll_number"] == 2
        assert rolls[0]["available_cp"] == 200
        assert rolls[0]["purchased_perks"][0]["name"] == "Fashion"
        assert rolls[1]["display_kind"] == "chapter_roll"
        assert rolls[1]["target_chapter_num"] == "2"
        assert rolls[1]["target_roll_index"] == 1


@pytest.mark.asyncio
async def test_chapter_2_stats_header_counts_deferred_in_roll() -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        stats = app.query_one("#stats")
        rendered = getattr(stats, "_renderable", None) or stats.render()
        text = str(rendered)

        assert "Rolls (4 predicted +1 deferred)" in text
        assert "deferred from ch 1 #2 (global #2) hit" in text
        assert "available CP at slot: 200" in text


@pytest.mark.asyncio
async def test_unified_rolls_ignore_manual_quote_until_derived_regenerated(
    tmp_path: Path,
) -> None:
    app = ForgeCuratorApp(start_chapter="2")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        chapter_state = app.state.chapter
        assert chapter_state is not None
        app.persistence = CurationPersistence(
            chapter_roll_overrides_path=tmp_path / "chapter_roll_overrides.json",
            journal_dir_path=tmp_path / ".journals",
        )

        app.persistence.update_roll_at_index(
            "2", 1, narrative_evidence="manual quote not yet derived"
        )
        rolls = app._unified_rolls(chapter_state)

        assert rolls[1]["target_chapter_num"] == "2"
        assert rolls[1]["target_roll_index"] == 1
        assert rolls[1].get("narrative_evidence") != "manual quote not yet derived"


@pytest.mark.asyncio
async def test_chapter_1_roll_jumps_reach_deferred_display_roll() -> None:
    app = ForgeCuratorApp(start_chapter="1")
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        chapter_state = app.state.chapter
        assert chapter_state is not None
        rolls = app._unified_rolls(chapter_state)

        first_raw = app._raw_word_for_cp_offset(int(rolls[0]["word_position"]))
        second_raw = app._raw_word_for_cp_offset(int(rolls[1]["word_position"]))

        app._jump_to_word(first_raw)
        app._jump_roll_predicted(forward=True)
        await pilot.pause()
        assert chapter_state.cursor_word_index == second_raw

        app._jump_to_word(first_raw)
        app._jump_roll_quoted(forward=True)
        await pilot.pause()
        assert chapter_state.cursor_word_index == second_raw


def test_mark_roll_deferred_preserves_existing_outcome(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )
    persistence.update_roll_at_index("1", 2, outcome="hit")

    persistence.mark_roll_deferred_to_chapter("1", 2, "2")

    rolls = (
        persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"]
    )
    assert rolls[1]["outcome"] == "hit"
    assert rolls[1]["mention_chapter_num"] == "2"
    assert rolls[1]["mention_word_position"] is None
    assert rolls[1]["display_position_policy"] == "mechanical"


def test_mark_roll_deferred_creates_unset_outcome_stub(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=path,
        journal_dir_path=tmp_path / ".journals",
    )

    persistence.mark_roll_deferred_to_chapter("1", 2, "2")

    rolls = (
        persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"]
    )
    assert len(rolls) == 2
    assert rolls[1]["outcome"] is None
    assert rolls[1]["mention_chapter_num"] == "2"
    assert rolls[1]["mention_word_position"] is None
    assert rolls[1]["display_position_policy"] == "mechanical"
