"""Tests for section splitting and CP eligibility span accounting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from extract_chapter_sections import (  # noqa: E402
    _classify_section,
    _detect_auto_header_words,
    _split_sections,
    _text,
)


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


def test_plain_addendum_heading_splits_into_ineligible_section() -> None:
    html = (
        "<p>Joe finished the scene.</p>"
        "<p/><hr/>"
        "<p>Addendum PHO</p>"
        "<p>♦ Topic: Apeiron Medical Technology Discussion Thread</p>"
        "<p>In: Boards ► Places ► America ► Brocton Bay ► Capes</p>"
    )

    sections = _split_sections(html)

    assert [section[0] for section in sections] == [None, "Addendum PHO"]
    addendum_text = _text(html[sections[1][1]:sections[1][2]])
    addendum = _classify_section(sections[1][0], addendum_text)
    assert addendum.classification == "non_mc_other_pov"


# --- simulator: CP subtraction -------------------------------------------


def test_predict_rolls_applies_ineligible_span_overrides(tmp_path, monkeypatch):
    """`_load_cp_words_per_chapter` applies passage eligibility spans."""
    sections = {
        "_source": "test",
        "_count": 1,
        "_total_sections": 1,
        "_classification_distribution": {"mc": 1},
        "_confidence_distribution": {"high": 1},
        "_total_words": 1000,
        "_note": "test",
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "Test Chapter",
                "epub_href": "x.xhtml",
                "total_word_count": 1000,
                "sections": [
                    {
                        "header": None,
                        "word_count": 1000,
                        "classification": "mc",
                        "confidence": "high",
                        "classification_reason": "test",
                        "fp_count": 0,
                        "tp_count": 0,
                        "structural_markers": [],
                        "sample": "x",
                        "auto_header_word_count": 0,
                    }
                ],
            }
        ],
    }
    classifications = {
        "classifications": {
            "1@0": {
                "counts_for_cp": True,
                "span_overrides": [
                    {
                        "word_offset_start": 0,
                        "word_offset_end": 100,
                        "counts_for_cp": False,
                        "reason_code": "author_note",
                    }
                ],
            }
        }
    }

    sections_path = tmp_path / "chapter_sections.json"
    cls_path = tmp_path / "section_classifications.json"
    sections_path.write_text(json.dumps(sections))
    cls_path.write_text(json.dumps(classifications))

    import predict_rolls as pr  # noqa: E402

    monkeypatch.setattr(pr, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(pr, "CLASSIFICATIONS_JSON", cls_path)
    cp = pr._load_cp_words_per_chapter()
    assert cp["Test Chapter"] == 900


def test_predict_rolls_skips_non_cp_sections(tmp_path, monkeypatch):
    """Sections marked counts_for_cp=False via manual classifications
    are excluded entirely.
    """
    sections = {
        "_source": "t", "_count": 1, "_total_sections": 2,
        "_classification_distribution": {"mc": 1, "non_mc_other_pov": 1},
        "_confidence_distribution": {"high": 2},
        "_total_words": 1500,
        "_note": "test",
        "chapters": [
            {
                "chapter_num": "1",
                "full_title": "Test Chapter",
                "epub_href": "x.xhtml",
                "total_word_count": 1500,
                "sections": [
                    {
                        "header": None, "word_count": 1000,
                        "classification": "mc",
                        "confidence": "high", "classification_reason": "t",
                        "fp_count": 0, "tp_count": 0,
                        "structural_markers": [], "sample": "",
                        "auto_header_word_count": 0,
                    },
                    {
                        "header": "Interlude X", "word_count": 500,
                        "classification": "non_mc_other_pov",
                        "confidence": "high", "classification_reason": "t",
                        "fp_count": 0, "tp_count": 0,
                        "structural_markers": [], "sample": "",
                        "auto_header_word_count": 0,
                    },
                ],
            }
        ],
    }
    classifications = {
        "classifications": {
            "1@0": {"counts_for_cp": True},
            "1@1": {"counts_for_cp": False},
        }
    }

    sections_path = tmp_path / "chapter_sections.json"
    cls_path = tmp_path / "section_classifications.json"
    sections_path.write_text(json.dumps(sections))
    cls_path.write_text(json.dumps(classifications))

    import predict_rolls as pr  # noqa: E402

    monkeypatch.setattr(pr, "SECTIONS_JSON", sections_path)
    monkeypatch.setattr(pr, "CLASSIFICATIONS_JSON", cls_path)
    cp = pr._load_cp_words_per_chapter()
    assert cp["Test Chapter"] == 1000
