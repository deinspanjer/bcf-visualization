"""Playwright proofs for the Phase 2 portrait tracer slice (02-01-PLAN.md).

Protected behaviors:
- render() branches to renderMobilePortrait() only in portrait (D-12); the
  desktop `.app` shell never mounts at a phone-portrait viewport.
- updatePlaybackFrame()'s portrait early return lands before the desktop
  `#scrubber-playhead` gate, so portrait playback produces zero structural
  re-renders and no recursion (D-18, RESEARCH Pitfall 2).
- The mini-rail commits scrubs through the existing setWordPos path only
  (D-17) and persists the bookmark on release.
"""

from __future__ import annotations

import pytest

from tests.helpers.web_runtime_site import staged_web_runtime_site


def _chromium_browser_or_skip(playwright, playwright_api):
    try:
        return playwright.chromium.launch()
    except playwright_api.Error as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        raise


def _page_with_console_capture(
    browser,
    site,
    path="/web/?dataPackage=tiny-default",
    *,
    viewport=None,
    storage: dict[str, str] | None = None,
    init_script: str | None = None,
):
    page = browser.new_page(viewport=viewport or PHONE_PORTRAIT)
    if init_script:
        page.add_init_script(init_script)
    if storage:
        import json as _json

        page.add_init_script(
            "const entries = "
            + _json.dumps(storage)
            + "; for (const [key, value] of Object.entries(entries)) localStorage.setItem(key, value);"
        )
    messages: list[str] = []
    page.on(
        "console",
        lambda msg: messages.append(f"{msg.type}: {msg.text}") if msg.type in {"error", "pageerror"} else None,
    )
    page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
    page.goto(site.url_for(path), wait_until="networkidle")
    return page, messages


PHONE_PORTRAIT = {"width": 390, "height": 844}
PHONE_PORTRAIT_SMALL = {"width": 320, "height": 568}

DEFAULT_STORAGE = {
    "bcf:preview-port-storage-version": "3",
    "bcf:bookmark:word_position": "0",
}


def test_portrait_tracer_renders_sky_dock_and_rail_scrub_commits(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            expect = playwright_api.expect
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )

            expect(page.locator(".mobile-app")).to_be_visible()
            expect(page.locator(".mobile-sky")).to_be_visible()
            expect(page.locator(".mobile-dock")).to_be_visible()
            expect(page.locator(".mobile-rail")).to_be_visible()
            assert page.evaluate("document.querySelector('.app')") is None
            assert page.evaluate("document.querySelector('.mobile-app .viewport')") is None
            assert page.evaluate("document.querySelector('.mobile-app .app')") is None

            # Phase 1 probe stays mounted (F-01) and is unstealable by portrait
            # content — z-index pinned to the max 32-bit signed int.
            probe_z_index = page.evaluate(
                "getComputedStyle(document.querySelector('.mobile-gesture-probe')).zIndex"
            )
            assert probe_z_index == "2147483647"

            # touch-action policy: sky claims vertical scroll only, rail claims
            # full custom gesture control (Phase 1 CSS foundation, D-03).
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.mobile-sky')).touchAction"
            ) == "pan-y"
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.mobile-rail')).touchAction"
            ) == "none"

            # Exactly one play/pause control and one readout-meta element —
            # the Phase 1 plumbing tests' invariant (F-01) still holds.
            assert page.evaluate(
                "document.querySelectorAll('button[aria-label=\"Play\"], button[aria-label=\"Pause\"]').length"
            ) == 1
            assert page.evaluate("document.querySelectorAll('.readout-meta').length") == 1

            meta_before = page.locator(".mobile-dock-meta").inner_text()
            playhead = page.locator(".mobile-playhead")
            left_before = playhead.evaluate("el => el.style.left")

            rail_box = page.locator(".mobile-rail").bounding_box()
            assert rail_box is not None
            x = rail_box["x"] + rail_box["width"] * 0.25
            y = rail_box["y"] + rail_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 2, y)

            meta_after = page.locator(".mobile-dock-meta").inner_text()
            left_after = playhead.evaluate("el => el.style.left")
            assert meta_after != meta_before
            assert left_after != left_before

            page.mouse.up()
            page.wait_for_timeout(50)
            bookmark = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark is not None
            assert bookmark != "0"

            assert console_messages == []
            browser.close()


def test_portrait_cinematic_renders_sky_camera_svg(tmp_path):
    # D-13: the portrait sky shows the REAL sky-camera cinematic, never the
    # prototype's procedural placeholder — mounted under .mobile-sky-camera-layer
    # (never the desktop .sky-camera-layer name, RESEARCH Pitfall 5).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        import json as _json

        facts = _json.loads(facts_path.read_text())
        first_roll_word = None
        for chapter in facts.get("chapters", []):
            rolls = chapter.get("rolls", [])
            if rolls:
                first_roll_word = rolls[0]["epub_word_offset_predicted"]
                break
        assert first_roll_word is not None

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                viewport=PHONE_PORTRAIT,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(first_roll_word),
                },
            )

            assert page.evaluate(
                "document.querySelector('.mobile-sky-camera-layer svg')"
            ) is not None
            assert console_messages == []
            browser.close()


def test_portrait_playback_has_no_recursive_renders(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                viewport=PHONE_PORTRAIT,
                storage=DEFAULT_STORAGE,
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")

            meta_before = page.locator(".mobile-dock-meta").inner_text()
            page.click('button[aria-label="Play"]')
            page.wait_for_timeout(1500)

            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            meta_after = page.locator(".mobile-dock-meta").inner_text()
            assert meta_after != meta_before
            assert console_messages == []

            browser.close()
