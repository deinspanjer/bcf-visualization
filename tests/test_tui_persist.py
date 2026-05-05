"""Tests for nlp.tui.persist — pure I/O, no Textual screen subsystem.

Covers:
- JsonlAnnotationStore.append (validates schema, raises on bad input)
- JsonlAnnotationStore.by_passage_id returns latest when duplicates exist
- JsonlAnnotationStore.compact collapses duplicates keeping latest
- TuiWal record/restore round-trips a snapshot dict
- TuiWal.clear empties the WAL but preserves the file
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from nlp.schema import (
    SCHEMA_VERSION,
    SectionRecord,
    SpanAnnotation,
    SpanRecord,
)
from nlp.tui.persist import JsonlAnnotationStore, TuiWal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _span_record(passage_id: str, annotated_at: str, label: str = "ACQUISITION") -> SpanRecord:
    """Build a minimal valid SpanRecord."""
    return SpanRecord(
        passage_id=passage_id,
        chapter_num="16.1",
        section_index=0,
        epub_char_start=0,
        epub_char_end=100,
        text="Some passage text here.",
        spans=[
            SpanAnnotation(layer="A", label=label, start=0, end=4),
        ],
        source="manual",
        model_proposal_score=None,
        annotator="test_user",
        annotated_at=annotated_at,
        schema_version=SCHEMA_VERSION,
    )


def _section_record(chapter_num: str = "16.1", section_index: int = 0) -> SectionRecord:
    return SectionRecord(
        chapter_num=chapter_num,
        section_index=section_index,
        header="16.1 Test Section",
        first_chars="Some first chars.",
        word_count=100,
        labels={
            "pov_joe": True,
            "joe_on_screen": True,
            "joe_mentioned_offscreen": False,
            "time_real": True,
            "time_flashback": False,
            "time_framing": False,
            "time_dilated": False,
            "counts_for_cp": True,
        },
        annotator="test_user",
        annotated_at="2026-05-05T00:00:00Z",
        schema_version=SCHEMA_VERSION,
    )


# ---------------------------------------------------------------------------
# JsonlAnnotationStore — basic append + by_passage_id
# ---------------------------------------------------------------------------


def test_append_and_retrieve(tmp_path: Path) -> None:
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")
    rec = _span_record("ch16.1_p01", "2026-05-04T10:00:00Z")
    store.append(rec)
    retrieved = store.by_passage_id("ch16.1_p01")
    assert retrieved is not None
    assert retrieved.passage_id == "ch16.1_p01"
    assert retrieved.annotated_at == "2026-05-04T10:00:00Z"


def test_by_passage_id_returns_latest(tmp_path: Path) -> None:
    """Appending two records with the same passage_id: by_passage_id returns the later one."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")

    rec_old = _span_record("ch16.1_p01", "2026-05-04T09:00:00Z")
    rec_new = _span_record("ch16.1_p01", "2026-05-04T15:00:00Z", label="MISS")

    store.append(rec_old)
    store.append(rec_new)

    result = store.by_passage_id("ch16.1_p01")
    assert result is not None
    # Must be the newer one (later annotated_at)
    assert result.annotated_at == "2026-05-04T15:00:00Z"
    assert result.spans[0].label == "MISS"


def test_all_passage_ids(tmp_path: Path) -> None:
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")
    store.append(_span_record("ch1_p01", "2026-05-04T10:00:00Z"))
    store.append(_span_record("ch1_p02", "2026-05-04T10:01:00Z"))
    store.append(_span_record("ch1_p01", "2026-05-04T10:02:00Z"))  # dupe

    ids = store.all_passage_ids()
    # Should contain both IDs (deduplicated)
    assert set(ids) == {"ch1_p01", "ch1_p02"}


def test_append_with_section(tmp_path: Path) -> None:
    """Append a SpanRecord + SectionRecord pair; both are written."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")
    span_rec = _span_record("ch16.1_p01", "2026-05-04T10:00:00Z")
    sec_rec = _section_record()
    store.append(span_rec, sec_rec)

    lines = (tmp_path / "test.jsonl").read_text().splitlines()
    assert len(lines) == 2  # span line + section line
    span_data = json.loads(lines[0])
    assert span_data["passage_id"] == "ch16.1_p01"
    sec_data = json.loads(lines[1])
    assert "header" in sec_data


def test_append_validates_schema_bad_span(tmp_path: Path) -> None:
    """append raises ValidationError (or TypeError) on invalid input."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")

    # Pass a dict with missing required fields
    bad_dict = {"passage_id": "bad", "text": "hi"}
    with pytest.raises((ValidationError, Exception)):
        store.append(bad_dict)  # type: ignore[arg-type]


def test_append_rejects_bad_source(tmp_path: Path) -> None:
    """source must be one of the SourceKind literals."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")
    with pytest.raises(ValidationError):
        SpanRecord(
            passage_id="x",
            chapter_num="1",
            section_index=0,
            epub_char_start=0,
            epub_char_end=10,
            text="hello",
            spans=[],
            source="invalid_source",  # type: ignore[arg-type]
            annotator="me",
            annotated_at="2026-05-05T00:00:00Z",
            schema_version=1,
        )


# ---------------------------------------------------------------------------
# JsonlAnnotationStore — compact
# ---------------------------------------------------------------------------


def test_compact_collapses_dupes(tmp_path: Path) -> None:
    """compact() keeps only the latest record per passage_id."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")

    # Three passages; ch1_p01 written twice
    store.append(_span_record("ch1_p01", "2026-05-04T09:00:00Z"))
    store.append(_span_record("ch1_p02", "2026-05-04T10:00:00Z"))
    store.append(_span_record("ch1_p01", "2026-05-04T11:00:00Z", label="MISS"))

    removed = store.compact()
    assert removed == 1  # one duplicate collapsed

    lines = (tmp_path / "test.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2

    ids_in_file = {json.loads(l).get("passage_id") for l in lines}
    assert ids_in_file == {"ch1_p01", "ch1_p02"}

    # After compact, by_passage_id returns the latest
    result = store.by_passage_id("ch1_p01")
    assert result is not None
    assert result.annotated_at == "2026-05-04T11:00:00Z"
    assert result.spans[0].label == "MISS"


def test_compact_empty_file(tmp_path: Path) -> None:
    """compact on an empty / nonexistent file returns 0."""
    store = JsonlAnnotationStore(tmp_path / "empty.jsonl")
    assert store.compact() == 0


def test_compact_no_dupes(tmp_path: Path) -> None:
    """compact with no duplicates removes 0 lines."""
    store = JsonlAnnotationStore(tmp_path / "test.jsonl")
    store.append(_span_record("ch1_p01", "2026-05-04T10:00:00Z"))
    store.append(_span_record("ch1_p02", "2026-05-04T10:01:00Z"))
    removed = store.compact()
    assert removed == 0


# ---------------------------------------------------------------------------
# TuiWal
# ---------------------------------------------------------------------------


def test_wal_record_and_restore(tmp_path: Path) -> None:
    """record_state / restore round-trip a snapshot dict."""
    wal = TuiWal(tmp_path / ".wal.jsonl")
    snapshot = {
        "passage_id": "ch16.1_p01",
        "spans": [{"layer": "A", "label": "ACQUISITION", "start": 0, "end": 10}],
        "section_flags": {"pov_joe": True},
    }
    wal.record_state(snapshot)
    assert wal.has_unflushed()

    restored = wal.restore()
    assert restored is not None
    assert restored["passage_id"] == "ch16.1_p01"
    assert restored["spans"][0]["label"] == "ACQUISITION"
    assert restored["section_flags"]["pov_joe"] is True


def test_wal_restore_returns_last(tmp_path: Path) -> None:
    """restore returns the *last* snapshot when multiple are written."""
    wal = TuiWal(tmp_path / ".wal.jsonl")
    wal.record_state({"passage_id": "first", "spans": []})
    wal.record_state({"passage_id": "second", "spans": []})
    wal.record_state({"passage_id": "third", "spans": []})

    restored = wal.restore()
    assert restored is not None
    assert restored["passage_id"] == "third"


def test_wal_clear_empties_but_preserves_file(tmp_path: Path) -> None:
    """clear() empties the WAL content but leaves the file on disk."""
    wal_path = tmp_path / ".wal.jsonl"
    wal = TuiWal(wal_path)
    wal.record_state({"passage_id": "x", "spans": []})
    assert wal.has_unflushed()

    wal.clear()

    # File still exists
    assert wal_path.exists()
    # But has_unflushed is now False
    assert not wal.has_unflushed()
    # And restore returns None
    assert wal.restore() is None


def test_wal_empty_initially(tmp_path: Path) -> None:
    """has_unflushed returns False for a fresh WAL."""
    wal = TuiWal(tmp_path / ".wal.jsonl")
    assert not wal.has_unflushed()
    assert wal.restore() is None


def test_wal_fsync_survives_reopen(tmp_path: Path) -> None:
    """Data persists after the TuiWal object is garbage-collected and re-opened."""
    wal_path = tmp_path / ".wal.jsonl"
    snapshot = {"passage_id": "persist_test", "spans": []}

    wal1 = TuiWal(wal_path)
    wal1.record_state(snapshot)
    del wal1

    wal2 = TuiWal(wal_path)
    assert wal2.has_unflushed()
    restored = wal2.restore()
    assert restored is not None
    assert restored["passage_id"] == "persist_test"
