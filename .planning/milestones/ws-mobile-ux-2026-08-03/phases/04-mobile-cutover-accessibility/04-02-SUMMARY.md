---
phase: 04-mobile-cutover-accessibility
plan: 02
subsystem: ui
tags: [accessibility, aria-live, keyboard, mobile, playwright]

requires:
  - phase: 04-mobile-cutover-accessibility
    provides: "plan 04-01's whole-milestone freeze proof (tests/test_freeze_proof.py) and the deleted rotate-to-landscape banner, which this plan's precondition checks before touching web/app.js again"

provides:
  - "web/app.js: one visually-hidden aria-live=\"polite\" .mobile-live-region, mounted on both mobile layouts and never on desktop, announcing outcome-aware roll text on exactly five user-caused trigger kinds (double-tap, swipe-step, rail-scrub release, keyboard arrow-step, keyboard Home)"
  - "web/app.js: mobileRollAnnouncement(roll)/announceMobileRoll() — the outcome-aware string builder and clear-then-set writer, reusing rollMarkerModel/paidRollPerks/perkDisplayLabel/rollTotalCost with no second classifier"
  - "web/app.js: a layoutMode-gated early branch inside the ONE existing window keydown listener — ArrowRight/ArrowLeft step one roll via the existing rollStepFrom(), Home mirrors onDoubleTap's live-edge snap, `?` toggles Help via the existing openMobileSurface(\"help\")"
  - "web/mobile.css: .mobile-live-region — the UI-SPEC's locked visually-hidden hiding technique, applied verbatim"
  - "16 new Playwright tests (14 in tests/test_mobile_portrait.py, 2 in tests/test_mobile_landscape.py) covering presence/hiding, desktop absence, the swipe/tap/playback silence contract, special-character text safety, single-announcement-at-release, empty and repeat-landing edges, keyboard stepping/adjacency, the `?` toggle, and desktop's numerically-unchanged stepping"

affects: [04-03, 04-04, 04-05]

tech-stack:
  added: []
  patterns:
    - "Visually-hidden ARIA live region: position:absolute + 1x1px + overflow:hidden + clip-path:inset(50%) + white-space:nowrap + margin:-1px + zero border/padding — the standard sr-only technique, locked verbatim from 04-UI-SPEC.md; never display:none/visibility:hidden/aria-hidden/zero-size, all of which remove the node from the accessibility tree while still passing DOM-presence assertions"
    - "Double synchronous textContent write (clear, then set) to force a screen-reader re-announcement even when landing twice on the identical roll — assistive tech fires on a text MUTATION, not on a value comparison"
    - "MutationObserver callback-invocation counting (not raw MutationRecord counting) as the Playwright-side proof that one announceMobileRoll() call == one screen-reader announcement, regardless of how many DOM operations its two textContent writes produce underneath"

key-files:
  created: []
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_portrait.py
    - tests/test_mobile_landscape.py

key-decisions:
  - "Used window.history.state (not history.length) to prove the `?` key's toggle leaves no orphaned sentinel — window.history.length never shrinks via history.back() (empirically verified this session), matching the exact caveat already recorded in this file's own test_surface_stack_focus_trap_and_back_gesture"
  - "Split the single plan's two file-overlapping tasks into two truly atomic commits by temporarily removing Task 2's keyboard branch/tests, committing Task 1 standalone-green, then re-applying Task 2's exact content and committing it separately — rather than one combined commit for both tasks"
  - "Test fixtures already in scope (dense-rolls, tiny-default) fully cover the phrasing table's miss/single-paid-perk/special-character rows; the multi-grab (\"and N more\") branch is implemented per the locked template but has no fixture with 2+ purchased_perks in one roll, so it ships untested by this plan (files_modified excludes tests/helpers/web_runtime_site.py) — same status as the free-only fallback and the FA-MOBX-05 untracked-acquisition row, both explicitly zero-instance/untested-by-design per 04-UI-SPEC.md"

patterns-established:
  - "Live-region trigger wiring lives immediately after the pre-existing setWordPos(...) call at each of the three gesture sites and the two keyboard sites — never in the rAF playback tier and never in a plain-tap or per-move scrub callback"

requirements-completed: [MOBX-03]

coverage:
  - id: D1
    description: "One visually-hidden aria-live=\"polite\" region mounts on both mobile layouts (never desktop), hidden with the UI-SPEC's locked 1px-clipped technique — verified as a non-zero, non-display:none, non-visibility:hidden box"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_mounts_hidden_on_mobile_only"
        status: pass
    human_judgment: false
  - id: D2
    description: "Announcements fire on exactly five user-caused trigger kinds (double-tap, swipe-step, rail-scrub release, keyboard arrow-step, keyboard Home) and stay silent on plain tap, per-move scrub, and free playback across multiple roll crossings"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_announces_on_swipe_and_silent_on_tap"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_rail_scrub_announces_once_at_release"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_silent_during_free_playback"
        status: pass
    human_judgment: false
  - id: D3
    description: "Announcement phrasing branches on outcome (miss checked first) before touching perk fields, reusing rollMarkerModel/paidRollPerks/perkDisplayLabel/rollTotalCost and the existing indexOf-plus-one roll numbering; text reaches the DOM via textContent only, never innerHTML, including special characters"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_renders_special_characters_as_text"
        status: pass
      - kind: other
        ref: "grep -c 'innerHTML' web/app.js == 0; grep -c 'aria-live' web/app.js == 1; grep -c 'rollMarkerModel' web/app.js >= 2"
        status: pass
    human_judgment: false
  - id: D4
    description: "MOBX-03 edges: empty (no announcement before the first roll), ordering (repeat landing re-announces via a real mutation), and adjacency (repeated arrow presses hold at the list ends and re-announce every press)"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_empty_when_no_roll_before_playhead"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_live_region_reannounces_repeat_landing"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_arrow_adjacency_holds_at_list_ends"
        status: pass
    human_judgment: false
  - id: D5
    description: "Mobile keyboard equivalents: ArrowRight/ArrowLeft step one roll via the existing rollStepFrom(); Home snaps to the live edge and resumes (not word 0); `?` toggles Help through the existing openMobileSurface(\"help\"); Space already worked and needed no code change — all inside the ONE existing keydown listener, with the editable-field guard still shielding every mobile key"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_arrows_step_one_roll_and_announce"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_home_snaps_to_live_edge_and_resumes"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_question_mark_toggles_help"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_space_toggles_playback_on_every_layout"
        status: pass
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_mobile_keyboard_respects_editable_guard"
        status: pass
      - kind: other
        ref: "grep -c 'window.addEventListener(\"keydown\"' web/app.js == 1"
        status: pass
    human_judgment: false
  - id: D6
    description: "Desktop keyboard behavior at >=1100px stays numerically unchanged: ArrowRight steps exactly 10000 words, Shift+ArrowRight exactly 2000, Home lands on word 0, and the live region never mounts on the desktop path"
    requirement: MOBX-03
    verification:
      - kind: integration
        ref: "tests/test_mobile_portrait.py::test_desktop_keyboard_stepping_unaffected_by_mobile_branch"
        status: pass
      - kind: integration
        ref: "tests/test_desktop_smoke.py (full suite, unaffected)"
        status: pass
    human_judgment: false
  - id: D7
    description: "A screen reader actually SPEAKS the region on a real device, and stays silent through playback — a device-pass backstop, not automatable in a headless browser"
    verification: []
    human_judgment: true
    rationale: "04-UI-SPEC.md flags this as a backstop truth: DOM presence and computed style are assertable in Playwright, but whether VoiceOver actually announces is not — no headless browser runs a screen reader. Carried to the phase's real-device gate with Dre, per the plan's own must_haves.truths."

duration: 50min
completed: 2026-08-02
status: complete
---

# Phase 4 Plan 2: Live Region Announcements & Mobile Keyboard Equivalents Summary

**One visually-hidden aria-live region announces outcome-aware roll text on five user-caused triggers (double-tap, swipe-step, rail-scrub release, arrow-step, Home), plus a keyboard-only path (arrows/Home/`?`) added as a single early branch inside the app's one existing keydown listener — desktop stays numerically untouched.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2
- **Files modified:** 4 (web/app.js, web/mobile.css, tests/test_mobile_portrait.py, tests/test_mobile_landscape.py)

## Accomplishments
- Mounted `.mobile-live-region` (`role="status"`, `aria-live="polite"`, `aria-atomic="true"`) in `render()`'s existing non-desktop block, hidden with the UI-SPEC's locked visually-hidden property set — a non-zero 1px clipped box, never `display:none`/`visibility:hidden`/`aria-hidden`, any of which would silently remove it from the accessibility tree while still passing every DOM-presence assertion
- Wrote `mobileRollAnnouncement(roll)` — checks `rollMarkerModel(roll).isMissLike` FIRST (misses are 410/670 real rolls) before ever touching a perk field, implementing the four reachable phrasing rows (miss, single paid perk, multi-grab, free-only fallback) and leaving a one-line pointer comment for the zero-instance `untracked_acquisition` row (FA-MOBX-05) instead of inventing copy
- Wrote `announceMobileRoll()` — resolves the current roll via the existing `lastRollAtWord()`, writes nothing when none exists (silence, not a placeholder), and double-writes `textContent` (clear, then set) so a repeat landing on the same roll still re-announces
- Wired the announcement into exactly three gesture call sites (`onDoubleTap`, `onSwipeStep`, `onScrubEnd`) — never the per-move scrub callback, never the plain-tap callback, never the rAF playback tier
- Added a `layoutMode !== "desktop"` early branch inside the app's ONE existing `window.addEventListener("keydown", ...)` listener: ArrowRight/ArrowLeft step one roll via the existing `rollStepFrom()`; Home mirrors `onDoubleTap`'s body exactly (live edge, not word 0); `?` calls the existing `openMobileSurface("help")`, which already toggles closed on a second press
- Added 16 new Playwright tests (14 portrait, 2 landscape) — zero `aria-live`/keyboard assertions existed in the suite before this plan

## Task Commits

Each task was committed atomically:

1. **Task 1: The visually-hidden live region, its outcome-aware announcement, and its three gesture triggers** - `b3cbf8e` (feat)
2. **Task 2: Mobile keyboard equivalents as an early branch inside the one existing keydown handler** - `85fa86c` (feat)

_Both tasks touch `web/app.js`/the mobile test files, so they were committed as two genuinely separate, independently-green diffs: Task 2's keyboard branch and its tests were built alongside Task 1's work, then temporarily removed, Task 1 was verified standalone-green and committed, and Task 2's exact content was re-applied and committed second._

## Files Created/Modified
- `web/app.js` - `rollMarkerModel` added to the `viz-model.js` import block; `.mobile-live-region` DOM node + `app.dom.mobileLiveRegion` mounted in `render()`'s non-desktop block; `mobileRollAnnouncement()`/`announceMobileRoll()`; three gesture call sites wired; the mobile keyboard early branch inside the existing `keydown` listener
- `web/mobile.css` - `.mobile-live-region` visually-hidden rule, inside the existing single `@media` block
- `tests/test_mobile_portrait.py` - 14 new tests: live-region presence/hiding, desktop absence, swipe/tap/playback silence contract, special-character text safety, single-announcement-at-release, empty/repeat-landing edges, keyboard arrow/Home/`?`/adjacency/space/editable-guard, desktop numeric stepping
- `tests/test_mobile_landscape.py` - 2 new tests: live-region mount+announce in landscape, keyboard arrow+`?` in landscape

## Decisions Made
- `window.history.state` (not raw `history.length`) is the correct proof that the `?` key's toggle consumes its history sentinel — empirically confirmed this session that `history.length` never shrinks via `history.back()` (it only moves the navigation pointer), matching this file's own pre-existing comment on the identical point for the on-screen Settings/About/Help toggle
- Split the plan's two file-overlapping tasks into two genuinely atomic commits (see Task Commits note above) rather than accept a combined diff, so each task's own `<verify>` block could be run against a standalone, task-scoped tree before committing it
- The multi-grab ("Roll N of Total. {perk} and {k} more, {cp} CP.") and free-only-hit phrasing branches are implemented exactly per the locked template but ship untested by this plan — no fixture in scope (`tests/helpers/web_runtime_site.py` is outside this plan's `files_modified`) has a roll with 2+ purchased perks or a free-only hit; this matches the already-documented zero-live-instance status of those exact rows in `04-UI-SPEC.md`'s phrasing table

## Deviations from Plan

None - plan executed as specified. The `window.history.state` vs. `history.length` choice above is a test-design correction of the plan's own literal but empirically-inaccurate acceptance-criteria wording (browser `history.length` never shrinks via `back()`), not a change to any shipped behavior — the underlying toggle/sentinel behavior itself matches D-48 exactly, and this file already carried the identical correction for the on-screen surface toggle before this plan touched it.

## Issues Encountered
- An early version of the swipe-announcement test drove two roll-steps instead of one because a prior phase in the same test ran playback for ~600ms before the swipe, drifting the seeded word position past the intended target. Fixed by splitting the "plain taps stay silent" and "swipe announces" checks into two independent fresh page loads, matching this file's own established `fresh_page()`-per-phase idiom (documented in-test as the reason for the split).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The live region and keyboard branch are both scoped entirely to `web/app.js`/`web/mobile.css`; `web/style.css` and `web/mobile-gestures.js` remain untouched (`tests/test_freeze_proof.py` still 4/4 green, `git diff --numstat 57d2768 HEAD -- web/style.css` still exactly `0  38`)
- Plans 04-03..04-05 (landing page, FAB hit-area, Lighthouse gate) can proceed without further edits to the live region or keyboard branch — this plan closes both of MOBX-03's behavioral clauses (announcements + keyboard) that plan 04-05's Lighthouse pass will audit alongside the pre-existing tap-target/reduced-motion work
- FA-MOBX-05 (the zero-instance `untracked_acquisition` phrasing row) and RESEARCH Assumption A3 (the announcement copy itself — "Miss.", "and N more", etc.) both remain explicitly unresolved/unapproved, carried to the Phase D+E gate with Dre exactly as `04-UI-SPEC.md` specifies — this plan implements the phrasing but does not close either open item
- The device-pass backstop (does VoiceOver actually speak the region, and does it stay silent through playback on real hardware) is unverified by this plan by design — carried to the same gate

## Self-Check: PASSED

- FOUND: web/app.js (rollMarkerModel import, mobile-live-region mount, mobileRollAnnouncement/announceMobileRoll, keyboard branch)
- FOUND: web/mobile.css (.mobile-live-region rule)
- FOUND: tests/test_mobile_portrait.py (31 collected tests, 14 new)
- FOUND: tests/test_mobile_landscape.py (22 collected tests, 2 new)
- FOUND: commit b3cbf8e (Task 1)
- FOUND: commit 85fa86c (Task 2)

---
*Phase: 04-mobile-cutover-accessibility*
*Completed: 2026-08-02*
