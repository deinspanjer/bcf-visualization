"""Tests for nlp.candidates — candidate passage selection.

Uses tmpdir-based fixture data so no real derived files are needed.
Requires only stdlib + pydantic.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from nlp.candidates import Candidate, iter_candidates


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_chapter_sections(tmp_path: Path, chapters: list[dict]) -> Path:
    data = {
        "_source": "test fixture",
        "_count": len(chapters),
        "_total_sections": sum(len(c["sections"]) for c in chapters),
        "_classification_distribution": {"mc": 1},
        "_confidence_distribution": {"high": 1},
        "_total_words": 10000,
        "_cp_earning_words": 8000,
        "_note": "test",
        "chapters": chapters,
    }
    p = tmp_path / "chapter_sections.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_predicted_rolls(tmp_path: Path, rolls: list[dict]) -> Path:
    data = {
        "_source": "test fixture",
        "_count": len(rolls),
        "_total_words_epub_exact": 100000,
        "_regime_summary": {},
        "_validation_chapters_1_75": {},
        "predicted": rolls,
        "comparison_per_chapter": {},
    }
    p = tmp_path / "predicted_rolls.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _make_regex_locations(tmp_path: Path, locations: list[dict]) -> Path:
    data = {
        "_source": "test fixture",
        "_nuance_log": [],
        "_total_locations": len(locations),
        "_total_events": len(locations),
        "_locations_by_chapter": {},
        "_locations_by_kind": {},
        "_events_by_chapter": {},
        "_events_by_anchor_kind": {},
        "_note": "test",
        "locations": locations,
        "events": [],
    }
    p = tmp_path / "roll_locations_regex.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _simple_fixture(tmp_path: Path) -> Path:
    """Build a minimal derived_dir with 2 chapters and a few events."""
    chapters = [
        {
            "chapter_num": "1",
            "full_title": "Chapter 1",
            "epub_href": "chap_1.xhtml",
            "total_word_count": 500,
            "cp_earning_word_count": 400,
            "sections": [
                {
                    "header": None,
                    "word_count": 400,
                    "counts_for_cp": True,
                    "classification": "mc",
                    "confidence": "high",
                    "classification_reason": "test",
                    "fp_count": 5,
                    "tp_count": 0,
                    "structural_markers": [],
                    "sample": "Joe felt the wheel spin. It landed on Perfect Pitch.",
                }
            ],
        },
        {
            "chapter_num": "2",
            "full_title": "Chapter 2",
            "epub_href": "chap_2.xhtml",
            "total_word_count": 600,
            "cp_earning_word_count": 500,
            "sections": [
                {
                    "header": None,
                    "word_count": 500,
                    "counts_for_cp": True,
                    "classification": "mc",
                    "confidence": "high",
                    "classification_reason": "test",
                    "fp_count": 3,
                    "tp_count": 0,
                    "structural_markers": [],
                    "sample": "The next day Joe tried again. He missed.",
                }
            ],
        },
    ]

    rolls = [
        {"roll_number": 1, "word_position": 100, "chapter_num": "1", "regime": 1, "cp_threshold": 100},
        {"roll_number": 2, "word_position": 200, "chapter_num": "2", "regime": 1, "cp_threshold": 100},
        {"roll_number": 3, "word_position": 300, "chapter_num": "1", "regime": 1, "cp_threshold": 100},
    ]

    locations = [
        {
            "chapter_num": "1",
            "epub_href": "chap_1.xhtml",
            "section_index": 0,
            "match_phrase": "spin",
            "match_offset": 50,
            "context": "Joe felt the wheel spin and stop.",
            "candidate_kind": "roll_attempt",
        },
        {
            "chapter_num": "2",
            "epub_href": "chap_2.xhtml",
            "section_index": 0,
            "match_phrase": "missed",
            "match_offset": 80,
            "context": "He missed again, the wheel empty.",
            "candidate_kind": "miss",
        },
    ]

    _make_chapter_sections(tmp_path, chapters)
    _make_predicted_rolls(tmp_path, rolls)
    _make_regex_locations(tmp_path, locations)
    return tmp_path


# ---------------------------------------------------------------------------
# Tests: event_focused strategy
# ---------------------------------------------------------------------------


class TestEventFocused:
    def test_produces_candidates(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            seed=1337,
        ))
        assert len(candidates) > 0

    def test_candidate_fields(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            seed=1337,
        ))
        for c in candidates:
            assert isinstance(c, Candidate)
            assert c.passage_id.startswith("ch")
            assert c.chapter_num in ("1", "2")
            assert isinstance(c.section_index, int) and c.section_index >= 0
            assert isinstance(c.epub_char_start, int)
            assert isinstance(c.epub_char_end, int)
            assert isinstance(c.text, str) and len(c.text) > 0
            assert c.source in ("predicted_roll", "regex_anchor", "section_first_chars")

    def test_limit_respected(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        for limit in (1, 2, 3):
            candidates = list(iter_candidates(
                strategy="event_focused",
                derived_dir=derived,
                seed=1337,
                limit=limit,
            ))
            assert len(candidates) <= limit

    def test_limit_1_returns_exactly_1(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            seed=1337,
            limit=1,
        ))
        assert len(candidates) == 1

    def test_stable_passage_ids_same_seed(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        run_a = [c.passage_id for c in iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=42, limit=5
        )]
        run_b = [c.passage_id for c in iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=42, limit=5
        )]
        assert run_a == run_b

    def test_different_seed_may_differ(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        run_a = [c.passage_id for c in iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=1, limit=5
        )]
        run_b = [c.passage_id for c in iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=999, limit=5
        )]
        # With different seeds the order may differ (not guaranteed to differ
        # with tiny fixture, but the API must at least not crash)
        assert len(run_a) == len(run_b)

    def test_no_duplicate_passage_ids(self, tmp_path: Path) -> None:
        """passage_id counter must be per-chapter so ids are unique."""
        derived = _simple_fixture(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=1337
        ))
        ids = [c.passage_id for c in candidates]
        assert len(ids) == len(set(ids)), f"Duplicate passage ids: {ids}"

    def test_passage_ids_follow_convention(self, tmp_path: Path) -> None:
        """passage_id should match ch<chapter_num>_p<index> pattern."""
        import re
        derived = _simple_fixture(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused", derived_dir=derived, seed=1337, limit=6
        ))
        pattern = re.compile(r"^ch[\d.]+_p\d+$")
        for c in candidates:
            assert pattern.match(c.passage_id), f"Bad passage_id: {c.passage_id!r}"


# ---------------------------------------------------------------------------
# Tests: EPUB-missing fallback
# ---------------------------------------------------------------------------


class TestEpubMissingFallback:
    def test_fallback_to_first_chars_when_epub_missing(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        missing_epub = tmp_path / "nonexistent.epub"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            candidates = list(iter_candidates(
                strategy="event_focused",
                derived_dir=derived,
                epub_path=missing_epub,
                seed=1337,
            ))

        # Should warn about missing EPUB
        warning_texts = [str(warning.message) for warning in w]
        assert any("EPUB" in t or "epub" in t.lower() for t in warning_texts), \
            f"Expected EPUB warning, got: {warning_texts}"

        # Should still produce candidates
        assert len(candidates) > 0

    def test_fallback_source_is_section_first_chars(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        missing_epub = tmp_path / "nonexistent.epub"

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            candidates = list(iter_candidates(
                strategy="event_focused",
                derived_dir=derived,
                epub_path=missing_epub,
                seed=1337,
            ))

        # All sources must be the fallback sentinel
        for c in candidates:
            assert c.source == "section_first_chars", \
                f"Expected source='section_first_chars', got {c.source!r} for {c.passage_id}"

    def test_no_epub_arg_does_not_warn(self, tmp_path: Path) -> None:
        """Passing epub_path=None (not missing, just absent) should not warn."""
        derived = _simple_fixture(tmp_path)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            candidates = list(iter_candidates(
                strategy="event_focused",
                derived_dir=derived,
                epub_path=None,
                seed=1337,
            ))

        epub_warnings = [str(warning.message) for warning in w if "EPUB" in str(warning.message)]
        # No EPUB-missing warning expected
        assert not epub_warnings, f"Unexpected EPUB warning: {epub_warnings}"

        # Still should produce candidates
        assert len(candidates) > 0


# ---------------------------------------------------------------------------
# Tests: unimplemented strategies
# ---------------------------------------------------------------------------


class TestUnimplementedStrategies:
    @pytest.mark.parametrize("strategy", ["balanced", "low_confidence", "coverage_gap"])
    def test_raises_not_implemented(self, tmp_path: Path, strategy: str) -> None:
        derived = _simple_fixture(tmp_path)
        with pytest.raises(NotImplementedError, match="phase 2/3"):
            list(iter_candidates(strategy=strategy, derived_dir=derived))

    def test_unknown_strategy_raises_value_error(self, tmp_path: Path) -> None:
        derived = _simple_fixture(tmp_path)
        with pytest.raises(ValueError, match="Unknown strategy"):
            list(iter_candidates(strategy="bogus_strategy", derived_dir=derived))
