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
# Real large-phone landscape widths. 844x390 (above) is an iPhone 12/13/14-class
# viewport and fit under the OLD `(max-width: 900px)` landscape clause, which is
# exactly why CI stayed green while a real iPhone 16 Pro Max — 956x390, measured
# over the WebKit inspector during the Phase 3 gate — fell through to the desktop
# shell and never mounted the landscape layout at all. Any landscape breakpoint
# change must be proven against these, not just against 844.
PHONE_LANDSCAPE_LARGE = {"width": 956, "height": 390}   # iPhone 16 Pro Max
PHONE_LANDSCAPE_LARGE_ALT = {"width": 932, "height": 430}  # iPhone 14/15 Pro Max
# The rotation of Phase 2's PHONE_PORTRAIT_SMALL (320x568). UI-SPEC's own
# "390x568" row for this viewport reads as a transposition — 568x320 is the
# true rotated form of the smallest in-scope portrait viewport.
PHONE_LANDSCAPE_SMALL = {"width": 568, "height": 320}
# Phase 3 Task 2 (03-03-PLAN.md): the rotation tests below start sessions in
# portrait — matches tests/test_mobile_portrait.py's own PHONE_PORTRAIT.
PHONE_PORTRAIT = {"width": 390, "height": 844}

DEFAULT_STORAGE = {
    "bcf:preview-port-storage-version": "3",
    "bcf:bookmark:word_position": "0",
    # Plan 02-04's first-run Help auto-open fires whenever bcf:help-seen is
    # unset — pre-seed it so these tests exercise the landscape surface
    # normally instead of tripping the mobileSurface guard that disables
    # gesture attach while a surface is open.
    "bcf:help-seen": "true",
}

# tiny-default's whole story is only 10000 words — at the default 5000
# words/sec playback speed it finishes (and auto-pauses at the end) inside
# 2 seconds, well short of the 4000ms auto-hide boundary the timing tests
# below need to hold playback open across. Merge this into a test's storage
# dict to keep playback running for the full duration of a multi-second
# real-time wait.
SLOW_PLAYBACK_STORAGE = {"bcf:playback:speed:v2": "50"}


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

            # --- MOBL-02 edge criterion: on the zero-roll story, the
            #     cinema-scrub still reveals/hides and the play FAB still
            #     toggles, with no roll markers on the track. Auto-hide must
            #     not assume at least one roll exists anywhere in its path.
            #     no-rolls' whole story is only 10000 words — at the default
            #     5000 words/sec it would finish (and auto-pause) inside 2s,
            #     well short of the 4000ms boundary this case needs to
            #     exercise, so this seeds a much slower speed to keep
            #     playback running for the full window. ---
            page3, console_messages3 = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=no-rolls",
                viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE},
            )
            fab = page3.locator('.mobile-cinema-scrub-fab[aria-label="Play"]')
            fab.click()
            page3.wait_for_timeout(4100)
            assert page3.evaluate(
                "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
            ) is True
            page3.locator(".mobile-sky").click(force=True)
            page3.wait_for_timeout(50)
            assert page3.evaluate(
                "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
            ) is False
            assert page3.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]').count() == 1
            assert console_messages3 == []
            page3.close()

            # --- FA-MOBL-03 backstop: rotating into landscape at word
            #     position 0 on the zero-roll story throws nothing and
            #     renders the empty field log and zero-marker scrub in the
            #     freshly-mounted landscape DOM. ---
            page4, console_messages4 = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=no-rolls",
                viewport=PHONE_PORTRAIT,
                storage=DEFAULT_STORAGE,
            )
            page4.set_viewport_size(PHONE_LANDSCAPE)
            page4.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            assert page4.locator(".mobile-field-log-header").count() == 1
            assert page4.locator(".mobile-field-log-list").evaluate("el => el.children.length") == 0
            assert page4.locator(".mobile-cinema-scrub-inner .mobile-cinema-scrub-roll").count() == 0
            assert console_messages4 == []
            page4.close()

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


def _dense_rolls_facts(site):
    facts_path = site.root / "data/packages/dense-rolls/visualization_facts.json"
    return json.loads(facts_path.read_text())


def _dense_rolls_positions_sorted(facts: dict) -> list[int]:
    return sorted(
        roll["epub_word_offset_predicted"]
        for chapter in facts.get("chapters", [])
        for roll in chapter.get("rolls", [])
    )


def _tiny_default_facts(site):
    facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
    return json.loads(facts_path.read_text())


def _facts_total_words(facts: dict) -> int:
    # Mirrors web/app.js buildStory()'s total_words — see test_mobile_
    # portrait.py's own copy of this helper for the module-scope rationale.
    chapters = facts.get("chapters", [])
    return chapters[-1]["cumulative_words_through_chapter"] if chapters else 0


def test_landscape_sky_gesture_contract(tmp_path):
    # MOBL-02/D-34: the sky gesture callbacks generalize verbatim from
    # portrait's own proofs (test_sky_gesture_contract and
    # test_sky_tap_is_noop_when_tap_to_pause_off in tests/test_mobile_
    # portrait.py) — a tap toggles playback when tap-to-pause is on, is a
    # no-op when it's off, a double-tap snaps to the last roll at/before the
    # playhead and resumes (never the story's final roll), and a horizontal
    # swipe steps exactly one roll per 56px of travel, with zero structural
    # re-renders across the swipe (D-07/T-02-05).
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        roll_positions = _dense_rolls_positions_sorted(facts)
        mid_word = 5000
        last_at_or_before = max(w for w in roll_positions if w <= mid_word)
        final_roll_word = roll_positions[-1]
        idx = roll_positions.index(last_at_or_before)
        forward_two = roll_positions[idx + 2]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # Each phase opens its own fresh page seeded to the same starting
            # bookmark, so a running playback tick from one phase's
            # assertions can never drift the word position the next phase's
            # assertions depend on.
            def fresh_page(extra_storage=None):
                storage = {
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(mid_word),
                    "bcf:help-seen": "true",
                }
                if extra_storage:
                    storage.update(extra_storage)
                return _page_with_console_capture(
                    browser, site, path="/web/?dataPackage=dense-rolls",
                    viewport=PHONE_LANDSCAPE, storage=storage,
                )

            # A single tap toggles playback (the cinema-scrub FAB flips Play
            # -> Pause), and a second single tap (spaced past the
            # double-tap window) flips it back.
            page, console_messages = fresh_page()
            sky = page.locator(".mobile-sky")
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]')).to_be_visible()
            sky.click()
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(400)
            sky.click()
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]')).to_be_visible()
            assert console_messages == []
            page.close()

            # Tap-to-pause off: a sky tap leaves play state unchanged.
            page, console_messages = fresh_page({"bcf:tap-to-pause": "false"})
            sky = page.locator(".mobile-sky")
            fab_label_before = page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label")
            sky.click()
            page.wait_for_timeout(100)
            assert page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label") == fab_label_before
            assert console_messages == []
            page.close()

            # Double-tap snaps the playhead to the last roll at/before the
            # pre-double-tap position and resumes — never the final roll.
            page, console_messages = fresh_page()
            sky = page.locator(".mobile-sky")
            sky.dblclick()
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(50)
            bookmark = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark == str(last_at_or_before)
            assert int(bookmark) < final_roll_word
            assert console_messages == []
            page.close()

            # Horizontal swipe: engagement costs SWIPE_ENGAGE (24px), then
            # one roll per SCRUB_STEP_PX (56px) — a 140px drag yields exactly
            # 2 roll-steps (24 + 2*56 = 136 <= 140 < 192), with zero
            # structural re-renders (gestures ride the incremental tier
            # only).
            page, console_messages = fresh_page()
            page.evaluate("window.__bcfRenderStats = { structuralRenders: 0 }")
            sky = page.locator(".mobile-sky")
            sky_box = sky.bounding_box()
            assert sky_box is not None
            x = sky_box["x"] + sky_box["width"] / 2
            y = sky_box["y"] + sky_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            for dx in range(8, 141, 8):
                page.mouse.move(x + dx, y)
            page.mouse.up()
            page.wait_for_timeout(50)
            bookmark_after_right = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark_after_right == str(forward_two)
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_landscape_cinema_scrub_drag_is_monotonic_at_every_zoom(tmp_path):
    # MOBL-02/D-17: the landscape cinema-scrub reuses the SAME
    # attachRailScrub input path and the SAME frozen-auto-pan fix (ed59087,
    # Phase 2's device-found monotonicity bug) portrait's own regression
    # proof (test_rail_drag_is_monotonic_at_every_zoom) pins — a continuous
    # rightward drag must never move the playhead backward, at every zoom
    # level, from its first commit (not rediscovered on a second device).
    #
    # Mid-drag the bookmark key is not yet written (persistBookmarkNow runs
    # on onScrubEnd), so this reads the live thumb marker's left% instead,
    # which tracks wordPos through the incremental update tier — the defect
    # this guards against lives strictly BETWEEN moves of one drag.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        total_words = _facts_total_words(_tiny_default_facts(site))

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            for zoom in (1, 2, 4, 8):
                page, console_messages = _page_with_console_capture(
                    browser,
                    site,
                    viewport=PHONE_LANDSCAPE,
                    storage={
                        "bcf:preview-port-storage-version": "3",
                        "bcf:bookmark:word_position": str(total_words // 2),
                        "bcf:timeline-zoom": str(zoom),
                        "bcf:help-seen": "true",
                    },
                )

                track_box = page.locator(".mobile-cinema-scrub-track").bounding_box()
                assert track_box is not None
                y = track_box["y"] + track_box["height"] / 2

                def playhead_pct():
                    raw = page.evaluate(
                        "() => document.querySelector('.mobile-cinema-scrub-thumb')?.style.left ?? null"
                    )
                    assert raw is not None, "landscape cinema-scrub thumb not found"
                    return float(raw.rstrip("%"))

                def x_at(fraction):
                    return track_box["x"] + track_box["width"] * fraction

                # One drag: press at 30%, then sweep right without lifting.
                page.mouse.move(x_at(0.30), y)
                page.mouse.down()
                page.wait_for_timeout(60)
                observed = [playhead_pct()]
                for fraction in (0.40, 0.50, 0.60, 0.70):
                    page.mouse.move(x_at(fraction), y)
                    page.wait_for_timeout(60)
                    observed.append(playhead_pct())
                page.mouse.up()

                # Rightward drag => playhead never goes backward. Tolerance
                # absorbs sub-pixel rounding in the percentage readback only.
                for earlier, later in zip(observed, observed[1:]):
                    assert later >= earlier - 0.01, (
                        f"zoom {zoom}x: rightward drag moved the playhead backward "
                        f"({earlier:.3f}% -> {later:.3f}%) across the full sweep {observed}"
                    )

                # And it must actually travel — a frozen mapping would be
                # monotonic too, but useless.
                assert observed[-1] > observed[0] + 1.0, (
                    f"zoom {zoom}x: drag barely moved the playhead: {observed}"
                )

                assert console_messages == []
                page.close()

            browser.close()


def test_landscape_gestures_survive_rerender_and_surface_toggle(tmp_path):
    # D-34/Pitfall 3: opening a landscape flyout detaches both gesture
    # surfaces (a sky tap while it's open never changes play state); closing
    # it re-attaches exactly once (no double-binding from a stale listener
    # surviving the structural re-render); and Tab-cycling past the last
    # focusable inside the open flyout keeps focus trapped there — landscape's
    # counterpart to test_surface_stack_focus_trap_and_back_gesture, proving
    # the D-16 focus trap re-attaches outside portrait too (Pitfall 3).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )

            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            fab_label_before = page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label")
            page.click(".mobile-sky", force=True)
            assert page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label") == fab_label_before

            # Focus trap (Pitfall 3 proof): Tab past every focusable control
            # inside the open flyout more times than it has focusable
            # children — focus stays inside, never escaping to the document.
            focusable_selector = (
                ".mobile-flyout button, .mobile-flyout [href], .mobile-flyout input, "
                ".mobile-flyout select, .mobile-flyout textarea"
            )
            focusable_count = page.evaluate(
                "(sel) => document.querySelectorAll(sel).length", focusable_selector,
            )
            for _ in range(focusable_count + 2):
                page.keyboard.press("Tab")
            assert page.evaluate(
                "document.querySelector('.mobile-flyout').contains(document.activeElement)"
            ) is True

            # Close via the backdrop, then confirm a single sky tap after the
            # structural re-render fires exactly once — a second, stale
            # listener left over from the surface toggle would double-fire
            # and desync the play state from a single tap.
            page.locator(".mobile-flyout-backdrop").click(position={"x": 5, "y": 5})
            assert page.locator(".mobile-flyout").count() == 0
            fab_label_after_close = page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label")
            page.locator(".mobile-sky").click()
            expected = "Pause" if fab_label_after_close == "Play" else "Play"
            assert page.locator(".mobile-cinema-scrub-fab").get_attribute("aria-label") == expected

            assert console_messages == []
            browser.close()


def test_landscape_chrome_autohide_boundary(tmp_path):
    # MOBL-02/D-28/D-29: the landscape chrome auto-hide idle timer fires
    # only during playback, asserted from BOTH sides of the 4000ms boundary
    # (not only the far side, per the plan's own backstop truth); an
    # interaction resets/pushes the window out; a paused reader never has
    # the timer arm at all, and pausing WHILE hidden immediately reveals and
    # holds it; only the cinema-scrub hides (D-29) — the top chips and the
    # sidebar stay visible throughout; and the whole hide/reveal cycle costs
    # zero structural re-renders (auto-hide mutates a class on a cached DOM
    # ref, never calls render() — D-18/D-22).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            def is_hidden(page):
                return page.evaluate(
                    "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
                )

            # --- Both sides of the boundary (visible at 3900ms, hidden at
            #     4600ms), D-29's hide scope, pause-while-hidden reveal, and
            #     the zero-structural-render guarantee — one continuous
            #     session so later assertions build on the timer state
            #     earlier ones already proved. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE},
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )
            # Reset AFTER the initial load's own render()s (the "loading"
            # frame plus the post-loadRuntime rebuild both count) so only
            # renders from here on are measured — matching the idiom
            # test_landscape_tracer_renders_and_follows_playhead already
            # uses.
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]').click()
            page.wait_for_timeout(3900)
            assert is_hidden(page) is False
            page.wait_for_timeout(700)  # ~4600ms total elapsed
            assert is_hidden(page) is True
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0

            # D-29: only the scrub hides — top chips and the sidebar stay
            # visible with non-zero bounding boxes the whole time.
            top_box = page.locator(".mobile-top-cluster").bounding_box()
            sidebar_box = page.locator(".mobile-sidebar").bounding_box()
            assert top_box is not None and top_box["width"] > 0 and top_box["height"] > 0
            assert sidebar_box is not None and sidebar_box["width"] > 0 and sidebar_box["height"] > 0

            # Pausing while hidden reveals immediately and holds it — past
            # 4000ms more of paused idle, the scrub stays visible; the timer
            # never re-arms while paused.
            #
            # The FAB sits inside `.mobile-cinema-scrub.is-hidden`, which is
            # `pointer-events: none` — a Playwright force-click still resolves
            # to real screen coordinates, and the browser's own hit-test
            # would route that click straight through to the sky underneath
            # (itself a valid gesture surface, and its own onTap has a
            # reveal branch — the resulting pass/fail would be a false
            # positive for the WRONG code path). Invoke the DOM .click()
            # method directly on the button instead: it dispatches a real
            # "click" event from that exact element, bypassing hit-testing
            # entirely, so this exercises the FAB's own toggle-playback
            # delegation regardless of the pointer-events CSS.
            page.evaluate("document.querySelector('.mobile-cinema-scrub-fab').click()")
            page.wait_for_timeout(50)
            assert is_hidden(page) is False
            page.wait_for_timeout(4200)
            assert is_hidden(page) is False
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []
            page.close()

            # --- Reset: an interaction ~3000ms in (a swipe — resets
            #     unconditionally from onSwipeStep/onSwipeEnd regardless of
            #     the tap-to-pause preference, unlike a plain tap) pushes the
            #     hide out — still visible at ~6900ms (3900ms after the
            #     interaction, not 3900ms after the original start). ---
            page2, console_messages2 = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE},
            )
            page2.locator('.mobile-cinema-scrub-fab[aria-label="Play"]').click()
            page2.wait_for_timeout(3000)
            sky = page2.locator(".mobile-sky")
            sky_box = sky.bounding_box()
            assert sky_box is not None
            x = sky_box["x"] + sky_box["width"] / 2
            y = sky_box["y"] + sky_box["height"] / 2
            page2.mouse.move(x, y)
            page2.mouse.down()
            page2.mouse.move(x + 30, y)
            page2.mouse.up()
            page2.wait_for_timeout(3800)  # ~6800-6900ms total elapsed
            assert is_hidden(page2) is False
            assert console_messages2 == []
            page2.close()

            # --- Paused from the start: the scrub never hides, even well
            #     past 6000ms of idle. ---
            page3, console_messages3 = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            page3.wait_for_timeout(6000)
            assert is_hidden(page3) is False
            assert page3.locator(".mobile-cinema-scrub").is_visible()
            assert console_messages3 == []
            page3.close()

            browser.close()


def test_cinema_scrub_fab_offset_click_hit_area(tmp_path):
    # 04-04-PLAN.md Task 1 (D-39/MOBX-03): the FAB's hit area is a
    # transparent ::before overlay (inset: -4px -> a 48x48 hit-testable box
    # around the unchanged 40x40 painted circle), not padding — padding
    # would visibly grow the glowing circle since background/box-shadow
    # paint through the padding box (04-UI-SPEC.md, 04-PATTERNS.md's
    # CONTRASTING pair with .mobile-icon-btn.compact). Because the overlay
    # is a pseudo-element, getBoundingClientRect() on the host can never
    # prove the 44x44 floor here (04-VALIDATION.md finding 3) — verify by
    # offset click instead. Sky-tap is seeded OFF so a click that misses the
    # overlay and lands on the sky underneath is a genuine no-op, not a
    # second route to toggling playback that would mask a real failure.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            def fresh_page():
                return _page_with_console_capture(
                    browser, site, viewport=PHONE_LANDSCAPE,
                    storage={**DEFAULT_STORAGE, "bcf:tap-to-pause": "false"},
                )

            # Test 1: a click 2px outside the painted left edge, at the
            # button's vertical midpoint, toggles playback — the overlay
            # dispatches the click to its host.
            page, console_messages = fresh_page()
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]')).to_be_visible()
            fab_box = page.locator(".mobile-cinema-scrub-fab").bounding_box()
            assert fab_box is not None
            y_mid = fab_box["y"] + fab_box["height"] / 2
            page.mouse.click(fab_box["x"] - 2, y_mid)
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]')).to_be_visible()
            assert console_messages == []
            page.close()

            # Test 2 (control): a click 10px outside that same edge does NOT
            # toggle playback — proving test 1's result came from the
            # overlay and not from something else catching the click (e.g.
            # the sky underneath, with sky-tap disabled, correctly no-op'ing).
            page2, console_messages2 = fresh_page()
            fab2_box = page2.locator(".mobile-cinema-scrub-fab").bounding_box()
            assert fab2_box is not None
            y_mid2 = fab2_box["y"] + fab2_box["height"] / 2
            page2.mouse.click(fab2_box["x"] - 10, y_mid2)
            page2.wait_for_timeout(100)
            expect(page2.locator('.mobile-cinema-scrub-fab[aria-label="Play"]')).to_be_visible()
            assert console_messages2 == []
            page2.close()

            # Test 3: the play button's own bounding rect still measures
            # exactly 40x40 — asserted deliberately as documentation of why
            # a rect check cannot verify this control (a ::before's
            # absolute-position overflow never changes its host's own
            # layout box).
            page3, console_messages3 = fresh_page()
            fab3_box = page3.locator(".mobile-cinema-scrub-fab").bounding_box()
            assert fab3_box is not None
            assert fab3_box["width"] == 40
            assert fab3_box["height"] == 40

            # Test 4: the overlay's own computed box measures at least
            # 44x44 and carries no paint declaration — computed from the
            # pseudo-element's resolved inset offsets against the host's
            # own rect, since getBoundingClientRect() cannot target a
            # pseudo-element directly.
            overlay = page3.evaluate(
                "() => {"
                "  const el = document.querySelector('.mobile-cinema-scrub-fab');"
                "  const rect = el.getBoundingClientRect();"
                "  const cs = getComputedStyle(el, '::before');"
                "  const left = parseFloat(cs.left);"
                "  const right = parseFloat(cs.right);"
                "  const top = parseFloat(cs.top);"
                "  const bottom = parseFloat(cs.bottom);"
                "  return {"
                "    width: rect.width - left - right,"
                "    height: rect.height - top - bottom,"
                "    backgroundImage: cs.backgroundImage,"
                "    backgroundColor: cs.backgroundColor,"
                "    boxShadow: cs.boxShadow,"
                "  };"
                "}"
            )
            assert overlay["width"] >= 44
            assert overlay["height"] >= 44
            assert overlay["backgroundImage"] == "none"
            assert overlay["backgroundColor"] in ("rgba(0, 0, 0, 0)", "transparent")
            assert overlay["boxShadow"] == "none"
            assert console_messages3 == []
            page3.close()

            browser.close()


def test_landscape_other_tap_targets_clear_44px(tmp_path):
    # 04-04-PLAN.md Task 1 test 5: every OTHER tappable control in the
    # landscape layout (top-cluster help button, sidebar quick-action
    # buttons) still clears the 44x44 floor by rect — the existing portrait
    # pattern (tests/test_mobile_portrait.py) extended to landscape's own
    # controls. The cinema-scrub FAB is deliberately excluded by selector:
    # its host box is permanently 40x40 by design (D-39) and is verified by
    # offset click in test_cinema_scrub_fab_offset_click_hit_area above, not
    # by a rect measurement — do NOT "fix" this exclusion by relaxing the
    # threshold below 44 for the FAB.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE_SMALL, storage=DEFAULT_STORAGE,
            )
            boxes = page.eval_on_selector_all(
                ".mobile-top-cluster button, .mobile-sidebar .mobile-dock-btn",
                "els => els.map(el => { const r = el.getBoundingClientRect(); "
                "return { width: r.width, height: r.height }; })",
            )
            assert len(boxes) >= 3
            for box in boxes:
                assert box["width"] >= 44
                assert box["height"] >= 44
            assert console_messages == []
            browser.close()


def test_landscape_reveal_tap_semantics(tmp_path):
    # D-30: the first sky tap on hidden landscape chrome ALWAYS reveals it
    # and leaves playback running, regardless of the tap-to-pause
    # preference — hidden chrome is never a trap (the "no-trap" guarantee
    # must be asserted, not merely reasoned about). The NEXT tap pauses only
    # when tap-to-pause is on; with it off, the second tap changes nothing
    # (play state unchanged, scrub stays visible).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            for tap_to_pause in ("true", "false"):
                storage = {**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE, "bcf:tap-to-pause": tap_to_pause}
                page, console_messages = _page_with_console_capture(
                    browser, site, viewport=PHONE_LANDSCAPE, storage=storage,
                )
                page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]').click()
                page.wait_for_timeout(4100)
                assert page.evaluate(
                    "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
                ) is True

                sky = page.locator(".mobile-sky")

                # First tap: reveals AND leaves play state unchanged — an
                # explicit boolean pair, not inferred — in BOTH tap-to-pause
                # configurations.
                sky.click(force=True)
                page.wait_for_timeout(50)
                assert page.evaluate(
                    "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
                ) is False
                assert page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]').count() == 1

                # Second tap (past the double-tap window): pauses only when
                # tap-to-pause is ON; with it off, this tap is a no-op.
                page.wait_for_timeout(400)
                sky.click()
                page.wait_for_timeout(50)
                if tap_to_pause == "true":
                    assert page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]').count() == 1
                else:
                    assert page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]').count() == 1
                # The scrub stays visible either way — the second tap never
                # re-hides it.
                assert page.evaluate(
                    "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
                ) is False

                assert console_messages == []
                page.close()


def test_landscape_surface_stack(tmp_path):
    # MOBL-04 (03-03-PLAN.md Task 1, D-33): the layout-agnostic surface
    # stack (openMobileSurface/closeMobileSurface/trapMobileSurfaceFocus) is
    # reused wholesale in landscape — a backdrop tap anywhere across the
    # root (including over the sidebar, the landscape analogue of Phase 2
    # device defect #3), the opening control a second time, and the mobile
    # back gesture all dismiss with a balanced history sentinel (D-16);
    # keyboard focus is trapped inside the panel both directions; the panel
    # never overlaps the control-dock buttons (the landscape analogue of
    # Phase 2 device defect #2), and the dock's Settings/About buttons stay
    # reachable ABOVE the backdrop the same way portrait's transport row
    # does; every external About link carries rel=noopener (T-03-03); and
    # the Help overlay's CTA stays reachable within the sky's own height.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Backdrop spans the whole root (including the sidebar); the
            #     open panel never overlaps a dock button and never exceeds
            #     the sky's height; a tap over the sidebar's field-log region
            #     (not a dock button) closes it. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            assert page.locator(".mobile-sky .mobile-flyout").count() == 1
            assert page.locator(".mobile-flyout-backdrop").count() == 1

            backdrop_box = page.locator(".mobile-flyout-backdrop").bounding_box()
            sidebar_box = page.locator(".mobile-sidebar").bounding_box()
            assert backdrop_box is not None and sidebar_box is not None
            assert backdrop_box["x"] + backdrop_box["width"] >= sidebar_box["x"] + sidebar_box["width"] - 1

            flyout_box = page.locator(".mobile-flyout").bounding_box()
            sky_box = page.locator(".mobile-sky").bounding_box()
            assert flyout_box is not None and sky_box is not None
            assert flyout_box["height"] <= sky_box["height"] + 1
            dock_btn_locators = page.locator(".mobile-dock-btn").all()
            assert len(dock_btn_locators) > 0
            for dock_btn in dock_btn_locators:
                dock_box = dock_btn.bounding_box()
                assert dock_box is not None
                assert not _intersects(flyout_box, dock_box)

            field_log_box = page.locator(".mobile-field-log").bounding_box()
            assert field_log_box is not None
            x = sidebar_box["x"] + sidebar_box["width"] / 2
            y = field_log_box["y"] + field_log_box["height"] / 2
            page.mouse.click(x, y)
            assert page.locator(".mobile-flyout").count() == 0
            assert console_messages == []
            page.close()

            # --- The opening control closes it a second press; About while
            #     Settings is open swaps in (reusing the outstanding
            #     sentinel, not stacking a second one) — this requires the
            #     REAL dock button to receive the tap, not the backdrop
            #     underneath it (Task 1's z-index fix; a non-forced
            #     Playwright click fails outright if the backdrop still
            #     intercepts it). ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            history_state_before_open = page.evaluate("window.history.state")
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator('.mobile-flyout[aria-label="Settings"]').count() == 1
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 0
            page.wait_for_timeout(50)
            assert page.evaluate("window.history.state") == history_state_before_open

            page.click('[data-action="mobile-open-settings"]')
            assert page.locator('.mobile-flyout[aria-label="Settings"]').count() == 1
            state_with_settings_open = page.evaluate("window.history.state")
            page.click('[data-action="mobile-open-info"]')
            assert page.locator(".mobile-flyout").count() == 1
            assert page.locator('.mobile-flyout[aria-label="About"]').count() == 1
            # The swap reuses the single outstanding sentinel — the state
            # object is unchanged from what it was right after Settings
            # opened, not a second pushState for About.
            assert page.evaluate("window.history.state") == state_with_settings_open
            assert console_messages == []
            page.close()

            # --- Focus trap: Tab from the last focusable and Shift+Tab from
            #     the first both wrap inside the panel, never escaping to the
            #     sky/rail/dock behind it. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            assert page.evaluate(
                "document.querySelector('.mobile-flyout').contains(document.activeElement)"
            ) is True
            focusable_selector = (
                ".mobile-flyout button, .mobile-flyout [href], .mobile-flyout input, "
                ".mobile-flyout select, .mobile-flyout textarea"
            )
            focusable_count = page.evaluate(
                "(sel) => document.querySelectorAll(sel).length", focusable_selector,
            )
            assert focusable_count > 0
            for _ in range(focusable_count + 2):
                page.keyboard.press("Tab")
            assert page.evaluate(
                "document.querySelector('.mobile-flyout').contains(document.activeElement)"
            ) is True
            for _ in range(focusable_count + 2):
                page.keyboard.press("Shift+Tab")
            assert page.evaluate(
                "document.querySelector('.mobile-flyout').contains(document.activeElement)"
            ) is True
            assert console_messages == []
            page.close()

            # --- The mobile back gesture closes the flyout and leaves the
            #     app on the same URL; the sentinel is fully consumed
            #     (history.state returns to whatever it was pre-open — raw
            #     window.history.length never shrinks via back(), matching
            #     the established portrait proof's own reasoning). ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            history_state_before_open2 = page.evaluate("window.history.state")
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            page.go_back()
            page.wait_for_timeout(50)
            assert page.locator(".mobile-flyout").count() == 0
            assert page.evaluate("document.querySelector('.mobile-app-landscape') != null") is True
            assert page.evaluate("window.history.state") == history_state_before_open2
            assert console_messages == []
            page.close()

            # --- T-03-03: every external anchor in the About flyout carries
            #     rel=noopener — enumerate ALL of them, not just the first. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-info"]')
            links = page.locator('.mobile-flyout[aria-label="About"] a[href^="http"]')
            link_count = links.count()
            assert link_count > 0
            rels = links.evaluate_all("els => els.map(el => el.rel)")
            assert len(rels) == link_count
            assert all("noopener" in rel for rel in rels)
            assert console_messages == []
            page.close()

            # --- Help overlay: opens from the top-cluster help button in
            #     landscape, never exceeds the sky region's height (D-19),
            #     and its CTA stays reachable inside that bound. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-help"]')
            help_box = page.locator(".mobile-help-overlay").bounding_box()
            sky_box2 = page.locator(".mobile-sky").bounding_box()
            assert help_box is not None and sky_box2 is not None
            assert help_box["height"] <= sky_box2["height"] + 1
            cta = page.locator(".mobile-got-it")
            expect(cta).to_be_visible()
            cta_box = cta.bounding_box()
            assert cta_box is not None
            assert cta_box["y"] + cta_box["height"] <= sky_box2["y"] + sky_box2["height"] + 1
            assert console_messages == []
            browser.close()


def test_rotation_preserves_state(tmp_path):
    # MOBL-03 (03-03-PLAN.md Task 2, D-20/D-23): the CI half of the phase's
    # two-pronged rotation proof. Every field MOBL-03 names lives on app.*
    # and survives onLayoutMaybeChanged()'s full render() rebuild, asserted
    # individually (not as one aggregate) in both directions; landscape
    # arrival shows chrome and starts the D-31 idle window; the real-device
    # resize/orientationchange timing race is plan 04's gate, not this test.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Every preference field set through the real Settings UI
            #     (never a direct localStorage write), playback started,
            #     rotated to landscape, then rotated back — each field
            #     compared individually at every stage. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            groups = page.locator(".mobile-flyout .mobile-group")
            groups.nth(0).get_by_text("Details", exact=True).click()
            groups.nth(1).locator('[data-on-roll-behavior="quick"]').click()
            # 0.5x (2500 words/sec), not the default 1x — also slow enough
            # that tiny-default's 10000-word story survives every wait this
            # test holds playback open across (a faster rung would finish
            # and auto-pause the story before the rotation-preserves-
            # playing-state assertions below run).
            groups.nth(2).get_by_text("½×", exact=True).click()
            groups.nth(3).get_by_text("4×", exact=True).click()
            groups.nth(4).locator(".mobile-row-val").nth(0).click()  # tap-to-pause -> Off
            groups.nth(4).locator(".mobile-row-val").nth(1).click()  # haptics -> Off
            # Toggle the flyout shut through the same opening control (D-33
            # reuses portrait's toggle-shut convention).
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 0

            page.click(".mobile-fab-play")
            assert page.locator(".mobile-fab-play").get_attribute("aria-label") == "Pause"
            # Let tickPlayback's persistBookmarkSoon debounce (<=500ms) flush
            # at least once so the bookmark key reflects live playback, not
            # just the seeded word 0.
            page.wait_for_timeout(600)

            def read_fields(fab_selector):
                return {
                    "speed": page.evaluate("localStorage.getItem('bcf:playback:speed:v2')"),
                    "mode": page.evaluate("localStorage.getItem('bcf:mode')"),
                    "onRoll": page.evaluate("localStorage.getItem('bcf:on-roll-behavior')"),
                    "zoom": page.evaluate("window.__bcfPrefs.mobileTimelineZoom"),
                    "tapToPause": page.evaluate("window.__bcfPrefs.tapToPause"),
                    "haptics": page.evaluate("window.__bcfPrefs.haptics"),
                    "playing": page.locator(fab_selector).get_attribute("aria-label"),
                    "wordPos": int(page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")),
                }

            before = read_fields(".mobile-fab-play")
            assert before["speed"] == "2500"
            assert before["mode"] == "detail"
            assert before["onRoll"] == "quick"
            assert before["zoom"] == 4
            assert before["tapToPause"] is False
            assert before["haptics"] is False
            assert before["playing"] == "Pause"

            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            expect(page.locator(".mobile-sidebar")).to_be_visible()
            assert page.evaluate("document.querySelector('.mobile-dock')") is None

            # Phase-level verification #3 (D-20/RESEARCH A3): no cross-fade
            # was built — the landscape root's className read immediately
            # after the swap is byte-identical 500ms later, i.e. no
            # transient transition/animation class is ever applied on
            # rotation. Asserted behaviorally rather than by grepping for
            # ROTATION_ANIM's name, so an explanatory comment alone could
            # never satisfy this gate.
            class_name_immediately_after = page.evaluate(
                "document.querySelector('.mobile-app-landscape').className"
            )
            page.wait_for_timeout(500)
            class_name_500ms_later = page.evaluate(
                "document.querySelector('.mobile-app-landscape').className"
            )
            assert class_name_500ms_later == class_name_immediately_after

            page.wait_for_timeout(100)

            after = read_fields(".mobile-cinema-scrub-fab")
            for key in ("speed", "mode", "onRoll", "zoom", "tapToPause", "haptics", "playing"):
                assert after[key] == before[key], f"{key} changed across rotation: {before[key]!r} -> {after[key]!r}"
            assert after["wordPos"] >= before["wordPos"]

            # Round trip: rotate back, every field returns, .mobile-dock is
            # present again and .mobile-app-landscape is gone.
            page.set_viewport_size(PHONE_PORTRAIT)
            page.wait_for_function("window.__bcfLayoutMode === 'portrait'")
            expect(page.locator(".mobile-dock")).to_be_visible()
            assert page.evaluate("document.querySelector('.mobile-app-landscape')") is None
            page.wait_for_timeout(600)

            round_trip = read_fields(".mobile-fab-play")
            for key in ("speed", "mode", "onRoll", "zoom", "tapToPause", "haptics", "playing"):
                assert round_trip[key] == before[key], (
                    f"{key} did not round-trip: {before[key]!r} -> {round_trip[key]!r}"
                )
            assert round_trip["wordPos"] >= after["wordPos"]

            assert console_messages == []
            page.close()

            # --- D-31: rotating into landscape arrives with chrome visible
            #     and the idle window started — NOT hidden immediately after
            #     the swap, and hidden 4600ms later if playback continues
            #     untouched. tiny-default's default speed finishes the whole
            #     10000-word story in ~2s, so this session seeds a much
            #     slower speed to survive the wait, matching
            #     test_landscape_chrome_autohide_boundary's own idiom. ---
            page2, console_messages2 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE},
            )
            page2.click(".mobile-fab-play")
            page2.set_viewport_size(PHONE_LANDSCAPE)
            page2.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            assert page2.evaluate(
                "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
            ) is False
            page2.wait_for_timeout(4600)
            assert page2.evaluate(
                "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
            ) is True
            assert console_messages2 == []
            browser.close()


def test_rotation_at_routing_boundaries(tmp_path):
    # MOBL-03 boundary matrix (FA-MOBL-03). Updated at the Phase 3 gate when the
    # landscape clause moved from `(max-width: 900px)` to
    # `(orientation: landscape) and (max-height: 500px)` — see
    # test_large_phones_in_landscape_get_the_mobile_layout for why.
    #
    # One expectation genuinely INVERTED, and that is the accepted trade-off of
    # the height-based rule, not an accident: 900x600 used to be mobile
    # landscape (900 <= the old 900px ceiling) and is now desktop, because a
    # 600px-tall landscape viewport is not a phone — real phones in landscape
    # are ~390-440 tall. Approved by Dre when choosing the height-based clause.
    #
    # Still mirrors test_layout_mode_matrix_matches_css_breakpoint in
    # tests/test_mobile_plumbing.py (verified still green and left byte-
    # identical — all five of its rows hold under the new query too).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            cases = [
                ({"width": 1100, "height": 900}, "desktop"),
                ({"width": 900, "height": 1100}, "portrait"),
                # Was "landscape" under the width-based clause; now desktop.
                ({"width": 900, "height": 600}, "desktop"),
                # Pin the new ceiling from both sides so a silent drift in the
                # 500px threshold fails loudly.
                ({"width": 900, "height": 500}, "landscape"),
                ({"width": 900, "height": 501}, "desktop"),
            ]
            for viewport, expected in cases:
                page, console_messages = _page_with_console_capture(
                    browser, site, viewport=viewport, storage=DEFAULT_STORAGE,
                )
                assert page.evaluate("window.__bcfLayoutMode") == expected
                if expected == "desktop":
                    # The landscape arm never mounts at a viewport the
                    # matrix routes to desktop.
                    assert page.evaluate("document.querySelector('.mobile-app-landscape')") is None
                    assert page.locator(".app").count() == 1
                assert console_messages == []
                page.close()

            browser.close()


def test_rotation_with_surface_open_and_mid_drag(tmp_path):
    # MOBL-03 (03-03-PLAN.md Task 2, D-21/D-22): (a) an open surface
    # survives rotation and re-renders in the new layout with a balanced
    # history sentinel; (b) rotating mid-drag aborts the in-flight scrub
    # cleanly (the existing frozen-pan teardown, verified rather than
    # rebuilt per the plan) without deferring the layout swap, and a fresh
    # drag in the new layout is monotonic from its first sample; (c)
    # rotating away from landscape while the idle timer is armed leaves no
    # stale timer behind — it never fires into the new layout.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # (a) Surface survives rotation; history stays balanced.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            history_state_before_open = page.evaluate("window.history.state")
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            history_length_with_surface_open = page.evaluate("window.history.length")

            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            assert page.locator(".mobile-sky .mobile-flyout").count() == 1
            # Rotation itself touches no history state — the joint session
            # history is exactly as long as it was the instant before the
            # swap, and the sentinel's state object is untouched (D-21).
            assert page.evaluate("window.history.length") == history_length_with_surface_open
            assert page.evaluate("window.history.state") == {"bcfMobileSurface": "settings"}

            page.click('[data-action="mobile-open-settings"]')  # toggles shut, consumes the sentinel
            assert page.locator(".mobile-flyout").count() == 0
            page.wait_for_timeout(50)
            assert page.evaluate("window.history.state") == history_state_before_open
            assert console_messages == []
            page.close()

            # (b) Mid-drag rotation: press on the portrait mini-rail, rotate
            #     while still down, release, then a fresh drag on the
            #     landscape cinema-scrub track is monotonic from its first
            #     sample with no console error.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            rail_box = page.locator(".mobile-rail").bounding_box()
            assert rail_box is not None
            ry = rail_box["y"] + rail_box["height"] / 2
            page.mouse.move(rail_box["x"] + rail_box["width"] * 0.30, ry)
            page.mouse.down()
            page.mouse.move(rail_box["x"] + rail_box["width"] * 0.30 + 20, ry)

            page.set_viewport_size(PHONE_LANDSCAPE)
            page.wait_for_function("window.__bcfLayoutMode === 'landscape'")
            # The structural render that swaps layouts tears the portrait
            # rail's listeners down mid-drag (the same teardown that clears
            # app.mobileScrubPanPct on every structural render, D-22) — the
            # still-held mouse button has nothing left listening to it.
            page.mouse.up()

            track_box = page.locator(".mobile-cinema-scrub-track").bounding_box()
            assert track_box is not None
            ty = track_box["y"] + track_box["height"] / 2

            def playhead_pct():
                raw = page.evaluate(
                    "() => document.querySelector('.mobile-cinema-scrub-thumb')?.style.left ?? null"
                )
                assert raw is not None, "landscape cinema-scrub thumb not found"
                return float(raw.rstrip("%"))

            def x_at(fraction):
                return track_box["x"] + track_box["width"] * fraction

            page.mouse.move(x_at(0.30), ty)
            page.mouse.down()
            page.wait_for_timeout(60)
            observed = [playhead_pct()]
            for fraction in (0.40, 0.50, 0.60, 0.70):
                page.mouse.move(x_at(fraction), ty)
                page.wait_for_timeout(60)
                observed.append(playhead_pct())
            page.mouse.up()

            for earlier, later in zip(observed, observed[1:]):
                assert later >= earlier - 0.01, (
                    f"post-rotation drag moved the playhead backward "
                    f"({earlier:.3f}% -> {later:.3f}%) across {observed}"
                )
            assert observed[-1] > observed[0] + 1.0, f"post-rotation drag barely moved: {observed}"
            assert console_messages == []
            page.close()

            # (c) Rotating away from landscape while the idle timer is
            #     armed leaves no stale timer behind: once hidden, rotating
            #     to portrait and waiting well past the window produces no
            #     console error and no element anywhere carries the
            #     hidden-state class.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, **SLOW_PLAYBACK_STORAGE},
            )
            page.locator('.mobile-cinema-scrub-fab[aria-label="Play"]').click()
            page.wait_for_timeout(4600)
            assert page.evaluate(
                "document.querySelector('.mobile-cinema-scrub').classList.contains('is-hidden')"
            ) is True
            page.set_viewport_size(PHONE_PORTRAIT)
            page.wait_for_function("window.__bcfLayoutMode === 'portrait'")
            page.wait_for_timeout(5000)
            assert page.evaluate("document.querySelectorAll('.is-hidden').length") == 0
            assert console_messages == []

            browser.close()

            browser.close()


@pytest.mark.parametrize(
    "viewport,label",
    [
        (PHONE_LANDSCAPE, "844x390 iPhone 12/13/14-class"),
        (PHONE_LANDSCAPE_LARGE, "956x390 iPhone 16 Pro Max"),
        (PHONE_LANDSCAPE_LARGE_ALT, "932x430 iPhone 14/15 Pro Max"),
        (PHONE_LANDSCAPE_SMALL, "568x320 smallest in-scope"),
    ],
)
def test_large_phones_in_landscape_get_the_mobile_layout(tmp_path, viewport, label):
    # MOBL-01 regression, found on real hardware at the Phase 3 gate.
    #
    # The landscape clause used to be `(max-width: 900px)`, inherited from the
    # frozen portrait-banner rule (style.css:360) and written before phones got
    # this wide. A real iPhone 16 Pro Max is 956x390 in landscape, so the clause
    # failed, neither clause matched, and layoutMode resolved to "desktop" — the
    # entire landscape layout silently never mounted. Not a crash: the desktop
    # shell rendered instead, which is why it survived every automated check.
    #
    # CI could not have caught it. All three test files used 844x390, which fits
    # under the old 900px ceiling. The clause is now height-based
    # ((orientation: landscape) and (max-height: 500px)), and this test pins the
    # real widths so a width-based regression cannot return unnoticed.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=viewport, storage=DEFAULT_STORAGE,
            )

            assert page.evaluate("window.__bcfLayoutMode") == "landscape", (
                f"{label} must resolve to the landscape mobile layout, not desktop"
            )
            # The mobile surface mounts and the desktop shell does not — the
            # bare layoutMode string alone would not have caught the original
            # defect's user-visible symptom.
            assert page.evaluate("document.querySelector('.mobile-app') != null") is True
            assert page.evaluate("document.querySelector('.app')") is None
            assert page.evaluate("document.querySelector('.portrait-banner')") is None
            assert console_messages == []
            page.close()

            browser.close()


def test_tablets_in_landscape_stay_desktop(tmp_path):
    # The other half of the height-based clause: raising the phone ceiling must
    # NOT sweep tablets into the mobile layout. §7 is explicit that
    # iPads-in-landscape are desktop. Heights here (768-1024) are far above the
    # 500px landscape ceiling, so they resolve to desktop by the dimension that
    # actually distinguishes them, regardless of how wide phones later become.
    playwright_api = pytest.importorskip("playwright.sync_api")

    tablets = [
        ({"width": 1024, "height": 768}, "iPad mini / classic 4:3 landscape"),
        ({"width": 1180, "height": 820}, "iPad Air landscape"),
        ({"width": 1366, "height": 1024}, "iPad Pro 12.9 landscape"),
    ]

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            for viewport, label in tablets:
                page, console_messages = _page_with_console_capture(
                    browser, site, viewport=viewport, storage=DEFAULT_STORAGE,
                )
                assert page.evaluate("window.__bcfLayoutMode") == "desktop", (
                    f"{label} must stay on the desktop shell (§7)"
                )
                assert page.evaluate("document.querySelector('.mobile-app')") is None
                assert console_messages == []
                page.close()

            browser.close()


# ---------------------------------------------------------------------------
# 04-02-PLAN.md (Task 1 test 9 / Task 2 test 10): the live region and mobile
# keyboard equivalents mount/behave identically in landscape — attachMobile-
# Gestures()/the keydown handler both gate on `layoutMode !== "desktop"`,
# never a layout-specific check, so the cheapest proof is one gesture and
# one key each, mirroring the portrait file's own coverage.
# ---------------------------------------------------------------------------


def test_mobile_live_region_mounts_and_announces_in_landscape(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "2000"},
            )
            assert page.locator('.mobile-live-region[role="status"]').count() == 1

            sky = page.locator(".mobile-sky")
            sky.dblclick()
            expect(page.locator('.mobile-cinema-scrub-fab[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(100)
            text = page.locator(".mobile-live-region").text_content()
            assert text == "Roll 1 of 2. Synthetic Toolkit, 100 CP."
            assert console_messages == []
            browser.close()


def test_mobile_keyboard_arrow_and_help_in_landscape(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        roll_positions = _dense_rolls_positions_sorted(facts)
        mid_word = 5000
        last_at_or_before = max(w for w in roll_positions if w <= mid_word)
        idx = roll_positions.index(last_at_or_before)
        forward_one = roll_positions[idx + 1]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_LANDSCAPE,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": str(mid_word)},
            )
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == str(forward_one)
            assert page.locator(".mobile-live-region").text_content() != ""

            page.keyboard.press("?")
            page.wait_for_timeout(50)
            assert page.locator(".mobile-help-overlay").count() == 1
            page.keyboard.press("?")
            page.wait_for_timeout(50)
            assert page.locator(".mobile-help-overlay").count() == 0

            assert console_messages == []
            browser.close()
