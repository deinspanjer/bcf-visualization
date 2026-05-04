"""Extract per-chapter "Last edited:" timestamps from the FicHub EPUB.

The FicHub export preserves SV's per-post "Last edited: Mon DD, YYYY"
footer (date only — SV strips the time when displaying). We harvest
those into a derived JSON keyed by chapter_num, and compute a publish
→ last-edited lag in days for each chapter that has the stamp.

Inputs:
  - data/raw/Brocktons_Celestial_Forge.epub
  - data/derived/chapters.json (for the chap_N.xhtml ↔ chapter_num map
    and the publish_iso baseline)

Output:
  - data/derived/chapter_last_edited.json
"""

from __future__ import annotations

import datetime as dt
import json
import re
import zipfile
from pathlib import Path

from _common import write_validated_json
from find_roll_locations import _build_chapter_index

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
OUT = ROOT / "data" / "derived" / "chapter_last_edited.json"

# SV displays edit timestamps as "Last edited: Mon DD, YYYY" (no time)
# and FicHub carries that literal through unchanged.
_LAST_EDITED_RE = re.compile(r"Last edited:\s*([A-Za-z]+\s+\d+,\s+\d{4})")


def _parse_sv_date(s: str) -> dt.date:
    """Parse SV's 'Mon DD, YYYY' → date.  Strict; raises if format drifts."""
    return dt.datetime.strptime(s.strip(), "%b %d, %Y").date()


def main() -> None:
    if not EPUB.exists():
        raise SystemExit(f"missing {EPUB.relative_to(ROOT)}")

    chapters_json = json.loads(CHAPTERS.read_text())
    chapters = chapters_json["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    out_rows: list[dict] = []
    with_stamp = 0
    without_stamp: list[str] = []

    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            href = title_to_href.get(c["full_title"])
            if not href:
                # Unmapped chapter (shouldn't happen given chapters.json is
                # built from the same EPUB nav, but be defensive).
                without_stamp.append(c["chapter_num"])
                out_rows.append({
                    "chapter_num": c["chapter_num"],
                    "full_title": c["full_title"],
                    "last_edited_at": None,
                    "last_edited_known": False,
                    "edited_lag_days": None,
                })
                continue
            body = zf.read(f"EPUB/{href}").decode("utf-8", errors="replace")
            m = _LAST_EDITED_RE.search(body)
            if not m:
                without_stamp.append(c["chapter_num"])
                out_rows.append({
                    "chapter_num": c["chapter_num"],
                    "full_title": c["full_title"],
                    "last_edited_at": None,
                    "last_edited_known": False,
                    "edited_lag_days": None,
                })
                continue
            edited = _parse_sv_date(m.group(1))
            # publish_iso looks like "2020-07-19T21:07:12-0400"; strip to date
            published = dt.date.fromisoformat(c["publish_iso"][:10])
            lag = (edited - published).days
            with_stamp += 1
            out_rows.append({
                "chapter_num": c["chapter_num"],
                "full_title": c["full_title"],
                "last_edited_at": edited.isoformat(),
                "last_edited_known": True,
                "edited_lag_days": lag,
            })

    payload = {
        "_source": (
            "Per-chapter 'Last edited:' timestamps harvested from the "
            "FicHub EPUB. SV records date-only; FicHub preserves it "
            "verbatim. Chapters never edited post-publish do not carry "
            "the stamp — those rows have last_edited_known=false."
        ),
        "_count": len(out_rows),
        "_with_timestamp": with_stamp,
        "_without_timestamp_count": len(without_stamp),
        "_without_timestamp_chapters": without_stamp,
        "chapters": out_rows,
    }

    write_validated_json(OUT, payload, "chapter_last_edited")

    print(f"wrote {OUT.relative_to(ROOT)}: {len(out_rows)} chapters")
    print(f"  with timestamp:    {with_stamp}")
    print(f"  without timestamp: {len(without_stamp)} ({without_stamp})")
    if with_stamp:
        lags = [r["edited_lag_days"] for r in out_rows if r["edited_lag_days"] is not None]
        print(f"  edit lag days:     min={min(lags)}, max={max(lags)}, "
              f"median={sorted(lags)[len(lags)//2]}")


if __name__ == "__main__":
    main()
