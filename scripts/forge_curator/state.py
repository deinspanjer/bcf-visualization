"""In-memory state model for the Forge Curator TUI (Phase 1 read-only)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from scripts.forge_curator.evidence_scorer import EvidenceCandidate
from scripts.forge_curator.evidence_scorer import evidence_candidates
from scripts.forge_curator.data_loader import (
    ChapterDerived,
    ChapterMeta,
    ChapterProse,
    ForgeCuratorData,
)


@dataclass
class RegexHits:
    pattern: str = ""
    error: str | None = None
    word_indices: list[int] = field(default_factory=list)
    """Word indices into the current chapter's prose where the regex matches."""
    char_spans: list[tuple[int, int]] = field(default_factory=list)
    """Character spans for the full regex matches."""


DEFAULT_REGEX_PATTERNS: tuple[str, ...] = ()


@dataclass
class ChapterState:
    meta: ChapterMeta
    derived: ChapterDerived
    prose: ChapterProse
    cursor_char: int = 0
    """Current cursor position as a char offset into ``prose.text``."""
    regex_hits: list[RegexHits] = field(
        default_factory=lambda: [RegexHits(), RegexHits(), RegexHits(), RegexHits()]
    )
    evidence_candidates: list[EvidenceCandidate] = field(default_factory=list)

    @property
    def cursor_word_index(self) -> int:
        """Word index (0-based) for the current cursor position.

        If the cursor is in whitespace between words, returns the index
        of the next word; if past the end, returns total_words.
        """
        wo = self.prose.word_offsets
        for i, (s, e) in enumerate(wo):
            if self.cursor_char < e:
                return i
        return len(wo)

    @property
    def total_words(self) -> int:
        return len(self.prose.word_offsets)

    def section_index_at(self, word_idx: int) -> int:
        """Return which section the given word index belongs to (0-based)."""
        breaks = self.prose.section_break_word_indices
        idx = 0
        for i, b in enumerate(breaks):
            if word_idx >= b:
                idx = i + 1
            else:
                break
        return idx


@dataclass
class ForgeCuratorState:
    data: ForgeCuratorData
    chapter: ChapterState | None = None

    def load_chapter(self, chapter_num: str) -> ChapterState:
        cn = str(chapter_num)
        meta = self.data.chapter_meta(cn)
        derived = self.data.chapter_derived(cn)
        prose = self.data.chapter_prose(cn)
        cs = ChapterState(meta=meta, derived=derived, prose=prose)
        header_ranges = tuple(prose.implicit_header_word_ranges or ())
        cs.evidence_candidates = [
            candidate
            for candidate in evidence_candidates(prose.text, prose.word_offsets)
            if not any(
                start <= candidate.word_index < end
                for start, end in header_ranges
            )
        ]
        self.chapter = cs
        for slot, pattern in enumerate(DEFAULT_REGEX_PATTERNS):
            self.set_regex(slot, pattern)
        return cs

    # --- navigation helpers ---

    def next_chapter(self) -> str | None:
        if self.chapter is None:
            return None
        order = self.data.chapter_order
        try:
            i = order.index(self.chapter.meta.chapter_num)
        except ValueError:
            return None
        if i + 1 < len(order):
            return order[i + 1]
        return None

    def prev_chapter(self) -> str | None:
        if self.chapter is None:
            return None
        order = self.data.chapter_order
        try:
            i = order.index(self.chapter.meta.chapter_num)
        except ValueError:
            return None
        if i > 0:
            return order[i - 1]
        return None

    # --- cursor moves ---

    def set_cursor_char(self, char: int) -> None:
        if self.chapter is None:
            return
        n = len(self.chapter.prose.text)
        self.chapter.cursor_char = max(0, min(char, n))

    def char_at_word_index(self, word_idx: int) -> int:
        if self.chapter is None:
            return 0
        wo = self.chapter.prose.word_offsets
        if not wo:
            return 0
        if word_idx <= 0:
            return wo[0][0]
        if word_idx >= len(wo):
            return wo[-1][0]
        return wo[word_idx][0]

    # --- regex ---

    def set_regex(self, slot: int, pattern: str) -> RegexHits:
        if self.chapter is None or not (0 <= slot < 4):
            return RegexHits(pattern=pattern)
        hits = RegexHits(pattern=pattern)
        if not pattern:
            self.chapter.regex_hits[slot] = hits
            return hits
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            hits.error = str(exc)
            self.chapter.regex_hits[slot] = hits
            return hits
        text = self.chapter.prose.text
        word_offsets = self.chapter.prose.word_offsets
        for match in rx.finditer(text):
            start, end = match.span()
            if start < end:
                hits.char_spans.append((start, end))
            wi = _word_index_for_char(word_offsets, start)
            if wi is not None and wi not in hits.word_indices:
                hits.word_indices.append(wi)
        hits.word_indices.sort()
        self.chapter.regex_hits[slot] = hits
        return hits


def _word_index_for_char(
    word_offsets: list[tuple[int, int]], char: int
) -> int | None:
    """Binary-search-ish: which word does ``char`` fall in / before?"""
    for i, (s, e) in enumerate(word_offsets):
        if char < e:
            return i
    return len(word_offsets) - 1 if word_offsets else None
