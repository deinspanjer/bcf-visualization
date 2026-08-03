---
phase: 02-portrait-layout
plan: 01
subsystem: ui
tags: [vanilla-js, css-flexbox, playwright, pointer-events, svg]

requires:
  - phase: 01-mobile-state-gesture-plumbing
    provides: "layoutMode detection, mobile-gestures.js (attachSkyGestures/attachRailScrub), bcf:* pref plumbing, mobile.css touch-action/safe-area/vh foundation"
provides:
  - "render() D-12 portrait branch: renderMobilePortrait() replaces renderAppShell() only in portrait; desktop/landscape byte-identical"
  - "updatePlaybackFrame() D-18 portrait early-return before the desktop #scrubber-playhead gate (no render() recursion)"
  - "Real sky-camera cinematic mounted under .mobile-sky-camera-layer (never the prototype's procedural placeholder)"
  - "Mini-rail (chapters/rolls/playhead lanes) with zoom-aware pan (panOffsetForPlayhead/fractionFromPointer/mobileInnerFraction)"
  - "Rail drag scrub committed through the existing setWordPos path (D-17), single scrub input, bookmark persisted on release"
  - "Top chip cluster (CH + amber roll chip), sky focal label, hint row — MOBP-01 no-overlap bar proven at 390px and 320px"
affects: [02-02-portrait-speed-help, 02-03-cluster-binning, 02-04-settings-flyouts]

tech-stack:
  added: []
  patterns:
    - "Portrait DOM duplicates markup over the shared model (playthroughFrameState/renderViewportFrame/renderSkyCamera) rather than editing frozen desktop renderers"
    - "Structural-presence-change keying (roll uid / firing composite) for the amber chip and focal label — replaceChildren only fires on key change, never every incremental frame"
    - "Sky/dock flex split: sky flex:0 1 60% (no grow) + dock flex:1 0 auto (absorbs leftover) holds the sky at its locked 60% basis regardless of the dock's actual content height"

key-files:
  created:
    - tests/test_mobile_portrait.py
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_desktop_smoke.py
    - tests/helpers/web_runtime_site.py

key-decisions:
  - "Sky gets flex:0 1 60% (no grow) and dock gets flex:1 0 auto (absorbs leftover) rather than the UI-SPEC's literal flex:1 1 60% / flex:0 0 auto, because the dock's real content height (~178px) is well under 40% of typical phone viewports — the literal combination let the sky absorb ~80% of the viewport instead of the intended ~60%."
  - "Empty-state em-dash fallback (chapterAtWord() returning undefined) is only reachable via a zero-chapter package — added a dedicated `chapterless` test fixture rather than skip that acceptance bullet."

requirements-completed: [MOBP-01, MOBP-03]

coverage:
  - id: D1
    description: "Portrait render() branch: renderMobilePortrait() replaces the desktop shell only in portrait; desktop/landscape stay byte-identical"
    requirement: "MOBP-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_tracer_renders_sky_dock_and_rail_scrub_commits"
        status: pass
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_range_resizes_cause_zero_rerenders_while_crossings_flip_layout_mode"
        status: pass
    human_judgment: false
  - id: D2
    description: "Portrait playback produces zero structural re-renders and no render() recursion"
    requirement: "MOBP-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_playback_has_no_recursive_renders"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mini-rail drag scrubs the story and persists the bookmark through the existing setWordPos path"
    requirement: "MOBP-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_tracer_renders_sky_dock_and_rail_scrub_commits"
        status: pass
    human_judgment: false
  - id: D4
    description: "Real sky-camera cinematic renders under .mobile-sky-camera-layer while firing"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_cinematic_renders_sky_camera_svg"
        status: pass
    human_judgment: false
  - id: D5
    description: "Top chip cluster never overlaps the sky focal label at 390x844 or 320x568, including a long multibyte perk name; sky/dock split lands in the 50-70% band"
    requirement: "MOBP-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_layout_proportions_and_chip_overlap"
        status: pass
    human_judgment: false
  - id: D6
    description: "Empty/partial states: no amber chip or focal label before the first roll; dock title never renders literal 'undefined'; em-dash fallback for an unknown chapter"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_portrait_empty_and_partial_states"
        status: pass
    human_judgment: false
  - id: D7
    description: "On a real iPhone in Safari the top chips read as clearly separated from the sky focal label, and the sky camera's letterboxing reads as intentional cinematic framing"
    verification: []
    human_judgment: true
    rationale: "Backstop truths in the plan's must_haves explicitly require real-device Safari verification (RESEARCH Assumption A1) — emulation cannot substitute for actual iOS toolbar/aspect-ratio behavior."

duration: 40min
completed: 2026-07-26
status: complete
---

# Phase 2 Plan 1: Portrait Tracer — Render Branch, Real Sky, Dock, Mini-Rail Scrub Summary

**Portrait render() arm wired end-to-end: real sky-camera cinematic, mini-rail scrub through the existing setWordPos path, top chips + focal label proven not to overlap at 390px and 320px — zero structural re-renders during playback.**

## Performance

- **Duration:** 40 min
- **Started:** 2026-07-26T18:18:00-04:00
- **Completed:** 2026-07-26T18:50:31-04:00
- **Tasks:** 2
- **Files modified:** 5 (2 created counted within)

## Accomplishments

- `render()` now branches to `renderMobilePortrait()` only when `app.layoutMode === "portrait"` (D-12); desktop and the interim landscape fallback keep `renderAppShell()` byte-identical.
- `updatePlaybackFrame()`'s portrait early return lands before the desktop `#scrubber-playhead` gate, closing the render()-recursion pitfall the RESEARCH doc flagged (D-18/T-02-01) — proven by a live 1.5s playback run with zero structural re-renders.
- The real sky-camera cinematic (frozen `renderSkyCamera`/`playthroughFrameState`) mounts under `.mobile-sky-camera-layer`, never the prototype's procedural placeholder (D-13).
- The mini-rail (chapter ticks, POV bands, one dot per roll, playhead) commits drags through the existing `setWordPos` path via `attachRailScrub` + the new `mobileInnerFraction` conversion (D-17) — no parallel scrub input — and persists the bookmark on release.
- Top chip cluster (CH chip + amber roll chip, structurally absent with no active roll), sky focal label (kicker/name/sub), and hint row all wired into the incremental update tier with keyed structural-presence diffing.
- MOBP-01's acceptance bar (chips never overlap the focal label, sky/dock split in the 50-70% band) proven at both 390x844 and 320x568, including a long multibyte perk name.
- Both Phase 1 regression suites (`test_mobile_plumbing.py`, `test_desktop_smoke.py`) still pass unmodified except the one flagged F-02 assertion.

## Task Commits

1. **Task 1: End-to-end portrait slice — render branch, real sky, dock, mini-rail scrub** - `b5b5109` (feat)
2. **Task 2: Top chips, focal label and hint row without overlap at 320px** - `45c04e1` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `web/app.js` - `render()`/`updatePlaybackFrame()`/`cachePlaybackDomRefs()` portrait branches; new `renderMobilePortrait`, `renderMobileTopCluster`, `renderMobileFocalLabel`, `renderMobileScrubber`, `renderMobileHintRow`, `updateMobilePortraitFrame` + its per-region helpers, `attachMobilePortraitGestures`, `panOffsetForPlayhead`, `fractionFromPointer`, `mobileInnerFraction`
- `web/mobile.css` - Portrait layout rules: `.mobile-app`/`.mobile-top-cluster`/`.mobile-chip`/`.mobile-sky`/`.mobile-focal-label`/`.mobile-dock`/`.mobile-rail` and lane/tick/band/dot/playhead/hint-row rules
- `tests/test_mobile_portrait.py` - Created: portrait tracer, cinematic-sky, no-recursion, layout-overlap (parametrized 390/320), and empty/partial-state tests
- `tests/test_desktop_smoke.py` - The one F-02 superseded assertion now checks `.mobile-app` visibility instead of `.portrait-banner`
- `tests/helpers/web_runtime_site.py` - New `dense-rolls` (dense cluster + long multibyte perk name) and `chapterless` (zero-chapter fallback) staged packages; `tiny-default`/`tiny-alt` payloads stay byte-identical

## Decisions Made

- **Sky/dock flex-grow swap:** Kept the UI-SPEC's locked flex-basis values (`sky: ...60%`, `dock: ...auto`) but moved which side gets `flex-grow` — sky is `flex: 0 1 60%` (no grow) and dock is `flex: 1 0 auto` (absorbs leftover). The literal `sky: flex:1 1 60% / dock: flex:0 0 auto` combination let the sky's grow factor absorb 100% of the space above the dock's compact real content (~178px), pushing the sky to ~80% of the viewport instead of the intended ~60% — the swap holds the sky at its locked 60% basis exactly regardless of the dock's actual content height.
- **`chapterless` test fixture for the em-dash fallback:** `chapterAtWord()` only ever returns `undefined` (triggering the dock title's `"—"` fallback) when `story.chapters` is empty — every real chapter always resolves a non-empty title via `normChapterTitle`'s `Chapter ${num}` default. Added a dedicated zero-chapter package rather than skip that UI-SPEC acceptance bullet.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `mobileChChipText()` crashed on an undefined chapter**
- **Found during:** Task 2 (writing `test_portrait_empty_and_partial_states` against the new `chapterless` fixture)
- **Issue:** `chapterAtWord(app.wordPos).chapter_num` dereferenced the result without a null check; `chapterAtWord()` returns `undefined` when `story.chapters` is empty, throwing `Cannot read properties of undefined (reading 'chapter_num')` and aborting the render before any portrait DOM mounted.
- **Fix:** Optional-chained the lookup with an em-dash fallback: `` `CH ${chapterAtWord(app.wordPos)?.chapter_num ?? "—"} · ...` ``.
- **Files modified:** `web/app.js`
- **Verification:** `test_portrait_empty_and_partial_states` passes against the `chapterless` package with an empty console.
- **Committed in:** `45c04e1` (Task 2 commit)

**2. [Rule 1 - Bug] Sky/dock flex ratio didn't hold the ~60% truth**
- **Found during:** Task 2 (`test_portrait_layout_proportions_and_chip_overlap` at 390x844 first measured a 0.796 sky/viewport ratio, outside the 50-70% band)
- **Issue:** With `sky: flex:1 1 60%` and `dock: flex:0 0 auto`, the sky's grow factor of 1 absorbed all leftover space above the dock's real (compact) content height, giving ~80% instead of ~60%.
- **Fix:** Swapped grow assignment — `sky: flex:0 1 60%` (no grow, holds its basis), `dock: flex:1 0 auto` (grow:1, shrink:0, absorbs the leftover ~40% without ever compressing below its own content).
- **Files modified:** `web/mobile.css`
- **Verification:** `test_portrait_layout_proportions_and_chip_overlap` passes at both 390x844 and 320x568 (ratio == exactly 0.6 at both).
- **Committed in:** `45c04e1` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes were necessary for correctness (one prevented a crash, one closed a truth-statement gap); no scope creep.

## Known Stubs

These are intentionally out of this plan's scope per the plan's own `<action>` text and the phase's artifact-ownership list — none block this plan's own MOBP-01/MOBP-03 acceptance bar, and each has a named owning plan later in this phase:

- `.mobile-help-spacer` in `renderMobileTopCluster()` (`web/app.js`) — empty 44x44 reserved area, no `?` help button wired yet. **Owner:** Plan 02-04.
- `renderMobileScrubber()`'s rail renders one `.mobile-roll-dot` per roll with no cluster-bin merging (`binRolls`/`finalizeBin`/`binSize` not yet ported). **Owner:** Plan 02-03 (MOBP-04).
- `.mobile-dock-transport` has no speed-cycle, gear (Settings), or info (About) buttons — dock-transport only holds the FAB and the now-meta/title. **Owner:** Plan 02-02 (speed) and Plan 02-04 (gear/info/Settings-About-Help surfaces).
- `.mobile-roll-dot.active` / `app.dom.mobileActiveDot` cached ref exists but nothing currently assigns the `.active` class to a specific dot (no separate always-on-top active marker rendered yet, matching the prototype's MiniRail). Deferred alongside cluster-binning — **Owner:** Plan 02-03.

## Threat Flags

None — all new surface (portrait DOM construction, rail scrub input, localStorage-driven zoom/bookmark reads) was already covered by this plan's `<threat_model>` register (T-02-01..T-02-04, T-02-SC).

## Issues Encountered

None beyond the two auto-fixed bugs above (discovered and resolved during the plan's own test-writing, not separate incidents).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The portrait render/incremental-update/gesture plumbing this plan built is the foundation every remaining Phase 2 plan (02-02 speed+help, 02-03 cluster binning, 02-04 Settings/About/Help surfaces) extends — no rework needed, only additive wiring into the same `renderMobilePortrait`/`updateMobilePortraitFrame`/`attachMobilePortraitGestures` functions.
- Real iOS Safari verification (D7 above) remains an explicit backstop item for the Phase B gate review with Dre — emulation cannot substitute for actual toolbar/letterboxing behavior.
- D-15 (no mobile "details" view in v1 — the Settings mode toggle persists but portrait always renders playthrough) is unaffected by this plan and stays on the Phase B gate agenda per `02-CONTEXT.md`.

---
*Phase: 02-portrait-layout*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (`b5b5109`, `45c04e1`) verified present in git log.
