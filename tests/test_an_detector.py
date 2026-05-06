"""Tests for the author-note (AN) detector and the simulator's CP
subtraction. The detector lives in scripts/extract_chapter_sections.py
and is consumed by scripts/predict_rolls.py via the
`author_note_word_count` field on each section.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from extract_chapter_sections import find_author_note_ranges, _word_count


# --- regex detector -------------------------------------------------------


def test_detects_authors_note_basic():
    text = "Joe walked. (Author's note: chapter split next week.) He kept walking."
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert text[s] == "("
    assert text[e - 1] == ")"
    assert "Author's note" in text[s:e]


def test_detects_a_slash_n():
    text = "Some prose. (A/N: a quick aside.) More prose."
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert text[s:e] == "(A/N: a quick aside.)"


def test_detects_note_from_named_author():
    text = "Beginning. (Note from LordRoustabout: thanks!) End."
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert "LordRoustabout" in text[s:e]


def test_handles_nested_parens():
    text = "(Author's note: see (the previous arc) for context.) Next sentence."
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    # Range must extend through the OUTER closing paren, past the
    # nested (the previous arc) clause.
    assert text[s:e].endswith("for context.)")


def test_handles_multiline_an():
    text = (
        "Story prose.\n"
        "(Author's note: line one\n"
        "line two\n"
        "line three.)\n"
        "More prose."
    )
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    assert "line three" in text[s:e]


def test_does_not_match_in_character_parenthetical():
    # Joe-style aside; not author-voiced. Should not match.
    text = "Joe paused (he was tired) and then continued. (Naturally, he sighed.)"
    ranges = find_author_note_ranges(text)
    assert ranges == []


def test_detects_multiple_separate_ans():
    text = (
        "(Author's note: first aside.) Some prose. "
        "(A/N: second aside.) Closing prose."
    )
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 2
    assert "first aside" in text[ranges[0][0]:ranges[0][1]]
    assert "second aside" in text[ranges[1][0]:ranges[1][1]]


def test_chapter_93_style_an():
    """Mirrors the actual chapter-93 leading author note."""
    text = (
        "93 Loom and Thread 93 Loom and Thread "
        "(Author's note: A last minute situation prevented me from closing "
        "out the chapter like I had planned. I needed to split the chapter "
        "in two and will be wrapping things up next week. )"
    )
    ranges = find_author_note_ranges(text)
    assert len(ranges) == 1
    s, e = ranges[0]
    an = text[s:e]
    assert an.startswith("(Author's note:")
    assert an.endswith(")")
    # The author-note word count should be >0 and account for almost
    # all the section's words (the section is essentially the AN).
    assert _word_count(an) > 30


# --- simulator: CP subtraction --------------------------------------------


def test_predict_rolls_subtracts_an_words(tmp_path, monkeypatch):
    """Build a tiny synthetic chapter_sections.json and confirm the
    simulator's `_load_cp_words_per_chapter` subtracts AN words for
    CP-eligible sections.
    """
    # Stage tmp inputs
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
    # Point labeled-spans dir somewhere empty to skip that path
    monkeypatch.setattr(pr, "LABELED_SPANS_DIR", tmp_path / "no_such_dir")

    cp = pr._load_cp_words_per_chapter()
    # 1000 total - 100 AN = 900 CP-eligible
    assert cp["Test Chapter"] == 900


def test_predict_rolls_subtracts_labeled_an_spans(tmp_path, monkeypatch):
    """Confirm AUTHOR_NOTE-labeled spans from data/labeled/spans are
    also subtracted, on top of the regex-detected count.
    """
    sections = {
        "_source": "test", "_count": 1, "_total_sections": 1,
        "_classification_distribution": {"mc": 1},
        "_confidence_distribution": {"high": 1},
        "_total_words": 500, "_cp_earning_words": 500,
        "_note": "test",
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "Test Chapter",
                "epub_href": "x.xhtml",
                "total_word_count": 500,
                "cp_earning_word_count": 500,
                "sections": [
                    {
                        "header": None, "word_count": 500,
                        "counts_for_cp": True, "classification": "mc",
                        "confidence": "high", "classification_reason": "t",
                        "fp_count": 0, "tp_count": 0,
                        "structural_markers": [], "sample": "",
                        "author_note_ranges": [], "author_note_word_count": 0,
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

    spans_dir = tmp_path / "spans"
    spans_dir.mkdir()
    (spans_dir / "pilot.jsonl").write_text(json.dumps({
        "passage_id": "ch1_p0",
        "chapter_num": "1",
        "section_index": 0,
        "epub_char_start": 0,
        "epub_char_end": 100,
        "text": "one two three four five six seven eight nine ten",
        "spans": [
            {"layer": "B", "label": "AUTHOR_NOTE", "start": 0, "end": 23}
            # "one two three four five" -> 5 words
        ],
        "source": "manual",
        "annotator": "tester",
        "annotated_at": "2026-05-06T00:00:00Z",
        "schema_version": 1,
    }) + "\n")

    import predict_rolls as pr  # noqa: E402

    monkeypatch.setattr(pr, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(pr, "CLASSIFICATIONS_JSON", cls_path)
    monkeypatch.setattr(pr, "LABELED_SPANS_DIR", spans_dir)

    cp = pr._load_cp_words_per_chapter()
    # 500 total - 0 regex AN - 5 labeled AN = 495
    assert cp["Test Chapter"] == 495
