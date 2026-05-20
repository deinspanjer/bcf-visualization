"""Hydrate the local source EPUB from already-present source files.

Maintainer releases should checkout ``data/private-source`` before running
this script. Public contributors can place a compatible EPUB directly at
``data/raw/Brocktons_Celestial_Forge.epub``. This script never downloads from
the network; it only selects, validates, copies when needed, and records source
metadata for release packaging.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

try:
    from data_paths import DATA, ROOT
except ModuleNotFoundError:  # package import path used by tests
    from scripts.data_paths import DATA, ROOT


EPUB_NAME = "Brocktons_Celestial_Forge.epub"
SOURCE_METADATA_NAME = "Brocktons_Celestial_Forge.source.json"
NAV_PATH = "EPUB/nav.xhtml"
PREFIX_RE = re.compile(r"^(?P<num>\d+)(?:\.(?P<sub>\d+))?[\s,:.\-]+(?P<title>.*)$")


@dataclass(frozen=True)
class SourceSelection:
    kind: str
    path: Path
    relative_path: str
    private_source_commit: str | None


@dataclass(frozen=True)
class ChapterSummary:
    chapter_num: str
    full_title: str
    href: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_relative(path: Path, data_dir: Path, root: Path) -> str:
    try:
        return (Path(data_dir.name) / path.resolve().relative_to(data_dir.resolve())).as_posix()
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _private_source_commit(private_dir: Path) -> str | None:
    if not (private_dir / ".git").exists():
        return None
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=private_dir,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def select_source_epub(*, data_dir: Path = DATA, root: Path = ROOT) -> SourceSelection:
    private_dir = data_dir / "private-source"
    private_epub = private_dir / EPUB_NAME
    raw_epub = data_dir / "raw" / EPUB_NAME
    if private_epub.is_file():
        return SourceSelection(
            kind="private-source",
            path=private_epub,
            relative_path=_data_relative(private_epub, data_dir, root),
            private_source_commit=_private_source_commit(private_dir),
        )
    if raw_epub.is_file():
        return SourceSelection(
            kind="raw",
            path=raw_epub,
            relative_path=_data_relative(raw_epub, data_dir, root),
            private_source_commit=None,
        )
    raise FileNotFoundError(
        "missing source EPUB. Maintainers should checkout "
        f"data/private-source/{EPUB_NAME}; contributors should provide a "
        f"compatible EPUB at data/raw/{EPUB_NAME}."
    )


def _element_text(element: ElementTree.Element) -> str:
    return " ".join(" ".join(element.itertext()).split())


def _parse_chapter_link(href: str, title_text: str, ordinal: int) -> ChapterSummary:
    prefix = PREFIX_RE.match(title_text)
    if not prefix:
        raise ValueError(
            f"EPUB nav entry {href!r} lacks a chapter-number prefix: {title_text!r}"
        )
    major = int(prefix.group("num"))
    minor = int(prefix.group("sub")) if prefix.group("sub") else 0
    chapter_num = f"{major}.{minor}" if minor else str(major)
    expected_href = f"chap_{ordinal}.xhtml"
    if href != expected_href:
        raise ValueError(
            f"EPUB nav ordering drift at ordinal {ordinal}: "
            f"expected href {expected_href!r}, got {href!r}"
        )
    return ChapterSummary(chapter_num=chapter_num, full_title=title_text, href=href)


def parse_epub_nav(epub_path: Path) -> list[ChapterSummary]:
    with zipfile.ZipFile(epub_path) as zf:
        try:
            raw_nav = zf.read(NAV_PATH)
        except KeyError as exc:
            raise ValueError(f"EPUB is missing {NAV_PATH}") from exc
    root = ElementTree.fromstring(raw_nav)
    chapters: list[ChapterSummary] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "a":
            continue
        href = str(element.attrib.get("href", ""))
        if not re.fullmatch(r"chap_\d+\.xhtml", href):
            continue
        title_text = _element_text(element)
        chapters.append(_parse_chapter_link(href, title_text, len(chapters) + 1))
    if not chapters:
        raise ValueError(f"EPUB nav {NAV_PATH} has no chapter links")
    return chapters


def _json_files(manual_dir: Path) -> list[Path]:
    if not manual_dir.is_dir():
        return []
    return sorted(path for path in manual_dir.glob("*.json") if path.is_file())


def _add_reference(
    refs: dict[str, set[str]],
    chapter_num: object,
    *,
    source: Path,
    context: str,
) -> None:
    if chapter_num is None:
        return
    text = str(chapter_num).strip()
    if not text:
        return
    refs.setdefault(source.name, set()).add(text)


def _collect_chapter_references(value: object, *, source: Path, refs: dict[str, set[str]]) -> None:
    if isinstance(value, dict):
        chapter_rolls = value.get("chapter_roll_overrides")
        if isinstance(chapter_rolls, dict):
            for chapter_num in chapter_rolls:
                _add_reference(refs, chapter_num, source=source, context="chapter_roll_overrides")
        classifications = value.get("classifications")
        if isinstance(classifications, dict):
            for key, item in classifications.items():
                if "@" in str(key):
                    _add_reference(refs, str(key).split("@", 1)[0], source=source, context="classifications")
                if isinstance(item, dict):
                    _add_reference(refs, item.get("chapter_num"), source=source, context="classifications")
        for key, item in value.items():
            if key in {"chapter_num", "mention_chapter_num"}:
                _add_reference(refs, item, source=source, context=key)
            else:
                _collect_chapter_references(item, source=source, refs=refs)
    elif isinstance(value, list):
        for item in value:
            _collect_chapter_references(item, source=source, refs=refs)


def validate_manual_chapter_references(
    *,
    manual_dir: Path,
    chapters: list[ChapterSummary],
) -> None:
    available = {chapter.chapter_num for chapter in chapters}
    missing_by_file: dict[str, list[str]] = {}
    for path in _json_files(manual_dir):
        refs: dict[str, set[str]] = {}
        payload = json.loads(path.read_text())
        _collect_chapter_references(payload, source=path, refs=refs)
        missing = sorted(
            (refs.get(path.name) or set()) - available,
            key=lambda value: tuple(int(part) for part in value.split(".")),
        )
        if missing:
            missing_by_file[path.name] = missing
    if missing_by_file:
        details = "; ".join(
            f"{name} references missing chapters: {', '.join(chapters)}"
            for name, chapters in missing_by_file.items()
        )
        raise ValueError(details)


def hydrate_source_epub(*, data_dir: Path = DATA, root: Path = ROOT) -> dict:
    data_dir = data_dir.resolve()
    root = root.resolve()
    selection = select_source_epub(data_dir=data_dir, root=root)
    raw_epub = data_dir / "raw" / EPUB_NAME
    raw_epub.parent.mkdir(parents=True, exist_ok=True)
    if selection.path.resolve() != raw_epub.resolve():
        shutil.copy2(selection.path, raw_epub)
    chapters = parse_epub_nav(raw_epub)
    validate_manual_chapter_references(
        manual_dir=data_dir / "manual",
        chapters=chapters,
    )
    last = chapters[-1]
    metadata = {
        "schema_version": 1,
        "source_kind": selection.kind,
        "source_path": selection.relative_path,
        "private_source_commit": selection.private_source_commit,
        "epub_sha256": _sha256(raw_epub),
        "chapter_count": len(chapters),
        "last_chapter_num": last.chapter_num,
        "last_chapter_title": last.full_title,
    }
    out = data_dir / "raw" / SOURCE_METADATA_NAME
    out.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    try:
        metadata = hydrate_source_epub(data_dir=args.data_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "hydrated source EPUB: "
        f"{metadata['source_kind']} "
        f"ch {metadata['chapter_count']} / {metadata['last_chapter_num']} "
        f"({metadata['epub_sha256']})"
    )


if __name__ == "__main__":
    main()
