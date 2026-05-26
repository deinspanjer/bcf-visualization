"""Curation persistence for the Forge Curator TUI (Phase 2).

Routes each curation action to its canonical override file and journals
every change for forensic rollback. Auto-save semantics: each
:meth:`apply_action` call writes the override file AND appends a journal
entry, so the working set on disk is always current.

Override files (each is a single JSON document):

- ``data/manual/chapter_roll_overrides.json`` — per-roll metadata
  (outcome, constellation, perks, evidence_quotes, word_position).
- ``data/manual/section_classifications.json`` — section-level
  CP-eligibility truth and passage-level span overrides used by derivation.

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
    CHAPTER_ROLL_OVERRIDES,
    MANUAL,
)

SECTION_CLASSIFICATIONS = MANUAL / "section_classifications.json"
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
        section_classifications_path: Path | None = None,
        journal_dir_path: Path | None = None,
    ) -> None:
        self.chapter_roll_overrides_path = chapter_roll_overrides_path or CHAPTER_ROLL_OVERRIDES
        self.chapter_alignment_fingerprints_path = (
            self.chapter_roll_overrides_path.parent.parent
            / "derived"
            / "chapter_alignment_fingerprints.json"
        )
        self.section_classifications_path = (
            section_classifications_path or SECTION_CLASSIFICATIONS
        )
        self.journal_dir_path = journal_dir_path or JOURNAL_DIR
        # Load existing override docs (or empty stubs).
        self.chapter_roll_overrides = self._load_or_default(
            self.chapter_roll_overrides_path,
            {
                "_purpose": "Per-chapter paid roll structure + curated metadata.",
                "chapter_roll_overrides": {},
            },
        )
        self.section_classifications = self._load_or_default(
            self.section_classifications_path,
            {
                "_source": "Forge Curator section eligibility curation.",
                "classifications": {},
            },
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

    def _write_chapter_roll_overrides(self, before: dict) -> None:
        try:
            _atomic_write_json(
                self.chapter_roll_overrides_path,
                self.chapter_roll_overrides,
            )
        except Exception:
            self.chapter_roll_overrides = deepcopy(before)
            raise

    def _write_section_classifications(self, before: dict) -> None:
        try:
            _atomic_write_json(
                self.section_classifications_path,
                self.section_classifications,
            )
        except Exception:
            self.section_classifications = deepcopy(before)
            raise

    # ------------------------------------------------------------------
    # Helpers — locate / create per-chapter or per-roll structures.
    # ------------------------------------------------------------------

    def _ensure_chapter_entry(self, chapter_num: str) -> dict:
        """Get or create the chapter_roll_overrides entry for ``chapter_num``."""
        cro = self.chapter_roll_overrides.setdefault("chapter_roll_overrides", {})
        if chapter_num not in cro:
            cro[chapter_num] = {"rolls": []}
        elif "rolls" not in cro[chapter_num]:
            cro[chapter_num]["rolls"] = []
        self._stamp_chapter_alignment_fingerprint(chapter_num, cro[chapter_num])
        return cro[chapter_num]

    def _stamp_chapter_alignment_fingerprint(
        self,
        chapter_num: str,
        entry: dict,
    ) -> None:
        if entry.get("_fingerprint"):
            return
        if not self.chapter_alignment_fingerprints_path.exists():
            return
        doc = json.loads(self.chapter_alignment_fingerprints_path.read_text())
        fingerprints = doc.get("chapter_alignment_fingerprints") or {}
        entry["_fingerprint"] = fingerprints.get(str(chapter_num), "sha256:none")

    def _ensure_section_classification_entry(
        self,
        chapter_num: str,
        section_index: int,
        *,
        header: str | None,
        current_counts_for_cp: bool | None = None,
    ) -> dict:
        classifications = self.section_classifications.setdefault(
            "classifications", {}
        )
        key = f"{chapter_num}@{int(section_index)}"
        if key not in classifications:
            classifications[key] = {
                "chapter_num": str(chapter_num),
                "section_index": int(section_index),
                "header": header,
                "counts_for_cp": (
                    bool(current_counts_for_cp)
                    if current_counts_for_cp is not None else True
                ),
                "reason": "curator-created section classification",
            }
        return classifications[key]

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
                "skipped": False,
                "source_roll_number": None,
                "evidence_quotes": [],
                "deferred_to_later_chapter": False,
                "curator_note": None,
            })
        return rolls[index - 1]

    @staticmethod
    def _quote_record(
        text: str,
        mention_chapter_num: str | None,
        mention_word_position: int | None,
    ) -> dict:
        return {
            "text": text,
            "mention_chapter_num": (
                str(mention_chapter_num)
                if mention_chapter_num is not None else None
            ),
            "mention_word_position": (
                int(mention_word_position)
                if mention_word_position is not None else None
            ),
        }

    def update_roll_at_index(
        self,
        chapter_num: str,
        index: int,
        *,
        outcome: str | None = None,
        constellation: str | None = None,
        perks: list[str] | None = None,
        evidence_quotes: list[dict] | None = None,
        mention_chapter_num: str | None = None,
        mention_word_position: int | None = None,
        display_position_policy: str | None = None,
        curator_note: str | None = None,
        skipped: bool | None = None,
        source_roll_number: int | None = None,
    ) -> dict:
        """Update an override roll at 1-based chapter-local ``index``.

        Auto-saves and journals. Fields left as ``None`` are not changed.
        """
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        if outcome is not None:
            roll["outcome"] = outcome
            roll["skipped"] = False
        if constellation is not None:
            roll["constellation"] = constellation
        if perks is not None:
            roll["perks"] = list(perks)
            if perks:
                roll["skipped"] = False
        if evidence_quotes is not None:
            roll["evidence_quotes"] = list(evidence_quotes)
        if mention_chapter_num is not None:
            roll["mention_chapter_num"] = str(mention_chapter_num)
        if mention_word_position is not None:
            roll["mention_word_position"] = int(mention_word_position)
        if display_position_policy is not None:
            roll["display_position_policy"] = display_position_policy
        if curator_note is not None:
            roll["curator_note"] = curator_note
        if skipped is not None:
            roll["skipped"] = bool(skipped)
            if skipped:
                roll["outcome"] = None
                roll["perks"] = []
                roll["constellation"] = None
        if source_roll_number is not None:
            roll["source_roll_number"] = int(source_roll_number)
            roll["deferred_to_later_chapter"] = False
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "update_roll_at_index", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"index": index, "outcome": outcome,
                   "constellation": constellation, "perks": perks,
                   "evidence_quotes": evidence_quotes,
                   "mention_chapter_num": mention_chapter_num,
                   "mention_word_position": mention_word_position,
                   "display_position_policy": display_position_policy,
                   "curator_note": curator_note,
                   "skipped": skipped,
                   "source_roll_number": source_roll_number},
        )
        return roll

    def assign_source_roll_at_index(
        self, chapter_num: str, index: int, source_roll_number: int,
    ) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        source_roll_number = int(source_roll_number)
        for other_chapter, entry in (
            self.chapter_roll_overrides.get("chapter_roll_overrides", {}).items()
        ):
            for other_index, roll in enumerate(entry.get("rolls") or [], start=1):
                if (
                    str(other_chapter) == str(chapter_num)
                    and int(other_index) == int(index)
                ):
                    continue
                if not isinstance(roll, dict):
                    continue
                if roll.get("source_roll_number") == source_roll_number:
                    roll["source_roll_number"] = None
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["source_roll_number"] = source_roll_number
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "assign_source_roll_at_index",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": int(index),
                "source_roll_number": source_roll_number,
            },
        )
        return roll

    def assign_obtained_perk_at_index(
        self,
        chapter_num: str,
        index: int,
        *,
        perk_name: str,
        constellation: str | None = None,
    ) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["outcome"] = "hit"
        roll["perks"] = [str(perk_name)]
        roll["constellation"] = str(constellation) if constellation else None
        roll["skipped"] = False
        roll["source_roll_number"] = None
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "assign_obtained_perk_at_index",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": int(index),
                "perk_name": str(perk_name),
                "constellation": constellation,
            },
        )
        return roll

    def ensure_roll_count(self, chapter_num: str, count: int) -> None:
        before = deepcopy(self.chapter_roll_overrides)
        for index in range(1, int(count) + 1):
            self.get_or_create_roll_at_index(chapter_num, index)
        self._write_chapter_roll_overrides(before)

    def mark_source_roll_deferred_to_chapter(
        self,
        chapter_num: str,
        index: int,
        target_chapter_num: str,
    ) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["source_deferred_to_chapter"] = str(target_chapter_num)
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "mark_source_roll_deferred_to_chapter",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": index,
                "target_chapter_num": str(target_chapter_num),
            },
        )
        return roll

    def clear_source_roll_deferral(self, chapter_num: str, index: int) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["source_deferred_to_chapter"] = None
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "clear_source_roll_deferral",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"index": index},
        )
        return roll

    def _existing_roll_at_index(self, chapter_num: str, index: int) -> dict | None:
        entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(chapter_num), {})
        )
        rolls = entry.get("rolls") or []
        if not (1 <= int(index) <= len(rolls)):
            return None
        roll = rolls[int(index) - 1]
        return roll if isinstance(roll, dict) else None

    def delete_chapter_curation_items(self, items: list[dict]) -> int:
        """Clear selected persisted curation fields without deleting roll slots."""
        before = {
            "chapter_roll_overrides": deepcopy(self.chapter_roll_overrides),
            "section_classifications": deepcopy(self.section_classifications),
        }
        deleted = 0
        for item in items:
            kind = str(item.get("kind") or "")
            chapter_num = str(item.get("chapter_num") or "")
            roll_index = item.get("roll_index")
            if kind == "model_validation_resolution":
                entry = (
                    self.chapter_roll_overrides
                    .get("chapter_roll_overrides", {})
                    .get(chapter_num, {})
                )
                if entry.pop("model_validation_resolution", None) is not None:
                    deleted += 1
                continue
            if kind == "section_eligibility":
                section_key = str(item.get("section_key") or "")
                entry = (
                    self.section_classifications
                    .get("classifications", {})
                    .get(section_key)
                )
                if (
                    isinstance(entry, dict)
                    and str(entry.get("chapter_num")) == chapter_num
                    and str(entry.get("reason") or "").startswith("curator toggle:")
                ):
                    entry["counts_for_cp"] = True
                    entry.pop("reason", None)
                    deleted += 1
                continue
            if kind == "eligibility_span":
                section_key = str(item.get("section_key") or "")
                span_index = int(item.get("span_index", -1))
                entry = (
                    self.section_classifications
                    .get("classifications", {})
                    .get(section_key)
                )
                if isinstance(entry, dict) and str(entry.get("chapter_num")) == chapter_num:
                    spans = list(entry.get("span_overrides") or [])
                    if 0 <= span_index < len(spans):
                        spans.pop(span_index)
                        if spans:
                            entry["span_overrides"] = spans
                        else:
                            entry.pop("span_overrides", None)
                        deleted += 1
                continue
            if roll_index is None:
                continue
            roll = self._existing_roll_at_index(chapter_num, int(roll_index))
            if roll is None:
                continue
            if kind == "source_deferral":
                if roll.get("source_deferred_to_chapter") is not None:
                    roll["source_deferred_to_chapter"] = None
                    deleted += 1
            elif kind == "source_assignment":
                if roll.get("source_roll_number") is not None:
                    roll["source_roll_number"] = None
                    deleted += 1
            elif kind == "evidence_quote":
                quote_index = int(item.get("quote_index", -1))
                quotes = roll.get("evidence_quotes") or []
                if 0 <= quote_index < len(quotes):
                    quotes.pop(quote_index)
                    roll["evidence_quotes"] = quotes
                    deleted += 1
            elif kind == "outcome":
                if roll.get("outcome") is not None:
                    roll["outcome"] = None
                    deleted += 1
            elif kind == "constellation":
                if roll.get("constellation") is not None:
                    roll["constellation"] = None
                    deleted += 1
            elif kind == "perks":
                if roll.get("perks"):
                    roll["perks"] = []
                    deleted += 1
            elif kind == "skipped":
                if roll.get("skipped"):
                    roll["skipped"] = False
                    deleted += 1
            elif kind == "roll_deferral":
                changed = False
                for field, value in (
                    ("mention_chapter_num", None),
                    ("mention_word_position", None),
                    ("display_position_policy", None),
                    ("deferred_to_later_chapter", False),
                ):
                    if roll.get(field) != value:
                        roll[field] = value
                        changed = True
                if changed:
                    deleted += 1
        if not deleted:
            return 0
        chapter_before = before["chapter_roll_overrides"]
        section_before = before["section_classifications"]
        if self.chapter_roll_overrides != chapter_before:
            self._write_chapter_roll_overrides(chapter_before)
        if self.section_classifications != section_before:
            self._write_section_classifications(section_before)
        self._append_journal(
            "delete_chapter_curation_items",
            MANUAL,
            ",".join(sorted({str(item.get("chapter_num") or "") for item in items})),
            before,
            {
                "chapter_roll_overrides": deepcopy(self.chapter_roll_overrides),
                "section_classifications": deepcopy(self.section_classifications),
            },
            extra={"items": deepcopy(items), "deleted": deleted},
        )
        return deleted

    @staticmethod
    def _clear_quote_display_anchor_if_empty(roll: dict, old_quotes: list[dict]) -> None:
        if roll.get("evidence_quotes"):
            return
        if roll.get("display_position_policy") != "mention":
            return
        for quote in old_quotes:
            if (
                str(roll.get("mention_chapter_num"))
                == str(quote.get("mention_chapter_num"))
                and roll.get("mention_word_position")
                == quote.get("mention_word_position")
            ):
                roll["mention_chapter_num"] = None
                roll["mention_word_position"] = None
                roll["display_position_policy"] = None
                return

    def shift_roll_evidence_for_deferred_source_assignment(
        self,
        *,
        target_chapter_num: str,
        target_index: int,
        source_chapter_num: str,
        source_index: int,
    ) -> str:
        """Move a chapter-local quote chain after a deferred source assignment."""
        target_roll = self.get_or_create_roll_at_index(
            str(target_chapter_num), int(target_index)
        )
        if target_roll.get("evidence_quotes"):
            return "target_has_evidence"

        source_entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(source_chapter_num))
        )
        source_rolls = (source_entry or {}).get("rolls") or []
        if not (1 <= int(source_index) <= len(source_rolls)):
            return "no_source_evidence"
        source_roll = source_rolls[int(source_index) - 1]
        if not isinstance(source_roll, dict) or not source_roll.get("evidence_quotes"):
            return "no_source_evidence"

        before = deepcopy(self.chapter_roll_overrides)
        target_roll["evidence_quotes"] = deepcopy(source_roll.get("evidence_quotes") or [])
        for offset in range(int(source_index) - 1, len(source_rolls)):
            roll = source_rolls[offset]
            if not isinstance(roll, dict):
                continue
            old_quotes = list(roll.get("evidence_quotes") or [])
            next_quotes: list[dict] = []
            if offset + 1 < len(source_rolls):
                next_roll = source_rolls[offset + 1]
                if isinstance(next_roll, dict):
                    next_quotes = deepcopy(next_roll.get("evidence_quotes") or [])
            roll["evidence_quotes"] = next_quotes
            self._clear_quote_display_anchor_if_empty(roll, old_quotes)
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "shift_roll_evidence_for_deferred_source_assignment",
            self.chapter_roll_overrides_path,
            f"{source_chapter_num}->{target_chapter_num}",
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "target_chapter_num": str(target_chapter_num),
                "target_index": int(target_index),
                "source_chapter_num": str(source_chapter_num),
                "source_index": int(source_index),
            },
        )
        return "shifted"

    def assign_source_roll_with_evidence_at_index(
        self,
        *,
        target_chapter_num: str,
        target_index: int,
        source_roll_number: int,
        copied_quotes: list[dict] | None = None,
        mention_chapter_num: str | None = None,
        display_position_policy: str | None = None,
        shift_source_chapter_num: str | None = None,
        shift_source_index: int | None = None,
    ) -> str:
        """Assign source provenance and any quote movement in one journal entry."""
        before = deepcopy(self.chapter_roll_overrides)
        source_roll_number = int(source_roll_number)
        for other_chapter, entry in (
            self.chapter_roll_overrides.get("chapter_roll_overrides", {}).items()
        ):
            for other_index, roll in enumerate(entry.get("rolls") or [], start=1):
                if (
                    str(other_chapter) == str(target_chapter_num)
                    and int(other_index) == int(target_index)
                ):
                    continue
                if not isinstance(roll, dict):
                    continue
                if roll.get("source_roll_number") == source_roll_number:
                    roll["source_roll_number"] = None

        target_roll = self.get_or_create_roll_at_index(target_chapter_num, target_index)
        target_roll["source_roll_number"] = source_roll_number
        target_roll["deferred_to_later_chapter"] = False
        if mention_chapter_num is not None:
            target_roll["mention_chapter_num"] = str(mention_chapter_num)
        if display_position_policy is not None:
            target_roll["display_position_policy"] = display_position_policy

        result = "assigned"
        if shift_source_chapter_num is not None and shift_source_index is not None:
            if target_roll.get("evidence_quotes"):
                result = "target_has_evidence"
            else:
                source_entry = (
                    self.chapter_roll_overrides
                    .get("chapter_roll_overrides", {})
                    .get(str(shift_source_chapter_num))
                )
                source_rolls = (source_entry or {}).get("rolls") or []
                if 1 <= int(shift_source_index) <= len(source_rolls):
                    source_roll = source_rolls[int(shift_source_index) - 1]
                    if isinstance(source_roll, dict) and source_roll.get("evidence_quotes"):
                        target_roll["evidence_quotes"] = deepcopy(
                            source_roll.get("evidence_quotes") or []
                        )
                        for offset in range(int(shift_source_index) - 1, len(source_rolls)):
                            roll = source_rolls[offset]
                            if not isinstance(roll, dict):
                                continue
                            old_quotes = list(roll.get("evidence_quotes") or [])
                            next_quotes: list[dict] = []
                            if offset + 1 < len(source_rolls):
                                next_roll = source_rolls[offset + 1]
                                if isinstance(next_roll, dict):
                                    next_quotes = deepcopy(
                                        next_roll.get("evidence_quotes") or []
                                    )
                            roll["evidence_quotes"] = next_quotes
                            self._clear_quote_display_anchor_if_empty(roll, old_quotes)
                        result = "shifted"
                    else:
                        result = "no_source_evidence"
                else:
                    result = "no_source_evidence"

        if result in {"assigned", "no_source_evidence"}:
            quotes = target_roll.setdefault("evidence_quotes", [])
            for quote in copied_quotes or []:
                if not isinstance(quote, dict) or not quote.get("text"):
                    continue
                record = self._quote_record(
                    str(quote["text"]),
                    (
                        str(quote["mention_chapter_num"])
                        if quote.get("mention_chapter_num") is not None
                        else None
                    ),
                    quote.get("mention_word_position"),
                )
                if record not in quotes:
                    quotes.append(record)

        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "assign_source_roll_with_evidence_at_index",
            self.chapter_roll_overrides_path,
            str(target_chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "target_index": int(target_index),
                "source_roll_number": source_roll_number,
                "result": result,
                "shift_source_chapter_num": (
                    str(shift_source_chapter_num)
                    if shift_source_chapter_num is not None else None
                ),
                "shift_source_index": shift_source_index,
            },
        )
        return result

    def mark_roll_skipped(self, chapter_num: str, index: int) -> dict:
        """Mark a predicted slot as deliberately skipped.

        This is metadata only: the derivation pipeline ignores skipped
        placeholders when building paid roll facts.
        """
        return self.update_roll_at_index(chapter_num, index, skipped=True)

    def append_roll_evidence_at_index(
        self,
        chapter_num: str,
        index: int,
        *,
        text: str,
        mention_chapter_num: str | None = None,
        mention_word_position: int | None = None,
        display_position_policy: str | None = None,
    ) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        quotes = roll.setdefault("evidence_quotes", [])
        record = self._quote_record(text, mention_chapter_num, mention_word_position)
        was_empty = len(quotes) == 0
        if record not in quotes:
            quotes.append(record)
        if roll.get("deferred_to_later_chapter"):
            if mention_chapter_num is not None:
                roll["mention_chapter_num"] = str(mention_chapter_num)
            if mention_word_position is not None:
                roll["mention_word_position"] = int(mention_word_position)
            roll["display_position_policy"] = (
                display_position_policy
                or roll.get("display_position_policy")
                or "mechanical"
            )
            roll["deferred_to_later_chapter"] = False
        if was_empty and display_position_policy is not None:
            if mention_chapter_num is not None:
                roll["mention_chapter_num"] = str(mention_chapter_num)
            if mention_word_position is not None:
                roll["mention_word_position"] = int(mention_word_position)
            roll["display_position_policy"] = display_position_policy
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "append_roll_evidence_at_index",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"index": int(index), "quote": record},
        )
        return roll

    def append_roll_evidence_at_indices(
        self,
        chapter_num: str,
        indices: list[int],
        *,
        text: str,
        mention_chapter_num: str | None = None,
        mention_word_position: int | None = None,
        display_position_policy: str | None = None,
    ) -> list[dict]:
        """Append the same curated quote to multiple chapter-local rolls.

        Missing rows are created as index-aligned stubs; untouched rows
        remain unchanged.
        """
        clean_indices = sorted({int(i) for i in indices if int(i) > 0})
        if not clean_indices:
            return []
        before = deepcopy(self.chapter_roll_overrides)
        updated: list[dict] = []
        record = self._quote_record(text, mention_chapter_num, mention_word_position)
        for index in clean_indices:
            roll = self.get_or_create_roll_at_index(chapter_num, index)
            quotes = roll.setdefault("evidence_quotes", [])
            was_empty = len(quotes) == 0
            if record not in quotes:
                quotes.append(record)
            if roll.get("deferred_to_later_chapter"):
                if mention_chapter_num is not None:
                    roll["mention_chapter_num"] = str(mention_chapter_num)
                if mention_word_position is not None:
                    roll["mention_word_position"] = int(mention_word_position)
                roll["display_position_policy"] = (
                    display_position_policy
                    or roll.get("display_position_policy")
                    or "mechanical"
                )
                roll["deferred_to_later_chapter"] = False
            if was_empty and display_position_policy is not None:
                if mention_chapter_num is not None:
                    roll["mention_chapter_num"] = str(mention_chapter_num)
                if mention_word_position is not None:
                    roll["mention_word_position"] = int(mention_word_position)
                roll["display_position_policy"] = display_position_policy
            updated.append(roll)
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "append_roll_evidence_at_indices",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "indices": clean_indices,
                "quote": record,
            },
        )
        return updated

    def append_roll_evidence_records(self, records: list[dict]) -> list[dict]:
        """Append distinct quote evidence records in one journaled mutation."""
        clean_records: list[dict] = []
        for record in records:
            try:
                chapter_num = str(record["chapter_num"])
                index = int(record["index"])
            except (KeyError, TypeError, ValueError):
                continue
            if index <= 0:
                continue
            clean_records.append({
                "chapter_num": chapter_num,
                "index": index,
                "text": str(record.get("text") or ""),
                "mention_chapter_num": (
                    str(record["mention_chapter_num"])
                    if record.get("mention_chapter_num") is not None else None
                ),
                "mention_word_position": record.get("mention_word_position"),
                "display_position_policy": record.get("display_position_policy"),
            })
        clean_records = [
            record for record in clean_records
            if record["text"].strip()
        ]
        if not clean_records:
            return []
        before = deepcopy(self.chapter_roll_overrides)
        updated: list[dict] = []
        extras: list[dict] = []
        for item in clean_records:
            quote = self._quote_record(
                item["text"],
                item["mention_chapter_num"],
                item["mention_word_position"],
            )
            roll = self.get_or_create_roll_at_index(
                item["chapter_num"], item["index"]
            )
            quotes = roll.setdefault("evidence_quotes", [])
            was_empty = len(quotes) == 0
            if quote not in quotes:
                quotes.append(quote)
            if roll.get("deferred_to_later_chapter"):
                if item["mention_chapter_num"] is not None:
                    roll["mention_chapter_num"] = item["mention_chapter_num"]
                if item["mention_word_position"] is not None:
                    roll["mention_word_position"] = int(item["mention_word_position"])
                roll["display_position_policy"] = (
                    item["display_position_policy"]
                    or roll.get("display_position_policy")
                    or "mechanical"
                )
                roll["deferred_to_later_chapter"] = False
            if was_empty and item["display_position_policy"] is not None:
                if item["mention_chapter_num"] is not None:
                    roll["mention_chapter_num"] = item["mention_chapter_num"]
                if item["mention_word_position"] is not None:
                    roll["mention_word_position"] = int(item["mention_word_position"])
                roll["display_position_policy"] = item["display_position_policy"]
            updated.append(roll)
            extras.append({
                "chapter_num": item["chapter_num"],
                "index": item["index"],
                "quote": quote,
            })
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "append_roll_evidence_records",
            self.chapter_roll_overrides_path,
            clean_records[0]["chapter_num"],
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"records": extras},
        )
        return updated

    def remove_roll_evidence_quote_at_index(
        self, chapter_num: str, index: int, quote: dict,
    ) -> bool:
        entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(chapter_num))
        )
        rolls = (entry or {}).get("rolls") or []
        if not (1 <= int(index) <= len(rolls)):
            return False
        roll = rolls[int(index) - 1]
        quotes = roll.get("evidence_quotes") or []
        if quote not in quotes:
            return False
        before = deepcopy(self.chapter_roll_overrides)
        roll["evidence_quotes"] = [q for q in quotes if q != quote]
        if (
            not roll["evidence_quotes"]
            and roll.get("display_position_policy") == "mention"
            and str(roll.get("mention_chapter_num")) == str(quote.get("mention_chapter_num"))
            and roll.get("mention_word_position") == quote.get("mention_word_position")
        ):
            roll["mention_chapter_num"] = None
            roll["mention_word_position"] = None
            roll["display_position_policy"] = None
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "remove_roll_evidence_quote_at_index",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"index": int(index), "quote": quote},
        )
        return True

    def move_roll_evidence_quote_between_indices(
        self,
        *,
        source_chapter_num: str,
        source_index: int,
        target_chapter_num: str,
        target_index: int,
        quote: dict,
    ) -> bool:
        """Move one saved quote record between roll override rows.

        This preserves the quote record exactly and writes one journaled
        mutation so quote reassignments cannot be half-applied.
        """
        source_entry = (
            self.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(source_chapter_num))
        )
        source_rolls = (source_entry or {}).get("rolls") or []
        if not (1 <= int(source_index) <= len(source_rolls)):
            return False
        source_roll = source_rolls[int(source_index) - 1]
        source_quotes = source_roll.get("evidence_quotes") or []
        if quote not in source_quotes:
            return False
        before = deepcopy(self.chapter_roll_overrides)
        target_roll = self.get_or_create_roll_at_index(
            str(target_chapter_num), int(target_index)
        )
        target_quotes = target_roll.setdefault("evidence_quotes", [])
        if quote not in target_quotes:
            target_quotes.append(deepcopy(quote))
        source_roll["evidence_quotes"] = [q for q in source_quotes if q != quote]
        if (
            not source_roll["evidence_quotes"]
            and source_roll.get("display_position_policy") == "mention"
            and str(source_roll.get("mention_chapter_num"))
            == str(quote.get("mention_chapter_num"))
            and source_roll.get("mention_word_position")
            == quote.get("mention_word_position")
        ):
            source_roll["mention_chapter_num"] = None
            source_roll["mention_word_position"] = None
            source_roll["display_position_policy"] = None
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "move_roll_evidence_quote_between_indices",
            self.chapter_roll_overrides_path,
            str(source_chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "source_index": int(source_index),
                "target_chapter_num": str(target_chapter_num),
                "target_index": int(target_index),
                "quote": quote,
            },
        )
        return True

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
        if not roll.get("evidence_quotes"):
            return False
        before = deepcopy(self.chapter_roll_overrides)
        roll["evidence_quotes"] = []
        self._write_chapter_roll_overrides(before)
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
        self._write_chapter_roll_overrides(before)
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

    def mark_roll_deferred_to_later_chapter(
        self,
        chapter_num: str,
        index: int,
        *,
        display_position_policy: str = "mechanical",
    ) -> dict:
        """Mark an unresolved predicted slot as deferred to a later chapter.

        Unlike concrete roll deferral, this leaves the mention chapter unset so
        Forge Curator can surface the unresolved slot in every later chapter
        until a source row or quote ties it to a specific chapter.
        """
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["mention_chapter_num"] = None
        roll["mention_word_position"] = None
        roll["display_position_policy"] = display_position_policy
        roll["deferred_to_later_chapter"] = True
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "mark_roll_deferred_to_later_chapter",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": index,
                "display_position_policy": display_position_policy,
            },
        )
        return roll

    def clear_roll_deferral(self, chapter_num: str, index: int) -> dict:
        """Remove roll-level deferral and keep display at the mechanical slot."""
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["mention_chapter_num"] = str(chapter_num)
        roll["mention_word_position"] = None
        roll["display_position_policy"] = "mechanical"
        roll["deferred_to_later_chapter"] = False
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "clear_roll_deferral",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={"index": int(index)},
        )
        return roll

    def set_roll_visualization_anchor(
        self,
        chapter_num: str,
        index: int,
        *,
        mention_chapter_num: str,
        mention_word_position: int | None,
        display_position_policy: str,
    ) -> dict:
        before = deepcopy(self.chapter_roll_overrides)
        roll = self.get_or_create_roll_at_index(chapter_num, index)
        roll["mention_chapter_num"] = str(mention_chapter_num)
        roll["mention_word_position"] = (
            int(mention_word_position)
            if mention_word_position is not None else None
        )
        roll["display_position_policy"] = display_position_policy
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "set_roll_visualization_anchor",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "index": int(index),
                "mention_chapter_num": str(mention_chapter_num),
                "mention_word_position": mention_word_position,
                "display_position_policy": display_position_policy,
            },
        )
        return roll

    def resolve_model_validation_issue(
        self,
        chapter_num: str,
        *,
        issue_code: str,
        reason_code: str,
        note: str,
    ) -> dict:
        """Mark a chapter-level model validation issue as curator-resolved."""
        before = deepcopy(self.chapter_roll_overrides)
        entry = self._ensure_chapter_entry(str(chapter_num))
        existing = entry.get("model_validation_resolution") or {}
        existing_codes = [
            str(code)
            for code in (existing.get("resolved_issue_codes") or [])
        ]
        resolved_codes = list(dict.fromkeys([*existing_codes, str(issue_code)]))
        resolution = {
            "status": "resolved",
            "resolved_issue_codes": resolved_codes,
            "reason_code": reason_code,
            "note": note,
        }
        entry["model_validation_resolution"] = resolution
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "resolve_model_validation_issue",
            self.chapter_roll_overrides_path,
            str(chapter_num),
            before,
            deepcopy(self.chapter_roll_overrides),
            extra={
                "issue_code": str(issue_code),
                "reason_code": reason_code,
                "note": note,
            },
        )
        return resolution

    # ------------------------------------------------------------------
    # Action handlers — one per <space>X keybind.
    # ------------------------------------------------------------------

    def toggle_section_eligibility(
        self,
        chapter_num: str,
        section_index: int,
        *,
        header: str | None,
        current_counts_for_cp: bool | None = None,
    ) -> bool:
        before = deepcopy(self.section_classifications)
        cn = str(chapter_num)
        entry = self._ensure_section_classification_entry(
            cn,
            int(section_index),
            header=header,
            current_counts_for_cp=current_counts_for_cp,
        )
        previous_reason = str(entry.get("reason") or "")
        now_eligible = not bool(entry.get("counts_for_cp", True))
        entry["counts_for_cp"] = now_eligible
        entry["reason"] = (
            f"curator toggle: {'eligible' if now_eligible else 'ineligible'}"
            + (f" (was: {previous_reason})" if previous_reason else "")
        )
        self._write_section_classifications(before)
        self._append_journal(
            "toggle_section_eligibility",
            self.section_classifications_path,
            cn,
            before,
            deepcopy(self.section_classifications),
            extra={
                "section_index": int(section_index),
                "counts_for_cp": now_eligible,
            },
        )
        return now_eligible

    def mark_span_eligibility(
        self,
        chapter_num: str,
        section_index: int,
        word_offset_start: int,
        word_offset_end: int,
        *,
        counts_for_cp: bool,
        reason_code: str,
        note: str | None = None,
        excerpt: str = "",
        header: str | None = None,
        current_counts_for_cp: bool | None = None,
    ) -> dict:
        """Record a selected passage as a CP-eligibility span override.

        Offsets are chapter-local word offsets. The entry lives under
        the containing section's classification row so the derivation
        pipeline can apply it on top of the section-level base state.
        """
        if int(word_offset_end) <= int(word_offset_start):
            raise ValueError("eligibility span must cover at least one word")
        reason_code = str(reason_code).strip()
        if not reason_code:
            raise ValueError("eligibility span reason_code is required")
        before = deepcopy(self.section_classifications)
        entry = self._ensure_section_classification_entry(
            str(chapter_num),
            int(section_index),
            header=header,
            current_counts_for_cp=current_counts_for_cp,
        )
        spans = entry.setdefault("span_overrides", [])
        spans = [
            span for span in spans
            if not (
                int(span.get("word_offset_start", -1)) == int(word_offset_start)
                and int(span.get("word_offset_end", -1)) == int(word_offset_end)
            )
        ]
        new_entry = {
            "word_offset_start": int(word_offset_start),
            "word_offset_end": int(word_offset_end),
            "counts_for_cp": bool(counts_for_cp),
            "reason_code": reason_code,
            "note": str(note).strip() if note and str(note).strip() else None,
            "excerpt": excerpt,
        }
        spans.append(new_entry)
        spans.sort(key=lambda span: (
            int(span.get("word_offset_start", 0)),
            int(span.get("word_offset_end", 0)),
        ))
        entry["span_overrides"] = spans
        self._write_section_classifications(before)
        self._append_journal(
            "mark_span_eligibility",
            self.section_classifications_path,
            str(chapter_num),
            before,
            deepcopy(self.section_classifications),
            extra={
                "section_index": int(section_index),
                "new_entry": new_entry,
            },
        )
        return new_entry

    def remove_annotations_at_word(
        self,
        chapter_num: str,
        word_index: int,
    ) -> dict[str, int]:
        """Remove passage-level eligibility spans that cover ``word_index``."""
        cn = str(chapter_num)
        wi = int(word_index)

        before = {
            "section_classifications": deepcopy(self.section_classifications),
        }

        classifications = self.section_classifications.setdefault(
            "classifications", {}
        )
        removed_eligibility_spans = 0
        for key, entry in classifications.items():
            if str(entry.get("chapter_num")) != cn:
                continue
            spans = entry.get("span_overrides") or []
            kept_spans = []
            for span in spans:
                if (
                    int(span.get("word_offset_start", -1)) <= wi
                    and wi < int(span.get("word_offset_end", -1))
                ):
                    removed_eligibility_spans += 1
                    continue
                kept_spans.append(span)
            if kept_spans:
                entry["span_overrides"] = kept_spans
            elif "span_overrides" in entry:
                entry.pop("span_overrides", None)

        if removed_eligibility_spans:
            self._write_section_classifications(before["section_classifications"])
        if removed_eligibility_spans:
            self._append_journal(
                "remove_annotations_at_word",
                MANUAL,
                cn,
                before,
                {
                    "section_classifications": deepcopy(
                        self.section_classifications
                    ),
                },
                extra={
                    "word_index": wi,
                    "removed_eligibility_spans": removed_eligibility_spans,
                },
            )
        return {"eligibility_spans": removed_eligibility_spans}

    def set_last_roll_outcome(
        self, chapter_num: str, outcome: str
    ) -> dict | None:
        """Set ``outcome`` (``hit``/``miss``) on the chapter's last roll."""
        before = deepcopy(self.chapter_roll_overrides)
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        roll["outcome"] = outcome
        self._write_chapter_roll_overrides(before)
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
        self._write_chapter_roll_overrides(before)
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
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "set_last_roll_perks", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"perks": list(perk_names)},
        )
        return roll

    def save_last_roll_quote(
        self, chapter_num: str, quote: str
    ) -> dict | None:
        roll = self._last_roll(str(chapter_num))
        if roll is None:
            return None
        return self.append_roll_evidence_at_index(
            chapter_num,
            len(
                self.chapter_roll_overrides
                .get("chapter_roll_overrides", {})
                .get(str(chapter_num), {})
                .get("rolls", [])
            ),
            text=quote,
        )

    def insert_roll(
        self,
        chapter_num: str,
        word_position: int | None,
        outcome: str = "miss",
        constellation: str = "",
        perks: list[str] | None = None,
        evidence_quotes: list[dict] | None = None,
    ) -> dict:
        """Insert a new roll at ``word_position`` (CP-words, chapter-local)."""
        before = deepcopy(self.chapter_roll_overrides)
        entry = self._ensure_chapter_entry(str(chapter_num))
        new_roll = {
            "perks": list(perks or []),
            "outcome": outcome,
            "constellation": constellation,
            "word_position": word_position,
            "evidence_quotes": list(evidence_quotes or []),
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
        self._write_chapter_roll_overrides(before)
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
        target_rel = last["target_file"]
        before_state = last["before"]
        target_abs = Path(target_rel)
        if not target_abs.is_absolute():
            target_abs = MANUAL.parent / target_rel
        _atomic_write_json(target_abs, before_state)
        # Sync in-memory copies so live consumers see the rollback.
        if target_abs == self.chapter_roll_overrides_path or target_abs.name == "chapter_roll_overrides.json":
            self.chapter_roll_overrides = before_state
        elif target_abs == self.section_classifications_path or target_abs.name == "section_classifications.json":
            self.section_classifications = before_state
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
        self._write_chapter_roll_overrides(before)
        self._append_journal(
            "delete_last_roll", self.chapter_roll_overrides_path, str(chapter_num),
            before, deepcopy(self.chapter_roll_overrides),
            extra={"removed": removed},
        )
        return removed
