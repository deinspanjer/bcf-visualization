"""Curation persistence for the Forge Curator TUI (Phase 2).

Routes each curation action to its canonical override file and journals
every change for forensic rollback. Auto-save semantics: each
:meth:`apply_action` call writes the override file AND appends a journal
entry, so the working set on disk is always current.

Override files (each is a single JSON document):

- ``data/manual/chapter_roll_overrides.json`` — per-roll metadata
  (outcome, constellation, perks, narrative_evidence, word_position).
- ``data/manual/author_notes.json`` — AN spans (per chapter + section).
- ``data/manual/chapter_eligibility.json`` — chapter-level CP-eligibility
  toggle (when the user disables a chapter's contribution to CP).
- ``data/manual/header_corrections.json`` — markup spans excluded from
  word counts.

Journal: ``data/manual/.session_journals/<ISO-timestamp>.jsonl`` — one
JSON line per action, with timestamp, action_type, target_file,
chapter_num, before_state, after_state. Gitignored.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.forge_curator.data_loader import (
    AUTHOR_NOTES,
    CHAPTER_ROLL_OVERRIDES,
    HEADER_CORRECTIONS,
    MANUAL,
)

CHAPTER_ELIGIBILITY = MANUAL / "chapter_eligibility.json"
JOURNAL_DIR = MANUAL / ".session_journals"


def _utcnow_iso() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H-%M-%S")


def _atomic_write_json(path: Path, doc: Any) -> None:
    """Write ``doc`` as pretty-printed JSON to ``path`` via tmp-then-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


class CurationPersistence:
    """Apply curation actions, auto-saving to override files + journal."""

    def __init__(
        self,
        *,
        chapter_roll_overrides_path: Path | None = None,
        author_notes_path: Path | None = None,
        chapter_eligibility_path: Path | None = None,
        header_corrections_path: Path | None = None,
        journal_dir_path: Path | None = None,
    ) -> None:
        self.chapter_roll_overrides_path = chapter_roll_overrides_path or CHAPTER_ROLL_OVERRIDES
        self.author_notes_path = author_notes_path or AUTHOR_NOTES
        self.chapter_eligibility_path = chapter_eligibility_path or CHAPTER_ELIGIBILITY
        self.header_corrections_path = header_corrections_path or HEADER_CORRECTIONS
        self.journal_dir_path = journal_dir_path or JOURNAL_DIR
        # Load existing override docs (or empty stubs).
        self.chapter_roll_overrides = self._load_or_default(
            self.chapter_roll_overrides_path,
            {
                "_purpose": "Per-chapter paid roll structure + curated metadata.",
                "chapter_roll_overrides": {},
            },
        )
        self.author_notes = self._load_or_default(
            self.author_notes_path,
            {"author_notes": []},
        )
        self.chapter_eligibility = self._load_or_default(
            self.chapter_eligibility_path,
            {
                "_purpose": "Per-chapter CP eligibility override (default: on).",
                "disabled_chapters": [],
            },
        )
        self.header_corrections = self._load_or_default(
            self.header_corrections_path,
            {"corrections": []},
        )
        # Initialise the session journal lazily on first action.
        self._journal_path: Path | None = None

    @staticmethod
    def _load_or_default(path: Path, default: dict) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return deepcopy(default)
        return deepcopy(default)

    def _journal(self) -> Path:
        if self._journal_path is None:
            self.journal_dir_path.mkdir(parents=True, exist_ok=True)
            self._journal_path = self.journal_dir_path / f"{_utcnow_iso()}.jsonl"
        return self._journal_path

    def _append_journal(
        self,
        action_type: str,
        target_file: Path,
        chapter_num: str | None,
        before: Any,
        after: Any,
        extra: dict | None = None,
    ) -> None:
        entry = {
            "timestamp": (
                dt.datetime.now(dt.UTC)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            ),
            "action_type": action_type,
            "chapter_num": chapter_num,
            "before": before,
            "after": after,
        }
        if extra:
            entry["extra"] = extra
        try:
            entry["target_file"] = str(target_file.relative_to(MANUAL.parent))
        except ValueError:
            entry["target_file"] = str(target_file)
        with self._journal().open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Helpers — locate / create per-chapter or per-roll structures.
    # ------------------------------------------------------------------

    def _ensure_chapter_entry(self, chapter_num: str) -> dict:
        """Get or create the chapter_roll_overrides entry for ``chapter_num``."""
        cro = self.chapter_roll_overrides.setdefault("chapter_roll_overrides", {})
        if chapter_num not in cro:
            cro[chapter_num] = {"rolls": [], "narrative_evidence": ""}
        elif "rolls" not in cro[chapter_num]:
            cro[chapter_num]["rolls"] = []
        return cro[chapter_num]

    def _last_roll(self, chapter_num: str) -> dict | None:
        entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(chapter_num)
        )
        if not entry:
            return None
        rolls = entry.get("rolls") or []
        return rolls[-1] if rolls else None

    def get_or_create_roll_at_index(
        self, chapter_num: str, index: int,
    ) -> dict:
        """Return the override-roll at 1-based ``index`` for this
        chapter, creating empty entries up to that index if needed.

        Used when curation actions target a specific predicted roll by
        chapter-local sequence number — keeps the override array
        index-aligned with the predicted roll list.
        """
        entry = self._ensure_chapter_entry(str(chapter_num))
        rolls = entry["rolls"]
        while len(rolls) < index:
            rolls.append({
                "perks": [],
                "outcome": None,
                "constellation": None,
                "word_position": None,
                "mention_chapter_num": None,
                "mention_word_position": None,
                "display_position_policy": None,
                "narrative_evidence": None,
            })
        return rolls[index - 1]

    def update_roll_at_index(
        self,
        chapter_num: str,
        index: int,
        *,
        outcome: str | None = None,
        constellation: str | None = None,
        perks: list[str] | None = None,
        narrative_evidence: str | None = None,
        mention_chapter_num: str | None = None,
        mention_word_position: int | None = None,
        display_position_policy: str | None = None,
    ) -> dict:
        """Update an override roll at 1-based chapter-local ``index``.

        Auto-saves and journals. Fields left as ``None`` are not changed.
        """
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        if outcome is not None:
            roll["outcome"] = outcome
        if constellation is not None:
            roll["constellation"] = constellation
        if perks is not None:
            roll["perks"] = list(perks)
        if narrative_evidence is not None:
            roll["narrative_evidence"] = narrative_evidence
        if mention_chapter_num is not None:
            roll["mention_chapter_num"] = str(mention_chapter_num)
        if mention_word_position is not None:
            roll["mention_word_position"] = int(mention_word_position)
        if display_position_policy is not None:
            roll["display_position_policy"] = display_position_policy
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "update_roll_at_index", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"index": index, "outcome": outcome,
                   "constellation": constellation, "perks": perks,
                   "narrative_evidence": narrative_evidence,
                   "mention_chapter_num": mention_chapter_num,
                   "mention_word_position": mention_word_position,
                   "display_position_policy": display_position_policy},
        )
        return roll

    def update_rolls_at_indices(
        self,
        chapter_num: str,
        indices: list[int],
        *,
        narrative_evidence: str,
        mention_chapter_num: str | None = None,
        mention_word_position: int | None = None,
        display_position_policy: str | None = None,
    ) -> list[dict]:
        """Save the same curated quote to multiple chapter-local rolls.

        Missing rows are created as index-aligned stubs; untouched rows
        remain unchanged.
        """
        clean_indices = sorted({int(i) for i in indices if int(i) > 0})
        if not clean_indices:
            return []
        before = deepcopy(self.chapter_roll_overrides)
        updated: list[dict] = []
        for index in clean_indices:
            roll = self.get_or_create_roll_at_index(chapter_num, index)
            roll["narrative_evidence"] = narrative_evidence
            if mention_chapter_num is not None:
                roll["mention_chapter_num"] = str(mention_chapter_num)
            if mention_word_position is not None:
                roll["mention_word_position"] = int(mention_word_position)
            if display_position_policy is not None:
                roll["display_position_policy"] = display_position_policy
            updated.append(roll)
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "update_rolls_at_indices",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "indices": clean_indices,
                "narrative_evidence": narrative_evidence,
                "mention_chapter_num": mention_chapter_num,
                "mention_word_position": mention_word_position,
                "display_position_policy": display_position_policy,
            },
        )
        return updated

    def clear_roll_evidence_at_index(self, chapter_num: str, index: int) -> bool:
        """Clear curated narrative evidence from an existing override row."""
        entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(chapter_num))
        )
        rolls = (entry or {}).get("rolls") or []
        if not (1 <= int(index) <= len(rolls)):
            return False
        roll = rolls[int(index) - 1]
        if not roll.get("narrative_evidence"):
            return False
        before = deepcopy(self.chapter_roll_overrides)
        roll["narrative_evidence"] = None
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "clear_roll_evidence_at_index",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"index": int(index)},
        )
        return True

    def mark_roll_deferred_to_chapter(
        self,
        chapter_num: str,
        index: int,
        mention_chapter_num: str,
        *,
        mention_word_position: int | None = None,
        display_position_policy: str = "mechanical",
    ) -> dict:
        """Mark an index-aligned roll as narrated/listed in another chapter.

        This is evidence-location metadata only. It deliberately leaves
        outcome/perks/constellation untouched so hit/miss curation remains a
        separate action.
        """
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["mention_chapter_num"] = str(mention_chapter_num)
        roll["mention_word_position"] = mention_word_position
        roll["display_position_policy"] = display_position_policy
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "mark_roll_deferred_to_chapter",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": index,
                "mention_chapter_num": str(mention_chapter_num),
                "mention_word_position": mention_word_position,
                "display_position_policy": display_position_policy,
            },
        )
        return roll

    # ------------------------------------------------------------------
    # Action handlers — one per <space>X keybind.
    # ------------------------------------------------------------------

    def toggle_chapter_eligibility(self, chapter_num: str) -> bool:
        before = list(self.chapter_eligibility.get("disabled_chapters", []))
        disabled = self.chapter_eligibility.setdefault("disabled_chapters", [])
        cn = str(chapter_num)
        if cn in disabled:
            disabled.remove(cn)
            now_disabled = False
        else:
            disabled.append(cn)
            disabled.sort()
            now_disabled = True
        _atomic_write_json(self.chapter_eligibility_path, self.chapter_eligibility)
        self._append_journal(
            "toggle_chapter_eligibility", self.chapter_eligibility_path,
            cn, {"disabled_chapters": before},
            {"disabled_chapters": list(disabled)},
        )
        return now_disabled

    def mark_header_span(
        self, chapter_num: str, section_index: int,
        word_offset_start: int, word_offset_end: int,
        excerpt: str = "",
    ) -> dict:
        """Record a header span (excluded from CP-earning word counts).

        Replaces any prior entry for the same (chapter, section, range)
        — idempotent within a single run.
        """
        cors = self.header_corrections.setdefault("corrections", [])
        before = deepcopy(cors)
        # Drop any exact duplicate.
        cors = [
            c for c in cors
            if not (
                str(c.get("chapter_num")) == str(chapter_num)
                and int(c.get("section_index", -1)) == int(section_index)
                and int(c.get("word_offset_start", -1)) == int(word_offset_start)
                and int(c.get("word_offset_end", -1)) == int(word_offset_end)
            )
        ]
        new_entry = {
            "chapter_num": str(chapter_num),
            "section_index": int(section_index),
            "word_offset_start": int(word_offset_start),
            "word_offset_end": int(word_offset_end),
            "excerpt": excerpt,
        }
        cors.append(new_entry)
        cors.sort(key=lambda c: (
            str(c.get("chapter_num")),
            int(c.get("section_index", 0)),
            int(c.get("word_offset_start", 0)),
        ))
        self.header_corrections["corrections"] = cors
        _atomic_write_json(self.header_corrections_path, self.header_corrections)
        self._append_journal(
            "mark_header_span", self.header_corrections_path, str(chapter_num),
            before, deepcopy(cors), extra={"new_entry": new_entry},
        )
        return new_entry

    def mark_an_span(
        self, chapter_num: str, section_index: int,
        an_text: str, reason: str = "marked via curator TUI",
    ) -> dict:
        """Append (or replace) an author-note entry for ``chapter_num``+``section_index``."""
        notes = self.author_notes.setdefault("author_notes", [])
        before = deepcopy(notes)
        # Replace any existing entry for the same (chapter_num, section_index).
        notes = [
            n for n in notes
            if not (str(n.get("chapter_num")) == str(chapter_num)
                    and int(n.get("section_index", -1)) == int(section_index))
        ]
        new_entry = {
            "chapter_num": str(chapter_num),
            "section_index": int(section_index),
            "an_text": an_text,
            "reason": reason,
        }
        notes.append(new_entry)
        notes.sort(key=lambda n: (str(n.get("chapter_num")), int(n.get("section_index", 0))))
        self.author_notes["author_notes"] = notes
        _atomic_write_json(self.author_notes_path, self.author_notes)
        self._append_journal(
            "mark_an_span", self.author_notes_path, str(chapter_num),
            before, deepcopy(notes), extra={"new_entry": new_entry},
        )
        return new_entry

    def remove_annotations_at_word(
        self,
        chapter_num: str,
        word_index: int,
        *,
        author_note_keys: list[tuple[int, str]] | None = None,
    ) -> dict[str, int]:
        """Remove manual AN/header annotations that cover ``word_index``.

        ``author_note_keys`` contains ``(section_index, an_text)`` pairs
        already resolved by the caller. Header corrections carry explicit
        word offsets, so they can be removed directly here.
        """
        cn = str(chapter_num)
        wi = int(word_index)
        note_keys = {
            (int(section_index), str(an_text))
            for section_index, an_text in (author_note_keys or [])
        }

        before = {
            "author_notes": deepcopy(self.author_notes),
            "header_corrections": deepcopy(self.header_corrections),
        }

        notes = self.author_notes.setdefault("author_notes", [])
        kept_notes = []
        removed_notes = 0
        for note in notes:
            key = (int(note.get("section_index", -1)), str(note.get("an_text") or ""))
            if str(note.get("chapter_num")) == cn and key in note_keys:
                removed_notes += 1
                continue
            kept_notes.append(note)
        self.author_notes["author_notes"] = kept_notes

        corrections = self.header_corrections.setdefault("corrections", [])
        kept_corrections = []
        removed_headers = 0
        for correction in corrections:
            if (
                str(correction.get("chapter_num")) == cn
                and int(correction.get("word_offset_start", -1)) <= wi
                and wi < int(correction.get("word_offset_end", -1))
            ):
                removed_headers += 1
                continue
            kept_corrections.append(correction)
        self.header_corrections["corrections"] = kept_corrections

        if removed_notes:
            _atomic_write_json(self.author_notes_path, self.author_notes)
        if removed_headers:
            _atomic_write_json(self.header_corrections_path, self.header_corrections)
        if removed_notes or removed_headers:
            self._append_journal(
                "remove_annotations_at_word",
                MANUAL,
                cn,
                before,
                {
                    "author_notes": deepcopy(self.author_notes),
                    "header_corrections": deepcopy(self.header_corrections),
                },
                extra={
                    "word_index": wi,
                    "removed_author_notes": removed_notes,
                    "removed_header_corrections": removed_headers,
                },
            )
        return {
            "author_notes": removed_notes,
            "header_corrections": removed_headers,
        }

    def set_last_roll_outcome(
        self, chapter_num: str, outcome: str
    ) -> dict | None:
        """Set ``outcome`` (``hit``/``miss``) on the chapter's last roll."""
        before = deepcopy(self.chapter_roll_overrides)
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        roll["outcome"] = outcome
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "set_last_roll_outcome", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"outcome": outcome},
        )
        return roll

    def set_last_roll_constellation(
        self, chapter_num: str, constellation: str
    ) -> dict | None:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        roll["constellation"] = constellation
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "set_last_roll_constellation", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"constellation": constellation},
        )
        return roll

    def set_last_roll_perks(
        self, chapter_num: str, perk_names: list[str]
    ) -> dict | None:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        roll["perks"] = list(perk_names)
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "set_last_roll_perks", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"perks": list(perk_names)},
        )
        return roll

    def save_last_roll_quote(
        self, chapter_num: str, quote: str
    ) -> dict | None:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        roll["narrative_evidence"] = quote
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "save_last_roll_quote", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"quote_len": len(quote)},
        )
        return roll

    def insert_roll(
        self,
        chapter_num: str,
        word_position: int | None,
        outcome: str = "miss",
        constellation: str = "",
        perks: list[str] | None = None,
        narrative_evidence: str = "",
    ) -> dict:
        """Insert a new roll at ``word_position`` (CP-words, chapter-local)."""
        before = deepcopy(self.chapter_roll_overrides)
        entry = self._ensure_chapter_entry(str(chapter_num))
        new_roll = {
            "perks": list(perks or []),
            "outcome": outcome,
            "constellation": constellation,
            "word_position": word_position,
            "narrative_evidence": narrative_evidence,
        }
        rolls = entry["rolls"]
        # Insert in word-position order; rolls without word_position go last.
        inserted = False
        for i, r in enumerate(rolls):
            wp = r.get("word_position")
            if wp is not None and word_position is not None and word_position < wp:
                rolls.insert(i, new_roll)
                inserted = True
                break
        if not inserted:
            rolls.append(new_roll)
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "insert_roll", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"word_position": word_position, "outcome": outcome},
        )
        return new_roll

    def undo_last(self) -> tuple[str, str | None] | None:
        """Pop the latest journal entry and restore the prior state.

        Returns ``(action_type, chapter_num)`` for the action that was
        undone, or ``None`` if there's nothing to undo. Skips entries
        that are themselves undos (no double-undo cycling).
        """
        journal_path = self._journal()
        if not journal_path.exists():
            return None
        text = journal_path.read_text().splitlines()
        if not text:
            return None
        # Walk backward to find the latest non-undo action.
        idx = len(text) - 1
        while idx >= 0:
            try:
                last = json.loads(text[idx])
            except Exception:
                idx -= 1
                continue
            if last.get("action_type") != "undo":
                break
            idx -= 1
        if idx < 0:
            return None
        if last.get("action_type") == "remove_annotations_at_word":
            before_state = last["before"]
            author_notes = before_state.get("author_notes")
            header_corrections = before_state.get("header_corrections")
            if author_notes is not None:
                _atomic_write_json(self.author_notes_path, author_notes)
                self.author_notes = author_notes
            if header_corrections is not None:
                _atomic_write_json(self.header_corrections_path, header_corrections)
                self.header_corrections = header_corrections
            self._append_journal(
                "undo", MANUAL, last.get("chapter_num"),
                before=last.get("after"),
                after=before_state,
                extra={"undid": last.get("action_type")},
            )
            return last.get("action_type", "?"), last.get("chapter_num")
        target_rel = last["target_file"]
        before_state = last["before"]
        target_abs = Path(target_rel)
        if not target_abs.is_absolute():
            target_abs = MANUAL.parent / target_rel
        _atomic_write_json(target_abs, before_state)
        # Sync in-memory copies so live consumers see the rollback.
        if target_abs == self.chapter_roll_overrides_path or target_abs.name == "chapter_roll_overrides.json":
            self.chapter_roll_overrides = before_state
        elif target_abs == self.author_notes_path or target_abs.name == "author_notes.json":
            self.author_notes = before_state
        elif target_abs == self.chapter_eligibility_path or target_abs.name == "chapter_eligibility.json":
            self.chapter_eligibility = before_state
        elif target_abs == self.header_corrections_path or target_abs.name == "header_corrections.json":
            self.header_corrections = before_state
        # Append an "undo" record so audit trail is preserved.
        self._append_journal(
            "undo", target_abs, last.get("chapter_num"),
            before=last.get("after"),
            after=before_state,
            extra={"undid": last.get("action_type")},
        )
        return last.get("action_type", "?"), last.get("chapter_num")

    def delete_last_roll(self, chapter_num: str) -> dict | None:
        before = deepcopy(self.chapter_roll_overrides)
        cro = self.chapter_roll_overrides.get("chapter_roll_overrides") or {}
        entry = cro.get(str(chapter_num))
        if not entry:
            return None
        rolls = entry.get("rolls") or []
        if not rolls:
            return None
        removed = rolls.pop()
        _atomic_write_json(self.chapter_roll_overrides_path, self.chapter_roll_overrides)
        self._append_journal(
            "delete_last_roll", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"removed": removed},
        )
        return removed
