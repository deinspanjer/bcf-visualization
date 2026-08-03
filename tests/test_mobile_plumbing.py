"""Playwright proofs for the Phase 1 mobile plumbing tracer slice.

Protected behaviors (see .planning/phases/01-mobile-state-gesture-plumbing/):
- app.layoutMode / window.__bcfLayoutMode derive from the exact CSS breakpoint
  query and stay correct across rotation (D-06, MOBF-02).
- Gesture callbacks fire exactly once per gesture through forced re-renders and
  a re-render landing mid-drag — no double-binding, no stale listeners, and the
  gesture path never triggers a structural render (D-07, MOBF-03).
- The bcf:* preference keys round-trip through localStorage via allow-list
  readers, and the STORAGE_VERSION 2->3 bump purges stale keys (D-09,
  MOBF-04). bcf:portrait-dismissed was removed from the clear-list in
  Phase 4 (MOBX-01/D-37) when the banner it gated was deleted — it is now
  orphaned dead data, left un-purged by design (RESEARCH Pitfall 5), and
  the version-bump test below asserts it survives untouched.
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
    page = browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
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


GESTURE_STATS_INIT = (
    "window.__bcfGestureStats = "
    "{ taps: 0, doubleTaps: 0, swipeSteps: 0, swipeEnds: 0, attaches: 0 };"
)

PHONE_PORTRAIT = {"width": 390, "height": 844}
PHONE_LANDSCAPE = {"width": 844, "height": 390}


def _probe_center(page):
    probe = page.wait_for_selector(".mobile-gesture-probe")
    box = probe.bounding_box()
    assert box is not None
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _gesture_stats(page):
    return page.evaluate("window.__bcfGestureStats")


def test_layout_mode_matrix_matches_css_breakpoint(tmp_path):
    # (max-width: 900px), (orientation: portrait) and (max-width: 1100px):
    # phones are portrait/landscape, iPad landscape stays desktop, iPad
    # portrait falls inside the mobile envelope.
    playwright_api = pytest.importorskip("playwright.sync_api")

    matrix = [
        ((1280, 900), "desktop"),
        ((390, 844), "portrait"),
        ((844, 390), "landscape"),
        ((1024, 768), "desktop"),
        ((768, 1024), "portrait"),
    ]

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            for (width, height), expected in matrix:
                page, console_messages = _page_with_console_capture(
                    browser, site, viewport={"width": width, "height": height},
                )
                assert page.evaluate("window.__bcfLayoutMode") == expected, (
                    f"{width}x{height} should report {expected}"
                )
                assert console_messages == []
                page.close()
            browser.close()


def test_layout_mode_survives_rotation(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT,
            )

            assert page.evaluate("window.__bcfLayoutMode") == "portrait"
            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            page.set_viewport_size(PHONE_PORTRAIT)
            page.wait_for_function("window.__bcfLayoutMode === 'portrait'")
            assert console_messages == []

            browser.close()


def test_gestures_fire_exactly_once_without_structural_renders(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                viewport=PHONE_PORTRAIT,
                init_script=GESTURE_STATS_INIT
                + " window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            x, y = _probe_center(page)

            # Single tap fires exactly once.
            page.mouse.click(x, y)
            assert _gesture_stats(page)["taps"] == 1

            # Clear the double-tap window before the next gesture segment.
            page.wait_for_timeout(400)

            # Two taps inside DOUBLE_TAP_INTERVAL fire one doubleTap (the first
            # press of the pair also fires its immediate single tap per the
            # gesture contract's ambiguity resolution).
            page.mouse.dblclick(x, y)
            stats = _gesture_stats(page)
            assert stats["doubleTaps"] == 1
            assert stats["taps"] == 2

            page.wait_for_timeout(400)

            # Horizontal swipe with intermediate moves: engagement costs
            # SWIPE_ENGAGE (24px), then one step per SCRUB_STEP_PX (56px), so a
            # 140px drag yields exactly 2 steps (24 + 2*56 = 136 <= 140 < 192)
            # and one swipeEnd on release. Structural render count must not
            # move — gestures ride the incremental tier only (D-07).
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            page.mouse.move(x, y)
            page.mouse.down()
            for dx in range(8, 141, 8):
                page.mouse.move(x + dx, y)
            page.mouse.up()

            stats = _gesture_stats(page)
            assert stats["swipeSteps"] == 2
            assert stats["swipeEnds"] == 1
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_gesture_attach_survives_forced_rerenders_without_double_fire(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, init_script=GESTURE_STATS_INIT,
            )

            page.wait_for_selector(".mobile-gesture-probe")
            attaches_before = _gesture_stats(page)["attaches"]
            assert attaches_before >= 1

            # Force two structural re-renders via layout transitions.
            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            page.set_viewport_size(PHONE_PORTRAIT)
            page.wait_for_function("window.__bcfLayoutMode === 'portrait'")

            stats = _gesture_stats(page)
            assert stats["attaches"] == attaches_before + 2

            # One further tap fires exactly once — no accumulated listeners.
            taps_before = stats["taps"]
            x, y = _probe_center(page)
            page.mouse.click(x, y)
            assert _gesture_stats(page)["taps"] == taps_before + 1
            assert console_messages == []

            browser.close()


def test_mid_drag_rerender_is_safe_and_fresh_probe_fires_once(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, init_script=GESTURE_STATS_INIT,
            )

            x, y = _probe_center(page)

            # Begin an engaged drag, then flip orientation mid-drag: the
            # structural render tears the probe down while the pointer is held.
            page.mouse.move(x, y)
            page.mouse.down()
            for dx in range(8, 41, 8):
                page.mouse.move(x + dx, y)
            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            page.mouse.up()

            # A fresh tap on the re-created probe fires exactly once.
            taps_before = _gesture_stats(page)["taps"]
            x2, y2 = _probe_center(page)
            page.mouse.click(x2, y2)
            assert _gesture_stats(page)["taps"] == taps_before + 1
            assert console_messages == []

            browser.close()


def test_storage_version_bump_purges_stale_keys(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:portrait-dismissed": "true",
                    "bcf:tap-to-pause": "false",
                },
            )

            assert page.evaluate(
                "localStorage.getItem('bcf:preview-port-storage-version')"
            ) == "3"
            # bcf:portrait-dismissed is now orphaned dead data (Phase 4 deleted
            # the rotate-to-landscape banner it gated, MOBX-01/D-37; RESEARCH
            # Pitfall 5). Nothing reads it anymore, and it is deliberately NOT
            # in migratePreviewStorage()'s clear-list — a STORAGE_VERSION bump
            # for its own sake would purge every bcf:* key across 34 seeded
            # test-fixture sites for zero functional gain. It survives the
            # version-bump migration untouched.
            assert page.evaluate("localStorage.getItem('bcf:portrait-dismissed')") == "true"
            assert page.evaluate("localStorage.getItem('bcf:tap-to-pause')") is None
            assert console_messages == []

            browser.close()


def test_mobile_pref_setters_round_trip_across_reload(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={"bcf:preview-port-storage-version": "3"},
            )

            page.evaluate("window.__bcfMobile.setMobileTimelineZoom(4)")
            page.evaluate("window.__bcfMobile.setTapToPause(false)")
            assert page.evaluate("localStorage.getItem('bcf:timeline-zoom')") == "4"
            assert page.evaluate("localStorage.getItem('bcf:tap-to-pause')") == "false"

            page.reload(wait_until="networkidle")
            assert page.evaluate("window.__bcfPrefs.mobileTimelineZoom") == 4
            assert page.evaluate("window.__bcfPrefs.tapToPause") is False
            assert console_messages == []

            browser.close()


def test_css_foundation_touch_action_and_viewport_primitives(tmp_path):
    # web/mobile.css (MOBF-05, D-08): gesture-surface touch-action/
    # overscroll-behavior classes and the svh/dvh + safe-area-inset
    # primitives, all scoped behind the character-identical mobile
    # breakpoint — inert (no element carries them) until Phase 2/3 apply
    # them to real sky/rail/dock nodes, but computed-style-verifiable now.
    playwright_api = pytest.importorskip("playwright.sync_api")

    probe_script = """
    () => {
      const surface = document.createElement("div");
      surface.className = "mobile-sky-surface";
      document.body.appendChild(surface);
      const skyStyle = getComputedStyle(surface);
      const touchActionSky = skyStyle.touchAction;
      const overscrollSky = skyStyle.overscrollBehavior;

      surface.className = "mobile-rail-surface";
      const touchActionRail = getComputedStyle(surface).touchAction;
      surface.remove();

      const vhProbe = document.createElement("div");
      vhProbe.style.height = "var(--mobile-vh)";
      document.body.appendChild(vhProbe);
      const vhHeight = getComputedStyle(vhProbe).height;
      vhProbe.remove();

      const safeProbe = document.createElement("div");
      safeProbe.style.paddingBottom = "var(--safe-bottom)";
      document.body.appendChild(safeProbe);
      const safeBottom = getComputedStyle(safeProbe).paddingBottom;
      safeProbe.remove();

      return { touchActionSky, overscrollSky, touchActionRail, vhHeight, safeBottom };
    }
    """

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT,
            )

            result = page.evaluate(probe_script)
            assert result["touchActionSky"] == "pan-y"
            assert "contain" in result["overscrollSky"]
            assert result["touchActionRail"] == "none"
            assert result["vhHeight"] == f"{PHONE_PORTRAIT['height']}px"
            assert result["safeBottom"] == "0px"

            # Desktop (media block not matched): surface classes fall back to
            # browser defaults — the mobile foundation is inert above the
            # breakpoint, proving the freeze holds.
            page.set_viewport_size({"width": 1280, "height": 900})
            desktop_touch_action = page.evaluate(
                """
                () => {
                  const surface = document.createElement("div");
                  surface.className = "mobile-sky-surface";
                  document.body.appendChild(surface);
                  const value = getComputedStyle(surface).touchAction;
                  surface.remove();
                  return value;
                }
                """
            )
            assert desktop_touch_action == "auto"
            assert console_messages == []

            browser.close()


_FORCE_HIDDEN_SCRIPT = """
() => {
  Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}
"""


def test_visibilitychange_pauses_playback_on_mobile_only(tmp_path):
    # D-02: hiding the page pauses playthrough on mobile layouts, with state
    # intact (no auto-resume, no reset); the desktop path is unchanged —
    # the single existing handler still only persists the bookmark there.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # Mobile (phone portrait): hidden -> paused, state intact.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT,
            )
            page.click('button[aria-label="Play"]')
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()

            page.evaluate(_FORCE_HIDDEN_SCRIPT)

            # Paused (not just relabeled): the word-position readout stops
            # advancing once hidden — state intact, no further playback tick.
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            readout_at_pause = page.locator(".readout-meta").inner_text()
            page.wait_for_timeout(300)
            readout_after_wait = page.locator(".readout-meta").inner_text()
            assert readout_after_wait == readout_at_pause
            assert console_messages == []
            page.close()

            # Desktop: same play + forced-hidden sequence leaves playback
            # running — only the bookmark-persist branch fires.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport={"width": 1280, "height": 900},
            )
            page.click('button[aria-label="Play"]')
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()

            page.evaluate(_FORCE_HIDDEN_SCRIPT)

            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            assert console_messages == []
            page.close()

            browser.close()


def test_out_of_set_stored_values_fall_back_to_defaults(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:timeline-zoom": "3",
                    "bcf:haptics": "banana",
                },
            )

            assert page.evaluate("window.__bcfPrefs.mobileTimelineZoom") == 1
            assert page.evaluate("window.__bcfPrefs.haptics") is True
            assert console_messages == []

            browser.close()
