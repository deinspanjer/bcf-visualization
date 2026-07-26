"""D-10 desktop smoke gate (MOBF-06).

Scripts the INTEGRATION_PLAN.md §0.5 six-step manual desktop smoke checklist
into pytest+Playwright checks so "desktop unchanged" is a command with an
exit code, not a claim. Per the Milestone Gates, a Track A phase (this one
and Phases 2-4) that fails this test is not done — re-run it unchanged at
every phase gate (§5).

Quick command: `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q`

Peer module to tests/test_web_app_integration.py — same harness
(staged_web_runtime_site), same console-capture convention, but this file's
own default viewport is 1920x1080 (all tests here run at >= 1100px except
the step-5/6 resize tests, which sweep down through and across the mobile
breakpoint and back).

Synthetic fixture note: the staged site serves the tiny-default synthetic
data package (tests/helpers/web_runtime_site.py), which has a small roll
count. §0.5 step 3's "scrub to roll #47" is adapted here to "scrub to the
last roll in the fixture dataset" — the behavior under test (scrub-to-roll
centers/focuses its carousel card) is data-size-independent (see this
plan's PLAN.md <interfaces> note, 01-03-PLAN.md).
"""

from __future__ import annotations

import json
import re

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
    # Default viewport is 1920x1080 (desktop) — distinct from
    # test_web_app_integration.py's 1280x900 default, per this file's own
    # smoke-test convention (every test here exercises the >= 1100px range
    # except the step-5/6 resize sweeps in this same file).
    page = browser.new_page(viewport=viewport or {"width": 1920, "height": 1080})
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


def _read_visualization_facts(site) -> dict:
    facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
    return json.loads(facts_path.read_text())


def _total_fixture_rolls(facts: dict) -> int:
    return sum(len(chapter.get("rolls", [])) for chapter in facts.get("chapters", []))


def _first_fixture_roll_word(facts: dict) -> int:
    for chapter in facts.get("chapters", []):
        rolls = chapter.get("rolls", [])
        if rolls:
            return rolls[0]["epub_word_offset_predicted"]
    raise AssertionError("fixture has no rolls")


# ── §0.5 steps 1-4: static render, playback, carousel focus, details mode ──


def test_desktop_static_shell_renders_full_shell_with_no_portrait_banner(tmp_path):
    # §0.5 step 1: header, scrubber, carousel/field-log all render as on
    # main; no "Best in landscape" banner; console stays silent.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            expect(page.locator(".app-header")).to_be_visible()
            expect(page.locator(".scrubber")).to_be_visible()
            expect(page.locator(".stat-strip")).to_be_visible()
            expect(page.locator("#field-log-panel")).to_be_visible()
            # .portrait-banner always carries the "is-visible" class when not
            # dismissed (web/app.js:1084) — actual visibility is CSS-driven
            # (display:none outside the mobile media query, style.css:326/360).
            # Check computed visibility, not DOM presence.
            expect(page.locator(".portrait-banner")).to_be_hidden()
            assert console_messages == []

            browser.close()


def test_desktop_playback_advances_and_cinematic_fires_on_roll(tmp_path):
    # §0.5 step 2: clicking play flips the button and advances the playhead;
    # a roll cinematic fires when a roll is reached under on-roll behavior
    # "cinematic" — reuses the same #play-pause + #scrubber-playhead +
    # .sky-camera contract test_web_app_integration.py's pause/cinematic
    # tests already exercise, not a reinvented one.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _read_visualization_facts(site)
        first_roll_word = _first_fixture_roll_word(facts)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            expect = playwright_api.expect

            # Part A: generic playback advance, away from any roll trigger.
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": "0",
                    "bcf:playback:speed:v2": "5000",
                    "bcf:on-roll-behavior": "quick",
                },
            )
            play = page.locator("#play-pause")
            play.click()
            expect(play).to_have_attribute("aria-label", "Pause")
            page.wait_for_timeout(350)
            value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert value > 0
            assert console_messages == []
            page.close()

            # Part B: cinematic on-roll behavior locks the playhead at the
            # trigger word and renders the sky-camera cinematic.
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "3",
                    "bcf:bookmark:word_position": str(first_roll_word),
                    "bcf:playback:speed:v2": "5000",
                    "bcf:on-roll-behavior": "cinematic",
                },
            )
            page.locator("#play-pause").click()
            page.wait_for_timeout(350)
            assert int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow")) == first_roll_word
            assert page.locator(".sky-camera").count() == 1
            assert console_messages == []
            page.close()

            browser.close()


def test_desktop_carousel_focuses_last_fixture_roll_via_scrub(tmp_path):
    # §0.5 step 3, adapted: scrub to "the last roll in the fixture dataset"
    # (not "roll #47" — the synthetic tiny-default package has a small roll
    # count; see this file's module docstring). Clicking a .roll-marker
    # calls setWordPos(roll.word_position) directly (web/app.js
    # renderRollTrack), so the last marker scrubs exactly to the last roll;
    # the resulting carousel card (constellation or unresolved, depending on
    # whether that roll has a constellation) carries .is-active.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            markers = page.locator(".roll-marker")
            expect(markers.first).to_be_visible()
            markers.last.click()

            active_card = page.locator(".carousel-strip .is-active")
            expect(active_card).to_have_count(1)
            expect(active_card).to_be_visible()
            assert console_messages == []

            browser.close()


def test_desktop_details_mode_renders_full_roll_log(tmp_path):
    # §0.5 step 4: toggling Details mode renders the full roll log table,
    # one row per fixture roll.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts = _read_visualization_facts(site)
        expected_rows = _total_fixture_rolls(facts)

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            page.locator("#mode-detail").click()
            expect(page.locator("#mode-detail")).to_have_class(re.compile(r"\bis-active\b"))
            expect(page.locator(".detail")).to_be_visible()
            expect(page.locator("#detail-roll-log-panel")).to_be_visible()
            expect(page.locator("#detail-roll-log-body tr")).to_have_count(expected_rows)
            assert console_messages == []

            browser.close()
