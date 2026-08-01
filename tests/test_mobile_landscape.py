"""Playwright proofs for the Phase 3 landscape tracer slice (03-01-PLAN.md).

Protected behaviors:
- render() branches to renderMobileLandscape() in landscape (Phase 3 retires
  the D-12 interim fallback); the desktop `.app` shell and the portrait
  banner never mount at a phone-landscape viewport, and the desktop-sized
  `.narrative-mount` never mounts either (D-24 — the field log is a separate
  view over the same recentRolls() model, never renderNarrativeReadout).
- cachePlaybackDomRefs()/updatePlaybackFrame()'s landscape branches keep the
  field log and cinema-scrub following the playhead through the SAME
  incremental tier portrait uses, with zero structural re-renders (D-18,
  RESEARCH Pitfall 2).
- The field log is structurally absent/em-dash-safe for the empty states
  (zero rolls anywhere, word position 0) rather than ever rendering a
  placeholder or the literal word "undefined" (UI-SPEC empty-state rows).
"""

from __future__ import annotations

import json

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
    page = browser.new_page(viewport=viewport or PHONE_LANDSCAPE)
    if init_script:
        page.add_init_script(init_script)
    if storage:
        page.add_init_script(
            "const entries = "
            + json.dumps(storage)
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


PHONE_LANDSCAPE = {"width": 844, "height": 390}
# The rotation of Phase 2's PHONE_PORTRAIT_SMALL (320x568). UI-SPEC's own
# "390x568" row for this viewport reads as a transposition — 568x320 is the
# true rotated form of the smallest in-scope portrait viewport.
PHONE_LANDSCAPE_SMALL = {"width": 568, "height": 320}

DEFAULT_STORAGE = {
    "bcf:preview-port-storage-version": "3",
    "bcf:bookmark:word_position": "0",
    # Plan 02-04's first-run Help auto-open fires whenever bcf:help-seen is
    # unset — pre-seed it so these tests exercise the landscape surface
    # normally instead of tripping the mobileSurface guard that disables
    # gesture attach while a surface is open.
    "bcf:help-seen": "true",
}


def test_landscape_tracer_renders_and_follows_playhead(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                viewport=PHONE_LANDSCAPE,
                storage=DEFAULT_STORAGE,
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            assert page.evaluate("window.__bcfLayoutMode") == "landscape"

            # renderMobileLandscape() mounts its own surface; the desktop
            # shell, the portrait banner, and the desktop-sized narrative
            # mount never do.
            expect(page.locator(".mobile-app")).to_be_visible()
            assert page.evaluate("document.querySelector('.app')") is None
            assert page.evaluate("document.querySelector('.portrait-banner')") is None
            assert page.evaluate("document.querySelector('.narrative-mount')") is None
            assert page.evaluate("document.querySelector('.mobile-gesture-probe') != null") is True

            # The rail: exactly one field log, exactly one control dock, with
            # Settings/About buttons wired through the existing data-action
            # delegation.
            assert page.locator(".mobile-sidebar .mobile-field-log").count() == 1
            assert page.locator(".mobile-sidebar .mobile-control-dock").count() == 1
            assert page.locator('[data-action="mobile-open-settings"]').count() == 1
            assert page.locator('[data-action="mobile-open-info"]').count() == 1
            assert page.evaluate("document.querySelector('.mobile-cinema-scrub-track') != null") is True

            # The cinema-scrub play button toggles playback through the
            # existing module-level delegation — no new click handler.
            play_button = page.locator('.mobile-cinema-scrub-fab[data-action="toggle-playback"]')
            expect(play_button).to_be_visible()
            assert page.evaluate("window.__bcfLayoutMode") == "landscape"

            # Playhead-following: zero structural re-renders, but the field
            # log visibly advances.
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            count_before = page.locator(".mobile-field-log-header .count").inner_text()
            live_name_before = page.evaluate(
                "document.querySelector('.mobile-field-log-live .name')?.textContent ?? ''"
            )
            play_button.click()
            page.wait_for_timeout(1000)

            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            count_after = page.locator(".mobile-field-log-header .count").inner_text()
            live_name_after = page.evaluate(
                "document.querySelector('.mobile-field-log-live .name')?.textContent ?? ''"
            )
            assert (count_after != count_before) or (live_name_after != live_name_before)

            assert console_messages == []
            browser.close()


def test_landscape_field_log_zero_and_empty_states(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Zero rolls anywhere in the story (UI-SPEC empty-zero-rolls
            #     row). tiny-default carries real rolls elsewhere, so this
            #     uses the dedicated no-rolls fixture, mirroring the portrait
            #     rail's own empty-data test. ---
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=no-rolls",
                viewport=PHONE_LANDSCAPE,
                storage=DEFAULT_STORAGE,
            )
            assert page.locator(".mobile-field-log-header").count() == 1
            assert page.locator(".mobile-field-log-list").evaluate("el => el.children.length") == 0
            assert page.locator(".mobile-cinema-scrub-inner .mobile-cinema-scrub-roll").count() == 0
            assert console_messages == []
            page.close()

            # --- Word position 0 on tiny-default (rolls exist elsewhere in
            #     the story, but none has fired yet at the playhead): the
            #     live card is absent and the header count reads "0 of N". ---
            page2, console_messages2 = _page_with_console_capture(
                browser,
                site,
                viewport=PHONE_LANDSCAPE,
                storage=DEFAULT_STORAGE,
            )
            assert page2.evaluate("document.querySelector('.mobile-field-log-live')") is None
            count_text = page2.locator(".mobile-field-log-header .count").inner_text()
            assert count_text.startswith("0 of ")
            assert console_messages2 == []
            page2.close()

            browser.close()
