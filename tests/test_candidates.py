"""Tests for nlp.candidates — candidate passage selection.

Uses tmpdir-based fixture data so no real derived files are needed.
Requires only stdlib + pydantic.
"""

from __future__ import annotations

import io
import json
import warnings
import zipfile
from pathlib import Path

import pytest

from nlp.candidates import Candidate, iter_candidates


def _make_fake_epub(
    tmp_path: Path,
    text_length: int = 5000,
    chapter_hrefs: tuple[str, ...] = ("chap_1.xhtml", "chap_2.xhtml", "chap_5.xhtml"),
) -> Path:
    """Create a minimal valid EPUB zip with per-chapter xhtml files and a whole-EPUB
    fallback file.

    Each chapter file lives at ``EPUB/<href>`` so that
    ``_read_chapter_html_raw`` can locate it.  The text is spaces/letters long enough to cover all
    ``predicted_char_offsets`` used in the test fixture data.
    """
    # Build a text body long enough to cover all predicted_char_offsets in the fixture
    body_text = ("A" * 80 + "\n") * (text_length // 81 + 1)
    xhtml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<html><body><p>" + body_text + "</p></body></html>"
    )
    epub_path = tmp_path / "fake.epub"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Whole-EPUB fallback used by regex_anchor path
        zf.writestr("OEBPS/content.xhtml", xhtml)
        # Per-chapter files used by the predicted_roll path
        for href in chapter_hrefs:
            zf.writestr(f"EPUB/{href}", xhtml)
    epub_path.write_bytes(buf.getvalue())
    return epub_path


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


def _make_roll_resolutions(tmp_path: Path, rolls: list[dict]) -> Path:
    data = {
        "schema_version": "1.0",
        "generated_from": "test fixture",
        "rolls": rolls,
    }
    p = tmp_path / "roll_resolutions.json"
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

    # roll_resolutions.json drives Source 1; predicted_rolls.json is present
    # because the derived directory fixture mirrors the real data bundle.
    roll_resolution_entries = [
        {
            "roll_number": 1,
            "chapter_num": "1",
            "section_index": 0,
            "predicted_word_position_epub": 100,
            "predicted_char_offset": 500,
            "anchor_string": "Joe felt the wheel spin",
            "banked_at_roll": 100,
            "banked_at_roll_source": "curator",
            "curator_chapter_num": "1",
            "chapter_attribution_disagreement": False,
            "curator_outcome": "HIT",
            "curator_perk_name": "Perfect Pitch",
            "curator_constellation": "Toolkits",
            "curator_cost": 100,
            "curator_free_associated_perks": ["Access Key"],
            "curator_banked_before": 100,
            "curator_banked_after": 0,
            "chapter_acquired_perks_in_order": [
                {"name": "Perfect Pitch", "constellation": "Toolkits", "cost": 100, "free": False}
            ],
            "outstanding_perks_with_cost_gt_banked": [
                {"name": "Big Perk", "cost": 800, "constellation": "Knowledge"}
            ],
            "constellations_known_by_joe": ["Toolkits"],
        },
        {
            "roll_number": 2,
            "chapter_num": "2",
            "section_index": 0,
            "predicted_word_position_epub": 200,
            "predicted_char_offset": 1000,
            "anchor_string": "The next day Joe tried again",
            "banked_at_roll": 200,
            "banked_at_roll_source": "predicted",
            "curator_chapter_num": "2",
            "chapter_attribution_disagreement": False,
            "curator_outcome": "MISS",
            "curator_perk_name": None,
            "curator_constellation": None,
            "curator_cost": None,
            "curator_free_associated_perks": None,
            "curator_banked_before": 200,
            "curator_banked_after": 200,
            "chapter_acquired_perks_in_order": [],
            "outstanding_perks_with_cost_gt_banked": [],
            "constellations_known_by_joe": [],
        },
        {
            "roll_number": 3,
            "chapter_num": "1",
            "section_index": 0,
            "predicted_word_position_epub": 300,
            "predicted_char_offset": 1500,
            "anchor_string": "He tried a third time",
            "banked_at_roll": 150,
            "banked_at_roll_source": "predicted",
            "curator_chapter_num": None,
            "chapter_attribution_disagreement": False,
            "curator_outcome": None,
            "curator_perk_name": None,
            "curator_constellation": None,
            "curator_cost": None,
            "curator_free_associated_perks": None,
            "curator_banked_before": 150,
            "curator_banked_after": 150,
            "chapter_acquired_perks_in_order": [],
            "outstanding_perks_with_cost_gt_banked": [],
            "constellations_known_by_joe": [],
        },
    ]
    rolls = [
        {
            "roll_number": 1,
            "word_position": 100,
            "chapter_num": "1",
            "cp_rule_regime": 1,
            "roll_trigger_cp_threshold": 100,
        },
        {
            "roll_number": 2,
            "word_position": 200,
            "chapter_num": "2",
            "cp_rule_regime": 1,
            "roll_trigger_cp_threshold": 100,
        },
        {
            "roll_number": 3,
            "word_position": 300,
            "chapter_num": "1",
            "cp_rule_regime": 1,
            "roll_trigger_cp_threshold": 100,
        },
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
    _make_roll_resolutions(tmp_path, roll_resolution_entries)
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


# ---------------------------------------------------------------------------
# Tests: roll_resolutions-driven roll_context attachment
# ---------------------------------------------------------------------------


class TestRollContextAttachment:
    """Verify that predicted_roll candidates carry roll_context from
    roll_resolutions.json and that the context dict has the expected keys."""

    _EXPECTED_KEYS = {
        "roll_number",
        "chapter_num",
        "section_index",
        "predicted_char_offset",
        "anchor_string",
        "banked_at_roll",
        "banked_at_roll_source",
        "curator_chapter_num",
        "chapter_attribution_disagreement",
        "curator_outcome",
        "curator_perk_name",
        "curator_constellation",
        "curator_cost",
        "curator_free_associated_perks",
        "chapter_acquired_perks_in_order",
        "outstanding_perks_with_cost_gt_banked",
        "constellations_known_by_joe",
    }

    def test_predicted_roll_candidates_have_roll_context(self, tmp_path: Path) -> None:
        """Candidates from the predicted_roll source must have a non-None roll_context."""
        derived = _simple_fixture(tmp_path)
        epub = _make_fake_epub(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            epub_path=epub,
            seed=1337,
        ))
        roll_candidates = [c for c in candidates if c.source == "predicted_roll"]
        assert roll_candidates, "Expected at least one predicted_roll candidate"
        for c in roll_candidates:
            assert c.roll_context is not None, (
                f"Expected roll_context on predicted_roll candidate {c.passage_id}"
            )

    def test_roll_context_has_expected_keys(self, tmp_path: Path) -> None:
        """roll_context must contain all required keys."""
        derived = _simple_fixture(tmp_path)
        epub = _make_fake_epub(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            epub_path=epub,
            seed=1337,
        ))
        roll_candidates = [c for c in candidates if c.source == "predicted_roll"]
        assert roll_candidates
        for c in roll_candidates:
            ctx = c.roll_context
            assert ctx is not None
            missing = self._EXPECTED_KEYS - set(ctx.keys())
            assert not missing, (
                f"roll_context for {c.passage_id} missing keys: {missing}"
            )

    def test_roll_context_hit_fields_populated(self, tmp_path: Path) -> None:
        """For the HIT roll (roll_number=1, ch1), curator fields must be set."""
        derived = _simple_fixture(tmp_path)
        epub = _make_fake_epub(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            epub_path=epub,
            seed=1337,
        ))
        hit_candidates = [
            c for c in candidates
            if c.source == "predicted_roll"
            and c.roll_context is not None
            and c.roll_context.get("curator_outcome") == "HIT"
        ]
        assert hit_candidates, "Expected at least one HIT roll candidate"
        c = hit_candidates[0]
        ctx = c.roll_context
        assert ctx["curator_perk_name"] == "Perfect Pitch"
        assert ctx["curator_constellation"] == "Toolkits"
        assert ctx["anchor_string"] == "Joe felt the wheel spin"

    def test_regex_anchor_candidates_have_no_roll_context(self, tmp_path: Path) -> None:
        """Regex anchor candidates must have roll_context=None."""
        derived = _simple_fixture(tmp_path)
        epub = _make_fake_epub(tmp_path)
        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=derived,
            epub_path=epub,
            seed=1337,
        ))
        regex_candidates = [c for c in candidates if c.source == "regex_anchor"]
        assert regex_candidates, "Expected at least one regex_anchor candidate"
        for c in regex_candidates:
            assert c.roll_context is None, (
                f"Expected roll_context=None for regex_anchor {c.passage_id}, "
                f"got {c.roll_context!r}"
            )

    def test_outstanding_perks_truncated_to_top5(self, tmp_path: Path) -> None:
        """outstanding_perks_with_cost_gt_banked in roll_context must have at most 5 entries."""
        # Build a fixture roll with more than 5 outstanding perks
        chapters = [
            {
                "chapter_num": "5",
                "full_title": "Chapter 5",
                "epub_href": "chap_5.xhtml",
                "total_word_count": 1000,
                "cp_earning_word_count": 800,
                "sections": [
                    {
                        "header": None,
                        "word_count": 800,
                        "counts_for_cp": True,
                        "classification": "mc",
                        "confidence": "high",
                        "classification_reason": "test",
                        "fp_count": 5,
                        "tp_count": 0,
                        "structural_markers": [],
                        "sample": "Long chapter with many possibilities.",
                    }
                ],
            }
        ]
        many_outstanding = [
            {"name": f"Perk {i}", "cost": (i + 1) * 100, "constellation": "Knowledge"}
            for i in range(10)
        ]
        resolution_entries = [
            {
                "roll_number": 99,
                "chapter_num": "5",
                "section_index": 0,
                "predicted_word_position_epub": 500,
                "predicted_char_offset": 100,
                "anchor_string": "some anchor",
                "banked_at_roll": 50,
                "banked_at_roll_source": "predicted",
                "curator_chapter_num": None,
                "chapter_attribution_disagreement": False,
                "curator_outcome": None,
                "curator_perk_name": None,
                "curator_constellation": None,
                "curator_cost": None,
                "curator_free_associated_perks": None,
                "curator_banked_before": 50,
                "curator_banked_after": 50,
                "chapter_acquired_perks_in_order": [],
                "outstanding_perks_with_cost_gt_banked": many_outstanding,
                "constellations_known_by_joe": [],
            }
        ]
        _make_chapter_sections(tmp_path, chapters)
        _make_predicted_rolls(tmp_path, [])  # empty — not used by new code
        _make_roll_resolutions(tmp_path, resolution_entries)
        _make_regex_locations(tmp_path, [])
        epub = _make_fake_epub(tmp_path, text_length=10000)

        candidates = list(iter_candidates(
            strategy="event_focused",
            derived_dir=tmp_path,
            epub_path=epub,
            seed=1337,
        ))
        roll_candidates = [c for c in candidates if c.source == "predicted_roll"]
        assert roll_candidates
        ctx = roll_candidates[0].roll_context
        assert ctx is not None
        outstanding = ctx["outstanding_perks_with_cost_gt_banked"]
        assert len(outstanding) <= 5, (
            f"Expected at most 5 outstanding perks, got {len(outstanding)}"
        )
