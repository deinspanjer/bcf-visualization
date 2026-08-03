"""Playwright proofs for the repo-root landing page (04-03-PLAN.md).

Protected behaviors:
- MOBX-02: the landing page's meta row (title chip + author credit + `?`
  help button) sits above the Survey letter, never inside it; the letter
  itself, its subject line, and the existing nav stay byte-identical.
- The `?` control opens a native <dialog> containing a condensed
  credit-and-help block whose three source links are copied verbatim from
  web/app.js's STORY_LINKS constant (FA-MOBX-06 — compared at test time,
  never retyped from memory).
- Degraded states (04-UI-SPEC.md "UI Considerations" / FA-MOBX-02): no-JS
  hides the `?` control entirely from the accessibility tree; an
  unsupported <dialog> fails silently; the dialog fits a 320px viewport
  with the chip wrapping rather than clipping; focus returns to the `?`
  button on close via both the CTA and Escape.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.helpers.web_runtime_site import staged_web_runtime_site

DESKTOP_VIEWPORT = {"width": 900, "height": 800}
NARROW_VIEWPORT = {"width": 320, "height": 700}

STORY_LINK_LABELS = ["SV", "FF", "AO3"]

# The Survey letter, subject line, and nav — asserted verbatim so any
# accidental edit to the locked prose fails loudly (MOBX-02's explicit
# "letter stays verbatim" constraint).
LETTER_PARAGRAPHS = [
    "Aisha,",
    "Regarding your recent complaint about how difficult it is to understand "
    'what exactly Joe is talking about when he discusses the "constellations" '
    'of his "Forge" and how it "grabs perks," I have performed a new '
    "in-depth analysis of all recorded power acquisitions to date and "
    "rendered them in an interactive visualization that I hope will provide "
    "valuable insight for you.",
    "Similar to digital audio workstation software, the scrubber will allow "
    "you to review the power progression to your desired level of detail, "
    "with links to various recordings of what Joe and other relevant "
    "individuals were doing at that time.",
    "Please let me know if you observe any inaccuracies or have ideas on "
    "ways to provide additional analysis.",
    "- Survey",
]
SUBJECT_TEXT = "Re: Joe's power progression visualization"


def _story_links_from_app_js() -> list[str]:
    """Read the live STORY_LINKS hrefs out of web/app.js at test time.

    FA-MOBX-06: the dialog's three hrefs are two independent hardcoded
    copies of the same URLs. Comparing against a hardcoded expectation here
    would defeat the point of the guard — read the actual source instead.
    """
    app_js = Path(__file__).resolve().parents[1] / "web" / "app.js"
    text = app_js.read_text()
    match = re.search(r"const STORY_LINKS = \[(.*?)\];", text, re.S)
    assert match is not None, "web/app.js's STORY_LINKS constant was not found"
    return re.findall(r'href:\s*"([^"]+)"', match.group(1))


def _chromium_browser_or_skip(playwright, playwright_api):
    try:
        return playwright.chromium.launch()
    except playwright_api.Error as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        raise


def _landing_page_with_console_capture(
    browser,
    site,
    *,
    viewport=None,
    java_script_enabled=True,
):
    page = browser.new_page(
        viewport=viewport or DESKTOP_VIEWPORT,
        java_script_enabled=java_script_enabled,
    )
    messages: list[str] = []
    page.on(
        "console",
        lambda msg: messages.append(f"{msg.type}: {msg.text}") if msg.type in {"error", "pageerror"} else None,
    )
    page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
    page.goto(site.url_for("/"), wait_until="load" if not java_script_enabled else "networkidle")
    return page, messages


# --- Task 1: happy-path coverage --------------------------------------------


def test_landing_page_meta_row_shows_title_chip_and_author_credit_above_letter(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            assert page.locator(".landing-title-chip").text_content().strip() == "Brockton's Celestial Forge"
            assert page.locator(".landing-author-credit").text_content().strip() == "by LordRoustabout"

            class_names = page.eval_on_selector_all(
                ".message-panel > *",
                "els => els.map(el => el.className || el.tagName)",
            )
            meta_index = next(i for i, c in enumerate(class_names) if "landing-meta-row" in c)
            letter_index = next(i for i, c in enumerate(class_names) if c == "letter")
            assert meta_index < letter_index

            assert messages == []
            browser.close()


def test_landing_page_help_button_is_44px_with_accessible_name_and_keyboard_reachable(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            btn = page.get_by_role("button", name="Help")
            box = btn.bounding_box()
            assert box is not None
            assert box["width"] >= 44
            assert box["height"] >= 44

            btn.focus()
            assert page.evaluate("document.activeElement.classList.contains('landing-help-btn')") is True

            assert messages == []
            browser.close()


def test_landing_page_help_button_opens_modal_dialog(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.click(".landing-help-btn")
            assert page.evaluate("document.getElementById('landing-help-dialog').open") is True
            assert page.locator("#landing-help-dialog").get_attribute("aria-label") == "About & help"

            assert messages == []
            browser.close()


def test_landing_page_dialog_contains_credit_and_help_content(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.click(".landing-help-btn")
            dialog_text = page.locator("#landing-help-dialog").inner_text()

            assert "Brockton's Celestial Forge" in dialog_text
            assert "LordRoustabout" in dialog_text
            for label in STORY_LINK_LABELS:
                assert label in dialog_text
            assert "once you open the visualization" in dialog_text
            # .landing-dialog-cta applies text-transform:uppercase, which
            # inner_text() reflects as rendered text — compare case-insensitively.
            assert "got it" in dialog_text.lower()

            assert messages == []
            browser.close()


def test_landing_page_dialog_external_links_are_safe_and_match_app_js(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    expected_hrefs = _story_links_from_app_js()

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.click(".landing-help-btn")
            attrs = page.eval_on_selector_all(
                "#landing-help-dialog a",
                "els => els.map(el => ({href: el.getAttribute('href'), "
                "target: el.getAttribute('target'), rel: el.getAttribute('rel')}))",
            )
            assert len(attrs) == 3
            assert [a["href"] for a in attrs] == expected_hrefs
            for a in attrs:
                assert a["target"] == "_blank"
                assert a["rel"] == "noopener noreferrer"

            assert messages == []
            browser.close()


def test_landing_page_letter_subject_and_nav_are_verbatim(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            paragraphs = page.eval_on_selector_all(".letter p", "els => els.map(el => el.textContent)")
            assert paragraphs == LETTER_PARAGRAPHS
            assert page.locator(".subject").text_content() == SUBJECT_TEXT
            assert page.locator("a.primary-link").text_content() == "Open visualization"
            assert page.locator("a.primary-link").get_attribute("href") == "./web/"
            assert page.locator("a.secondary-link").text_content() == "View source"
            assert (
                page.locator("a.secondary-link").get_attribute("href")
                == "https://github.com/deinspanjer/bcf-visualization"
            )

            assert messages == []
            browser.close()


def test_landing_page_open_visualization_link_resolves_to_staged_app(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            with page.expect_navigation():
                page.click("a.primary-link")

            assert "/web/" in page.url
            assert page.locator("#root").count() == 1

            assert messages == []
            browser.close()


def test_landing_page_dialog_close_via_cta_returns_focus_to_help_button(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.click(".landing-help-btn")
            page.click(".landing-dialog-cta")
            assert page.evaluate("document.getElementById('landing-help-dialog').open") is False
            assert page.evaluate("document.activeElement.classList.contains('landing-help-btn')") is True

            assert messages == []
            browser.close()


def test_landing_page_loads_with_zero_console_errors(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            assert messages == []
            browser.close()


# --- Task 2: degraded-state backstops ---------------------------------------


def test_landing_page_no_js_hides_help_button_but_letter_and_nav_survive(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            expect = playwright_api.expect
            page, messages = _landing_page_with_console_capture(browser, site, java_script_enabled=False)

            btn = page.locator(".landing-help-btn")
            expect(btn).to_be_hidden()
            display = page.evaluate("getComputedStyle(document.querySelector('.landing-help-btn')).display")
            assert display == "none"

            expect(page.locator(".letter")).to_be_visible()
            expect(page.locator("a.primary-link")).to_be_visible()
            assert page.locator("a.primary-link").get_attribute("href") == "./web/"

            assert messages == []
            browser.close()


def test_landing_page_dialog_unsupported_fails_silently(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.evaluate("document.getElementById('landing-help-dialog').showModal = undefined")
            page.click(".landing-help-btn")

            assert page.evaluate("document.getElementById('landing-help-dialog').open") is False
            assert messages == []
            browser.close()


def test_landing_page_dialog_fits_320px_viewport_and_chip_wraps_not_clips(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site, viewport=NARROW_VIEWPORT)

            page.click(".landing-help-btn")
            box = page.locator("#landing-help-dialog").bounding_box()
            assert box is not None
            assert box["x"] >= 0
            assert box["x"] + box["width"] <= 320

            chip_metrics = page.eval_on_selector(
                ".landing-title-chip",
                "el => ({scrollWidth: el.scrollWidth, clientWidth: el.clientWidth})",
            )
            assert chip_metrics["scrollWidth"] <= chip_metrics["clientWidth"]

            assert messages == []
            browser.close()


def test_landing_page_dialog_close_via_cta_returns_focus_backstop(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site, viewport=NARROW_VIEWPORT)

            page.click(".landing-help-btn")
            page.click(".landing-dialog-cta")
            assert page.evaluate("document.activeElement.classList.contains('landing-help-btn')") is True

            assert messages == []
            browser.close()


def test_landing_page_dialog_close_via_escape_returns_focus(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")

    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, messages = _landing_page_with_console_capture(browser, site)

            page.click(".landing-help-btn")
            page.keyboard.press("Escape")
            assert page.evaluate("document.getElementById('landing-help-dialog').open") is False
            assert page.evaluate("document.activeElement.classList.contains('landing-help-btn')") is True

            assert messages == []
            browser.close()
