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
                storage={"bcf:preview-port-storage-version": "3", "bcf:bookmark:word_position": "0"},
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
                storage={"bcf:preview-port-storage-version": "3"},
            )
            fallback_title = page.locator(".mobile-dock-title").inner_text()
            assert fallback_title == "—"
            assert console_messages == []
            page.close()

            browser.close()
