---
phase: 02-portrait-layout
plan: 03
subsystem: ui
tags: [vanilla-js, css, playwright, resize-observer, mobile-scrubber]

requires:
  - phase: 02-portrait-layout
    plan: 02
    provides: "Portrait gesture callbacks, attachMobilePortraitGestures lifecycle, dock speed cycle, tap hint — the mini-rail scrub path (attachRailScrub/panOffsetForPlayhead/mobileInnerFraction) already wired"
provides:
  - "Cluster-binned mini-rail: MIN_DOT_SPACING_PX/binRolls/finalizeBin/binSize ported verbatim from design/mobile-ux/prototype/scrubber.jsx, reading the live word_position/outcome schema"
  - "recomputeMobileRailBins() cached on app.mobileRailBins, recomputed only on structural render, zoom change, and a rAF-coalesced ResizeObserver callback — never on a playback frame (D-18)"
  - "renderMobileRailRollsLaneChildren(): POV bands + cluster bins + a single always-on-top active diamond, shared between the initial build and later partial rebuilds"
  - "updateMobileActiveDotFrame(): keyed style.left write moves the active roll's marker without rebuilding the lane"
  - "window.__bcfMobile now exposes binRolls/binSize/panOffsetForPlayhead/mobileInnerFraction read-only for direct test assertions"
  - "ResizeObserver on .mobile-rail keeps app.mobileRailWidth current; setMobileTimelineZoom recomputes bins and re-renders on every zoom change; .mobile-rail-inner gets the prototype's 220ms ease transform transition"
affects: [02-04-settings-flyouts]

tech-stack:
  added: []
  patterns:
    - "Cluster-bin split comparison is against the CURRENTLY OPEN bin's firstWord (cumulative from bin start), not the immediately preceding roll — a verbatim port of the prototype's `r.wordPosition - cur.firstWord > minWords`, not a pairwise-adjacent-gap merge"
    - "Bin recomputation has exactly three call sites (structural render, zoom setter, rail ResizeObserver) and is explicitly excluded from the playback frame path (D-18)"
    - "Rolls-lane children are built by one shared function (renderMobileRailRollsLaneChildren) reused by the initial structural build and the ResizeObserver's partial replaceChildren rebuild — never a third copy of the markup"

key-files:
  created: []
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_portrait.py
    - tests/helpers/web_runtime_site.py

key-decisions:
  - "Tightened the dense-rolls fixture's 8-roll cluster span from 280 words (40-word gaps) to 70 words (10-word gaps): binRolls' split test compares each roll against the bin's FIRST member, not its neighbor, so the original spacing exceeded minWords partway through a real ~300-370px rail width and split into two 4-roll bins instead of merging into the single badge-worthy cluster the fixture's own comment promised. This is a fixture correction, not an algorithm change — binRolls itself is a verbatim port of the prototype."
  - "Added a dedicated `no-rolls` test package (chapters present, zero rolls anywhere) for the UI-SPEC empty-zero-rolls truth — tiny-default carries two real rolls elsewhere in the story and cannot exercise a genuinely zero-roll rail."
  - "Read-position assertions in test_rail_scrub_zoom_aware go through localStorage's `bcf:bookmark:word_position` key (written synchronously by persistBookmarkNow on a rail press's pointerup) and the staged package's own JSON for total_words, rather than a bare `app.wordPos`/`app.data.story.total_words` — web/app.js is loaded `<script type=\"module\">`, so its top-level `app` binding is module-scoped and NOT reachable from page.evaluate()'s global realm. window.__bcfMobile IS reachable (a real `window` property) and used directly for the pure-function assertions."

requirements-completed: [MOBP-03, MOBP-04]

coverage:
  - id: D1
    description: "At 1x the mini-rail collapses tight clusters into counted bin markers, coloured by dominant outcome, instead of a smear of overlapping dots"
    requirement: "MOBP-04"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_cluster_binning_at_1x"
        status: pass
    human_judgment: false
  - id: D2
    description: "The active roll always renders as its own cyan diamond drawn on top of the bins, even when its word position falls inside a merged bin's span, and moves on scrub while bin positions stay fixed"
    requirement: "MOBP-04"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_cluster_binning_at_1x"
        status: pass
    human_judgment: false
  - id: D3
    description: "binRolls' strict split comparison, binSize's floor/cap, and empty-input short-circuits match the ported algorithm exactly; dominant-outcome tie-break (hit > miss > unknown)"
    requirement: "MOBP-04"
    verification:
      - kind: unit
        ref: "tests/test_mobile_portrait.py#test_bin_threshold_and_size_boundaries"
        status: pass
    human_judgment: false
  - id: D4
    description: "Cluster bins recompute only on structural render, zoom change, or rail resize — never on a playback frame"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_cluster_binning_at_1x"
        status: pass
    human_judgment: false
  - id: D5
    description: "With zero rolls in the data the rail still renders chapter ticks, POV bands and playhead with no bins and no active diamond, and does not throw"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_cluster_binning_at_1x"
        status: pass
    human_judgment: false
  - id: D6
    description: "Dragging the mini-rail lands the playhead on the word position under the finger at zoom 1, 2, 4 and 8, including auto-panned positions; auto-pan stays clamped to [0, (zoom-1)*100]; a fraction of 0/1 resolves to word 0/total_words"
    requirement: "MOBP-03"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_rail_scrub_zoom_aware"
        status: pass
    human_judgment: false
  - id: D7
    description: "Zoom 4x sets the rail inner's inline width to 400% and the hint row reports the zoom segment; there is exactly one .mobile-rail element and a forced layout-mode round trip never leaves a stale duplicate scrub listener behind"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_rail_scrub_zoom_aware"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-07-26
status: complete
---

# Phase 2 Plan 3: Cluster-Binned Mini-Rail + Zoom-Aware Scrub Summary

**Mini-rail rolls collapse into counted, dominant-outcome-coloured cluster bins at 1x (900-odd rolls become a handful of markers), the active roll always stands out as its own cyan diamond, and dragging lands exactly on the word under the finger at 1x/2x/4x/8x with clamped auto-pan.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-07-26T19:11:00-04:00 (approx, following 02-02's completion)
- **Completed:** 2026-07-26T20:01:00-04:00 (approx)
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `MIN_DOT_SPACING_PX`/`binRolls`/`finalizeBin`/`binSize` ported verbatim from `design/mobile-ux/prototype/scrubber.jsx` into `web/app.js`, reading the live `word_position`/`outcome` schema instead of the prototype's camelCase fields — the split comparison is a strict `>` against the currently-open bin's first member (cumulative-from-bin-start, not pairwise-adjacent), exactly matching the prototype's own algorithm.
- `recomputeMobileRailBins()` caches bins on `app.mobileRailBins`, called from exactly three places (structural render, `setMobileTimelineZoom`, and the rail's `ResizeObserver`) — proven never to run during a live 1.5s playback window (`structuralRenders` stays 0, bin count unchanged).
- `renderMobileRailRollsLaneChildren()` replaces the Plan 02-01 one-dot-per-roll rendering with POV bands + cluster bins + a single always-on-top active diamond, shared between the initial structural build and the ResizeObserver's partial `replaceChildren` rebuild.
- `updateMobileActiveDotFrame()` moves the active roll's marker via a keyed `style.left` write in the incremental frame tier, so playback/scrub never rebuilds the lane to move it.
- A `ResizeObserver` on `.mobile-rail` keeps `app.mobileRailWidth` current (rAF-coalesced), and `setMobileTimelineZoom` now recomputes bins and issues a structural render on every zoom change; `.mobile-rail-inner` carries the prototype's 220ms ease transform transition.
- `window.__bcfMobile` now exposes `binRolls`/`binSize`/`panOffsetForPlayhead`/`mobileInnerFraction` read-only, letting tests assert the numeric contract directly.
- Verified: a single press at 25% of the rail lands within 1 word of the independently-computed target at zoom 1/2/4/8; extreme-left/right presses land exactly on word 0/`total_words` at every zoom; `panOffsetForPlayhead`/`mobileInnerFraction` boundary values match the ported formulas exactly.

## Task Commits

1. **Task 1: Cluster binning — merged markers, count badges, active diamond on top** - `98626cd` (feat)
2. **Task 2: Zoom-aware scrub at 1x/2x/4x/8x with clamped auto-pan** - **BLOCKED, not yet committed** (see Deviations/Issues below — changes are complete, tested, and staged in the working tree)

**Plan metadata:** _(pending — blocked on the same issue as Task 2)_

## Files Created/Modified

- `web/app.js` — `MIN_DOT_SPACING_PX`, `binRolls`, `finalizeBin`, `binSize`, `recomputeMobileRailBins`, `renderMobileRailBinEl`, `renderMobileRailRollsLaneChildren`, `updateMobileActiveDotFrame`; `renderMobilePortrait()`'s bin-recompute call; `renderMobileScrubber()` rewired onto the shared rolls-lane-children function; `setMobileTimelineZoom` recompute+render; the rail `ResizeObserver` install/teardown in `attachMobilePortraitGestures`; `window.__bcfMobile` bridge extension; new `app` state fields (`mobileRailWidth`, `mobileRailBins`, `mobileRailResizeObserver`) and `app.dom.mobileRailRollsLane`/`app.frameKeys.mobileActiveDot`.
- `web/mobile.css` — `.mobile-roll-bin`/`.mobile-roll-bin .count` styling (amber/hit/miss, z-index below the active dot); removed the now-dead `.mobile-roll-dot.hit`/`.miss` rules (only the always-active variant renders); `.mobile-rail-inner`'s 220ms ease transform transition.
- `tests/test_mobile_portrait.py` — `test_cluster_binning_at_1x`, `test_bin_threshold_and_size_boundaries`, `test_rail_scrub_zoom_aware`, plus `_tiny_default_facts`/`_facts_total_words` helpers.
- `tests/helpers/web_runtime_site.py` — tightened the dense-rolls cluster spacing (280→70-word span) so the 8-roll cluster actually merges at real rail widths; added the `no-rolls` fixture package (chapters present, zero rolls anywhere).

## Decisions Made

- **Dense-rolls cluster spacing fix:** the `binRolls` split test compares each roll's position against the bin's FIRST member (cumulative from bin start), not the immediately preceding roll. The fixture's original 40-word gaps (280-word total span) exceeded `minWords` (~135-167 words at real rail widths) partway through, splitting the intended single 8-roll cluster into two 4-roll bins and silently failing the fixture's own documented intent ("merges into one bin at 390px width"). Tightened to 10-word gaps (70-word span), which merges with comfortable margin at both 390px and 320px rail widths. This is a fixture correction; `binRolls` itself is an unmodified verbatim port.
- **`no-rolls` test fixture:** the UI-SPEC "empty-zero-rolls" truth requires a story with real chapters (so ticks/POV bands render) but zero rolls anywhere — `tiny-default` has two real rolls elsewhere in the story and cannot exercise this; added a dedicated fixture rather than skip the truth.
- **Test read-path via localStorage/JSON, not `app.*`:** `web/app.js` is loaded `<script type="module">`, so top-level `app` is module-scoped and invisible to `page.evaluate()`'s global realm. `test_rail_scrub_zoom_aware` reads the post-scrub word position from `localStorage`'s `bcf:bookmark:word_position` key (written synchronously on a rail press's `pointerup`) and reads `total_words` from the staged package's JSON, while still using `window.__bcfMobile` directly for the exposed pure functions (a real `window` property, unaffected by module scoping).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dense-rolls fixture's cluster span didn't actually merge into one bin at real rail widths**
- **Found during:** Task 1 (writing `test_cluster_binning_at_1x` against the live `dense-rolls` package)
- **Issue:** The fixture's 8-roll cluster (offsets 3100-3380, 40-word gaps) was documented as "merges into one bin at 390px width and 1x zoom", but `binRolls`' split comparison (`roll.word_position - cur.firstWord > minWords`) is cumulative from the bin's first member, not pairwise-adjacent. At a real measured rail width of ~366px (`minWords` ≈ 137), the cluster split into two 4-roll bins partway through, producing zero count-badge-worthy bins (`binSize(4)` = 8, under the 10px badge floor) instead of the intended single 8-roll cluster with a visible "8" badge.
- **Fix:** Tightened `cluster_offsets` to 10-word gaps (70-word total span), comfortably under `minWords` at every rail width this phase's viewports produce (390px and 320px).
- **Files modified:** `tests/helpers/web_runtime_site.py`
- **Verification:** `test_cluster_binning_at_1x` passes — exactly one `.mobile-roll-bin .count` badge reads "8".
- **Committed in:** `98626cd` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 fixture bug)
**Impact on plan:** Necessary for the fixture to actually exercise the merge behavior its own comment promised; no change to the ported `binRolls`/`finalizeBin`/`binSize` algorithm itself.

## Known Stubs

None — both tasks' `<verify>` criteria are fully wired and tested; no placeholder data paths remain in the rail.

## Issues Encountered

**BLOCKING: Task 2's commit and all downstream git-writing steps (state updates' git-touching parts, final metadata commit) could not complete — the local 1Password SSH-signing agent is wedged.**

- Task 1's commit (`98626cd`) succeeded normally.
- Task 2's file changes (ResizeObserver install/teardown, `setMobileTimelineZoom` recompute+render, `.mobile-rail-inner` transition, `test_rail_scrub_zoom_aware` + helpers) are complete, fully tested (all 12 tests in `tests/test_mobile_portrait.py` pass, plus `tests/test_mobile_plumbing.py`/`tests/test_desktop_smoke.py` regression-clean), staged in the working tree (`git add` already run), but **`git commit` repeatedly fails** with:
  ```
  error: 1Password: agent returned an error
  fatal: failed to write commit object
  ```
- Diagnosed directly (not assumed): a raw `ssh-keygen -Y sign` test against the configured signing key failed with `agent refused operation` / `communication with agent failed`, and `op whoami` / `op vault list` hung and had to be killed after timing out. This confirms the 1Password desktop app's SSH agent is unresponsive on this machine right now — a local environment issue, not a code or plan issue. The project's `git config` requires SSH-format commit signing (`gpg.format=ssh`, `commit.gpgsign=true`); per the mandatory git safety protocol, signing must never be bypassed (no `--no-verify`, no `-c commit.gpgsign=false`) even to work around this.
- **This is a `checkpoint:human-action` condition**, not a plan defect: the user needs to restart or unlock the 1Password desktop app (its SSH-agent helper is unresponsive — `op whoami` times out), after which the following resumes exactly where it left off:
  ```bash
  cd /Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc
  git commit -m "$(cat <<'EOF'
  feat(02-03): zoom-aware rail auto-pan tracks live rail width (MOBP-03)

  - ResizeObserver on .mobile-rail (installed/torn down in
    attachMobilePortraitGestures, same defensive-teardown discipline as the
    gesture slots) keeps app.mobileRailWidth current and recomputes bins on
    resize, rAF-coalesced, replacing only the rolls lane's children — never
    calling render().
  - setMobileTimelineZoom now recomputes bins and issues a structural render
    on every zoom change, since pxWidth (railWidth * zoom) depends on it.
  - .mobile-rail-inner gets the prototype's 220ms ease transform transition.
  - The scrub conversion itself (onScrub -> panOffsetForPlayhead ->
    mobileInnerFraction -> setWordPos) was already wired by Plan 02-01/02-02
    as the single attachRailScrub input path; this task adds the missing
    bin/width feedback loop around it and proves 1x/2x/4x/8x land on the word
    under the finger including auto-panned positions.

  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  EOF
  )"
  ```
  Verification after it succeeds: `git log --oneline -3` should show the new Task 2 commit above `98626cd`.
- Everything downstream of this commit (STATE.md/ROADMAP.md updates and the final `docs(02-03): complete ...` metadata commit) is also blocked on the same signing agent, since those steps write their own commits.

## User Setup Required

**Yes — see the BLOCKING item above.** Restart or unlock the 1Password desktop app to clear its wedged SSH-signing agent, then run the `git commit` command given above from this worktree. No other external service configuration is required.

## Next Phase Readiness

- Both of this plan's tasks are code-complete and fully verified by tests (`tests/test_mobile_portrait.py` — 12/12 pass; `tests/test_mobile_plumbing.py`/`tests/test_desktop_smoke.py` regression-clean). Plan 02-04 (Settings/About/Help flyouts) can proceed once Task 2's commit lands — no rework needed, only the git-signing environment issue stands between "code done" and "plan fully closed out."
- `app.mobileSurface`'s guard (wired defensively since Plan 02-02) is unaffected by this plan; Plan 02-04 still only needs to set the field when an overlay opens.
- Real iOS Safari verification remains an explicit backstop item for the Phase B gate review with Dre (unchanged from prior plans in this phase).

---
*Phase: 02-portrait-layout*
*Completed: 2026-07-26*

## Self-Check: PARTIAL

- All created/modified files verified present on disk: `web/app.js`, `web/mobile.css`, `tests/test_mobile_portrait.py`, `tests/helpers/web_runtime_site.py`, this SUMMARY.md.
- Task 1 commit `98626cd` verified present in `git log --oneline --all`.
- Task 2's changes are staged (`git add` complete, `git status` shows them modified/staged) but **not yet committed** — `git commit` fails repeatedly with `1Password: agent returned an error` / `fatal: failed to write commit object`, confirmed as a genuine local SSH-signing-agent wedge (not a code issue) via a direct `ssh-keygen -Y sign` test and a timed-out `op whoami`. See "Issues Encountered" above for the exact resume command.
- No files were force-added or committed with signing bypassed, per the mandatory git safety protocol.
