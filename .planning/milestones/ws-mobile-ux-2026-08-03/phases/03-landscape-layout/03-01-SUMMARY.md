---
phase: 03-landscape-layout
plan: 01
subsystem: ui
tags: [vanilla-js, mobile-ux, css, playwright, dom-incremental-update]

# Dependency graph
requires:
  - phase: 02-portrait-layout
    provides: renderMobilePortrait(), the surface stack (openMobileSurface/closeMobileSurface/trapMobileSurfaceFocus), the D-18 render/cache-refs/incremental-update tier, and the recentRolls()/binRolls() model helpers this plan reuses verbatim
provides:
  - renderMobileLandscape() — the landscape arm of render(), retiring the D-12 interim desktop-shell fallback
  - renderMobileSkyRegion(frame) — the D-35 sky markup shared by both mobile layouts
  - The right-rail field log (renderMobileFieldLog/renderMobileFieldLogChildren/mobileFieldLogRows) wired to recentRolls() (D-24), following the playhead through a memoized-key incremental update (updateMobileFieldLogFrame) with zero structural re-renders
  - The cinema-scrub markup (renderMobileCinemaScrub/renderMobileCinemaScrubTrackChildren) and control dock (renderMobileLandscapeSidebar)
  - Landscape CSS: 224px rail, 2/3 field-log / 1/3 control-dock split, floating cinema-scrub pill, safe-area padding on both notch edges, D-32 body scroll-lock covering both orientations
  - D-27 evidence-quote truncation (data layer) + CSS hard clamp (defense-in-depth), T-03-01 markup-safety proof
affects: [03-02, 03-03, 03-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared sky helper (D-35): renderMobileSkyRegion(frame) returns an array of children, spread into each layout's own '.mobile-sky mobile-sky-surface' wrapper — one place to fix the camera layer/focal label/tap hint/surface mount, never duplicated"
    - "Three-way render() dispatch (portrait | landscape | desktop) replacing the D-12 two-way ternary, with matching landscape branches added to cachePlaybackDomRefs() and updatePlaybackFrame() (RESEARCH Pitfall 2 — all three sites must move together or the surface renders once and goes inert)"
    - "updateMobileSkyCameraFrame(frame) factored out of updateMobilePortraitFrame() so the sky-camera key-diff exists once and is reused by updateMobileLandscapeFrame()"
    - "mobileScrubWidthDefaultForLayout()/app.mobileRailWidthLayout — a per-layout default guard around the SHARED app.mobileRailWidth/app.mobileRailBins fields, so a stale measurement from the other layout never mis-bins a scrub track for one frame after rotation"

key-files:
  created:
    - tests/test_mobile_landscape.py
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_portrait.py
    - tests/helpers/web_runtime_site.py

key-decisions:
  - "mobileFieldLogPrincipalName(roll) generalizes renderMobileFocalLabel()'s hit-only principal-perk expression to every outcome (miss/unknown rolls have no purchased/free perks, so it falls straight through to constellation then em-dash) rather than special-casing 'Miss' text — matches the Copywriting Contract's simpler {perkName || constellation || \"—\"} chain for field-log rows"
  - "updateMobileFieldLogFrame() writes the header's left label AND the cinema-scrub count span every frame (not just the count span the plan's prose calls out) — the plan's own D-26 promise ('follows the playhead') would be broken if the constellation label or the scrub's roll-count went stale between list-rebuild keys, so both are cheap per-frame textContent writes alongside the specified header count write"
  - "The landscape evidence-quote test fixture lives on a NEW dense-rolls roll (chapter 3, word 7200), not the existing long-multibyte-perk-name roll, so the two edge cases (Task 1's overlap test vs Task 2's text-containment test) stay independently seekable/bookmarkable"

patterns-established:
  - "Landscape-only class names (.mobile-app-landscape, .mobile-sidebar, .mobile-field-log*, .mobile-control-dock, .mobile-cinema-scrub*) are distinct from portrait's, so most landscape CSS sits unscoped inside the outer mobile media query rather than nested under @media (orientation: landscape) — only the sky/rail flex-split rules (genuinely differ by orientation) are nested, mirroring the file's one other orientation-scoped rule (the D-32 body lock)"

requirements-completed: [MOBL-01]

coverage:
  - id: D1
    description: "Landscape phone mounts renderMobileLandscape()'s own surface (.mobile-app/.mobile-sidebar) and never renderAppShell()'s .app/.portrait-banner or the desktop .narrative-mount — retires the D-12 interim fallback"
    requirement: "MOBL-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_tracer_renders_and_follows_playhead"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_portrait.py::test_landscape_no_longer_falls_back_to_desktop_shell"
        status: pass
    human_judgment: false
  - id: D2
    description: "The right-rail field log is built from recentRolls(wordPos, 6) (D-24) and follows the playhead through the existing incremental tier with zero structural re-renders (D-18/D-26)"
    requirement: "MOBL-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_tracer_renders_and_follows_playhead"
        status: pass
    human_judgment: false
  - id: D3
    description: "Empty states never throw or render a placeholder: zero-roll story (no-rolls package) and word-position-0 both render an em-dash-safe header with an empty/absent list"
    requirement: "MOBL-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_field_log_zero_and_empty_states"
        status: pass
    human_judgment: false
  - id: D4
    description: "Landscape layout proportions (224px rail, sky >=70% width at 844x390, field-log/dock non-overlapping and rail-contained at both in-scope viewports, top-cluster/cinema-scrub non-overlap) and the D-32 body scroll-lock covering both orientations"
    requirement: "MOBL-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_layout_proportions[844x390]"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_layout_proportions[568x320]"
        status: pass
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_body_scroll_lock_still_covers_portrait"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-27 evidence-quote truncation (~100 chars, data layer) plus a CSS hard clamp, and T-03-01 markup safety — a quote containing tag-looking characters renders as literal text with zero extra element children"
    requirement: "MOBL-01"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_landscape.py::test_landscape_field_log_text_containment"
        status: pass
    human_judgment: false
  - id: D6
    description: "Safe-area insets on notched devices (both rotation directions) and the real-device iOS Safari gate for MOBL-01's landscape surface"
    verification: []
    human_judgment: true
    rationale: "Insets resolve to 0px in the simulator and in Chrome/Android (per UI-SPEC's own backstop note) — can only be confirmed on a real notched iPhone in both rotation directions, which is the phase's D-23 device-pass gate, not this plan's automated suite"

duration: 40min
completed: 2026-08-01
status: complete
---

# Phase 3 Plan 1: Landscape tracer — layout, field log, cinema-scrub Summary

**Retired the D-12 desktop-shell landscape fallback with a real renderMobileLandscape() surface: a shared 75%-width sky beside a 224px rail (live field log over a Settings/About dock and a floating cinema-scrub pill), wired through the existing render/cache-refs/incremental-update tier so it follows the playhead with zero structural re-renders.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-08-01
- **Tasks:** 2 (Task 1: end-to-end tracer slice; Task 2: landscape CSS)
- **Files modified:** 5 (web/app.js, web/mobile.css, tests/test_mobile_landscape.py [new], tests/test_mobile_portrait.py, tests/helpers/web_runtime_site.py)

## Accomplishments
- `render()`/`cachePlaybackDomRefs()`/`updatePlaybackFrame()`'s three portrait-only branch points (RESEARCH Pitfall 2) all gained a landscape counterpart in the same commit, so the new surface is alive from its first frame — no dead/inert-looking landscape render.
- `renderMobileSkyRegion(frame)` (D-35) extracted the sky markup common to both layouts into exactly one place; `grep -c 'renderMobileSkyRegion' web/app.js` returns 5 (definition + 2 call sites + 2 doc-comment mentions).
- The field log is the ONLY new data-reading surface this plan adds, and it reads exclusively through `recentRolls(wordPos, 6)` (D-24) — `renderNarrativeReadout`/`renderRecentRolls` (§0.2 frozen, desktop-sized) are never called.
- Landscape CSS lands entirely inside the existing outer mobile media query; the D-32 body scroll-lock now covers both orientations (previously portrait-only, since the desktop-shell fallback needed to stay scrollable in landscape).
- Full mobile+desktop suite: 39 passed (33 baseline + 6 new landscape tests), zero regressions. The three frozen files (`tests/test_mobile_plumbing.py`, `web/mobile-gestures.js`, `web/style.css`) are byte-identical (`git diff --exit-code` clean).

## Task Commits

1. **Task 1: End-to-end landscape slice — render arm, shared sky helper, live field log, incremental tier** - `b5d3730` (feat)
2. **Task 2: Landscape CSS — sky/rail split, field log, control dock, cinema-scrub pill, safe areas, D-32 scroll-lock** - `167dc89` (feat)

_Task 1 is `type="tracer"` — its own `<verify>` (the two pytest/git-diff commands in the task) was re-run immediately after commit per the tracer feedback gate, both passed, and Task 2 proceeded without a checkpoint (autonomous run)._

## Files Created/Modified
- `web/app.js` - `renderMobileLandscape()`, `renderMobileSkyRegion(frame)`, `renderMobileLandscapeSidebar(frame)`, `renderMobileFieldLog()`/`renderMobileFieldLogChildren()`/`mobileFieldLogRows()`/`mobileFieldLogPrincipalName()`/`mobileFieldLogQuoteText()`/`mobileTruncate()`/`mobileFieldLogSubChildren()`, `renderMobileCinemaScrub()`/`renderMobileCinemaScrubTrackChildren()`, `updateMobileLandscapeFrame()`/`updateMobileFieldLogFrame()`/`updateMobileSkyCameraFrame()` (factored out of `updateMobilePortraitFrame()`), `mobileScrubWidthDefaultForLayout()`, landscape branches in `render()`/`cachePlaybackDomRefs()`/`updatePlaybackFrame()`/`mobileChChipText()`, `app.mobileRailWidthLayout` state, `app.frameKeys.mobileFieldLog`/`mobileCinemaScrub`
- `web/mobile.css` - D-32 un-nested body scroll-lock; `.mobile-app-landscape`/`.mobile-landscape-stage`/`.mobile-sky-landscape`/`.mobile-sidebar` (nested `@media (orientation: landscape)`); `.mobile-field-log*`, `.mobile-control-dock`/`.mobile-dock-grid`/`.mobile-dock-btn`/`.mobile-dock-status`, `.mobile-cinema-scrub*` (unscoped, mount only inside landscape DOM); extended `.mobile-rail-surface`'s comment to name its second consumer
- `tests/test_mobile_landscape.py` - new file: `test_landscape_tracer_renders_and_follows_playhead`, `test_landscape_field_log_zero_and_empty_states`, `test_landscape_layout_proportions` (parametrized x2), `test_landscape_body_scroll_lock_still_covers_portrait`, `test_landscape_field_log_text_containment`
- `tests/test_mobile_portrait.py` - `test_landscape_fallback_is_unchanged` renamed to `test_landscape_no_longer_falls_back_to_desktop_shell` and rewritten to assert the inverse contract; stray duplicated `browser.close()` removed
- `tests/helpers/web_runtime_site.py` - `LANDSCAPE_EVIDENCE_QUOTE_TEXT` (>100 chars, contains literal `<`/`>`) added to one dense-rolls roll (chapter 3, word 7200) via a new `evidence_quotes` param on `_dense_roll()`; `tiny-default`/`tiny-alt` payloads untouched

## Decisions Made
- `mobileFieldLogPrincipalName(roll)` generalizes `renderMobileFocalLabel()`'s principal-perk expression to every outcome instead of special-casing "Miss" text, matching the UI-SPEC Copywriting Contract's `{perkName || constellation || "—"}` chain for field-log rows exactly.
- `updateMobileFieldLogFrame()` writes the header's left constellation label and the cinema-scrub's count span every frame, not only the header's count span the plan's prose named — leaving either stale between list-rebuild keys would contradict D-26's "follows the playhead" promise; both are cheap textContent writes riding the same incremental pass.
- The `mobileScrubWidthDefaultForLayout()` guard is wired into `renderMobileLandscape()` and `renderMobilePortrait()` per plan, but `app.mobileRailWidthLayout` is never written to in this plan — Plan 02's ResizeObserver is what sets it. Until then every structural render (including a portrait Settings toggle) resets `app.mobileRailWidth` to its layout-appropriate default (350/200) rather than preserving the prior ResizeObserver measurement. This matches the plan's own explicit "Plan 02's ResizeObserver is what sets it... until then the layout-appropriate default is used" framing, and no committed test depends on a measured (non-default) rail width surviving a portrait re-render.
- Task 2's evidence-quote fixture uses a new dense-rolls roll (chapter 3, word 7200) rather than reusing the existing long-multibyte-perk-name roll, keeping the two edge-case tests independently seekable by bookmark.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `.mobile-field-log-header .count`'s uppercase transform broke a literal-text assertion via `inner_text()`**
- **Found during:** Task 2 (writing `test_landscape_field_log_zero_and_empty_states` against the new CSS)
- **Issue:** Task 2's `.mobile-field-log-header` CSS applies `text-transform: uppercase`. Playwright's `inner_text()` returns the RENDERED text (honoring CSS transforms), so `"0 of 2"` in the DOM read back as `"0 OF 2"`, failing the `count_text.startswith("0 of ")` assertion written in Task 1 before the CSS existed.
- **Fix:** Switched that one read to `.evaluate("el => el.textContent")` (raw DOM text, unaffected by CSS) with an explanatory comment. Every other `inner_text()` read in the same file only compares before/after equality (unaffected by a consistent transform), so those were left unchanged.
- **Files modified:** tests/test_mobile_landscape.py
- **Verification:** `pytest tests/test_mobile_landscape.py -q` — full file green after the fix.
- **Committed in:** `167dc89` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test-only fix, no production code affected. No scope creep.

## Known Stubs

None — this plan's field log/cinema-scrub/control-dock all read real `app.data`/`app.wordPos` state through `recentRolls()`; no hardcoded empty value or placeholder text flows to rendering.

## Issues Encountered
None beyond the auto-fixed test issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `renderMobileLandscape()`, the shared sky helper, the field log's D-24 data seam, and the render/cache-refs/incremental-update dispatch trio are all in place for Plan 02 (gestures + chrome auto-hide) and Plan 03 (rotation hand-off, safe-area device pass) to build on directly.
- Plan 02 owns: renaming/generalizing `attachMobilePortraitGestures` to `attachMobileGestures` (D-34), wiring `attachRailScrub` against `.mobile-cinema-scrub-track`, the chrome auto-hide idle timer, and setting `app.mobileRailWidthLayout` from the cinema-scrub's ResizeObserver.
- The `.mobile-cinema-scrub.is-hidden` CSS variant is already defined (Task 2) so Plan 02's auto-hide toggle has no CSS work left to do — only the `classList.toggle` wiring.
- No blockers. The real-device iOS Safari safe-area gate (D6 above) remains an explicit backstop for the phase's D-23 device-pass gate, not this plan.

---
*Phase: 03-landscape-layout*
*Completed: 2026-08-01*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`b5d3730`, `167dc89`) found in git log.
