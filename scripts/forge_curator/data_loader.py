"""Data loading utilities for the Forge Curator TUI.

Provides per-chapter slices of the derived data files, plus the
plain-text prose for a chapter (extracted from the EPUB and
HTML-stripped). Everything is loaded lazily and cached so chapter
navigation is cheap.

Phase 1 is read-only: no writes are issued from this module.
"""

from __future__ import annotations

import html
import json
import re
import warnings
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from scripts.data_paths import DERIVED, MANUAL, RAW, ROOT

EPUB_PATH = RAW / "Brocktons_Celestial_Forge.epub"

CHAPTER_SECTIONS = DERIVED / "chapter_sections.json"
CHAPTERS = DERIVED / "chapters.json"
ROLL_FACTS = DERIVED / "roll_facts.json"
PREDICTED = DERIVED / "predicted_rolls.json"
CHAPTER_FACTS = DERIVED / "chapter_facts.json"
ROLL_VALIDATION = DERIVED / "roll_validation.json"
OBTAINED_PERKS = DERIVED / "obtained_perks.json"
PERKS_CATALOG = DERIVED / "perks_catalog.json"
ROLL_OUTCOMES = DERIVED / "roll_outcomes.json"
OUTSTANDING_PERKS = DERIVED / "outstanding_perks_by_chapter.json"

CHAPTER_ROLL_OVERRIDES = MANUAL / "chapter_roll_overrides.json"
AUTHOR_NOTES = MANUAL / "author_notes.json"
REGIME_TRANSITIONS = MANUAL / "regime_transitions.json"
HEADER_CORRECTIONS = MANUAL / "header_corrections.json"


# ---------- HTML stripping --------------------------------------------------


class _HtmlStripper(HTMLParser):
    """Tag-stripper that records section break boundaries.

    We collapse consecutive whitespace/newlines into a single newline so
    the rendered prose stays compact, but preserve paragraph breaks.
    """

    BLOCK_TAGS = {
        "p", "div", "section", "article", "header", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "ul", "ol", "blockquote", "pre", "br", "hr",
    }

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"head", "title", "script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"head", "title", "script", "style"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self._skip_depth:
            return
        self._parts.append(html.unescape(f"&#{name};"))

    def text(self) -> str:
        joined = "".join(self._parts)
        # Collapse runs of whitespace except newlines.
        joined = re.sub(r"[ \t]+", " ", joined)
        # Collapse 3+ newlines to 2.
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip("\n ")


def _strip_html(raw: str) -> str:
    s = _HtmlStripper()
    s.feed(raw)
    return s.text()


# ---------- on-disk JSON helpers --------------------------------------------


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


# ---------- public data structures ------------------------------------------


@dataclass
class ChapterMeta:
    chapter_num: str
    full_title: str
    epub_href: str | None
    total_word_count: int
    cp_earning_word_count: int
    sections: list[dict]
    excluded_word_ranges: list[list[int]] = field(default_factory=list)


@dataclass
class ChapterDerived:
    """Per-chapter slice of derived data needed by the stats panel."""

    chapter_num: str
    chapter_facts: dict | None
    roll_facts: list[dict]
    predicted_rolls: list[dict]
    roll_outcomes: list[dict]
    validation: dict | None
    perks: list[dict]
    overrides: dict[str, bool] = field(default_factory=dict)
    """Map override-file name → True if this chapter has an entry."""


@dataclass
class ChapterProse:
    """Prose for a single chapter, plus index annotations."""

    chapter_num: str
    text: str
    """Plain-text prose, newline-separated paragraphs."""
    word_offsets: list[tuple[int, int]]
    """For each word index, (char_start, char_end_exclusive) into ``text``."""
    section_break_word_indices: list[int]
    """Word indices at which section breaks (header rows) begin."""
    implicit_header_word_ranges: list[tuple[int, int]] = field(default_factory=list)
    """Auto-detected header spans: each section's `header` field matched
    against the first words of that section's prose. Excluded from CP
    counts the same way as manual header_corrections entries."""


# ---------- loader ----------------------------------------------------------


class ForgeCuratorData:
    """Lazy, cached access to all data the TUI needs.

    Loads big files once on first access; per-chapter slices are
    computed on demand and cached.
    """

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self._chapter_sections_doc: dict | None = None
        self._chapters_doc: dict | None = None
        self._roll_facts_doc: dict | None = None
        self._predicted_doc: dict | None = None
        self._chapter_facts_doc: dict | None = None
        self._roll_validation_doc: dict | None = None
        self._obtained_doc: dict | None = None
        self._roll_outcomes_doc: dict | None = None
        self._outstanding_doc: dict | None = None
        self._chapter_roll_overrides_doc: dict | None = None
        self._author_notes_doc: dict | None = None
        self._regime_transitions_doc: dict | None = None
        self._header_corrections_doc: dict | None = None
        # Cached per-chapter derived slice and prose.
        self._derived_cache: dict[str, ChapterDerived] = {}
        self._prose_cache: dict[str, ChapterProse] = {}
        self._meta_by_chapter: dict[str, ChapterMeta] | None = None
        self._chapter_order: list[str] | None = None

    def reload_from_disk(self) -> None:
        """Clear loaded JSON/prose slices so future reads use disk state."""
        self._chapter_sections_doc = None
        self._chapters_doc = None
        self._roll_facts_doc = None
        self._predicted_doc = None
        self._chapter_facts_doc = None
        self._roll_validation_doc = None
        self._obtained_doc = None
        self._roll_outcomes_doc = None
        self._outstanding_doc = None
        self._chapter_roll_overrides_doc = None
        self._author_notes_doc = None
        self._regime_transitions_doc = None
        self._header_corrections_doc = None
        self._derived_cache = {}
        self._prose_cache = {}
        self._meta_by_chapter = None
        self._chapter_order = None

    # ----- top-level loaders -----

    @property
    def chapter_sections(self) -> dict:
        if self._chapter_sections_doc is None:
            self._chapter_sections_doc = _read_json(CHAPTER_SECTIONS)
        return self._chapter_sections_doc

    @property
    def chapters(self) -> dict:
        if self._chapters_doc is None:
            self._chapters_doc = _read_json(CHAPTERS)
        return self._chapters_doc

    @property
    def roll_facts(self) -> dict:
        if self._roll_facts_doc is None:
            self._roll_facts_doc = _read_json(ROLL_FACTS)
        return self._roll_facts_doc

    @property
    def predicted(self) -> dict:
        if self._predicted_doc is None:
            self._predicted_doc = _read_json(PREDICTED)
        return self._predicted_doc

    @property
    def chapter_facts(self) -> dict:
        if self._chapter_facts_doc is None:
            self._chapter_facts_doc = _read_json(CHAPTER_FACTS)
        return self._chapter_facts_doc

    @property
    def roll_validation(self) -> dict:
        if self._roll_validation_doc is None:
            self._roll_validation_doc = _read_json(ROLL_VALIDATION)
        return self._roll_validation_doc

    @property
    def obtained_perks(self) -> dict:
        if self._obtained_doc is None:
            self._obtained_doc = _read_json(OBTAINED_PERKS)
        return self._obtained_doc

    @property
    def roll_outcomes(self) -> dict:
        if self._roll_outcomes_doc is None:
            self._roll_outcomes_doc = _read_json(ROLL_OUTCOMES)
        return self._roll_outcomes_doc

    @property
    def outstanding_perks(self) -> dict:
        if self._outstanding_doc is None:
            self._outstanding_doc = _read_json(OUTSTANDING_PERKS)
        return self._outstanding_doc

    @property
    def chapter_roll_overrides(self) -> dict:
        if self._chapter_roll_overrides_doc is None:
            if CHAPTER_ROLL_OVERRIDES.exists():
                self._chapter_roll_overrides_doc = _read_json(CHAPTER_ROLL_OVERRIDES)
            else:
                self._chapter_roll_overrides_doc = {"chapter_roll_overrides": {}}
        return self._chapter_roll_overrides_doc

    @property
    def author_notes(self) -> dict:
        if self._author_notes_doc is None:
            if AUTHOR_NOTES.exists():
                self._author_notes_doc = _read_json(AUTHOR_NOTES)
            else:
                self._author_notes_doc = {"notes": []}
        return self._author_notes_doc

    @property
    def regime_transitions(self) -> dict:
        if self._regime_transitions_doc is None:
            if REGIME_TRANSITIONS.exists():
                self._regime_transitions_doc = _read_json(REGIME_TRANSITIONS)
            else:
                self._regime_transitions_doc = {"transitions": []}
        return self._regime_transitions_doc

    @property
    def header_corrections(self) -> dict:
        if self._header_corrections_doc is None:
            if HEADER_CORRECTIONS.exists():
                self._header_corrections_doc = _read_json(HEADER_CORRECTIONS)
            else:
                self._header_corrections_doc = {"corrections": []}
        return self._header_corrections_doc

    # ----- chapter metadata -----

    def _build_meta(self) -> None:
        meta: dict[str, ChapterMeta] = {}
        order: list[str] = []
        # chapter_sections.json carries the parser's structure but the
        # CP-eligibility flag there is pre-classification. chapter_facts.json
        # carries the post-classification flag. Merge: prefer
        # chapter_facts's per-section ``counts_for_cp`` when available.
        cf_by_chapter = {
            str(c.get("chapter_num")): c
            for c in self.chapter_facts.get("chapters", [])
        }
        for c in self.chapter_sections.get("chapters", []):
            cn = str(c["chapter_num"])
            sections = list(c.get("sections") or [])
            cf_chapter = cf_by_chapter.get(cn) or {}
            cf_sections = cf_chapter.get("sections") or []
            # Overlay counts_for_cp from chapter_facts onto each section.
            merged_sections: list[dict] = []
            for i, sec in enumerate(sections):
                merged = dict(sec)
                if i < len(cf_sections):
                    merged["counts_for_cp"] = bool(
                        cf_sections[i].get("counts_for_cp", merged.get("counts_for_cp", True))
                    )
                merged_sections.append(merged)
            meta[cn] = ChapterMeta(
                chapter_num=cn,
                full_title=c.get("full_title", cn),
                epub_href=c.get("epub_href"),
                total_word_count=int(c.get("total_word_count") or 0),
                cp_earning_word_count=int(
                    cf_chapter.get("cp_earning_word_count")
                    if cf_chapter.get("cp_earning_word_count") is not None
                    else c.get("cp_earning_word_count") or 0
                ),
                sections=merged_sections,
                excluded_word_ranges=list(c.get("excluded_word_ranges") or []),
            )
            order.append(cn)
        self._meta_by_chapter = meta
        self._chapter_order = order

    @property
    def meta_by_chapter(self) -> dict[str, ChapterMeta]:
        if self._meta_by_chapter is None:
            self._build_meta()
        assert self._meta_by_chapter is not None
        return self._meta_by_chapter

    @property
    def chapter_order(self) -> list[str]:
        if self._chapter_order is None:
            self._build_meta()
        assert self._chapter_order is not None
        return self._chapter_order

    def chapter_meta(self, chapter_num: str) -> ChapterMeta:
        meta = self.meta_by_chapter.get(str(chapter_num))
        if meta is None:
            raise KeyError(f"unknown chapter {chapter_num!r}")
        return meta

    # ----- per-chapter derived slice -----

    def chapter_derived(self, chapter_num: str) -> ChapterDerived:
        cn = str(chapter_num)
        if cn in self._derived_cache:
            return self._derived_cache[cn]

        chapter_facts_for = next(
            (c for c in self.chapter_facts.get("chapters", [])
             if str(c.get("chapter_num")) == cn),
            None,
        )

        rf = [
            r for r in self.roll_facts.get("rolls", [])
            if (
                str(r.get("chapter_num")) == cn
                or str(r.get("mechanical_chapter_num")) == cn
                or str(r.get("display_chapter_num")) == cn
                or cn in {str(ch) for ch in r.get("visible_chapter_nums") or []}
            )
        ]
        rf.sort(key=lambda r: (
            _chapter_roll_sort_word(cn, r),
            r.get("roll_number") or r.get("roll_sequence_in_chapter") or 0,
        ))

        preds = [
            p for p in self.predicted.get("predicted", [])
            if str(p.get("chapter_num")) == cn
        ]
        preds.sort(key=lambda p: p.get("word_position") or 0)

        outs = [
            o for o in self.roll_outcomes.get("rolls", [])
            if str(o.get("chapter_num")) == cn
        ]

        validation = (
            (chapter_facts_for or {}).get("model_validation")
            if chapter_facts_for else None
        ) or {"status": "unknown"}

        perks = [
            p for p in self.obtained_perks.get("perks", [])
            if str(p.get("chapter_num")) == cn
        ]
        perks.sort(key=lambda p: p.get("epub_sequence", 0))

        overrides_present: dict[str, bool] = {}
        cro = self.chapter_roll_overrides.get("chapter_roll_overrides") or {}
        overrides_present["chapter_roll_overrides"] = cn in cro
        an_doc = self.author_notes
        an_list = an_doc.get("author_notes") or an_doc.get("notes") or []
        an_entries = [n for n in an_list if str(n.get("chapter_num")) == cn]
        overrides_present["author_notes"] = bool(an_entries)
        rt = self.regime_transitions.get("transitions") or []
        overrides_present["regime_transitions"] = any(
            str(t.get("chapter_num")) == cn for t in rt
        )
        hc = self.header_corrections.get("corrections") or []
        overrides_present["header_corrections"] = any(
            str(t.get("chapter_num")) == cn for t in hc
        )

        derived = ChapterDerived(
            chapter_num=cn,
            chapter_facts=chapter_facts_for,
            roll_facts=rf,
            predicted_rolls=preds,
            roll_outcomes=outs,
            validation=validation,
            perks=perks,
            overrides=overrides_present,
        )
        self._derived_cache[cn] = derived
        return derived

    # ----- prose loading -----

    def chapter_prose(self, chapter_num: str) -> ChapterProse:
        cn = str(chapter_num)
        if cn in self._prose_cache:
            return self._prose_cache[cn]

        meta = self.chapter_meta(cn)
        text_pieces: list[str] = []
        section_break_word_offsets: list[int] = []
        running_words = 0

        # If we have an epub_href for the chapter, prefer the EPUB raw HTML.
        # Otherwise fall back to nothing (chapter prose is missing).
        if meta.epub_href and EPUB_PATH.exists():
            raw_html = _read_chapter_html(EPUB_PATH, meta.epub_href)
            if raw_html is not None:
                stripped = _strip_html(raw_html)
                # Split at section breaks: each section in chapter_sections
                # corresponds to one header within the file. Without
                # per-section text on disk we treat the whole chapter as
                # one section flow plus header markers from the section
                # list. This is good enough for Phase 1 visual gutter
                # indicators; Phase 2 work may refine alignment.
                text_pieces.append(stripped)
                # Mark section break word positions roughly by the section
                # cumulative word counts.
                cum = 0
                for i, sec in enumerate(meta.sections):
                    if i > 0:  # first section begins at offset 0
                        section_break_word_offsets.append(cum)
                    cum += int(sec.get("word_count") or 0)

        if not text_pieces:
            # Fallback: synthesise text from section samples (rare; only if
            # EPUB unavailable). Each section's `sample` is short, but
            # better than nothing for the read-only viewer.
            cum = 0
            for i, sec in enumerate(meta.sections):
                if i > 0:
                    section_break_word_offsets.append(cum)
                hdr = sec.get("header") or ""
                sample = sec.get("sample") or ""
                piece = (hdr + "\n" + sample).strip()
                if piece:
                    text_pieces.append(piece)
                cum += int(sec.get("word_count") or 0)

        text = "\n\n".join(text_pieces) if len(text_pieces) > 1 else (text_pieces[0] if text_pieces else "")
        word_offsets = _compute_word_offsets(text)
        running_words = len(word_offsets)

        # Clamp section breaks to actual word count (in case our offsets
        # disagree with chapter_sections by a small margin).
        section_break_word_offsets = [
            min(idx, running_words) for idx in section_break_word_offsets
        ]

        # Auto-header word ranges come from the canonical
        # ``auto_header_word_count`` written by extract_chapter_sections.
        # We map each section's count to a leading word range.
        implicit_headers: list[tuple[int, int]] = []
        cum = 0
        for sec in meta.sections:
            wc = int(sec.get("word_count") or 0)
            ahc = int(sec.get("auto_header_word_count") or 0)
            if ahc > 0 and cum + ahc <= len(word_offsets):
                implicit_headers.append((cum, cum + ahc))
            cum += wc
        prose = ChapterProse(
            chapter_num=cn,
            text=text,
            word_offsets=word_offsets,
            section_break_word_indices=section_break_word_offsets,
            implicit_header_word_ranges=implicit_headers,
        )
        self._prose_cache[cn] = prose
        return prose


# ---------- helpers --------------------------------------------------------


def _read_chapter_html(epub_path: Path, epub_href: str) -> str | None:
    try:
        with zipfile.ZipFile(epub_path) as zf:
            for candidate in (f"EPUB/{epub_href}", epub_href):
                try:
                    return zf.read(candidate).decode("utf-8", errors="replace")
                except KeyError:
                    continue
    except Exception as exc:  # pragma: no cover
        warnings.warn(
            f"forge_curator: could not read {epub_href!r} from "
            f"{epub_path}: {exc}",
            stacklevel=2,
        )
    return None


def _chapter_roll_sort_word(chapter_num: str, roll: dict) -> int:
    cn = str(chapter_num)
    if (
        str(roll.get("display_chapter_num")) == cn
        and roll.get("display_word_position") is not None
    ):
        return int(roll["display_word_position"])
    if (
        str(roll.get("mechanical_chapter_num")) == cn
        and roll.get("mechanical_word_position") is not None
    ):
        return int(roll["mechanical_word_position"])
    if roll.get("word_position") is not None:
        return int(roll["word_position"])
    return 0


_WORD_RE = re.compile(r"\S+")


def _compute_word_offsets(text: str) -> list[tuple[int, int]]:
    """Return `(start, end)` char offsets for each whitespace-delimited word."""
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


# Auto-header detection is now canonical in
# ``scripts/extract_chapter_sections.py``; the per-section
# ``auto_header_word_count`` field is read directly. The local
# detection helper that used to live here has been removed to enforce
# the single-source-of-truth rule.
