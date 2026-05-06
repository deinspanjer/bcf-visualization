"""Enrich chapter_sections.json with author_note_ranges fields.

When the source EPUB is unavailable, the canonical
`extract_chapter_sections.py` cannot run end-to-end. This helper
performs an in-place enrichment using only the per-section `sample`
field (the first 600 chars of section text) so the simulator gets at
least the leading-section AN ranges (which is where ~all observed ANs
sit, e.g. the chapter 93 split-notice AN).

Limitations:
  - ANs that begin past offset 600 inside a section are not detected.
  - When the EPUB is available, prefer running
    `python scripts/extract_chapter_sections.py` instead, which scans
    the full section text.

Output: data/derived/chapter_sections.json (in place), with each section
gaining `author_note_ranges` and `author_note_word_count`. Per-chapter
`cp_earning_word_count` and the top-level `_cp_earning_words` are
recomputed to subtract AN words from MC sections.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _common import write_validated_json
from extract_chapter_sections import find_author_note_ranges, _word_count

SECTIONS_JSON = ROOT / "data" / "derived" / "chapter_sections.json"


def main() -> None:
    data = json.loads(SECTIONS_JSON.read_text())

    total_an_sections = 0
    total_an_words = 0
    new_total_words = 0
    new_cp_words = 0

    for chap in data["chapters"]:
        cp_words = 0
        total_words = 0
        for section in chap["sections"]:
            sample = section.get("sample", "")
            ranges = find_author_note_ranges(sample)
            an_words = sum(_word_count(sample[s:e]) for s, e in ranges)
            section["author_note_ranges"] = [list(r) for r in ranges]
            section["author_note_word_count"] = an_words
            total_words += section["word_count"]
            if section["counts_for_cp"]:
                cp_words += section["word_count"] - an_words
            if ranges:
                total_an_sections += 1
                total_an_words += an_words
        chap["total_word_count"] = total_words
        chap["cp_earning_word_count"] = cp_words
        new_total_words += total_words
        new_cp_words += cp_words

    data["_total_words"] = new_total_words
    data["_cp_earning_words"] = new_cp_words

    write_validated_json(SECTIONS_JSON, data, "chapter_sections")

    print(f"enriched {SECTIONS_JSON.relative_to(ROOT)}: "
          f"{total_an_sections} sections with author-note ranges, "
          f"{total_an_words:,} AN words total")
    print(f"  cp_earning_words: {new_cp_words:,} (was previously inflated by AN words)")


if __name__ == "__main__":
    main()
