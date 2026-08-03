"""Length-preserving prose adapter: the one word-offset space for Stage 2.

``cp_word_index`` is the single source of prose text and word offsets for
Stage 2 (D-05a). This module adapts that canonical text so the *existing*
``evidence_scorer``/``miss_quote_matcher`` can consume it — it does not
introduce a second scorer, a second tokenizer, or a third offset pipeline.

**The trap this module exists for (D-33, measured).** D-05a said
``evidence_scorer.evidence_candidates()`` "composes without modification"
because it takes ``word_offsets`` as a parameter. That is half true, and
the wrong half is dangerous:

* ``word_offsets`` composes. ``text`` does not.
* ``_paragraph_matches`` splits on blank lines, but the epub HTML carries
  **13 newlines in 68 KB**. Feeding the canonical ``_prose_search_text``
  straight to ``evidence_candidates`` collapses a 262-paragraph chapter
  into **3** regex "paragraphs" and retrieval silently returns almost
  nothing — presenting as a model-quality problem.

The fix is to re-introduce paragraph breaks **without changing string
length**, so every character offset stays a valid index into the raw
chapter HTML and therefore into ``_chapter_word_index``'s offsets. Two
characters of an existing block tag are overwritten with ``\\n\\n``; tags
are already blanked to spaces by ``_prose_search_text``, so nothing real
is lost.

**Why not the TUI's pipeline.** The Forge Curator's own loader module
maintains an independent offset space that diverges from this one by **571
to 18,760 words** (ch 121.1: 23,922 CP words vs 42,682 TUI words) — a
different character space *and* a different word population. Mixing them
produces position errors that look like model hallucination. Stage 2 never
imports that module; a grep test asserts the absence by searching these
sources for its name, so the name must not appear even in prose.
"""

from __future__ import annotations

import re

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from cp_word_index import _chapter_word_index, _split_sections, _strip_to_spaces
    from mechanical_verifier import _build_tier2_pattern, _prose_search_text
except ImportError:  # pragma: no cover - import-path shim
    from scripts.cp_word_index import (  # type: ignore[no-redef]
        _chapter_word_index,
        _split_sections,
        _strip_to_spaces,
    )
    from scripts.mechanical_verifier import (  # type: ignore[no-redef]
        _build_tier2_pattern,
        _prose_search_text,
    )


# Block-level tags whose opening/closing marks a real paragraph boundary.
# Every one of these is at least 3 characters ("<p>", "<br>", ...), so
# overwriting two of its characters never runs past the tag's own span.
_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|h[1-6]|li|blockquote|br|hr)\b[^>]*>", re.IGNORECASE
)


def paragraphized_prose_text(
    chapter_html: str,
    *,
    section_classifications: dict[str, dict] | None = None,
    chapter_num: str | None = None,
) -> str:
    """``_prose_search_text`` plus length-preserving paragraph breaks.

    ``len(paragraphized_prose_text(html)) == len(html)`` always. That
    invariant is what keeps every char offset a valid index into the raw
    HTML, and therefore a valid input to the same bisect lookup the
    verifier uses.

    When ``section_classifications`` and ``chapter_num`` are supplied,
    sections that do not earn CP are blanked to spaces (still
    length-preservingly). This matches CP-word semantics: a paragraph
    retrieved from a non-CP section would otherwise bisect to the last CP
    word *before* it, potentially thousands of words away, producing a
    nonsense position.

    Note the deliberate asymmetry: ``verify_roll()`` searches the
    *unblanked* text, so a quote from a non-CP section still verifies.
    Blanking only changes what the model is *shown*, never what is
    accepted — it can cause under-retrieval, which is a routing outcome,
    never a wrong position.
    """
    base = _prose_search_text(chapter_html)
    if section_classifications is not None and chapter_num is not None:
        base = _blank_non_cp_sections(
            chapter_html, base, section_classifications, chapter_num
        )

    buf = list(base)
    for match in _BLOCK_TAG_RE.finditer(chapter_html):
        if match.end() - match.start() >= 2:
            buf[match.start()] = "\n"
            buf[match.start() + 1] = "\n"
    return "".join(buf)


def _blank_non_cp_sections(
    chapter_html: str,
    prose_text: str,
    section_classifications: dict[str, dict],
    chapter_num: str,
) -> str:
    """Replace non-CP-earning sections with spaces, preserving length."""
    buf = list(prose_text)
    body_match = re.search(r"<body[^>]*>", chapter_html)
    body_start = body_match.end() if body_match else 0

    for section_index, (_header, start, end) in enumerate(
        _split_sections(chapter_html)
    ):
        cls = section_classifications.get(f"{chapter_num}@{section_index}")
        if cls and cls.get("counts_for_cp"):
            continue
        for i in range(max(start, 0), min(end, len(buf))):
            buf[i] = " "
    # The preamble before <body> is never CP-earning prose.
    for i in range(0, min(body_start, len(buf))):
        buf[i] = " "
    return "".join(buf)


def word_starts_to_spans(
    word_starts: list[int], text_len: int
) -> list[tuple[int, int]]:
    """Adapt ``cp_word_index``'s ``list[int]`` into the ``list[tuple]``
    that ``evidence_scorer``/``miss_quote_matcher`` expect.

    Contiguous spans reproduce ``bisect_right(word_starts, c) - 1``
    semantics, so a char offset resolves to the same word index either
    way.

    Known edge case (measured on ch 1): a paragraph starting *before* the
    first CP-earning word maps to index ``0`` under
    ``evidence_scorer._word_index_for_char`` but ``-1`` under
    ``bisect_right(...) - 1``. Both mean "before the corpus starts" and
    the disagreement is harmless — recorded here so a test does not
    rediscover it as a bug.
    """
    return [
        (start, word_starts[i + 1] if i + 1 < len(word_starts) else text_len)
        for i, start in enumerate(word_starts)
    ]


def chapter_word_starts(
    chapter_html: str, section_classifications: dict[str, dict], chapter_num: str
) -> list[int]:
    """The canonical CP-earning word offsets. Thin, deliberate pass-through.

    Exists so Stage 2 modules never reach for a different tokenizer; there
    is exactly one call site for the real index.
    """
    return _chapter_word_index(chapter_html, section_classifications, chapter_num)


def prose_span_text(
    chapter_html: str,
    word_starts: list[int],
    start_word: int,
    end_word: int,
) -> str:
    """Return the prose covering CP words ``[start_word, end_word)``.

    Clamped to the chapter's real bounds. Whitespace is collapsed for
    readability — the returned text is for the model to *read*, never for
    the verifier to match against, so collapsing costs nothing here.
    """
    if not word_starts:
        return ""
    total = len(word_starts)
    start = max(0, min(int(start_word), total - 1))
    end = max(start, min(int(end_word), total))

    text = _prose_search_text(chapter_html)
    char_start = word_starts[start]
    char_end = word_starts[end] if end < total else len(text)
    return re.sub(r"\s+", " ", text[char_start:char_end]).strip()


def locate_quote(
    quote_text: str, chapter_html: str, word_starts: list[int]
) -> dict:
    """Locate ``quote_text`` in real prose and derive its word position.

    This is D-10's mechanism: the model proposes quote TEXT, and the
    position is derived here by *finding* that text. A quote that cannot
    be located returns ``found: False`` and no position — never an
    invented one.

    Tier 1 is exact substring; Tier 2 reuses the verifier's own tolerant
    pattern builder (whitespace + confusable folding). There is no third
    matcher and no fuzzy path: a quote needing word-level edits to match
    is rejected, exactly as the verifier would reject it.
    """
    import bisect

    result: dict = {
        "found": False,
        "tier": None,
        "word_position": None,
        "occurrence_count": 0,
        "char_offset": None,
    }
    if not quote_text or not quote_text.strip():
        return result

    search_text = _prose_search_text(chapter_html)

    offsets = [m.start() for m in re.finditer(re.escape(quote_text), search_text)]
    tier: int | None = 1 if offsets else None
    if not offsets:
        pattern = _build_tier2_pattern(quote_text)
        offsets = [m.start() for m in pattern.finditer(search_text)]
        tier = 2 if offsets else None

    if not offsets:
        return result

    char_offset = offsets[0]
    word_position = bisect.bisect_right(word_starts, char_offset) - 1
    result.update(
        {
            "found": True,
            "tier": tier,
            "word_position": max(word_position, 0),
            "occurrence_count": len(offsets),
            "char_offset": char_offset,
        }
    )
    return result
