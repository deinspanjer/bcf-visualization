from __future__ import annotations

import re

from scripts.forge_curator.data_loader import ChapterDerived, ChapterMeta, ChapterProse
from scripts.forge_curator.state import (
    DEFAULT_REGEX_PATTERNS,
    ChapterState,
    ForgeCuratorState,
)


def test_regex_hits_preserve_full_match_char_span() -> None:
    text = "the Forge met my power"
    state = ForgeCuratorState(data=object())  # type: ignore[arg-type]
    state.chapter = ChapterState(
        meta=ChapterMeta(
            chapter_num="1",
            full_title="1",
            epub_href=None,
            total_word_count=5,
            cp_earning_word_count=5,
            sections=[],
        ),
        derived=ChapterDerived(
            chapter_num="1",
            chapter_facts=None,
            roll_facts=[],
            predicted_rolls=[],
            roll_outcomes=[],
            validation=None,
            perks=[],
        ),
        prose=ChapterProse(
            chapter_num="1",
            text=text,
            word_offsets=[(0, 3), (4, 9), (10, 13), (14, 16), (17, 22)],
            section_break_word_indices=[],
        ),
    )

    hits = state.set_regex(0, "my power")

    assert hits.word_indices == [3]
    assert hits.char_spans == [(text.index("my power"), len(text))]


def test_default_regex_patterns_are_word_bounded_and_match_expected_phrases() -> None:
    text = (
        "remote mote reach outreach constellation constellations "
        "Celestial Forge the Forge The Forge my power My power my powers overpower"
    )
    state = ForgeCuratorState(data=object())  # type: ignore[arg-type]
    state.chapter = ChapterState(
        meta=ChapterMeta(
            chapter_num="1",
            full_title="1",
            epub_href=None,
            total_word_count=15,
            cp_earning_word_count=15,
            sections=[],
        ),
        derived=ChapterDerived(
            chapter_num="1",
            chapter_facts=None,
            roll_facts=[],
            predicted_rolls=[],
            roll_outcomes=[],
            validation=None,
            perks=[],
        ),
        prose=ChapterProse(
            chapter_num="1",
            text=text,
            word_offsets=[
                (match.start(), match.end()) for match in re.finditer(r"\S+", text)
            ],
            section_break_word_indices=[],
        ),
    )

    slot_1_hits = state.set_regex(0, DEFAULT_REGEX_PATTERNS[0])
    slot_2_hits = state.set_regex(1, DEFAULT_REGEX_PATTERNS[1])

    slot_1_matches = [text[start:end] for start, end in slot_1_hits.char_spans]
    slot_2_matches = [text[start:end] for start, end in slot_2_hits.char_spans]

    assert slot_1_hits.error is None
    assert slot_2_hits.error is None
    assert slot_1_matches == ["mote", "reach", "constellation"]
    assert slot_2_matches == [
        "Celestial Forge",
        "the Forge",
        "The Forge",
        "my power",
        "My power",
        "my powers",
    ]
