"""Parse the Celestial Forge Fandom Wiki timeline page into a structured
in-world timeline of dated event bullets.

The wiki page is a one-off HTML download saved at
`data/raw/wiki/bcf_wiki_timeline.html`. Its Timeline section is a flat
sequence of `<p><b>{date}</b></p>` headings followed by `<ul>` lists
of event-bullet `<li>` items.

Output: `data/derived/timeline_wiki.json`.

Chapter linkage
---------------

We do NOT attempt to derive per-bullet chapter numbers here. An earlier
attempt at substring-matching catalog perk names against bullet text
produced too many false positives (the wiki uses perk-derived names as
references to existing characters/locations, e.g. "Garment Gloves
patrols around the Docks" or "in his Workshop"). The `--match-perks`
flag still runs the strict acquisition-context matcher and emits the
candidates under `match_candidates` for diagnostic purposes only —
treat those as low-confidence hints, not anchors.

The wiki header notes coverage as "Up to date through 104.2 Interlude
Rachel", giving us a coarse end-anchor (2011-04-28 ≈ ch 104.2). The
start of the story (2011-04-08) corresponds to chapter 1. Reliable
intermediate chapter→date anchors should be built by a separate, more
focused tool (manual curation or perk-density alignment).

Notes
-----

* Wiki coverage is April 1-28, 2011 (19 dated entries, 214 bullets).
* We carry the year (2011) forward when entries omit it. Only the
  first wiki entry mentions a year explicitly.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_HTML = ROOT / "data" / "raw" / "wiki" / "bcf_wiki_timeline.html"
DEFAULT_PERKS = ROOT / "data" / "derived" / "obtained_perks.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "timeline_wiki.json"

SCHEMA_VERSION = 1

# The Timeline section is bounded by two <h2> tags. We anchor by the
# heading text rather than byte offsets so re-saves of the page don't
# silently desync.
_TIMELINE_SECTION_RE = re.compile(
    r'<h2[^>]*>\s*<span[^>]*id="Timeline".*?</h2>(.*?)<h2',
    re.S | re.I,
)
# Fallback: any h2 whose text contains "Timeline".
_TIMELINE_SECTION_RE_FALLBACK = re.compile(
    r'<h2[^>]*>(?:(?!</h2>).)*Timeline(?:(?!</h2>).)*</h2>(.*?)<h2',
    re.S | re.I,
)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_DATE_RE = re.compile(
    r'^\s*'
    r'(?:(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat)[a-z]*,?\s+)?'
    r'(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+'
    r'(?P<day>\d{1,2})(?:st|nd|rd|th)?'
    r'(?:,?\s+(?P<year>\d{4}))?'
    r'\s*$',
    re.I,
)


def _strip_tags(s: str) -> str:
    return unescape(re.sub(r'<[^>]+>', '', s)).strip()


def _parse_date(text: str, fallback_year: int) -> tuple[str, int]:
    """Return (iso_date, year_used). Raises ValueError on failure."""
    m = _DATE_RE.match(text)
    if not m:
        raise ValueError(f"unparseable date heading: {text!r}")
    month = _MONTHS[m.group("month").lower()]
    day = int(m.group("day"))
    year = int(m.group("year")) if m.group("year") else fallback_year
    return date(year, month, day).isoformat(), year


def _extract_section(html: str) -> str:
    m = _TIMELINE_SECTION_RE.search(html) or _TIMELINE_SECTION_RE_FALLBACK.search(html)
    if not m:
        raise SystemExit("Could not locate Timeline section in HTML.")
    return m.group(1)


def parse_wiki_dates(html: str) -> list[dict]:
    """Walk the Timeline section and return a list of
    {date_text, in_world_date_iso, events: [str]} entries.
    """
    body = _extract_section(html)

    blocks = list(re.finditer(
        r'<p\b[^>]*>(?P<p>.*?)</p>|<ul\b[^>]*>(?P<ul>.*?)</ul>',
        body, re.S | re.I,
    ))

    entries: list[dict] = []
    current_year = 2011  # safe default: timeline opens in April 2011
    for blk in blocks:
        p_html = blk.group("p")
        ul_html = blk.group("ul")
        if p_html is not None:
            text = _strip_tags(p_html)
            if not text:
                continue
            try:
                iso, current_year = _parse_date(text, current_year)
            except ValueError:
                # Non-date paragraph; if we're inside a date block, treat
                # as a single event line.
                if entries:
                    entries[-1]["events"].append(text)
                continue
            entries.append({
                "date_text": text,
                "in_world_date_iso": iso,
                "events": [],
            })
        elif ul_html is not None and entries:
            for li in re.findall(r'<li\b[^>]*>(.*?)</li>', ul_html, re.S | re.I):
                t = _strip_tags(li)
                if t:
                    entries[-1]["events"].append(t)
    return entries


# ---------------------------------------------------------------------------
# Perk-name matcher
# ---------------------------------------------------------------------------

# Word-boundary regex helper that treats common punctuation as boundaries
# and is case-insensitive. Building a precompiled regex per name would
# be expensive (~500 names) so we do scan-time matching with a single
# pre-built alternation, longest-name-first to bias toward specific
# matches.

_BOUND_LEFT = r'(?<![A-Za-z0-9])'
_BOUND_RIGHT = r'(?![A-Za-z0-9])'


def _build_name_regex(names: list[str]) -> re.Pattern[str]:
    # Sort longest-first so the alternation prefers specific names like
    # "Master Craftsman" over a substring like "Master".
    ordered = sorted(set(names), key=lambda s: (-len(s), s))
    pattern = (
        _BOUND_LEFT
        + r'(?:' + '|'.join(re.escape(n) for n in ordered) + r')'
        + _BOUND_RIGHT
    )
    return re.compile(pattern, re.I)


# Acquisition signals — phrases that strongly imply Joe gained a new
# perk. We only treat a perk-name match as a real acquisition when it
# falls inside the span starting at the signal and extending through the
# rest of the sentence.
_ACQUISITION_SIGNAL_RE = re.compile(
    r'\b('
    r'(?:Joe|Apeiron)\s+(?:acquires?|gains?|obtains?|earns?|receives?|unlocks?)'
    r'|^\s*(?:Acquires?|Gains?|Obtains?|Receives?)\b'
    r'|first\s+\d+\s*point\s+perk'
    r'|the\s+Forge\s+(?:grants|gives)'
    r'|(?:joins\s+the\s+team)'
    r')',
    re.I | re.M,
)


def _acquisition_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) char spans within `text` where an acquisition
    is being described. The span runs from the signal's start to the end
    of its sentence (next '.', '!', '?' or end-of-text).
    """
    spans: list[tuple[int, int]] = []
    for m in _ACQUISITION_SIGNAL_RE.finditer(text):
        start = m.start()
        # End at next sentence terminator (very loose: '.', '!', '?', or
        # newline) so we don't bleed into unrelated content.
        end_match = re.search(r'[.!?\n]', text[m.end():])
        end = m.end() + end_match.start() + 1 if end_match else len(text)
        spans.append((start, end))
    return spans


def _build_perk_index(perks: list[dict]) -> dict[str, list[dict]]:
    """name (lowercase) -> list of perk acquisitions in epub_sequence order."""
    by_name: dict[str, list[dict]] = defaultdict(list)
    for p in sorted(perks, key=lambda p: p.get("epub_sequence", 0)):
        by_name[p["perk_name"].lower()].append(p)
    return by_name


def match_perks(
    entries: list[dict],
    perks: list[dict],
) -> dict:
    """Walk entries in order and look for perk acquisitions in bullets.

    Only matches inside an "acquisition context" (Joe acquires/gets/...,
    "first N point perk", "joins the team", etc.) are treated as real
    acquisitions, to keep precision high. Even so, this is heuristic
    and lossy — the output is exposed as `match_candidates`, not
    authoritative chapter anchors.

    Returns a dict with summary stats; mutates `entries` to add
    `match_candidates` to each bullet and `candidate_chapter_anchors`
    to each entry.
    """
    name_index = _build_perk_index(perks)
    name_regex = _build_name_regex([p["perk_name"] for p in perks])
    consumed: dict[str, int] = defaultdict(int)  # name_lower -> count consumed

    total_bullets = 0
    bullets_with_match = 0
    matched_perk_count = 0

    for entry in entries:
        anchors_for_entry: list[str] = []
        bullets_out: list[dict] = []
        for bullet_text in entry["events"]:
            total_bullets += 1
            matches: list[dict] = []
            seen_spans: list[tuple[int, int]] = []
            # Only consider perk-name occurrences inside an acquisition
            # context to keep precision high (otherwise references to
            # "Garment Gloves" the character or "Workshop" the location
            # get treated as new acquisitions).
            acq_spans = _acquisition_spans(bullet_text)
            for m in name_regex.finditer(bullet_text):
                span = m.span()
                # Drop matches that aren't inside any acquisition span.
                in_acq = any(
                    a_start <= span[0] and span[1] <= a_end
                    for a_start, a_end in acq_spans
                )
                if not in_acq:
                    continue
                # Skip overlapping matches (longest-first ordering already
                # gives priority to bigger names, but we still need to skip
                # nested smaller ones that would double-count).
                if any(not (span[1] <= s or span[0] >= e) for s, e in seen_spans):
                    continue
                seen_spans.append(span)

                name_lower = m.group(0).lower()
                pool = name_index.get(name_lower) or []
                idx = consumed[name_lower]
                if idx >= len(pool):
                    # All catalog acquisitions of this name already
                    # consumed; record the match anyway but flag it.
                    matches.append({
                        "name": m.group(0),
                        "epub_sequence": None,
                        "chapter_num": None,
                        "exhausted": True,
                    })
                    continue
                acq = pool[idx]
                consumed[name_lower] = idx + 1
                matches.append({
                    "name": acq["perk_name"],
                    "epub_sequence": acq.get("epub_sequence"),
                    "chapter_num": acq.get("chapter_num"),
                    "constellation": acq.get("constellation"),
                })
                if acq.get("chapter_num"):
                    anchors_for_entry.append(acq["chapter_num"])

            if matches:
                bullets_with_match += 1
                matched_perk_count += sum(1 for x in matches if not x.get("exhausted"))
            bullets_out.append({"text": bullet_text, "match_candidates": matches})

        entry["events"] = bullets_out
        unique_anchors = sorted(set(anchors_for_entry), key=_chapter_sort_key)
        entry["candidate_chapter_anchors"] = unique_anchors

    return {
        "total_bullets": total_bullets,
        "bullets_with_match": bullets_with_match,
        "matched_perk_count": matched_perk_count,
        "perks_in_catalog": len(perks),
        "perks_consumed": sum(consumed.values()),
    }


def _chapter_sort_key(c: str) -> tuple[float, str]:
    # Chapter nums are like "8", "104.2"; sort numerically when possible.
    try:
        return (float(c), c)
    except ValueError:
        return (float("inf"), c)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", type=Path, default=DEFAULT_HTML)
    p.add_argument("--perks", type=Path, default=DEFAULT_PERKS)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument(
        "--match-perks",
        action="store_true",
        help="Also attempt heuristic perk-name matching to surface "
        "low-confidence chapter anchor candidates (off by default).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    html = args.html.read_text()
    entries = parse_wiki_dates(html)

    if args.match_perks:
        perks = json.loads(args.perks.read_text())["perks"]
        stats = match_perks(entries, perks)
    else:
        stats = None
        # Normalise event shape to be consistent (list of {text}) regardless
        # of whether matching ran.
        for entry in entries:
            entry["events"] = [{"text": t} for t in entry["events"]]

    # Add sequence numbers and a top-level summary.
    for i, e in enumerate(entries, start=1):
        e["sequence"] = i

    payload = {
        "schema_version": SCHEMA_VERSION,
        "_source": "data/raw/wiki/bcf_wiki_timeline.html (Celestial Forge Fandom Wiki)",
        "_attribution": "Celestial Forge Fandom Wiki (Whamodyne)",
        "_note": (
            "Auto-extracted from the Wiki Timeline section. Per the wiki header: "
            "'Up to date through 104.2 Interlude Rachel' — i.e. these 28 in-world "
            "days correspond roughly to story chapters 1 through 104.2. Per-event "
            "chapter linkage is NOT included here; build a chapter->date mapping "
            "separately from explicit anchors."
        ),
        "_count": len(entries),
        "_first_in_world_date": entries[0]["in_world_date_iso"] if entries else None,
        "_last_in_world_date": entries[-1]["in_world_date_iso"] if entries else None,
        "_coverage_anchor": {
            "in_world_date_iso": "2011-04-28",
            "approx_chapter_num": "104.2",
            "source": "wiki page header note",
        },
        "_match_stats": stats,
        "entries": entries,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    rel = args.output.relative_to(ROOT)
    total_bullets = sum(len(e["events"]) for e in entries)
    print(f"wrote {rel}")
    print(f"  dated entries:           {len(entries)}")
    print(f"  date range:              "
          f"{payload['_first_in_world_date']} -> {payload['_last_in_world_date']}")
    print(f"  total event bullets:     {total_bullets}")
    if stats:
        print(f"  bullets with perk match: {stats['bullets_with_match']} "
              f"(low-confidence diagnostic)")
        print(f"  perks consumed:          "
              f"{stats['perks_consumed']} / {stats['perks_in_catalog']}")


if __name__ == "__main__":
    main()
