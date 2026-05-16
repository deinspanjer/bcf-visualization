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
