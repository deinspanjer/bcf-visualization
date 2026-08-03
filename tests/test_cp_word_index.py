from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import _chapter_word_index, _strip_to_spaces  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders — small synthetic HTML strings, never live repo data.
# ---------------------------------------------------------------------------

def _words_at(html: str, offsets: list[int]) -> list[str]:
    """Reconstruct the token starting at each returned char offset,
    matched against the SAME tag-stripped-to-spaces view the production
    tokenizer walks — a black-box check that the returned offsets really
    do point at the tokenizer's real word boundaries.
    """
    spaced = _strip_to_spaces(html)
    out: list[str] = []
    for off in offsets:
        m = re.match(r"\S+", spaced[off:])
        out.append(m.group(0) if m else "")
    return out


# ---------------------------------------------------------------------------
# 1. Two-section chapter: only the counts_for_cp=True section's words are
#    returned, in order; the counts_for_cp=False section is excluded.
# ---------------------------------------------------------------------------

def test_two_section_chapter_returns_only_counted_section_words() -> None:
    html = (
        "<html><body>"
        "<p><strong>Header A</strong></p>"
        "<p>foo bar baz</p>"
        "<p><strong>Header B</strong></p>"
        "<p>qux quux</p>"
        "</body></html>"
    )
    classifications = {
        "1@0": {"counts_for_cp": False},  # preamble before first marker
        "1@1": {"counts_for_cp": True},   # "Header A" section
        "1@2": {"counts_for_cp": False},  # "Header B" section — excluded
    }
    offsets = _chapter_word_index(html, classifications, "1")
    assert _words_at(html, offsets) == ["Header", "A", "foo", "bar", "baz"]


# ---------------------------------------------------------------------------
# 2. A section not present in section_classifications at all (missing key)
#    is treated as not counting — same as an explicit False.
# ---------------------------------------------------------------------------

def test_missing_classification_key_defaults_to_excluded() -> None:
    html = (
        "<html><body>"
        "<p><strong>Header A</strong></p>"
        "<p>alpha beta</p>"
        "</body></html>"
    )
    # No "1@1" key at all.
    classifications: dict[str, dict] = {"1@0": {"counts_for_cp": False}}
    offsets = _chapter_word_index(html, classifications, "1")
    assert offsets == []


# ---------------------------------------------------------------------------
# 3. Body clamping: a section spanning the XML/head preamble (before the
#    opening <body> tag) contributes zero words even when counts_for_cp is
#    True — this prevents <title>...</title> text from being counted as
#    CP-earning prose.
# ---------------------------------------------------------------------------

def test_preamble_section_before_body_tag_is_clamped_to_empty() -> None:
    html = (
        "<?xml version='1.0'?>"
        "<html><head><title>Chapter Title Words</title></head>"
        "<body><p><strong>Header</strong></p><p>real content</p></body></html>"
    )
    classifications = {
        "2@0": {"counts_for_cp": True},   # preamble (title) — must clamp to empty
        "2@1": {"counts_for_cp": False},  # "Header" section — excluded
    }
    offsets = _chapter_word_index(html, classifications, "2")
    assert offsets == []


# ---------------------------------------------------------------------------
# 4. Body clamping does not affect content that legitimately starts after
#    <body> — the same preamble+header fixture, but now the post-body
#    section is the one counted.
# ---------------------------------------------------------------------------

def test_post_body_section_counts_normally_despite_clamp() -> None:
    html = (
        "<?xml version='1.0'?>"
        "<html><head><title>Chapter Title Words</title></head>"
        "<body><p><strong>Header</strong></p><p>real content</p></body></html>"
    )
    classifications = {
        "2@0": {"counts_for_cp": False},  # preamble (title) — excluded anyway
        "2@1": {"counts_for_cp": True},   # "Header" section — counted
    }
    offsets = _chapter_word_index(html, classifications, "2")
    assert _words_at(html, offsets) == ["Header", "real", "content"]
