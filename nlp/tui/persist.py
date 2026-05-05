"""Append-only JSONL annotation store + WAL for crash safety.

Classes
-------
JsonlAnnotationStore
    Append-only writer for SpanRecord / SectionRecord pairs.
    Keeps an in-memory index of passage_id -> last byte offset for
    quick lookups. compact() collapses duplicates to a temp file and
    renames it over the original; call manually only, never in a session.

TuiWal
    Tiny write-ahead log.  The TUI writes the current working span list
    (as a raw dict) on every mutating keypress so a crash loses at most
    one keypress of work.  On launch the app checks has_unflushed() and
    offers to restore.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from nlp.schema import SectionRecord, SpanRecord

__all__ = ["JsonlAnnotationStore", "TuiWal"]

# How many WAL entries we keep before silently rotating (prevents unbounded growth)
_WAL_MAX_LINES = 500


class JsonlAnnotationStore:
    """Append-only JSONL store for annotated passages.

    Each call to ``append`` writes *two* JSONL lines (or one if
    ``section`` is ``None``): a ``SpanRecord`` line and an optional
    ``SectionRecord`` line.  Both are fsynced before returning.

    Parameters
    ----------
    path:
        Path to the JSONL file.  Created if it does not exist.
        The directory must exist.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # passage_id -> latest byte-offset of its SpanRecord line
        self._index: dict[str, int] = {}
        self._rebuild_index()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append(
        self,
        record: SpanRecord,
        section: SectionRecord | None = None,
    ) -> None:
        """Append *record* (and optionally *section*) to the JSONL file.

        Validates both records against the pydantic schemas and raises
        ``ValidationError`` on bad input.  Writes are atomic per-line
        and fsynced.
        """
        # Validate inputs (raises pydantic.ValidationError on bad data)
        if not isinstance(record, SpanRecord):
            record = SpanRecord.model_validate(record)
        if section is not None and not isinstance(section, SectionRecord):
            section = SectionRecord.model_validate(section)

        with self.path.open("ab") as fh:
            # Span record
            span_offset = fh.seek(0, 2)  # end of file
            line = record.model_dump_json() + "\n"
            fh.write(line.encode())
            fh.flush()
            os.fsync(fh.fileno())

            # Optional section record (same file; tagged by presence of
            # "chapter_num" without "passage_id" distinguishes them)
            if section is not None:
                section_line = section.model_dump_json() + "\n"
                fh.write(section_line.encode())
                fh.flush()
                os.fsync(fh.fileno())

        self._index[record.passage_id] = span_offset

    def by_passage_id(self, passage_id: str) -> SpanRecord | None:
        """Return the *latest* SpanRecord for *passage_id*, or ``None``."""
        if passage_id not in self._index:
            return None
        offset = self._index[passage_id]
        try:
            with self.path.open("rb") as fh:
                fh.seek(offset)
                raw = fh.readline().decode()
                data = json.loads(raw)
                return SpanRecord.model_validate(data)
        except (OSError, json.JSONDecodeError, ValidationError):
            return None

    def all_passage_ids(self) -> list[str]:
        """Return list of all unique passage_ids in the store (latest wins)."""
        return list(self._index.keys())

    def compact(self) -> int:
        """Collapse duplicate passage_id entries, keeping the latest.

        Writes to a ``<path>.compact`` temp file then renames over the
        original.  Returns the number of *duplicate* lines removed.

        Call manually only — never during an annotation session.
        """
        if not self.path.exists():
            return 0

        # Two-pass: first collect latest SpanRecord per passage_id and
        # all SectionRecords (deduped by chapter_num+section_index).
        span_records: dict[str, SpanRecord] = {}
        section_records: dict[tuple[str, int], SectionRecord] = {}
        total_lines = 0

        with self.path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                total_lines += 1
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "passage_id" in data:
                    try:
                        rec = SpanRecord.model_validate(data)
                        existing = span_records.get(rec.passage_id)
                        if existing is None or rec.annotated_at >= existing.annotated_at:
                            span_records[rec.passage_id] = rec
                    except ValidationError:
                        pass
                elif "header" in data:
                    try:
                        rec = SectionRecord.model_validate(data)
                        key = (rec.chapter_num, rec.section_index)
                        existing = section_records.get(key)
                        if existing is None or rec.annotated_at >= existing.annotated_at:
                            section_records[key] = rec
                    except ValidationError:
                        pass

        kept = len(span_records) + len(section_records)
        removed = total_lines - kept

        tmp = self.path.with_suffix(".compact")
        with tmp.open("w", encoding="utf-8") as fh:
            for rec in span_records.values():
                fh.write(rec.model_dump_json() + "\n")
            for rec in section_records.values():
                fh.write(rec.model_dump_json() + "\n")
        tmp.replace(self.path)

        self._rebuild_index()
        return max(0, removed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rebuild_index(self) -> None:
        """Scan the file and build passage_id -> latest byte-offset index."""
        self._index.clear()
        if not self.path.exists():
            return
        offset = 0
        with self.path.open("rb") as fh:
            while True:
                line_start = fh.tell()
                raw = fh.readline()
                if not raw:
                    break
                try:
                    data = json.loads(raw.decode())
                    if "passage_id" in data:
                        self._index[data["passage_id"]] = line_start
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass


# ---------------------------------------------------------------------------
# WAL
# ---------------------------------------------------------------------------


class TuiWal:
    """Write-ahead log for in-progress annotation work.

    Each call to ``record_state`` appends a JSON snapshot of the current
    working state to the WAL file with a UTC timestamp.  On launch the
    app checks ``has_unflushed()``; if True, ``restore()`` returns the
    last snapshot dict so the app can offer to continue from where it
    crashed.  ``clear()`` removes all entries (called after a successful
    save).

    The WAL is capped at ``_WAL_MAX_LINES`` entries to prevent unbounded
    growth; oldest entries are silently dropped on overflow.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record_state(self, snapshot: dict[str, Any]) -> None:
        """Append *snapshot* to the WAL, fsynced."""
        entry = {"ts": time.time(), "snapshot": snapshot}
        line = json.dumps(entry, default=str) + "\n"
        # Rotate if too large
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as fh:
                    lines = fh.readlines()
                if len(lines) >= _WAL_MAX_LINES:
                    keep = lines[len(lines) // 2 :]  # keep newer half
                    with self.path.open("w", encoding="utf-8") as fh:
                        fh.writelines(keep)
        except OSError:
            pass

        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    def has_unflushed(self) -> bool:
        """Return True if the WAL contains any entries."""
        if not self.path.exists():
            return False
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        return True
        except OSError:
            pass
        return False

    def restore(self) -> dict[str, Any] | None:
        """Return the last snapshot in the WAL, or ``None`` if empty."""
        if not self.path.exists():
            return None
        last: dict[str, Any] | None = None
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        last = entry.get("snapshot")
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
        return last

    def clear(self) -> None:
        """Truncate the WAL to zero bytes (preserves the file for next session)."""
        try:
            with self.path.open("w", encoding="utf-8") as fh:
                fh.truncate(0)
        except OSError:
            pass
