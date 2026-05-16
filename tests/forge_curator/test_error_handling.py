from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

import scripts.forge_curator.persistence as persistence_module
from scripts.forge_curator.persistence import CurationPersistence
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def test_malformed_manual_roll_overrides_load_as_empty_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    overrides_path = fixture.manual / "chapter_roll_overrides.json"
    overrides_path.write_text("{not valid json")

    persistence = CurationPersistence(
        chapter_roll_overrides_path=overrides_path,
        section_classifications_path=fixture.manual / "section_classifications.json",
        journal_dir_path=fixture.manual / ".session_journals",
    )

    assert persistence.chapter_roll_overrides == {
        "_purpose": "Per-chapter paid roll structure + curated metadata.",
        "chapter_roll_overrides": {},
    }


def test_roll_override_write_failure_rolls_back_memory_and_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    overrides_path = fixture.manual / "chapter_roll_overrides.json"
    before_text = overrides_path.read_text()
    persistence = CurationPersistence(
        chapter_roll_overrides_path=overrides_path,
        section_classifications_path=fixture.manual / "section_classifications.json",
        journal_dir_path=fixture.manual / ".session_journals",
    )
    before_doc = deepcopy(persistence.chapter_roll_overrides)
    real_write = persistence_module._atomic_write_json

    def fail_write(path: Path, doc: object) -> None:
        if path == overrides_path:
            raise OSError("fixture write failure")
        real_write(path, doc)

    monkeypatch.setattr(persistence_module, "_atomic_write_json", fail_write)

    with pytest.raises(OSError, match="fixture write failure"):
        persistence.update_roll_at_index("1", 2, outcome="miss")

    assert persistence.chapter_roll_overrides == before_doc
    assert overrides_path.read_text() == before_text
    assert not (fixture.manual / ".session_journals").exists()


def test_section_classification_write_failure_rolls_back_memory_and_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    sections_path = fixture.manual / "section_classifications.json"
    before_text = sections_path.read_text()
    persistence = CurationPersistence(
        chapter_roll_overrides_path=fixture.manual / "chapter_roll_overrides.json",
        section_classifications_path=sections_path,
        journal_dir_path=fixture.manual / ".session_journals",
    )
    before_doc = deepcopy(persistence.section_classifications)
    real_write = persistence_module._atomic_write_json

    def fail_write(path: Path, doc: object) -> None:
        if path == sections_path:
            raise OSError("fixture write failure")
        real_write(path, doc)

    monkeypatch.setattr(persistence_module, "_atomic_write_json", fail_write)

    with pytest.raises(OSError, match="fixture write failure"):
        persistence.mark_span_eligibility(
            "1",
            0,
            2,
            4,
            counts_for_cp=False,
            reason_code="fixture_reason",
            header=None,
            current_counts_for_cp=True,
        )

    assert persistence.section_classifications == before_doc
    assert sections_path.read_text() == before_text
    assert not (fixture.manual / ".session_journals").exists()


def test_full_rebuild_action_requests_full_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    app._handle_space_chord("R")

    assert refreshes == [("full curation rebuild complete", True)]


def test_undo_reruns_derivation_and_refreshes_from_fixture_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    persistence = CurationPersistence(
        chapter_roll_overrides_path=fixture.manual / "chapter_roll_overrides.json",
        section_classifications_path=fixture.manual / "section_classifications.json",
        journal_dir_path=fixture.manual / ".session_journals",
    )
    persistence.append_roll_evidence_at_index(
        "2",
        1,
        text="quote",
        mention_chapter_num="2",
        mention_word_position=1,
    )
    app = fixture.loaded_app("2")
    app.persistence = persistence
    refreshes: list[tuple[str, bool]] = []
    app._post_curation_refresh = (
        lambda message, *, full=False: refreshes.append((message, full))
    )

    app.action_undo_last()

    assert refreshes == [("undid: append_roll_evidence_at_index (ch 2)", False)]


def test_post_curation_refresh_reloads_fixture_derived_documents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None
    app.data.roll_facts
    app.data.chapter_facts
    old_roll_facts = app.data._roll_facts_doc
    old_chapter_facts = app.data._chapter_facts_doc
    app.data._derived_cache["sentinel"] = object()
    calls: list[str] = []
    app._run_post_curation_derivation = lambda: calls.append("ran")

    app._post_curation_refresh("changed roll")

    assert calls == ["ran"]
    assert app.data._roll_facts_doc is not old_roll_facts
    assert app.data._chapter_facts_doc is not old_chapter_facts
    assert "sentinel" not in app.data._derived_cache
    assert app._last_curation_message == "changed roll"
    assert app._last_curation_error is None


def test_failed_post_curation_derivation_reports_error_without_reload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    app = fixture.loaded_app("2")
    app.refresh_all_panels = lambda: None
    app._scroll_cursor_into_view = lambda: None
    app.data.roll_facts
    app.data.chapter_facts
    old_roll_facts = app.data._roll_facts_doc
    old_chapter_facts = app.data._chapter_facts_doc

    def fail() -> None:
        raise RuntimeError("derive failed")

    app._run_post_curation_derivation = fail

    app._post_curation_refresh("changed roll")

    assert app._last_curation_error == "derive failed"
    assert app._last_curation_message is None
    assert app.data._roll_facts_doc is old_roll_facts
    assert app.data._chapter_facts_doc is old_chapter_facts
