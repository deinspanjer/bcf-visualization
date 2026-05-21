from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.helpers.web_runtime_site import _serve


def _write_workbench_site(site_root: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    web_constellations = site_root / "web" / "constellations"
    data_size = site_root / "data" / "constellations" / "09-size"
    web_constellations.mkdir(parents=True)
    data_size.mkdir(parents=True)
    shutil.copy2(
        repo_root / "web" / "constellations" / "tracing-workbench.html",
        web_constellations / "tracing-workbench.html",
    )
    (web_constellations / "index.html").write_text(
        """<!doctype html>
<table><tbody>
<tr>
  <td>09</td>
  <td><a href="09-size/index.html">Size</a></td>
  <td></td>
  <td>17 perks</td>
  <td>8</td>
  <td>17</td>
  <td>synthetic size concept</td>
</tr>
</tbody></table>
""",
    )
    (data_size / "current.svg").write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"
     data-vertex-source="perks" color="oklch(0.82 0.14 196)">
  <title>Size</title>
  <desc>Synthetic size constellation.</desc>
  <defs><symbol id="star-mark"><circle cx="5" cy="5" r="5"/></symbol></defs>
  <polyline class="cluster-outline" fill="none" points="10,10 90,90"/>
  <g class="jump-markers">
    <use href="#star-mark" x="5" y="5" width="10" height="10"/>
  </g>
</svg>
""",
    )
    (data_size / "metadata.json").write_text(
        '{\n  "schema_version": 1,\n  "intended_image": "synthetic size reference"\n}\n',
    )


def _chromium_browser_or_skip(playwright, playwright_api):
    try:
        return playwright.chromium.launch()
    except playwright_api.Error as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        raise


def test_workbench_static_mode_loads_editable_constellation_source_from_data_tree(tmp_path: Path) -> None:
    """Clicking Edit from generated web pages must load the hand-authored
    SVG/metadata source, even though publish output lives under web/.
    """
    playwright_api = pytest.importorskip("playwright.sync_api")
    site_root = tmp_path / "workbench-site"
    _write_workbench_site(site_root)

    with _serve(site_root) as base_url:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            messages: list[str] = []
            page.on(
                "console",
                lambda msg: messages.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None,
            )
            page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))

            page.goto(
                f"{base_url}/web/constellations/tracing-workbench.html?constellation=09-size",
                wait_until="networkidle",
            )

            expect = playwright_api.expect
            expect(page.locator("#sourceMessage")).to_contain_text("Loaded 09-size from static fetch.")
            expect(page.locator("#statusLine")).to_have_text("Size: 09-size/current.svg")
            expect(page.locator("#intendedImage")).to_have_value("synthetic size reference")
            expect(page.locator("#vertexCount")).to_have_text("2")
            assert "data-vertex-source=\"perks\"" in page.locator("#exportText").input_value()
            assert messages == []

            browser.close()
