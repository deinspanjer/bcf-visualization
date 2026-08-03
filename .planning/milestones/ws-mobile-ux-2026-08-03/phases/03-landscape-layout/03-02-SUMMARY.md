---
phase: 03-landscape-layout
plan: 02
subsystem: ui
tags: [vanilla-js, mobile-ux, gestures, playwright, dom-incremental-update]

# Dependency graph
requires:
  - phase: 03-landscape-layout (plan 01)
    provides: renderMobileLandscape()/renderMobileSkyRegion(), the cinema-scrub/field-log markup and DOM refs (app.dom.mobileCinemaScrub*/mobileFieldLog*), the render/cache-refs/incremental-update dispatch trio, and the `.mobile-cinema-scrub.is-hidden` CSS variant this plan wires behavior into
provides:
  - attachMobileGestures() — the single gesture-attach lifecycle for BOTH mobile layouts (D-34), replacing attachMobilePortraitGestures; one teardown block, one scrub-input path via mobileScrubSurfaceEl()
  - render()'s gesture-attach + D-16 focus-trap re-attach block widened from portrait-only to every non-desktop layout in one edit (Pitfall 3) — landscape flyouts now trap keyboard focus
  - The landscape cinema-scrub drag committing through the existing attachRailScrub/setWordPos path, monotonic at 1x/2x/4x/8x from its first commit (the Phase 2 auto-pan-freeze fix applied by construction)
  - rebuildMobileCinemaScrubTrack() (ResizeObserver rebuild target) and app.mobileRailWidthLayout now written by the observer, closing plan 01's "written but not yet set" gap
  - Chrome auto-hide: resetMobileChromeHideTimer()/revealMobileChrome(), app.mobileChromeHideTimer state, wired into all six gesture callbacks and both ordinary exits (plus the held-cinematic early return) of togglePlayback()
affects: [03-03, 03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mobileScrubSurfaceEl() — the one place the scrub-drag surface selector lives (portrait .mobile-rail vs landscape .mobile-cinema-scrub-track), used by both the attachRailScrub call and the ResizeObserver observe() call"
    - "Idle-timer lifecycle mirrors the existing teardown-discipline pattern (state on `app`, not `app.dom`; unconditional clear at the top of attachMobileGestures() before any re-attach) already established for mobileSurfaceFocusTrapTeardown/mobileSkyTeardown/mobileRailTeardown"
    - "Auto-hide reset threaded through discrete gesture-callback bodies only (tap/double-tap/swipe-step/swipe-end/scrub/scrub-end) plus togglePlayback()'s transitions — never from updateMobileLandscapeFrame() or a wordPos comparison (Pitfall 1)"

key-files:
  created: []
  modified:
    - web/app.js
    - tests/test_mobile_landscape.py

key-decisions:
  - "revealMobileChrome()/resetMobileChromeHideTimer() are fully implemented in Task 1's commit (not deferred to Task 2) because Task 1's own onTap reveal branch calls them by name — Task 2 only adds togglePlayback()'s transition-based wiring and the full timing-contract tests, matching the plan's own 'six gesture-callback sites Task 1 already wired' vs. 'Task 2: auto-hide wiring in togglePlayback()' split"
  - "A no-op tap with tap-to-pause OFF does NOT reset the chrome-hide timer, matching the plan's literal 'onTap (after the existing toggle) ends with a resetMobileChromeHideTimer() call' placement — the reset call sits after togglePlayback(), inside the tap-to-pause-gated branch, not before it"
  - "Test-only: tiny-default's whole story is 10000 words, which finishes (and auto-pauses) inside 2s at the default 5000 words/sec — every timing-sensitive auto-hide test seeds a much slower bcf:playback:speed:v2 so playback stays running across the multi-second real-time waits the 4000ms boundary needs"
  - "Test-only: clicking the auto-hidden cinema-scrub FAB (pointer-events:none) must invoke the DOM .click() method directly rather than a Playwright force-click, which would resolve to real screen coordinates and hit-test through to the sky underneath — a false-positive pass through the wrong gesture path"

patterns-established: []

requirements-completed: [MOBL-02]

coverage:
  - id: D1
    description: "One attachMobileGestures() serves both mobile layouts through one teardown block (now four slots, including the auto-hide timer) and one scrub-input path (mobileScrubSurfaceEl()) — attachMobilePortraitGestures no longer exists"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_sky_gesture_contract"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_gestures_survive_rerender_and_surface_toggle"
        status: pass
      - kind: other
        ref: "grep -c 'function attachMobileGestures(' web/app.js == 1; grep -c 'function attachMobilePortraitGestures(' web/app.js == 0; grep -c 'window.attachRailScrub(' web/app.js == 1"
        status: pass
    human_judgment: false
  - id: D2
    description: "render()'s gesture-attach AND the D-16 focus-trap re-attach widened from portrait-only to every non-desktop layout in one edit — a landscape flyout traps keyboard focus exactly like portrait's does"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_gestures_survive_rerender_and_surface_toggle"
        status: pass
    human_judgment: false
  - id: D3
    description: "The landscape cinema-scrub drag commits through the existing attachRailScrub/setWordPos path and is monotonic at zoom 1x/2x/4x/8x from its first commit — no second scrub-input implementation"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_cinema_scrub_drag_is_monotonic_at_every_zoom"
        status: pass
    human_judgment: false
  - id: D4
    description: "Chrome auto-hides after 4000ms of idle DURING PLAYBACK only (asserted from both sides of the boundary), an interaction resets the window, a paused reader never has the timer arm, pausing while hidden immediately reveals and holds it, only the cinema-scrub hides (top chips/sidebar stay visible), and the whole cycle costs zero structural re-renders"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_chrome_autohide_boundary"
        status: pass
    human_judgment: false
  - id: D5
    description: "The first sky tap on hidden chrome ALWAYS reveals and leaves playback running, regardless of the tap-to-pause preference (the D-30 no-trap guarantee); only the next tap pauses, and only when tap-to-pause is on"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_reveal_tap_semantics"
        status: pass
    human_judgment: false
  - id: D6
    description: "Auto-hide behaves correctly on the zero-roll story too — the cinema-scrub still reveals/hides and the play FAB still toggles, with no roll markers on the track"
    requirement: "MOBL-02"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_field_log_zero_and_empty_states"
        status: pass
    human_judgment: false

# Metrics
duration: 65min
completed: 2026-08-02
status: complete
---

# Phase 3 Plan 2: Landscape gestures and chrome auto-hide Summary

**Generalized attachMobilePortraitGestures into a single attachMobileGestures() serving both mobile layouts (D-34), wired the landscape cinema-scrub drag through the existing attachRailScrub/setWordPos path with the Phase 2 monotonicity fix applied from the start, and added the phase's one genuinely novel piece — a 4000ms chrome auto-hide idle timer with D-28..D-31's reveal-vs-pause semantics — driven entirely by discrete gesture callbacks and togglePlayback(), never by a wordPos comparison.**

## Performance

- **Duration:** ~65 min
- **Completed:** 2026-08-02
- **Tasks:** 2 (Task 1: gesture-attach generalization + cinema-scrub drag; Task 2: auto-hide timer wiring in togglePlayback)
- **Files modified:** 2 (web/app.js, tests/test_mobile_landscape.py)

## Accomplishments
- `render()`'s gesture-attach and D-16 focus-trap re-attach block moved from portrait-only to every non-desktop layout in a single edit (Pitfall 3) — a landscape Settings/About/Help flyout now traps keyboard focus exactly like portrait's does, proven by a Tab-cycling test that never escapes the flyout.
- `attachMobilePortraitGestures` is gone; `attachMobileGestures()` is the one gesture-attach lifecycle for both layouts, sharing all four teardown slots (`mobileSkyTeardown`, `mobileRailTeardown`, `mobileRailResizeObserver`, and the new `mobileChromeHideTimer`) and one scrub-input path (`mobileScrubSurfaceEl()`), never a fourth parallel landscape-only teardown slot.
- The landscape cinema-scrub drag reuses the identical `onScrub`/`onScrubEnd` callback bodies portrait's rail already uses — same `app.mobileScrubPanPct` freeze-on-drag-start shape that fixed the Phase 2 Pixel 10 Pro XL 68k-word backward-drag defect (`ed59087`) — so the fix applies to landscape by construction, not rediscovered on a second device. Proven monotonic at zoom 1x/2x/4x/8x.
- The ResizeObserver generalizes to both layouts: it now records `app.mobileRailWidthLayout` (closing the gap plan 01 explicitly left open) and branches its rebuild target — `rebuildMobileCinemaScrubTrack()` for landscape, the existing rolls-lane rebuild for portrait.
- Chrome auto-hide: `resetMobileChromeHideTimer()` arms a 4000ms window only while `layoutMode === "landscape" && app.playing && !app.mobileSurface`, reset from all six gesture-callback bodies and both of `togglePlayback()`'s exits (plus the held-cinematic early return); `revealMobileChrome()` and the timer callback mutate a class on the cached `.mobile-cinema-scrub` ref directly — zero `render()` calls, zero structural re-renders across a full hide/reveal cycle (asserted).
- The D-30 no-trap guarantee is asserted, not just reasoned about: the first tap on hidden chrome reveals and leaves play state unchanged under both tap-to-pause settings; only the next tap pauses, and only when the preference is on.
- Full mobile+desktop suite: 44 passed (33 baseline + 11 new/extended landscape tests), zero regressions. The three frozen files (`tests/test_mobile_plumbing.py`, `web/mobile-gestures.js`, `web/style.css`) are byte-identical (`git diff --exit-code` clean).

## Task Commits

1. **Task 1: One gesture-attach lifecycle for both layouts — D-34 generalization and the landscape cinema-scrub drag** - `a888d3a` (feat)
2. **Task 2: Chrome auto-hide — the 4000ms idle timer, reveal-vs-pause semantics, and pause-reveals-and-holds** - `c31a885` (feat)

Both tasks are `tdd="true"`; tests were authored and run alongside each task's implementation (this repo's Python/pytest+Playwright suite doesn't separate RED/GREEN into distinct commits the way a unit-test-first JS suite would — each task commit carries its implementation and its own new/extended tests together, verified green before committing).

## Files Created/Modified
- `web/app.js` - `mobileScrubSurfaceEl()`, `rebuildMobileCinemaScrubTrack()`, `revealMobileChrome()`, `resetMobileChromeHideTimer()`, `attachMobileGestures()` (rename+generalize of `attachMobilePortraitGestures`), `app.mobileChromeHideTimer` state, `render()`'s widened non-desktop gesture-attach/focus-trap guard, `togglePlayback()`'s auto-hide wiring at both exits plus the held-cinematic early return
- `tests/test_mobile_landscape.py` - `test_landscape_sky_gesture_contract`, `test_landscape_cinema_scrub_drag_is_monotonic_at_every_zoom`, `test_landscape_gestures_survive_rerender_and_surface_toggle`, `test_landscape_chrome_autohide_boundary`, `test_landscape_reveal_tap_semantics`, extended `test_landscape_field_log_zero_and_empty_states`; added `SLOW_PLAYBACK_STORAGE`/`_dense_rolls_facts`/`_dense_rolls_positions_sorted`/`_tiny_default_facts`/`_facts_total_words` helpers mirroring `test_mobile_portrait.py`'s own copies

## Decisions Made
- `revealMobileChrome()`/`resetMobileChromeHideTimer()` are fully implemented in Task 1's own commit rather than stubbed until Task 2, because Task 1's `onTap` reveal branch calls them by name and a plan that left them undefined would commit a function reference with no declaration anywhere in the file. Task 2 adds only the `togglePlayback()` transition wiring and the full timing-contract tests — matching the plan's own text, which lists all six gesture-callback reset call sites under Task 1 and lists only "auto-hide wiring in `togglePlayback()`" as new under Task 2.
- A tap with tap-to-pause OFF does not reset the chrome-hide timer — the plan's action text places the reset call literally "after the existing toggle" (i.e., after `togglePlayback()`, inside the tap-to-pause-gated branch), so a genuine no-op tap doesn't touch the timer. This matches the plan's exact wording rather than a broader "every tap is activity" reading.
- Two test-only fixes, both scoped to `tests/test_mobile_landscape.py`, needed to make the auto-hide timing tests actually exercise the intended code path: (1) seeded a slower `bcf:playback:speed:v2` for every timing-sensitive test, since `tiny-default`'s whole 10000-word story finishes at the default speed inside 2 real seconds — well short of the 4000ms boundary these tests hold playback open across; (2) replaced a Playwright force-click on the auto-hidden (`pointer-events: none`) cinema-scrub FAB with a direct DOM `.click()` call, since a force-click still resolves to real screen coordinates and the browser hit-tests straight through to the sky underneath, which has its own reveal branch — the force-click version was passing for the wrong reason.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Force-clicking the auto-hidden cinema-scrub FAB tested the wrong gesture path**
- **Found during:** Task 2, while writing `test_landscape_chrome_autohide_boundary`'s "pausing while hidden reveals" assertion
- **Issue:** `.mobile-cinema-scrub.is-hidden` sets `pointer-events: none`. A Playwright `locator.click(force=True)` still dispatches a real mouse event at the element's screen coordinates; with `pointer-events: none` the browser's own hit-test routes that click through to `.mobile-sky` underneath instead of the FAB. Since chrome was hidden at that moment, the sky's own tap-to-reveal branch fired instead of `togglePlayback()` — the assertion passed by coincidence (chrome did become visible) but playback was never paused, so the later "stays visible past 4000ms more" assertion failed once the still-running playback's own reveal-triggered timer re-armed and fired again.
- **Fix:** Replaced the click with `page.evaluate("document.querySelector('.mobile-cinema-scrub-fab').click()")` — the DOM `.click()` method dispatches a real click event from that exact element, bypassing hit-testing and CSS pointer-events entirely, correctly exercising the FAB's own `toggle-playback` delegation.
- **Files modified:** tests/test_mobile_landscape.py
- **Verification:** `pytest tests/test_mobile_landscape.py -q` — full file green after the fix.
- **Committed in:** `c31a885` (Task 2 commit)

**2. [Rule 3 - Blocking] tiny-default's short story finished playback before the 4000ms auto-hide boundary**
- **Found during:** Task 2, first run of the new timing-sensitive tests (and independently while extending the no-rolls zero/empty-states case)
- **Issue:** `tiny-default`/`no-rolls` are both ~10000-word synthetic fixtures. At the app's default playback speed (5000 words/sec) the whole story plays through and auto-pauses inside 2 real seconds — well before the tests' 4000-6900ms real-time waits complete, so the FAB's aria-label (and play state generally) no longer matched what each test expected by the time its later assertions ran.
- **Fix:** Added a `SLOW_PLAYBACK_STORAGE = {"bcf:playback:speed:v2": "50"}` fixture, merged into every timing-sensitive test's seeded `localStorage`, keeping playback running for the full duration each test needs.
- **Files modified:** tests/test_mobile_landscape.py
- **Verification:** `pytest tests/test_mobile_landscape.py -q` — full file green after the fix.
- **Committed in:** `c31a885` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3, both test-only — no production code affected)
**Impact on plan:** Both fixes were necessary for the new tests to actually exercise the behavior they claim to prove. No scope creep; `web/app.js` changes match the plan's action text as written.

## Known Stubs

None — every new/modified code path (gesture-attach generalization, cinema-scrub drag, auto-hide timer) reads and writes real `app.*` state and drives real DOM mutations; no hardcoded empty value or placeholder text was introduced.

## Issues Encountered
None beyond the two auto-fixed test issues documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `attachMobileGestures()`, the auto-hide primitives, and the widened `render()` guard are all in place for Plan 03 (rotation hand-off, `onLayoutMaybeChanged()`'s landscape-arrival handling per D-31, real-device safe-area pass) to build on directly.
- Plan 03 owns: landscape arrival handling in `onLayoutMaybeChanged()` (D-31 — arriving with chrome visible and the idle timer started; D-22 mid-gesture rotation abort; the rail-width layout reset this plan's `app.mobileRailWidthLayout` write already supports).
- No blockers. The real-device iOS Safari gate (D-23) remains an explicit backstop for the phase's device-pass gate, not this plan.

---
*Phase: 03-landscape-layout*
*Completed: 2026-08-02*

## Self-Check: PASSED

All created/modified files found on disk (`web/app.js`, `tests/test_mobile_landscape.py`, this SUMMARY.md); both task commits (`a888d3a`, `c31a885`) found in git log.
