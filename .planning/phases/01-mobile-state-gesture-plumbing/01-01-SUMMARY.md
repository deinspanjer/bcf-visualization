---
phase: 01-mobile-state-gesture-plumbing
plan: 01
subsystem: ui
tags: [mobile, gestures, pointer-events, matchmedia, localstorage, playwright]

requires: []
provides:
  - "web/mobile-gestures.js — byte-identical port of the prototype gesture module (attachSkyGestures / attachRailScrub / haptic / GestureConstants window exports)"
  - "app.layoutMode detection from the CSS-identical breakpoint query (D-06) with rAF-coalesced re-render on layout transitions, mirrored to window.__bcfLayoutMode"
  - "bcf:* storage schema v3: LS_MOBILE_TIMELINE_ZOOM / LS_TAP_TO_PAUSE / LS_HAPTICS / LS_HELP_SEEN, purge-on-bump incl. bcf:portrait-dismissed (D-09)"
  - "window.__bcfPrefs getter bridge + window.__bcfMobile setters (the MOBF-04 written-on-change contract Phase 2's Settings UI calls)"
  - "Per-render gesture attach lifecycle convention (D-07): attach post-mount inside render(), teardown-before-reattach on app.mobileGestureTeardown, never from matchMedia handlers"
  - "tests/test_mobile_plumbing.py — Playwright proofs Phase 2 extends"
affects: [01-02, 01-03, 01-04, mobile-renderers, settings-ui]

tech-stack:
  added: []
  patterns:
    - "Single canonical breakpoint string: MOBILE_LAYOUT_QUERY in app.js is character-identical to web/style.css:360; never a second width check"
    - "Gesture attach only from the render pass (cachePlaybackDomRefs convention); gesture callbacks never trigger structural renders"
    - "Diagnostic counters (__bcfGestureStats) increment only when harness-injected, mirroring __bcfRenderStats"

key-files:
  created:
    - web/mobile-gestures.js
    - tests/test_mobile_plumbing.py
  modified:
    - web/app.js
    - web/index.html
    - tests/helpers/web_runtime_site.py
    - tests/test_web_app_integration.py

key-decisions:
  - "window.__bcfPrefs implemented as a getter bridge in app.js so mobile-gestures.js stays byte-identical to the prototype (RESEARCH Pattern 3 Option A)"
  - "Layout debounce is plain rAF coalescing; the ~100ms iOS re-settle re-check is withheld until a real device shows the flap"
  - "Existing web integration fixtures re-seeded to storage version 3 in the same change as the bump (no-backwards-compat consumer rewrite)"
  - "Swipe-step test geometry corrected: 2 steps require >= 136px travel (SWIPE_ENGAGE 24 + 2x SCRUB_STEP_PX 56), not the plan's 120px figure"

patterns-established:
  - "Mobile UX section: all Phase 1+ mobile plumbing lives under the `// ── Mobile UX ─────────` divider before the module-tail listeners"
  - "Phase 2 renderers pass production callbacks through attachMobileGestureProbes' exact attach/teardown convention"

requirements-completed: [MOBF-01, MOBF-02, MOBF-03, MOBF-04]

coverage:
  - id: D1
    description: "window.__bcfLayoutMode reports desktop/portrait/landscape per the exact CSS breakpoint query and survives rotation"
    requirement: MOBF-02
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_layout_mode_matrix_matches_css_breakpoint"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_layout_mode_survives_rotation"
        status: pass
    human_judgment: false
  - id: D2
    description: "Gestures fire exactly once per gesture through forced re-renders and mid-drag re-renders; gesture path never triggers a structural render"
    requirement: MOBF-03
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_gestures_fire_exactly_once_without_structural_renders"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_gesture_attach_survives_forced_rerenders_without_double_fire"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_mid_drag_rerender_is_safe_and_fresh_probe_fires_once"
        status: pass
    human_judgment: false
  - id: D3
    description: "bcf:* keys round-trip through localStorage via allow-list readers; STORAGE_VERSION 2->3 bump purges bcf:portrait-dismissed and the new keys"
    requirement: MOBF-04
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_storage_version_bump_purges_stale_keys"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_mobile_pref_setters_round_trip_across_reload"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_out_of_set_stored_values_fall_back_to_defaults"
        status: pass
    human_judgment: false
  - id: D4
    description: "web/mobile-gestures.js is byte-identical to the prototype and its window exports are callable in the served app; desktop untouched"
    requirement: MOBF-01
    verification:
      - kind: other
        ref: "diff -q design/mobile-ux/prototype/gestures.js web/mobile-gestures.js (exit 0)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest tests/test_web_app_integration.py -q (20 passed, console-silence incl.)"
        status: pass
      - kind: other
        ref: "git diff web/style.css empty (desktop CSS freeze §0.1.5)"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-26
status: complete
---

# Phase 1 Plan 01: Mobile State & Gesture Plumbing Tracer Summary

**End-to-end mobile plumbing slice: byte-identical gesture-module port, matchMedia layout-mode detection off the CSS-canonical breakpoint, bcf:* storage schema v3 with purge-on-bump, and a per-render gesture attach lifecycle — all proven by 8 new Playwright tests with the desktop suite untouched and green.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-26T02:40:29Z
- **Completed:** 2026-07-26T02:50:11Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Ported `design/mobile-ux/prototype/gestures.js` byte-for-byte to `web/mobile-gestures.js`, loaded as a plain script before the `app.js` module; the `window.__bcfPrefs` getter bridge in app.js satisfies its haptics guard without editing the port (D-11).
- `app.layoutMode` ("desktop"/"portrait"/"landscape") computed before first render from `MOBILE_LAYOUT_QUERY` — character-identical to `web/style.css:360` (D-06) — with rAF-coalesced transitions on matchMedia/orientationchange that re-render only on actual mode change, mirrored to `window.__bcfLayoutMode`.
- `STORAGE_VERSION` "2"→"3" with the purge array extended to drop `bcf:portrait-dismissed` plus the four new keys; `window.__bcfMobile` setters (`setTapToPause`, `setHaptics`, `setMobileTimelineZoom` with [1,2,4,8] allow-list, `markHelpSeen`) persist on change (D-09, MOBF-04).
- Gesture attach lifecycle (D-07): `attachMobileGestureProbes()` runs post-mount inside `render()`'s `app.layoutMode` branch (the only sanctioned edit to existing render code), invokes prior teardown before re-attach, and drives harness-only `__bcfGestureStats` counters; desktop path executes exactly its prior code.
- `tests/test_mobile_plumbing.py` (8 tests): 5-viewport layout matrix incl. iPad bounds, rotation survival, tap/double-tap/swipe single-fire, no-double-bind across forced re-renders, mid-drag re-render safety, purge-on-bump, setter round-trip across reload, allow-list fallback — all with console-silence assertions.

## Task Commits

1. **Task 1: End-to-end mobile plumbing slice — port, detect, persist, attach** - `3034d90` (feat)
2. **Task 2: Playwright proof of the tracer** - `c212c19` (test)

Tracer feedback gate: after committing Task 1, the full tracer `<verify>` (node --check ×2, byte-diff, desktop integration suite) was re-run end-to-end and passed before expansion.

## Files Created/Modified

- `web/mobile-gestures.js` - Byte-identical port; window exports attachSkyGestures/attachRailScrub/haptic/GestureConstants
- `web/index.html` - Plain script tag before the app.js module; viewport meta `width=device-width, initial-scale=1, viewport-fit=cover` (D-03, page zoom stays enabled)
- `web/app.js` - LS_* mobile constants, STORAGE_VERSION 3 + purge extension, layout detection, Mobile UX section (bridge/setters/counters/attach lifecycle), render() layoutMode branch
- `tests/helpers/web_runtime_site.py` - WEB_FILES gains "mobile-gestures.js"
- `tests/test_web_app_integration.py` - Storage fixtures re-seeded "2"→"3" (consumer rewrite for the schema bump)
- `tests/test_mobile_plumbing.py` - New 8-test Playwright proof module

## Decisions Made

- `window.__bcfPrefs` bridge (Option A) over adapting haptic() call sites — keeps the port verbatim.
- Plain rAF coalescing for layout debounce; iOS ~100ms re-settle re-check deferred until a real device shows the flap (plan discretion, recorded).
- `infoOpen: false` already existed in the app literal (web/app.js:90); not duplicated — the plan's field list was written against a pre-info-popover state.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Existing integration fixtures pinned storage version "2"**
- **Found during:** Task 1 (verification run)
- **Issue:** 9 tests in `tests/test_web_app_integration.py` seed `"bcf:preview-port-storage-version": "2"`; after the v3 bump the migration purges their seeded bookmark/speed/mode keys, failing the suite the plan requires green.
- **Fix:** Re-seeded all fixture literals to `"3"` — the schema-change-rewrites-all-consumers policy applied to test fixtures.
- **Files modified:** tests/test_web_app_integration.py
- **Verification:** Full suite 20/20 green.
- **Committed in:** 3034d90 (Task 1 commit)

**2. [Rule 1 - Bug] Plan's swipe behavior spec arithmetic vs. verbatim gesture constants**
- **Found during:** Task 2 (test design)
- **Issue:** The `<behavior>` block expects `+120px → swipeSteps == 2`, but the ported constants make that impossible: engagement consumes SWIPE_ENGAGE (24px) before step accumulation, so 2 steps need ≥ 24 + 2×56 = 136px.
- **Fix:** Test drags 140px in 8px increments (engage at 24, steps at 80 and 136), asserting exactly 2 steps + 1 swipeEnd per the real contract.
- **Files modified:** tests/test_mobile_plumbing.py
- **Verification:** Test passes and would catch a double-fire regression.
- **Committed in:** c212c19 (Task 2 commit)

### Plan-sanctioned deviations from INTEGRATION_PLAN.md (pre-recorded in the plan)

- Viewport meta omits `user-scalable=no`/`maximum-scale=1` — D-03 supersedes stale §3.3.
- `LS_PORTRAIT_DISMISSED` **added** to the purge list — D-09/RESEARCH Pitfall 1 supersede §3.1's stale "remove" wording.

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 plan-spec bug)
**Impact on plan:** Both necessary for correctness of the verification contract. No scope creep.

## Issues Encountered

- `scripts/verify.py` (AGENTS.md full gate) fails at `data_release.py check-derived` on **pre-existing** local derived-data staleness: stale `perk_directory` sha256 and a ch 95.5 multi_grab override referencing 'Minor Blessing Zeus – Lightning' with no matching obtained perk. This is Track B curation/data-pipeline state untouched by this plan; logged to `deferred-items.md` per executor scope boundary. Verification run instead: `node --check web/app.js web/mobile-gestures.js` + `.venv/bin/python -m pytest tests/test_web_app_integration.py tests/test_mobile_plumbing.py -q` (28 passed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The bcf:* key strings, STORAGE_VERSION "3", `window.__bcfLayoutMode`/`__bcfPrefs`/`__bcfMobile` globals, and the attach-lifecycle convention are now the contract plans 01-02..01-04 build on.
- Ready for 01-02 (mobile CSS foundation + visibilitychange pause branch).
- Pre-existing derived-data staleness (see Issues) should be resolved on the Track B side before `scripts/verify.py` can gate Track A phases.

## Self-Check: PASSED

- Created files exist on disk (web/mobile-gestures.js, tests/test_mobile_plumbing.py, this SUMMARY)
- Task commits present: 3034d90, c212c19
- All plan `<verification>` commands re-run green; `git diff web/style.css` empty

---
*Phase: 01-mobile-state-gesture-plumbing*
*Completed: 2026-07-26*
