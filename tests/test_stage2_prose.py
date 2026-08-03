"""Regression guards for the D-33 length-preserving prose adapter.

These tests exist because the failure they guard is *silent*: feeding the
canonical prose text straight to ``evidence_candidates`` collapses a
chapter into three "paragraphs" and retrieval returns almost nothing,
which presents as a model-quality problem rather than a plumbing bug.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import EPUB, _chapter_word_index, load_chapter_html  # noqa: E402
from scripts.data_paths import DERIVED, MANUAL  # noqa: E402
from scripts.forge_curator.evidence_scorer import (  # noqa: E402
    _paragraph_matches,
    evidence_candidates,
)
from scripts.mechanical_verifier import _prose_search_text  # noqa: E402
from scripts.stage2_prose import (  # noqa: E402
    locate_quote,
    paragraphized_prose_text,
    prose_span_text,
    word_starts_to_spans,
)

# Chapters spanning short, mid, long, and the multi-section outlier.
REAL_CHAPTERS = ["1", "92", "104", "121.1"]


@pytest.fixture(scope="module")
def chapter_data() -> dict[str, tuple[str, list[int]]]:
    chapters_doc = json.loads((DERIVED / "chapters.json").read_text())
    href_by_chapter = {
        c["chapter_num"]: c["epub_href"] for c in chapters_doc["chapters"]
    }
    classifications = json.loads(
        (MANUAL / "section_classifications.json").read_text()
    )["classifications"]

    out: dict[str, tuple[str, list[int]]] = {}
    for chapter_num in REAL_CHAPTERS:
        html = load_chapter_html(EPUB, href_by_chapter[chapter_num])
        out[chapter_num] = (
            html,
            _chapter_word_index(html, classifications, chapter_num),
        )
    return out


def test_adapter_preserves_length(chapter_data) -> None:
    """Length preservation is what keeps every char offset valid.

    If this fails, every derived word position silently shifts.
    """
    for chapter_num, (html, _word_starts) in chapter_data.items():
        adapted = paragraphized_prose_text(html)
        assert len(adapted) == len(html), f"chapter {chapter_num} changed length"
        assert len(adapted) == len(_prose_search_text(html))


def test_adapter_offsets_match_cp_word_index(chapter_data) -> None:
    """Adapter word starts are byte-identical to the canonical tokenizer.

    This is the D-05a guarantee: one word-offset space, not two. The TUI's
    parallel pipeline diverges from this one by 571 to 18,760 words.
    """
    for chapter_num, (html, word_starts) in chapter_data.items():
        adapted = paragraphized_prose_text(html)
        spans = word_starts_to_spans(word_starts, len(adapted))
        assert [start for start, _end in spans] == word_starts, (
            f"chapter {chapter_num} word starts diverged"
        )
        # Spans are contiguous and ordered.
        for (start, end) in spans:
            assert start <= end


def test_paragraph_segmentation(chapter_data) -> None:
    """The Pitfall 3 regression guard.

    The canonical text yields ~3 regex paragraphs because the epub HTML
    carries almost no newlines. The adapter must restore real paragraph
    structure.
    """
    for chapter_num, (html, _word_starts) in chapter_data.items():
        canonical_paragraphs = len(_paragraph_matches(_prose_search_text(html)))
        adapted_paragraphs = len(_paragraph_matches(paragraphized_prose_text(html)))

        assert canonical_paragraphs <= 3, (
            "canonical text unexpectedly segments; the trap may have moved"
        )
        assert adapted_paragraphs > 3, (
            f"chapter {chapter_num} still collapses to {adapted_paragraphs} paragraphs"
        )
        assert adapted_paragraphs >= 90


def test_retrieval_returns_candidates_on_real_chapters(chapter_data) -> None:
    """Retrieval actually produces candidates once segmentation is fixed."""
    for chapter_num, (html, word_starts) in chapter_data.items():
        adapted = paragraphized_prose_text(html)
        spans = word_starts_to_spans(word_starts, len(adapted))
        found = evidence_candidates(adapted, spans, threshold=3)
        assert len(found) > 3, f"chapter {chapter_num} retrieved only {len(found)}"


def test_threshold_default_is_not_mutated() -> None:
    """The TUI's navigation threshold stays at its tuned default (D-02)."""
    from scripts.forge_curator.evidence_scorer import EVIDENCE_CANDIDATE_THRESHOLD

    assert EVIDENCE_CANDIDATE_THRESHOLD == 4


def test_locate_quote_derives_position_or_reports_not_found(chapter_data) -> None:
    html, word_starts = chapter_data["92"]

    real = locate_quote(
        "I felt the Forge fail to connect to a massive mote from the "
        "Knowledge constellation",
        html,
        word_starts,
    )
    assert real["found"] is True
    assert real["tier"] == 1
    assert isinstance(real["word_position"], int)

    fabricated = locate_quote(
        "The Forge granted me a wondrous device that never existed.",
        html,
        word_starts,
    )
    assert fabricated["found"] is False
    # No invented position, ever.
    assert fabricated["word_position"] is None
    assert fabricated["tier"] is None


def test_locate_quote_tier2_tolerates_whitespace_not_paraphrase(chapter_data) -> None:
    html, word_starts = chapter_data["92"]
    base = "I felt the Forge fail to connect to a massive mote"

    spaced = locate_quote(base.replace(" ", "   "), html, word_starts)
    assert spaced["found"] is True
    assert spaced["tier"] == 2

    # A word-level edit must be rejected outright -- exact-or-reject.
    paraphrased = locate_quote(
        "I sensed the Forge fail to connect to a massive mote", html, word_starts
    )
    assert paraphrased["found"] is False


def test_prose_span_is_bounded_and_clamped(chapter_data) -> None:
    html, word_starts = chapter_data["92"]

    span = prose_span_text(html, word_starts, 1000, 1100)
    assert span
    assert len(span.split()) <= 200

    # Out-of-range indices clamp rather than raise.
    assert prose_span_text(html, word_starts, 10**9, 10**9 + 10) is not None
    assert prose_span_text(html, word_starts, 0, 0) == ""


def test_stage2_uses_one_word_offset_pipeline() -> None:
    """No Stage 2 module may reach for the TUI's parallel offset space."""
    for path in sorted(SCRIPTS.glob("stage2_*.py")):
        assert "data_loader" not in path.read_text(), (
            f"{path.name} references data_loader; Stage 2 must use "
            "cp_word_index only (D-05a)"
        )
