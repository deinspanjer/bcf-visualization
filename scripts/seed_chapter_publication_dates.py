"""One-shot bootstrap for data/manual/chapter_publication_dates.json.

That manual file is the single source of truth for per-chapter publish
and last-edit dates. This script populates it from the two upstream
captures:

  - AO3 'Navigate Work' page (first-publication date, authoritative
    where present — for the earliest chapters SV mirrored months later)
  - FicHub EPUB 'Last edited: Mon DD, YYYY' footers (SV's own per-post
    edit stamp, only present for chapters edited after their initial
    post)

The chapter row set comes from chapters.json (SV threadmark index), so
chapter_num formatting matches the rest of the pipeline.

Re-running overwrites the manual file. If you've hand-edited rows,
back the file up first.

Inputs:
  - data/raw/ao3_index/navigate_work.html
  - data/raw/Brocktons_Celestial_Forge.epub
  - data/derived/chapters.json

Output:
  - data/manual/chapter_publication_dates.json
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
AO3_HTML = ROOT / "data" / "raw" / "ao3_index" / "navigate_work.html"
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
OUT = ROOT / "data" / "manual" / "chapter_publication_dates.json"

AO3_ROW_RE = re.compile(
    r'<li>\s*'
    r'<a href="/works/\d+/chapters/\d+">'
    r'\d+\.\s+(?P<full>[^<]+)'
    r'</a>\s*'
    r'<span class="datetime">\((?P<date>\d{4}-\d{2}-\d{2})\)</span>'
)
PREFIX_RE = re.compile(
    r"^(?P<num>\d+)(?:\.(?P<sub>\d+))?[\s,:.\-]+(?P<title>.*)$"
)
LAST_EDITED_RE = re.compile(r"Last edited:\s*([A-Za-z]+\s+\d+,\s+\d{4})")


def _chapter_num_from_title(full: str) -> str:
    m = PREFIX_RE.match(full)
    if not m:
        raise ValueError(f"AO3 title lacks chapter-number prefix: {full!r}")
    major = int(m.group("num"))
    sub = m.group("sub")
    return f"{major}.{int(sub)}" if sub else str(major)


def _load_ao3() -> dict[str, str]:
    """chapter_num -> AO3 first-publication date (YYYY-MM-DD)."""
    html = AO3_HTML.read_text()
    out: dict[str, str] = {}
    for m in AO3_ROW_RE.finditer(html):
        cn = _chapter_num_from_title(m.group("full").strip())
        if cn in out:
            raise ValueError(f"AO3: duplicate chapter_num {cn}")
        out[cn] = m.group("date")
    return out


def _load_epub_last_edited(chapters: list[dict]) -> dict[str, str]:
    """chapter_num -> EPUB 'Last edited:' date (YYYY-MM-DD), only for
    chapters that carry the stamp."""
    out: dict[str, str] = {}
    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            href = title_to_href.get(c["full_title"])
            if not href:
                continue
            body = zf.read(f"EPUB/{href}").decode("utf-8", errors="replace")
            m = LAST_EDITED_RE.search(body)
            if not m:
                continue
            edited = dt.datetime.strptime(m.group(1).strip(), "%b %d, %Y").date()
            out[c["chapter_num"]] = edited.isoformat()
    return out


def main() -> None:
    for path in (AO3_HTML, EPUB, CHAPTERS):
        if not path.exists():
            raise SystemExit(f"missing {path.relative_to(ROOT)}")

    chapters = json.loads(CHAPTERS.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    ao3 = _load_ao3()
    edits = _load_epub_last_edited(chapters)

    rows: list[dict] = []
    missing_ao3: list[str] = []
    for c in chapters:
        cn = c["chapter_num"]
        if cn in ao3:
            pub = ao3[cn]
            pub_src = "ao3"
        else:
            # Fallback: SV publish date (date-only). The user's stated
            # goal is to correct SV dates with AO3; falling back here is
            # only for chapters AO3 doesn't carry.
            pub = c["publish_iso"][:10]
            pub_src = "sv"
            missing_ao3.append(cn)

        edit = edits.get(cn)
        rows.append({
            "chapter_num": cn,
            "published_at": pub,
            "published_source": pub_src,
            "last_edited_at": edit,
            "last_edited_source": "epub" if edit else None,
        })

    payload = {
        "_source": (
            "Bootstrapped from AO3 navigate page + EPUB 'Last edited:' "
            "footers. Hand-editable thereafter; re-running this script "
            "overwrites. published_source/last_edited_source record where "
            "each date came from."
        ),
        "_count": len(rows),
        "chapters": rows,
    }
    write_validated_json(OUT, payload, "chapter_publication_dates")

    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} chapters")
    src_counts = {}
    edit_counts = {}
    for r in rows:
        src_counts[r["published_source"]] = src_counts.get(r["published_source"], 0) + 1
        key = r["last_edited_source"] or "none"
        edit_counts[key] = edit_counts.get(key, 0) + 1
    print(f"  published_source: {src_counts}")
    print(f"  last_edited_source: {edit_counts}")
    if missing_ao3:
        print(f"  not on AO3 (fell back to SV): {missing_ao3}")


if __name__ == "__main__":
    main()
