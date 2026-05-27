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


def _main_child_classes(page):
    return page.locator(".app-main").evaluate(
        "(main) => [...main.children].map(node => node.className || node.id || node.tagName.toLowerCase())"
    )


def test_web_app_loads_preview_playthrough_without_obsolete_sky_dom(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            expect(page.locator(".app-header")).to_be_visible()
            main_children = _main_child_classes(page)
            playthrough_idx = next(i for i, class_name in enumerate(main_children) if "playthrough" in class_name)
            scrubber_idx = next(i for i, class_name in enumerate(main_children) if "scrubber" in class_name)
            assert playthrough_idx < scrubber_idx
            expect(page.locator(".scrubber.panel-cut")).to_be_visible()
            expect(page.locator(".playthrough .viewport")).to_be_visible()
            expect(page.locator(".carousel-strip")).to_have_count(1)
            expect(page.locator(".const-card").first).to_be_visible()
            expect(page.locator(".narrative")).to_be_visible()
            expect(page.locator("#mode-playthrough")).to_have_class(re.compile(r"\bis-active\b"))
            expect(page.locator(".app-header #data-package-select")).to_have_count(0)
            expect(page.locator("#playback-speed")).to_have_value("5000")
            expect(page.locator("#zoom-readout")).to_have_text("2.75×")
            assert page.locator(".scrubber-track.axis .predicted-tick").count() <= 20
            expect(page.locator(".roll-mode-switch button", has_text="cinematic")).to_have_class(
                re.compile(r"\bis-active\b")
            )
            expect(page.locator("#sky-section")).to_have_count(0)
            expect(page.locator("#sky-canvas")).to_have_count(0)
            expect(page.locator("#playthrough-unavailable")).to_have_count(0)
            assert console_messages == []

            browser.close()


def test_web_app_mode_switch_toggles_detail_and_persists(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            page.locator("#mode-detail").click()
            expect(page.locator("#mode-detail")).to_have_class(re.compile(r"\bis-active\b"))
            expect(page.locator(".detail")).to_be_visible()
            expect(page.locator("#detail-roll-log-panel")).to_be_visible()
            main_children = _main_child_classes(page)
            scrubber_idx = next(i for i, class_name in enumerate(main_children) if "scrubber" in class_name)
            controls_idx = next(i for i, class_name in enumerate(main_children) if "scrubber-controls" in class_name)
            stats_idx = next(i for i, class_name in enumerate(main_children) if "stat-strip" in class_name)
            detail_idx = next(i for i, class_name in enumerate(main_children) if class_name == "detail")
            assert scrubber_idx < controls_idx < stats_idx < detail_idx
            assert page.locator(".playthrough").count() == 0
            assert page.evaluate("localStorage.getItem('bcf:mode')") == "detail"

            page.reload(wait_until="networkidle")
            expect(page.locator("#mode-detail")).to_have_class(re.compile(r"\bis-active\b"))
            expect(page.locator(".detail")).to_be_visible()
            assert console_messages == []

            browser.close()


def test_web_app_package_selector_switches_and_default_removes_query(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site, "/web/")

            expect = playwright_api.expect
            expect(page.locator(".app-header #data-package-select")).to_have_count(0)
            page.locator("#info-toggle").click()
            selector = page.locator("#data-package-select")
            expect(selector).to_be_visible()
            selector.select_option("tiny-alt")
            expect(page).to_have_url(re.compile(r"[?&]dataPackage=tiny-alt(?:&|$)"))

            page.locator("#info-toggle").click()
            selector = page.locator("#data-package-select")
            selector.select_option("tiny-default")
            expect(page).to_have_url(re.compile(r"/web/?$"))
            assert console_messages == []

            browser.close()


def test_web_app_required_document_error_uses_load_error_panel(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        broken_bundle = site.root / "data/packages/tiny-default/visualization_facts.json"
        broken_bundle.write_text('{"schema_version": 999, "chapters": []}\n')
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(site.url_for("/web/?dataPackage=tiny-default"), wait_until="networkidle")

            expect = playwright_api.expect
            error = page.locator("#load-error")
            expect(error).to_be_visible()
            expect(error).to_contain_text("Failed to load data")
            expect(error).to_contain_text("Unsupported visualization_facts schema_version")

            browser.close()


def test_web_app_field_log_uses_quotes_and_no_log_placeholder_without_synthetic_prose(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        facts["chapters"][1]["rolls"][0]["evidence_quotes"] = [{"text": "The fixture quote line."}]
        facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "0",
                },
            )

            expect = playwright_api.expect
            page.locator(".roll-marker").first.click()
            log = page.locator("#field-log-panel")
            expect(log).to_be_visible()
            expect(log.locator("#field-log-body")).to_contain_text("The fixture quote line.")

            facts["chapters"][1]["rolls"][0]["evidence_quotes"] = []
            facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
            page.reload(wait_until="networkidle")
            page.locator(".roll-marker").first.click()
            expect(log.locator("#field-log-body")).to_contain_text("No log data")
            expect(log.locator("#field-log-body")).not_to_contain_text("Forge reached")

            page.locator("#field-log-hide").click()
            expect(log).to_have_count(0)
            expect(page.locator("#field-log-reopen")).to_be_visible()
            page.locator("#field-log-reopen").click()
            expect(page.locator("#field-log-panel")).to_be_visible()
            assert console_messages == []

            browser.close()


def test_web_app_detail_roll_log_filters_sorts_and_click_moves_playhead(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        facts["chapters"][2]["rolls"].append(
            {
                "predicted_ordinal": 4,
                "predicted_label": "P4",
                "source_ordinal": None,
                "source_label": None,
                "roll_ordinal": 4,
                "roll_label": "R4",
                "chapter_ordinal": 2,
                "chapter_label": "C2",
                "association_source": "none",
                "outcome": "hit",
                "constellation": "Magic",
                "epub_word_offset_predicted": 8200,
                "epub_word_offset_curated": 8200,
                "available_cp": 600,
                "purchased_perk_cost_total": 600,
                "purchased_perks": [
                    {"name": "Multi A", "cost": 200, "constellation": "Magic", "free": False},
                    {"name": "Multi B", "cost": 400, "constellation": "Magic", "free": False},
                ],
                "free_perks": [],
            }
        )
        facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            expect = playwright_api.expect
            page.locator("#mode-detail").click()
            page.keyboard.press("End")
            expect(page.locator("#detail-roll-log-body tr")).to_have_count(3)

            page.locator("[data-roll-filter='multi']").click()
            expect(page.locator("#detail-roll-log-body tr")).to_have_count(1)
            expect(page.locator("#detail-roll-log-body")).to_contain_text("Multi A")

            page.locator("#detail-roll-log-body tr").first.click()
            expect(page.locator("#scrubber-playhead")).to_have_attribute("aria-valuenow", "8200")
            assert console_messages == []

            browser.close()


def test_web_app_displays_canonical_epub_word_offset_for_each_roll(tmp_path):
    # The UI reads roll.epub_word_offset_predicted / epub_word_offset_curated
    # directly — no client-side CP↔EPUB derivation. This test verifies that
    # the EPUB position the bundle ships is what the scrubber, log, and
    # playhead all use.
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        facts["chapters"][1]["rolls"].append(
            {
                "predicted_ordinal": 9,
                "predicted_label": "P9",
                "source_ordinal": None,
                "source_label": None,
                "roll_ordinal": 9,
                "roll_label": "R9",
                "chapter_ordinal": 2,
                "chapter_label": "C2",
                "association_source": "none",
                "outcome": "hit",
                "constellation": "Toolkits",
                "epub_word_offset_predicted": 4000,
                "epub_word_offset_curated": 4000,
                "available_cp": 100,
                "purchased_perk_cost_total": 100,
                "purchased_perks": [
                    {"name": "Mapped CP Roll", "cost": 100, "constellation": "Toolkits", "free": False},
                ],
                "free_perks": [],
            }
        )
        facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "10000",
                    "bcf:mode": "detail",
                },
            )

            expect = playwright_api.expect
            row = page.locator("#detail-roll-log-body tr").filter(has_text="Mapped CP Roll")
            expect(row).to_be_visible()
            expect(row.locator("td").nth(2)).to_have_text("4,000")
            row.click()
            expect(page.locator("#scrubber-playhead")).to_have_attribute("aria-valuenow", "4000")
            assert console_messages == []

            browser.close()


def test_web_app_places_rolls_without_epub_offsets_inside_their_chapter(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        facts["chapters"][2]["rolls"].append(
            {
                "predicted_ordinal": None,
                "predicted_label": None,
                "source_ordinal": None,
                "source_label": None,
                "roll_ordinal": 99,
                "roll_label": "R99",
                "chapter_ordinal": 2,
                "chapter_label": "C2",
                "association_source": "none",
                "outcome": "hit",
                "constellation": "Magic",
                "word_position": 600,
                "available_cp": 600,
                "purchased_perk_cost_total": 600,
                "purchased_perks": [
                    {"name": "Late Unmapped", "cost": 600, "constellation": "Magic", "free": False},
                ],
                "free_perks": [],
            }
        )
        facts_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "0",
                    "bcf:mode": "detail",
                },
            )

            expect = playwright_api.expect
            expect(page.locator(".stat-strip")).to_contain_text("0 hits")
            page.keyboard.press("End")
            row = page.locator("#detail-roll-log-body tr").filter(has_text="Late Unmapped")
            expect(row).to_be_visible()
            expect(row.locator("td").nth(2)).to_have_text("7,600")
            row.click()
            expect(page.locator("#scrubber-playhead")).to_have_attribute("aria-valuenow", "7600")
            assert console_messages == []

            browser.close()


def test_web_app_pause_on_roll_can_resume_without_manual_scrubbing(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "1500",
                    "bcf:playback:speed:v2": "5000",
                    "bcf:on-roll-behavior": "pause",
                },
            )

            expect = playwright_api.expect
            play = page.locator("#play-pause")
            play.click()
            expect(play).to_have_attribute("aria-label", "Pause")
            page.wait_for_timeout(350)
            value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert value > 1500
            assert console_messages == []

            browser.close()


def test_web_app_playback_updates_without_structural_render_and_keeps_markers_interactive(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        first_roll_word = facts["chapters"][1]["rolls"][0]["epub_word_offset_predicted"]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "3000",
                    "bcf:playback:speed:v2": "1000",
                    "bcf:on-roll-behavior": "quick",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")

            page.locator("#play-pause").click()
            page.wait_for_timeout(350)

            value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert value > 3000
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0

            page.locator("#play-pause").click()
            page.locator(".roll-marker").first.click()
            clicked_value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert first_roll_word <= clicked_value <= first_roll_word + 250
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_web_app_detail_playback_keeps_detail_panels_in_sync(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "0",
                    "bcf:mode": "detail",
                    "bcf:playback:speed:v2": "50000",
                    "bcf:on-roll-behavior": "quick",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            page.locator("#play-pause").click()
            page.wait_for_timeout(250)

            value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert value > 7000
            assert page.locator(".chapter-meta strong").inner_text().startswith("ch 3 ")
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_web_app_detail_playback_preserves_stable_panels_until_visible_state_changes(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "3500",
                    "bcf:mode": "detail",
                    "bcf:playback:speed:v2": "1000",
                    "bcf:on-roll-behavior": "quick",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            page.locator("#detail-roll-log-panel [data-roll-filter='hit']").click()
            page.locator("#detail-roll-log-panel [data-roll-sort='cost']").click()
            page.evaluate(
                """() => {
                    window.__bcfRenderStats.structuralRenders = 0;
                    document.querySelector('#selected-chapter-panel').dataset.probe = 'stable';
                    document.querySelector('#detail-roll-log-panel table').dataset.probe = 'stable';
                }"""
            )

            page.locator("#play-pause").click()
            page.wait_for_timeout(250)

            assert page.locator("#selected-chapter-panel").get_attribute("data-probe") == "stable"
            assert page.locator("#detail-roll-log-panel table").get_attribute("data-probe") == "stable"
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_web_app_detail_playback_refreshes_when_chapter_or_filtered_roll_state_changes(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "6200",
                    "bcf:mode": "detail",
                    "bcf:playback:speed:v2": "4000",
                    "bcf:on-roll-behavior": "quick",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            page.locator("#detail-roll-log-panel [data-roll-filter='miss']").click()
            page.locator("#detail-roll-log-panel [data-roll-sort='cost']").click()
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")

            expect = playwright_api.expect
            expect(page.locator("#detail-roll-log-body tr")).to_have_count(0)
            expect(page.locator(".chapter-meta strong")).to_contain_text("ch 2")

            page.locator("#play-pause").click()
            expect(page.locator("#detail-roll-log-body tr")).to_have_count(1)
            expect(page.locator("#detail-roll-log-body")).to_contain_text("MISS")
            expect(page.locator(".chapter-meta strong")).to_contain_text("ch 3")
            assert int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow")) >= 7000
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_web_app_pause_lock_can_resume_after_switching_to_cinematic(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        first_roll_word = facts["chapters"][1]["rolls"][0]["epub_word_offset_predicted"]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": str(first_roll_word),
                    "bcf:playback:speed:v2": "5000",
                    "bcf:on-roll-behavior": "pause",
                },
            )

            page.locator(".roll-mode-switch button", has_text="cinematic").click()
            page.locator("#play-pause").click()
            page.wait_for_timeout(350)

            value = int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow"))
            assert value > first_roll_word
            assert console_messages == []

            browser.close()


def test_web_app_cinematic_focus_frames_do_not_structurally_render(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        first_roll_word = facts["chapters"][1]["rolls"][0]["epub_word_offset_predicted"]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": str(first_roll_word),
                    "bcf:playback:speed:v2": "5000",
                    "bcf:on-roll-behavior": "cinematic",
                },
                init_script="window.__bcfRenderStats = { structuralRenders: 0 };",
            )

            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            page.locator("#play-pause").click()
            page.wait_for_timeout(350)

            assert int(page.locator("#scrubber-playhead").get_attribute("aria-valuenow")) == first_roll_word
            assert page.locator(".sky-camera").count() == 1
            assert page.evaluate("window.__bcfRenderStats.structuralRenders") == 0
            assert console_messages == []

            browser.close()


def test_web_app_diffraction_markers_share_gradient_defs_across_scrubber_and_detail(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "10000",
                },
            )

            expect = playwright_api.expect
            expect(page.locator(".scrubber .roll-marker .star-wrap svg").first).to_be_visible()
            page.locator("#mode-detail").click()
            expect(page.locator("#detail-roll-log-panel .star-wrap svg").first).to_be_visible()

            marker_defs = page.evaluate(
                """() => ({
                    shared: document.querySelectorAll('#diffraction-ray-grad').length,
                    perMarker: document.querySelectorAll('.star-wrap svg defs linearGradient[id^="ray-"]').length,
                    markerGradientRefs: [...document.querySelectorAll('.star-wrap svg rect')]
                        .filter(rect => rect.getAttribute('fill') === 'url(#diffraction-ray-grad)').length,
                })"""
            )
            assert marker_defs["shared"] == 1
            assert marker_defs["perMarker"] == 0
            assert marker_defs["markerGradientRefs"] > 0
            assert console_messages == []

            browser.close()


def test_web_app_cinematic_beam_renders_without_svg_blur_filters(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        facts_path = site.root / "data/packages/tiny-default/visualization_facts.json"
        facts = json.loads(facts_path.read_text())
        cinematic_words = [
            facts["chapters"][1]["rolls"][0]["epub_word_offset_predicted"],
            facts["chapters"][2]["rolls"][0]["epub_word_offset_predicted"],
        ]

        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            for word_pos in cinematic_words:
                page, console_messages = _page_with_console_capture(
                    browser,
                    site,
                    storage={
                        "bcf:preview-port-storage-version": "2",
                        "bcf:bookmark:word_position": str(word_pos),
                        "bcf:playback:speed:v2": "5000",
                        "bcf:on-roll-behavior": "cinematic",
                    },
                )

                expect = playwright_api.expect
                page.locator("#play-pause").click()
                expect(page.locator(".cam-beam")).to_have_count(1)
                beam_blur_usage = page.evaluate(
                    """() => ({
                        filters: document.querySelectorAll('#beam-outer-blur, #beam-inner-blur').length,
                        attrs: [...document.querySelectorAll('.cam-beam [filter]')]
                            .map(node => node.getAttribute('filter')),
                    })"""
                )
                assert beam_blur_usage == {"filters": 0, "attrs": []}
                assert console_messages == []
                page.close()

            browser.close()


def test_web_app_constellation_cards_avoid_blur_filter_compositing(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(browser, site)

            filter_stack = page.evaluate(
                """() => {
                    const card = document.querySelector('.const-card');
                    const halo = card.querySelector('.halo');
                    card.style.transition = 'none';
                    card.classList.remove('is-active', 'is-flank');
                    const inactive = getComputedStyle(card).filter;
                    card.classList.add('is-active');
                    const active = getComputedStyle(card).filter;
                    card.classList.remove('is-active');
                    card.classList.add('is-flank');
                    const flank = getComputedStyle(card).filter;
                    return {
                        inactive,
                        active,
                        flank,
                        halo: getComputedStyle(halo).filter,
                    };
                }"""
            )
            assert "blur" not in filter_stack["inactive"]
            assert "blur" not in filter_stack["active"]
            assert "blur" not in filter_stack["flank"]
            assert filter_stack["halo"] == "none"
            assert console_messages == []

            browser.close()


def test_web_app_bookmark_persistence_is_throttled_and_flushes_on_lifecycle(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    bookmark_write_probe = """
        (() => {
            const originalSetItem = Storage.prototype.setItem;
            Storage.prototype.setItem = function(key, value) {
                if (key === "bcf:bookmark:word_position") {
                    window.__bookmarkWrites = window.__bookmarkWrites || [];
                    window.__bookmarkWrites.push(String(value));
                }
                return originalSetItem.apply(this, arguments);
            };
        })();
    """

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "3000",
                    "bcf:playback:speed:v2": "1000",
                    "bcf:on-roll-behavior": "quick",
                },
                init_script=bookmark_write_probe,
            )

            page.evaluate("window.__bookmarkWrites = []")
            page.locator("#play-pause").click()
            page.wait_for_timeout(650)
            frame_value = page.locator("#scrubber-playhead").get_attribute("aria-valuenow")
            writes_during_playback = page.evaluate("window.__bookmarkWrites.slice()")
            assert len(writes_during_playback) <= 2

            page.evaluate("window.__bookmarkWrites = []")
            lifecycle_flush = page.evaluate(
                """() => {
                    window.dispatchEvent(new PageTransitionEvent("pagehide"));
                    return {
                        writes: window.__bookmarkWrites.slice(),
                        stored: localStorage.getItem("bcf:bookmark:word_position"),
                    };
                }"""
            )
            assert len(lifecycle_flush["writes"]) == 1
            assert lifecycle_flush["stored"] == lifecycle_flush["writes"][0]
            assert int(lifecycle_flush["stored"]) >= int(frame_value)

            page.locator("#play-pause").click()
            page.evaluate("window.__bookmarkWrites = []")
            page.keyboard.press("ArrowRight")
            explicit_value = page.locator("#scrubber-playhead").get_attribute("aria-valuenow")
            assert page.evaluate("window.__bookmarkWrites.slice()") == [explicit_value]
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == explicit_value
            assert console_messages == []

            browser.close()


def test_web_app_keyboard_controls_move_clamp_and_ignore_text_input_focus(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser,
                site,
                storage={
                    "bcf:preview-port-storage-version": "2",
                    "bcf:bookmark:word_position": "0",
                },
            )

            expect = playwright_api.expect
            playhead = page.locator("#scrubber-playhead")
            expect(playhead).to_have_attribute("aria-valuenow", "0")

            page.locator("#timeline-zoom").focus()
            page.keyboard.press("ArrowRight")
            expect(playhead).to_have_attribute("aria-valuenow", "0")

            page.locator("#play-pause").focus()
            page.keyboard.press("ArrowRight")
            expect(playhead).to_have_attribute("aria-valuenow", "10000")
            page.keyboard.press("PageDown")
            expect(playhead).to_have_attribute("aria-valuenow", "10000")
            page.keyboard.press("Home")
            expect(playhead).to_have_attribute("aria-valuenow", "0")
            page.keyboard.press("End")
            expect(playhead).to_have_attribute("aria-valuenow", "10000")
            assert page.evaluate("localStorage.getItem('bcf:bookmark:word_position')") == "10000"
            assert console_messages == []

            browser.close()
