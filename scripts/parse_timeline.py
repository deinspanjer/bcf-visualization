"""Parse the Whamodyne in-story timeline post into timeline.json.

Source:  data/raw/info_posts/sv_page_0233.mht  (post-18327981)
Output:  data/derived/timeline.json

Each entry of the timeline is a single in-story day, formatted like:
    Friday April 1st 2011 - Joe triggers...
    Friday, April 8th - Start of the story.
    Tuesday, April 19th - Acquires Veritech...

The year is given on the first entry (April 2011) and inherited by
later entries that omit it. The post itself is dated 2020-12-10 SV
post time and the author noted it was updated through chapter 93;
the story has continued past that, so this dataset covers chapters
1..~93.
"""

from __future__ import annotations

import email
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "info_posts" / "sv_page_0233.mht"
OUT = ROOT / "data" / "derived" / "timeline.json"

POST_ID = "post-18327981"


@dataclass
class TimelineEntry:
    sequence: int               # 1-based, in original document order
    in_world_date: str          # ISO date, e.g. "2011-04-01"
    day_of_week: str            # "Friday", "Saturday", etc. (as written)
    events: str                 # raw narrative text for the day


_DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
_MONTHS = {
    m: i for i, m in enumerate(
        ("January February March April May June "
         "July August September October November December").split(),
        start=1,
    )
}
# Day, Month DayOrdinal [Year] - events
_LINE_RE = re.compile(
    rf"^(?P<dow>{_DAYS}),?\s+"
    r"(?P<month>[A-Z][a-z]+)\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:[\s,]+(?P<year>\d{4}))?"
    r"\s*[-–—]\s*"
    r"(?P<events>.+)$"
)
# fallback: trailing summary line "In story time is ... Tuesday April 26th 2011."
_TRAILER_RE = re.compile(
    rf"\b(?P<dow>{_DAYS})\s+"
    r"(?P<month>[A-Z][a-z]+)\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
    r"\s+(?P<year>\d{4})\b"
)


class _Strip(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "td"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def _strip_html(s: str) -> str:
    p = _Strip()
    p.feed(s)
    txt = "".join(p.out)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n[ \t]+", "\n", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)
    return txt.strip()


def _extract_post_text() -> str:
    msg = email.message_from_bytes(SRC.read_bytes())
    html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    payload = html_part.get_payload(decode=True).decode("utf-8", errors="replace")
    article = re.search(
        rf'<article\b[^>]*?data-content="{POST_ID}"[^>]*?>(.*?)</article>',
        payload, re.DOTALL,
    )
    if not article:
        raise RuntimeError(f"Could not locate {POST_ID} in {SRC}")
    body = article.group(1)
    bb = re.search(r'<div class="bbWrapper"[^>]*>(.*)$', body, re.DOTALL)
    return _strip_html(bb.group(1)) if bb else _strip_html(body)


def parse_timeline(text: str) -> list[TimelineEntry]:
    entries: list[TimelineEntry] = []
    current_year: int | None = None
    seq = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        if m.group("year"):
            current_year = int(m.group("year"))
        if current_year is None:
            # No year known yet -- skip until we have one (the post starts
            # with a year, so this should never trigger in practice).
            continue
        try:
            iso = date(
                current_year,
                _MONTHS[m.group("month")],
                int(m.group("day")),
            ).isoformat()
        except (KeyError, ValueError):
            continue
        seq += 1
        entries.append(
            TimelineEntry(
                sequence=seq,
                in_world_date=iso,
                day_of_week=m.group("dow"),
                events=m.group("events").strip(),
            )
        )
    return entries


def main() -> None:
    text = _extract_post_text()
    entries = parse_timeline(text)

    trailer = _TRAILER_RE.search(text.split("\n")[-1] if text else "")
    if trailer:
        try:
            trailer_iso = date(
                int(trailer.group("year")),
                _MONTHS[trailer.group("month")],
                int(trailer.group("day")),
            ).isoformat()
        except (KeyError, ValueError):
            trailer_iso = None
    else:
        trailer_iso = None

    payload = {
        "_source": f"data/raw/info_posts/sv_page_0233.mht#{POST_ID}",
        "_author": "Whamodyne (reader-curated; SV post 2020-12-10)",
        "_count": len(entries),
        "_first_in_world_date": entries[0].in_world_date if entries else None,
        "_last_in_world_date": entries[-1].in_world_date if entries else None,
        "_post_trailer_date": trailer_iso,
        "_note": "Through chapter 93 per author. Year inherited from first dated entry.",
        "entries": [asdict(e) for e in entries],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(entries)} dated days")
    if entries:
        print(f"  range: {entries[0].in_world_date} ({entries[0].day_of_week})"
              f"  ->  {entries[-1].in_world_date} ({entries[-1].day_of_week})")
    print(f"  trailer date: {trailer_iso}")


if __name__ == "__main__":
    main()
