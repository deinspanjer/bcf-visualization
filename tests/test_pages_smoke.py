from __future__ import annotations

import json
import sys
import types
from contextlib import contextmanager
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n")


def _write_minimal_site(
    site: Path,
    *,
    broken: bool = False,
    smoke_status: str = "passed",
    package_path: str = "data/packages/pkg-smoke",
) -> None:
    (site / "web").mkdir(parents=True)
    (site / "web" / "index.html").write_text("<!doctype html><div id='app'></div>\n")
    package_id = "pkg-smoke"
    _write_json(
        site / "data" / "packages.json",
        {
            "schema_version": 1,
            "default_package_id": package_id,
            "packages": [
                {
                    "package_id": package_id,
                    "path": package_path,
                    "smoke_status": smoke_status,
                }
            ],
        },
    )
    _write_json(
        site / "data" / "packages" / package_id / "data_package.json",
        {
            "package_id": package_id,
            "contract": "bcf-visualization-data",
            "contract_version": 1,
            "files": {"visualization_facts": {"path": "visualization_facts.json", "schema_version": 2}},
            "entrypoints": {"web": {"required": ["visualization_facts"], "optional": []}},
        },
    )
    if broken:
        return
    _write_json(
        site / "data" / "packages" / package_id / "visualization_facts.json",
        {
            "schema_version": 2,
            "chapters": [
                {
                    "chapter_num": "1",
                    "total_word_count": 100,
                    "cumulative_words_through_chapter": 100,
                    "rolls": [{"global_roll_number": 1, "outcome": "miss"}],
                }
            ],
        },
    )


def test_pages_smoke_accepts_staged_site_with_default_package(tmp_path: Path) -> None:
    from scripts import smoke_pages_site

    site = tmp_path / "site"
    _write_minimal_site(site)

    result = smoke_pages_site.validate_site(site_dir=site)

    assert result.package_id == "pkg-smoke"
    assert result.chapter_count == 1
    assert result.roll_count == 1


def test_pages_smoke_rejects_missing_required_runtime_file(tmp_path: Path) -> None:
    from scripts import smoke_pages_site

    site = tmp_path / "site"
    _write_minimal_site(site, broken=True)

    with pytest.raises(RuntimeError, match="required runtime file is missing"):
        smoke_pages_site.validate_site(site_dir=site)


def test_pages_smoke_rejects_default_package_without_passed_status(tmp_path: Path) -> None:
    from scripts import smoke_pages_site

    site = tmp_path / "site"
    _write_minimal_site(site, smoke_status="unknown")

    with pytest.raises(RuntimeError, match="smoke_status is not passed"):
        smoke_pages_site.validate_site(site_dir=site)


def test_pages_smoke_rejects_default_package_path_escape(tmp_path: Path) -> None:
    from scripts import smoke_pages_site

    site = tmp_path / "site"
    _write_minimal_site(site, package_path="../outside")

    with pytest.raises(RuntimeError, match="path escapes staged site"):
        smoke_pages_site.validate_site(site_dir=site)


def test_browser_smoke_waits_for_current_scrubber_dom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import smoke_pages_site

    site = tmp_path / "site"
    _write_minimal_site(site)
    waited: list[str] = []
    measured: list[str] = []

    class FakeLocator:
        def __init__(self, selector: str) -> None:
            self.selector = selector

        def bounding_box(self) -> dict[str, int]:
            measured.append(self.selector)
            return {"width": 1280}

    class FakePage:
        def on(self, *_args: object) -> None:
            return None

        def goto(self, *_args: object, **_kwargs: object) -> None:
            return None

        def wait_for_selector(self, selector: str, **_kwargs: object) -> None:
            waited.append(selector)

        def locator(self, selector: str) -> FakeLocator:
            return FakeLocator(selector)

    class FakeBrowser:
        def new_page(self, **_kwargs: object) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakeChromium:
        def launch(self) -> FakeBrowser:
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

        def __enter__(self) -> "FakePlaywright":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    @contextmanager
    def fake_served_site(_site_dir: Path):
        yield "http://127.0.0.1:1/web/"

    fake_playwright_module = types.SimpleNamespace(
        sync_playwright=lambda: FakePlaywright()
    )

    monkeypatch.setattr(smoke_pages_site, "_served_site", fake_served_site)
    monkeypatch.setitem(
        sys.modules,
        "playwright.sync_api",
        fake_playwright_module,
    )

    smoke_pages_site.smoke_browser(site_dir=site)

    assert waited == ["#scrubber-playhead"]
    assert measured == [".scrubber-scroller"]
