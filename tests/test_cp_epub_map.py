"""Round-trip + invariant tests for the canonical CP↔EPUB map."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cp_epub_map import (  # noqa: E402
    CpEpubMap,
    build_map,
    chapter_local_to_epub,
    cp_to_epub,
    epub_to_chapter_local,
    epub_to_cp,
)
from eligibility_spans import section_eligible_ranges  # noqa: E402


@pytest.fixture(scope="module")
def m() -> CpEpubMap:
    return build_map()


# ---------- unit tests on section_eligible_ranges ---------------------------


def test_section_eligible_ranges_base_eligible_no_overrides():
    assert section_eligible_ranges(
        section_word_start=0, section_word_end=100,
        base_counts_for_cp=True, span_overrides=[],
    ) == [(0, 100)]


def test_section_eligible_ranges_base_ineligible_no_overrides():
    assert section_eligible_ranges(
        section_word_start=0, section_word_end=100,
        base_counts_for_cp=False, span_overrides=[],
    ) == []


def test_section_eligible_ranges_subtract_passage():
    # ch 8.1 shape: section is eligible, but words 0..787 are flipped off.
    ranges = section_eligible_ranges(
        section_word_start=0, section_word_end=3138,
        base_counts_for_cp=True,
        span_overrides=[
            {"word_offset_start": 0, "word_offset_end": 787, "counts_for_cp": False},
        ],
    )
    assert ranges == [(787, 3138)]


def test_section_eligible_ranges_add_passage_into_ineligible_section():
    ranges = section_eligible_ranges(
        section_word_start=100, section_word_end=500,
        base_counts_for_cp=False,
        span_overrides=[
            {"word_offset_start": 200, "word_offset_end": 300, "counts_for_cp": True},
        ],
    )
    assert ranges == [(200, 300)]


def test_section_eligible_ranges_later_override_wins():
    # Subtract then re-add: re-add wins (file order).
    ranges = section_eligible_ranges(
        section_word_start=0, section_word_end=1000,
        base_counts_for_cp=True,
        span_overrides=[
            {"word_offset_start": 200, "word_offset_end": 400, "counts_for_cp": False},
            {"word_offset_start": 300, "word_offset_end": 350, "counts_for_cp": True},
        ],
    )
    assert ranges == [(0, 200), (300, 350), (400, 1000)]


# ---------- map endpoints ---------------------------------------------------


def test_map_endpoints(m: CpEpubMap):
    assert epub_to_cp(m, 0) == 0
    assert epub_to_cp(m, m.total_epub_words) == m.total_cp_words
    assert cp_to_epub(m, 0) == 0
    assert cp_to_epub(m, m.total_cp_words) == m.total_epub_words


def test_map_monotonic(m: CpEpubMap):
    # Sample 50 evenly spaced EPUB positions; CP must be non-decreasing.
    step = m.total_epub_words // 50 or 1
    prev = -1
    for w in range(0, m.total_epub_words + 1, step):
        cp = epub_to_cp(m, w)
        assert cp >= prev
        prev = cp


def test_intervals_are_disjoint_and_sorted(m: CpEpubMap):
    for i in range(1, len(m.epub_starts)):
        assert m.epub_starts[i] >= m.epub_ends[i - 1]
    for i, (s, e) in enumerate(zip(m.epub_starts, m.epub_ends)):
        assert s < e
        if i > 0:
            assert m.cp_before[i] == m.cp_before[i - 1] + (m.epub_ends[i - 1] - m.epub_starts[i - 1])


# ---------- round-trip ------------------------------------------------------


def test_cp_to_epub_round_trip_one_past_interval_starts(m: CpEpubMap):
    # cp_to_epub returns the smallest EPUB where the cumulative CP count
    # reaches the requested value. At an interval start `s`, the count
    # hasn't incremented yet — epub_to_cp(s) is the same as deep inside
    # the prior gap. Round-trip only makes sense for "just after the
    # first eligible word of the interval," i.e. EPUB position `s + 1`.
    for s, cp_before_i in zip(m.epub_starts, m.cp_before):
        # cp_before_i + 1 is the CP value reached at EPUB s+1.
        assert cp_to_epub(m, cp_before_i + 1) == s + 1


def test_epub_to_cp_round_trip_dense(m: CpEpubMap):
    # 200 sampled CP positions: cp_to_epub then back must give the same CP.
    step = m.total_cp_words // 200 or 1
    for cp in range(0, m.total_cp_words, step):
        ew = cp_to_epub(m, cp)
        assert epub_to_cp(m, ew) == cp


def test_position_inside_ineligible_run_freezes_cp(m: CpEpubMap):
    # Pick an interval boundary; the EPUB position one past the end and
    # the EPUB position at the next interval start should both have CP
    # equal to the cumulative at the end of the prior interval.
    for i in range(len(m.epub_starts) - 1):
        prior_end = m.epub_ends[i]
        next_start = m.epub_starts[i + 1]
        if next_start <= prior_end:
            continue  # contiguous; skip
        cp_at_end = epub_to_cp(m, prior_end)
        mid = (prior_end + next_start) // 2
        assert epub_to_cp(m, mid) == cp_at_end
        assert epub_to_cp(m, next_start) == cp_at_end


# ---------- agreement with the existing per-chapter count ------------------


def test_per_chapter_cp_matches_predict_rolls_loader(m: CpEpubMap):
    from predict_rolls import _load_cp_words_per_chapter
    import json
    chapters = json.loads(
        (ROOT / "data" / "derived" / "chapters.json").read_text()
    )["chapters"]
    by_title = _load_cp_words_per_chapter()
    for c in chapters:
        cn = str(c["chapter_num"])
        full_title = c["full_title"]
        start = m.chapter_epub_start[cn]
        end = m.chapter_epub_end[cn]
        map_cp = epub_to_cp(m, end) - epub_to_cp(m, start)
        assert map_cp == by_title[full_title], (
            f"chapter {cn} CP-eligible mismatch: "
            f"map={map_cp} predict_rolls={by_title[full_title]}"
        )


# ---------- ch 8.1 specifically: Joe doesn't appear until word 787 ---------


def test_ch_8_1_first_787_words_are_cp_ineligible(m: CpEpubMap):
    cn = "8.1"
    epub_start = m.chapter_epub_start[cn]
    cp_at_chapter_start = epub_to_cp(m, epub_start)
    # 100 words in: still no Joe, still no CP banked.
    cp_at_100 = epub_to_cp(m, epub_start + 100)
    assert cp_at_100 == cp_at_chapter_start
    # 787 words in (boundary): also still no CP banked.
    cp_at_787 = epub_to_cp(m, epub_start + 787)
    assert cp_at_787 == cp_at_chapter_start
    # One word past: now banking has begun.
    cp_at_788 = epub_to_cp(m, epub_start + 788)
    assert cp_at_788 == cp_at_chapter_start + 1


# ---------- chapter-local convenience --------------------------------------


def test_chapter_local_convenience_round_trips(m: CpEpubMap):
    for cn in ("1", "8.1", "97"):
        epub = chapter_local_to_epub(m, cn, 500)
        back_cn, back_local = epub_to_chapter_local(m, epub)
        assert back_cn == cn
        assert back_local == 500
