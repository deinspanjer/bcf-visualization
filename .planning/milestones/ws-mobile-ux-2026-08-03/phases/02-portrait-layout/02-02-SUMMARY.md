---
phase: 02-portrait-layout
plan: 02
subsystem: ui
tags: [vanilla-js, pointer-events, gesture, css, playwright]

requires:
  - phase: 02-portrait-layout
    plan: 01
    provides: "Portrait render() branch, attachMobilePortraitGestures lifecycle (mobileSkyTeardown/mobileRailTeardown slots), real sky-camera cinematic, dock/rail markup, hint row shell"
provides:
  - "Production sky gesture callbacks wired through window.attachSkyGestures: tap toggles playback (gated on tap-to-pause), double-tap snaps to the last roll at/before the playhead and resumes, swipe steps roll-by-roll, swipe-end persists the bookmark"
  - "rollStepFrom(wordPos, dir): the single roll-index-lookup semantic reused by swipe-step (derived from lastRollAtWord, not a second binary search)"
  - "app.mobileSurface guard on the gesture attach path (falsy today; Plan 02-04 wires the field) so an open overlay can never leak taps into the sky"
  - "Dock speed control: MOBILE_SPEED_RUNGS/mobileSpeedMultiplier/setMobileSpeedMultiplier cycling the four locked rungs through the existing LS_SPEED persistence path"
  - "First-run '.mobile-sky-tap-hint' affordance, mounted once per session while tap-to-pause is on"
  - ".mobile-icon-btn/.mobile-icon-btn.compact — a 44px tap-target floor with a 36x36 visual footprint via a content-box override scoped to the compact selector"
affects: [02-03-cluster-binning, 02-04-settings-flyouts]

tech-stack:
  added: []
  patterns:
    - "Gesture callbacks commit only through existing shared setters (setWordPos/togglePlayback/persistBookmarkNow) — never render() — so the incremental frame tier is the only path a gesture can touch"
    - "Control changes (speed cycle) are a sanctioned structural render; gestures are not — the dock speed button calls render() directly, unlike every sky/rail callback"
    - "Session-only affordance state (app.mobileSkyHintShown) lives on `app`, not localStorage, distinguishing a once-per-load UI cue from a durable bcf:* preference"

key-files:
  created: []
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_portrait.py

key-decisions:
  - "MOBILE_SPEED_RUNGS labels stay the UI-SPEC's canonical value strings ('0.5'/'1'/'2'/'4', matching the prototype's own Settings speed radio group convention) rather than pre-formatted display glyphs, so Plan 02-04's Settings UI can reuse the same table without a second value vocabulary; only the dock button's own label-formatting function maps '0.5' to the '½' glyph the prototype's speedLabel also renders."
  - "'.mobile-icon-btn.compact' uses box-sizing:content-box scoped to just that selector (not a project-wide override) so the UI-SPEC's literal 36x36 visual figure and the 44px tap-target floor (MOBX-03) are both satisfied by the SAME rendered element, rather than a ::before hit-area expander that would leave the element's own bounding box under 44px and fail the acceptance bar's literal bounding-box assertion."

requirements-completed: [MOBP-02]

coverage:
  - id: D1
    description: "Tap toggles playback when tap-to-pause is on and is a no-op when it's off"
    requirement: "MOBP-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_sky_gesture_contract"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_sky_tap_is_noop_when_tap_to_pause_off"
        status: pass
    human_judgment: false
  - id: D2
    description: "Double-tap snaps the playhead to the last roll at/before the current position and resumes — never the final roll"
    requirement: "MOBP-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_sky_gesture_contract"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_sky_tap_is_noop_when_tap_to_pause_off"
        status: pass
    human_judgment: false
  - id: D3
    description: "Horizontal swipe steps exactly one roll per 56px traveled, with zero structural re-renders across the gesture, and persists the bookmark on release"
    requirement: "MOBP-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_sky_gesture_contract"
        status: pass
    human_judgment: false
  - id: D4
    description: "Dock speed control cycles through the four locked rungs (½×/1×/2×/4×), writes only allow-listed desktop-select values, and the choice survives a reload"
    requirement: "MOBP-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_dock_speed_cycle_persists_and_hint_row_context"
        status: pass
    human_judgment: false
  - id: D5
    description: "Hint row right span reports zoom only above 1x and always ends with a non-empty POV name (default-POV fallback for a chapter with no explicit POV)"
    requirement: "MOBP-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_dock_speed_cycle_persists_and_hint_row_context"
        status: pass
    human_judgment: false
  - id: D6
    description: "First-run sky tap hint mounts once per session while tap-to-pause is on, never remounts after a structural re-render, and is absent entirely with tap-to-pause off; every dock-transport button clears the 44px tap-target floor at 320px width"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_dock_speed_cycle_persists_and_hint_row_context"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-26
status: complete
---

# Phase 2 Plan 2: Sky Gesture Callbacks, Dock Speed Cycle, Tap Hint Summary

**Production tap/double-tap/swipe callbacks wired through the existing attachSkyGestures contract, plus a four-rung dock speed cycle and a first-run sky tap hint — all riding the shared setState/render lifecycle Plan 02-01 proved.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-26T18:54:00-04:00
- **Completed:** 2026-07-26T19:10:20-04:00
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `attachMobilePortraitGestures()` now attaches `window.attachSkyGestures` to `.mobile-sky` with production callbacks: tap toggles playback (gated on `app.tapToPause`), double-tap snaps to `lastRollAtWord(app.wordPos)` and resumes (never the story's final roll), swipe steps one roll per 56px via the new `rollStepFrom()` helper, and swipe-end persists the bookmark.
- `rollStepFrom(wordPos, dir)` derives its index from `lastRollAtWord`'s result rather than a second binary search — the codebase now has exactly one roll-lookup semantic.
- Both the sky and rail gesture attach are guarded behind `app.mobileSurface` (falsy until Plan 02-04 wires it) so an open overlay's taps can never bubble into a pause toggle.
- None of the four gesture callbacks ever call `render()` — every commit routes through `setWordPos`/`togglePlayback`/`persistBookmarkNow`, keeping the swipe path on the incremental tier only (`structuralRenders` stays 0 across an engaged 140px drag, proven in `test_sky_gesture_contract`).
- Dock speed control: `MOBILE_SPEED_RUNGS` maps the UI-SPEC's four canonical values onto the frozen desktop `<select>`'s existing rungs; the new `.mobile-icon-btn.compact` button (`data-action="mobile-cycle-speed"`) cycles through them, wrapping, and persists through the same `LS_SPEED` path the desktop control uses.
- `.mobile-sky-tap-hint`: a first-run "tap sky to pause" pill mounted once per session (`app.mobileSkyHintShown`) while tap-to-pause is on, with the prototype's 5s fade keyframes ported into `mobile.css`.
- The hint row's zoom/POV right-span logic (already implemented in Plan 02-01) is verified against this plan's own acceptance bar with no further code changes needed.

## Task Commits

1. **Task 1: Production sky gesture callbacks — tap, double-tap, swipe-step** - `91cd468` (feat)
2. **Task 2: Dock speed cycle, tap hint and hint-row context** - `3b84109` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `web/app.js` - `rollStepFrom`, production sky gesture callbacks inside `attachMobilePortraitGestures`, `app.mobileSurface` guard, `MOBILE_SPEED_RUNGS`/`mobileSpeedMultiplier`/`setMobileSpeedMultiplier`/`mobileSpeedButtonLabel`, dock speed button markup, `mobile-cycle-speed` click-delegation branch, `renderMobileSkyTapHint`, `app.mobileSkyHintShown`
- `web/mobile.css` - `.mobile-icon-btn`/`.mobile-icon-btn.compact` (44px floor via a scoped content-box override), `.mobile-sky-tap-hint` pill + `mobile-hint-fade` keyframes
- `tests/test_mobile_portrait.py` - `test_sky_gesture_contract`, `test_sky_tap_is_noop_when_tap_to_pause_off`, `test_dock_speed_cycle_persists_and_hint_row_context`

## Decisions Made

- **Speed rung labels stay canonical, display formatting is local:** `MOBILE_SPEED_RUNGS`'s labels are the UI-SPEC's literal value strings (`"0.5"/"1"/"2"/"4"`, matching `design/mobile-ux/prototype/panels.jsx`'s own Settings speed radio group), not pre-formatted glyphs. The plan's action text implied the dock button's label is simply `${mobileSpeedMultiplier()}×`, which would have rendered `"0.5×"` — contradicting both this plan's own acceptance criteria (which requires `"½×"`) and the UI-SPEC's locked glyph convention (line 124: `½× · 1× · 2× · 4×`). Resolved by keeping the rung table's canonical value strings for lookup/persistence/future-Settings-reuse, and mapping `"0.5"` to `"½"` only inside `mobileSpeedButtonLabel()`'s display formatting — confirmed against the prototype's own `app.jsx` (`prefs.speed === 0.5 ? "½×" : ...`), which uses the identical value/glyph split.
- **`.mobile-icon-btn.compact` uses a content-box override, not a `::before` hit-area expander:** the plan's action text offered "padding or an `::before` expander" as options for clearing the 44px floor while keeping the compact button's 36x36 UI-SPEC visual figure. Under this project's global `* { box-sizing: border-box }` reset, an explicit `width:36px` IS the total box regardless of padding, so a `::before` expander would leave the element's own `getBoundingClientRect()` at 36x36 — failing the acceptance bar's literal "every button in `.mobile-dock-transport` reports a bounding box of at least 44x44" assertion (Playwright's `bounding_box()` measures the host element only, not pseudo-element overflow). Scoped `box-sizing: content-box` to just `.mobile-icon-btn.compact` lets `width:36px` stay the literal CONTENT size while `padding:4px` grows the rendered — and hit-tested — box to 44x44, satisfying both the visual spec and the test's literal measurement without opting the whole stylesheet out of border-box.

## Deviations from Plan

### Auto-fixed Issues

None — both items above are documented as decisions rather than auto-fixed bugs because the plan's action-text guidance was advisory (illustrating an approach) rather than a literal contract; the plan's own acceptance criteria and CLAUDE.md's schema/no-parallel-implementation constraints were followed as the authoritative bar in both cases.

---

**Total deviations:** 0 auto-fixed; 2 documented design decisions where the plan's action-text guidance and its own acceptance criteria pointed in different directions (both resolved in favor of the acceptance criteria, cross-checked against the prototype's established conventions).
**Impact on plan:** No scope creep — both decisions stayed within Task 2's stated file list and artifact set.

## Issues Encountered

- Initial `test_sky_gesture_contract` draft ran the single-tap, double-tap, and swipe assertions sequentially on one page load; the single-tap toggle's playback (running during the 400ms waits between assertions) drifted `app.wordPos` out from under the later double-tap/swipe assertions. Fixed by giving each gesture phase its own fresh page load seeded to the same starting bookmark, so no phase's playback tick can affect another's assertions.
- `test_dock_speed_cycle_persists_and_hint_row_context`'s hint-row assertions initially used Playwright's `inner_text()`, which reflects the `.mobile-hint-row` CSS's `text-transform: uppercase` (returning `"4× ZOOM · JOE POV"` instead of the raw string). Switched to `text_content()`, which returns the untransformed DOM text.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The gesture callback set, dock speed control, and tap hint are the last pieces `attachMobilePortraitGestures`/`renderMobilePortrait` need before Plan 02-03 (cluster-binning) and Plan 02-04 (Settings/About/Help overlays, which introduce `app.mobileSurface` for real).
- `app.mobileSurface` guard is wired defensively now (treated as falsy) so Plan 02-04 only needs to set the field when an overlay opens — no rework of the gesture attach lifecycle required.
- `MOBILE_SPEED_RUNGS`'s canonical value-string labels are ready for Plan 02-04's Settings speed radio group to reuse directly via `setMobileSpeedMultiplier`, without introducing a second speed-value vocabulary.
- Real iOS Safari verification remains an explicit backstop item for the Phase B gate review with Dre (unchanged from Plan 02-01's summary) — emulation cannot substitute for actual touch/haptic behavior, though haptics themselves stay decorative-only per D-11 and are not exercised by this plan's own acceptance bar.

---
*Phase: 02-portrait-layout*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`91cd468`, `3b84109`) verified present in git log.
