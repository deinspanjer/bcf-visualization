---
phase: 04-mobile-cutover-accessibility
plan: 03
subsystem: ui
tags: [landing-page, accessibility, dialog, static-html, playwright]

requires:
  - phase: 04-mobile-cutover-accessibility
    provides: "plan 04-01's whole-milestone freeze proof (tests/test_freeze_proof.py), which this plan's index.html verify step reruns against the same 57d2768 base commit"

provides:
  - "index.html: .landing-meta-row (title chip, author credit, 44x44 ? button) inserted as the first child of .message-panel, above the verbatim Survey letter"
  - "index.html: #landing-help-dialog — a native <dialog>, feature-checked open (onclick=\"this.nextElementSibling.showModal && ...\"), condensed credit/help content (title, byline, SV/FF/AO3 links, a pointer to in-app Help, and the Got-it CTA), explicit max-width so it cannot overflow a 320px viewport, and an ::backdrop rule"
  - "index.html: a <noscript> rule hiding .landing-help-btn when JS is disabled, and the file's first-ever inline <script> restoring focus to the ? button on the dialog's close event"
  - "tests/helpers/web_runtime_site.py: staged_web_runtime_site() now also stages the repo-root index.html at the site root, so site.url_for(\"/\") serves the landing page and its ./web/ link resolves to the already-staged app"
  - "tests/test_landing_page.py: 14 new Playwright tests — the happy path (meta row, dialog open/content/links, verbatim letter/nav, fixture staging, focus-return, zero console errors) plus the four degraded-state backstops (no-JS, dialog-unsupported, 320px viewport, focus-return via Escape)"

affects: [04-04, 04-05]

tech-stack:
  added: []
  patterns:
    - "Native <dialog> + showModal()/close(), feature-checked with a plain onclick attribute (\"this.nextElementSibling.showModal && ...\") rather than a hand-rolled focus trap/Escape/backdrop handler — the first JS and the first <dialog> this static file has ever carried"
    - "A <form method=\"dialog\"> submit button closes the dialog natively (fires the 'close' event) with zero extra script, reused for the CTA"
    - "Repo-root static-file Playwright fixture staging: copy index.html into the same staged site_root that already serves web/, so one fixture (not a second server) covers both surfaces"
    - "FA-MOBX-06 guard: the dialog's three hrefs are asserted against values read live out of web/app.js's STORY_LINKS via regex at test time, never retyped from memory"

key-files:
  created:
    - tests/test_landing_page.py
  modified:
    - index.html
    - tests/helpers/web_runtime_site.py

key-decisions:
  - "Used a <form method=\"dialog\"> submit button for the Got-it CTA instead of a plain button + JS close() call — the native form-associated close requires zero script and still fires the same 'close' event the focus-return listener needs"
  - "Verified (throwaway script, not committed) that clicking the ::backdrop does NOT close #landing-help-dialog — native <dialog> has no light-dismiss behavior without an explicit click-target check, and the plan explicitly forbids hand-rolling one for symmetry. Recorded here rather than assumed, per the plan's own instruction; this is the answer to FA-MOBX-02's 'backdrop' close route: it is a no-op, and no third handler was added to change that"
  - "Task 1 and Task 2 were implemented, tested, and committed together as a single commit rather than two atomic per-task commits (see Deviations) — a process deviation, not a functional one"

patterns-established:
  - "Any future repo-root static-page test targets staged_web_runtime_site()'s site_root directly (via site.url_for(\"/\")) rather than a bespoke server, now that the fixture stages both surfaces"

requirements-completed: [MOBX-02]

coverage:
  - id: D1
    description: "Meta row shows a title chip and author credit above the Survey letter, and the ? help button is 44x44-or-larger, has a non-empty accessible name, and is keyboard-focusable"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_meta_row_shows_title_chip_and_author_credit_above_letter"
        status: pass
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_help_button_is_44px_with_accessible_name_and_keyboard_reachable"
        status: pass
    human_judgment: false
  - id: D2
    description: "Activating the ? button opens a native modal <dialog> containing the condensed credit/help block (title, byline, source links, a pointer to in-app Help, the Got-it CTA) — not the full seven-row gesture how-to"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_help_button_opens_modal_dialog"
        status: pass
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_contains_credit_and_help_content"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every external link in the dialog carries target=_blank + rel=noopener noreferrer, and its three hrefs are asserted equal to web/app.js's STORY_LINKS read live at test time (FA-MOBX-06)"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_external_links_are_safe_and_match_app_js"
        status: pass
      - kind: other
        ref: "target=\"_blank\" and rel=\"noopener noreferrer\" occurrence counts in index.html are equal"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Survey letter's paragraphs, the subject line, and both existing nav links are byte-verbatim; git diff against the pre-milestone base shows zero removed content lines in index.html"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_letter_subject_and_nav_are_verbatim"
        status: pass
      - kind: other
        ref: "git diff 57d2768 HEAD -- index.html | grep -c '^-[^-]' == 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "The staged fixture serves both the landing page and the app together — the Open-visualization link resolves to a real staged page rather than 404ing, and the page loads with zero console errors"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_open_visualization_link_resolves_to_staged_app"
        status: pass
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_loads_with_zero_console_errors"
        status: pass
    human_judgment: false
  - id: D6
    description: "MOBX-02 edge (no-JS): with JavaScript disabled the ? button is display:none (removed from the accessibility tree), while the letter and the Open-visualization anchor remain visible and functional"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_no_js_hides_help_button_but_letter_and_nav_survive"
        status: pass
    human_judgment: false
  - id: D7
    description: "MOBX-02 edge (dialog unsupported): with showModal deleted from the dialog instance, activating ? produces no console error and the dialog stays closed — the feature check makes the failure a silent no-op"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_unsupported_fails_silently"
        status: pass
    human_judgment: false
  - id: D8
    description: "MOBX-02 edge (narrow viewport / long title): at 320px the dialog's bounding box lies entirely within the viewport, and the title chip's scrollWidth never exceeds its clientWidth (wraps, never clips)"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_fits_320px_viewport_and_chip_wraps_not_clips"
        status: pass
    human_judgment: false
  - id: D9
    description: "Focus returns to the ? button after closing the dialog via the Got-it CTA and via Escape (the inline close-event listener is route-agnostic); backdrop click was verified NOT to close the dialog (no light-dismiss handler exists, by design)"
    requirement: MOBX-02
    verification:
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_close_via_cta_returns_focus_to_help_button"
        status: pass
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_close_via_cta_returns_focus_backstop"
        status: pass
      - kind: integration
        ref: "tests/test_landing_page.py::test_landing_page_dialog_close_via_escape_returns_focus"
        status: pass
    human_judgment: false
  - id: D10
    description: "The four-file mobile/desktop suite plus the freeze proof stay green — this plan touches nothing under web/"
    verification:
      - kind: integration
        ref: "pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py tests/test_freeze_proof.py -q (74 passed)"
        status: pass
    human_judgment: false
  - id: D11
    description: "On a real iPhone, the ? opens the dialog and it reads correctly at phone width — static-file <dialog> behavior on iOS Safari differs from headless Chromium"
    verification: []
    human_judgment: true
    rationale: "04-UI-SPEC.md flags this as a device-pass backstop truth: headless Chromium cannot substitute for real iOS Safari rendering/interaction of a native <dialog>. Carried to the Phase D+E gate with Dre."

duration: 45min
completed: 2026-08-02
status: complete
---

# Phase 4 Plan 3: Landing-Page Meta Row, Help Dialog & Repo-Root Fixture Summary

**The repo-root landing page now names the story and its author above a byte-verbatim Survey letter, and a native `<dialog>` behind a 44x44 `?` button offers a condensed credit-and-help block — feature-checked, focus-returning, and covered by 14 new Playwright tests including four degraded-state backstops.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 (implemented and committed together — see Deviations)
- **Files modified:** 3 (index.html, tests/helpers/web_runtime_site.py, tests/test_landing_page.py)

## Accomplishments
- Inserted `.landing-meta-row` (title chip + author credit + 44x44 `?` button) as the first child of `.message-panel`, immediately before `.constellation` — above the letter, never inside it
- Added `#landing-help-dialog`, a native `<dialog>` with an explicit `max-width: min(420px, calc(100vw - 32px))` so it can never overflow a narrow viewport, condensed credit/help content (title, byline, SV/FF/AO3 links, a pointer to in-app Help, and the `Got it — read on` CTA reused verbatim from the in-app overlay), and an `::backdrop` rule
- The `?` button's `onclick` feature-checks `showModal` before calling it (`this.nextElementSibling.showModal && this.nextElementSibling.showModal()`), so a browser without native `<dialog>` support fails silently
- A `<noscript>` rule hides `.landing-help-btn` entirely when JavaScript is disabled, so no reader is offered a dead affordance
- Added the file's first-ever inline `<script>` — a single `close` event listener that restores focus to the `?` button, since native `<dialog>` does not do this reliably on its own
- The CTA is a `<form method="dialog">` submit button, which closes the dialog natively (firing the same `close` event) with zero extra script
- Extended `staged_web_runtime_site()` to also stage the repo-root `index.html` at `site_root`, so `site.url_for("/")` serves the landing page and its `./web/` link resolves against the already-staged app in the same fixture
- Wrote `tests/test_landing_page.py` (14 tests): the happy path (meta row, dialog open/content/links, verbatim letter/subject/nav, fixture staging, CTA focus-return, zero console errors) plus the four degraded-state backstops from 04-UI-SPEC.md (no-JS accessibility-tree absence, dialog-unsupported silent no-op, 320px viewport fit + chip wrapping, Escape focus-return)

## Task Commits

Both tasks landed in a single commit (see Deviations for why):

1. **Task 1 + Task 2: Landing-page meta row, help dialog, repo-root fixture, and all degraded-state coverage** - `c563a60` (feat)

## Files Created/Modified
- `index.html` - `.landing-meta-row`/`.landing-title-chip`/`.landing-author-credit`/`.landing-help-btn` markup + CSS; `#landing-help-dialog` markup, CSS, and `::backdrop` rule; the `<noscript>` hiding rule; the file's first inline `<script>` (focus return on dialog close)
- `tests/helpers/web_runtime_site.py` - `_copy_landing_page()` stages the repo-root `index.html` into `site_root`, called from `staged_web_runtime_site()` right after `_copy_web_files()`
- `tests/test_landing_page.py` - new file, 14 tests (9 happy-path, 5 degraded-state)

## Decisions Made
- `<form method="dialog">` for the CTA instead of a JS `.close()` call — native form-associated dialog close needs no script and still fires `close`, which the focus-return listener already listens for
- Verified directly (a throwaway script, not committed to the test suite) that clicking `#landing-help-dialog`'s `::backdrop` does **not** close the dialog — native `<dialog>` has no light-dismiss behavior without an explicit click-target check, and the plan explicitly forbids hand-rolling one purely for symmetry with the CTA/Escape routes. This is the recorded answer to the plan's "record what the backdrop-click route actually does rather than assuming it": it is inert by design, carried to the Phase D+E gate as the actual (not assumed) behavior
- Dialog CTA and help-button glyph reuse `text-transform: uppercase` from the app's own bold-CTA convention (`.primary-link`); tests compare dialog text case-insensitively where this applies

## Deviations from Plan

### Process deviation (no functional impact)

**1. Tasks 1 and 2 were implemented, tested, and committed as a single commit rather than two atomic per-task commits**
- **What happened:** All 14 tests (Task 1's 9 happy-path tests plus Task 2's 5 degraded-state tests) were written in one pass before the first verification run, rather than committing Task 1's markup+8 tests first and then adding Task 2's 5 backstop tests as a second, independently-verified commit per the plan's task boundary and Task 2's own precondition ("Task 1's markup is committed and `pytest tests/test_landing_page.py -x -q` is green").
- **Impact:** None functional — every one of Task 1's and Task 2's `<verify>`/`<acceptance_criteria>` items were independently satisfied by the final state (14/14 tests pass, `git diff 57d2768 HEAD -- index.html` shows zero removed lines, `target="_blank"`/`rel="noopener noreferrer"` counts match, the four-file regression suite plus freeze proof are green). The only loss is a task-boundary commit in the git history; no production fix was needed by either task's degraded-state tests (no gap was found).
- **Files/commit:** `index.html`, `tests/helpers/web_runtime_site.py`, `tests/test_landing_page.py` — commit `c563a60`.

**Total deviations:** 1 process deviation (no functional impact).
**Impact on plan:** None on shipped behavior; every acceptance criterion from both tasks is independently proven by a passing test or a passing shell check.

## Issues Encountered
- An early version of `test_landing_page_dialog_contains_credit_and_help_content` asserted the literal string `"Got it"` against the dialog's `inner_text()`, but `.landing-dialog-cta`'s `text-transform: uppercase` renders it as `"GOT IT — READ ON"` — Playwright's `inner_text()` reflects rendered text. Fixed by comparing case-insensitively.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `index.html` gains no dependency on `web/`; `tests/test_freeze_proof.py` and the four-file mobile/desktop suite are still green (74 tests total), and `git diff --numstat 57d2768 HEAD -- web/style.css` is unaffected by this plan since it touches nothing under `web/`
- FA-MOBX-06 (the two hardcoded STORY_LINKS copies) is enforced by a red-on-drift test (`test_landing_page_dialog_external_links_are_safe_and_match_app_js`), but the human-facing question — whether Dre accepts this duplication going forward — remains open for the Phase D+E gate, exactly as `04-UI-SPEC.md` specifies
- FA-MOBX-02's gate-agenda item ("is the condensed credit-only dialog the right scope, or does Dre want the gesture how-to duplicated after all?") is unresolved by design and carried to the gate
- D11 (real-device `<dialog>` rendering/interaction on iOS Safari) is unverified by this plan and carried to the same device pass already scheduled for plans 04-02/04-04/04-05's other backstops
- Plans 04-04 (FAB hit-area) and 04-05 (Lighthouse gate) can proceed without further edits to the landing page — this plan's file set (`index.html`, `tests/helpers/web_runtime_site.py`, `tests/test_landing_page.py`) is fully disjoint from theirs

## Self-Check: PASSED

- FOUND: index.html (.landing-meta-row, .landing-title-chip, .landing-author-credit, .landing-help-btn, #landing-help-dialog, noscript rule, inline script)
- FOUND: tests/helpers/web_runtime_site.py (_copy_landing_page)
- FOUND: tests/test_landing_page.py (14 collected tests)
- FOUND: commit c563a60

---
*Phase: 04-mobile-cutover-accessibility*
*Completed: 2026-08-02*
