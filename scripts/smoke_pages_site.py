"""Smoke-test a staged GitHub Pages artifact for the visualization."""

from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import socketserver
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class SmokeResult:
    package_id: str
    chapter_count: int
    roll_count: int
    constellation_pages_count: int


@dataclass(frozen=True)
class EarlyChapterProbe:
    chapter_num: str
    word_position: int
    hits: int
    misses: int


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON: {path}") from exc


def _default_package(index: dict) -> dict:
    packages = index.get("packages")
    if not isinstance(packages, list) or not packages:
        raise RuntimeError("packages.json has no packages")
    default_id = index.get("default_package_id")
    if default_id:
        for package in packages:
            if isinstance(package, dict) and package.get("package_id") == default_id:
                return package
        raise RuntimeError(f"default package is not listed: {default_id}")
    package = packages[0]
    if not isinstance(package, dict):
        raise RuntimeError("first package entry is malformed")
    return package


def _default_runtime_paths(site_dir: Path) -> tuple[Path, Path]:
    site_dir = site_dir.resolve()
    index = _read_json(site_dir / "data" / "packages.json")
    package = _default_package(index)
    package_path = package.get("path")
    if not isinstance(package_path, str):
        raise RuntimeError("default package entry is missing path")
    package_dir = (site_dir / package_path).resolve()
    try:
        package_dir.relative_to(site_dir)
    except ValueError as exc:
        raise RuntimeError(f"default package path escapes staged site: {package_path}") from exc

    manifest = _read_json(package_dir / "data_package.json")
    files = manifest.get("files")
    viz_meta = files.get("visualization_facts") if isinstance(files, dict) else None
    if not isinstance(viz_meta, dict) or not isinstance(viz_meta.get("path"), str):
        raise RuntimeError("visualization_facts file metadata is missing")
    return package_dir, package_dir / viz_meta["path"]


def validate_site(*, site_dir: Path) -> SmokeResult:
    site_dir = site_dir.resolve()
    if not (site_dir / "web" / "index.html").is_file():
        raise RuntimeError("staged site is missing web/index.html")

    index = _read_json(site_dir / "data" / "packages.json")
    package = _default_package(index)
    package_id = package.get("package_id")
    package_path = package.get("path")
    smoke_status = package.get("smoke_status")
    if not isinstance(package_id, str) or not isinstance(package_path, str):
        raise RuntimeError("default package entry is missing package_id or path")
    if smoke_status != "passed":
        raise RuntimeError(
            "default package smoke_status is not passed: "
            f"{package_id} -> {smoke_status!r}"
        )

    package_dir = (site_dir / package_path).resolve()
    try:
        package_dir.relative_to(site_dir)
    except ValueError as exc:
        raise RuntimeError(f"default package path escapes staged site: {package_path}") from exc
    manifest = _read_json(package_dir / "data_package.json")
    required = manifest.get("entrypoints", {}).get("web", {}).get("required")
    files = manifest.get("files")
    if not isinstance(required, list) or not isinstance(files, dict):
        raise RuntimeError("default package manifest has no web runtime contract")
    if "visualization_facts" not in required:
        raise RuntimeError("visualization_facts is not a required web entrypoint")

    viz_meta = files.get("visualization_facts")
    if not isinstance(viz_meta, dict) or not isinstance(viz_meta.get("path"), str):
        raise RuntimeError("visualization_facts file metadata is missing")
    viz_path = package_dir / viz_meta["path"]
    if not viz_path.is_file():
        raise RuntimeError(f"required runtime file is missing: {viz_path}")

    facts = _read_json(viz_path)
    if facts.get("schema_version") != viz_meta.get("schema_version"):
        raise RuntimeError("visualization_facts schema_version does not match manifest")
    chapters = facts.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise RuntimeError("visualization_facts has no chapters")
    roll_count = 0
    for chapter in chapters:
        if isinstance(chapter, dict):
            rolls = chapter.get("rolls")
            if isinstance(rolls, list):
                roll_count += len(rolls)
    if roll_count == 0:
        raise RuntimeError("visualization_facts has no rolls to render")

    constellation_pages_count = _validate_constellation_pages(
        site_dir=site_dir, package_dir=package_dir, manifest=manifest,
    )

    return SmokeResult(
        package_id=package_id,
        chapter_count=len(chapters),
        roll_count=roll_count,
        constellation_pages_count=constellation_pages_count,
    )


def _validate_constellation_pages(
    *, site_dir: Path, package_dir: Path, manifest: dict
) -> int:
    """Assert every cluster from the canonical lifecycle data has a deployed
    constellation page reachable at the path the info-popover link uses.

    Driven by ``constellation_lifecycle.json`` (the canonical list of which
    clusters exist) rather than by directory contents, so adding or
    removing a cluster upstream automatically updates what the smoke
    expects. If the lifecycle file isn't in the package (legacy runtime
    without RUNTIME_OPTIONAL), the constellation index regen step in
    deploy-pages.yml was skipped and we return 0 — caller decides whether
    to fail.
    """
    files = manifest.get("files", {}) or {}
    lifecycle_meta = files.get("constellation_lifecycle")
    if not isinstance(lifecycle_meta, dict) or not isinstance(lifecycle_meta.get("path"), str):
        # Optional runtime input absent — no canonical list to check against.
        # Still flag if the staged site somehow has constellation pages anyway,
        # so the smoke surfaces a "you forgot to update the manifest" case.
        if (site_dir / "web" / "constellations" / "index.html").is_file():
            raise RuntimeError(
                "web/constellations/ is staged but the runtime manifest has "
                "no constellation_lifecycle — these states must agree"
            )
        return 0

    lifecycle_path = package_dir / lifecycle_meta["path"]
    if not lifecycle_path.is_file():
        raise RuntimeError(f"manifest references missing file: {lifecycle_path}")
    lifecycle = _read_json(lifecycle_path)
    clusters = lifecycle.get("constellations") or []
    if not isinstance(clusters, list) or not clusters:
        raise RuntimeError("constellation_lifecycle has no clusters")

    top_index = site_dir / "web" / "constellations" / "index.html"
    if not top_index.is_file():
        raise RuntimeError(
            "info-popover link target missing: "
            f"{top_index.relative_to(site_dir)}"
        )

    missing: list[str] = []
    miscontent: list[str] = []
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        slug = cluster.get("slug")
        name = cluster.get("name")
        if not isinstance(slug, str) or not isinstance(name, str):
            continue
        page = site_dir / "web" / "constellations" / slug / "index.html"
        if not page.is_file():
            missing.append(slug)
            continue
        body = page.read_text()
        if name not in body:
            miscontent.append(f"{slug} (expected name {name!r} in body)")

    if missing:
        raise RuntimeError(
            f"constellation pages missing for: {', '.join(missing)}"
        )
    if miscontent:
        raise RuntimeError(
            "constellation pages have wrong content: " + "; ".join(miscontent)
        )
    return len(clusters)


def _finite_number(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in {float("inf"), float("-inf")} else None


def _roll_word_position(
    *, raw_roll: dict, chapter_start: int, chapter_end: int, index: int, total_rolls: int
) -> int:
    for key in (
        "epub_word_offset_predicted",
        "display_word_position_epub",
        "cumulative_word_offset",
        "display_cumulative_word_offset",
        "source_cumulative_word_offset",
    ):
        position = _finite_number(raw_roll.get(key))
        if position is not None:
            return max(0, round(position))

    chapter_span = max(0, chapter_end - chapter_start)
    for key in (
        "display_word_position",
        "word_position",
        "source_word_position",
        "mechanical_word_position",
    ):
        local_position = _finite_number(raw_roll.get(key))
        if local_position is None:
            continue
        return round(chapter_start + min(max(local_position, 0), chapter_span))

    if raw_roll.get("source_kind") == "trigger":
        return round(chapter_start)
    fraction = (index + 1) / ((total_rolls or 0) + 1)
    return round(chapter_start + chapter_span * fraction)


def _early_chapter_probe(facts: dict) -> EarlyChapterProbe:
    chapters = facts.get("chapters")
    if not isinstance(chapters, list) or not chapters or not isinstance(chapters[0], dict):
        raise RuntimeError("visualization_facts has no first chapter for browser smoke")

    first = chapters[0]
    first_chapter_num = str(first.get("chapter_num") or "1")
    first_chapter_words = int(_finite_number(first.get("total_word_count")) or 0)
    probe_word = max(0, first_chapter_words - 1)

    chapter_start = 0
    hits = 0
    misses = 0
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        chapter_words = int(_finite_number(chapter.get("total_word_count")) or 0)
        chapter_end = chapter_start + chapter_words
        rolls = chapter.get("rolls")
        if isinstance(rolls, list):
            for index, raw_roll in enumerate(rolls):
                if not isinstance(raw_roll, dict):
                    continue
                position = _roll_word_position(
                    raw_roll=raw_roll,
                    chapter_start=chapter_start,
                    chapter_end=chapter_end,
                    index=index,
                    total_rolls=len(rolls),
                )
                if position > probe_word:
                    continue
                if raw_roll.get("outcome") == "hit":
                    hits += 1
                elif raw_roll.get("outcome") == "miss":
                    misses += 1
        chapter_start = chapter_end

    return EarlyChapterProbe(
        chapter_num=first_chapter_num,
        word_position=probe_word,
        hits=hits,
        misses=misses,
    )


@contextlib.contextmanager
def _served_site(site_dir: Path) -> Iterator[str]:
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *args,
        directory=str(site_dir),
        **kwargs,
    )
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{port}/web/"
        finally:
            httpd.shutdown()
            thread.join(timeout=5)


def smoke_browser(*, site_dir: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "browser smoke requires playwright; install it and run "
            "`python3 -m playwright install chromium`"
        ) from exc

    _package_dir, viz_path = _default_runtime_paths(site_dir)
    probe = _early_chapter_probe(_read_json(viz_path))

    with _served_site(site_dir) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.add_init_script(
                """
                localStorage.setItem("bcf:preview-port-storage-version", "2");
                localStorage.setItem("bcf:bookmark:word_position", String(window.__BCF_SMOKE_WORD__));
                localStorage.setItem("bcf:mode", "playthrough");
                """.replace("window.__BCF_SMOKE_WORD__", str(probe.word_position))
            )
            messages: list[str] = []
            page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text}"))
            page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
            page.goto(url, wait_until="networkidle")
            page.wait_for_selector("#scrubber-playhead", timeout=15_000)
            width = page.locator(".scrubber-scroller").bounding_box()["width"]
            stat_text = page.locator(".stat-strip").inner_text(timeout=15_000)
            browser.close()
    errors = [msg for msg in messages if msg.startswith(("error:", "pageerror:"))]
    if errors:
        raise RuntimeError("browser console errors during smoke: " + "; ".join(errors))
    if width <= 0:
        raise RuntimeError("scrubber rendered with zero width")
    expected_fragments = (
        f"ch {probe.chapter_num}",
        f"{probe.hits} hits",
        f"{probe.misses} misses",
    )
    stat_text_normalized = " ".join(stat_text.lower().split())
    missing = [
        fragment
        for fragment in expected_fragments
        if fragment.lower() not in stat_text_normalized
    ]
    if missing:
        raise RuntimeError(
            "early chapter roll counts mismatch: expected stat strip to include "
            f"{', '.join(expected_fragments)} at word {probe.word_position}; "
            f"missing {', '.join(missing)} from {stat_text!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, required=True)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()

    result = validate_site(site_dir=args.site_dir)
    if args.browser:
        smoke_browser(site_dir=args.site_dir)
    print(
        "smoke ok: "
        f"{result.package_id}, chapters={result.chapter_count}, "
        f"rolls={result.roll_count}, "
        f"constellation_pages={result.constellation_pages_count}"
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
