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
            # Read raw textContent, not inner_text(): the header carries
            # text-transform:uppercase (Task 2 CSS), which inner_text()
            # honors visually ("0 OF 2") but the DOM text itself stays
            # "0 of 2" — this asserts the underlying string, not the render.
            count_text = page2.locator(".mobile-field-log-header .count").evaluate("el => el.textContent")
            assert count_text.startswith("0 of ")
            assert console_messages2 == []
            page2.close()

            browser.close()


def _contained(inner: dict, outer: dict, *, tolerance: float = 1.0) -> bool:
    return (
        inner["x"] >= outer["x"] - tolerance
        and inner["y"] >= outer["y"] - tolerance
        and inner["x"] + inner["width"] <= outer["x"] + outer["width"] + tolerance
        and inner["y"] + inner["height"] <= outer["y"] + outer["height"] + tolerance
    )


def _intersects(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


@pytest.mark.parametrize("viewport", [PHONE_LANDSCAPE, PHONE_LANDSCAPE_SMALL], ids=["844x390", "568x320"])
def test_landscape_layout_proportions(tmp_path, viewport):
    # MOBL-01 acceptance bar: the 224px fixed rail against a fluid sky, the
    # rail's 2/3 field log over 1/3 control dock never overlapping or
    # spilling past the viewport, and the top-cluster chips never
    # intersecting the floating cinema-scrub pill — at both the standard and
    # smallest in-scope landscape viewports (UI-SPEC backstop rows: rail
    # overflow, chip-vs-scrub collision).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=viewport, storage=DEFAULT_STORAGE,
            )

            sidebar_box = page.locator(".mobile-sidebar").bounding_box()
            stage_box = page.locator(".mobile-landscape-stage").bounding_box()
            assert sidebar_box is not None
            assert stage_box is not None
            assert sidebar_box["width"] == pytest.approx(224, abs=1)

            # The "stage is at least 70% of the viewport" acceptance bar is
            # scoped to PHONE_LANDSCAPE (844px wide) per 03-01-PLAN.md's
            # acceptance criteria — the 224px FIXED rail eats a much larger
            # proportion of the narrower PHONE_LANDSCAPE_SMALL (568px), so
            # that viewport is not held to the same ratio.
            if viewport["width"] == PHONE_LANDSCAPE["width"]:
                assert stage_box["width"] >= 0.70 * viewport["width"]

            field_log_box = page.locator(".mobile-field-log").bounding_box()
            dock_box = page.locator(".mobile-control-dock").bounding_box()
            assert field_log_box is not None
            assert dock_box is not None
            assert _contained(field_log_box, sidebar_box)
            assert _contained(dock_box, sidebar_box)
            # Field log sits above the dock — their vertical ranges must not
            # intersect.
            assert field_log_box["y"] + field_log_box["height"] <= dock_box["y"] + 1
            # The control dock never spills past the bottom of the viewport.
            assert dock_box["y"] + dock_box["height"] <= viewport["height"] + 1

            cluster_box = page.locator(".mobile-top-cluster").bounding_box()
            scrub_box = page.locator(".mobile-cinema-scrub").bounding_box()
            assert cluster_box is not None
            assert scrub_box is not None
            assert not _intersects(cluster_box, scrub_box)

            # D-32: the body scroll-lock now covers landscape too (previously
            # scoped to `@media (orientation: portrait)` only, since the
            # landscape fallback used to render the scrollable desktop shell).
            assert page.evaluate("getComputedStyle(document.body).overflowY") == "hidden"

            assert console_messages == []
            browser.close()


def test_landscape_body_scroll_lock_still_covers_portrait(tmp_path):
    # D-32 regression companion to test_landscape_layout_proportions above:
    # un-nesting the body lock must not accidentally stop applying it to
    # portrait.
    playwright_api = pytest.importorskip("playwright.sync_api")
    portrait_viewport = {"width": 390, "height": 844}

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=portrait_viewport, storage=DEFAULT_STORAGE,
            )
            assert page.evaluate("getComputedStyle(document.body).overflowY") == "hidden"
            assert console_messages == []
            browser.close()


def test_landscape_field_log_text_containment(tmp_path):
    # D-27: the live-roll evidence quote is truncated to ~100 chars at the
    # data layer AND hard-clamped in CSS (defense-in-depth); T-03-01: a quote
    # containing tag-looking characters renders as literal text, never
    # parsed markup. Long perk names in the recent list ellipsize rather
    # than widening the 224px rail.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            # Bookmark to word 7200 — the single dense-rolls roll carrying
            # the landscape evidence-quote fixture (see
            # tests/helpers/web_runtime_site.py's LANDSCAPE_EVIDENCE_QUOTE_TEXT)
            # — so it is the LIVE roll (recentRolls' element 0) at load.
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_LANDSCAPE,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": "7200",
                    "bcf:help-seen": "true",
                },
            )

            live_sub = page.locator(".mobile-field-log-live .sub")
            expect(live_sub).to_be_visible()
            sub_text = live_sub.inner_text()
            # Truncated to <=100 chars at the data layer plus the two
            # surrounding straight-quote characters mobileFieldLogSubChildren
            # wraps the quote in.
            assert len(sub_text) <= 102

            # T-03-01: zero element children other than the `em` wrapper —
            # specifically no `b` (or any other) tag ever appears — while the
            # literal angle-bracket characters from the fixture quote survive
            # as plain text.
            assert page.locator(".mobile-field-log-live .sub b").count() == 0
            assert "<" in sub_text and ">" in sub_text

            # D-27 hard clamp: the rendered box stays within ~3 line-heights
            # (9.5px font, 1.3 line-height => ~12.35px/line) even though the
            # untruncated source quote is far longer.
            sub_box = live_sub.bounding_box()
            assert sub_box is not None
            assert sub_box["height"] <= (3 * 9.5 * 1.3) + 6

            # Long perk names in the recent list never widen the rail.
            list_client_width = page.locator(".mobile-field-log-list").evaluate("el => el.clientWidth")
            for name_locator in page.locator(".mobile-field-log-entry .name").all():
                name_box = name_locator.bounding_box()
                assert name_box is not None
                assert name_box["width"] <= list_client_width + 1

            # The list can scroll internally without pushing the control dock
            # off-screen.
            dock_box = page.locator(".mobile-control-dock").bounding_box()
            assert dock_box is not None
            assert dock_box["y"] + dock_box["height"] <= PHONE_LANDSCAPE["height"] + 1

            assert console_messages == []
            browser.close()
