"""Candidate passage selection for the BCF annotation pipeline.

Picks passages to label next from existing derived data.  The primary
strategy for Phase 1 is ``event_focused`` (sources 1 and 2 from the
playbook).

See docs/local_nlp_annotation_playbook.md §"Candidate selection".
"""

from __future__ import annotations

import html.parser
import json
import random
import warnings
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Candidate dataclass
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """One candidate passage for annotation."""

    passage_id: str
    chapter_num: str
    section_index: int
    epub_char_start: int
    """For predicted_roll candidates this is a PER-CHAPTER RAW-HTML offset
    (consistent with how predicted_char_offset is computed by
    scripts/find_text_backed_rolls.py against a single chapter's HTML).
    For regex_anchor candidates this is a whole-EPUB plain-text offset."""
    epub_char_end: int
    """See epub_char_start for offset interpretation notes."""
    text: str
    source: str  # "predicted_roll" | "regex_anchor" | "section_first_chars" | ...
    roll_context: Optional[dict] = field(default=None)
    """Per-roll context from roll_resolutions.json.  Set for predicted_roll
    candidates; None for regex_anchor and section_first_chars sources."""
    chapter_title: str = ""
    """Full chapter title from chapters.json, e.g. ``"39 Set Up - Addendum Kenta"``."""
    section_header: str = ""
    """Section header from chapter_sections.json, e.g. ``"Addendum Kenta"``.
    Empty string when the section has no explicit header (often the case for
    the chapter's primary Joe-POV section)."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_WORDS_WINDOW = 250          # ±250 words around an event anchor
_CHARS_WINDOW = _WORDS_WINDOW * 6  # rough char approximation (avg ~6 chars/word)
_FIRST_CHARS_WINDOW = 3000   # fallback window from section.sample


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class _StripParser(html.parser.HTMLParser):
    """Minimal HTML tag stripper — returns concatenated text data nodes."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def _load_chapter_sections(derived_dir: Path) -> dict[str, list[dict]]:
    """Return mapping chapter_num → list[section_dict]."""
    raw = _read_json(derived_dir / "chapter_sections.json")
    assert isinstance(raw, dict)
    chapters: list[dict] = raw["chapters"]
    result: dict[str, list[dict]] = {}
    for ch in chapters:
        result[str(ch["chapter_num"])] = ch["sections"]
    return result


def _load_chapter_titles(derived_dir: Path) -> dict[str, str]:
    """Return mapping chapter_num → full_title from chapters.json.

    Returns ``{}`` if the file is missing or malformed.
    """
    path = derived_dir / "chapters.json"
    if not path.exists():
        return {}
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for ch in raw.get("chapters", []) or []:
        cn = str(ch.get("chapter_num", ""))
        title = str(ch.get("full_title", "") or "")
        if cn:
            result[cn] = title
    return result


def _load_chapter_href_map(derived_dir: Path) -> dict[str, str]:
    """Return mapping chapter_num → epub_href from chapter_sections.json.

    epub_href values are bare filenames (e.g. "chap_28.xhtml") that sit
    inside the EPUB's "EPUB/" directory.  Returns an empty dict (with a
    warning) when the file is missing or the field is absent.
    """
    path = derived_dir / "chapter_sections.json"
    if not path.exists():
        warnings.warn(
            f"chapter_sections.json not found at {path}. "
            "Per-chapter HTML extraction unavailable for predicted_roll candidates.",
            stacklevel=4,
        )
        return {}
    raw = _read_json(path)
    assert isinstance(raw, dict)
    result: dict[str, str] = {}
    for ch in raw.get("chapters", []):
        href = ch.get("epub_href")
        if href:
            result[str(ch["chapter_num"])] = href
    return result


def _read_chapter_html_raw(epub_path: Path, epub_href: str) -> Optional[str]:
    """Read the raw HTML/XHTML for a single chapter from the EPUB.

    *epub_href* is the bare filename (e.g. "chap_28.xhtml"); the function
    tries both "EPUB/<href>" and "<href>" as zip member paths.

    Returns None (with a warning) if the file cannot be read.

    NOTE: This returns the *raw HTML* string, not plain text.  The
    ``predicted_char_offset`` field in roll_resolutions.json is computed by
    ``scripts/find_text_backed_rolls.py`` against the raw HTML (it indexes
    into the same string returned by ``zf.read(...).decode("utf-8")``), so
    any slice that uses that offset must operate in raw-HTML coordinates.
    Strip HTML *after* slicing to render plain text for display.
    """
    try:
        with zipfile.ZipFile(epub_path) as zf:
            # Try the canonical EPUB subdirectory first, then root-relative.
            for candidate_path in (f"EPUB/{epub_href}", epub_href):
                try:
                    return zf.read(candidate_path).decode("utf-8", errors="replace")
                except KeyError:
                    continue
        warnings.warn(
            f"Chapter file {epub_href!r} not found in {epub_path}. "
            "Falling back to section sample for this candidate.",
            stacklevel=4,
        )
        return None
    except Exception as exc:
        warnings.warn(
            f"Could not read chapter {epub_href!r} from {epub_path}: {exc}. "
            "Falling back to section sample for this candidate.",
            stacklevel=4,
        )
        return None


def _strip_html(raw_html: str) -> str:
    """Strip HTML tags and return concatenated text data nodes."""
    parser = _StripParser()
    parser.feed(raw_html)
    return parser.text()


def _load_roll_resolutions(derived_dir: Path) -> dict[int, dict]:
    """Load roll_resolutions.json and return a dict keyed by roll_number.

    Returns an empty dict (with a warning) if the file is missing, so that
    callers degrade gracefully without crashing.
    """
    path = derived_dir / "roll_resolutions.json"
    if not path.exists():
        warnings.warn(
            f"roll_resolutions.json not found at {path}. "
            "roll_context will be None for all predicted_roll candidates.",
            stacklevel=4,
        )
        return {}
    raw = _read_json(path)
    assert isinstance(raw, dict)
    rolls: list[dict] = raw.get("rolls", [])
    return {int(r["roll_number"]): r for r in rolls}


def _load_regex_locations(derived_dir: Path) -> list[dict]:
    raw = _read_json(derived_dir / "roll_locations_regex.json")
    assert isinstance(raw, dict)
    return list(raw["locations"])  # type: ignore[arg-type]


def _read_epub_text(epub_path: Path) -> Optional[str]:
    """Extract plain text from EPUB (concatenated HTML bodies, stripped).

    Concatenates ALL HTML/XHTML files in sorted order to produce a single
    whole-EPUB string.  The resulting offsets are whole-EPUB-relative and are
    used exclusively by the regex_anchor path in ``_iter_event_focused``.

    Returns None if the EPUB cannot be read.  Requires only stdlib.
    """
    try:
        parts: list[str] = []
        with zipfile.ZipFile(epub_path) as zf:
            names = sorted(
                [n for n in zf.namelist() if n.endswith(".xhtml") or n.endswith(".html")],
            )
            for name in names:
                raw_html = zf.read(name).decode("utf-8", errors="replace")
                parser = _StripParser()
                parser.feed(raw_html)
                parts.append(parser.text())

        return "".join(parts)
    except Exception as exc:
        warnings.warn(
            f"Could not read EPUB at {epub_path}: {exc}. "
            "Full-prose passages unavailable; will fall back to section first_chars.",
            stacklevel=4,
        )
        return None


def _passage_id(chapter_num: str, counter: dict[str, int]) -> str:
    idx = counter.get(chapter_num, 0)
    counter[chapter_num] = idx + 1
    return f"ch{chapter_num}_p{idx}"


def _window_from_epub(
    epub_text: str,
    char_offset: int,
    half_window: int = _CHARS_WINDOW,
) -> tuple[int, int]:
    """Return (start, end) char offsets for a ±window around char_offset."""
    start = max(0, char_offset - half_window)
    end = min(len(epub_text), char_offset + half_window)
    return start, end


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _iter_event_focused(
    derived_dir: Path,
    epub_path: Optional[Path],
    epub_text: Optional[str],
    counter: dict[str, int],
    rng: random.Random,
    limit: Optional[int],
) -> Iterator[Candidate]:
    """Sources 1+2: predicted-roll positions and regex anchors.

    *epub_text* is the whole-EPUB concatenated plain text used exclusively
    for the regex_anchor path (its offsets are whole-EPUB-relative).

    *epub_path* is the raw EPUB zip, used to read individual chapter files
    for the predicted_roll path (predicted_char_offset is per-chapter).
    """
    roll_resolutions = _load_roll_resolutions(derived_dir)
    # Use the resolution records directly as the roll list (they contain
    # predicted_char_offset, anchor_string, chapter_num, etc.)
    rolls = list(roll_resolutions.values())
    regex_locs = _load_regex_locations(derived_dir)

    # Shuffle each list independently, then interleave so we alternate sources
    rng.shuffle(rolls)
    rng.shuffle(regex_locs)

    yielded = 0

    # Helper: build a Candidate from a roll_resolutions record
    chapter_sections = _load_chapter_sections(derived_dir)
    # chapter_num → epub_href (e.g. "chap_28.xhtml"), loaded once for all rolls.
    chapter_href_map = _load_chapter_href_map(derived_dir)
    # chapter_num → full title (e.g. "39 Set Up - Addendum Kenta")
    chapter_titles = _load_chapter_titles(derived_dir)

    def _section_header(ch_num: str, sec_idx: int) -> str:
        """Return the section's header string from chapter_sections.json,
        or ``""`` if missing/None."""
        sections = chapter_sections.get(str(ch_num), [])
        if 0 <= sec_idx < len(sections):
            hdr = sections[sec_idx].get("header")
            return str(hdr) if hdr else ""
        return ""

    def _candidate_from_roll(res: dict) -> Optional[Candidate]:
        ch_num = str(res["chapter_num"])
        # predicted_char_offset is a PER-CHAPTER RAW-HTML offset, as computed
        # by scripts/find_text_backed_rolls.py against the individual chapter's
        # raw HTML file (the same string returned by zf.read(...).decode("utf-8")).
        # We slice raw HTML at this offset and strip tags afterward to render
        # plain text — the older approach (strip first, slice second) used a
        # different coordinate system and silently fell back for ~74 rolls
        # where the predicted offset landed past the plain-text length.
        char_offset: int = int(res["predicted_char_offset"])
        sec_idx: int = int(res.get("section_index", 0))

        # Build roll_context regardless of text-extraction path.
        # outstanding_perks_with_cost_gt_banked can be very long; truncate
        # to the top 5 by ascending cost to keep prompt size reasonable.
        outstanding_all: list[dict] = res.get("outstanding_perks_with_cost_gt_banked", []) or []
        outstanding_top5 = sorted(outstanding_all, key=lambda p: p.get("cost", 0))[:5]
        roll_ctx: Optional[dict] = {
            "roll_number": res.get("roll_number"),
            "chapter_num": ch_num,
            "section_index": sec_idx,
            "predicted_char_offset": char_offset,
            "anchor_string": res.get("anchor_string"),
            "banked_at_roll": res.get("banked_at_roll"),
            "banked_at_roll_source": res.get("banked_at_roll_source"),
            "curator_chapter_num": res.get("curator_chapter_num"),
            "chapter_attribution_disagreement": res.get("chapter_attribution_disagreement", False),
            "curator_outcome": res.get("curator_outcome"),
            "curator_perk_name": res.get("curator_perk_name"),
            "curator_constellation": res.get("curator_constellation"),
            "curator_cost": res.get("curator_cost"),
            "curator_free_associated_perks": res.get("curator_free_associated_perks"),
            "chapter_acquired_perks_in_order": res.get("chapter_acquired_perks_in_order"),
            "outstanding_perks_with_cost_gt_banked": outstanding_top5,
            "constellations_known_by_joe": res.get("constellations_known_by_joe"),
        }

        # --- Preferred path: read the individual chapter's raw HTML from the
        # EPUB, slice in raw-HTML coordinates around the predicted offset,
        # then strip tags to render plain text. ---
        epub_href = chapter_href_map.get(ch_num)
        if epub_path is not None and epub_href is not None:
            chapter_html = _read_chapter_html_raw(epub_path, epub_href)
            if chapter_html is not None:
                if 0 <= char_offset <= len(chapter_html):
                    start, end = _window_from_epub(chapter_html, char_offset)
                    text = _strip_html(chapter_html[start:end]).strip()
                    if text:
                        pid = _passage_id(ch_num, counter)
                        return Candidate(
                            passage_id=pid,
                            chapter_num=ch_num,
                            section_index=sec_idx,
                            # epub_char_start/end are per-chapter raw-HTML offsets.
                            epub_char_start=start,
                            epub_char_end=end,
                            text=text,
                            source="predicted_roll",
                            roll_context=roll_ctx,
                            chapter_title=chapter_titles.get(ch_num, ""),
                            section_header=_section_header(ch_num, sec_idx),
                        )

        # --- Fallback: use the section's sample text. ---
        # Reached when: epub_path is None, epub_href is not found,
        # _read_chapter_html_raw fails, or offset is out of range.  Even on
        # this path we keep the *full* roll_ctx so the LLM still sees the
        # chapter's curator outcome, perk list, banked CP, anchor_string,
        # and known constellations — the only thing we lose is the prose
        # window centered on the predicted offset.
        sections = chapter_sections.get(ch_num, [])
        if not sections:
            return None
        sec = sections[0]
        sample: str = sec.get("sample", "")
        text = sample[:_FIRST_CHARS_WINDOW]
        if not text:
            return None
        start = 0
        end = len(text)
        pid = _passage_id(ch_num, counter)
        return Candidate(
            passage_id=pid,
            chapter_num=ch_num,
            section_index=sec_idx,
            epub_char_start=start,
            epub_char_end=end,
            text=text,
            source="section_first_chars",
            roll_context=roll_ctx,
            chapter_title=chapter_titles.get(ch_num, ""),
            section_header=_section_header(ch_num, sec_idx),
        )

    def _candidate_from_regex(loc: dict) -> Optional[Candidate]:
        ch_num = str(loc["chapter_num"])
        match_offset: int = int(loc.get("match_offset", 0))
        section_index: int = int(loc.get("section_index", 0))

        if epub_text is not None:
            start, end = _window_from_epub(epub_text, match_offset)
            text = epub_text[start:end].strip()
            source = "regex_anchor"
        else:
            sections = chapter_sections.get(ch_num, [])
            if section_index < len(sections):
                sec = sections[section_index]
            elif sections:
                sec = sections[0]
            else:
                return None
            context: str = loc.get("context", sec.get("sample", ""))
            # The `context` field in roll_locations_regex.json wraps the
            # matched anchor phrase in `[[...]]` for human-readable display.
            # Strip those markers so the LLM/labeler sees clean prose.
            context = context.replace("[[", "").replace("]]", "")
            text = context[:_FIRST_CHARS_WINDOW]
            start = 0
            end = len(text)
            source = "section_first_chars"

        pid = _passage_id(ch_num, counter)
        return Candidate(
            passage_id=pid,
            chapter_num=ch_num,
            section_index=section_index,
            epub_char_start=start,
            epub_char_end=end,
            text=text,
            source=source,
            chapter_title=chapter_titles.get(ch_num, ""),
            section_header=_section_header(ch_num, section_index),
        )

    # Interleave the two sources
    roll_iter = iter(rolls)
    regex_iter = iter(regex_locs)
    roll_done = False
    regex_done = False

    while True:
        if limit is not None and yielded >= limit:
            return

        if not roll_done:
            try:
                roll = next(roll_iter)
                c = _candidate_from_roll(roll)
                if c is not None and c.text:
                    yield c
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        return
            except StopIteration:
                roll_done = True

        if not regex_done:
            try:
                loc = next(regex_iter)
                c = _candidate_from_regex(loc)
                if c is not None and c.text:
                    yield c
                    yielded += 1
                    if limit is not None and yielded >= limit:
                        return
            except StopIteration:
                regex_done = True

        if roll_done and regex_done:
            return


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def iter_candidates(
    *,
    strategy: str = "event_focused",
    epub_path: Optional[Path] = None,
    derived_dir: Path = Path("data/derived"),
    seed: int = 1337,
    limit: Optional[int] = None,
) -> Iterator[Candidate]:
    """Yield annotation candidates according to *strategy*.

    Parameters
    ----------
    strategy:
        Selection strategy.  Only ``"event_focused"`` is fully implemented
        for Phase 1.  ``"balanced"``, ``"low_confidence"``, and
        ``"coverage_gap"`` raise ``NotImplementedError``.
    epub_path:
        Path to the EPUB file.  If *None* or the file doesn't exist, the
        generator falls back to ``chapter_sections.json``'s ``sample``
        field and emits a warning.
    derived_dir:
        Directory containing ``chapter_sections.json``,
        ``predicted_rolls.json``, and ``roll_locations_regex.json``.
    seed:
        RNG seed for reproducible candidate ordering.
    limit:
        If given, stop after yielding this many candidates.

    Yields
    ------
    Candidate
    """
    rng = random.Random(seed)

    epub_text: Optional[str] = None
    if epub_path is not None:
        if epub_path.exists():
            epub_text = _read_epub_text(epub_path)
        else:
            warnings.warn(
                f"EPUB not found at {epub_path}. "
                "Full-prose passages unavailable; will fall back to section first_chars. "
                "Provide --epub <path> to enable full-passage extraction.",
                stacklevel=2,
            )

    counter: dict[str, int] = {}

    if strategy == "event_focused":
        yield from _iter_event_focused(
            derived_dir=derived_dir,
            epub_path=epub_path if (epub_path is not None and epub_path.exists()) else None,
            epub_text=epub_text,
            counter=counter,
            rng=rng,
            limit=limit,
        )
    elif strategy == "balanced":
        raise NotImplementedError("phase 2/3 strategy: balanced")
    elif strategy == "low_confidence":
        raise NotImplementedError("phase 2/3 strategy: low_confidence")
    elif strategy == "coverage_gap":
        raise NotImplementedError("phase 2/3 strategy: coverage_gap")
    else:
        raise ValueError(
            f"Unknown strategy {strategy!r}. "
            "Valid values: 'event_focused', 'balanced', 'low_confidence', 'coverage_gap'."
        )


__all__ = ["Candidate", "iter_candidates"]
