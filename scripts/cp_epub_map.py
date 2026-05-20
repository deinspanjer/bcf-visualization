"""Canonical CP-eligible ↔ EPUB word offset map.

The CP-eligibility data lives in two files:
  - ``data/derived/chapter_sections.json``: per-chapter section structure
    (word_count for each section, chapter-local).
  - ``data/manual/section_classifications.json``: per-section
    ``counts_for_cp`` flag plus ``span_overrides`` that flip CP eligibility
    for individual passages.

This module folds that data into one sorted, disjoint list of CP-eligible
half-open EPUB word ranges, with a parallel CP-prefix-sum. Both
``epub_to_cp`` and ``cp_to_epub`` are O(log n) binary-search lookups.

Coordinates throughout:
  - EPUB word offset = cumulative word index across the whole story, where
    word 0 is the first word of chapter 1.
  - CP word offset = cumulative count of CP-eligible words in story order.
"""

from __future__ import annotations

import bisect
import json
from dataclasses import dataclass
from pathlib import Path

from data_paths import DERIVED, MANUAL
from eligibility_spans import (
    section_eligible_ranges,
    section_span_overrides,
)

CHAPTERS_JSON = DERIVED / "chapters.json"
SECTIONS_JSON = DERIVED / "chapter_sections.json"
CLASSIFICATIONS_JSON = MANUAL / "section_classifications.json"


@dataclass(frozen=True)
class CpEpubMap:
    """Bidirectional CP↔EPUB word offset map.

    Internally a sorted list of disjoint, half-open EPUB intervals that
    are CP-eligible, plus a parallel prefix-sum of CP-words counted
    before each interval. Both lookups are binary search + arithmetic.
    """

    epub_starts: tuple[int, ...]
    epub_ends: tuple[int, ...]
    cp_before: tuple[int, ...]
    total_epub_words: int
    total_cp_words: int
    chapter_epub_start: dict[str, int]
    chapter_epub_end: dict[str, int]


def build_map(
    chapters_path: Path = CHAPTERS_JSON,
    sections_path: Path = SECTIONS_JSON,
    classifications_path: Path = CLASSIFICATIONS_JSON,
) -> CpEpubMap:
    chapters = sorted(
        json.loads(chapters_path.read_text())["chapters"],
        key=lambda c: tuple(c["sort_key"]),
    )
    sections_by_chapter = {
        c["chapter_num"]: c["sections"]
        for c in json.loads(sections_path.read_text())["chapters"]
    }
    cls = json.loads(classifications_path.read_text())["classifications"]

    epub_starts: list[int] = []
    epub_ends: list[int] = []
    cp_before: list[int] = []
    chapter_epub_start: dict[str, int] = {}
    chapter_epub_end: dict[str, int] = {}
    chapter_epub_cursor = 0
    cp_cursor = 0

    for chapter in chapters:
        cn = str(chapter["chapter_num"])
        chapter_epub_start[cn] = chapter_epub_cursor
        sections = sections_by_chapter.get(cn, [])
        section_local_cursor = 0
        for i, section in enumerate(sections):
            wc = int(section["word_count"])
            sec_local_start = section_local_cursor
            sec_local_end = section_local_cursor + wc
            section_local_cursor = sec_local_end
            key = f"{cn}@{i}"
            if key not in cls:
                raise SystemExit(
                    f"missing classification for {key} in {classifications_path}"
                )
            entry = cls[key]
            for start, end in section_eligible_ranges(
                section_word_start=sec_local_start,
                section_word_end=sec_local_end,
                base_counts_for_cp=bool(entry.get("counts_for_cp")),
                span_overrides=section_span_overrides(
                    entry, sec_local_start, sec_local_end,
                ),
            ):
                gs = chapter_epub_cursor + start
                ge = chapter_epub_cursor + end
                if epub_ends and epub_ends[-1] == gs:
                    epub_ends[-1] = ge
                else:
                    epub_starts.append(gs)
                    epub_ends.append(ge)
                    cp_before.append(cp_cursor)
                cp_cursor += end - start
        chapter_epub_cursor += int(chapter["total_word_count"])
        chapter_epub_end[cn] = chapter_epub_cursor

    return CpEpubMap(
        epub_starts=tuple(epub_starts),
        epub_ends=tuple(epub_ends),
        cp_before=tuple(cp_before),
        total_epub_words=chapter_epub_cursor,
        total_cp_words=cp_cursor,
        chapter_epub_start=chapter_epub_start,
        chapter_epub_end=chapter_epub_end,
    )


def epub_to_cp(m: CpEpubMap, epub_word: int) -> int:
    """Cumulative CP-eligible words up to (but not including) ``epub_word``.

    Half-open: ``epub_to_cp(0) == 0`` and
    ``epub_to_cp(m.total_epub_words) == m.total_cp_words``. Positions inside
    ineligible runs return the cumulative CP count at the start of the gap.
    """
    if epub_word <= 0:
        return 0
    if epub_word >= m.total_epub_words:
        return m.total_cp_words
    idx = bisect.bisect_right(m.epub_starts, epub_word) - 1
    if idx < 0:
        return 0
    start = m.epub_starts[idx]
    end = m.epub_ends[idx]
    if epub_word <= start:
        return m.cp_before[idx]
    return m.cp_before[idx] + min(epub_word, end) - start


def cp_to_epub(m: CpEpubMap, cp_word: int) -> int:
    """Smallest EPUB position whose ``epub_to_cp`` equals ``cp_word``.

    For ``cp_word`` exactly at an interval boundary, returns the start of
    the next eligible interval (which is the first EPUB position whose
    cumulative count reaches ``cp_word + 1`` minus one — i.e. the position
    where the (cp_word+1)th eligible word lives, minus one... see tests).
    Out-of-range ``cp_word`` clamps to the relevant end of the story.
    """
    if cp_word <= 0:
        return 0
    if cp_word >= m.total_cp_words:
        return m.total_epub_words
    idx = bisect.bisect_right(m.cp_before, cp_word) - 1
    if idx < 0:
        return 0
    return m.epub_starts[idx] + (cp_word - m.cp_before[idx])


def chapter_local_to_epub(m: CpEpubMap, chapter_num: str, local_word: int) -> int:
    """Convenience: chapter-local EPUB offset → global EPUB offset."""
    return m.chapter_epub_start[str(chapter_num)] + int(local_word)


def epub_to_chapter_local(m: CpEpubMap, epub_word: int) -> tuple[str, int]:
    """Convenience: global EPUB offset → (chapter_num, chapter-local offset).

    For boundary positions, returns the chapter whose ``[start, end)``
    contains ``epub_word``. ``epub_word == total_epub_words`` returns the
    last chapter with its full length.
    """
    if epub_word >= m.total_epub_words:
        last = max(m.chapter_epub_start, key=lambda k: m.chapter_epub_start[k])
        return last, m.total_epub_words - m.chapter_epub_start[last]
    for cn, start in m.chapter_epub_start.items():
        if start <= epub_word < m.chapter_epub_end[cn]:
            return cn, epub_word - start
    raise ValueError(f"epub_word {epub_word} outside any chapter range")
