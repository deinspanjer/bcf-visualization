---
phase: 01-mobile-state-gesture-plumbing
plan: 03
subsystem: testing
tags: [playwright, pytest, desktop-smoke, breakpoint, D-10, regression-gate]

requires:
  - phase: 01-mobile-state-gesture-plumbing (plan 01)
    provides: "window.__bcfLayoutMode mirror, MOBILE_LAYOUT_QUERY breakpoint semantics"
  - phase: 01-mobile-state-gesture-plumbing (plan 02)
    provides: "web/mobile.css foundation, D-02 pause-on-hidden — verified untouched by desktop viewports in this plan"
provides:
  - "tests/test_desktop_smoke.py — the D-10 phase-gate artifact: 6 pytest+Playwright tests scripting the INTEGRATION_PLAN §0.5 six-step manual desktop-freeze checklist"
  - "Structural-render + layout-mode boundary matrix pinning zero re-renders within the desktop range and exactly one re-render per breakpoint crossing"
affects: [01-04, all future Track A phase gates (Phases 2-4 re-run this test unchanged)]

tech-stack:
  added: []
  patterns:
    - "Desktop smoke test is a peer module to tests/test_web_app_integration.py, reusing its _chromium_browser_or_skip / _page_with_console_capture helpers rather than a shared conftest — matches the existing per-module convention"
    - "Breakpoint truth is asserted against the media-query contract (web/style.css:360), not the looser §0.5 prose — 1100x900 landscape is desktop, only the portrait axis engages the 1100px bound"

key-files:
  created:
    - tests/test_desktop_smoke.py
  modified: []

key-decisions:
  - "§0.5 step 3's 'roll #47' is adapted to 'the last roll in the fixture dataset' — the synthetic tiny-default package has a small roll count; the behavior under test (scrub-to-roll centers its constellation card) is data-size-independent, documented inline in the test module"
  - "Boundary matrix asserts the counter-intuitive pair explicitly: 1100x900 stays desktop (landscape, width > 900) while 1100x1300 is portrait — the 1100px upper bound only engages in portrait orientation per web/style.css:360, not the flatter '1100px and below is mobile' reading of the §0.5 prose"

requirements-completed: [MOBF-06]

coverage:
  - id: D1
    description: "Desktop shell at >= 1100px renders header/scrubber/stat-strip/field-log with no portrait banner, playback advances, carousel focuses scrubbed-to roll, Details mode renders roll log (§0.5 steps 1-4)"
    requirement: MOBF-06
    verification:
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_static_shell_renders_full_shell_with_no_portrait_banner"
        status: pass
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_playback_advances_and_cinematic_fires_on_roll"
        status: pass
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_carousel_focuses_last_fixture_roll_via_scrub"
        status: pass
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_details_mode_renders_full_roll_log"
        status: pass
    human_judgment: false
  - id: D2
    description: "Resizing within the desktop range (1920px down to 1101px) causes zero structural re-renders and no layout-mode change; crossing the breakpoint flips mobile behavior on and back off cleanly with no console errors (§0.5 steps 5-6)"
    requirement: MOBF-06
    verification:
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_range_resizes_cause_zero_rerenders_while_crossings_flip_layout_mode"
        status: pass
      - kind: e2e
        ref: "tests/test_desktop_smoke.py#test_desktop_restores_cleanly_after_full_resize_round_trip"
        status: pass
    human_judgment: false
  - id: D3
    description: "The D-10 gate artifact is re-runnable on demand and passes together with the existing mobile-plumbing and desktop-integration suites"
    verification:
      - kind: e2e
        ref: ".venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q (6 passed)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_web_app_integration.py -q (36 passed)"
        status: pass
    human_judgment: false

duration: 1h50min (includes a human-action checkpoint pause for a 1Password SSH-signing helper stall; active work time was well under 30min across the two execution sessions)
completed: 2026-07-26
status: complete
---

# Phase 1 Plan 03: Desktop Smoke Test (D-10 Gate) Summary

**tests/test_desktop_smoke.py scripts the INTEGRATION_PLAN §0.5 six-step manual desktop-freeze checklist into 6 pytest+Playwright tests — static shell render, playback, carousel focus, Details mode, a breakpoint boundary matrix, and a clean-restore round trip — giving every future Track A phase gate a `pytest -x -q` exit code instead of a manual claim.**

## Performance

- **Duration:** 1h50min wall clock (a human-action checkpoint for a wedged 1Password SSH commit-signing helper paused execution mid-plan; active execution time was well under 30 minutes)
- **Started:** 2026-07-25T23:09:xx
- **Completed:** 2026-07-26T11:00:18-04:00
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments

- New `tests/test_desktop_smoke.py` (331 lines, 6 test functions) — a self-contained peer module to `tests/test_web_app_integration.py`, reusing its `_chromium_browser_or_skip`/`_page_with_console_capture` conventions, default viewport 1920x1080, path `/web/?dataPackage=tiny-default`.
- Steps 1-4 (Task 1): static-shell render with zero `.portrait-banner.is-visible` and empty console; Play/Pause toggling with a bounded-wait playhead-advance assertion; scrub-to-last-fixture-roll centers/focuses its constellation card in the carousel (documented adaptation of §0.5's "roll #47" for the small synthetic fixture); Details-mode toggle renders one roll-log row per fixture roll.
- Steps 5-6 (Task 2): a breakpoint boundary matrix using `window.__bcfRenderStats.structuralRenders` and `window.__bcfLayoutMode` — confirms 1101x900 and the counter-intuitive 1100x900 (landscape) both stay `"desktop"` with zero re-renders across in-range resizes, while 1100x1300 and 899x900 flip to `"portrait"` with the `.portrait-banner` appearing and exactly one structural re-render per crossing; a full 1920 -> 899x900 -> 1920x1080 round trip ends back at `"desktop"`, banner-hidden, `structuralRenders == 2`, console-clean.
- Every test asserts `console_messages == []`.
- Full quick command `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q` passes (6 passed); combined with `tests/test_mobile_plumbing.py` and `tests/test_web_app_integration.py`, all 36 tests across the three web suites pass together.

## Task Commits

1. **Task 1: Smoke steps 1-4 — static render, playback, carousel focus, details mode** - `66e9e1c` (test)
2. **Task 2: Smoke steps 5-6 — breakpoint boundary matrix and clean desktop restore** - `d2b61fd` (test)

**Plan metadata:** (this commit) - `docs(01-03): complete desktop smoke test plan`

## Files Created/Modified

- `tests/test_desktop_smoke.py` - New file: the D-10 phase-gate artifact scripting INTEGRATION_PLAN §0.5's six-step desktop-freeze checklist

## Decisions Made

- `§0.5` step 3's "roll #47" adapted to "the last roll in the fixture dataset" since the synthetic `tiny-default` package has a small roll count — the assertion under test (scrub-to-roll centers the carousel card) is data-size-independent; documented inline with a comment citing this plan.
- Boundary matrix explicitly pins the orientation-dependent breakpoint behavior (1100x900 landscape stays desktop; only 1100x1300 portrait crosses) rather than the flatter "1100px and below is mobile" reading of the §0.5 prose, matching the actual media-query contract at `web/style.css:360`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Human-action checkpoint:** after Task 2's code was written, staged, and fully verified, the commit attempt failed because the 1Password SSH commit-signing helper (`op-ssh-sign`) was wedged. This is a genuine auth/tooling gate, not a plan or code deviation — no plan tasks were reordered or skipped. The user resolved the 1Password helper out-of-band; the orchestrator verified signing worked again via a direct `op-ssh-sign` probe before resuming this continuation. Task 2 was committed on resume with no code changes (the staged diff was verified byte-identical to what had passed verification before the pause).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The D-10 gate artifact (`tests/test_desktop_smoke.py`) is complete and is the standing regression gate Phases 2-4 re-run unchanged at their §5 Track A gates.
- MOBF-06 satisfied; the desktop-freeze constraint (PROJECT.md core value) now has a mechanical enforcement point.
- Ready for 01-04.

## Self-Check: PASSED

- `tests/test_desktop_smoke.py` exists on disk (331 lines, 6 test functions)
- Task commits present in git log: `66e9e1c`, `d2b61fd`
- `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q` re-run green: 6 passed
- `.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_web_app_integration.py -q` re-run green: 36 passed

---
*Phase: 01-mobile-state-gesture-plumbing*
*Completed: 2026-07-26*
