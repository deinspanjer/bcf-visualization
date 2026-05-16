from __future__ import annotations

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


def test_default_regex_patterns_are_removed_for_single_user_buffer() -> None:
    assert DEFAULT_REGEX_PATTERNS == ()
