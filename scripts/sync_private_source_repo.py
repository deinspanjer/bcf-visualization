"""Sync the private source-file repository used by data release builds.

The public repository intentionally does not commit the source EPUB. This
script maintains a local clone of the private source repository under
``data/private-source/``, copies or downloads the EPUB there, writes sidecar
metadata, commits, tags, and pushes the private source update.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "deinspanjer/bcf-visualization-private-source"
DEFAULT_PRIVATE_DIR = ROOT / "data" / "private-source"
DEFAULT_LOCAL_EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
PRIVATE_EPUB_NAME = "Brocktons_Celestial_Forge.epub"
METADATA_NAME = "Brocktons_Celestial_Forge.metadata.json"
DEFAULT_STORY_URL = (
    "https://forums.sufficientvelocity.com/threads/"
    "brocktons-celestial-forge-worm-jumpchain.70036/"
)
FICHUB_EXPORT_URL = "https://fichub.net/legacy/epub_export"


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def ensure_clone(repo: str, private_dir: Path) -> None:
    if (private_dir / ".git").is_dir():
        dirty = run(["git", "status", "--porcelain"], cwd=private_dir).stdout.strip()
        has_head = run(["git", "rev-parse", "--verify", "HEAD"], cwd=private_dir, check=False)
        if not dirty and has_head.returncode == 0:
            run(["git", "pull", "--ff-only"], cwd=private_dir)
        return
    if private_dir.exists() and any(private_dir.iterdir()):
        raise SystemExit(f"{private_dir} exists but is not an empty git clone")
    private_dir.parent.mkdir(parents=True, exist_ok=True)
    run(["gh", "repo", "clone", repo, str(private_dir)])


def download_epub(output: Path, story_url: str) -> str:
    from download_bcf_epub import download_epub as download

    download(story_url, output)
    query = urllib.parse.urlencode({"q": story_url})
    return f"{FICHUB_EXPORT_URL}?{query}"


def digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def chapter_nav_entries(epub_path: Path) -> list[dict]:
    with zipfile.ZipFile(epub_path) as zf:
        nav = zf.read("EPUB/nav.xhtml").decode("utf-8", "replace")
    entries = []
    for href, title in re.findall(
        r'<a[^>]*?href="([^"]+)"[^>]*>(.*?)</a>',
        nav,
        re.DOTALL,
    ):
        title_text = re.sub(r"<[^>]+>", "", title)
        title_text = html.unescape(" ".join(title_text.split()))
        if not href.startswith("chap_"):
            continue
        chapter_num = title_text.split()[0] if title_text else None
        entries.append({
            "href": href,
            "title": title_text,
            "chapter_num": chapter_num,
        })
    return entries


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def derived_chapter_summary() -> dict:
    chapters_doc = load_json(ROOT / "data" / "derived" / "chapters.json") or {}
    edits_doc = load_json(ROOT / "data" / "derived" / "chapter_last_edited.json") or {}
    chapters = list(chapters_doc.get("chapters") or [])
    chapters.sort(key=lambda c: tuple(c.get("sort_key") or (0, 0)))
    edits = [
        row.get("last_edited_at")
        for row in edits_doc.get("chapters") or []
        if row.get("last_edited_at")
    ]
    if not chapters:
        return {
            "last_chapter_publish_timestamp": None,
            "max_last_modification_timestamp": max(edits) if edits else None,
        }
    last = chapters[-1]
    return {
        "last_chapter_publish_timestamp": last.get("publish_iso"),
        "max_last_modification_timestamp": max(edits) if edits else None,
    }


def next_version_tag(private_dir: Path, date: str) -> str:
    run(["git", "fetch", "--tags", "--quiet"], cwd=private_dir)
    result = run(["git", "tag", "--list", f"source-v{date}.*"], cwd=private_dir)
    max_ord = 0
    for line in result.stdout.splitlines():
        m = re.fullmatch(rf"source-v{re.escape(date)}\.(\d+)", line.strip())
        if m:
            max_ord = max(max_ord, int(m.group(1)))
    return f"source-v{date}.{max_ord + 1}"


def write_metadata(
    *,
    epub_path: Path,
    metadata_path: Path,
    version_tag: str,
    provenance_url: str,
    story_url: str,
) -> dict:
    entries = chapter_nav_entries(epub_path)
    last_entry = entries[-1] if entries else {}
    summary = derived_chapter_summary()
    generated_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    stat = epub_path.stat()
    metadata = {
        "schema_version": 1,
        "version_tag": version_tag,
        "generated_at": generated_at,
        "source_file": epub_path.name,
        "size_bytes": stat.st_size,
        "md5": digest(epub_path, "md5"),
        "sha256": digest(epub_path, "sha256"),
        "provenance": {
            "kind": "fichub_epub_export",
            "story_url": story_url,
            "fichub_url": provenance_url,
        },
        "chapters": {
            "count": len(entries),
            "last_chapter_friendly_number": last_entry.get("chapter_num"),
            "last_chapter_title": last_entry.get("title"),
            "last_chapter_href": last_entry.get("href"),
            "last_chapter_publish_timestamp": summary["last_chapter_publish_timestamp"],
            "max_last_modification_timestamp": summary["max_last_modification_timestamp"],
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return metadata


def commit_tag_push(private_dir: Path, version_tag: str, metadata: dict) -> None:
    run(["git", "add", PRIVATE_EPUB_NAME, METADATA_NAME], cwd=private_dir)
    diff = run(["git", "diff", "--cached", "--quiet"], cwd=private_dir, check=False)
    if diff.returncode == 0:
        print("private source repo already up to date; no commit created")
    else:
        title = metadata["chapters"].get("last_chapter_title") or "unknown chapter"
        run([
            "git",
            "commit",
            "-m",
            (
                f"source: update BCF EPUB {version_tag}\n\n"
                f"- Store {metadata['source_file']} ({metadata['size_bytes']} bytes).\n"
                f"- Latest chapter: {title}.\n"
                f"- Metadata: md5 {metadata['md5']}; sha256 {metadata['sha256']}."
            ),
        ], cwd=private_dir)
    tag_exists = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{version_tag}"], cwd=private_dir, check=False)
    if tag_exists.returncode != 0:
        run([
            "git",
            "tag",
            "-a",
            version_tag,
            "-m",
            f"BCF private source {version_tag}",
        ], cwd=private_dir)
    run(["git", "push", "origin", "HEAD"], cwd=private_dir)
    run(["git", "push", "origin", version_tag], cwd=private_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--private-dir", type=Path, default=DEFAULT_PRIVATE_DIR)
    parser.add_argument("--local-epub", type=Path, default=DEFAULT_LOCAL_EPUB)
    parser.add_argument("--story-url", default=DEFAULT_STORY_URL)
    parser.add_argument("--date", default=dt.datetime.now(dt.UTC).strftime("%Y%m%d"))
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download a fresh EPUB through FicHub into the private source clone.",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Update the private source clone but do not commit, tag, or push.",
    )
    args = parser.parse_args()

    private_dir = args.private_dir.resolve()
    ensure_clone(args.repo, private_dir)

    private_epub = private_dir / PRIVATE_EPUB_NAME
    if args.download:
        provenance_url = download_epub(private_epub, args.story_url)
    else:
        local_epub = args.local_epub.resolve()
        if not local_epub.exists():
            raise SystemExit(
                f"missing {local_epub}; pass --download to fetch from FicHub"
            )
        shutil.copy2(local_epub, private_epub)
        provenance_url = f"{FICHUB_EXPORT_URL}?{urllib.parse.urlencode({'q': args.story_url})}"

    version_tag = next_version_tag(private_dir, args.date)
    metadata = write_metadata(
        epub_path=private_epub,
        metadata_path=private_dir / METADATA_NAME,
        version_tag=version_tag,
        provenance_url=provenance_url,
        story_url=args.story_url,
    )

    if args.no_push:
        print(f"updated {private_dir} without pushing ({version_tag})")
        return 0

    commit_tag_push(private_dir, version_tag, metadata)
    print(f"synced private source repo at {version_tag}")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
