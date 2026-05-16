from __future__ import annotations

import re
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


def test_web_app_loads_scrubber_against_synthetic_runtime_package(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            expect(page.locator("#scrubber-container")).to_be_visible()
            expect(page.locator("#track-chapters .chap-tick")).to_have_count(3)
            expect(page.locator("#track-rolls .roll-dot")).to_have_count(2)
            expect(page.locator("#track-rolls .roll-skip-marker")).to_have_count(1)

            browser.close()


def test_web_app_opens_selected_chapter_details_from_chapter_tick(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            page.locator("#track-chapters .chap-tick[data-chapter-num='2']").click()

            detail = page.locator("#chapter-detail-panel")
            expect(detail).to_be_visible()
            expect(detail.locator("#this-chapter-meta")).to_contain_text("Synthetic Chapter Two")
            expect(detail.locator("#this-chapter-perks")).to_contain_text("Synthetic Toolkit")
            expect(page.locator("#constellation-bars")).to_contain_text("Toolkits")

            browser.close()


def test_web_app_package_selector_switches_to_non_default_package(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/"), wait_until="networkidle")

            expect = playwright_api.expect
            selector = page.locator("#data-package-select")
            expect(selector).to_be_visible()
            selector.select_option("tiny-alt")
            expect(page).to_have_url(re.compile(r"[?&]dataPackage=tiny-alt(?:&|$)"))

            browser.close()


def test_web_app_package_selector_removes_query_for_default_package(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-alt"), wait_until="networkidle")

            expect = playwright_api.expect
            selector = page.locator("#data-package-select")
            expect(selector).to_be_visible()
            selector.select_option("tiny-default")
            expect(page).to_have_url(re.compile(r"/web/?$"))

            browser.close()


def test_web_app_invalid_requested_package_falls_back_to_derived_runtime(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=missing"), wait_until="networkidle")

            expect = playwright_api.expect
            expect(page.locator("#scrubber-container")).to_be_visible()
            expect(page.locator("#track-chapters .chap-tick")).to_have_count(3)
            expect(page.locator("#load-error")).to_have_count(0)

            browser.close()


def test_web_app_required_document_error_uses_load_error_panel(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        broken_chapter_facts = site.root / "data/packages/tiny-default/chapter_facts.json"
        broken_chapter_facts.write_text('{"schema_version": 999, "chapters": []}\n')
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            error = page.locator("#load-error")
            expect(error).to_be_visible()
            expect(error).to_contain_text("Failed to load data")
            expect(error).to_contain_text("Unsupported chapter_facts schema_version")

            browser.close()


def test_web_app_theme_toggle_cycles_and_persists_theme_preference(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            toggle = page.locator("#theme-toggle")
            expect(toggle).to_have_attribute("data-theme-pref", "auto")

            toggle.click()
            expect(toggle).to_have_attribute("data-theme-pref", "light")
            expect(page.locator("html")).to_have_attribute("data-theme", "light")
            assert page.evaluate("localStorage.getItem('bcf:theme')") == "light"

            toggle.click()
            expect(toggle).to_have_attribute("data-theme-pref", "dark")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            assert page.evaluate("localStorage.getItem('bcf:theme')") == "dark"

            toggle.click()
            expect(toggle).to_have_attribute("data-theme-pref", "auto")
            expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")
            assert page.evaluate("localStorage.getItem('bcf:theme')") is None

            browser.close()


def test_web_app_zoom_controls_update_timeline_zoom_state(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            zoom = page.locator("#timeline-zoom")
            readout = page.locator("#zoom-readout")
            stack = page.locator("#track-stack")

            expect(zoom).to_have_value("1")
            expect(readout).to_have_text("1×")
            expect(stack).to_have_attribute("data-zoom-detail", "exact")

            page.locator("#zoom-out").click()
            expect(zoom).to_have_value("0.9")
            expect(readout).to_have_text("0.9×")
            assert page.evaluate("localStorage.getItem('bcf:timeline:zoom')") == "0.9"

            page.locator("#zoom-fit").click()
            expect(readout).to_have_text("fit")
            assert page.evaluate("Number(localStorage.getItem('bcf:timeline:zoom'))") < 0.1

            page.locator("#zoom-in").click()
            expect(readout).not_to_have_text("fit")

            browser.close()


def test_web_app_scrubber_keyboard_moves_clamps_and_saves_bookmark(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            playhead = page.locator("#scrubber-playhead")
            playhead.focus()
            expect(playhead).to_have_attribute("aria-valuenow", "3000")
            expect(page.locator("#readout-state")).to_have_text("pre-roll")

            page.keyboard.press("ArrowRight")
            expect(playhead).to_have_attribute("aria-valuenow", "5000")
            expect(page.locator("#readout-words")).to_contain_text("2,000 / 10,000")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "2000"

            page.keyboard.press("Home")
            expect(playhead).to_have_attribute("aria-valuenow", "0")
            expect(page.locator("#readout-state")).to_have_text("pre-roll")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "-3000"

            page.keyboard.press("End")
            expect(playhead).to_have_attribute("aria-valuenow", "13000")
            expect(page.locator("#readout-words")).to_contain_text("10,000 / 10,000")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "10000"

            page.keyboard.press("ArrowRight")
            expect(playhead).to_have_attribute("aria-valuenow", "13000")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "10000"

            browser.close()


def test_web_app_bookmark_restores_and_reset_returns_to_preroll(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")
            page.evaluate("localStorage.setItem('bcf:bookmark:word_position', '7000')")
            page.reload(wait_until="networkidle")

            expect = playwright_api.expect
            expect(page.locator("#scrubber-playhead")).to_have_attribute("aria-valuenow", "10000")
            expect(page.locator("#readout-words")).to_contain_text("7,000 / 10,000")

            page.locator("#reset-bookmark").click()
            expect(page.locator("#scrubber-playhead")).to_have_attribute("aria-valuenow", "0")
            expect(page.locator("#readout-state")).to_have_text("pre-roll")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "-3000"

            browser.close()


def test_web_app_scrubber_pointer_drag_updates_word_position(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            box = page.locator("#track-stack").bounding_box()
            assert box is not None
            y = box["y"] + box["height"] / 2
            start_x = box["x"] + box["width"] * 0.25
            end_x = box["x"] + box["width"] * 0.62

            page.mouse.move(start_x, y)
            page.mouse.down()
            page.mouse.move(end_x, y, steps=4)
            page.mouse.up()

            playhead = page.locator("#scrubber-playhead")
            expect(playhead).not_to_have_attribute("aria-valuenow", "3000")
            value = int(playhead.get_attribute("aria-valuenow"))
            assert 7000 <= value <= 9000
            expect(page.locator("#readout-words")).to_contain_text(" / 10,000 words")
            assert 4000 <= int(page.evaluate("localStorage.getItem('bcf:bookmark:word_position')")) <= 6000
            assert page.evaluate("document.body.style.userSelect") == ""

            browser.close()


def test_web_app_playback_toggles_state_advances_and_persists_speed(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            speed = page.locator("#playback-speed")
            speed.select_option("100")
            assert page.evaluate("localStorage.getItem('bcf:playback:speed:v2')") == "100"

            play = page.locator("#play-pause")
            play.click()
            expect(play).to_have_attribute("aria-label", "Pause")
            expect(play).to_have_class(re.compile(r"\bplaying\b"))
            expect(page.locator("#readout-state")).to_have_text("playing")
            expect(page.locator("#scrubber-playhead")).not_to_have_attribute("aria-valuenow", "3000")

            play.click()
            expect(play).to_have_attribute("aria-label", "Play")
            expect(play).not_to_have_class(re.compile(r"\bplaying\b"))

            page.reload(wait_until="networkidle")
            expect(page.locator("#playback-speed")).to_have_value("100")

            browser.close()


def test_web_app_playback_from_story_end_resets_before_playing(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            playhead = page.locator("#scrubber-playhead")
            playhead.focus()
            page.keyboard.press("End")
            expect(playhead).to_have_attribute("aria-valuenow", "13000")

            page.locator("#playback-speed").select_option("1")
            page.locator("#play-pause").click()

            expect(page.locator("#play-pause")).to_have_attribute("aria-label", "Pause")
            expect(playhead).not_to_have_attribute("aria-valuenow", "13000")
            assert int(playhead.get_attribute("aria-valuenow")) < 4000

            page.locator("#play-pause").click()
            browser.close()


def test_web_app_current_position_panels_update_and_clear_selected_chapter(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            expect(page.locator("#readout-state")).to_have_text("pre-roll")
            expect(page.locator("#stat-chapters")).to_have_text("0")
            expect(page.locator("#stat-words")).to_have_text("0")
            expect(page.locator("#constellation-bars")).to_contain_text("No constellations opened yet.")
            expect(page.locator("#recent-perks")).to_contain_text("—")

            page.locator("#track-chapters .chap-tick[data-chapter-num='2']").click()

            detail = page.locator("#chapter-detail-panel")
            expect(detail).to_be_visible()
            expect(page.locator("#readout-chapter")).to_have_text("ch 2")
            expect(page.locator("#stat-chapters")).to_have_text("2")
            expect(page.locator("#stat-words")).to_have_text("3k")
            expect(page.locator("#stat-perks-paid")).to_have_text("1")
            expect(page.locator("#stat-rolls-hits")).to_have_text("1")
            expect(page.locator("#constellation-bars")).to_contain_text("Toolkits")
            expect(page.locator("#recent-perks")).to_contain_text("Synthetic Toolkit")
            expect(detail.locator("#this-chapter-meta")).to_contain_text("Synthetic Chapter Two")

            page.locator("#chapter-detail-close").click()
            expect(detail).to_be_hidden()

            page.locator("#track-chapters .chap-tick[data-chapter-num='2']").click()
            expect(detail).to_be_visible()
            page.locator("#scrubber-playhead").focus()
            page.keyboard.press("End")
            expect(page.locator("#readout-chapter")).to_have_text("—")
            expect(detail).to_be_hidden()

            browser.close()


def test_web_app_roll_tooltip_shows_fixture_roll_details_on_hover(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            page.locator("#track-rolls .roll-dot").first.hover()
            tooltip = page.locator("#roll-tooltip")
            expect(tooltip).to_be_visible()
            expect(tooltip).to_contain_text("Synthetic Toolkit")
            expect(tooltip).to_contain_text("outcome hit")
            expect(tooltip).to_contain_text("constellation Toolkits")
            expect(tooltip).to_contain_text("cost 100 CP")

            page.mouse.move(0, 0)
            expect(tooltip).to_be_hidden()

            browser.close()


def test_web_app_roll_tooltip_touch_pin_and_outside_click_hide(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            dot = page.locator("#track-rolls .roll-dot").first()
            box = dot.bounding_box()
            assert box is not None
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2

            dot.dispatch_event(
                "pointerdown",
                {
                    "pointerId": 7,
                    "pointerType": "touch",
                    "clientX": x,
                    "clientY": y,
                    "isPrimary": True,
                },
            )
            page.dispatch_event(
                "body",
                "pointerup",
                {
                    "pointerId": 7,
                    "pointerType": "touch",
                    "clientX": x,
                    "clientY": y,
                    "isPrimary": True,
                },
            )

            tooltip = page.locator("#roll-tooltip")
            expect(tooltip).to_be_visible()
            expect(dot).to_have_class(re.compile(r"\bis-pinned\b"))

            page.mouse.click(1, 1)

            expect(tooltip).to_be_hidden()
            expect(dot).not_to_have_class(re.compile(r"\bis-pinned\b"))

            browser.close()


def test_web_app_renders_rich_track_semantics_from_runtime_facts(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/chapter_facts.json"
        facts = json.loads(facts_path.read_text())
        facts["chapters"][0]["sections"] = [
            {
                "section_index": 1,
                "header": "Joe opening",
                "word_count": 1200,
                "pov_character": "Joe",
                "marker_kind": "pov",
                "classification": "story",
                "classification_confidence": "manual",
                "counts_for_cp": True,
            },
            {
                "section_index": 2,
                "header": "Amy sidebar",
                "word_count": 1800,
                "pov_character": "Amy",
                "marker_kind": "pov",
                "classification": "joe_not_on_screen",
                "classification_confidence": "manual",
                "counts_for_cp": False,
            },
        ]
        facts["shadow_periods"] = [
            {
                "trigger_chapter_num": "2",
                "trigger_perk_name": "Synthetic Toolkit",
                "trigger_perk_cost": 100,
                "shadow_end_chapter_num": "2",
                "shadow_end_word_position_epub": 6200,
                "shadow_word_length": 800,
            }
        ]
        facts["chapters"][2]["rolls"] = [
            {
                "roll_number": 4,
                "global_roll_number": 4,
                "outcome": "hit",
                "constellation": "Magic",
                "predicted_word_position_epub": 7200,
                "display_word_position_epub": 7200,
                "available_cp": 300,
                "purchased_perk_cost_total": 300,
                "purchased_perks": [
                    {"name": "Binary A", "cost": 100, "constellation": "Magic", "free": False},
                    {"name": "Binary B", "cost": 200, "constellation": "Magic", "free": False},
                ],
                "free_perks": [],
            },
            {
                "roll_number": 5,
                "global_roll_number": 5,
                "outcome": "hit",
                "constellation": "Crafting",
                "predicted_word_position_epub": 7600,
                "display_word_position_epub": 7600,
                "available_cp": 600,
                "purchased_perk_cost_total": 600,
                "purchased_perks": [
                    {"name": "Tri A", "cost": 100, "constellation": "Crafting", "free": False},
                    {"name": "Tri B", "cost": 200, "constellation": "Crafting", "free": False},
                    {"name": "Tri C", "cost": 300, "constellation": "Crafting", "free": False},
                ],
                "free_perks": [],
            },
            {
                "roll_number": 6,
                "global_roll_number": 6,
                "outcome": "hit",
                "constellation": "Toolkits",
                "predicted_word_position_epub": 8000,
                "display_word_position_epub": 8000,
                "available_cp": 100,
                "purchased_perk_cost_total": 100,
                "purchased_perks": [
                    {"name": "Free Anchor", "cost": 100, "constellation": "Toolkits", "free": False},
                ],
                "free_perks": [
                    {"name": "Free Sibling", "cost": 0, "constellation": "Knowledge", "free": True},
                ],
            },
            {
                "roll_number": 7,
                "global_roll_number": 7,
                "outcome": "hit",
                "evidence_kind": "untracked_acquisition",
                "constellation": "Vehicles",
                "predicted_word_position_epub": 8400,
                "display_word_position_epub": 8400,
                "available_cp": 0,
                "purchased_perk_cost_total": 0,
                "purchased_perks": [],
                "free_perks": [],
            },
            {
                "roll_number": 8,
                "global_roll_number": 8,
                "outcome": "unknown",
                "constellation": None,
                "predicted_word_position_epub": 8800,
                "display_word_position_epub": 8800,
                "available_cp": 0,
                "purchased_perk_cost_total": 0,
                "purchased_perks": [],
                "free_perks": [],
            },
            {
                "roll_number": 9,
                "global_roll_number": 9,
                "outcome": "hit",
                "constellation": "Quality",
                "predicted_word_position_epub": None,
                "display_word_position_epub": None,
                "available_cp": 100,
                "purchased_perk_cost_total": 100,
                "purchased_perks": [
                    {"name": "Fallback Placed", "cost": 100, "constellation": "Quality", "free": False},
                ],
                "free_perks": [],
            },
        ]
        facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            pov_segments = page.locator("#track-pov .pov-segment")
            expect(pov_segments).to_have_count(4)
            expect(pov_segments.nth(0)).to_have_class(re.compile(r"\bcp-earning\b"))
            expect(pov_segments.nth(1)).to_have_class(re.compile(r"\bnon-cp\b"))
            expect(pov_segments.nth(1)).to_have_attribute("title", re.compile("Amy sidebar.*joe_not_on_screen"))

            expect(page.locator("#track-rolls .shadow-bar")).to_have_count(1)
            expect(page.locator("#track-rolls .shadow-bar")).to_have_attribute("title", re.compile("100 CP shadow"))
            expect(page.locator("#track-rolls .roll-skip-marker")).to_have_count(1)

            expect(page.locator("#track-rolls .roll-dot.marker-binary")).to_have_count(1)
            expect(page.locator("#track-rolls .roll-dot.marker-trinary")).to_have_count(1)
            expect(page.locator("#track-rolls .roll-dot.marker-single-free .star-companion")).to_have_count(1)
            expect(page.locator("#track-rolls .roll-dot.marker-single-untracked .star-untracked-ring")).to_have_count(1)
            expect(page.locator("#track-rolls .roll-dot.unknown.marker-miss")).to_have_count(1)

            fallback_pos = page.locator("#track-rolls .roll-dot[data-roll-number='9']").evaluate(
                "node => node._wordPos"
            )
            assert fallback_pos == 8500

            browser.close()


def test_web_app_hides_sky_section_when_optional_wireframes_are_absent(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default&sky=1"), wait_until="networkidle")

            expect = playwright_api.expect
            sky = page.locator("#sky-section")
            expect(sky).to_be_hidden()
            expect(sky).to_have_attribute("hidden", "")

            browser.close()


def test_web_app_shows_sky_section_when_optional_wireframes_are_available(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path, include_wireframes=True) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default&sky=1"), wait_until="networkidle")

            expect = playwright_api.expect
            sky = page.locator("#sky-section")
            expect(sky).to_be_visible()
            expect(page.locator("#sky-canvas")).to_be_visible()
            expect(page.locator("#sky-hud-title")).to_contain_text("The Forge sky")

            page.locator("#track-chapters .chap-tick[data-chapter-num='2']").click()
            expect(page.locator("#sky-focus-readout")).to_contain_text("Toolkits")

            browser.close()


def test_web_app_sky_controls_toggle_persist_and_show_active_roll_focus(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path, include_wireframes=True) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default&sky=1"), wait_until="networkidle")

            expect = playwright_api.expect
            focus = page.locator("#sky-focus-toggle")
            art = page.locator("#sky-art-toggle")
            lines = page.locator("#sky-wire-toggle")
            labels = page.locator("#sky-label-toggle")
            rotate = page.locator("#sky-rotate-toggle")

            expect(focus).to_have_attribute("aria-pressed", "false")
            expect(art).to_have_attribute("aria-pressed", "true")
            expect(lines).to_have_attribute("aria-pressed", "true")
            expect(labels).to_have_attribute("aria-pressed", "true")
            expect(rotate).to_have_attribute("aria-pressed", "true")

            focus.click()
            art.click()
            lines.click()
            labels.click()
            rotate.click()

            expect(focus).to_have_attribute("aria-pressed", "true")
            expect(art).to_have_attribute("aria-pressed", "false")
            expect(lines).to_have_attribute("aria-pressed", "false")
            expect(labels).to_have_attribute("aria-pressed", "false")
            expect(rotate).to_have_attribute("aria-pressed", "false")
            assert page.evaluate("JSON.parse(localStorage.getItem('bcf:sky:prefs:v1'))") == {
                "art": False,
                "focus": True,
                "labels": False,
                "rotate": False,
                "wireframes": False,
            }

            page.locator("#track-chapters .chap-tick[data-chapter-num='2']").click()
            expect(page.locator("#sky-hud-kicker")).to_contain_text("Roll 1 - HIT")
            expect(page.locator("#sky-hud-title")).to_contain_text("Synthetic Toolkit")
            expect(page.locator("#sky-focus-readout")).to_contain_text("Toolkits")
            expect(page.locator("#sky-grab-readout")).to_contain_text("100 CP grab exactly covers 100 CP")

            page.reload(wait_until="networkidle")
            expect(page.locator("#sky-focus-toggle")).to_have_attribute("aria-pressed", "true")
            expect(page.locator("#sky-art-toggle")).to_have_attribute("aria-pressed", "false")
            expect(page.locator("#sky-wire-toggle")).to_have_attribute("aria-pressed", "false")
            expect(page.locator("#sky-label-toggle")).to_have_attribute("aria-pressed", "false")
            expect(page.locator("#sky-rotate-toggle")).to_have_attribute("aria-pressed", "false")

            browser.close()


def test_web_app_bad_optional_wireframes_disable_sky_without_breaking_scrubber(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path, include_wireframes=True) as site:
        bad_wireframes = (
            site.root
            / "data/packages/tiny-default/constellation_wireframes.json"
        )
        bad_wireframes.write_text('{"schema_version": 999}\n')
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default&sky=1"), wait_until="networkidle")

            expect = playwright_api.expect
            expect(page.locator("#scrubber-container")).to_be_visible()
            expect(page.locator("#track-chapters .chap-tick")).to_have_count(3)
            expect(page.locator("#sky-section")).to_be_hidden()
            expect(page.locator("#load-error")).to_have_count(0)

            browser.close()
