"""Build chapters.json from the EPUB navigation and chapter HTML.

Input:   data/raw/Brocktons_Celestial_Forge.epub
Output:  data/derived/chapters.json

The EPUB navigation document (EPUB/nav.xhtml) lists every chapter in
publication order. Each entry's href (chap_N.xhtml) doubles as the
chapter's ordinal; the link text carries the friendly chapter number
and title (e.g. "120.2 Interlude Accord - Preamble Mike").

`total_word_count` is the raw token count of the entire chapter HTML
(headers, author notes, "Jumpchain abilities" perk footers, and any
non-MC POV sections all included). This is a structural summary, NOT
the count CP arithmetic runs on. For CP-eligible words see
`chapter_facts.json:cp_earning_word_count`, computed by filtering
`chapter_sections.json` to sections where
`section_classifications.json:counts_for_cp` is true.

Publish dates and last-edit timestamps live in
data/manual/chapter_publication_dates.json (AO3 + EPUB-footer sourced).
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
OUT_PATH = ROOT / "data" / "derived" / "chapters.json"

NAV_PATH = "EPUB/nav.xhtml"
NAV_LINK_RE = re.compile(
    r'<a[^>]*?href="(?P<href>chap_\d+\.xhtml)"[^>]*>(?P<title>.*?)</a>',
    re.DOTALL,
)
PREFIX_RE = re.compile(
    r"^(?P<num>\d+)(?:\.(?P<sub>\d+))?[\s,:.\-]+(?P<title>.*)$"
)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Chapter:
    chapter_num: str            # "1", "3.1", "120.2"
    sort_key: tuple[int, int]   # (3, 1) < (3, 2) < (4, 0)
    ordinal: int                # EPUB nav position, 1..N (matches chap_N.xhtml)
    title: str                  # everything after the numeric prefix
    full_title: str             # "120.2 Interlude Accord - Preamble Mike"
    epub_href: str              # "chap_195.xhtml"
    total_word_count: int       # raw chapter HTML tokens; NOT CP-eligible (see module docstring)


def _strip_tags(html_text: str) -> str:
    return TAG_RE.sub(" ", html_text)


def _word_count(body: str) -> int:
    text = html.unescape(_strip_tags(body))
    return len(text.split())


def parse_all() -> list[Chapter]:
    chapters: list[Chapter] = []
    with zipfile.ZipFile(EPUB) as zf:
        nav = zf.read(NAV_PATH).decode("utf-8")
        ordinal = 0
        for m in NAV_LINK_RE.finditer(nav):
            href = m.group("href")
            title_text = html.unescape(
                " ".join(_strip_tags(m.group("title")).split())
            )
            prefix = PREFIX_RE.match(title_text)
            if not prefix:
                raise ValueError(
                    f"EPUB nav entry {href!r} lacks a chapter-number prefix: "
                    f"{title_text!r}"
                )
            major = int(prefix.group("num"))
            minor = int(prefix.group("sub")) if prefix.group("sub") else 0
            chapter_num = f"{major}.{minor}" if minor else str(major)
            ordinal += 1
            expected_href = f"chap_{ordinal}.xhtml"
            if href != expected_href:
                raise ValueError(
                    f"EPUB nav ordering drift at ordinal {ordinal}: "
                    f"expected href {expected_href!r}, got {href!r}"
                )
            body = zf.read(f"EPUB/{href}").decode("utf-8", errors="replace")
            chapters.append(Chapter(
                chapter_num=chapter_num,
                sort_key=(major, minor),
                ordinal=ordinal,
                title=prefix.group("title").strip(),
                full_title=title_text,
                epub_href=href,
                total_word_count=_word_count(body),
            ))
    chapters.sort(key=lambda c: c.sort_key)
    return chapters


def main() -> None:
    chapters = parse_all()
    payload = {
        "_source": (
            "Walked EPUB/nav.xhtml in data/raw/Brocktons_Celestial_Forge.epub. "
            "ordinal mirrors the nav position (chap_N.xhtml). total_word_count "
            "is the raw chapter HTML token count (headers, author notes, perk "
            "footers, non-MC POV sections all included) — NOT the CP-eligible "
            "count. CP arithmetic uses chapter_facts.json:cp_earning_word_count, "
            "derived from section classifications. Publish dates live in "
            "data/manual/chapter_publication_dates.json."
        ),
        "_count": len(chapters),
        "chapters": [asdict(c) for c in chapters],
    }
    write_validated_json(OUT_PATH, payload, "chapters")
    print(f"wrote {OUT_PATH.relative_to(ROOT)}: {len(chapters)} chapters")

    first, last = chapters[0], chapters[-1]
    print(f"  range: {first.full_title!r}  -->  {last.full_title!r}")
    total_words = sum(c.total_word_count for c in chapters)
    print(f"  total raw chapter words: {total_words:,} (includes headers, A/N, perk footers)")


if __name__ == "__main__":
    main()
