"""Shared CP-earning-word tokenizer, extracted per Phase 2 D-01/D-02.

Pure module — no argparse, no top-level file I/O. This is the single,
importable source of the CP-earning-word char-offset index; no other
script should reimplement ``_chapter_word_index``.

``scripts/find_text_backed_rolls.py`` is this module's rewritten
consumer (D-01: full rewrite, no shim, no re-export). ``_split_sections``
and ``_strip_to_spaces`` are copied verbatim (not imported) from
``scripts/find_roll_locations.py`` to keep this module's dependency
graph confined to itself rather than reaching into a script outside
D-01's stated scope — see this phase's ``deferred-items.md`` for the
resulting three-way duplication this leaves unresolved.

``EPUB``/``load_chapter_html`` route the epub path through
``scripts/data_paths.py`` (D-02), replacing the hardcoded
``ROOT / "data" / "raw"`` pattern this tokenizer used to live behind.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from data_paths import RAW

EPUB = RAW / "Brocktons_Celestial_Forge.epub"


# ---------- copied verbatim from scripts/find_roll_locations.py -----------
# (see module docstring — copied, not imported, per D-01's blast-radius
# finding; this is a THIRD independent copy of these two functions, see
# deferred-items.md)

def _strip_to_spaces(html: str) -> str:
    """Replace every HTML tag and HTML entity with spaces of equal
    length. Returns a string of the SAME length as the input where tag
    runs become whitespace runs. Plain-text characters keep their exact
    offsets.

    This is intentional: regex offsets in the result are valid offsets
    in the original chapter HTML, which is what the schema records.
    Entities like `&nbsp;` become e.g. 6 spaces, which is fine — they
    were that many characters in the HTML stream too.
    """
    out = list(html)
    for m in re.finditer(r"<[^>]*>", html):
        for i in range(m.start(), m.end()):
            out[i] = " "
    # Decode common entities by replacing them in place with spaces too;
    # entity references would otherwise leak into matches like &amp;.
    for m in re.finditer(r"&[a-zA-Z]+;|&#\d+;", html):
        for i in range(m.start(), m.end()):
            out[i] = " "
    return "".join(out)


_PLAIN_PAI_MARKER_RE = (
    r"(?:Preamble|Addendum|Interlude)[:\s]+[A-Z][A-Za-z0-9 .'\-]{0,60}"
)
_PLAIN_TITLE_PAI_MARKER_RE = (
    r"(?:\d+(?:\.\d+)?\s+)?" + _PLAIN_PAI_MARKER_RE
)
_PLAIN_SECTION_MARKER_RE = (
    r"(?:Jumpchain abilities this chapter:?|New abilities for [^:<]+:?|"
    + _PLAIN_TITLE_PAI_MARKER_RE
    + r")"
)

_MARKER_RE = re.compile(
    r"(?:"
    r"<p[^>]*>\s*(?:"
    r"<strong[^>]*>(?P<strong>[^<]+)</strong>"
    r"|(?P<plain>" + _PLAIN_SECTION_MARKER_RE + r")"
    r")\s*</p>"
    r"|<strong[^>]*>(?P<strong_inline>" + _PLAIN_SECTION_MARKER_RE + r")</strong>"
    r"|(?<=>)\s*(?P<plain_inline>" + _PLAIN_TITLE_PAI_MARKER_RE + r")\s*(?=<p\b)"
    r")",
    re.IGNORECASE,
)


def _marker_header(match: re.Match[str]) -> str:
    return (
        match.group("strong")
        or match.group("plain")
        or match.group("strong_inline")
        or match.group("plain_inline")
        or ""
    ).strip()


def _split_sections(html: str) -> list[tuple[str | None, int, int]]:
    """Return list of (header, html_start, html_end) tuples covering the
    full chapter HTML, identical to extract_chapter_sections._split_sections.
    """
    markers = list(_MARKER_RE.finditer(html))
    if not markers:
        return [(None, 0, len(html))]
    out: list[tuple[str | None, int, int]] = []
    if markers[0].start() > 0:
        out.append((None, 0, markers[0].start()))
    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(html)
        out.append((_marker_header(m), start, end))
    return out


# ---------- moved verbatim from scripts/find_text_backed_rolls.py ---------

def _chapter_word_index(
    chapter_html: str,
    section_classifications: dict[str, dict],
    chapter_num: str,
) -> list[int]:
    """Return a list of char offsets, one per CP-earning word in the
    chapter, in order. Index N gives the start char of the (N+1)-th
    CP-earning word in this chapter's HTML.

    Sections whose span starts before the opening <body> tag (i.e. the
    XML declaration, DOCTYPE, and <head> preamble) are clamped to start
    at the first byte after <body>.  This prevents the chapter title
    inside <title>...</title> from being counted as CP-earning prose
    words when a section's html_start == 0.
    """
    # Locate the end of the <body...> opening tag so we never count words
    # in the XML/DOCTYPE/head preamble.  If somehow the file has no <body>
    # tag, fall back to 0 (no clamping).
    body_m = re.search(r"<body[^>]*>", chapter_html)
    body_content_start = body_m.end() if body_m else 0

    out: list[int] = []
    for section_index, (_header, s_start, s_end) in enumerate(_split_sections(chapter_html)):
        cls = section_classifications.get(f"{chapter_num}@{section_index}")
        if not cls or not cls.get("counts_for_cp"):
            continue
        # Clamp: skip any bytes that fall inside the XML/HTML preamble.
        effective_start = max(s_start, body_content_start)
        if effective_start >= s_end:
            continue
        spaced = _strip_to_spaces(chapter_html[effective_start:s_end])
        for m in re.finditer(r"\S+", spaced):
            out.append(effective_start + m.start())
    return out


def load_chapter_html(epub_path: Path, epub_href: str) -> str:
    """Read one chapter's raw HTML out of the epub archive.

    Preserves the ``"EPUB/" + href`` prefix byte-for-byte — the same
    convention used identically today in ``find_text_backed_rolls.py``,
    ``find_roll_locations.py``, and ``extract_chapter_sections.py``.
    """
    with zipfile.ZipFile(epub_path) as zf:
        return zf.read(f"EPUB/{epub_href}").decode("utf-8")
