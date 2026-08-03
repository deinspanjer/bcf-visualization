---
phase: 04-mobile-cutover-accessibility
plan: 01
subsystem: ui
tags: [css, dom-deletion, freeze-proof, localStorage, playwright, pytest]

requires:
  - phase: 03-landscape-layout
    provides: "the stable mobile portrait/landscape shell that made the rotate-to-landscape banner obsolete"

provides:
  - "web/app.js and web/style.css with the rotate-to-landscape banner deleted end-to-end (render function, call site, storage constant, state field, migration entry, CSS rules)"
  - "tests/test_freeze_proof.py — a committed, repeatable whole-milestone freeze gate (git-diff-wrapped, no browser dependency)"
  - "web/style.css's whole-milestone diff against 57d2768 proven deletion-only (0 added lines)"

affects: [04-02, 04-03, 04-04, 04-05]

tech-stack:
  added: []
  patterns:
    - "Freeze-proof pytest module wraps `git diff`/`git rev-parse` via subprocess, asserts on returncode/stdout explicitly, never skips — a new test shape alongside the existing Playwright-only suite"
    - "File-appropriate base commit selection for freeze proofs: artifacts that predate the milestone diff against the pre-milestone base; artifacts a specific phase created diff against the base commit immediately after that phase closed"

key-files:
  created:
    - tests/test_freeze_proof.py
  modified:
    - web/app.js
    - web/style.css
    - tests/test_desktop_smoke.py
    - tests/test_mobile_plumbing.py

key-decisions:
  - "Used two base commits in tests/test_freeze_proof.py (57d2768 for web/style.css, 1351450 for web/mobile-gestures.js and web/index.html's mobile tags) instead of the plan's single-constant design, because the latter two artifacts did not exist at the pre-Phase-1 base — Phase 1 itself created them"
  - "STORAGE_VERSION left unchanged at \"3\"; the orphaned bcf:portrait-dismissed key is left un-purged by design per RESEARCH Pitfall 5"

patterns-established:
  - "Deletion-only frozen-CSS edits are verified with `git diff --numstat` asserting added==0 and deleted>0 against a pinned base commit, not a subjective diff review"

requirements-completed: [MOBX-01]

coverage:
  - id: D1
    description: "Rotate-to-landscape banner deleted end-to-end: renderPortraitBanner(), its renderAppShell() call site, LS_PORTRAIT_DISMISSED, app.portraitDismissed, and the migratePreviewStorage() clear-list entry are all gone; no banner element exists in the DOM at desktop, portrait, or landscape widths"
    requirement: MOBX-01
    verification:
      - kind: integration
        ref: "tests/test_desktop_smoke.py::test_desktop_static_shell_renders_full_shell_with_no_portrait_banner"
        status: pass
      - kind: integration
        ref: "tests/test_desktop_smoke.py::test_desktop_restores_cleanly_after_full_resize_round_trip"
        status: pass
      - kind: other
        ref: "grep -c 'renderPortraitBanner|LS_PORTRAIT_DISMISSED|portraitDismissed' web/app.js == 0; grep -c 'portrait-banner' web/style.css == 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "web/style.css's whole-milestone diff (vs. pre-Phase-1 commit 57d2768) is deletion-only — 0 added lines, non-zero deleted lines — the milestone's one sanctioned frozen-CSS edit"
    requirement: MOBX-01
    verification:
      - kind: other
        ref: "git diff --numstat 57d2768 HEAD -- web/style.css"
        status: pass
      - kind: integration
        ref: "tests/test_freeze_proof.py::test_style_css_diff_against_whole_milestone_base_is_deletion_only"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/test_freeze_proof.py committed as a standing, non-skippable pytest gate proving web/mobile-gestures.js byte-identical, the style.css deletion-only diff, the deleted selector's absence from both served stylesheets, and web/'s continued dependency-free/build-step-free status"
    requirement: MOBX-01
    verification:
      - kind: integration
        ref: "pytest tests/test_freeze_proof.py -x -q (4 items collected, all pass)"
        status: pass
    human_judgment: false
  - id: D4
    description: "STORAGE_VERSION stays at \"3\"; bcf:portrait-dismissed is no longer purged by migratePreviewStorage() and survives untouched as inert dead data, avoiding a 34-fixture-site rewrite for zero functional gain"
    requirement: MOBX-01
    verification:
      - kind: integration
        ref: "tests/test_mobile_plumbing.py::test_storage_version_bump_purges_stale_keys"
        status: pass
      - kind: other
        ref: "git diff 57d2768 HEAD -- web/app.js | grep -c STORAGE_VERSION == 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "Device confirmation that portrait genuinely stands on its own with no residual gap where the banner used to sit (FA-MOBX-01 criterion 5)"
    verification: []
    human_judgment: true
    rationale: "FA-MOBX-01 is an unresolved flagged assumption explicitly carried to the Phase D+E gate for Dre's ruling; the planner marked it must-not-be-closed-by-an-agent. This plan implements and proves the automatable criteria (1-4) but the reader-facing consequence (criterion 5) requires a human on a real device."

duration: 25min
completed: 2026-08-02
status: complete
---

# Phase 4 Plan 1: Rotate-to-Landscape Banner Deletion & Whole-Milestone Freeze Proof Summary

**Deleted the rotate-to-landscape banner end-to-end from web/app.js and web/style.css, then committed a repeatable pytest freeze proof confirming desktop stays byte-identical to the pre-Phase-1 base commit.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments
- Removed `renderPortraitBanner()`, its `renderAppShell()` call site, `LS_PORTRAIT_DISMISSED`, `app.portraitDismissed`, and its `migratePreviewStorage()` clear-list entry from `web/app.js` — five deletions, no rewrites
- Deleted the `.portrait-banner` rule block and the stale `@media (max-width: 900px), …` wrapper from `web/style.css`, verified deletion-only (0 added lines) against the pre-Phase-1 base commit `57d2768`
- Restated `tests/test_desktop_smoke.py`'s two banner assertions from CSS-hidden checks to DOM-absence checks (`document.querySelector('.portrait-banner') is None`)
- Committed `tests/test_freeze_proof.py` — a new, non-skippable pytest module wrapping `git diff`/`git rev-parse` that will rerun the whole-milestone freeze claim at every future gate instead of relying on one-off shell commands

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete the rotate banner end-to-end** - `1f965d9` (feat)
2. **Task 2: Commit the whole-milestone freeze proof** - `8309761` (test)

## Files Created/Modified
- `web/app.js` - Five deletion sites: banner call site, render function, state field, migration entry, storage constant
- `web/style.css` - `.portrait-banner` rule block + stale media wrapper deleted (38 lines removed, 0 added)
- `tests/test_desktop_smoke.py` - Two banner assertions restated as DOM-absence checks with updated comments
- `tests/test_mobile_plumbing.py` - Version-bump migration test updated: `bcf:portrait-dismissed` now asserted to survive (no longer purged, by design)
- `tests/test_freeze_proof.py` - New: 4-test freeze-proof module (mobile-gestures.js byte-identity, style.css deletion-only diff, deleted-selector absence, web/ dependency-free check)

## Decisions Made
- Kept `STORAGE_VERSION` at `"3"` — bumping it to purge the now-orphaned `bcf:portrait-dismissed` key would wipe every `bcf:*` preference for a returning reader and require rewriting 34 seeded test-fixture sites across 4 files, for a key that has zero functional impact once nothing reads it (RESEARCH Pitfall 5, plan `must_haves.prohibitions`)
- Used two base commits in the freeze-proof test rather than the plan's single-constant design — see Deviations below

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a factually-impossible git-diff base commit in the freeze proof's design for two artifacts**
- **Found during:** Task 2 (writing `tests/test_freeze_proof.py`)
- **Issue:** The plan's `<action>`/`<behavior>` for Task 2 specified diffing `web/mobile-gestures.js` and `web/index.html`'s mobile `<script>`/`<link>` tags against the single whole-milestone base `57d2768` (pre-Phase-1). Direct verification showed both artifacts were *created during Phase 1 itself* (`git log --follow -- web/mobile-gestures.js` shows exactly one commit, `3034d90`, which postdates `57d2768`). Diffing against `57d2768` reports the entire file as newly added (`git diff --exit-code 57d2768 HEAD -- web/mobile-gestures.js` returns exit 1, confirmed directly), not "unchanged" — a test written exactly as specified would fail on its very first run and could never pass, defeating Task 2's own acceptance criterion that the module exit 0.
- **Fix:** Used `57d2768` only for `web/style.css` (the artifact that genuinely predates the milestone, and the one MOBX-01's whole-milestone claim is actually about). Used `1351450` (the pre-Phase-2 base — i.e., the commit immediately after Phase 1 closed) for `web/mobile-gestures.js` and `web/index.html`'s mobile tag diff, matching the exact base every prior phase's own freeze-proof record (`02-05-SUMMARY.md`, `03-04-SUMMARY.md`) already used for this same file before this plan formalized the practice as a standing gate. The acceptance criteria's `grep -c '22bdd8c' == 0` constraint (the phase-local base must not appear) is still satisfied — `1351450` is a different commit, and `22bdd8c` does not appear anywhere in the file.
- **Files modified:** `tests/test_freeze_proof.py`
- **Verification:** `pytest tests/test_freeze_proof.py -x -q` — 4/4 pass; manually confirmed the edge case (an unresolvable SHA fails loudly naming the SHA, not skip) by temporarily setting `WHOLE_MILESTONE_BASE` to a garbage value, observing the named failure, then reverting before commit.
- **Committed in:** `8309761` (Task 2 commit)

**2. [Rule 3 - Blocking] Updated a pre-existing test asserting the now-removed migration purge of `bcf:portrait-dismissed`**
- **Found during:** Task 1 verification (`pytest tests/test_mobile_plumbing.py`)
- **Issue:** `test_storage_version_bump_purges_stale_keys` (pre-existing, not in this plan's file scope) asserted `localStorage.getItem('bcf:portrait-dismissed') is None` after a version-bump migration, because Phase 1 originally put `LS_PORTRAIT_DISMISSED` in `migratePreviewStorage()`'s clear-list. Task 1 removes that constant from the clear-list entirely (per RESEARCH Pitfall 5 / the plan's own prohibition against bumping `STORAGE_VERSION`), so the key is no longer purged and the pre-existing assertion started failing — directly caused by this task's change, blocking the required four-file suite from passing green.
- **Fix:** Updated the assertion to expect the seeded value (`"true"`) to survive the migration untouched, and updated the docstring at the top of the file describing this protected behavior, documenting why the key is now orphaned dead data left un-purged by design.
- **Files modified:** `tests/test_mobile_plumbing.py`
- **Verification:** `pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py tests/test_freeze_proof.py -q` — 57/57 pass (53 baseline + 4 new).
- **Committed in:** `1f965d9` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug in plan's own test design, 1 blocking issue directly caused by the task's change)
**Impact on plan:** Both fixes were necessary to make the plan's own acceptance criteria achievable at all; no scope creep beyond the two directly-affected test files.

## Issues Encountered
- The plan's Task 1 acceptance-criteria bullet `git diff --exit-code 57d2768 HEAD -- web/mobile-gestures.js exits 0` is also factually unsatisfiable for the same reason described in Deviation 1 above (the file didn't exist at that base commit) — this bullet is prose-only (not part of Task 1's `<automated>` `<verify>` block) so it did not block Task 1's completion, but it is flagged here for visibility. Task 2's committed freeze-proof test now encodes the corrected, passable version of this same check.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `tests/test_freeze_proof.py` is now part of the four-plus-one-file suite (`tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py tests/test_freeze_proof.py`, 57 passing) — later plans in this phase should run this five-file command, not the old four-file one, to keep the freeze gate live.
- FA-MOBX-01's flagged assumption remains explicitly **unresolved** — its automatable criteria (banner null at all three viewport classes, no dismissal state anywhere) are proven here, but criterion 5 (the reader-facing device confirmation) is carried forward to the Phase D+E gate with Dre, as the planner specified. This plan does not close it.
- Desktop freeze (`web/style.css`, `web/mobile-gestures.js`) is intact per the new standing gate; subsequent plans (04-02..04-05) touch `web/mobile.css`/`web/app.js` new surfaces only and should not need to revisit `web/style.css` again this phase.

## Self-Check: PASSED

- FOUND: tests/test_freeze_proof.py
- FOUND: .planning/workstreams/mobile-ux/phases/04-mobile-cutover-accessibility/04-01-SUMMARY.md
- FOUND: commit 1f965d9 (Task 1)
- FOUND: commit 8309761 (Task 2)

---
*Phase: 04-mobile-cutover-accessibility*
*Completed: 2026-08-02*
