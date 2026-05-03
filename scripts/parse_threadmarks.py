"""Parse SV threadmark index MHT files into a structured chapters.json.

Input:   data/raw/threadmark_index/threadmarks_p*.mht
Output:  data/derived/chapters.json

The forum renders word counts in rounded form ("5k", "8.2k") -- the
numeric `words_approx` field reflects that rounding, not exact counts.
"""

from __future__ import annotations

import email
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "raw" / "threadmark_index"
OUT_PATH = ROOT / "data" / "derived" / "chapters.json"


@dataclass
class Chapter:
    chapter_num: str            # raw prefix, e.g. "1", "3.1", "74.2"
    sort_key: tuple[int, int]   # for stable ordering: (3, 1) < (3, 2) < (4, 0)
    title: str                  # everything after the prefix, e.g. "Introduction"
    full_title: str             # original threadmark text, e.g. "1 Introduction"
    post_id: int
    post_url: str
    publish_ts: int             # Unix seconds
    publish_iso: str            # XenForo's datetime attribute, e.g. "2020-07-19T21:07:12-0400"
    words_text: str             # original "5k" / "8.2k"
    words_approx: int           # parsed: "5k" -> 5000, "8.2k" -> 8200
    likes: int
    author: str
    source_file: str


_ROW_RE = re.compile(
    r'<div class="structItem structItem--threadmark[^"]*"[^>]*?'
    r'data-likes="(?P<likes>\d+)"[^>]*?'
    r'data-content-author="(?P<author>[^"]*)"[^>]*?'
    r'data-content-date="(?P<cdate>\d+)"[^>]*?>'
    r'(?P<body>.*?)'
    r'(?=<div class="structItem structItem--threadmark|<div class="block-outer)',
    re.DOTALL,
)
_LINK_RE = re.compile(
    r'<a [^>]*?href="(?P<url>[^"]*?#post-(?P<pid>\d+))"[^>]*>(?P<title>[^<]+)</a>'
)
_WORDS_RE = re.compile(r"<dt>Words</dt>\s*<dd>([^<]+)</dd>")
_TIME_RE = re.compile(
    r'<time[^>]*datetime="(?P<iso>[^"]+)"[^>]*data-time="(?P<ts>\d+)"'
)
_PREFIX_RE = re.compile(
    r"^(?P<num>\d+)(?:\.(?P<sub>\d+))?[\s,:.\-]+(?P<title>.*)$"
)


def _read_mht_html(path: Path) -> str:
    msg = email.message_from_bytes(path.read_bytes())
    html_part = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    return html_part.get_payload(decode=True).decode("utf-8", errors="replace")


def _parse_words(text: str) -> int:
    """Convert "5k" -> 5000, "8.2k" -> 8200. Forum rounds to 1 decimal."""
    text = text.strip().lower().rstrip("k")
    return int(round(float(text) * 1000))


def _parse_chapter(match: re.Match[str], source_file: str) -> Chapter:
    body = match.group("body")
    link = _LINK_RE.search(body)
    words = _WORDS_RE.search(body)
    time_m = _TIME_RE.search(body)

    full_title = link.group("title").strip()
    prefix = _PREFIX_RE.match(full_title)
    chapter_num = full_title.split(" ", 1)[0]
    sort_key: tuple[int, int]
    title: str
    if prefix:
        major = int(prefix.group("num"))
        minor = int(prefix.group("sub")) if prefix.group("sub") else 0
        sort_key = (major, minor)
        title = prefix.group("title").strip()
    else:
        sort_key = (0, 0)
        title = full_title

    return Chapter(
        chapter_num=chapter_num,
        sort_key=sort_key,
        title=title,
        full_title=full_title,
        post_id=int(link.group("pid")),
        post_url=link.group("url"),
        publish_ts=int(time_m.group("ts")),
        publish_iso=time_m.group("iso"),
        words_text=words.group(1).strip(),
        words_approx=_parse_words(words.group(1)),
        likes=int(match.group("likes")),
        author=match.group("author"),
        source_file=source_file,
    )


def parse_all() -> list[Chapter]:
    chapters: list[Chapter] = []
    for mht in sorted(SRC_DIR.glob("threadmarks_p*.mht")):
        html = _read_mht_html(mht)
        for m in _ROW_RE.finditer(html):
            chapters.append(_parse_chapter(m, mht.name))
    chapters.sort(key=lambda c: (c.sort_key, c.publish_ts))
    return chapters


def main() -> None:
    chapters = parse_all()
    payload = {
        "_source": "data/raw/threadmark_index/threadmarks_p*.mht",
        "_count": len(chapters),
        "_note": "words_approx is derived from the forum-rounded display ('5k', '8.2k'), not exact counts.",
        "chapters": [asdict(c) for c in chapters],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}: {len(chapters)} chapters")

    first, last = chapters[0], chapters[-1]
    print(f"  range: {first.full_title!r}  -->  {last.full_title!r}")
    print(f"  dates: {first.publish_iso[:10]} -> {last.publish_iso[:10]}")
    total_words = sum(c.words_approx for c in chapters)
    print(f"  total words (approx): {total_words:,}")


if __name__ == "__main__":
    main()
