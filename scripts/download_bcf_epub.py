"""Download the Brockton's Celestial Forge EPUB used by validation scripts."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_STORY_URL = (
    "https://forums.sufficientvelocity.com/threads/"
    "brocktons-celestial-forge-worm-jumpchain.70036/"
)
DEFAULT_OUTPUT = Path("data/raw/Brocktons_Celestial_Forge.epub")
FICHUB_EXPORT_URL = "https://fichub.net/legacy/epub_export"


class EpubLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value and ".epub" in value:
                self.links.append(value)


def find_epub_url(html: str, base_url: str) -> str:
    parser = EpubLinkParser()
    parser.feed(html)
    for href in parser.links:
        if "/cache/epub/" in href or href.endswith(".epub"):
            return urllib.parse.urljoin(base_url, href)
    raise RuntimeError("FicHub export response did not contain an EPUB download link")


def download_epub(story_url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    query = urllib.parse.urlencode({"q": story_url})
    export_url = f"{FICHUB_EXPORT_URL}?{query}"
    request = urllib.request.Request(export_url, headers={"User-Agent": "bcf-visualization setup"})
    with urllib.request.urlopen(request, timeout=120) as response:
        html = response.read().decode("utf-8", "replace")
        response_url = response.geturl()
    epub_url = find_epub_url(html, response_url)
    urllib.request.urlretrieve(epub_url, output)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--story-url", default=DEFAULT_STORY_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        print(f"{args.output} already exists; skipping download")
        return 0

    try:
        download_epub(args.story_url, args.output)
    except Exception as exc:
        print(f"failed to download EPUB from FicHub: {exc}", file=sys.stderr)
        return 1
    print(f"downloaded {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
