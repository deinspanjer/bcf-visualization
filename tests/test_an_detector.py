"""Tests for the curated author-note pipeline.

The single source of truth is `data/manual/author_notes.json`. The
extractor (`scripts/extract_chapter_sections.py`) loads that file and
locates each AN's verbatim text in the source section, then writes the
char ranges and word count onto each section. The simulator
(`scripts/predict_rolls.py`) subtracts that word count from each
CP-eligible section. There is no detection, no regex, no fallback —
edits to the AN list happen by editing the manual file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from extract_chapter_sections import (  # noqa: E402
    _classify_section,
    _detect_auto_header_words,
    _split_sections,
    _text,
    _resolve_author_note_ranges,
    _word_count,
    _words_in_ranges,
)


# --- AN range resolution --------------------------------------------------


def test_resolve_an_locates_verbatim_string():
    text = "Joe walked. (Author's note: chapter split next week.) He kept walking."
    an = "(Author's note: chapter split next week.)"
    ranges = _resolve_author_note_ranges(text, [an], "test", 0)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert text[s:e] == an


def test_resolve_an_handles_multiple_in_section():
    text = "(Author's note: first.) Some prose. (Author's note: second.) End."
    ans = ["(Author's note: first.)", "(Author's note: second.)"]
    ranges = _resolve_author_note_ranges(text, ans, "test", 0)
    assert len(ranges) == 2
    # Returned sorted by offset
    assert ranges[0][0] < ranges[1][0]
    assert text[ranges[0][0]:ranges[0][1]] == ans[0]
    assert text[ranges[1][0]:ranges[1][1]] == ans[1]


def test_resolve_an_handles_multiline_verbatim():
    text = (
        "Story prose.\n"
        "(Author's note: line one\n"
        "line two\n"
        "line three.)\n"
        "More prose."
    )
    an = "(Author's note: line one\nline two\nline three.)"
    ranges = _resolve_author_note_ranges(text, [an], "test", 0)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert text[s:e] == an


def test_resolve_an_empty_when_no_curated_entries():
    text = "Just narration, no curated AN here."
    ranges = _resolve_author_note_ranges(text, [], "test", 0)
    assert ranges == []


def test_resolve_an_raises_when_curated_text_drifted():
    text = "Section text without the curated AN string anywhere inside."
    with pytest.raises(SystemExit, match="not found in source text"):
        _resolve_author_note_ranges(
            text,
            ["(Author's note: this exact string is not in the section)"],
            "42",
            0,
        )


def test_words_in_ranges_counts_via_substring():
    text = "alpha beta (Author's note: gamma delta epsilon.) zeta."
    an = "(Author's note: gamma delta epsilon.)"
    ranges = _resolve_author_note_ranges(text, [an], "test", 0)
    # 4 words including the parenthesized prefix
    assert _words_in_ranges(text, ranges) == _word_count(an)


# --- header / markup exclusion -------------------------------------------


def test_strip_skips_head_title_markup() -> None:
    html = (
        "<html><head><title>2 Preparation</title></head>"
        "<body><h2>2 Preparation</h2><p>My watch beeped.</p></body></html>"
    )
    assert _text(html).split() == ["2", "Preparation", "My", "watch", "beeped."]


def test_implicit_repeated_chapter_title_words_are_auto_header() -> None:
    text = "2 Preparation\n\n2 Preparation\n\nMy watch alarm began to chime."
    assert _detect_auto_header_words(text, None, implicit_header="2 Preparation") == 4


def test_plain_jumpchain_footer_splits_into_ineligible_section() -> None:
    html = (
        "<p>Story body.</p>"
        "<p>Jumpchain abilities this chapter:</p>"
        "<p>Useful Perk (Example) 100:</p>"
        "<p>Perk text.</p>"
    )

    sections = _split_sections(html)

    assert [section[0] for section in sections] == [
        None,
        "Jumpchain abilities this chapter:",
    ]
    footer_text = _text(html[sections[1][1]:sections[1][2]])
    footer = _classify_section(sections[1][0], footer_text)
    assert footer.classification == "non_mc_meta"
    assert footer.counts_for_cp is False


# --- simulator: CP subtraction -------------------------------------------


def test_predict_rolls_subtracts_an_words(tmp_path, monkeypatch):
    """`_load_cp_words_per_chapter` subtracts each section's
    `author_note_word_count` from CP-eligible sections.
    """
    sections = {
        "_source": "test",
        "_count": 1,
        "_total_sections": 1,
        "_classification_distribution": {"mc": 1},
        "_confidence_distribution": {"high": 1},
        "_total_words": 1000,
        "_cp_earning_words": 900,
        "_note": "test",
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "Test Chapter",
                "epub_href": "x.xhtml",
                "total_word_count": 1000,
                "cp_earning_word_count": 900,
                # Canonical exclusion ranges: a 100-word AN at the start
                # of the chapter (chapter-local word offsets 0..100).
                "excluded_word_ranges": [[0, 100]],
                "sections": [
                    {
                        "header": None,
                        "word_count": 1000,
                        "counts_for_cp": True,
                        "classification": "mc",
                        "confidence": "high",
                        "classification_reason": "test",
                        "fp_count": 0,
                        "tp_count": 0,
                        "structural_markers": [],
                        "sample": "x",
                        "author_note_ranges": [[0, 50]],
                        "author_note_word_count": 100,
                    }
                ],
            }
        ],
    }
    classifications = {"classifications": {}}

    sections_path = tmp_path / "chapter_sections.json"
    cls_path = tmp_path / "section_classifications.json"
    sections_path.write_text(json.dumps(sections))
    cls_path.write_text(json.dumps(classifications))

    import predict_rolls as pr  # noqa: E402

    monkeypatch.setattr(pr, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(pr, "CLASSIFICATIONS_JSON", cls_path)
    # Isolate the test from any real header_corrections.json on disk.
    empty_hdr = tmp_path / "header_corrections.json"
    empty_hdr.write_text(json.dumps({"corrections": []}))
    monkeypatch.setattr(pr, "_HEADER_CORRECTIONS_JSON", empty_hdr)

    cp = pr._load_cp_words_per_chapter()
    assert cp["Test Chapter"] == 900


def test_predict_rolls_skips_non_cp_sections(tmp_path, monkeypatch):
    """Sections marked counts_for_cp=False via the manual classifications
    map are excluded entirely (their AN-subtracted word count doesn't
    contribute), regardless of `author_note_word_count`.
    """
    sections = {
        "_source": "t", "_count": 1, "_total_sections": 2,
        "_classification_distribution": {"mc": 1, "non_mc_other_pov": 1},
        "_confidence_distribution": {"high": 2},
        "_total_words": 1500, "_cp_earning_words": 1000,
        "_note": "test",
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "Test Chapter",
                "epub_href": "x.xhtml",
                "total_word_count": 1500,
                "cp_earning_word_count": 1000,
                "sections": [
                    {
                        "header": None, "word_count": 1000,
                        "counts_for_cp": True, "classification": "mc",
                        "confidence": "high", "classification_reason": "t",
                        "fp_count": 0, "tp_count": 0,
                        "structural_markers": [], "sample": "",
                        "author_note_ranges": [], "author_note_word_count": 0,
                    },
                    {
                        "header": "Interlude X", "word_count": 500,
                        "counts_for_cp": False,
                        "classification": "non_mc_other_pov",
                        "confidence": "high", "classification_reason": "t",
                        "fp_count": 0, "tp_count": 0,
                        "structural_markers": [], "sample": "",
                        "author_note_ranges": [], "author_note_word_count": 0,
                    },
                ],
            }
        ],
    }
    # Override section 1 to be excluded via the manual map
    classifications = {"classifications": {"1@1": {"counts_for_cp": False}}}

    sections_path = tmp_path / "chapter_sections.json"
    cls_path = tmp_path / "section_classifications.json"
    sections_path.write_text(json.dumps(sections))
    cls_path.write_text(json.dumps(classifications))

    import predict_rolls as pr  # noqa: E402

    monkeypatch.setattr(pr, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(pr, "CLASSIFICATIONS_JSON", cls_path)
    # Isolate the test from any real header_corrections.json on disk.
    empty_hdr = tmp_path / "header_corrections.json"
    empty_hdr.write_text(json.dumps({"corrections": []}))
    monkeypatch.setattr(pr, "_HEADER_CORRECTIONS_JSON", empty_hdr)

    cp = pr._load_cp_words_per_chapter()
    assert cp["Test Chapter"] == 1000
