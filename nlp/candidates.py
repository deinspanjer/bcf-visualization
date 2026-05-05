"""Candidate passage selection for the BCF annotation pipeline.

Picks passages to label next from existing derived data.  The primary
strategy for Phase 1 is ``event_focused`` (sources 1 and 2 from the
playbook).

See docs/local_nlp_annotation_playbook.md §"Candidate selection".
"""

from __future__ import annotations

import json
import random
import warnings
from dataclasses import dataclass
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
    epub_char_end: int
    text: str
    source: str  # "predicted_roll" | "regex_anchor" | "section_first_chars" | ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_WORDS_WINDOW = 250          # ±250 words around an event anchor
_CHARS_WINDOW = _WORDS_WINDOW * 6  # rough char approximation (avg ~6 chars/word)
_FIRST_CHARS_WINDOW = 3000   # fallback window from section.sample


def _read_json(path: Path) -> object:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_chapter_sections(derived_dir: Path) -> dict[str, list[dict]]:
    """Return mapping chapter_num → list[section_dict]."""
    raw = _read_json(derived_dir / "chapter_sections.json")
    assert isinstance(raw, dict)
    chapters: list[dict] = raw["chapters"]
    result: dict[str, list[dict]] = {}
    for ch in chapters:
        result[str(ch["chapter_num"])] = ch["sections"]
    return result


def _load_predicted_rolls(derived_dir: Path) -> list[dict]:
    raw = _read_json(derived_dir / "predicted_rolls.json")
    assert isinstance(raw, dict)
    return list(raw["predicted"])  # type: ignore[arg-type]


def _load_regex_locations(derived_dir: Path) -> list[dict]:
    raw = _read_json(derived_dir / "roll_locations_regex.json")
    assert isinstance(raw, dict)
    return list(raw["locations"])  # type: ignore[arg-type]


def _read_epub_text(epub_path: Path) -> Optional[str]:
    """Extract plain text from EPUB (concatenated HTML bodies, stripped).

    Returns None if the EPUB cannot be read.  Requires only stdlib.
    """
    try:
        import zipfile
        import html.parser

        class _StripParser(html.parser.HTMLParser):
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
    epub_text: Optional[str],
    counter: dict[str, int],
    rng: random.Random,
    limit: Optional[int],
) -> Iterator[Candidate]:
    """Sources 1+2: predicted-roll positions and regex anchors."""
    rolls = _load_predicted_rolls(derived_dir)
    regex_locs = _load_regex_locations(derived_dir)

    # Shuffle each list independently, then interleave so we alternate sources
    rolls = list(rolls)
    regex_locs = list(regex_locs)
    rng.shuffle(rolls)
    rng.shuffle(regex_locs)

    yielded = 0

    # Helper: build a Candidate from a word_position (predicted_roll)
    chapter_sections = _load_chapter_sections(derived_dir)

    def _candidate_from_roll(roll: dict) -> Optional[Candidate]:
        ch_num = str(roll["chapter_num"])
        word_pos: int = int(roll["word_position"])

        if epub_text is not None:
            # Approximate word-to-char offset using a simple ratio
            # We don't have a per-chapter char offset map, so we use the word
            # position as a rough char offset (average ~5 chars/word in prose)
            char_est = word_pos * 5
            start, end = _window_from_epub(epub_text, char_est)
            text = epub_text[start:end].strip()
            source = "predicted_roll"
        else:
            # Fall back: use the section's sample text
            sections = chapter_sections.get(ch_num, [])
            if not sections:
                return None
            sec = sections[0]
            sample: str = sec.get("sample", "")
            text = sample[:_FIRST_CHARS_WINDOW]
            start = 0
            end = len(text)
            source = "section_first_chars"

        pid = _passage_id(ch_num, counter)
        return Candidate(
            passage_id=pid,
            chapter_num=ch_num,
            section_index=0,
            epub_char_start=start,
            epub_char_end=end,
            text=text,
            source=source,
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
