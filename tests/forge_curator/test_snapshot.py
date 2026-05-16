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
    assert snapshot["rolls"][0]["roll_number"] == 1
    assert snapshot["derived"]["chapter_facts"]["chapter_num"] == "1"
    assert snapshot["derived"]["roll_facts"][0]["roll_number"] == 1
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


def test_snapshot_includes_fixture_deferred_predicted_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.mark_roll_deferred_to_chapter("1", 1, "2")

    app.action_snapshot()
    snapshot = json.loads(fixture.snapshot_path.read_text())

    deferred = [
        roll for roll in snapshot["rolls"]
        if roll.get("display_kind") == "deferred_in"
        and roll.get("source_kind") == "predicted_slot"
    ]
    assert len(deferred) == 1
    assert deferred[0]["target_chapter_num"] == "1"
    assert deferred[0]["target_roll_index"] == 1
    assert deferred[0]["visible_chapter_num"] == "2"
    assert deferred[0]["mechanical_chapter_num"] == "1"
    assert deferred[0]["mention_chapter_num"] == "2"
    assert deferred[0]["roll_number"] == 1
    assert deferred[0]["evidence_quotes"] == []
