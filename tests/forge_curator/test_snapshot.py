from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.forge_curator_fixture import forge_curator_fixture


def test_snapshot_writes_fixture_backed_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    app.state.set_cursor_char(cs.prose.word_offsets[3][0])
    app.state.set_regex(3, "motes|connection")

    app.action_snapshot()
    snapshot = json.loads(fixture.snapshot_path.read_text())

    assert snapshot["snapshot_version"] == 1
    assert snapshot["snapshot_kind"] == "forge_curator_tui"
    assert snapshot["chapter"]["chapter_num"] == "1"
    assert snapshot["cursor"]["word_index"] == 3
    assert snapshot["active_regex_slot"] == 3
    assert snapshot["regex"][0]["slot"] == "*"
    assert snapshot["regex"][0]["pattern"] == "motes|connection"
    assert snapshot["regex"][0]["word_indices"]
    assert snapshot["rolls"][0]["roll_ordinal"] == 1
    assert snapshot["rolls"][0]["roll_label"] == "R1"
    assert snapshot["derived"]["chapter_facts"]["chapter_num"] == "1"
    assert snapshot["derived"]["roll_facts"][0]["roll_ordinal"] == 1
    assert snapshot["prose"]["text"].startswith("chapter1 forge motes")


@pytest.mark.asyncio
async def test_ctrl_s_writes_fixture_backed_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.app("2")

    async with app.run_test(size=(140, 40)) as pilot:
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    snapshot = json.loads(fixture.snapshot_path.read_text())
    assert snapshot["snapshot_kind"] == "forge_curator_tui"
    assert snapshot["chapter"]["chapter_num"] == "2"


def test_snapshot_includes_cross_chapter_source_projection_as_roll(
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
            "roll_sequence_in_chapter": 2,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "1",
            "display_word_position": 20,
            "display_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_chapter_ordinal": 1,
            "source_word_position": 40,
            "source_cumulative_word_offset": 120,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]

    app.action_snapshot()
    snapshot = json.loads(fixture.snapshot_path.read_text())

    projected = next(
        roll for roll in snapshot["rolls"]
        if roll.get("target_chapter_num") == "1"
        and roll.get("target_roll_index") == 2
    )
    assert projected["display_kind"] == "chapter_roll"
    assert projected["source_chapter_num"] == "2"
