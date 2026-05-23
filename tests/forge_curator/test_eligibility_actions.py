from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.forge_curator.persistence import CurationPersistence
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def test_toggle_section_eligibility_writes_section_classification_and_full_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    app._action_toggle_section_eligibility("1")

    entry = json.loads((fixture.manual / "section_classifications.json").read_text())[
        "classifications"
    ]["1@0"]
    assert entry["counts_for_cp"] is False
    assert "curator toggle" in entry["reason"]
    assert refreshes == [("ch 1 sec 0 CP eligibility: DISABLED", True)]


def test_save_span_eligibility_persists_under_section_classification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    app._save_span_eligibility(
        "1",
        2,
        6,
        counts_for_cp=False,
        reason_code="joe_not_on_screen",
        note="Fixture cutaway.",
        excerpt="motes connection constellation evidence",
    )

    entry = json.loads((fixture.manual / "section_classifications.json").read_text())[
        "classifications"
    ]["1@0"]
    assert entry["span_overrides"] == [
        {
            "word_offset_start": 2,
            "word_offset_end": 6,
            "counts_for_cp": False,
            "reason_code": "joe_not_on_screen",
            "note": "Fixture cutaway.",
            "excerpt": "motes connection constellation evidence",
        }
    ]
    assert refreshes == [
        ("CP ineligible span saved (4 words, joe_not_on_screen)", True)
    ]


def test_curation_refresh_message_warns_about_later_alignment_reviews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("1")
    app.data._chapter_facts_doc = {
        "chapters": [
            {"chapter_num": "1", "sort_key": [1, 0], "model_validation": {"issues": []}},
            {
                "chapter_num": "2",
                "sort_key": [2, 0],
                "model_validation": {
                    "issues": [
                        {
                            "code": "chapter_alignment_stale",
                            "severity": "error",
                            "message": "Review alignment.",
                        }
                    ]
                },
            },
        ]
    }

    message = app._curation_refresh_message("CP ineligible span saved", "1")

    assert message == (
        "CP ineligible span saved; alignment warning: 1 later chapter needs review"
    )


def test_chapter_delete_candidates_include_eligibility_curation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    section_classifications_path = fixture.manual / "section_classifications.json"
    section_classifications_path.write_text(json.dumps({
        "_source": "test",
        "classifications": {
            "2@0": {
                "chapter_num": "2",
                "section_index": 0,
                "header": None,
                "counts_for_cp": False,
                "reason": "curator toggle: ineligible",
                "span_overrides": [
                    {
                        "word_offset_start": 2,
                        "word_offset_end": 6,
                        "counts_for_cp": False,
                        "reason_code": "joe_not_on_screen",
                        "note": "Fixture cutaway.",
                    },
                    {
                        "word_offset_start": 8,
                        "word_offset_end": 9,
                        "counts_for_cp": False,
                        "reason_code": "section_header",
                        "note": "generated from chapter section header",
                    },
                ],
            }
        },
    }))
    app = fixture.loaded_app("2")
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=fixture.manual / "chapter_roll_overrides.json",
        section_classifications_path=section_classifications_path,
        journal_dir_path=fixture.manual / ".session_journals",
    )

    candidates = app._chapter_curation_delete_candidates("2")
    labels = [candidate.label for candidate in candidates]
    items = [candidate.item for candidate in candidates]

    assert "ch 2 sec 0: section eligibility = ineligible" in labels
    assert any(
        label.startswith("ch 2 sec 0: eligibility span 2-6 ineligible")
        for label in labels
    )
    assert not any("section_header" in label for label in labels)
    assert {"kind": "section_eligibility", "chapter_num": "2", "section_key": "2@0"} in items
    assert {
        "kind": "eligibility_span",
        "chapter_num": "2",
        "section_key": "2@0",
        "span_index": 0,
    } in items


def test_chapter_delete_action_removes_selected_eligibility_curation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    section_classifications_path = fixture.manual / "section_classifications.json"
    section_classifications_path.write_text(json.dumps({
        "_source": "test",
        "classifications": {
            "2@0": {
                "chapter_num": "2",
                "section_index": 0,
                "header": None,
                "counts_for_cp": False,
                "reason": "curator toggle: ineligible",
                "span_overrides": [
                    {
                        "word_offset_start": 2,
                        "word_offset_end": 6,
                        "counts_for_cp": False,
                        "reason_code": "joe_not_on_screen",
                    }
                ],
            }
        },
    }))
    app = fixture.loaded_app("2")
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=fixture.manual / "chapter_roll_overrides.json",
        section_classifications_path=section_classifications_path,
        journal_dir_path=fixture.manual / ".session_journals",
    )
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    def pick_all(screen) -> None:
        screen._on_confirm([candidate.item for candidate in screen._candidates])

    app.push_screen = pick_all

    app._action_delete_chapter_curation_data("2")

    entry = json.loads(section_classifications_path.read_text())[
        "classifications"
    ]["2@0"]
    assert entry["counts_for_cp"] is True
    assert "reason" not in entry
    assert "span_overrides" not in entry
    assert refreshes == [("deleted 2 curation records", True)]


def test_remove_annotations_action_deletes_eligibility_spans_at_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    section_classifications_path = fixture.manual / "section_classifications.json"
    section_classifications_path.write_text(json.dumps({
        "_source": "test",
        "classifications": {
            "2@0": {
                "chapter_num": "2",
                "section_index": 0,
                "header": None,
                "counts_for_cp": True,
                "reason": "test",
                "span_overrides": [
                    {
                        "word_offset_start": 0,
                        "word_offset_end": 4,
                        "counts_for_cp": False,
                        "reason_code": "author_note",
                    },
                    {
                        "word_offset_start": 10,
                        "word_offset_end": 12,
                        "counts_for_cp": False,
                        "reason_code": "joe_not_on_screen",
                    },
                ],
            }
        },
    }))
    app = fixture.loaded_app("2")
    app.persistence = CurationPersistence(
        chapter_roll_overrides_path=fixture.manual / "chapter_roll_overrides.json",
        section_classifications_path=section_classifications_path,
        journal_dir_path=fixture.manual / ".session_journals",
    )
    app._roll_evidence_targets_at_selection_or_cursor = lambda: []
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    app._action_remove_annotations_at_current_word("2")

    spans = json.loads(section_classifications_path.read_text())[
        "classifications"
    ]["2@0"]["span_overrides"]
    assert [span["reason_code"] for span in spans] == ["joe_not_on_screen"]
    assert refreshes == [("annotation delete: 1 eligibility, 0 roll evidence", True)]
