---
phase: 01-mobile-state-gesture-plumbing
plan: 02
subsystem: ui
tags: [mobile, css, touch-action, viewport-units, safe-area, visibilitychange, playwright]

requires:
  - phase: 01-mobile-state-gesture-plumbing (plan 01)
    provides: "app.layoutMode / window.__bcfLayoutMode, MOBILE_LAYOUT_QUERY, STORAGE_VERSION 3, the Mobile UX section in app.js, tests/test_mobile_plumbing.py module"
provides:
  - "web/mobile.css — mobile CSS foundation: .mobile-sky-surface/.mobile-rail-surface touch-action/overscroll-behavior classes (D-03), --mobile-vh/--mobile-dvh svh/dvh primitives and --safe-top/--safe-bottom/--safe-left/--safe-right env(safe-area-inset-*) custom properties (D-08), all scoped behind the character-identical mobile breakpoint"
  - "web/index.html mobile.css stylesheet link, loaded after style.css so it always cascades over the pre-existing narrow-viewport blocks at style.css:1564/:1607"
  - "Mobile-only pause-on-hidden branch (D-02) inside the single existing visibilitychange handler in web/app.js"
affects: [01-03, 01-04, mobile-renderers, mobile portrait/landscape layout CSS]

tech-stack:
  added: []
  patterns:
    - "Mobile CSS lives entirely in web/mobile.css, loaded after web/style.css — never a new block inside style.css; load order is the mechanical enforcement of the freeze (git diff web/style.css stays empty)"
    - "Gesture-surface suppression via declarative touch-action/overscroll-behavior classes (D-03) rather than JS preventDefault or viewport-meta zoom locks"

key-files:
  created:
    - web/mobile.css
  modified:
    - web/index.html
    - web/app.js
    - tests/helpers/web_runtime_site.py
    - tests/test_mobile_plumbing.py

key-decisions:
  - "CSS foundation classes/variables are defined now but inert (no element carries them yet) — Phases 2-3 apply them to real sky/rail/dock nodes per CONTEXT.md's requirement that these decisions land in Phase 1, not be retrofitted"
  - "--mobile-vh uses 100svh (not 100dvh) per RESEARCH.md Pitfall 4 — this app has no scrollable body content to trigger an iOS toolbar-hide reflow, so svh avoids the dvh reflow-during-scroll jank; --mobile-dvh is exposed separately for any future case that intentionally wants toolbar-aware sizing"
  - "D-02 pause test asserts the readout stops advancing across a wait after the hidden event, not just that it differs from the pre-click reading — the naive before/after-click comparison is flaky because real playback time elapses between the click and the forced-hidden dispatch"

requirements-completed: [MOBF-05]

coverage:
  - id: D1
    description: "Mobile CSS foundation: touch-action pan-y/none + overscroll-behavior contain gesture-surface classes, computed-style-verified at phone and desktop viewports"
    requirement: MOBF-05
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_css_foundation_touch_action_and_viewport_primitives"
        status: pass
    human_judgment: false
  - id: D2
    description: "svh/dvh viewport-height primitives and env(safe-area-inset-*) custom properties exposed on :root behind the mobile breakpoint"
    requirement: MOBF-05
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_css_foundation_touch_action_and_viewport_primitives"
        status: pass
    human_judgment: false
  - id: D3
    description: "Hiding the page pauses playthrough on mobile layouts with state intact (no reset, no auto-resume); desktop path unchanged (D-02)"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_plumbing.py#test_visibilitychange_pauses_playback_on_mobile_only"
        status: pass
    human_judgment: false
  - id: D4
    description: "web/style.css is never edited; mobile.css cascades after it; desktop integration suite stays green"
    verification:
      - kind: other
        ref: "git diff --quiet web/style.css (exit 0)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest tests/test_web_app_integration.py -q (20 passed)"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-26
status: complete
---

# Phase 1 Plan 02: Mobile CSS Foundation + Pause-on-Hidden Summary

**web/mobile.css lands the D-03/D-08 CSS foundation decisions (touch-action/overscroll-behavior gesture-surface classes, svh/dvh height primitives, safe-area-inset custom properties) as an inert, breakpoint-scoped, computed-style-proven stylesheet loaded after style.css; D-02 pause-on-hidden is wired into the one existing visibilitychange handler, mobile-only.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-26T02:51:45Z
- **Completed:** 2026-07-26T02:58:44Z
- **Tasks:** 2
- **Files modified:** 5 (1 created)

## Accomplishments

- New `web/mobile.css`, wrapped entirely in the character-identical mobile breakpoint (`web/style.css:360`), defines `.mobile-sky-surface` (`touch-action: pan-y`, D-03's page-zoom-safe replacement for the rejected `user-scalable=no`) and `.mobile-rail-surface` (`touch-action: none`), plus `:root` custom properties `--mobile-vh: 100svh` / `--mobile-dvh: 100dvh` and `--safe-top`/`--safe-bottom`/`--safe-left`/`--safe-right` via `env(safe-area-inset-*)` (D-08).
- `web/index.html` gets a `mobile.css` stylesheet link on the line after `style.css`, so later-loaded rules win the cascade against the pre-existing overlapping desktop-narrow blocks at `style.css:1564`/`:1607` without ever editing that file.
- `tests/helpers/web_runtime_site.py` `WEB_FILES` gains `"mobile.css"` so the Playwright harness serves the new asset.
- `tests/test_mobile_plumbing.py` proves the CSS foundation: at 390×844 the surface classes compute the expected `touchAction`/`overscrollBehavior`, an element styled `height: var(--mobile-vh)` computes to the exact viewport-height pixel value, and `padding-bottom: var(--safe-bottom)` computes to `0px` (env fallback in desktop-emulated Chromium); at 1280×900 the same class computes `touchAction: "auto"` (media block not matched — desktop untouched).
- `web/app.js`'s single existing `visibilitychange` listener gains a mobile-only branch: hidden + `app.layoutMode !== "desktop"` + `app.playing` calls the existing, unmodified `stopPlayback()`; the desktop bookmark-persist branch is untouched and no second listener was added.
- New Playwright test proves the D-02 contract end-to-end: on a phone viewport, Play → forced `visibilitychange` to hidden → the Play/Pause button flips back to "Play" and the word-position readout stops advancing across a subsequent wait (true pause, not just a relabel); on desktop the same sequence leaves the button showing "Pause" (playback keeps running).

## Task Commits

1. **Task 1: Mobile CSS foundation file — surface classes, viewport units, safe-area insets** - `0bca726` (feat)
2. **Task 2: Pause playback when the page is hidden — mobile layouts only (D-02)** - `9df5240` (feat)

## Files Created/Modified

- `web/mobile.css` - New file: mobile-scoped media block with gesture-surface classes, viewport-height primitives, safe-area custom properties
- `web/index.html` - `mobile.css` stylesheet link added after the `style.css` link
- `web/app.js` - Mobile-only `stopPlayback()` branch added inside the existing `visibilitychange` listener
- `tests/helpers/web_runtime_site.py` - `WEB_FILES` gains `"mobile.css"`
- `tests/test_mobile_plumbing.py` - `test_css_foundation_touch_action_and_viewport_primitives` and `test_visibilitychange_pauses_playback_on_mobile_only`

## Decisions Made

- `--mobile-vh` uses `100svh`, not `100dvh` — this app has no scrollable body content that would trigger an iOS toolbar-hide reflow, so `svh` avoids the `dvh` reflow-during-scroll jank noted in RESEARCH.md Pitfall 4; `--mobile-dvh` is still exposed as a separate primitive for any future case that intentionally wants toolbar-aware sizing.
- CSS foundation classes are defined now but carried by zero elements this phase (Phase 1 delivers plumbing, not UI) — Phases 2-3 apply `.mobile-sky-surface`/`.mobile-rail-surface` to real sky/rail nodes and consume the viewport/safe-area variables.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial version of the D-02 pause test compared the readout text immediately before the Play click against immediately after the forced-hidden dispatch; this is flaky because real playback time elapses between click and hidden-dispatch (network/event round-trips), so the readout legitimately differs even when pausing works correctly. Fixed by comparing the readout at the moment of pause against the same readout after an additional 300ms wait — this actually proves the pause holds (no further advance), which is a stronger and more correct assertion than the original before/after-click comparison. Not a deviation from plan scope, just a test-design correction made while implementing Task 2's `<behavior>` block.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `web/mobile.css` classes and custom properties (`--safe-top`/`--safe-bottom`/`--safe-left`/`--safe-right`, `--mobile-vh`, `--mobile-dvh`, `.mobile-sky-surface`, `.mobile-rail-surface`) are now the CSS contract Phase 2/3 layout work consumes rather than retrofits.
- D-02 pause-on-hidden is implemented and pinned by tests; MOBX-05 (later phase) re-verifies it on the real mobile layouts once they exist.
- Ready for 01-03.

## Self-Check: PASSED

- `web/mobile.css` exists on disk; `git diff --quiet web/style.css` confirms the frozen file is untouched
- Task commits present in git log: `0bca726`, `9df5240`
- All plan `<verification>` commands re-run green: `pytest tests/test_mobile_plumbing.py -q` (10 passed), `git diff --quiet web/style.css`, `node --check web/app.js`
- `pytest tests/test_web_app_integration.py -q` (20 passed) — desktop suite unaffected

---
*Phase: 01-mobile-state-gesture-plumbing*
*Completed: 2026-07-26*
