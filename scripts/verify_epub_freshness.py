"""Verify the hydrated source EPUB matches the private-source clone's release.

This is a mechanical, read-only comparison of two already-written JSON files —
``data/raw/Brocktons_Celestial_Forge.source.json`` (produced by
``hydrate_source_epub.py``) and ``data/private-source/Brocktons_Celestial_Forge.metadata.json``
(produced outside this repo by the private-source sync flow). It does NOT
re-parse the EPUB or re-implement any of ``hydrate_source_epub.parse_epub_nav``;
it only checks whether the two records agree.

When they disagree, the sanctioned remediation is the existing refresh flow:
``scripts/sync_private_source_repo.py`` then ``scripts/hydrate_source_epub.py``.
This script never fetches or hydrates anything itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from data_paths import DATA
except ModuleNotFoundError:  # package import path used by tests
    from scripts.data_paths import DATA


SOURCE_JSON_NAME = "Brocktons_Celestial_Forge.source.json"
PRIVATE_SOURCE_METADATA_NAME = "Brocktons_Celestial_Forge.metadata.json"


def _field(source: bool, private_source: object) -> dict:
    return {
        "source": source,
        "private_source": private_source,
        "match": source == private_source,
    }


def verify_epub_freshness(*, data_dir: Path = DATA) -> dict:
    data_dir = Path(data_dir).resolve()
    source_path = data_dir / "raw" / SOURCE_JSON_NAME
    private_metadata_path = data_dir / "private-source" / PRIVATE_SOURCE_METADATA_NAME

    source = json.loads(source_path.read_text())
    private_metadata = json.loads(private_metadata_path.read_text())
    chapters = private_metadata.get("chapters", {})

    chapter_count = _field(source.get("chapter_count"), chapters.get("count"))
    last_chapter_num = _field(
        source.get("last_chapter_num"), chapters.get("last_chapter_friendly_number")
    )
    epub_sha256 = _field(source.get("epub_sha256"), private_metadata.get("sha256"))

    fresh = chapter_count["match"] and last_chapter_num["match"] and epub_sha256["match"]

    return {
        "fresh": fresh,
        "chapter_count": chapter_count,
        "last_chapter_num": last_chapter_num,
        "epub_sha256": epub_sha256,
        "source_path": str(source_path),
        "private_source_metadata_path": str(private_metadata_path),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args(argv)

    result = verify_epub_freshness(data_dir=args.data_dir)

    if not result["fresh"]:
        mismatches = [
            f"{field}: source={result[field]['source']!r} "
            f"private_source={result[field]['private_source']!r}"
            for field in ("chapter_count", "last_chapter_num", "epub_sha256")
            if not result[field]["match"]
        ]
        print(
            "STALE: hydrated source EPUB does not match the private-source clone: "
            + "; ".join(mismatches),
            file=sys.stderr,
        )
        print(
            "Run scripts/sync_private_source_repo.py then scripts/hydrate_source_epub.py "
            "to refresh the hydrated source before retrying.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(
        "fresh: hydrated source EPUB matches private-source clone "
        f"(chapter_count={result['chapter_count']['source']}, "
        f"last_chapter_num={result['last_chapter_num']['source']})"
    )
    raise SystemExit(0)


if __name__ == "__main__":
    main()
