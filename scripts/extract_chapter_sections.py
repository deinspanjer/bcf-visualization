"""Walk every EPUB chapter, split into sections, classify each section's
POV, count CP-earning words, and extract the perk listings from the
"Jumpchain abilities this chapter:" footers.

Inputs:
  - data/derived/chapters.json
  - data/raw/Brocktons_Celestial_Forge.epub  (full prose, build-time only)

Outputs:
  - data/derived/chapter_sections.json  - per-section classification and
                                          word count for the regime simulator
  - data/derived/extracted_perks.json   - per-chapter perk listings parsed
                                          from the chapter's footer, useful
                                          for filling catalog gaps

Section classification combines:

  1. Header pattern (existing logic):
     - "Jumpchain abilities" / "New Abilities for" / "Author" / "Note"
       / "A/N" -> non-MC, high confidence.
     - "Preamble X" / "Addendum X" / "Interlude X" where X starts with
       "Joe" -> MC; otherwise non-MC. High confidence either way.

  2. Content signals on first ~500 words of the section:
     - First-person pronoun ratio (I/my/me/I'm/I'd/I'll/myself vs
       he/she/his/her/him). High fp ratio -> MC; high tp -> non-MC.
     - Structural markers: PHO forum format ("Topic:", "►", "Posted On"),
       newspaper format (all-caps headlines, "Reported By"), meeting
       reports ("In attendance:", "Director ...") -> non-MC.

The two checks usually agree. Disagreements are surfaced as
confidence="low" and reported in stderr so they can be reviewed.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS_JSON = ROOT / "data" / "derived" / "chapters.json"
OUT_SECTIONS = ROOT / "data" / "derived" / "chapter_sections.json"
OUT_PERKS = ROOT / "data" / "derived" / "extracted_perks.json"


# ---------- helpers ---------------------------------------------------------


class _Strip(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ("head", "title", "script", "style"):
            self.skip += 1
        if not self.skip and tag in ("p", "div", "br", "li", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("head", "title", "script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _text(html: str) -> str:
    s = _Strip()
    s.feed(html)
    t = "".join(s.parts)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n[ \t]+", "\n", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def _word_count(text: str) -> int:
    return len(text.split()) if text else 0


_FIRST_PERSON_RE = re.compile(
    r"\b(?:I|I'm|I've|I'd|I'll|my|me|myself|mine)\b",
    re.IGNORECASE,
)
_THIRD_PERSON_RE = re.compile(
    r"\b(?:he|she|his|her|hers|him|himself|herself)\b",
    re.IGNORECASE,
)


def _pronoun_counts(text: str) -> tuple[int, int]:
    return (
        len(_FIRST_PERSON_RE.findall(text)),
        len(_THIRD_PERSON_RE.findall(text)),
    )


_PHO_RE = re.compile(
    r"►\s*(?:Topic|Posted|Replied)|\bPosted On\b\s+\w+|"
    r"\(Wiki Warrior\)|\(Original Poster\)|"
    r"In:\s*Boards\s*►",
    re.IGNORECASE,
)
_NEWS_RE = re.compile(
    r"\bBROCKTON BAY\b|BAYBULLETIN\.COM|EMERGENCY NEWS ALERT|"
    r"\bReported By\b|\bBreaking News\b",
)
_MEETING_RE = re.compile(
    r"\bMeeting Report\b|\bIn attendance:|\bDirector \w+\s",
)


def _structural_markers(text: str) -> list[str]:
    markers: list[str] = []
    if _PHO_RE.search(text):
        markers.append("pho")
    if _NEWS_RE.search(text):
        markers.append("news")
    if _MEETING_RE.search(text):
        markers.append("meeting_report")
    return markers


_AN_RE = re.compile(r"\(\s*Author'?s?\s+Note", re.IGNORECASE)


# ---------- author-note ranges (curated) -----------------------------------


AUTHOR_NOTES_JSON = ROOT / "data" / "manual" / "author_notes.json"


def _load_curated_author_notes() -> dict[tuple[str, int], list[str]]:
    """Read data/manual/author_notes.json and return verbatim AN texts
    keyed by (chapter_num, section_index).

    The curated file is the single source of truth for author-to-reader
    asides. It was built by a one-time human-supervised scan of every
    chapter (see file's `_source` field). Adding or removing an AN is a
    manual edit to that file — the extractor never guesses.
    """
    if not AUTHOR_NOTES_JSON.exists():
        return {}
    data = json.loads(AUTHOR_NOTES_JSON.read_text())
    out: dict[tuple[str, int], list[str]] = {}
    for entry in data.get("author_notes", []):
        key = (entry["chapter_num"], int(entry["section_index"]))
        out.setdefault(key, []).append(entry["an_text"])
    return out


def _resolve_author_note_ranges(
    section_text: str, an_texts: list[str], chapter_num: str, section_index: int
) -> list[tuple[int, int]]:
    """Locate each curated AN string in the section text and return
    (start, end) char offsets. Errors loudly if an AN cannot be found —
    that means the curated file has drifted from the source and a
    human needs to reconcile it.
    """
    ranges: list[tuple[int, int]] = []
    for an in an_texts:
        idx = section_text.find(an)
        if idx < 0:
            raise SystemExit(
                f"curated author-note text for chapter {chapter_num} "
                f"section {section_index} not found in source text. "
                f"data/manual/author_notes.json is stale; reconcile it "
                f"before re-running. AN starts: {an[:80]!r}"
            )
        ranges.append((idx, idx + len(an)))
    ranges.sort()
    return ranges


def _words_in_ranges(text: str, ranges: list[tuple[int, int]]) -> int:
    return sum(_word_count(text[s:e]) for s, e in ranges)


def _char_range_to_word_range(
    text: str, char_start: int, char_end: int
) -> tuple[int, int]:
    """Convert a char-offset range in ``text`` to a word-index range.

    Word indices count whitespace-delimited tokens (matching
    ``_word_count`` semantics). The returned range is half-open
    ``[word_start, word_end)``. Out-of-range or empty char spans
    return ``(0, 0)``.
    """
    if char_end <= char_start or not text:
        return (0, 0)
    char_start = max(0, char_start)
    char_end = min(len(text), char_end)
    word_start = _word_count(text[:char_start])
    word_end = word_start + _word_count(text[char_start:char_end])
    return (word_start, word_end)


def _merge_word_ranges(ranges: list[tuple[int, int]]) -> list[list[int]]:
    """Sort + merge overlapping/adjacent ``(start, end)`` ranges. Returns
    a list of two-element lists for JSON-friendliness."""
    out: list[list[int]] = []
    for s, e in sorted(ranges):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


# ---------- section data structures ----------------------------------------


@dataclass
class Section:
    header: str | None
    word_count: int
    counts_for_cp: bool
    classification: str          # mc | non_mc_perks | non_mc_other_pov | non_mc_meta
    confidence: str              # high | medium | low
    classification_reason: str
    fp_count: int
    tp_count: int
    structural_markers: list[str] = field(default_factory=list)
    sample: str = ""             # first ~200 chars of prose (for review)
    author_note_ranges: list[tuple[int, int]] = field(default_factory=list)
    author_note_word_count: int = 0
    # Auto-detected section-header word count: when the section's
    # ``header`` field appears as a contiguous run at the start of the
    # section's prose, those header words are excluded from CP-earning
    # totals. Computed deterministically here so the TUI doesn't need
    # to redo it.
    auto_header_word_count: int = 0


@dataclass
class ChapterSections:
    chapter_num: str
    full_title: str
    epub_href: str
    total_word_count: int
    cp_earning_word_count: int
    sections: list[Section]
    # Union of all per-section content-exclusion ranges in chapter-local
    # word coords. Built from AN word ranges (converted from per-section
    # AN char ranges) + auto-header word ranges. Downstream CP consumers
    # intersect these ranges with CP-eligible sections; content-word
    # consumers subtract them globally. Manual header_corrections from
    # data/manual/ are merged in at consumption time where needed since
    # they live outside this file.
    excluded_word_ranges: list[list[int]] = field(default_factory=list)


# ---------- header rule -----------------------------------------------------


_NON_MC_HEADER_PREFIXES = (
    "jumpchain abilities", "jumpchain perks",
    "new abilities for",
    "author", "a/n", "note",
)


def _classify_by_header(header: str | None) -> tuple[str | None, str]:
    """Returns (classification, reason) from header alone, or
    (None, ...) if the header doesn't conclusively decide it.
    """
    if header is None:
        return (None, "implicit (no header)")
    h = header.strip()
    hl = h.lower()
    if any(hl.startswith(p) for p in _NON_MC_HEADER_PREFIXES):
        return ("non_mc_meta", f"header matches {hl.split()[0]!r}")
    m = re.match(r"^(preamble|addendum|interlude)\b\s*:?\s*(.*)", h, re.I)
    if m:
        kind = m.group(1).lower()
        target = m.group(2).strip().lower()
        if target.startswith("joe"):
            return ("mc", f"header is {kind!r} but target is Joe (MC)")
        if not target:
            return (None, f"header is bare {kind!r}, no target")
        return ("non_mc_other_pov", f"header is {kind} {target!r} (not Joe)")
    return (None, "header doesn't match a known pattern")


# ---------- content rule ----------------------------------------------------


def _classify_by_content(text: str) -> tuple[str | None, str, dict]:
    """Returns (classification, reason, evidence_dict)."""
    sample = text[:3000]
    fp, tp = _pronoun_counts(sample)
    structural = _structural_markers(sample)
    has_an = bool(_AN_RE.search(sample))

    evidence = {
        "fp_count": fp,
        "tp_count": tp,
        "structural_markers": structural,
        "has_author_note": has_an,
    }

    if structural:
        return ("non_mc_other_pov", f"structural markers: {','.join(structural)}", evidence)

    total = fp + tp
    if total < 3:
        return (None, "too little pronoun signal", evidence)
    if fp >= 3 and fp / max(total, 1) >= 0.6:
        return ("mc", f"first-person dominant ({fp}/{total})", evidence)
    if tp >= 3 and tp / max(total, 1) >= 0.6:
        return ("non_mc_other_pov", f"third-person dominant ({tp}/{total})", evidence)
    return (None, f"mixed pronouns (fp={fp}, tp={tp})", evidence)


# ---------- combine ---------------------------------------------------------


def _classify_section(
    header: str | None,
    text: str,
    an_ranges: list[tuple[int, int]] | None = None,
    *,
    implicit_header: str | None = None,
) -> Section:
    if an_ranges is None:
        an_ranges = []
    header_class, header_reason = _classify_by_header(header)
    content_class, content_reason, evidence = _classify_by_content(text)

    classification: str
    reason: str
    confidence: str

    # Special case: implicit (no header) sections. These are the chapter
    # body before any explicit marker. They contain the main MC story
    # and should always count, even if the first paragraph happens to be
    # a third-person scene-setter or features dialogue heavy on other
    # characters. The content scan here is unreliable because we only
    # look at the first 3000 chars of what may be a 12k+-word section.
    if header is None:
        classification = "mc"
        reason = (f"implicit (no header): always MC by convention; "
                  f"content sample: {content_reason}")
        confidence = "high"
    elif header_class is not None and content_class is not None:
        if header_class == content_class:
            classification = header_class
            reason = f"header agrees: {header_reason}; content: {content_reason}"
            confidence = "high"
        else:
            # Header is explicit (Preamble/Addendum/Interlude X), trust it
            # but flag for review.
            classification = header_class
            reason = (f"header says {header_class}: {header_reason}; "
                      f"but content says {content_class}: {content_reason}")
            confidence = "low"
    elif header_class is not None:
        classification = header_class
        reason = f"header: {header_reason} (no content signal)"
        confidence = "high" if header_class != "mc" or header.startswith(("Preamble", "Addendum", "Interlude")) else "medium"
    elif content_class is not None:
        classification = content_class
        reason = f"content: {content_reason}"
        confidence = "medium"
    else:
        # Both ambiguous and we have a non-empty header that didn't
        # match any pattern — default to MC and flag.
        classification = "mc"
        reason = f"defaulted to mc: header={header_reason}; content={content_reason}"
        confidence = "low"

    counts_for_cp = classification == "mc"
    sample = text[:600].replace("\n", " ").strip()
    an_words = _words_in_ranges(text, an_ranges)
    auto_header_words = _detect_auto_header_words(
        text,
        header,
        implicit_header=implicit_header,
    )
    return Section(
        header=header,
        word_count=_word_count(text),
        counts_for_cp=counts_for_cp,
        classification=classification,
        confidence=confidence,
        classification_reason=reason,
        fp_count=evidence["fp_count"],
        tp_count=evidence["tp_count"],
        structural_markers=evidence["structural_markers"],
        sample=sample,
        author_note_ranges=[list(r) for r in an_ranges],
        author_note_word_count=an_words,
        auto_header_word_count=auto_header_words,
    )


_HEADER_NORM_RE = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


def _norm_header_word(w: str) -> str:
    return _HEADER_NORM_RE.sub("", w).lower()


def _detect_auto_header_words(
    text: str,
    header: str | None,
    *,
    implicit_header: str | None = None,
) -> int:
    """Return the number of words at the start of ``text`` that match
    the section's declared ``header`` field, or 0 if the match fails.

    Case-insensitive, punctuation-stripped per word, with a 5-word slack
    window. Same convention used previously by
    ``forge_curator/data_loader.py::_detect_section_headers``; that
    duplicate is now removed in favour of this canonical computation.
    """
    header = header or implicit_header
    if not header or not text.strip():
        return 0
    header_words = [_norm_header_word(w) for w in header.split() if _norm_header_word(w)]
    if not header_words:
        return 0
    text_words = text.split()
    if not text_words:
        return 0
    slack = 5
    max_offset = min(slack, len(text_words) - len(header_words))
    if max_offset < 0:
        return 0
    for offset in range(max_offset + 1):
        prose_norm = [
            _norm_header_word(text_words[offset + k])
            for k in range(len(header_words))
        ]
        if prose_norm == header_words:
            repeats = len(header_words)
            cursor = offset + len(header_words)
            while cursor + len(header_words) <= len(text_words):
                next_norm = [
                    _norm_header_word(text_words[cursor + k])
                    for k in range(len(header_words))
                ]
                if next_norm != header_words:
                    break
                repeats += len(header_words)
                cursor += len(header_words)
            # The auto-header occupies offset..cursor words. Including
            # leading slack would over-count if punctuation precedes the
            # header; this corpus does not do that in practice, so we
            # report only the matched/repeated header words.
            return repeats
    return 0


# ---------- perk extraction ------------------------------------------------


# A perk listing line looks like: "Workshop (Personal Reality) 100:"
# or "Master's Body (History's Strongest Disciple: Kenichi) Free after 10 years:"
# Source can contain parentheses (e.g. "Light of Terra DLC 5 (...) - W40k").
_PERK_HEAD_RE = re.compile(
    r"^(?P<name>.+?)\s*"
    r"\((?P<source>.+)\)\s*"
    r"(?P<cost>\d+|Free[^:]*)\s*:\s*$"
)


def _extract_perks_from_section(html: str) -> list[dict]:
    """Parse a perks-listing section's HTML into a list of perk dicts."""
    # Grab paragraphs as alternating: head-line, description-line(s), head-line, ...
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    # Strip inner tags from each paragraph
    cleaned: list[str] = []
    for p in paragraphs:
        t = re.sub(r"<[^>]+>", " ", p)
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            cleaned.append(t)

    perks: list[dict] = []
    i = 0
    while i < len(cleaned):
        line = cleaned[i]
        m = _PERK_HEAD_RE.match(line)
        if not m:
            i += 1
            continue
        name = m.group("name").strip()
        source = m.group("source").strip()
        cost_text = m.group("cost").strip()
        if cost_text.lower().startswith("free"):
            cost = 0
            free = True
        else:
            try:
                cost = int(cost_text)
            except ValueError:
                cost = 0
            free = False
        # Following paragraphs (until next match) are the description
        desc_parts: list[str] = []
        j = i + 1
        while j < len(cleaned) and not _PERK_HEAD_RE.match(cleaned[j]):
            desc_parts.append(cleaned[j])
            j += 1
        perks.append({
            "name": name,
            "source": source,
            "cost_text": cost_text,
            "cost": cost,
            "free": free,
            "description": " ".join(desc_parts).strip(),
        })
        i = j
    return perks


# ---------- main pipeline ---------------------------------------------------


_MARKER_RE = re.compile(
    r"<p[^>]*>\s*<strong[^>]*>([^<]+)</strong>\s*</p>", re.IGNORECASE,
)


def _split_sections(html: str) -> list[tuple[str | None, int, int]]:
    """Return list of (header, html_start, html_end) tuples covering the
    full chapter HTML. Sections are demarcated by <p><strong>X</strong></p>
    markers; an implicit section before the first marker is included if
    non-empty.

    The section's html range starts at the marker, not after — so the
    section's stripped text begins with the header text. This keeps
    word-count semantics consistent with how the chapter is rendered
    end-to-end (e.g. by the TUI's prose viewer); auto-header detection
    can then identify the leading header words and exclude them from
    CP-eligible totals.
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
        out.append((m.group(1).strip(), start, end))
    return out


def _build_chapter_index(zf: zipfile.ZipFile) -> dict[str, str]:
    """Map chapter full_title -> EPUB href."""
    nav = zf.read("EPUB/nav.xhtml").decode("utf-8")
    out: dict[str, str] = {}
    for href, title in re.findall(
        r'<a[^>]*?href="([^"]+)"[^>]*>([^<]+)</a>', nav, re.DOTALL
    ):
        out[title.strip()] = href
    return out


def main() -> None:
    if not EPUB.exists():
        raise SystemExit(
            f"missing {EPUB.relative_to(ROOT)}; this script needs the source EPUB"
        )

    chapters = json.loads(CHAPTERS_JSON.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    section_records: list[ChapterSections] = []
    perk_records: list[dict] = []
    low_confidence_count = 0
    flagged: list[tuple[str, str, str]] = []
    curated_an = _load_curated_author_notes()
    consumed_an_keys: set[tuple[str, int]] = set()

    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            href = title_to_href.get(c["full_title"])
            if not href:
                continue
            html = zf.read(f"EPUB/{href}").decode("utf-8")
            sections_html = _split_sections(html)

            sections: list[Section] = []
            cp_words = 0
            total_words = 0
            chapter_excluded_word_ranges: list[tuple[int, int]] = []
            chapter_word_cursor = 0
            for idx, (header, s, e) in enumerate(sections_html):
                section_html = html[s:e]
                section_text = _text(section_html)
                an_texts = curated_an.get((c["chapter_num"], idx), [])
                an_ranges = _resolve_author_note_ranges(
                    section_text, an_texts, c["chapter_num"], idx
                )
                if an_texts:
                    consumed_an_keys.add((c["chapter_num"], idx))
                section = _classify_section(
                    header,
                    section_text,
                    an_ranges,
                    implicit_header=c["full_title"] if header is None else None,
                )
                sections.append(section)
                total_words += section.word_count
                # Build chapter-local exclusion ranges for this section
                # for content accounting. Downstream CP accounting
                # intersects these ranges with CP-eligible sections, so
                # ranges in ineligible sections are harmless but remain
                # visible to content-word totals.
                for an_cs, an_ce in an_ranges:
                    ws_local, we_local = _char_range_to_word_range(
                        section_text, an_cs, an_ce,
                    )
                    if we_local > ws_local:
                        chapter_excluded_word_ranges.append((
                            chapter_word_cursor + ws_local,
                            chapter_word_cursor + we_local,
                        ))
                if section.auto_header_word_count > 0:
                    chapter_excluded_word_ranges.append((
                        chapter_word_cursor,
                        chapter_word_cursor + section.auto_header_word_count,
                    ))
                # Section-local pre-merge total (used only for the
                # legacy `cp_earning_word_count` field; the canonical
                # consumer `_load_cp_words_per_chapter` uses the merged
                # `excluded_word_ranges` instead).
                if section.counts_for_cp:
                    cp_words += (
                        section.word_count
                        - section.author_note_word_count
                        - section.auto_header_word_count
                    )
                chapter_word_cursor += section.word_count
                if section.confidence == "low":
                    low_confidence_count += 1
                    flagged.append((c["chapter_num"], header or "(implicit)",
                                    section.classification_reason))

                # If this is the perks footer, extract the perk list
                if header and header.lower().startswith("jumpchain abilities"):
                    perks = _extract_perks_from_section(section_html)
                    if perks:
                        perk_records.append({
                            "chapter_num": c["chapter_num"],
                            "chapter_full_title": c["full_title"],
                            "epub_href": href,
                            "perks": perks,
                        })

            section_records.append(ChapterSections(
                chapter_num=c["chapter_num"],
                full_title=c["full_title"],
                epub_href=href,
                total_word_count=total_words,
                cp_earning_word_count=cp_words,
                sections=sections,
                excluded_word_ranges=_merge_word_ranges(chapter_excluded_word_ranges),
            ))

    orphan_an = sorted(set(curated_an.keys()) - consumed_an_keys)
    if orphan_an:
        raise SystemExit(
            "data/manual/author_notes.json references chapter/section "
            f"keys not seen during extraction: {orphan_an}. The curated "
            "file is stale; remove or relocate those entries."
        )

    # Aggregate stats
    total_sections = sum(len(r.sections) for r in section_records)
    cp_total = sum(r.cp_earning_word_count for r in section_records)
    total_total = sum(r.total_word_count for r in section_records)
    by_class: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for r in section_records:
        for s in r.sections:
            by_class[s.classification] = by_class.get(s.classification, 0) + 1
            by_confidence[s.confidence] = by_confidence.get(s.confidence, 0) + 1

    write_validated_json(
        OUT_SECTIONS,
        {
            "_source": "Walked data/raw/Brocktons_Celestial_Forge.epub chapter HTML",
            "_count": len(section_records),
            "_total_sections": total_sections,
            "_classification_distribution": by_class,
            "_confidence_distribution": by_confidence,
            "_total_words": total_total,
            "_cp_earning_words": cp_total,
            "_note": (
                "Each section is classified as MC (counts toward CP), "
                "non_mc_perks/non_mc_meta (perk listings, author notes), "
                "or non_mc_other_pov (Preamble/Addendum/Interlude from a "
                "non-Joe character, PHO posts, news articles, meeting "
                "reports). Low-confidence sections are surfaced for "
                "manual review."
            ),
            "chapters": [asdict(r) for r in section_records],
        },
        "chapter_sections",
    )

    n_perks = sum(len(r["perks"]) for r in perk_records)
    write_validated_json(
        OUT_PERKS,
        {
            "_source": "Extracted from each chapter's 'Jumpchain abilities this chapter:' footer",
            "_count": len(perk_records),
            "_total_perks": n_perks,
            "_note": (
                "Per-chapter perk listings as written by the author in the "
                "chapter footer. Useful for cross-validating obtained_perks.json "
                "and filling catalog gaps with author-canonical names + costs."
            ),
            "chapters": perk_records,
        },
        "extracted_perks",
    )

    print(f"wrote {OUT_SECTIONS.relative_to(ROOT)}: "
          f"{len(section_records)} chapters, {total_sections} sections")
    print(f"  classifications: {by_class}")
    print(f"  confidence:      {by_confidence}")
    print(f"  cp-earning words: {cp_total:,} of {total_total:,} "
          f"({cp_total / total_total:.0%})")
    print(f"wrote {OUT_PERKS.relative_to(ROOT)}: "
          f"{len(perk_records)} chapters with footer, {n_perks} perks total")

    if flagged:
        print(f"\nlow-confidence sections ({len(flagged)}, top 10):")
        for ch, hdr, reason in flagged[:10]:
            print(f"  ch {ch:>5s}  [{hdr[:35]:35s}]  {reason}")


if __name__ == "__main__":
    main()
