---
phase: 03-landscape-layout
plan: 03
subsystem: ui
tags: [vanilla-js, mobile-ux, css, playwright, rotation, surface-stack]

# Dependency graph
requires:
  - phase: 03-landscape-layout (plan 01)
    provides: renderMobileLandscape()/renderMobileSkyRegion(), the D-33 sky-scoped Settings/About/Help mount already wired by construction, app.mobileRailWidthLayout (declared, unwritten)
  - phase: 03-landscape-layout (plan 02)
    provides: attachMobileGestures() (D-34), revealMobileChrome()/resetMobileChromeHideTimer() (the D-28..D-31 auto-hide primitives Task 2 calls on landscape arrival), the widened non-desktop gesture-attach/focus-trap render() guard (Pitfall 3), app.mobileRailWidthLayout now written by the ResizeObserver
provides:
  - Landscape's Settings/About/Help surfaces proven to dismiss on backdrop tap (including over the sidebar), the opening control a second press, and the mobile back gesture, with keyboard focus trapped both directions and a balanced history sentinel throughout (MOBL-04)
  - The landscape dock's Settings/About buttons kept reachable above the flyout backdrop via a z-index fix mirroring portrait's .mobile-dock-transport precedent — the backdrop no longer silently intercepts a second dock-button press
  - onLayoutMaybeChanged()'s landscape-arrival handling (D-31: reveal chrome + start the idle timer after render(); Pitfall 6: reset the rail-width layout guard before render())
  - The CI half of D-23's two-pronged rotation proof — every MOBL-03 field (speed, mode, onRoll, timeline zoom, tapToPause, haptics, playing, word position) individually verified across a portrait<->landscape round trip, the Phase 1 boundary matrix, a mid-drag rotation abort, an open-surface-survives-rotation case, and the no-cross-fade className-stability check
affects: [03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Landscape-only component z-index elevated above the flyout backdrop (.mobile-dock-grid, z-index 10) — the exact .mobile-dock-transport precedent Phase 2 established in portrait, applied to the new sidebar's Settings/About buttons so a second dock-button press is never silently intercepted by the backdrop underneath it"
    - "Landscape flyout bound switched from a fixed max-height (sized for portrait's ~506px sky) to a top+bottom-anchored box (12px each, matching the cinema-scrub's own inset) — scoped by the `.mobile-app-landscape` class rather than a nested `@media (orientation: landscape)` block, per the file's existing convention that landscape-only component rules never need the orientation query since their class names only ever mount in landscape DOM"
    - "Rotation arrival ordering: app.mobileRailWidthLayout reset happens BEFORE render() (so the new layout's default width applies to the very first frame); revealMobileChrome()/resetMobileChromeHideTimer() run AFTER render() (the cinema-scrub DOM ref they need doesn't exist until cachePlaybackDomRefs() has run inside it)"

key-files:
  created: []
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_landscape.py

key-decisions:
  - "Task 1's 'give the flyout body the same internal-scroll-plus-static-footer treatment as Help' is implemented as internal-scroll only (the base rule's existing overflow-y:auto), not a footer split — Settings/About have no separate footer element in their markup and Task 1 explicitly forbids touching that JavaScript; the Help overlay already has its own header/body/CTA structure from Phase 2 and needed no change"
  - "The landscape dock's Settings/About buttons (.mobile-dock-grid) needed a z-index fix (position:relative; z-index:10, above the backdrop's 8) that the plan's action text didn't spell out explicitly but the acceptance criteria required — without it, a second press on the opening control (or pressing About while Settings is open) would hit the backdrop instead of the real button and close the surface entirely rather than toggle/swap it. Task 1's own guidance ('if a landscape behavior appears broken, the cause is a CSS anchor or a stacking order') covers this exactly; verified by writing the test WITHOUT force=True, which fails outright if the backdrop still intercepts"
  - "test_rotation_preserves_state sets the Settings speed rung to 0.5x (2500 words/sec), not a faster rung — tiny-default's 10000-word story would otherwise finish and auto-pause partway through the test's several hundred-ms waits, breaking the 'playing state unchanged across rotation' assertion the same way Plan 02's tests had to guard against"
  - "history.length is NOT used to prove a surface closed (raw window.history.length never shrinks via back() — normal joint-session-history behavior, per the existing portrait test's own documented reasoning); window.history.state is used for that instead, and window.history.length is used only to prove rotation itself adds no new entries while a surface stays open"
  - "The rotating-at-word-0-on-no-rolls backstop (FA-MOBL-03) is implemented as an extension to Plan 01's existing test_landscape_field_log_zero_and_empty_states rather than a new test function, per the plan's own 'or extend' option"

patterns-established: []

requirements-completed: [MOBL-03, MOBL-04]

coverage:
  - id: D1
    description: "Landscape Settings/About/Help dismiss via backdrop tap (including over the sidebar), the opening control pressed a second time, and the mobile back gesture — all three routes proven, with a balanced history sentinel throughout and the sentinel reused (not stacked) across a Settings<->About swap"
    requirement: "MOBL-04"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_surface_stack"
        status: pass
    human_judgment: false
  - id: D2
    description: "Keyboard focus is trapped inside an open landscape flyout in both directions (Tab wraps at the last focusable, Shift+Tab wraps at the first) and the open panel never overlaps a control-dock button"
    requirement: "MOBL-04"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_surface_stack"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every external anchor in the landscape About flyout carries rel=noopener (T-03-03), and the Help overlay opens from the top-cluster button, staying within the sky's own height with a reachable CTA (D-19)"
    requirement: "MOBL-04"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_surface_stack"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every MOBL-03 field (speed, mode, onRoll, timeline zoom, tapToPause, haptics, playing, word position) survives a portrait->landscape->portrait rotation, asserted individually; no cross-fade is built (className is byte-identical immediately after the swap and 500ms later)"
    requirement: "MOBL-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_rotation_preserves_state"
        status: pass
    human_judgment: false
  - id: D5
    description: "Landscape arrival shows chrome visible immediately and starts the D-31 idle window (hidden 4600ms later if playback continues untouched)"
    requirement: "MOBL-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_rotation_preserves_state"
        status: pass
    human_judgment: false
  - id: D6
    description: "The Phase 1 boundary matrix holds at the exact routing edges: 1100x900 stays desktop, 900x1100 is mobile portrait, 900x600 is mobile landscape"
    requirement: "MOBL-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_rotation_at_routing_boundaries"
        status: pass
    human_judgment: false
  - id: D7
    description: "An open surface survives rotation with a balanced history sentinel; a mid-drag rotation aborts the in-flight scrub cleanly and a fresh drag in the new layout is monotonic from its first sample; rotating away from landscape while the idle timer is armed leaves no stale timer behind"
    requirement: "MOBL-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_rotation_with_surface_open_and_mid_drag"
        status: pass
    human_judgment: false
  - id: D8
    description: "Rotating into landscape at word position 0 on a zero-roll story throws nothing and renders the empty field log and zero-marker scrub in the freshly-mounted landscape DOM (FA-MOBL-03 backstop)"
    requirement: "MOBL-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_field_log_zero_and_empty_states"
        status: pass
    human_judgment: false
  - id: D9
    description: "On real iOS Safari, the OS edge-swipe-back gesture dismisses an open landscape flyout, and the landscape safe-area contract clears the notch on whichever side it lands after rotation — both device-only backstops"
    verification: []
    human_judgment: true
    rationale: "WebKit's popstate-on-swipe-back behavior and env(safe-area-inset-*) both resolve to trivial/zero values in Chromium/emulation (per RESEARCH Pitfall 5 and the UI-SPEC safe-area table's own backstop note) — only confirmable on a real notched iPhone in both rotation directions, which is plan 04's Phase C device-pass gate, not this plan's automated suite"

duration: 55min
completed: 2026-08-02
status: complete
---

# Phase 3 Plan 3: Rotation hand-off and the landscape surface stack Summary

**Closed the phase's hard gate (MOBL-03 rotation state preservation, D-31 landscape-arrival chrome/timer handling) and proved MOBL-04's reused surface stack in landscape — including a real dock-button z-index bug the backdrop's full-root coverage introduced — with four new Playwright tests and one small production edit to onLayoutMaybeChanged().**

## Performance

- **Duration:** ~55 min
- **Completed:** 2026-08-02
- **Tasks:** 2 (Task 1: landscape surface stack CSS + proof; Task 2: rotation hand-off JS + proof)
- **Files modified:** 3 (web/app.js, web/mobile.css, tests/test_mobile_landscape.py)

## Accomplishments
- Confirmed by direct read (per the plan's own instruction) that `openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus`/the popstate listener are already fully layout-agnostic and needed zero JavaScript changes — D-33's "reuse the D-19 arrangement wholesale" held exactly as designed.
- Found and fixed a real stacking-order bug the plan's CSS-only framing anticipated but didn't spell out: `.mobile-flyout-backdrop`'s full-root coverage (needed so a tap anywhere in the sidebar dismisses the flyout) silently intercepted the SECOND press on the Settings/About dock buttons, since `.mobile-dock-grid` had no z-index elevating it above the backdrop the way portrait's `.mobile-dock-transport` already does. Fixed with the identical precedent (`position:relative; z-index:10`); the test proves it with a non-forced Playwright click, which fails outright if the backdrop still wins.
- Switched the landscape flyout's height bound from a fixed `max-height` (sized against portrait's ~506px sky) to a top+bottom-anchored box matching the cinema-scrub's own 12px inset — correct at every in-scope landscape height without a hand-tuned pixel guess, and still falls back to the existing `overflow-y: auto` if content ever exceeds it.
- `onLayoutMaybeChanged()` gained its one new production behavior this phase: a landscape-arrival branch (D-31) that reveals chrome and starts the idle timer AFTER `render()` (the DOM ref it needs doesn't exist before), plus a `app.mobileRailWidthLayout = null` reset BEFORE `render()` (RESEARCH Pitfall 6) so the new layout's own default rail width applies to the very first frame instead of inheriting a stale measurement. No `setTimeout`, debounce, or pointer-state check was added anywhere in the function — confirmed by the plan's own manual read-back verification item.
- Every field MOBL-03 names (speed, mode, on-roll behavior, timeline zoom, tap-to-pause, haptics, playing, word position) is asserted individually — not as one aggregate — across a full portrait→landscape→portrait round trip, set through the real Settings UI (never a direct localStorage write).
- Verified, without rebuilding, the two behaviors the plan explicitly said were already correct by construction: an open surface survives rotation with its history sentinel intact (D-21), and a mid-drag rotation cleanly tears the old rail's listeners down via the existing structural-render teardown, leaving the next drag in the new layout monotonic from its first sample (D-22).
- Full mobile+desktop suite: 50 passed (44 baseline + 6 new/extended landscape tests — `test_landscape_surface_stack`, `test_rotation_preserves_state`, `test_rotation_at_routing_boundaries`, `test_rotation_with_surface_open_and_mid_drag`, plus one extension case in `test_landscape_field_log_zero_and_empty_states` and one Task-1-added assertion group), zero regressions. The three frozen files (`tests/test_mobile_plumbing.py`, `web/mobile-gestures.js`, `web/style.css`) are byte-identical (`git diff --exit-code` clean).

## Task Commits

1. **Task 1: Landscape surface stack — backdrop, focus trap, back gesture, and the landscape flyout anchor** - `5ccaf3e` (feat)
2. **Task 2: Rotation hand-off — state preservation, landscape arrival, mid-drag abort, and the boundary matrix** - `92eb58b` (feat)

Both tasks are `tdd="true"`; tests were authored and run alongside each task's implementation (this repo's Python/pytest+Playwright suite doesn't separate RED/GREEN into distinct commits the way a unit-test-first JS suite would — each task commit carries its implementation and its own new/extended tests together, verified green before committing). Task 1's test file changes were isolated from Task 2's (which land in the same file) via a manual patch split so each commit carries exactly one task's scope.

## Files Created/Modified
- `web/mobile.css` - `.mobile-dock-grid` gains `position:relative; z-index:10` (the landscape analogue of `.mobile-dock-transport`'s existing precedent); `.mobile-app-landscape .mobile-flyout` gains a top+bottom-anchored bound (12px each) replacing the inherited fixed `max-height`
- `web/app.js` - `onLayoutMaybeChanged()`: `app.mobileRailWidthLayout = null` reset before `render()`; a landscape-arrival branch after `render()` calling `revealMobileChrome()`/`resetMobileChromeHideTimer()`
- `tests/test_mobile_landscape.py` - `PHONE_PORTRAIT` constant added; `test_landscape_surface_stack` (new); `test_rotation_preserves_state`, `test_rotation_at_routing_boundaries`, `test_rotation_with_surface_open_and_mid_drag` (new); `test_landscape_field_log_zero_and_empty_states` extended with a rotation-at-word-0-on-no-rolls case

## Decisions Made
- The flyout's "internal-scroll-plus-static-footer" treatment the plan's prose invokes is implemented as internal-scroll only (the base rule's `overflow-y: auto`), since Settings/About have no separate footer element and Task 1 forbids touching that JavaScript — the Help overlay already has its own header/body/CTA split from Phase 2 and needed no landscape-specific change.
- Added a `.mobile-dock-grid` z-index fix the plan's action text didn't literally spell out but the acceptance criteria required (a second dock-button press, and the Settings→About swap, must hit the real button, not the backdrop underneath it) — squarely inside Task 1's own "if a landscape behavior appears broken, the cause is a CSS anchor or a stacking order" framing.
- `test_rotation_preserves_state` sets the Settings speed rung to 0.5× rather than a faster one, so tiny-default's 10000-word story survives the several hundred-ms waits the test holds playback open across without finishing and auto-pausing mid-assertion — the same class of fix Plan 02's timing tests already needed.
- `window.history.state` (not raw `window.history.length`) proves a surface fully closed, matching the existing portrait test's own documented reasoning that `history.length` never shrinks via `back()`; `window.history.length` is used only to prove rotation itself adds no entries while a surface stays open.
- The word-position-0/no-rolls rotation backstop (FA-MOBL-03) was added as an extension to Plan 01's existing `test_landscape_field_log_zero_and_empty_states`, per the plan's own "or extend" option, rather than a fifth new test function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `.mobile-dock-grid` had no z-index, so the flyout backdrop silently intercepted a second dock-button press**
- **Found during:** Task 1, while writing `test_landscape_surface_stack`'s opener-toggle/About-swap assertions
- **Issue:** The plan's D-33 design correctly puts the backdrop's full-root coverage above the sidebar (so a tap anywhere in the sidebar dismisses the flyout), but nothing elevated `.mobile-dock-grid` above that backdrop the way portrait's `.mobile-dock-transport` already is — so pressing the Settings dock button a second time (to close it) or pressing About while Settings was open would hit the backdrop instead of the real button, closing the surface entirely rather than toggling/swapping it.
- **Fix:** Added `position: relative; z-index: 10` to `.mobile-dock-grid`, the exact precedent `.mobile-dock-transport` already carries in portrait, with a comment cross-referencing why.
- **Files modified:** web/mobile.css
- **Verification:** `test_landscape_surface_stack`'s opener-toggle-shut and Settings→About-swap assertions use non-forced Playwright clicks, which fail outright if the backdrop still intercepts — both pass.
- **Committed in:** `5ccaf3e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** CSS-only fix, no production JS touched. No scope creep — this is exactly the class of finding Task 1's own text anticipated ("the cause is a CSS anchor or a stacking order, not the stack itself").

## Known Stubs

None — this plan proves existing, already-real data paths (rotation state on `app.*`, the surface stack's real DOM) rather than introducing any new rendering surface.

## Issues Encountered
None beyond the auto-fixed CSS issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 04 owns: `COVERAGE.md`, the §6 acceptance-evidence table, the freeze proof, and the Phase C gate review with Dre — including the mandatory real-device iOS Safari pass this plan explicitly could not close (D6/D9 above: the back-gesture-in-landscape re-exercise per RESEARCH Pitfall 5, and the landscape safe-area contract in both rotation directions per the UI-SPEC's own backstop note).
- No blockers. `onLayoutMaybeChanged()`, the landscape surface stack, and the full MOBL-01..04 automated suite are all green and ready for the device-pass gate.

---
*Phase: 03-landscape-layout*
*Completed: 2026-08-02*
