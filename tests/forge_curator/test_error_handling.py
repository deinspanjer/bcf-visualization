from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

import scripts.forge_curator.persistence as persistence_module
from scripts.forge_curator.persistence import CurationPersistence
from tests.helpers.forge_curator_fixture import forge_curator_fixture


def test_malformed_manual_roll_overrides_raises_on_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    overrides_path = fixture.manual / "chapter_roll_overrides.json"
    overrides_path.write_text("{not valid json")

    # A malformed *existing* file must raise, never silently collapse to
    # an empty document — the old behaviour here let CurationPersistence
    # swallow the parse error and treat the file as empty, which the
    # next auto-save would then write back over the real 118-chapter
    # hand-curated corpus (T-03-02, the data-destruction bug this
    # phase fixes). Only a genuinely absent file is allowed to default.
    with pytest.raises((ValueError, json.JSONDecodeError)):
        CurationPersistence(
            chapter_roll_overrides_path=overrides_path,
            section_classifications_path=fixture.manual / "section_classifications.json",
            journal_dir_path=fixture.manual / ".session_journals",
        )


def test_roll_override_write_failure_rolls_back_memory_and_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap-closure (CINF-01): _write_chapter_roll_overrides is now routed
    through chapter_roll_overrides_io.write_chapter_roll_overrides_doc
    (schema-validated, atomic) rather than the module-local
    _atomic_write_json, so a write failure must be simulated at that
    call site to still exercise this rollback path."""
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    overrides_path = fixture.manual / "chapter_roll_overrides.json"
    before_text = overrides_path.read_text()
    persistence = CurationPersistence(
        chapter_roll_overrides_path=overrides_path,
        section_classifications_path=fixture.manual / "section_classifications.json",
        journal_dir_path=fixture.manual / ".session_journals",
    )
    before_doc = deepcopy(persistence.chapter_roll_overrides)

    def fail_write(doc: object, path: Path | None = None) -> None:
        raise OSError("fixture write failure")

    monkeypatch.setattr(
        persistence_module, "write_chapter_roll_overrides_doc", fail_write
    )

    with pytest.raises(OSError, match="fixture write failure"):
        persistence.update_roll_at_index("1", 2, outcome="miss")

    assert persistence.chapter_roll_overrides == before_doc
    assert overrides_path.read_text() == before_text
    assert not (fixture.manual / ".session_journals").exists()


def test_roll_override_schema_violation_raises_value_error_and_rolls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gap-closure (CINF-01): the TUI auto-save now validates on every
    write. If a chapter entry's curated_by is ever corrupted to something
    schema-invalid, the write must raise a legible ValueError (not crash
    with something opaque, and never silently write the bad state to
    disk) and roll the in-memory document back to the pre-action state --
    same contract as the pre-existing OSError rollback test above, this
    time for the new validation gate rather than an I/O failure."""
    fixture = forge_curator_fixture(tmp_path, monkeypatch)
    overrides_path = fixture.manual / "chapter_roll_overrides.json"
    persistence = CurationPersistence(
        chapter_roll_overrides_path=overrides_path,
        section_classifications_path=fixture.manual / "section_classifications.json",
        journal_dir_path=fixture.manual / ".session_journals",
    )
    # Simulate an already-corrupted in-memory document (e.g. from a bug
    # elsewhere) rather than going through the normal action API, which
    # always stamps a valid curated_by on new entries.
    persistence.chapter_roll_overrides["chapter_roll_overrides"]["1"] = {
        "curated_by": "robot",
        "rolls": [],
    }
    before_text = overrides_path.read_text()
    before_doc = deepcopy(persistence.chapter_roll_overrides)

    with pytest.raises(ValueError, match="curated_by"):
        persistence.update_roll_at_index("1", 1, outcome="miss")

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
