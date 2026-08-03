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

import json

import pytest

from tests.helpers.web_runtime_site import LONG_MULTIBYTE_PERK_NAME, staged_web_runtime_site


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


PHONE_PORTRAIT = {"width": 390, "height": 844}
PHONE_PORTRAIT_SMALL = {"width": 320, "height": 568}
PHONE_LANDSCAPE = {"width": 844, "height": 390}

DEFAULT_STORAGE = {
    "bcf:preview-port-storage-version": "3",
    "bcf:bookmark:word_position": "0",
    # Plan 02-04's first-run Help auto-open fires whenever bcf:help-seen is
    # unset — pre-seed it so every pre-existing test in this file (written
    # before the surface stack existed) keeps exercising sky/rail gestures
    # normally instead of tripping the mobileSurface guard that disables
    # them while a surface is open. Tests that specifically exercise the
    # auto-open itself (test_first_run_help_auto_opens_once) seed storage
    # WITHOUT this key on purpose.
    "bcf:help-seen": "true",
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
        facts = json.loads(facts_path.read_text())
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
                    "bcf:help-seen": "true",
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


def _dense_rolls_facts(site):
    facts_path = site.root / "data/packages/dense-rolls/visualization_facts.json"
    return json.loads(facts_path.read_text())


def _tiny_default_facts(site):
    facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
    return json.loads(facts_path.read_text())


def _facts_total_words(facts: dict) -> int:
    # Mirrors web/app.js buildStory()'s total_words: the last chapter's
    # cumulative_words_through_chapter. app.js itself is an ES module (loaded
    # `<script type="module">`), so its top-level `app` binding is NOT
    # reachable from page.evaluate() (module scope, not the global realm) —
    # this reads the same value from the source-of-truth fixture instead of
    # querying the page for it.
    chapters = facts.get("chapters", [])
    return chapters[-1]["cumulative_words_through_chapter"] if chapters else 0


def _long_perk_roll_word(facts: dict) -> int:
    for chapter in facts.get("chapters", []):
        for roll in chapter.get("rolls", []):
            for perk in roll.get("purchased_perks", []):
                if len(perk.get("name", "")) >= 60:
                    return roll["epub_word_offset_predicted"]
    raise AssertionError("dense-rolls fixture has no long-multibyte-perk roll")


@pytest.mark.parametrize("viewport", [PHONE_PORTRAIT, PHONE_PORTRAIT_SMALL], ids=["390x844", "320x568"])
def test_portrait_layout_proportions_and_chip_overlap(tmp_path, viewport):
    # MOBP-01 acceptance bar: the sky/dock split lands in the 50-70% band at
    # both viewport sizes, and the top chip cluster never intersects the
    # sky's focal label — even with a long multibyte perk name as the active
    # roll (encoding edge, dense-rolls fixture).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        target_word = _long_perk_roll_word(facts)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=dense-rolls",
                viewport=viewport,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(target_word),
                    "bcf:help-seen": "true",
                },
            )

            sky_box = page.locator(".mobile-sky").bounding_box()
            dock_box = page.locator(".mobile-dock").bounding_box()
            assert sky_box is not None
            assert dock_box is not None
            ratio = sky_box["height"] / viewport["height"]
            assert 0.5 <= ratio <= 0.7, f"sky/viewport ratio {ratio} outside 50-70% band"
            assert dock_box["y"] + dock_box["height"] <= viewport["height"] + 1

            cluster_box = page.locator(".mobile-top-cluster").bounding_box()
            label_box = page.locator(".mobile-focal-label").bounding_box()
            assert cluster_box is not None
            assert label_box is not None
            assert cluster_box["y"] + cluster_box["height"] <= label_box["y"]

            assert console_messages == []
            browser.close()


def _dense_rolls_positions_sorted(facts: dict) -> list[int]:
    return sorted(
        roll["epub_word_offset_predicted"]
        for chapter in facts.get("chapters", [])
        for roll in chapter.get("rolls", [])
    )


def test_sky_gesture_contract(tmp_path):
    # MOBP-02: tap toggles playback, double-tap snaps to the last roll at or
    # before the current playhead (never the story's final roll), and a
    # horizontal swipe steps one roll per 56px of travel — all through the
    # shared setters, with zero structural re-renders across the swipe.
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

            # Each phase below opens its own fresh page seeded to the same
            # starting bookmark, so a running playback tick from one phase's
            # assertions can never drift the word position that the next
            # phase's assertions depend on.
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
                    viewport=PHONE_PORTRAIT, storage=storage,
                )

            # A single tap toggles playback (FAB flips Play -> Pause), and a
            # second single tap (spaced past the double-tap window) flips it
            # back.
            page, console_messages = fresh_page()
            sky = page.locator(".mobile-sky")
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            sky.click()
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(400)
            sky.click()
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            assert console_messages == []
            page.close()

            # Double-tap snaps the playhead to the last roll at/before the
            # pre-double-tap position and resumes — never the final roll.
            page, console_messages = fresh_page()
            sky = page.locator(".mobile-sky")
            sky.dblclick()
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(50)
            bookmark = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark == str(last_at_or_before)
            assert int(bookmark) < final_roll_word
            assert console_messages == []
            page.close()

            # Horizontal swipe: engagement costs SWIPE_ENGAGE (24px), then
            # one roll per SCRUB_STEP_PX (56px) — a 140px drag yields exactly
            # 2 roll-steps (24 + 2*56 = 136 <= 140 < 192). Structural render
            # count must not move (D-07/T-02-05) — gestures ride the
            # incremental tier only. The bookmark persists on release
            # (onSwipeEnd) and equals the in-memory word position.
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

            page.wait_for_timeout(400)
            page.mouse.move(x, y)
            page.mouse.down()
            for dx in range(8, 141, 8):
                page.mouse.move(x - dx, y)
            page.mouse.up()
            page.wait_for_timeout(50)
            bookmark_after_left = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark_after_left == str(last_at_or_before)
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_sky_tap_is_noop_when_tap_to_pause_off(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        roll_positions = _dense_rolls_positions_sorted(facts)
        mid_word = 5000
        last_at_or_before = max(w for w in roll_positions if w <= mid_word)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(mid_word),
                    "bcf:tap-to-pause": "false",
                    "bcf:help-seen": "true",
                },
            )

            sky = page.locator(".mobile-sky")
            fab_label_before = page.locator(".mobile-fab-play").get_attribute("aria-label")
            meta_before = page.locator(".mobile-dock-meta").inner_text()

            sky.click()
            page.wait_for_timeout(100)
            assert page.locator(".mobile-fab-play").get_attribute("aria-label") == fab_label_before
            assert page.locator(".mobile-dock-meta").inner_text() == meta_before

            # A double-tap still snaps and resumes even with tap-to-pause off
            # — only the single-tap pause toggle is gated by the preference.
            page.wait_for_timeout(400)
            sky.dblclick()
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(50)
            bookmark = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark == str(last_at_or_before)

            assert console_messages == []
            browser.close()


def test_dock_speed_cycle_persists_and_hint_row_context(tmp_path):
    # MOBP-02 (Task 2): the dock speed control cycles through the four
    # locked multiplier rungs and survives a reload; the first-run sky tap
    # hint mounts once per session and only while tap-to-pause is on; the
    # hint row's right span reports zoom (only above 1x) and POV correctly.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Speed cycle labels, allow-listed persisted values, and the
            #     tap hint's once-per-session mount lifecycle. ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )

            speed_btn = page.locator('[data-action="mobile-cycle-speed"]')
            assert speed_btn.inner_text() == "1×"

            # First-run tap hint mounts once, tap-to-pause is on by default.
            assert page.evaluate("document.querySelector('.mobile-sky-tap-hint') != null") is True

            desktop_option_values = {"1000", "2500", "5000", "10000", "25000", "50000", "100000"}
            expected_labels = ["2×", "4×", "½×"]
            for expected in expected_labels:
                speed_btn.click()
                assert speed_btn.inner_text() == expected
                written = page.evaluate("localStorage.getItem('bcf:playback:speed:v2')")
                assert written in desktop_option_values

            # Each speed-cycle click was a sanctioned structural re-render (a
            # control change, not a gesture) — the hint must not remount
            # after the first one.
            assert page.evaluate("document.querySelector('.mobile-sky-tap-hint')") is None

            page.reload(wait_until="networkidle")
            assert page.evaluate("localStorage.getItem('bcf:playback:speed:v2')") == "2500"
            assert page.locator('[data-action="mobile-cycle-speed"]').inner_text() == "½×"

            # Hint row right span at the default 1x zoom: no zoom segment,
            # POV segment always present and non-empty (this fixture's
            # chapters carry no chapter-level pov_characters field, so this
            # exercises the default-POV fallback).
            # text_content() (not inner_text()) — the hint row's CSS applies
            # text-transform: uppercase, which inner_text() would reflect.
            hint_right = page.locator(".mobile-hint-row span").nth(1).text_content()
            assert "zoom" not in hint_right
            assert hint_right.endswith(" POV")
            assert hint_right != " POV"

            assert console_messages == []
            page.close()

            # --- Hint row at 4x zoom: the zoom segment is present and
            #     ordered before the POV segment. ---
            page, console_messages2 = _page_with_console_capture(
                browser,
                site,
                storage={**DEFAULT_STORAGE, "bcf:timeline-zoom": "4"},
                viewport=PHONE_PORTRAIT,
            )
            hint_right_zoomed = page.locator(".mobile-hint-row span").nth(1).text_content()
            assert hint_right_zoomed.startswith("4× zoom · ")
            assert hint_right_zoomed.endswith(" POV")
            assert console_messages2 == []
            page.close()

            # --- Tap hint absent entirely with tap-to-pause off. ---
            page, console_messages3 = _page_with_console_capture(
                browser,
                site,
                storage={**DEFAULT_STORAGE, "bcf:tap-to-pause": "false"},
                viewport=PHONE_PORTRAIT,
            )
            assert page.evaluate("document.querySelector('.mobile-sky-tap-hint')") is None
            assert console_messages3 == []
            page.close()

            # --- Every dock-transport button clears the 44px tap-target
            #     floor at 320px viewport width. ---
            page, console_messages4 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT_SMALL, storage=DEFAULT_STORAGE,
            )
            boxes = page.eval_on_selector_all(
                ".mobile-dock-transport button",
                "els => els.map(el => { const r = el.getBoundingClientRect(); "
                "return { width: r.width, height: r.height }; })",
            )
            assert len(boxes) >= 2
            for box in boxes:
                assert box["width"] >= 44
                assert box["height"] >= 44
            assert console_messages4 == []

            browser.close()


def test_cluster_binning_at_1x(tmp_path):
    # MOBP-04: at 1x the mini-rail collapses tight clusters of rolls into
    # counted bin markers instead of an unreadable smear of dots, while the
    # active roll always renders as its own cyan diamond on top — and bins
    # never recompute on a playback frame (D-18).
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        total_rolls = sum(len(chapter.get("rolls", [])) for chapter in facts.get("chapters", []))
        assert total_rolls == 12  # 8-roll cluster (ch2) + 4 spread rolls (ch3)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Phase A: bin count, count badge, active diamond on top of a
            #     bin whose span it falls inside. ---
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    # Word 3125 falls after the cluster's 3rd roll (word 3120,
                    # a hit) and before its 4th (word 3130) — the active roll
                    # (3120) sits INSIDE the merged cluster bin's span
                    # (3100-3170), proving the active marker is never folded
                    # into a bin even when it geometrically overlaps one.
                    "bcf:bookmark:word_position": "3125",
                    "bcf:help-seen": "true",
                },
            )

            bin_count = page.locator(".mobile-roll-bin").count()
            assert bin_count < total_rolls

            counts = page.locator(".mobile-roll-bin .count").all_inner_texts()
            assert counts == ["8"]  # only the 8-roll cluster merges and clears the size>=10 badge floor

            expect(page.locator(".mobile-roll-dot.active")).to_have_count(1)
            active_z = page.evaluate(
                "getComputedStyle(document.querySelector('.mobile-roll-dot.active')).zIndex"
            )
            bin_z = page.evaluate(
                "getComputedStyle(document.querySelector('.mobile-roll-bin')).zIndex"
            )
            assert int(active_z) > int(bin_z)
            assert console_messages == []

            # --- Phase B: scrubbing moves the active diamond but never the
            #     (structurally fixed) bin markers. ---
            bins_before = page.eval_on_selector_all(".mobile-roll-bin", "els => els.map(el => el.style.left)")
            active_left_before = page.locator(".mobile-roll-dot.active").evaluate("el => el.style.left")

            rail_box = page.locator(".mobile-rail").bounding_box()
            assert rail_box is not None
            x = rail_box["x"] + rail_box["width"] * 0.85  # lands in the spread-roll region (~word 8500)
            y = rail_box["y"] + rail_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.up()
            page.wait_for_timeout(50)

            bins_after = page.eval_on_selector_all(".mobile-roll-bin", "els => els.map(el => el.style.left)")
            active_left_after = page.locator(".mobile-roll-dot.active").evaluate("el => el.style.left")
            assert bins_after == bins_before
            assert active_left_after != active_left_before
            assert console_messages == []
            page.close()

            # --- Phase C: bins never recompute during playback (D-18). ---
            page, console_messages2 = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": "3125",
                    "bcf:help-seen": "true",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            bin_count_before_playback = page.locator(".mobile-roll-bin").count()
            page.click('button[aria-label="Play"]')
            page.wait_for_timeout(1500)
            assert page.locator(".mobile-roll-bin").count() == bin_count_before_playback
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages2 == []
            page.close()

            # --- Phase D: with zero rolls anywhere in the story, the rail
            #     still renders ticks/POV bands/playhead, with zero bins and
            #     zero active diamond, and never throws (UI-SPEC
            #     empty-zero-rolls row). tiny-default cannot exercise this —
            #     it carries two real rolls elsewhere in the story — so this
            #     uses the dedicated `no-rolls` fixture (see
            #     tests/helpers/web_runtime_site.py).
            page, console_messages3 = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=no-rolls",
                viewport=PHONE_PORTRAIT,
                storage={"bcf:preview-port-storage-version": "3", "bcf:bookmark:word_position": "0", "bcf:help-seen": "true"},
            )
            assert page.locator(".mobile-ch-tick").count() > 0
            expect(page.locator(".mobile-playhead")).to_be_visible()
            assert page.locator(".mobile-roll-bin").count() == 0
            assert page.locator(".mobile-roll-dot.active").count() == 0
            assert console_messages3 == []
            page.close()

            browser.close()


def test_bin_threshold_and_size_boundaries(tmp_path):
    # MOBP-04 precision edges: the strict `>` split comparison, the binSize
    # floor/cap, and the empty-input short-circuits — asserted directly
    # against the ported pure functions via window.__bcfMobile, independent
    # of any staged package's real roll data.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site, viewport=PHONE_PORTRAIT)

            # pxWidth=1000, total=100000 -> minWords = (5/1000)*100000 = 500.
            # binRolls splits with a STRICT `>` comparison against minWords
            # (verbatim port of design/mobile-ux/prototype/scrubber.jsx): a
            # gap of 501 words (one word past the threshold) separates; a
            # gap of exactly 500 (the threshold itself) or 499 (one word
            # under it) both merge.
            def bin_count(gap):
                rolls = [
                    {"word_position": 0, "outcome": "hit"},
                    {"word_position": gap, "outcome": "hit"},
                ]
                return page.evaluate(
                    "([rolls, total, width]) => window.__bcfMobile.binRolls(rolls, total, width).length",
                    [rolls, 100000, 1000],
                )

            assert bin_count(501) == 2
            assert bin_count(500) == 1
            assert bin_count(499) == 1

            assert page.evaluate(
                "([bin]) => window.__bcfMobile.binSize(bin)", [{"rolls": [{"outcome": "hit"}]}]
            ) == 6
            assert page.evaluate(
                "([bin]) => window.__bcfMobile.binSize(bin)",
                [{"rolls": [{"outcome": "hit"}] * 200}],
            ) == 14

            assert page.evaluate(
                "([rolls, total, width]) => window.__bcfMobile.binRolls(rolls, total, width)",
                [[], 100000, 1000],
            ) == []
            assert page.evaluate(
                "([rolls, total, width]) => window.__bcfMobile.binRolls(rolls, total, width)",
                [[{"word_position": 0, "outcome": "hit"}], 100000, 0],
            ) == []

            # Dominant-outcome tie-break: hit wins ties against miss/unknown;
            # miss wins ties against unknown. All three rolls merge into one
            # bin (spacing 1-2 words against a huge minWords).
            hit_dominant = page.evaluate(
                "([rolls, total, width]) => window.__bcfMobile.binRolls(rolls, total, width)[0].dominant",
                [
                    [
                        {"word_position": 0, "outcome": "hit"},
                        {"word_position": 1, "outcome": "hit"},
                        {"word_position": 2, "outcome": "miss"},
                    ],
                    100,
                    1,
                ],
            )
            assert hit_dominant == "hit"

            miss_dominant = page.evaluate(
                "([rolls, total, width]) => window.__bcfMobile.binRolls(rolls, total, width)[0].dominant",
                [
                    [
                        {"word_position": 0, "outcome": "hit"},
                        {"word_position": 1, "outcome": "miss"},
                        {"word_position": 2, "outcome": "miss"},
                    ],
                    100,
                    1,
                ],
            )
            assert miss_dominant == "miss"

            assert console_messages == []
            browser.close()


def test_rail_scrub_zoom_aware(tmp_path):
    # MOBP-03: every zoom level (1x/2x/4x/8x) lands the playhead on the word
    # under the finger, including auto-panned positions, through the single
    # attachRailScrub input path (D-17) — no second raw pointer listener.
    #
    # web/app.js is loaded `<script type="module">`, so its top-level `app`
    # binding is module-scoped, NOT reachable from page.evaluate()'s global
    # realm — every assertion below reads the resulting word position via
    # the `bcf:bookmark:word_position` localStorage key (written
    # synchronously by persistBookmarkNow() on a rail press's pointerup,
    # i.e. attachRailScrub's onScrubEnd) rather than a bare `app.wordPos`,
    # and reads total_words from the staged package's own JSON rather than
    # `app.data.story.total_words`. window.__bcfMobile is a real `window`
    # property (not module-scoped) and IS reachable directly.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        total_words = _facts_total_words(_tiny_default_facts(site))

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            def load(bookmark, zoom=1):
                storage = {
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(bookmark),
                    "bcf:timeline-zoom": str(zoom),
                    "bcf:help-seen": "true",
                }
                return _page_with_console_capture(browser, site, viewport=PHONE_PORTRAIT, storage=storage)

            def rail_click_at_fraction(page, fraction):
                rail_box = page.locator(".mobile-rail").bounding_box()
                assert rail_box is not None
                x = rail_box["x"] + rail_box["width"] * fraction
                y = rail_box["y"] + rail_box["height"] / 2
                page.mouse.move(x, y)
                page.mouse.down()
                page.mouse.up()
                page.wait_for_timeout(50)
                return int(page.evaluate("localStorage.getItem('bcf:bookmark:word_position')"))

            for zoom in (1, 2, 4, 8):
                # A single press at 25% of the rail from a seeded starting
                # word (50% of the story) lands within 1 word of the
                # independently-computed expected target.
                page, console_messages = load(5000, zoom)
                start_pct = (5000 / total_words) * 100
                expected = page.evaluate(
                    "([startPct, zoom, total]) => { "
                    "const panPct = window.__bcfMobile.panOffsetForPlayhead(startPct, zoom); "
                    "const innerFrac = window.__bcfMobile.mobileInnerFraction(0.25, zoom, panPct); "
                    "return Math.round(innerFrac * total); }",
                    [start_pct, zoom, total_words],
                )
                actual = rail_click_at_fraction(page, 0.25)
                assert abs(actual - expected) <= 1
                assert console_messages == []
                page.close()

                # Extreme left (seeded at word 0, panPct forced to 0 at every
                # zoom since startPct=0) lands exactly on word 0.
                page, console_messages = load(0, zoom)
                assert rail_click_at_fraction(page, 0.0) == 0
                assert console_messages == []
                page.close()

                # Extreme right (seeded at total_words, panPct forced to its
                # (zoom-1)*100 ceiling) lands exactly on total_words.
                page, console_messages = load(total_words, zoom)
                assert rail_click_at_fraction(page, 1.0) == total_words
                assert console_messages == []
                page.close()

            # --- Pure numeric assertions over window.__bcfMobile. ---
            page, console_messages = load(5000, 1)
            assert page.evaluate(
                "[0, 25, 50, 100].every(pct => window.__bcfMobile.panOffsetForPlayhead(pct, 1) === 0)"
            ) is True
            assert page.evaluate("window.__bcfMobile.panOffsetForPlayhead(0, 4)") == 0
            assert page.evaluate("window.__bcfMobile.panOffsetForPlayhead(100, 4)") == 300
            assert page.evaluate("window.__bcfMobile.panOffsetForPlayhead(50, 4)") == 150

            assert page.evaluate(
                "() => { "
                "const fracs = [-1, -0.5, 0, 0.25, 0.5, 1, 1.5, 2]; "
                "const zooms = [1, 2, 4, 8]; "
                "const pans = [0, 50, 100, 300, 700]; "
                "for (const z of zooms) for (const p of pans) for (const f of fracs) { "
                "const v = window.__bcfMobile.mobileInnerFraction(f, z, p); "
                "if (v < 0 || v > 1) return false; } "
                "return true; }"
            ) is True
            assert console_messages == []
            page.close()

            # --- Zoom 4x: rail inner's inline width is 400% and the hint
            #     row's right span begins with "4× zoom · ". ---
            page, console_messages = load(5000, 4)
            assert page.evaluate(
                "document.querySelector('.mobile-rail-inner').style.width"
            ) == "400%"
            hint_right = page.locator(".mobile-hint-row span").nth(1).text_content()
            assert hint_right.startswith("4× zoom · ")
            assert console_messages == []
            page.close()

            # --- Exactly one .mobile-rail element, and a forced layout-mode
            #     round trip (desktop -> portrait) never leaves a stale
            #     duplicate scrub listener behind: a single press after the
            #     round trip still lands exactly on the single-press
            #     expected target (a second, competing listener would double-
            #     fire onScrub and desync the result). ---
            page, console_messages = load(5000, 1)
            assert page.evaluate("document.querySelectorAll('.mobile-rail').length") == 1
            page.set_viewport_size({"width": 1400, "height": 900})  # desktop: tears down portrait gestures
            page.wait_for_timeout(100)
            page.set_viewport_size(PHONE_PORTRAIT)  # back to portrait: re-attaches exactly once
            page.wait_for_timeout(100)
            assert page.evaluate("document.querySelectorAll('.mobile-rail').length") == 1
            # wordPos hasn't moved since the seeded bookmark (5000) — no
            # scrub has happened yet on this page, and the round trip itself
            # doesn't touch wordPos — so the seeded value is still current.
            start_pct = (5000 / total_words) * 100
            expected = page.evaluate(
                "([startPct, total]) => { "
                "const panPct = window.__bcfMobile.panOffsetForPlayhead(startPct, 1); "
                "const innerFrac = window.__bcfMobile.mobileInnerFraction(0.25, 1, panPct); "
                "return Math.round(innerFrac * total); }",
                [start_pct, total_words],
            )
            actual = rail_click_at_fraction(page, 0.25)
            assert abs(actual - expected) <= 1
            assert console_messages == []
            page.close()

            browser.close()


def test_portrait_empty_and_partial_states(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # Playhead before the first roll (word 0): no amber chip, no
            # focal label — structurally absent, never blanked placeholders.
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            assert page.evaluate("document.querySelector('.mobile-chip.amber')") is None
            assert page.evaluate("document.querySelector('.mobile-focal-label')") is None
            title_text = page.locator(".mobile-dock-title").inner_text()
            assert title_text != "undefined"
            assert console_messages == []
            page.close()

            # A chapter-less package: chapterAtWord() has nothing to resolve,
            # so the dock title falls back to the literal em-dash — never
            # the string "undefined".
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                path="/web/?dataPackage=chapterless",
                viewport=PHONE_PORTRAIT,
                storage={"bcf:preview-port-storage-version": "3", "bcf:help-seen": "true"},
            )
            fallback_title = page.locator(".mobile-dock-title").inner_text()
            assert fallback_title == "—"
            assert console_messages == []
            page.close()

            browser.close()


def _total_rolls(facts: dict) -> int:
    return sum(len(chapter.get("rolls", [])) for chapter in facts.get("chapters", []))


def _format_words(n: int) -> str:
    # Mirrors web/app.js's formatWords() exactly — used to assert the About
    # flyout's dataset line without duplicating a second word-count format.
    value = max(0, round(n))
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if value >= 1000:
        return f"{round(value / 1000)}k"
    return str(value)


def test_surface_stack_focus_trap_and_back_gesture(tmp_path):
    # MOBP-05 (Task 1): the one surface stack — a backdrop tap and the
    # phone's own back gesture both close a surface and leave the browser
    # history length unchanged; focus is trapped inside the flyout while
    # it's open and returns to the button that opened it on close (D-16);
    # sky gestures are inert while a surface is open.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Backdrop close: exactly one flyout + backdrop mount, and
            #     the sentinel is fully consumed — history.state (the CURRENT
            #     entry) is back to whatever it was before the open, proving
            #     history.back() actually moved off the "surface-open" entry
            #     rather than leaving it as the current position. (Raw
            #     window.history.length never shrinks via back() — that's
            #     normal joint-session-history behavior — so the CURRENT
            #     entry's state, not the stack's total length, is what
            #     proves the sentinel was consumed.) ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            history_state_before = page.evaluate("window.history.state")
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            assert page.locator(".mobile-flyout-backdrop").count() == 1
            assert page.evaluate("window.history.state") == {"bcfMobileSurface": "settings"}
            page.locator(".mobile-flyout-backdrop").click(position={"x": 5, "y": 5})
            assert page.locator(".mobile-flyout").count() == 0
            assert page.locator(".mobile-flyout-backdrop").count() == 0
            page.wait_for_timeout(50)
            assert page.evaluate("window.history.state") == history_state_before
            assert console_messages == []
            page.close()

            # --- Back gesture close: the surface closes and the page is
            #     still on the app URL — the back gesture never leaves the
            #     app itself. ---
            page, console_messages2 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout").count() == 1
            page.go_back()
            page.wait_for_timeout(50)
            assert page.locator(".mobile-flyout").count() == 0
            assert page.evaluate("document.querySelector('.mobile-app') != null") is True
            assert console_messages2 == []
            page.close()

            # --- Focus trap: focus starts inside the flyout, Tab past every
            #     focusable control keeps focus inside it (wrapped, never
            #     escaped to the document), and closing restores focus to
            #     the gear button that opened it. ---
            page, console_messages3 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
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
            for _ in range(focusable_count + 2):
                page.keyboard.press("Tab")
            assert page.evaluate(
                "document.querySelector('.mobile-flyout').contains(document.activeElement)"
            ) is True
            page.locator(".mobile-flyout-backdrop").click(position={"x": 5, "y": 5})
            assert page.evaluate(
                "document.activeElement === document.querySelector('[data-action=\"mobile-open-settings\"]')"
            ) is True
            assert console_messages3 == []
            page.close()

            # --- Sky gestures are inert while a surface is open: a tap
            #     landing on .mobile-sky never toggles playback (the
            #     backdrop sits on top and intercepts it — a "force" click
            #     bypasses Playwright's own obstruction check, matching what
            #     a real tap would hit, since the backdrop is the topmost
            #     element there by design while a surface is open). ---
            page, console_messages4 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            fab_label_before = page.locator(".mobile-fab-play").get_attribute("aria-label")
            page.click(".mobile-sky", force=True)
            assert page.locator(".mobile-fab-play").get_attribute("aria-label") == fab_label_before
            assert console_messages4 == []

            browser.close()


def test_settings_about_help_persist_across_reload(tmp_path):
    # MOBP-05 (Tasks 1 + 2): Settings group order is locked; every control
    # writes through the existing shared setter/delegated action and its
    # value survives a reload; the About flyout's source links and dataset
    # stats read the live STORY_LINKS/app.data.story; the Help overlay's
    # seven gesture rows and CTA are verbatim; opening one surface from
    # another (or opening Settings while About is open) leaves exactly one
    # surface mounted at a time.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _tiny_default_facts(site)
        total_rolls = _total_rolls(facts)
        total_chapters = len(facts.get("chapters", []))
        total_words = _facts_total_words(facts)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Settings group order (MOBP-05 ordering edge). ---
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            page.click('[data-action="mobile-open-settings"]')
            # all_text_contents() (not all_inner_texts()) — .mobile-group-label
            # is styled text-transform:uppercase, which inner_text() would
            # reflect (same pitfall documented for .mobile-hint-row in 02-02).
            labels = page.locator(".mobile-flyout .mobile-group-label").all_text_contents()
            assert labels == ["View mode", "On roll", "Speed", "Timeline zoom", "Comfort"]

            # --- Calling setMode with an out-of-allow-list value leaves
            #     storage untouched (T-02-12). ---
            mode_before = page.evaluate("localStorage.getItem('bcf:mode')")
            page.evaluate("window.__bcfMobile.setMode('details')")  # prototype's plural spelling
            assert page.evaluate("localStorage.getItem('bcf:mode')") == mode_before

            # --- Select Details / Skip / 2x speed / 4x zoom / both Comfort
            #     rows off, then reload and confirm every value round-trips
            #     through an allow-listed value the app itself reads back. ---
            groups = page.locator(".mobile-flyout .mobile-group")
            view_mode_group = groups.nth(0)
            on_roll_group = groups.nth(1)
            speed_group = groups.nth(2)
            zoom_group = groups.nth(3)
            comfort_group = groups.nth(4)

            view_mode_group.get_by_text("Details", exact=True).click()
            on_roll_group.locator('[data-on-roll-behavior="quick"]').click()
            speed_group.get_by_text("2×", exact=True).click()
            zoom_group.get_by_text("4×", exact=True).click()
            comfort_group.locator(".mobile-row-val").nth(0).click()
            comfort_group.locator(".mobile-row-val").nth(1).click()

            assert page.evaluate("localStorage.getItem('bcf:mode')") == "detail"
            assert page.evaluate("localStorage.getItem('bcf:on-roll-behavior')") == "quick"
            assert page.evaluate("localStorage.getItem('bcf:playback:speed:v2')") == "10000"
            assert console_messages == []

            page.reload(wait_until="networkidle")
            assert page.evaluate("localStorage.getItem('bcf:mode')") == "detail"
            assert page.evaluate("localStorage.getItem('bcf:on-roll-behavior')") == "quick"
            assert page.evaluate("localStorage.getItem('bcf:playback:speed:v2')") == "10000"
            assert page.evaluate("window.__bcfPrefs.mobileTimelineZoom") == 4
            assert page.evaluate("window.__bcfPrefs.tapToPause") is False
            assert page.evaluate("window.__bcfPrefs.haptics") is False

            # Reopening Settings shows those same options marked active.
            page.click('[data-action="mobile-open-settings"]')
            assert page.locator(".mobile-flyout .mobile-group").nth(0)\
                .get_by_text("Details", exact=True).get_attribute("class") == "is-active"
            assert page.locator('.mobile-flyout [data-on-roll-behavior="quick"]').get_attribute("class") == "is-active"
            assert page.locator(".mobile-flyout .mobile-group").nth(2)\
                .get_by_text("2×", exact=True).get_attribute("class") == "is-active"
            assert page.locator(".mobile-flyout .mobile-group").nth(3)\
                .get_by_text("4×", exact=True).get_attribute("class") == "is-active"
            comfort_after = page.locator(".mobile-flyout .mobile-group").nth(4).locator(".mobile-row-val")
            assert comfort_after.nth(0).inner_text() == "Off"
            assert comfort_after.nth(1).inner_text() == "Off"
            assert console_messages == []
            page.close()

            # --- Short viewport: every .mobile-seg button stays reachable
            #     inside the viewport, and the flyout scrolls internally
            #     rather than clipping. ---
            page2, console_messages2 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT_SMALL, storage=DEFAULT_STORAGE,
            )
            page2.click('[data-action="mobile-open-settings"]')
            seg_boxes = page2.eval_on_selector_all(
                ".mobile-flyout .mobile-seg button",
                "els => els.map(el => { const r = el.getBoundingClientRect(); "
                "return { top: r.top, bottom: r.bottom, left: r.left, right: r.right }; })",
            )
            assert len(seg_boxes) > 0
            for box in seg_boxes:
                assert box["top"] >= 0
                assert box["bottom"] <= PHONE_PORTRAIT_SMALL["height"]
                assert box["left"] >= 0
                assert box["right"] <= PHONE_PORTRAIT_SMALL["width"]
            assert page2.evaluate(
                "getComputedStyle(document.querySelector('.mobile-flyout')).overflowY"
            ) == "auto"
            assert console_messages2 == []
            page2.close()

            # --- About flyout: live STORY_LINKS hrefs (never the
            #     prototype's stale hard-coded URLs), live dataset counts,
            #     and the Gestures & help hand-off to the Help overlay. ---
            page3, console_messages3 = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            page3.click('[data-action="mobile-open-info"]')
            about = page3.locator('.mobile-flyout[aria-label="About"]')
            expect = playwright_api.expect
            expect(about).to_be_visible()

            links = page3.locator('.mobile-flyout[aria-label="About"] .mobile-source-row a')
            assert links.count() == 3
            hrefs = links.evaluate_all("els => els.map(el => el.href)")
            targets = links.evaluate_all("els => els.map(el => el.target)")
            rels = links.evaluate_all("els => els.map(el => el.rel)")
            assert set(hrefs) == {
                "https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks",
                "https://www.fanfiction.net/s/13574944/1/Brockton-s-Celestial-Forge",
                "https://archiveofourown.org/works/23949661/navigate",
            }
            assert all(t == "_blank" for t in targets)
            assert all("noopener" in r and "noreferrer" in r for r in rels)

            dataset_text = page3.locator(
                '.mobile-flyout[aria-label="About"] .mobile-flyout-dataset'
            ).inner_text()
            assert f"{total_rolls} rolls" in dataset_text
            assert f"{total_chapters} chapters" in dataset_text
            assert f"{_format_words(total_words)} words" in dataset_text

            # Opening Settings while About is open leaves exactly one
            # surface mounted.
            page3.click('[data-action="mobile-open-settings"]')
            assert page3.locator(".mobile-flyout").count() == 1
            assert page3.locator('.mobile-flyout[aria-label="Settings"]').count() == 1
            assert page3.locator('.mobile-flyout[aria-label="About"]').count() == 0

            # Reopen About, then hand off to Help — About gone, Help present.
            page3.locator(".mobile-flyout-backdrop").click(position={"x": 5, "y": 5})
            page3.click('[data-action="mobile-open-info"]')
            page3.click(".mobile-full-btn")
            assert page3.locator('.mobile-flyout[aria-label="About"]').count() == 0
            assert page3.locator(".mobile-help-overlay").count() == 1

            gesture_rows = page3.locator(".mobile-help-gestures .ico")
            assert gesture_rows.count() == 7
            # text_content() (not inner_text()) — .mobile-got-it is styled
            # text-transform:uppercase (locked verbatim from the prototype),
            # which inner_text() would reflect.
            assert page3.locator(".mobile-got-it").text_content() == "Got it — read on"
            assert console_messages3 == []

            browser.close()


def test_first_run_help_auto_opens_once(tmp_path):
    # MOBP-05 (Task 2): a first visit with empty storage auto-opens the Help
    # overlay with no extra structural render; dismissing it records
    # help-seen so a reload never remounts it; the dock (including the Play
    # FAB) stays fully operable throughout (D-19).
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # --- Empty storage: help auto-opens with no extra structural
            #     render versus a load with helpSeen pre-seeded. ---
            page_empty, console_empty = _page_with_console_capture(
                browser,
                site,
                storage={"bcf:preview-port-storage-version": "3"},
                viewport=PHONE_PORTRAIT,
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )
            assert page_empty.evaluate("document.querySelector('.mobile-help-overlay') != null") is True
            renders_empty = page_empty.evaluate("window.__bcfRenderStats.structuralRenders")

            assert page_empty.evaluate("window.__bcfPrefs.tapToPause") is True
            assert page_empty.evaluate("window.__bcfPrefs.haptics") is True
            assert page_empty.evaluate("window.__bcfPrefs.mobileTimelineZoom") == 1
            assert page_empty.evaluate("window.__bcfPrefs.helpSeen") is False

            # The dock stays fully operable while the auto-opened overlay is
            # present — the Play FAB is outside .mobile-sky (D-19).
            page_empty.click('button[aria-label="Play"]')
            expect(page_empty.locator('button[aria-label="Pause"]')).to_be_visible()

            assert console_empty == []
            page_empty.close()

            page_seeded, console_seeded = _page_with_console_capture(
                browser,
                site,
                storage={"bcf:preview-port-storage-version": "3", "bcf:help-seen": "true"},
                viewport=PHONE_PORTRAIT,
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )
            assert page_seeded.evaluate("document.querySelector('.mobile-help-overlay')") is None
            renders_seeded = page_seeded.evaluate("window.__bcfRenderStats.structuralRenders")
            assert renders_empty == renders_seeded
            assert console_seeded == []
            page_seeded.close()

            # --- Dismiss via the CTA persists help-seen and never remounts
            #     after a reload; a click with no data-action target nearby
            #     is a harmless no-op once nothing is open to dismiss. ---
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={"bcf:preview-port-storage-version": "3"},
                viewport=PHONE_PORTRAIT,
            )
            page.click(".mobile-got-it")
            assert page.evaluate("document.querySelector('.mobile-help-overlay')") is None
            assert page.evaluate("localStorage.getItem('bcf:help-seen')") == "true"

            page.reload(wait_until="networkidle")
            assert page.evaluate("document.querySelector('.mobile-help-overlay')") is None

            page.click(".mobile-dock-now")
            assert console_messages == []
            page.close()


def test_landscape_no_longer_falls_back_to_desktop_shell(tmp_path):
    # 03-01 phase-open proof: D-12's interim landscape fallback (desktop
    # shell + portrait banner) is RETIRED ON PURPOSE — Phase 3 replaces it
    # with renderMobileLandscape(), which is exactly what this test now
    # asserts. This is the inverse of the pre-Phase-3 contract this test used
    # to assert (see git history for the old body); it is a deliberate,
    # recorded change Phase 4 needs before it deletes the portrait banner
    # globally, not a regression. Renamed from
    # test_landscape_fallback_is_unchanged.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )

            assert page.evaluate("window.__bcfLayoutMode") == "landscape"

            # The desktop shell and its portrait-banner safety net must NEVER
            # mount at a landscape viewport now that renderMobileLandscape()
            # exists.
            assert page.evaluate("document.querySelector('.app')") is None
            assert page.evaluate("document.querySelector('.portrait-banner')") is None

            # renderMobileLandscape()'s own root mounts instead.
            expect(page.locator(".mobile-app")).to_be_visible()

            # Phase 1's gesture probe (F-01) is still attached in every
            # non-desktop layout mode, including landscape.
            assert page.evaluate("document.querySelector('.mobile-gesture-probe') != null") is True

            assert console_messages == []
            browser.close()


def test_rail_drag_is_monotonic_at_every_zoom(tmp_path):
    # MOBP-03 regression: a CONTINUOUS drag (one pointerdown, several
    # pointermoves) must move the playhead in the direction of the finger at
    # every zoom level.
    #
    # test_rail_scrub_zoom_aware above only exercises single discrete presses,
    # which are deterministic — each press captures its own auto-pan and
    # commits once. The defect this test pins lives strictly BETWEEN moves of
    # one drag: recomputing auto-pan per move feeds the position just
    # committed back into the mapping, shifting the rail content under a
    # finger that has not moved, so the next move lands somewhere unrelated.
    # Measured on a Pixel 10 Pro XL at 4x before the fix, a monotonic
    # rightward drag drove the playhead 68k words BACKWARD (398k -> 330k)
    # before recovering.
    #
    # Mid-drag the bookmark key is not yet written (persistBookmarkNow runs on
    # onScrubEnd), so this reads the live playhead marker's left% instead,
    # which tracks wordPos through the incremental update tier.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        total_words = _facts_total_words(_tiny_default_facts(site))

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            for zoom in (1, 2, 4, 8):
                page, console_messages = _page_with_console_capture(
                    browser,
                    site,
                    viewport=PHONE_PORTRAIT,
                    storage={
                        "bcf:preview-port-storage-version": "3",
                        "bcf:bookmark:word_position": str(total_words // 2),
                        "bcf:timeline-zoom": str(zoom),
                        "bcf:help-seen": "true",
                    },
                )

                rail_box = page.locator(".mobile-rail").bounding_box()
                assert rail_box is not None
                y = rail_box["y"] + rail_box["height"] / 2

                def playhead_pct():
                    raw = page.evaluate(
                        "() => document.querySelector('.mobile-playhead')?.style.left ?? null"
                    )
                    assert raw is not None, "portrait playhead marker not found"
                    return float(raw.rstrip("%"))

                def x_at(fraction):
                    return rail_box["x"] + rail_box["width"] * fraction

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


# ---------------------------------------------------------------------------
# 04-02-PLAN.md: the visually-hidden aria-live region (MOBX-03/D-42..D-45)
# and mobile keyboard equivalents (MOBX-03/D-46..D-48). No analog existed in
# this file before this plan (grep confirmed zero aria-live/keyboard
# assertions) — see 04-PATTERNS.md.
# ---------------------------------------------------------------------------

_LIVE_REGION_MUTATION_OBSERVER_SCRIPT = (
    "() => { window.__liveRegionMutationCount = 0; "
    "const el = document.querySelector('.mobile-live-region'); "
    "const mo = new MutationObserver(() => { window.__liveRegionMutationCount += 1; }); "
    "mo.observe(el, { childList: true, characterData: true, subtree: true }); "
    "window.__liveRegionMO = mo; }"
)


def _install_live_region_mutation_counter(page):
    # Counts MutationObserver CALLBACK invocations, not raw mutation
    # records — announceMobileRoll()'s two synchronous textContent writes
    # (clear, then set) land in the SAME microtask batch, so one call to
    # announceMobileRoll() always increments this counter by exactly 1.
    page.evaluate(_LIVE_REGION_MUTATION_OBSERVER_SCRIPT)


def test_mobile_live_region_mounts_hidden_on_mobile_only(tmp_path):
    # MOBX-03 (D-42..D-44): exactly one polite live region exists in the
    # mobile shell, hidden with 04-UI-SPEC.md's LOCKED visually-hidden
    # technique — a non-zero 1px box, clipped, never display:none/
    # visibility:hidden/aria-hidden (any of those removes the node from the
    # accessibility tree while still passing a DOM-presence assertion). It
    # must never mount on the desktop path (frozen).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            assert page.locator('.mobile-live-region[role="status"]').count() == 1
            box = page.evaluate(
                "() => { const el = document.querySelector('.mobile-live-region'); "
                "const cs = getComputedStyle(el); "
                "return { width: parseFloat(cs.width), height: parseFloat(cs.height), "
                "display: cs.display, visibility: cs.visibility, "
                "ariaLive: el.getAttribute('aria-live'), ariaAtomic: el.getAttribute('aria-atomic') }; }"
            )
            assert 0 < box["width"] <= 2
            assert 0 < box["height"] <= 2
            assert box["display"] != "none"
            assert box["visibility"] != "hidden"
            assert box["ariaLive"] == "polite"
            assert box["ariaAtomic"] == "true"
            assert console_messages == []
            page.close()

            # Desktop path (>= 1100px, frozen): the live region never mounts.
            page, console_messages2 = _page_with_console_capture(
                browser, site, viewport={"width": 1400, "height": 900},
            )
            assert page.evaluate("document.querySelector('.mobile-live-region')") is None
            assert console_messages2 == []
            browser.close()


def test_mobile_live_region_announces_on_swipe_and_silent_on_tap(tmp_path):
    # A swipe-step names the roll number, total, perk and CP; a plain tap
    # never calls setWordPos() (it only toggles play state / reveals chrome)
    # so it must never write the live region (D-42's resolved tap ambiguity).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            # Fresh page per phase (matching this file's own established
            # pattern) — a plain tap starts playback (tap-to-pause is on by
            # default), and a running playback tick would otherwise drift
            # the word position the swipe phase below depends on.
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "5000"},
            )
            sky = page.locator(".mobile-sky")

            # Two plain taps (toggle play, then toggle back) never announce.
            sky.click()
            page.wait_for_timeout(100)
            assert page.locator(".mobile-live-region").text_content() == ""
            page.wait_for_timeout(400)
            sky.click()
            page.wait_for_timeout(100)
            assert page.locator(".mobile-live-region").text_content() == ""
            assert console_messages == []
            page.close()

            # A swipe forward from word 5000 lands on the cluster's last roll
            # + 1 step -> the first spread roll (word 7200, hit, "Dense Perk
            # 9", 100 CP) -> roll 9 of 12 in this fixture's sorted roll list.
            # 24px engage + 1*56px step = 80px; a <=88px drag stays inside the
            # single-step band (2 steps would need >=136px).
            page, console_messages2 = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "5000"},
            )
            sky = page.locator(".mobile-sky")
            sky_box = sky.bounding_box()
            assert sky_box is not None
            x = sky_box["x"] + sky_box["width"] / 2
            y = sky_box["y"] + sky_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            for dx in range(8, 89, 8):
                page.mouse.move(x + dx, y)
            page.mouse.up()
            page.wait_for_timeout(100)

            text = page.locator(".mobile-live-region").text_content()
            assert text == "Roll 9 of 12. Dense Perk 9, 100 CP."
            # Structural safety: a text-only write, never markup.
            assert page.evaluate("document.querySelector('.mobile-live-region').children.length") == 0
            assert console_messages2 == []
            browser.close()


def test_mobile_live_region_renders_special_characters_as_text(tmp_path):
    # T-04-05: the perk-name string flows through node.textContent only,
    # never innerHTML — a name with special characters (em-dash, accented
    # letters) must reach the DOM as literal text.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                # Word 3105 resolves to the cluster's very first roll (word
                # 3100, hit, the long-multibyte-perk-name fixture roll).
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "3105"},
            )
            sky = page.locator(".mobile-sky")
            sky.dblclick()
            page.wait_for_timeout(100)
            text = page.locator(".mobile-live-region").text_content()
            assert text == f"Roll 1 of 12. {LONG_MULTIBYTE_PERK_NAME}, 100 CP."
            assert page.evaluate("document.querySelector('.mobile-live-region').children.length") == 0
            assert console_messages == []
            browser.close()


def test_mobile_live_region_rail_scrub_announces_once_at_release(tmp_path):
    # D-42: a rail-scrub DRAG writes nothing on any pointermove — only the
    # settled position at pointerup announces, exactly once, never a
    # throttled stream of the ones in between.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "0"},
            )
            _install_live_region_mutation_counter(page)

            rail_box = page.locator(".mobile-rail").bounding_box()
            assert rail_box is not None
            y = rail_box["y"] + rail_box["height"] / 2
            x_start = rail_box["x"] + rail_box["width"] * 0.1
            page.mouse.move(x_start, y)
            page.mouse.down()
            for frac in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
                page.mouse.move(rail_box["x"] + rail_box["width"] * frac, y)
                page.wait_for_timeout(10)
            page.mouse.up()
            page.wait_for_timeout(100)

            assert page.evaluate("window.__liveRegionMutationCount") == 1
            assert page.locator(".mobile-live-region").text_content() != ""
            assert console_messages == []
            browser.close()


def test_mobile_live_region_silent_during_free_playback(tmp_path):
    # D-42/D-45: the live region never writes during free playback, however
    # many rolls it crosses — a throttle is explicitly forbidden (it would
    # silently drop announcements and misreport the roll count), so the only
    # correct behavior is total silence between user gestures.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={
                    **DEFAULT_STORAGE,
                    # word 3100 = the cluster's first roll; "quick" on-roll
                    # behavior skips the cinematic lock entirely, so tickPlayback
                    # never stalls mid-cluster; a fast speed guarantees crossing
                    # the whole 8-roll cluster (words 3100-3170) well inside the
                    # wait window below.
                    "bcf:bookmark:word_position": "3100",
                    "bcf:on-roll-behavior": "quick",
                    "bcf:playback:speed:v2": "5000",
                },
            )
            sky = page.locator(".mobile-sky")
            sky.dblclick()  # snaps to roll 1 (already there) and starts playing
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(100)
            text_before = page.locator(".mobile-live-region").text_content()
            assert text_before != ""

            _install_live_region_mutation_counter(page)
            page.wait_for_timeout(500)
            sky.click()  # pause; forces an immediate, synchronous bookmark write
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            page.wait_for_timeout(50)

            bookmark = int(page.evaluate("localStorage.getItem('bcf:bookmark:word_position')"))
            assert bookmark > 3170  # advanced past the whole 8-roll cluster
            assert page.evaluate("window.__liveRegionMutationCount") == 0
            assert page.locator(".mobile-live-region").text_content() == text_before
            assert console_messages == []
            browser.close()


def test_mobile_live_region_empty_when_no_roll_before_playhead(tmp_path):
    # MOBX-03 edge (empty): scrubbing to a position before the first roll
    # writes nothing — silence, not a placeholder string.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "5000"},
            )
            rail_box = page.locator(".mobile-rail").bounding_box()
            assert rail_box is not None
            x = rail_box["x"]  # leftmost edge -> word 0, before the first roll (word 3100)
            y = rail_box["y"] + rail_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.up()
            page.wait_for_timeout(100)

            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "0"
            assert page.locator(".mobile-live-region").text_content() == ""
            assert console_messages == []
            browser.close()


def test_mobile_live_region_reannounces_repeat_landing(tmp_path):
    # MOBX-03 edge (ordering): landing on the same roll twice in a row still
    # re-announces — proven by observing a MUTATION, not by comparing two
    # equal strings (an unchanged string written twice produces no second
    # screen-reader announcement unless the node actually mutates).
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "5000"},
            )
            _install_live_region_mutation_counter(page)
            sky = page.locator(".mobile-sky")

            sky.dblclick()
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(50)
            text_first = page.locator(".mobile-live-region").text_content()
            assert text_first != ""

            page.wait_for_timeout(400)  # past the double-tap detection window
            sky.click()  # pause, so the second double-tap lands on the same roll
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            page.wait_for_timeout(400)

            sky.dblclick()
            page.wait_for_timeout(50)
            text_second = page.locator(".mobile-live-region").text_content()

            assert text_second == text_first
            assert page.evaluate("window.__liveRegionMutationCount") == 2
            assert console_messages == []
            browser.close()


def test_mobile_keyboard_arrows_step_one_roll_and_announce(tmp_path):
    # D-46/D-47: ArrowRight/ArrowLeft step exactly ONE ROLL on mobile via the
    # same rollStepFrom() the swipe callback already calls, and announce.
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
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": str(mid_word)},
            )
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == str(forward_one)
            assert page.locator(".mobile-live-region").text_content() != ""

            page.keyboard.press("ArrowLeft")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == str(last_at_or_before)

            assert console_messages == []
            browser.close()


def test_mobile_keyboard_home_snaps_to_live_edge_and_resumes(tmp_path):
    # D-46: Home mirrors the double-tap body exactly — the last roll at or
    # before the playhead, resuming playback — NOT desktop's jump to word 0.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        roll_positions = _dense_rolls_positions_sorted(facts)
        mid_word = 5000
        last_at_or_before = max(w for w in roll_positions if w <= mid_word)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": str(mid_word)},
            )
            expect(page.locator('button[aria-label="Play"]')).to_be_visible()
            page.keyboard.press("Home")
            expect(page.locator('button[aria-label="Pause"]')).to_be_visible()
            page.wait_for_timeout(50)

            bookmark = page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")
            assert bookmark == str(last_at_or_before)
            assert page.locator(".mobile-live-region").text_content() != ""
            assert console_messages == []
            browser.close()


def test_mobile_keyboard_question_mark_toggles_help(tmp_path):
    # D-48: `?` routes through the same openMobileSurface("help") call the
    # on-screen button makes, so a second press closes it — no second
    # history sentinel (window.history.state, not the raw joint-session
    # history.length, is the correct proxy: history.back() never shrinks
    # history.length — see test_surface_stack_focus_trap_and_back_gesture's
    # own comment on this exact point).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_PORTRAIT, storage=DEFAULT_STORAGE,
            )
            history_state_before = page.evaluate("window.history.state")

            page.keyboard.press("?")
            page.wait_for_timeout(50)
            assert page.locator(".mobile-help-overlay").count() == 1

            page.keyboard.press("?")
            page.wait_for_timeout(50)
            assert page.locator(".mobile-help-overlay").count() == 0
            assert page.evaluate("window.history.state") == history_state_before

            assert console_messages == []
            browser.close()


def test_mobile_keyboard_arrow_adjacency_holds_at_list_ends(tmp_path):
    # MOBX-03 edge (adjacency): stepping past either end of the roll list
    # holds at the first/last roll (rollStepFrom clamps) and re-announces
    # that same roll on every press, rather than wrapping or going silent.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _dense_rolls_facts(site)
        roll_positions = _dense_rolls_positions_sorted(facts)
        first_roll_word = roll_positions[0]
        last_roll_word = roll_positions[-1]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": str(first_roll_word)},
            )
            _install_live_region_mutation_counter(page)
            for _ in range(3):
                page.keyboard.press("ArrowLeft")
                page.wait_for_timeout(30)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == str(first_roll_word)
            assert page.evaluate("window.__liveRegionMutationCount") == 3
            assert console_messages == []
            page.close()

            page, console_messages2 = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": str(last_roll_word)},
            )
            _install_live_region_mutation_counter(page)
            for _ in range(3):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(30)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == str(last_roll_word)
            assert page.evaluate("window.__liveRegionMutationCount") == 3
            assert console_messages2 == []
            browser.close()


def test_desktop_keyboard_stepping_unaffected_by_mobile_branch(tmp_path):
    # D-47/§0.1: the new mobile branch never leaks into desktop — arrow step
    # sizes (10000, 2000 with shift) and Home (word 0) stay byte-identical,
    # asserted numerically (a mobile-shaped leak would still "move," just by
    # the wrong amount, so a directional assertion would not catch it).
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            def desktop_page(bookmark):
                return _page_with_console_capture(
                    browser, site, viewport={"width": 1400, "height": 900},
                    storage={
                        "bcf:preview-port-storage-version": "3",
                        "bcf:bookmark:word_position": str(bookmark),
                    },
                )

            page, console_messages = desktop_page(0)
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "10000"
            assert console_messages == []
            page.close()

            page, console_messages2 = desktop_page(0)
            page.keyboard.press("Shift+ArrowRight")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "2000"
            assert console_messages2 == []
            page.close()

            page, console_messages3 = desktop_page(5000)
            page.keyboard.press("Home")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "0"
            assert page.evaluate("document.querySelector('.mobile-live-region')") is None
            assert console_messages3 == []
            browser.close()


def test_mobile_keyboard_space_toggles_playback_on_every_layout(tmp_path):
    # MOBX-03: Space needs no new code — the existing handler's Space case
    # has no layoutMode gate and already toggles playback identically
    # everywhere; this closes the requirement with a test, not an edit.
    playwright_api = pytest.importorskip("playwright.sync_api")
    expect = playwright_api.expect

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)

            cases = [
                (PHONE_PORTRAIT, 'button[aria-label="Play"]', 'button[aria-label="Pause"]'),
                (PHONE_LANDSCAPE, '.mobile-cinema-scrub-fab[aria-label="Play"]', '.mobile-cinema-scrub-fab[aria-label="Pause"]'),
                ({"width": 1400, "height": 900}, "#play-pause[aria-label='Play']", "#play-pause[aria-label='Pause']"),
            ]
            for viewport, play_sel, pause_sel in cases:
                page, console_messages = _page_with_console_capture(
                    browser, site, viewport=viewport, storage=DEFAULT_STORAGE,
                )
                expect(page.locator(play_sel)).to_be_visible()
                page.keyboard.press("Space")
                expect(page.locator(pause_sel)).to_be_visible()
                page.keyboard.press("Space")
                expect(page.locator(play_sel)).to_be_visible()
                assert console_messages == []
                page.close()

            browser.close()


def test_mobile_keyboard_respects_editable_guard(tmp_path):
    # D-47: the mobile branch lives AFTER the handler's existing editable
    # guard, so a focused text control still swallows these keys exactly as
    # it swallows desktop's — this app's own mobile Settings surface is
    # all-button (no text input) today, so a bare <input> is synthesized to
    # exercise the guard honestly.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, path="/web/?dataPackage=dense-rolls",
                viewport=PHONE_PORTRAIT,
                storage={**DEFAULT_STORAGE, "bcf:bookmark:word_position": "5000"},
            )
            page.evaluate(
                "() => { const i = document.createElement('input'); "
                "document.body.appendChild(i); i.focus(); }"
            )
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(50)
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "5000"

            page.keyboard.press("?")
            page.wait_for_timeout(50)
            assert page.evaluate("document.querySelector('.mobile-help-overlay')") is None

            assert console_messages == []
            browser.close()
