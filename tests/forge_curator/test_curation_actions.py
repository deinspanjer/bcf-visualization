from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.forge_curator.app import (
    BatchMissQuotePicker,
    QuoteMoveSourcePicker,
    QuoteMoveTargetPicker,
    RollEvidencePicker,
    SourceLinkPicker,
)
from scripts.forge_curator.data_loader import _compute_word_offsets
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

    cp_start = sum(
        len(_chapter_words(ch["chapter_num"]))
        for ch in chapters["chapters"]
        if int(ch["chapter_num"]) < int(chapter_num)
    )
    chapter_facts = json.loads((fixture.derived / "chapter_facts.json").read_text())
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


def _clear_first_source_assignment(fixture) -> None:
    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    roll_facts["rolls"][0].update({
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


def _selected_prose(selection: tuple[int, int]) -> SimpleNamespace:
    return SimpleNamespace(
        selection=selection,
        cursor=selection[0],
        anchor=selection[1],
        visual_mode=True,
        visual_line_mode=False,
        selected_text="",
        refresh=lambda: None,
    )


def _cursor_prose() -> SimpleNamespace:
    return SimpleNamespace(
        selection=None,
        cursor=0,
        anchor=None,
        visual_mode=False,
        visual_line_mode=False,
        selected_text="",
        refresh=lambda: None,
    )


def _saved_quote_span(app, cs, quote: dict) -> tuple[int, int]:
    span = app._quote_text_char_span(cs, quote)
    assert span is not None
    assert span[0] < span[1]
    return span


def test_evidence_block_marks_quote_under_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    quote_start, _quote_end = _saved_quote_span(
        app, cs, cs.derived.roll_facts[0]["evidence_quotes"][0]
    )
    cs.cursor_char = quote_start + len("forge ")
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _cursor_prose())

    evidence = app._evidence_block(cs)

    assert "▸ Q1 against ch 1 #1 (R1/P1/S1)" in evidence


def test_evidence_block_renders_without_mounted_prose_view(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None

    evidence = app._evidence_block(cs)

    assert "Q1 against ch 1 #1 (R1/P1/S1)" in evidence


def test_metadata_only_quote_without_prose_match_does_not_target_roll_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    metadata_quote = {
        "text": "metadata note that is not in prose",
        "mention_chapter_num": "1",
        "mention_word_position": None,
    }
    cs.derived.roll_facts[0]["evidence_quotes"] = [metadata_quote]
    app.data.roll_facts["rolls"][0]["evidence_quotes"] = [metadata_quote]
    cs.cursor_char = cs.prose.word_offsets[20][0]
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _cursor_prose())

    spans = app._roll_evidence_char_spans(cs)
    targets = app._roll_evidence_quote_targets_at_selection_or_cursor()

    assert spans == []
    assert targets == []


def test_save_quote_action_writes_manual_roll_evidence_and_refreshes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[24][0]
    end = cs.prose.word_offsets[27][1]
    refreshes: list[str] = []
    monkeypatch.setattr(
        app, "query_one", lambda *args, **kwargs: _selected_prose((start, end))
    )
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_save_quote("1")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {
            "text": cs.prose.text[start:end].strip(),
            "mention_chapter_num": "1",
            "mention_word_position": 24,
        }
    ]
    assert refreshes == [
        f"roll #1 quote saved ({len(cs.prose.text[start:end].strip())} chars)"
    ]


def test_save_quote_targets_selection_start_not_visual_cursor_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[20][0]
    end = cs.prose.word_offsets[40][0]
    prose = _selected_prose((start, end))
    prose.cursor = end
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    app._post_curation_refresh = lambda _message: None

    app._action_save_quote("2")

    saved = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[0]["evidence_quotes"]
    assert len(saved) == 1


def test_save_quote_ignores_later_prior_open_slot_when_current_roll_is_at_cursor(
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
    predicted_path = fixture.derived / "predicted_rolls.json"
    predicted = json.loads(predicted_path.read_text())
    predicted["predicted"][0]["cp_offset"] = 60
    predicted["predicted"][0]["epub_offset"] = 60
    _write_json(predicted_path, predicted)

    app = fixture.loaded_app("3")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[24][0]
    end = cs.prose.word_offsets[27][1]
    monkeypatch.setattr(
        app, "query_one", lambda *args, **kwargs: _selected_prose((start, end))
    )
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    flashes: list[str] = []
    app._flash = lambda message: flashes.append(message)

    app._action_save_quote("3")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    chapter_overrides = overrides["chapter_roll_overrides"]
    assert "1" not in chapter_overrides
    saved = chapter_overrides["3"]["rolls"][0]["evidence_quotes"]
    assert saved == [
        {
            "text": cs.prose.text[start:end].strip(),
            "mention_chapter_num": "3",
            "mention_word_position": 24,
        }
    ]
    assert not flashes
    assert refreshes == [f"roll #1 quote saved ({len(cs.prose.text[start:end].strip())} chars)"]


def test_save_quote_prefers_current_roll_over_prior_visible_evidence_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    prior_roll = dict(app.data.roll_facts["rolls"][0])
    prior_roll.update({
        "visible_chapter_nums": ["1", "2"],
        "source_chapter_num": "2",
        "source_word_position": 25,
        "source_cumulative_word_offset": 105,
    })
    cs.derived.roll_facts.insert(0, prior_roll)
    start = cs.prose.word_offsets[30][0]
    end = cs.prose.word_offsets[33][1]
    monkeypatch.setattr(
        app, "query_one", lambda *args, **kwargs: _selected_prose((start, end))
    )
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    app._action_save_quote("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    chapter_overrides = overrides["chapter_roll_overrides"]
    assert "1" not in chapter_overrides
    saved = chapter_overrides["2"]["rolls"][0]["evidence_quotes"]
    assert saved == [
        {
            "text": cs.prose.text[start:end].strip(),
            "mention_chapter_num": "2",
            "mention_word_position": 30,
        }
    ]
    assert refreshes == [
        f"roll #1 quote saved ({len(cs.prose.text[start:end].strip())} chars)"
    ]


def test_save_quote_exits_visual_mode_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[20][0]
    end = cs.prose.word_offsets[23][1]
    prose = _selected_prose((start, end))
    prose.cursor = end
    prose.anchor = start
    cs.cursor_char = end
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    app._post_curation_refresh = lambda _message: None

    app._action_save_quote("2")

    assert prose.anchor is None
    assert prose.visual_mode is False
    assert prose.visual_line_mode is False


def test_batch_miss_quote_action_previews_detected_match_and_persists_checked_quote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    cs = app.state.chapter
    assert cs is not None
    cs.prose.text = (
        "intro words before the roll anchor. "
        "The Magic constellation missed a connection. "
        "ordinary prose after the evidence."
    )
    cs.prose.word_offsets = _compute_word_offsets(cs.prose.text)
    cs.derived.roll_facts[0]["evidence_quotes"] = []
    app.data.roll_facts["rolls"][0]["evidence_quotes"] = []
    refreshes: list[str] = []
    pushed: list[BatchMissQuotePicker] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    monkeypatch.setattr(app, "push_screen", lambda screen: pushed.append(screen))
    monkeypatch.setattr(app, "call_after_refresh", lambda callback: callback())

    app._action_batch_match_miss_quotes("1")

    assert len(pushed) == 1
    picker = pushed[0]
    assert picker._matches[0]["quote_text"] == "The Magic constellation missed a connection."
    assert "constellation Magic" in picker._matches[0]["source_context"]
    assert picker._matches[0]["quote_variants"][0]["label"] == "focused"
    assert picker._matches[0]["record"]["source_ordinal"] == 1
    picker._on_confirm([picker._matches[0]["id"]])

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {
            "text": "The Magic constellation missed a connection.",
            "mention_chapter_num": "1",
            "mention_word_position": 6,
        }
    ]
    assert refreshes == ["matched 1 miss quote"]


def test_batch_miss_quote_persistence_uses_source_ordinal_when_index_is_occupied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    app.persistence.update_roll_at_index(
        "1",
        2,
        outcome="hit",
        constellation="Toolkits",
        source_ordinal=99,
        evidence_quotes=[
            {
                "text": "existing Toolkits quote",
                "mention_chapter_num": "1",
                "mention_word_position": 30,
            }
        ],
    )

    app.persistence.append_roll_evidence_records([
        {
            "chapter_num": "1",
            "index": 2,
            "source_ordinal": 1,
            "text": "The Magic constellation missed a connection.",
            "mention_chapter_num": "1",
            "mention_word_position": 6,
        }
    ])

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    rolls = overrides["chapter_roll_overrides"]["1"]["rolls"]
    occupied = next(roll for roll in rolls if roll.get("source_ordinal") == 99)
    magic = next(roll for roll in rolls if roll.get("source_ordinal") == 1)
    assert occupied["evidence_quotes"] == [
        {
            "text": "existing Toolkits quote",
            "mention_chapter_num": "1",
            "mention_word_position": 30,
        }
    ]
    assert magic["evidence_quotes"] == [
        {
            "text": "The Magic constellation missed a connection.",
            "mention_chapter_num": "1",
            "mention_word_position": 6,
        }
    ]


def test_batch_miss_quote_action_pushes_modal_before_scanning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    events: list[str] = []

    def scan(_cs):
        events.append("scan")
        return []

    def push(_screen):
        events.append("push")

    def after_refresh(callback):
        events.append("scheduled")
        callback()

    monkeypatch.setattr(app, "_batch_miss_quote_matches", scan)
    monkeypatch.setattr(app, "push_screen", push)
    monkeypatch.setattr(app, "call_after_refresh", after_refresh)

    app._action_batch_match_miss_quotes("1")

    assert events == ["push", "scheduled", "scan"]


def test_batch_miss_quote_persistence_is_one_undoable_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")

    app.persistence.append_roll_evidence_records([
        {
            "chapter_num": "1",
            "index": 1,
            "text": "The Magic constellation missed a connection.",
            "mention_chapter_num": "1",
            "mention_word_position": 6,
        },
        {
            "chapter_num": "1",
            "index": 2,
            "text": "The Time constellation passed by.",
            "mention_chapter_num": "1",
            "mention_word_position": 12,
        },
    ])

    journal_entries = list((fixture.manual / ".session_journals").glob("*.jsonl"))
    assert len(journal_entries) == 1
    assert journal_entries[0].read_text().count(
        '"action_type": "append_roll_evidence_records"'
    ) == 1

    undone = app.persistence.undo_last()

    assert undone == ("append_roll_evidence_records", "1")
    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    assert overrides["chapter_roll_overrides"] == {}


def test_first_save_quote_stamps_new_chapter_override_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    start = cs.prose.word_offsets[24][0]
    end = cs.prose.word_offsets[27][1]
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: _selected_prose((start, end)))
    app._post_curation_refresh = lambda _message: None

    app._action_save_quote("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    entry = overrides["chapter_roll_overrides"]["2"]
    assert entry["_fingerprint"] == "sha256:fixturechapter2"


def test_multi_quote_persistence_creates_index_aligned_roll_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence

    persistence.append_roll_evidence_at_indices(
        "2",
        [1, 3],
        text="same quote",
        mention_chapter_num="2",
        mention_word_position=42,
    )

    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert len(rolls) == 3
    assert rolls[0]["evidence_quotes"] == [
        {"text": "same quote", "mention_chapter_num": "2", "mention_word_position": 42}
    ]
    assert rolls[1]["evidence_quotes"] == []
    assert rolls[2]["evidence_quotes"] == [
        {"text": "same quote", "mention_chapter_num": "2", "mention_word_position": 42}
    ]


def test_multi_quote_can_leave_cross_chapter_roll_at_mechanical_visualization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence
    persistence.set_roll_visualization_anchor(
        "1",
        1,
        mention_chapter_num="2",
        mention_word_position=None,
        display_position_policy="mechanical",
    )

    persistence.append_roll_evidence_at_indices(
        "1",
        [1],
        text="later quote",
        mention_chapter_num="2",
        mention_word_position=24,
        display_position_policy=None,
    )

    roll = persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "2"
    assert roll["mention_word_position"] is None
    assert roll["display_position_policy"] == "mechanical"
    assert roll["evidence_quotes"] == [
        {"text": "later quote", "mention_chapter_num": "2", "mention_word_position": 24}
    ]


def test_persistence_shift_roll_evidence_preserves_quote_sets_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence
    first_quote = {
        "text": "first quote",
        "mention_chapter_num": "2",
        "mention_word_position": 20,
    }
    second_quotes = [
        {
            "text": "second quote",
            "mention_chapter_num": "2",
            "mention_word_position": 40,
        },
        {
            "text": "second context",
            "mention_chapter_num": "2",
            "mention_word_position": 41,
        },
    ]
    persistence.append_roll_evidence_at_index("2", 1, **first_quote)
    for quote in second_quotes:
        persistence.append_roll_evidence_at_index("2", 2, **quote)

    result = persistence.shift_roll_evidence_for_source_assignment(
        target_chapter_num="1",
        target_index=1,
        source_chapter_num="2",
        source_index=1,
    )

    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert result == "shifted"
    assert rolls["1"]["rolls"][0]["evidence_quotes"] == [first_quote]
    assert rolls["2"]["rolls"][0]["evidence_quotes"] == second_quotes
    assert rolls["2"]["rolls"][1]["evidence_quotes"] == []
    journal_entries = list((fixture.manual / ".session_journals").glob("*.jsonl"))
    assert journal_entries
    assert "shift_roll_evidence_for_source_assignment" in journal_entries[-1].read_text()


def test_save_quote_multi_can_attach_to_prior_open_slot(
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
    monkeypatch.setattr(app, "_selected_quote", lambda _action_name: "chapter three quote")
    monkeypatch.setattr(app, "_selected_quote_start_word_index", lambda: 24)
    monkeypatch.setattr(app, "_clear_prose_selection", lambda: None)
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    screens: list[RollEvidencePicker] = []
    app.push_screen = lambda screen: screens.append(screen)

    app._action_save_quote_multi("3")

    assert [type(screen) for screen in screens] == [RollEvidencePicker]
    target = next(
        roll for roll in screens[0]._rolls
        if roll.get("target_chapter_num") == "1"
        and roll.get("target_roll_index") == 1
    )
    screens[0]._on_confirm([screens[0]._rolls.index(target) + 1], None)

    roll = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["evidence_quotes"] == [
        {
            "text": "chapter three quote",
            "mention_chapter_num": "3",
            "mention_word_position": 24,
        }
    ]
    assert refreshes == ["quote saved to rolls ch 1 #1"]


def test_save_quote_multi_orders_source_linked_prior_target_before_current_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    predicted_path = fixture.derived / "predicted_rolls.json"
    predicted = json.loads(predicted_path.read_text())
    predicted["predicted"].append({
        "chapter_num": "1",
        "slot_index": 2,
        "cp_offset": 40,
        "epub_offset": 40,
        "roll_number": 3,
    })
    _write_json(predicted_path, predicted)

    roll_facts_path = fixture.derived / "roll_facts.json"
    roll_facts = json.loads(roll_facts_path.read_text())
    prior_target_source = {
        **roll_facts["rolls"][1],
        "chapter_num": "2",
        "roll_sequence_in_chapter": 2,
        "chapter_ordinal": 2,
        "source_chapter_num": "2",
        "source_chapter_ordinal": 1,
        "source_ordinal": 3,
        "source_label": "S3",
        "source_word_position": 10,
        "source_cumulative_word_offset": len(_chapter_words("1")) + 10,
        "mechanical_chapter_num": "1",
        "mechanical_word_position": 40,
        "mechanical_cumulative_word_offset": 40,
        "predicted_chapter_num": "1",
        "predicted_ordinal": 3,
        "predicted_label": "P3",
        "roll_ordinal": 3,
        "roll_label": "R3",
        "evidence_quotes": [],
    }
    roll_facts["rolls"].append(prior_target_source)
    _write_json(roll_facts_path, roll_facts)

    app = fixture.loaded_app("2")
    monkeypatch.setattr(app, "_selected_quote", lambda _action_name: "chapter two quote")
    monkeypatch.setattr(app, "_selected_quote_start_word_index", lambda: 24)
    monkeypatch.setattr(app, "_clear_prose_selection", lambda: None)
    screens: list[RollEvidencePicker] = []
    app.push_screen = lambda screen: screens.append(screen)

    app._action_save_quote_multi("2")

    assert [type(screen) for screen in screens] == [RollEvidencePicker]
    labels = [
        app._roll_target_message_label(roll)
        for roll in screens[0]._rolls
    ]
    assert labels[:3] == ["ch 1 #2", "ch 2 #1", "ch 2 #2"]
    assert app._roll_reference_label(screens[0]._rolls[0]) == "R3/P3/S3"


def test_save_quote_multi_can_attach_to_global_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    monkeypatch.setattr(app, "_selected_quote", lambda _action_name: "later chapter quote")
    monkeypatch.setattr(app, "_selected_quote_start_word_index", lambda: 24)
    monkeypatch.setattr(app, "_clear_prose_selection", lambda: None)
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    screens: list[object] = []
    app.push_screen = lambda screen: screens.append(screen)

    app._action_save_quote_multi("2")
    assert [type(screen) for screen in screens] == [RollEvidencePicker]

    screens[0]._on_global_roll("mention")
    prompt = screens[1]
    prompt._submit("1")

    roll = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert roll["mention_chapter_num"] == "2"
    assert roll["mention_word_position"] == 24
    assert roll["display_position_policy"] == "mention"
    assert roll["evidence_quotes"] == [
        {
            "text": "later chapter quote",
            "mention_chapter_num": "2",
            "mention_word_position": 24,
        }
    ]
    assert refreshes == ["quote saved to R1 (ch 1 #1)"]


def test_delete_annotation_removes_quote_from_open_predicted_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    quote_start = cs.prose.text.find("cursor chapter2 forge")
    assert quote_start >= 0
    quote = cs.prose.text[quote_start:quote_start + len("cursor chapter2 forge")]
    quote_word = 39
    quote_record = {
        "text": quote,
        "mention_chapter_num": "2",
        "mention_word_position": quote_word,
    }
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text=quote,
        mention_chapter_num="2",
        mention_word_position=quote_word,
    )
    prose = _selected_prose(_saved_quote_span(app, cs, quote_record))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )
    flashes: list[str] = []
    app._flash = lambda message: flashes.append(message)

    app._action_remove_annotations_at_current_word("2")

    saved = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert saved["evidence_quotes"] == []
    assert refreshes == [("annotation delete: 0 eligibility, 1 roll evidence", False)]


def test_reassign_quote_moves_saved_metadata_without_reselecting_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.persistence.assign_source_ordinal_at_index("1", 2, 1)
    app.persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
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
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
            "evidence_quotes": [],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]
    prose = _selected_prose(_saved_quote_span(app, cs, {
        "text": "forge motes connection",
        "mention_chapter_num": "2",
        "mention_word_position": 20,
    }))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        assert isinstance(screen, QuoteMoveTargetPicker)
        target = next(
            roll for roll in screen._rolls
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 2
        )
        screen._select(screen._rolls.index(target) + 1)

    app.push_screen = push_screen

    app._action_reassign_roll_quote("2")

    overrides = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert overrides["2"]["rolls"][0]["evidence_quotes"] == []
    assert overrides["1"]["rolls"][1]["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["quote moved to ch 1 #2"]
    assert [type(screen) for screen in screens] == [QuoteMoveTargetPicker]


def test_reassign_quote_requires_source_choice_when_quotes_overlap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    quote_record = {
        "text": "forge motes connection",
        "mention_chapter_num": "2",
        "mention_word_position": 20,
    }
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text=quote_record["text"],
        mention_chapter_num=quote_record["mention_chapter_num"],
        mention_word_position=quote_record["mention_word_position"],
    )
    prose = _selected_prose(_saved_quote_span(app, cs, quote_record))
    monkeypatch.setattr(app, "query_one", lambda *args, **kwargs: prose)
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        if isinstance(screen, QuoteMoveSourcePicker):
            source = next(
                candidate for candidate in screen._sources
                if candidate["target_chapter"] == "2"
                and candidate["target_index"] == 2
            )
            screen._select(screen._sources.index(source) + 1)
            return
        assert isinstance(screen, QuoteMoveTargetPicker)
        target = next(
            roll for roll in screen._rolls
            if roll.get("target_chapter_num") == "2"
            and roll.get("target_roll_index") == 1
        )
        screen._select(screen._rolls.index(target) + 1)

    app.push_screen = push_screen

    app._action_reassign_roll_quote("2")

    overrides = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert overrides["2"]["rolls"][0]["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert overrides["2"]["rolls"][1]["evidence_quotes"] == []
    assert refreshes == ["quote moved to ch 2 #1"]
    assert [type(screen) for screen in screens] == [
        QuoteMoveSourcePicker,
        QuoteMoveTargetPicker,
    ]


def test_reassign_quote_moves_from_mismatched_display_index_to_source_ordinal_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    quote_record = {
        "text": "The Magic constellation missed a connection.",
        "mention_chapter_num": "1",
        "mention_word_position": 6,
    }
    app.persistence.update_roll_at_index(
        "1",
        2,
        outcome="hit",
        constellation="Toolkits",
        evidence_quotes=[quote_record],
    )

    moved = app.persistence.move_roll_evidence_quote_between_indices(
        source_chapter_num="1",
        source_index=5,
        source_source_ordinal=99,
        target_chapter_num="1",
        target_index=2,
        target_source_ordinal=1,
        quote=quote_record,
    )

    assert moved is True
    overrides = app.persistence.chapter_roll_overrides["chapter_roll_overrides"]
    rolls = overrides["1"]["rolls"]
    assert rolls[1]["evidence_quotes"] == []
    magic = next(roll for roll in rolls if roll.get("source_ordinal") == 1)
    assert magic["evidence_quotes"] == [quote_record]


def test_selected_predicted_slot_actions_write_index_aligned_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    target = {
        "display_kind": "predicted_slot",
        "target_chapter_num": "2",
        "target_roll_index": 2,
    }
    app._selected_roll_target_if_visible = lambda: target
    app._post_curation_refresh = lambda _message, *, full=False: None

    app._select_roll_target(target)
    app._action_set_last_outcome("2", "miss")
    app._handle_space_chord("s")

    saved = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())[
        "chapter_roll_overrides"
    ]["2"]["rolls"]
    assert saved[1]["outcome"] is None
    assert saved[1]["skipped"] is True


def test_source_assignment_persistence_moves_duplicate_source_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = fixture.loaded_app("2").persistence

    persistence.assign_source_ordinal_at_index("2", 2, 2)
    persistence.assign_source_ordinal_at_index("1", 1, 2)

    rolls = persistence.chapter_roll_overrides["chapter_roll_overrides"]
    assert rolls["1"]["rolls"][0]["source_ordinal"] == 2
    assert rolls["2"]["rolls"][1]["source_ordinal"] is None


def test_source_assignment_action_links_open_target_to_source_roll(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    refreshes: list[str] = []
    screens: list[object] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        screens.append(screen)
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "predicted_slot"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_ordinal") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert [type(screen) for screen in screens] == [SourceLinkPicker]
    assert saved["source_ordinal"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 2 roll #2 source = S2"]


def test_source_assignment_action_can_use_obtained_perk_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    (fixture.derived / "obtained_perks.json").write_text(json.dumps({
        "perks": [
            {
                "chapter_num": "2",
                "epub_sequence": 2,
                "perk_name": "I Am Iron Man",
                "jump": "Marvel Cinematic Universe",
                "cost": 400,
                "free": False,
                "constellation": "Knowledge",
            }
        ]
    }))
    (fixture.derived / "roll_facts.json").write_text(json.dumps({"rolls": []}))
    app = fixture.loaded_app("2")
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("display_kind") == "predicted_slot"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_kind") == "obtained_perk"
            and roll.get("rolled_perk_name") == "I Am Iron Man"
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["2"]["rolls"][1]
    assert saved["source_ordinal"] is None
    assert saved["outcome"] == "hit"
    assert saved["perks"] == ["I Am Iron Man"]
    assert saved["constellation"] == "Knowledge"
    assert refreshes == ["ch 2 roll #2 source = I Am Iron Man"]


def test_source_assignment_action_can_target_prior_open_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _clear_first_source_assignment(fixture)
    app = fixture.loaded_app("2")
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 1
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_ordinal") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert saved["mention_chapter_num"] == "2"
    assert saved["source_ordinal"] == 2
    assert saved["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 1 roll #1 source = S2"]


def test_source_assignment_action_shifts_chapter_quote_evidence_to_prior_open_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _clear_first_source_assignment(fixture)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    extra_rolls = [
        {
            **dict(app.data.roll_facts["rolls"][1]),
            "roll_number": 3,
            "roll_sequence_in_chapter": 2,
            "source_row_index": 3,
            "source_chapter_ordinal": 2,
            "source_word_position": 40,
            "evidence_quotes": [
                {
                    "text": "second source quote",
                    "mention_chapter_num": "2",
                    "mention_word_position": 40,
                }
            ],
        },
        {
            **dict(app.data.roll_facts["rolls"][1]),
            "roll_number": 4,
            "roll_sequence_in_chapter": 3,
            "source_row_index": 4,
            "source_chapter_ordinal": 3,
            "source_word_position": 60,
            "evidence_quotes": [
                {
                    "text": "third source quote",
                    "mention_chapter_num": "2",
                    "mention_word_position": 60,
                },
                {
                    "text": "third source context",
                    "mention_chapter_num": "2",
                    "mention_word_position": 61,
                },
            ],
        },
    ]
    app.data.roll_facts["rolls"].extend(extra_rolls)
    cs.derived.roll_facts.extend(extra_rolls)
    app.persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
    app.persistence.append_roll_evidence_at_index(
        "2",
        2,
        text="second source quote",
        mention_chapter_num="2",
        mention_word_position=40,
    )
    app.persistence.append_roll_evidence_at_index(
        "2",
        3,
        text="third source quote",
        mention_chapter_num="2",
        mention_word_position=60,
    )
    app.persistence.append_roll_evidence_at_index(
        "2",
        3,
        text="third source context",
        mention_chapter_num="2",
        mention_word_position=61,
    )
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 1
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("chapter_num") == "2"
            and roll.get("source_chapter_ordinal") == 1
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch1_roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    ch2_rolls = overrides["chapter_roll_overrides"]["2"]["rolls"]
    assert ch1_roll["source_ordinal"] == 2
    assert ch1_roll["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert ch2_rolls[0]["evidence_quotes"] == [
        {
            "text": "second source quote",
            "mention_chapter_num": "2",
            "mention_word_position": 40,
        }
    ]
    assert ch2_rolls[1]["evidence_quotes"] == [
        {
            "text": "third source quote",
            "mention_chapter_num": "2",
            "mention_word_position": 60,
        },
        {
            "text": "third source context",
            "mention_chapter_num": "2",
            "mention_word_position": 61,
        },
    ]
    assert ch2_rolls[2]["evidence_quotes"] == []
    assert refreshes == ["ch 1 roll #1 source = S2"]


def test_source_assignment_action_uses_source_mechanical_target_for_open_prior_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    cs = app.state.chapter
    assert cs is not None
    app.data.predicted["predicted"].append({
        "chapter_num": "1",
        "slot_index": 2,
        "cp_offset": 40,
        "epub_offset": 40,
        "roll_number": 3,
    })
    source_roll = dict(app.data.roll_facts["rolls"][1])
    source_roll.update(
        {
            "chapter_num": "2",
            "roll_number": 2,
            "predicted_chapter_num": "1",
            "mechanical_chapter_num": "1",
            "mechanical_word_position": 20,
            "mechanical_cumulative_word_offset": 20,
            "source_chapter_num": "2",
            "source_chapter_ordinal": 1,
            "source_word_position": 20,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_roll]
    app.data.roll_facts["rolls"] = [source_roll]
    app.persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
    app._post_curation_refresh = lambda _message: None

    def push_screen(screen) -> None:
        open_prior = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 2
        )
        source = next(roll for roll in screen._sources if roll.get("source_ordinal") == 2)
        screen._on_confirm(open_prior, source)

    app.push_screen = push_screen
    before = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch1_rolls = overrides["chapter_roll_overrides"]["1"]["rolls"]
    assert ch1_rolls[0]["source_ordinal"] is None
    assert ch1_rolls[0]["evidence_quotes"] == []
    assert ch1_rolls[1]["source_ordinal"] == 2
    assert ch1_rolls[1]["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]

    undone = app.persistence.undo_last()

    assert undone == ("assign_source_roll_with_evidence_at_index", "1")
    assert json.loads((fixture.manual / "chapter_roll_overrides.json").read_text()) == before


def test_source_assignment_action_skips_quote_shift_when_prior_target_has_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _clear_first_source_assignment(fixture)
    app = fixture.loaded_app("2")
    app.persistence.append_roll_evidence_at_index(
        "1",
        1,
        text="existing prior quote",
        mention_chapter_num="2",
        mention_word_position=10,
    )
    app.persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="forge motes connection",
        mention_chapter_num="2",
        mention_word_position=20,
    )
    refreshes: list[str] = []
    flashes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)
    app._flash = lambda message, **_kwargs: flashes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 1
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("chapter_num") == "2"
            and roll.get("source_chapter_ordinal") == 1
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch1_roll = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    ch2_roll = overrides["chapter_roll_overrides"]["2"]["rolls"][0]
    assert ch1_roll["source_ordinal"] == 2
    assert ch1_roll["evidence_quotes"] == [
        {
            "text": "existing prior quote",
            "mention_chapter_num": "2",
            "mention_word_position": 10,
        }
    ]
    assert ch2_roll["evidence_quotes"] == [
        {
            "text": "forge motes connection",
            "mention_chapter_num": "2",
            "mention_word_position": 20,
        }
    ]
    assert refreshes == ["ch 1 roll #1 source = S2"]
    assert flashes == ["assign source: target already has quote evidence"]


def test_source_assignment_action_can_target_open_prior_slot_without_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    _clear_first_source_assignment(fixture)
    app = fixture.loaded_app("2")
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 1
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_ordinal") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    saved = overrides["chapter_roll_overrides"]["1"]["rolls"][0]
    assert saved["source_ordinal"] == 2
    assert refreshes == ["ch 1 roll #1 source = S2"]


def test_source_assignment_action_links_projected_source_to_mechanical_slot(
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
            "source_word_position": 20,
            "source_cumulative_word_offset": 100,
            "visible_chapter_nums": ["1", "2"],
        }
    )
    cs.derived.roll_facts = [source_projected, *cs.derived.roll_facts]
    app.data.roll_facts["rolls"] = [source_projected, *app.data.roll_facts["rolls"]]
    refreshes: list[str] = []
    app._post_curation_refresh = lambda message: refreshes.append(message)

    def push_screen(screen) -> None:
        target = next(
            roll for roll in screen._targets
            if roll.get("target_chapter_num") == "1"
            and roll.get("target_roll_index") == 2
        )
        source = next(
            roll for roll in screen._sources
            if roll.get("source_ordinal") == 2
        )
        screen._on_confirm(target, source)

    app.push_screen = push_screen

    app._action_assign_source_roll("2")

    overrides = json.loads((fixture.manual / "chapter_roll_overrides.json").read_text())
    ch1_roll = overrides["chapter_roll_overrides"]["1"]["rolls"][1]
    assert ch1_roll["source_ordinal"] == 2
    assert refreshes == ["ch 1 roll #2 source = S2"]
