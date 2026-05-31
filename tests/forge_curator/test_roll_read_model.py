from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tests.helpers.forge_curator_fixture import (
    _chapter_fact,
    _chapter_html,
    _chapter_words,
    _roll_fact,
    _section,
    _write_json,
    forge_curator_fixture,
)


def _add_fixture_chapter(fixture, chapter_num: str = "3") -> None:
    title = f"{chapter_num} Fixture"
    with zipfile.ZipFile(fixture.epub, "a") as zf:
        zf.writestr(f"EPUB/chap_{chapter_num}.xhtml", _chapter_html(chapter_num))

    chapters = json.loads((fixture.derived / "chapters.json").read_text())
    chapters["chapters"].append({
        "chapter_num": chapter_num,
        "full_title": title,
        "epub_href": f"chap_{chapter_num}.xhtml",
        "sort_key": [int(chapter_num), 0],
    })
    _write_json(fixture.derived / "chapters.json", chapters)

    sections = json.loads((fixture.derived / "chapter_sections.json").read_text())
    sections["chapters"].append({
        "chapter_num": chapter_num,
        "full_title": title,
        "epub_href": f"chap_{chapter_num}.xhtml",
        "total_word_count": len(_chapter_words(chapter_num)),
        "sections": [_section(chapter_num)],
    })
    _write_json(fixture.derived / "chapter_sections.json", sections)

    chapter_facts = json.loads((fixture.derived / "chapter_facts.json").read_text())
    cp_start = sum(
        len(_chapter_words(ch["chapter_num"]))
        for ch in chapters["chapters"]
        if int(ch["chapter_num"]) < int(chapter_num)
    )
    chapter_facts["chapters"].append(_chapter_fact(chapter_num, title, cp_start=cp_start))
    _write_json(fixture.derived / "chapter_facts.json", chapter_facts)

    roll_facts = json.loads((fixture.derived / "roll_facts.json").read_text())
    roll_facts["rolls"].append(_roll_fact(chapter_num, cp_start=cp_start))
    _write_json(fixture.derived / "roll_facts.json", roll_facts)

    predicted = json.loads((fixture.derived / "predicted_rolls.json").read_text())
    predicted["predicted"].append({
        "chapter_num": chapter_num,
        "slot_index": 1,
        "cp_offset": cp_start + 20,
        "epub_offset": cp_start + 20,
        "roll_number": int(chapter_num),
    })
    _write_json(fixture.derived / "predicted_rolls.json", predicted)

    validation = json.loads((fixture.derived / "roll_validation.json").read_text())
    validation["chapter_checks"].append({"chapter_num": chapter_num})
    _write_json(fixture.derived / "roll_validation.json", validation)


def test_roll_slot_rows_merge_assigned_rolls_and_open_predicted_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None

    unified = app._unified_rolls(cs)
    rows = app._roll_slot_rows(cs, unified)

    assert [
        (
            row["display_kind"],
            row["target_roll_index"],
            row["predicted_ordinal"],
            row["outcome"],
        )
        for row in rows
    ] == [
        ("chapter_roll", 1, 2, "miss"),
        ("predicted_slot", 2, 3, "open"),
    ]
    assert rows[0]["source"] == "curator_rolls"
    assert rows[1]["mechanical_cumulative_word_offset"] == 120


def test_prior_roll_visible_only_by_mention_chapter_is_quote_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    prior_roll = dict(app.data.roll_facts["rolls"][0])
    prior_roll.update({
        "chapter_num": "2",
        "source_ordinal": None,
        "source_label": None,
        "source_chapter_num": None,
        "source_chapter_ordinal": None,
        "source_roll_label": None,
        "source_word_position": None,
        "source_cumulative_word_offset": None,
        "mention_chapter_num": "2",
        "mention_word_position": None,
        "display_chapter_num": "1",
        "display_position_policy": "mechanical",
        "visible_chapter_nums": ["1", "2"],
        "evidence_quotes": [],
    })
    cs.derived.roll_facts.insert(0, prior_roll)

    rows = app._roll_slot_rows(cs, app._unified_rolls(cs))
    quote_targets = app._current_chapter_roll_evidence_picker_rolls(cs)

    assert ("1", 1) in [
        (row["target_chapter_num"], row["target_roll_index"])
        for row in rows
    ]
    assert ("1", 1) in [
        (row["target_chapter_num"], row["target_roll_index"])
        for row in quote_targets
    ]


def test_source_assignment_targets_include_previous_unassigned_rolls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    previous_roll = roll_facts["rolls"][0]
    previous_roll.update({
        "source": "roll_outcomes",
        "source_kind": "interpolated",
        "source_ordinal": None,
        "source_label": None,
        "source_chapter_num": None,
        "source_chapter_ordinal": None,
        "source_roll_label": None,
        "association_source": "none",
    })
    _write_json(roll_facts_path, roll_facts)

    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None

    targets = app._source_assignment_target_rows(cs)

    assert [
        (row["target_chapter_num"], row["target_roll_index"])
        for row in targets
    ] == [
        ("1", 1),
        ("2", 1),
        ("2", 2),
    ]


def test_source_assignment_targets_include_all_prior_unassigned_open_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _add_fixture_chapter(fixture, "3")
    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    prior_roll = roll_facts["rolls"][0]
    prior_roll.update({
        "source": "roll_outcomes",
        "source_kind": "interpolated",
        "source_ordinal": None,
        "source_label": None,
        "source_chapter_num": None,
        "source_chapter_ordinal": None,
        "source_roll_label": None,
        "association_source": "none",
    })
    _write_json(roll_facts_path, roll_facts)

    app = fixture.loaded_app("3")
    cs = app.state.chapter
    assert cs is not None

    targets = app._source_assignment_target_rows(cs)

    assert ("1", 1) in [
        (row["target_chapter_num"], row["target_roll_index"])
        for row in targets
    ]


def test_source_assignment_targets_exclude_prior_skipped_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _add_fixture_chapter(fixture, "3")
    app = fixture.loaded_app("1")
    app.persistence.mark_roll_skipped("1", 1)
    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    prior_roll = roll_facts["rolls"][0]
    prior_roll.update({
        "source": "roll_outcomes",
        "source_kind": "interpolated",
        "source_ordinal": None,
        "source_label": None,
        "source_chapter_num": None,
        "source_chapter_ordinal": None,
        "source_roll_label": None,
        "association_source": "none",
        "skipped": True,
    })
    _write_json(roll_facts_path, roll_facts)

    app = fixture.loaded_app("3")
    cs = app.state.chapter
    assert cs is not None

    targets = app._source_assignment_target_rows(cs)

    assert ("1", 1) not in [
        (row["target_chapter_num"], row["target_roll_index"])
        for row in targets
    ]


def test_source_roll_picker_uses_source_ordinals_without_legacy_roll_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    source_rows = [
        dict(app.data.roll_facts["rolls"][1], roll_number=None),
        dict(
            app.data.roll_facts["rolls"][1],
            roll_ordinal=3,
            roll_label="R3",
            source_ordinal=4,
            source_label="S4",
            source_chapter_ordinal=2,
            raw="Roll 2 again",
        ),
    ]
    for ordinal, row in enumerate(source_rows, start=2):
        row.update({
            "chapter_num": "2",
            "source_chapter_num": "2",
            "source_ordinal": ordinal,
            "source_label": f"S{ordinal}",
        })
    app.data.roll_facts["rolls"] = source_rows

    rows = app._source_roll_picker_rows("2")

    assert [(row["source_ordinal"], row["source_chapter_ordinal"]) for row in rows] == [
        (2, 1),
        (3, 2),
    ]


def test_source_roll_picker_includes_rows_by_source_chapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    roll_facts["rolls"][0].update({
        "chapter_num": "1",
        "mechanical_chapter_num": "1",
        "source_chapter_num": "2",
        "source_chapter_ordinal": 1,
        "source_ordinal": 1,
        "source_label": "S1",
    })
    _write_json(roll_facts_path, roll_facts)
    app = fixture.loaded_app("2")

    rows = app._source_roll_picker_rows("2")

    assert any(
        row.get("source_ordinal") == 1
        and row.get("source_chapter_num") == "2"
        for row in rows
    )


def test_same_chapter_rolls_remain_current_and_cross_chapter_display_stays_chapter_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None

    current = app._unified_rolls(cs)[0]
    assert current["display_kind"] == "chapter_roll"
    assert current["target_chapter_num"] == "2"

    cs.derived.roll_facts = [
        {
            "roll_number": 99,
            "chapter_num": "2",
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "2",
            "display_word_position": 24,
            "display_cumulative_word_offset": 104,
            "mention_chapter_num": "2",
            "mention_word_position": 24,
            "display_position_policy": "mention",
            "source_kind": "miss",
            "source": "curator_rolls",
            "outcome": "miss",
            "available_cp": 100,
            "evidence_quotes": [],
            "word_position": 20,
            "raw_word_position": 24,
        }
    ]

    projected = app._unified_rolls(cs)
    assert len(projected) == 1
    assert projected[0]["display_kind"] == "chapter_roll"
    assert projected[0]["target_chapter_num"] == "1"
    assert projected[0]["word_position"] == 24


def test_roll_evidence_targets_include_source_only_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    current = {
        "display_kind": "chapter_roll",
        "target_chapter_num": "2",
        "target_roll_index": 1,
        "word_position": 20,
        "roll_number": 2,
        "outcome": "hit",
    }
    source_only = {
        "display_kind": "chapter_roll",
        "target_chapter_num": "2",
        "target_roll_index": 3,
        "word_position": 40,
        "roll_number": 4,
        "outcome": "miss",
        "mechanical_word_position": None,
        "display_word_position": None,
    }
    skipped = {
        "display_kind": "predicted_slot",
        "target_chapter_num": "2",
        "target_roll_index": 2,
        "word_position": 40,
        "skipped": True,
    }
    app._unified_rolls = lambda _cs: [current, source_only]
    app._roll_slot_rows = lambda _cs, unified=None: [current, skipped]

    rows = app._roll_evidence_picker_rolls(cs)

    assert any(row.get("roll_number") == 4 for row in rows)
    assert all(not row.get("skipped") for row in rows)


def test_open_predicted_slot_exposes_saved_quote_for_evidence_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text="open slot quote",
        mention_chapter_num="2",
        mention_word_position=42,
    )
    cs = app.state.chapter
    assert cs is not None

    rows = app._roll_slot_rows(cs)
    open_slot = next(
        row for row in rows
        if row.get("display_kind") == "predicted_slot"
        and row.get("target_chapter_num") == "2"
        and row.get("target_roll_index") == 2
    )

    assert open_slot["evidence_quotes"] == [
        {
            "text": "open slot quote",
            "mention_chapter_num": "2",
            "mention_word_position": 42,
        }
    ]


def test_action_target_uses_mechanical_slot_when_visual_marker_is_later(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.set_roll_visualization_anchor(
        "1",
        1,
        mention_chapter_num="2",
        mention_word_position=None,
        display_position_policy="mechanical",
    )
    cs = app.state.chapter
    assert cs is not None
    chapter_roll = next(
        roll for roll in cs.derived.roll_facts
        if str(roll.get("mechanical_chapter_num")) == "2"
    )
    chapter_roll["display_position_policy"] = "mention"
    chapter_roll["display_word_position"] = 60
    chapter_roll["display_cumulative_word_offset"] = 140
    chapter_roll["mention_word_position"] = 60

    target = app._current_roll_target(word_idx=21)

    assert target is not None
    assert target["display_kind"] == "chapter_roll"
    assert target["target_chapter_num"] == "2"
    assert target["target_roll_index"] == 1


def test_source_projection_keeps_mechanical_target_identity(
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
            "roll_sequence_in_chapter": 1,
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "display_chapter_num": "1",
            "display_word_position": 20,
            "display_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_chapter_ordinal": 1,
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected]
    app.data.roll_facts["rolls"] = [source_projected]
    app.persistence.assign_source_ordinal_at_index("1", 1, 2)

    projected = app._unified_rolls(cs)[0]

    assert projected["display_kind"] == "chapter_roll"
    assert projected["target_chapter_num"] == "1"
    assert projected["target_roll_index"] == 1
    assert projected["source_ordinal"] == 2
    assert app._is_source_link_source(projected) is True
    assert app._is_source_link_target(projected) is True
