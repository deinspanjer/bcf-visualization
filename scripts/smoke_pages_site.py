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

    return SmokeResult(
        package_id=package_id,
        chapter_count=len(chapters),
        roll_count=roll_count,
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

    with _served_site(site_dir) as url:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            messages: list[str] = []
            page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text}"))
            page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
            page.goto(url, wait_until="networkidle")
            page.wait_for_selector("#scrubber-container", timeout=15_000)
            width = page.locator("#scrubber-container").bounding_box()["width"]
            browser.close()
    errors = [msg for msg in messages if msg.startswith(("error:", "pageerror:"))]
    if errors:
        raise RuntimeError("browser console errors during smoke: " + "; ".join(errors))
    if width <= 0:
        raise RuntimeError("scrubber rendered with zero width")


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
        f"{result.package_id}, chapters={result.chapter_count}, rolls={result.roll_count}"
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
