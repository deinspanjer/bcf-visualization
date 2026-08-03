---
phase: 04-mobile-cutover-accessibility
plan: 06
subsystem: testing
tags: [freeze-proof, pytest, integration-plan, gate-agenda, milestone-close]

# Dependency graph
requires:
  - phase: 04-mobile-cutover-accessibility
    plan: 05
    provides: "the seven-file test suite (100 tests) and the Lighthouse Accessibility gate this sweep re-runs whole"
provides:
  - "Full seven-file pytest sweep: 100/100 passing in one invocation, empirically reconciled against the 53-test Phase 3 baseline (verified by running --collect-only at the pre-Phase-4 base commit f750a21, not assumed from prior summaries)"
  - "Whole-milestone freeze proof re-confirmed against 57d2768 (web/style.css, 0 added/38 deleted) and against 1351450 (web/mobile-gestures.js, byte-identical) — both bases recorded and justified"
  - "COVERAGE.md verified in place (grep -c == 1, unmodified)"
  - "The INTEGRATION_PLAN.md §6 acceptance-evidence table across every group, closing the Accessibility group for the first time this milestone"
  - "The requirement-by-requirement closure record for MOBX-01..05, with MOBX-03's four clauses cited separately and MOBX-04's throw-decay clause recorded as a requirements-accuracy note, not satisfied"
  - "The Phase D+E gate agenda (FA-MOBX-01..07, announcement copy, D-49/D-50, VoiceOver check, throw-decay wording, STORY_LINKS duplication, landing dialog scope, every 04-01..04-05 deviation, plus a newly-surfaced STORAGE_VERSION/bcf:portrait-dismissed accuracy note) — assembled and explicitly unanswered"
  - "The v2 deferral list, stated explicitly as the final phase of the workstream"
affects: [phase-d-e-gate, milestone-close]

tech-stack:
  added: []
  patterns:
    - "Empirical baseline reconciliation: rather than trusting a prior summary's self-reported test count, spin up a disposable `git worktree add --detach <base-sha>` and run `pytest --collect-only -q` there to get a ground-truth count — caught and resolved a 5-test discrepancy between two documentation sources (03-04-SUMMARY.md said landscape had 15 tests at Phase 3 close; 04-VALIDATION.md's own baseline table said 20) without touching either historical file."

key-files:
  created: []
  modified: []

key-decisions:
  - "Applied the same two-base freeze-proof pattern tests/test_freeze_proof.py already uses (57d2768 for web/style.css, 1351450 for web/mobile-gestures.js) when running this plan's own <automated> verify bullet, rather than the plan's literally-written single-base (57d2768) command for both files — the latter is unsatisfiable by construction (web/mobile-gestures.js did not exist at 57d2768; git diff --exit-code against a commit before a file's creation always reports it as newly added, never 'unchanged'), which 04-01-SUMMARY.md already flagged as an 'Issues Encountered' item on its own literal acceptance-criteria wording. Documented as a Rule 1 deviation below rather than silently substituted."
  - "Resolved the empirical Phase-3 baseline as 53 (6+10+17+20), matching 04-VALIDATION.md's table and NOT 03-04-SUMMARY.md's self-reported 48 (33+15) — verified directly via a disposable worktree at f750a21 (the last Phase-3 commit) rather than trusting either prior document. This does not change any pass/fail outcome (100 >= 53 either way) but is the correct number for the record."
  - "The INTEGRATION_PLAN.md §6 Persistence bullet ('STORAGE_VERSION bumped; old keys (bcf:portrait-dismissed) cleared on first load after upgrade') is NOT satisfied by design — 04-01 deliberately did not bump STORAGE_VERSION (RESEARCH Pitfall 5: would purge every bcf:* preference for a returning reader and require a 34-fixture-site test rewrite, for a key with zero functional impact once its JS reference is deleted). This is a new requirements-accuracy note surfaced during this sweep (not previously on any FA-MOBX list) and is added to the gate agenda rather than silently marked satisfied or silently omitted from the evidence table."
  - "Lighthouse's mobile-preset Accessibility score is cited from 04-05's own directly-measured run (0.98) rather than re-invoking the Lighthouse CLI a second time in this session purely to re-print a number — this sweep's own pytest run re-executed tests/test_lighthouse_accessibility.py (which itself re-invokes the pinned CLI fresh) and it passed green, confirming the >=0.90 gate holds; no production file this plan touches, and none has changed since 04-05, so the score is unchanged by construction."

patterns-established: []

requirements-completed: []

coverage:
  - id: D1
    description: "Full seven-file pytest suite (test_desktop_smoke, test_mobile_plumbing, test_mobile_portrait, test_mobile_landscape, test_freeze_proof, test_landing_page, test_lighthouse_accessibility) passes in one invocation: 100/100, reconciled against the empirically-verified 53-test Phase 3 baseline plus 47 new tests named across 04-01..04-05"
    requirement: MOBX-01
    verification:
      - kind: integration
        ref: "pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py tests/test_freeze_proof.py tests/test_landing_page.py tests/test_lighthouse_accessibility.py -q (100 passed, exit 0)"
        status: pass
      - kind: other
        ref: "disposable worktree at f750a21 (Phase 3 close): pytest --collect-only -q on the four pre-existing files == 6+10+17+20 = 53; diff of test_desktop_smoke.py's def test_ names against HEAD shows zero renames/deletions"
        status: pass
    human_judgment: false
  - id: D2
    description: "Whole-milestone freeze proof: web/style.css diff against pre-Phase-1 base 57d2768 is 0 added/38 deleted; web/mobile-gestures.js is byte-identical against 1351450 (the commit immediately after Phase 1 closed, since the file did not exist at 57d2768); web/ and repo root carry no package manifest, lockfile, or bundler config"
    requirement: MOBX-01
    verification:
      - kind: integration
        ref: "tests/test_freeze_proof.py (4/4 pass, part of the 100-test sweep)"
        status: pass
      - kind: other
        ref: "git diff --numstat 57d2768 HEAD -- web/style.css == '0\\t38'; git diff --exit-code 1351450 HEAD -- web/mobile-gestures.js exits 0; find web/ for package.json|package-lock.json|yarn.lock|vite.config.js|webpack.config.js|rollup.config.js == empty; test root package.json absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "COVERAGE.md verified in place with the exact API-coverage declaration sentence, unmodified from planning"
    requirement: MOBX-01
    verification:
      - kind: other
        ref: "grep -F -c 'No external API integration: cutover and accessibility work touches only local DOM, localStorage, static outbound links, and a local Lighthouse CLI invocation.' .planning/workstreams/mobile-ux/phases/04-mobile-cutover-accessibility/COVERAGE.md == 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "§6 acceptance-evidence table assembled for every applicable checklist bullet across all six groups, including the Accessibility group's four bullets closed for the first time this milestone (Phases 2 and 3 both deferred it here)"
    verification:
      - kind: other
        ref: "§6 Acceptance-Checklist Evidence Table below"
        status: pass
    human_judgment: false
  - id: D5
    description: "Requirement-by-requirement closure record for MOBX-01..05, with MOBX-03's four independent clauses (announcements, keyboard, 44x44, Lighthouse) each carrying its own citation and an explicit statement that the Lighthouse score is not evidence for the 44x44 bar, and MOBX-04's throw-decay clause recorded as a requirements-accuracy note rather than satisfied"
    verification:
      - kind: other
        ref: "Requirement Closure Record section below"
        status: pass
    human_judgment: false
  - id: D6
    description: "Dre rules on the Phase D+E gate (§5 phases D+E merged), the §6 acceptance checklist, D-49's device measurement and D-50's dependent ruling, the VoiceOver check in both directions, the announcement copy, all seven carried flagged assumptions (FA-MOBX-01..07), and the v2 deferral list — on real iOS Safari hardware"
    verification: []
    human_judgment: true
    rationale: "This is the plan's own blocking gate (gate=\"blocking\" checkpoint:human-verify, Task 2), the milestone's closing gate. It is not auto-approvable under any mode including autonomous/auto-advance. Emulation cannot reproduce a real screen reader, Safari's native desktop-mode viewport, or a real thumb at the FAB's edge — three phases running, hardware has found defects a green suite missed every single time, two of them structural."

duration: ~24min (Task 1 only; Task 2 is the blocking gate, not yet run)
completed: 2026-08-03
status: blocked
---

# Phase 4 Plan 6: Full-Suite Sweep, Whole-Milestone Freeze Proof & Phase D+E Gate Agenda Summary

**Whole seven-file suite green in one run (100/100, empirically reconciled against a freshly-measured 53-test Phase 3 baseline via a disposable worktree rather than a trusted prior count), the whole-milestone freeze proof re-confirmed against the pre-Phase-1 base, and the milestone-closing §6 acceptance-evidence table, requirement closure record, Phase D+E gate agenda, and v2 deferral list all assembled and unanswered — Task 2 (Dre's device-pass gate review) is the one item still outstanding.**

## Performance

- **Duration:** ~24 min (Task 1 only)
- **Started:** 2026-08-03T02:06:04Z (immediately following 04-05's completion)
- **Completed:** 2026-08-03T02:30:00Z (Task 1)
- **Tasks:** 1 of 2 (Task 2 is a blocking human gate, not run by this agent)
- **Files modified:** 1 (this SUMMARY.md; COVERAGE.md was already correct from planning and needed no edit)

## Accomplishments

- Ran the full seven-file suite in one invocation: **100/100 pass**, zero failures, zero errors, zero skips (`tests/test_desktop_smoke.py` 6, `tests/test_mobile_plumbing.py` 10, `tests/test_mobile_portrait.py` 33, `tests/test_mobile_landscape.py` 27, `tests/test_freeze_proof.py` 4, `tests/test_landing_page.py` 14, `tests/test_lighthouse_accessibility.py` 6).
- Reconciled the "53-test Phase 3 baseline" claim empirically rather than trusting either of two disagreeing prior documents: span up a disposable `git worktree add --detach f750a21` (the last Phase 3 commit), ran `pytest --collect-only -q` on the four pre-existing files there, and got **6+10+17+20 = 53** — confirming `04-VALIDATION.md`'s baseline table and correcting `03-04-SUMMARY.md`'s own self-reported 48 (33+15), which undercounted `test_mobile_landscape.py` by 5. This does not change any pass/fail outcome (100 ≥ 53 either way) but is recorded here as the verified number, not the disputed one. Also confirmed via `diff` that `test_desktop_smoke.py`'s six `def test_` names are byte-identical to the Phase-3-close commit — no pre-existing test was deleted or renamed, only two assertions inside two of those six functions were restated (04-01's documented change).
- Re-ran the whole-milestone freeze proof: `web/style.css` diff against **`57d2768`** (`docs(01): create phase plan` — the commit immediately before ANY mobile-ux code landed) is `0 added / 38 deleted`; `web/mobile-gestures.js` is byte-identical against **`1351450`** (`docs(02): create phase plan` — the commit immediately after Phase 1 closed, since the file did not exist at `57d2768` and diffing it there would report the whole file as newly added, not unchanged — the exact issue `04-01-SUMMARY.md` already flagged and `tests/test_freeze_proof.py` already resolved this same way). Both SHAs and the reason for using two, not one, are recorded above and in `key-decisions`.
- Verified `tests/test_desktop_smoke.py`'s only diff across the whole phase is 04-01's single justified assertion restatement (CSS-hidden → DOM-absence checks for the deleted banner): `git diff --stat 277f8f9 HEAD -- tests/test_desktop_smoke.py` shows 8 insertions/8 deletions, zero elsewhere.
- Dependency scan: no `package.json`, `package-lock.json`, `yarn.lock`, `vite.config.js`, `webpack.config.js`, or `rollup.config.js` anywhere under `web/`, and no `package.json` at the repo root.
- `COVERAGE.md` was already written during planning and already carries the exact required declaration sentence — verified in place (`grep -F -c` == 1), not rewritten.
- Assembled the §6 acceptance-evidence table below across all six `INTEGRATION_PLAN.md` groups, closing the Accessibility group's four bullets for the first time this milestone (Phases 2 and 3 both deferred it here) and the Help-and-credits group's landing-page bullet (Phase 3 deferred it here too).
- Assembled the requirement-by-requirement closure record for MOBX-01 through MOBX-05, citing MOBX-03's four independent clauses separately and stating explicitly that the Lighthouse score is not evidence for the 44×44 tap-target bar.
- Surfaced one new requirements-accuracy item not previously on any FA-MOBX list: `INTEGRATION_PLAN.md`'s own §6 Persistence bullet ("`STORAGE_VERSION` bumped; old keys (`bcf:portrait-dismissed`) cleared on first load after upgrade") is not satisfied by design — 04-01 deliberately chose not to bump `STORAGE_VERSION` (RESEARCH Pitfall 5). Added to the gate agenda rather than silently marked satisfied or silently dropped from the evidence table.
- Assembled the Phase D+E gate agenda (Task 2) and the v2 deferral list below — both explicitly unanswered.

## Task Commits

1. **Task 1: Full-suite sweep, whole-milestone freeze proof, COVERAGE.md verification, §6 evidence table, and the gate agenda** — _(commit follows immediately after this SUMMARY.md is written — see repository log)_

**Plan metadata:** Not yet committed — the plan is not complete. Task 2 (the blocking Phase D+E gate review with Dre) is outstanding.

## Files Created/Modified

- `.planning/workstreams/mobile-ux/phases/04-mobile-cutover-accessibility/04-06-SUMMARY.md` — New. This file.
- `.planning/workstreams/mobile-ux/phases/04-mobile-cutover-accessibility/COVERAGE.md` — Verified unchanged (already correct from planning).

## §6 Acceptance-Checklist Evidence Table

Per `design/mobile-ux/INTEGRATION_PLAN.md` §6, covering every group. No blank cells: every row is a real test citation, a hardware-only marker pointing at Task 2, or an out-of-scope marker naming the owning phase.

### Layout

| Checklist item | Automated test / evidence |
|---|---|
| §0.5 desktop smoke test passes at every phase gate | `tests/test_desktop_smoke.py` (6 tests) — green in this sweep; only diff across the whole phase is 04-01's single justified assertion restatement |
| Portrait: sky ~60%, mini-rail dock always visible, top chips don't overlap the focal label | **Out of scope for Phase 4** — Phase 2 delivered and proved this (`tests/test_mobile_portrait.py::test_portrait_layout_proportions_and_chip_overlap`); unmodified this phase |
| Landscape: sky ~75% width, right rail shows field log (top 2/3) + settings/about dock (bottom 1/3) | **Out of scope for Phase 4** — Phase 3 (`tests/test_mobile_landscape.py::test_landscape_layout_proportions`); unmodified this phase |
| Rotating mid-playback preserves word position, play state, speed, zoom, pref toggles; no remount visible | **Out of scope for Phase 4** — Phase 3 (`tests/test_mobile_landscape.py::test_rotation_preserves_state`); unmodified this phase |
| Desktop (≥1100px) byte-identical to pre-change | **This phase's own claim.** `tests/test_freeze_proof.py` (whole-milestone, base `57d2768`/`1351450`); `git diff --numstat 57d2768 HEAD -- web/style.css` = `0 38` |

### Gestures (gesture-contract.html §03 constants)

| Checklist item | Automated test / evidence |
|---|---|
| Tap sky → toggles pause/play within 250ms | **Out of scope for Phase 4** — Phase 2 (`tests/test_mobile_portrait.py`) / Phase 3 landscape equivalent; unmodified |
| Tap sky when `tapToPause` is off → no effect | **Out of scope for Phase 4** — Phase 2/3; unmodified |
| Double-tap sky → snaps playhead to last roll at/before position and resumes | **Out of scope for Phase 4** — Phase 2/3; unmodified. **Note:** double-tap is also one of MOBX-03's five live-region trigger kinds, closed this phase — see Accessibility group below |
| Horizontal swipe (≥24px engage, dx>1.5×dy) → ±1 roll per 56px of travel; haptic per roll crossed | **Out of scope for Phase 4** — Phase 2/3; unmodified. Also a live-region trigger kind, see Accessibility group |
| Drag mini-rail (portrait) → scrubs word position, respects zoom + auto-pan | **Out of scope for Phase 4** — Phase 2; unmodified |
| Drag cinema-scrub (landscape) → same, at every zoom | **Out of scope for Phase 4** — Phase 3; unmodified |
| Landscape chrome auto-hides after 4000ms idle; first tap reveals (not pause), second pauses | **Out of scope for Phase 4 at the 4000ms baseline** — Phase 3. **This phase's own claim:** the window doubles to 8000ms under `prefers-reduced-motion` — `tests/test_mobile_landscape.py::test_landscape_chrome_autohide_doubles_under_reduced_motion` (MOBX-04) |

### Scrubber zoom + binning

| Checklist item | Automated test / evidence |
|---|---|
| Settings → Timeline zoom segmented 1×/2×/4×/8×, selected value persists | **Out of scope for Phase 4** — Phase 2/3; unmodified |
| At 1× with the full dataset, rail shows cluster diamonds (not overlapping-dot smear) | **Out of scope for Phase 4** — Phase 2; unmodified |
| At 8×, individual rolls visible at thumb resolution; auto-pans to keep playhead centred | **Out of scope for Phase 4** — Phase 2/3; unmodified |
| Active roll always renders as a separate cyan diamond on top of any cluster | **Out of scope for Phase 4** — Phase 2; unmodified |

### Persistence

| Checklist item | Automated test / evidence |
|---|---|
| All `bcf:*` keys listed in §4 are read on init and written on change | **Out of scope for Phase 4** — Phase 1/2/3; no new `bcf:*` key introduced this phase |
| `STORAGE_VERSION` bumped; old keys (`bcf:portrait-dismissed`) cleared on first load after upgrade | **NOT satisfied, by deliberate design — flagged, not silently omitted.** 04-01 explicitly chose NOT to bump `STORAGE_VERSION` (RESEARCH Pitfall 5: bumping would purge every returning reader's `bcf:*` preferences and require rewriting 34 seeded fixture sites across 4 files, for a key with zero functional impact once its JS reference is deleted). `bcf:portrait-dismissed` survives as orphaned dead data — proven by `tests/test_mobile_plumbing.py::test_storage_version_bump_purges_stale_keys` (asserts the seeded value now *survives* migration, updated in 04-01). **Added to the Phase D+E gate agenda below as a new requirements-accuracy item, not previously on any FA-MOBX list.** |

### Help + credits surfaces

| Checklist item | Automated test / evidence |
|---|---|
| First-run help overlay auto-opens; dismissing sets `bcf:help-seen` so later loads don't reopen it | **Out of scope for Phase 4** — Phase 2 (`tests/test_mobile_portrait.py::test_first_run_help_auto_opens_once`); unmodified |
| About flyout shows story title/credit/SV-FF-AO3 links/dataset stats; "Gestures & help" link opens the same Help overlay | **Out of scope for Phase 4** — Phase 2/3; unmodified |
| Landing page (`index.html`) shows the `?` button top-right and the title-chip/credit at the top of Survey's letter | **This phase's own claim, closed for the first time.** `tests/test_landing_page.py` (14 tests): `::test_landing_page_meta_row_shows_title_chip_and_author_credit_above_letter`, `::test_landing_page_help_button_opens_modal_dialog`, `::test_landing_page_dialog_contains_credit_and_help_content`, plus five degraded-state backstops (MOBX-02) |

### Accessibility

**Closed for the first time this milestone — Phases 2 and 3 both marked this group out-of-scope and deferred it here.**

| Checklist item | Automated test / evidence |
|---|---|
| `prefers-reduced-motion: reduce`: no transitions, no throw decay, auto-hide extended to 8000ms | **Transitions:** already shipped pre-milestone (frozen `web/style.css:62`), verified by `tests/test_mobile_landscape.py::test_landscape_transitions_already_silenced_under_reduced_motion`. **Auto-hide doubling:** `tests/test_mobile_landscape.py::test_landscape_chrome_autohide_doubles_under_reduced_motion` (04-04). **Throw decay: NOT satisfied — requirements-accuracy note, not a passing test.** Throw-to-scrub inertia was never implemented (it is v2 backlog item `MOB2-04`); there is nothing to disable. See Requirement Closure Record below and the gate agenda. |
| Keyboard: Space, ←/→, Home, `?` all work | `tests/test_mobile_portrait.py::test_mobile_keyboard_arrows_step_one_roll_and_announce`, `::test_mobile_keyboard_home_snaps_to_live_edge_and_resumes`, `::test_mobile_keyboard_question_mark_toggles_help`, `::test_mobile_keyboard_space_toggles_playback_on_every_layout`, `::test_mobile_keyboard_respects_editable_guard`, `::test_desktop_keyboard_stepping_unaffected_by_mobile_branch`; landscape equivalents in `tests/test_mobile_landscape.py` (04-02) |
| Roll changes announce in the aria-live region | `tests/test_mobile_portrait.py::test_mobile_live_region_mounts_hidden_on_mobile_only`, `::test_mobile_live_region_announces_on_swipe_and_silent_on_tap`, `::test_mobile_live_region_rail_scrub_announces_once_at_release`, `::test_mobile_live_region_silent_during_free_playback`, `::test_mobile_live_region_renders_special_characters_as_text`, `::test_mobile_live_region_empty_when_no_roll_before_playhead`, `::test_mobile_live_region_reannounces_repeat_landing` (04-02). **DOM presence and computed style are not proof a screen reader speaks it — the VoiceOver check at Task 2 is the only real proof, see gate agenda.** |
| All tappable targets ≥44×44 CSS px | `tests/test_mobile_portrait.py` (extended 44px rect assertion, incl. top-cluster help button), `tests/test_mobile_landscape.py::test_landscape_other_tap_targets_clear_44px` (rect-based, other controls), `tests/test_mobile_landscape.py::test_cinema_scrub_fab_offset_click_hit_area` (offset-click, since the FAB's hit area is a `::before` pseudo-element a rect check cannot see — 04-04). **Explicitly NOT evidenced by the Lighthouse score below** — Lighthouse's bundled `target-size` audit defaults to 24×24 CSS px (WCAG 2.5.8 AA), a lower and different bar. |
| Lighthouse Accessibility ≥ 90 on the mobile preset (MOBX-03's fourth clause, named in REQUIREMENTS.md though not enumerated as a separate §6 tick) | `tests/test_lighthouse_accessibility.py::test_accessibility_score_at_or_above_threshold` — scored **0.98** at `formFactor: "mobile"`, `lighthouseVersion: "13.4.1"` (04-05's directly-measured run; re-confirmed green in this sweep's own 100-test run against the same, unmodified production files). **Explicitly NOT evidence for the 44×44 tap-target bar above** — the two checks measure different thresholds and neither substitutes for the other. |

## Requirement Closure Record

### MOBX-01 — `renderPortraitBanner` and its CSS deleted; no banner anywhere; desktop byte-identical

Closed by plan 04-01. `renderPortraitBanner()`, its `renderAppShell()` call site, `LS_PORTRAIT_DISMISSED`, `app.portraitDismissed`, and the migration-clear entry are all deleted (`grep -c` == 0 in `web/app.js`); `.portrait-banner` and the stale breakpoint media block are deleted from `web/style.css` (0 added/38 deleted vs. `57d2768`). Automated proof: `tests/test_desktop_smoke.py` (DOM-absence at desktop, both mobile widths via the mobile suite), `tests/test_freeze_proof.py`. **Not automatable, carried to gate:** the reader-facing device confirmation that portrait genuinely stands on its own with no residual gap where the banner sat, and the banner's absence on real hardware in both orientations (FA-MOBX-01 criterion 5, and Manual-Only item 2).

### MOBX-02 — Landing page shows title chip + author credit + `?` help button; Survey letter verbatim

Closed by plan 04-03. `.landing-meta-row`/`.landing-title-chip`/`.landing-author-credit`/`.landing-help-btn` inserted above the letter; `#landing-help-dialog` (native `<dialog>`, feature-checked, focus-returning) opens a condensed credit/help block. Automated proof: `tests/test_landing_page.py` (14 tests: happy path + four degraded-state backstops — no-JS, dialog-unsupported, 320px viewport, focus-return). Letter/subject/nav verbatim verified by `git diff 57d2768 HEAD -- index.html` showing zero removed lines. **Not automatable, carried to gate:** real-device `<dialog>` rendering/interaction on iOS Safari (D11, Manual-Only item 4); whether the condensed credit-only scope is right or the gesture how-to should be duplicated (FA-MOBX-02); the two hardcoded `STORY_LINKS` copies (FA-MOBX-06).

### MOBX-03 — Four independent clauses, each with its own citation

1. **`aria-live="polite"` announcements.** Closed by plan 04-02. Automated proof: `tests/test_mobile_portrait.py` (7 live-region tests) + `tests/test_mobile_landscape.py` landscape equivalent. **Not automatable, carried to gate:** whether VoiceOver actually speaks the region and stays silent through playback (the VoiceOver check, Manual-Only item 3) — "present in the DOM" is explicitly not proof.
2. **Keyboard equivalents (Space/←/→/Home/`?`).** Closed by plan 04-02, reusing the existing `rollStepFrom()` and `openMobileSurface()`. Automated proof: 6 portrait tests + landscape equivalents, plus desktop-numeric-stepping-unaffected proof.
3. **44×44 tap targets.** Closed by plan 04-04. Automated proof: rect assertions for host-box controls, offset-click assertion for the pseudo-element FAB overlay. **This is a separate, independent check from clause 4 below — a passing score there is never offered as evidence for this floor, and vice versa.** **Not automatable, carried to gate:** real-thumb edge-tap reliability at the FAB (backstop item, D-39/FA-MOBX-03-adjacent).
4. **Lighthouse Accessibility ≥ 90 on the mobile preset.** Closed by plan 04-05. Scored 0.98, re-confirmed green this sweep. Package legitimacy (Lighthouse CLI, pinned `13.4.1`) was ruled on by Dre ahead of execution and is restated on the gate agenda as FA-MOBX-07 per the plan's own instruction, not re-litigated.

**Also carried for MOBX-03:** the announcement-phrasing table is Claude's proposed copy grounded in the real dataset, not Dre-approved copy (RESEARCH Assumption A3); FA-MOBX-05 (the zero-instance `untracked_acquisition` phrasing row).

### MOBX-04 — `prefers-reduced-motion: reduce` disables transitions and throw decay, doubles auto-hide to 8000ms

**Two of three clauses closed; the third is a requirements-accuracy note, not a satisfied clause.** Transitions: already shipped pre-milestone (frozen `web/style.css:62`), verified not rebuilt by plan 04-04. Auto-hide doubling: closed by plan 04-04 (4000ms → 8000ms, reusing the single `PREFERS_REDUCED_MOTION` constant). **Throw decay: the feature this clause names — throw-to-scrub inertia — was never implemented anywhere in the milestone** (`attachSkyGestures`'s `onSwipeEnd(velocity)` ignores velocity by design; it is v2 backlog item `MOB2-04`). There is no code path to disable, so "disabled under reduced motion" has no referent. **This clause must not be marked satisfied** — it is presented to Dre at the gate as a wording-accuracy item (amend REQUIREMENTS.md's MOBX-04 text, or accept it as permanently and correctly unmet until `MOB2-04` ships in v2), per FA-MOBX-03/FA-MOBX-04.

### MOBX-05 — Playback pauses when the page is hidden

Already implemented in Phase 1 (D-02/D-51, `web/app.js:4592`'s `visibilitychange` → `stopPlayback()`). Plan 04-04 verified rather than rebuilt: portrait, landscape, and desktop-unaffected are each proven by a dedicated test, with the landscape arm confirmed to ride on the same `layoutMode !== "desktop"` guard added in Phase 3. **Not automatable, carried to gate:** whether pause-without-auto-resume is still the wanted behavior now that the mobile app actually exists as a real, lived-with product rather than a decision made in the Phase 1 interview before any mobile UI existed (FA-MOBX-04).

## Decisions Made

See `key-decisions` in frontmatter. Short form:
- Used the same two-base freeze-proof pattern `tests/test_freeze_proof.py` already established (04-01) when running this plan's own literal `<automated>` verify command, rather than the single-base command as literally written — documented as a Rule 1 deviation below.
- Resolved the empirical Phase-3 baseline as 53, correcting a 5-test discrepancy between two prior documents via a disposable worktree measurement rather than picking one prior claim over the other by assumption.
- Surfaced the `STORAGE_VERSION`/`bcf:portrait-dismissed` §6 bullet as unsatisfied-by-design and added it to the gate agenda, rather than silently marking it satisfied (it is not) or silently dropping it from the evidence table (the plan explicitly forbids blank/omitted rows).
- Cited 04-05's already-measured Lighthouse score (0.98) rather than re-invoking the CLI a second time purely to re-print an unchanged number; this sweep's own pytest run did re-execute the gate fresh and it stayed green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] This plan's own literal `<automated>` verify command for the freeze-proof bullet is factually unsatisfiable for `web/mobile-gestures.js`**
- **Found during:** Task 1, running the plan's second `<automated>` verify bullet
- **Issue:** The plan's `<verify>` block specifies `git diff --exit-code 57d2768 HEAD -- web/mobile-gestures.js` as part of a combined check. `web/mobile-gestures.js` did not exist at `57d2768` (it was created during Phase 1 itself, commit `3034d90`, which postdates `57d2768`) — `git diff --exit-code` against a commit before a file's creation always reports it as newly added (exit 1), never "unchanged" (exit 0), regardless of whether the file has changed since its own creation. This is the exact same issue `04-01-SUMMARY.md` already flagged in its own "Issues Encountered" section for an equivalent literal acceptance-criteria bullet, and which `tests/test_freeze_proof.py` already resolved by using two base commits instead of one.
- **Fix:** Ran the freeze-proof evidence using `57d2768` for `web/style.css` (the artifact that genuinely predates the milestone, matching MOBX-01's actual whole-milestone claim) and `1351450` (the commit immediately after Phase 1 closed) for `web/mobile-gestures.js`, exactly matching `tests/test_freeze_proof.py`'s own already-committed, already-passing logic. Confirmed `git diff --exit-code 1351450 HEAD -- web/mobile-gestures.js` exits 0.
- **Files modified:** None — this is a verification-command correction, not a code change. `tests/test_freeze_proof.py` (which already encodes the correct two-base logic) was not touched.
- **Verification:** `pytest tests/test_freeze_proof.py` — 4/4 pass, part of the 100-test sweep; manually re-ran both `git diff` commands standalone and confirmed the results match the test's own assertions.
- **Committed in:** This plan's Task 1 commit (docs-only; no source change).

---

**Total deviations:** 1 auto-fixed (a bug in this plan's own literal verify-command wording, matching a precedent already flagged and already resolved by a prior plan in this same phase).
**Impact on plan:** No scope creep; the correction only affects which base commit is cited for one file in the evidence record, and matches the already-committed, already-tested logic in `tests/test_freeze_proof.py` exactly.

## Issues Encountered

- **Documentation discrepancy resolved by direct measurement, not assumption.** `03-04-SUMMARY.md` self-reported 48 tests at Phase 3 close (33 baseline + 15 landscape); `04-VALIDATION.md`'s own baseline table said 53 (6+10+17+20, implying 20 landscape tests). Rather than trusting either, spun up a disposable `git worktree add --detach f750a21` (the actual last Phase-3 commit) and ran `pytest --collect-only -q` there directly: **53 confirmed** (`test_mobile_landscape.py` had 20 collected items at that commit, not 15 — `03-04-SUMMARY.md`'s own count was itself an undercount, ironically the same class of documentation-only miscount that summary's own "Issues Encountered" section flagged about a different figure). This does not change any pass/fail outcome for this plan (100 ≥ 53 either way) and is recorded here for the record, not silently corrected in either historical file.
- Two initial synchronous/manually-backgrounded pytest invocations were killed by the harness's shell-session teardown mid-completion (progress reached 100% but the final summary line never printed, output files empty of any "N passed" text). Resolved by re-running via the harness's own `run_in_background: true` mechanism, which is not tied to the calling shell's lifecycle; that run completed cleanly (exit code 0) and its pass count was cross-checked against `--collect-only`'s item counts (100, matching exactly). Not a code or test defect — a background-process lifecycle quirk of two earlier invocation methods, both abandoned in favor of the harness-native one.

## User Setup Required

None — no external service configuration required for Task 1. Task 2 requires Dre to serve the app locally and walk the checklist on real iOS Safari hardware — not an environment-configuration step, but the plan's own blocking gate.

## Phase D+E Gate Agenda (Task 2 — unanswered)

Assembled per the plan's Task 1, action item 6. **No item below is pre-answered.** Per `04-VALIDATION.md`'s Manual-Only Verifications table (Dre's standing scoping directive: only objectively-provable-by-screenshot-or-Playwright items reach the device pass), the four device items are: banner absence in both orientations, D-49's Safari-desktop-mode measurement, the landing-page `?` dialog on a real phone, and the VoiceOver check (the one item requiring Dre to turn something on). Auto-hide feel, sky framing, and haptics remain explicitly cut, as in every prior phase's gate.

### 1. Seven carried flagged assumptions (FA-MOBX-01 through FA-MOBX-07, never probe-resolved — must not be closed by an agent)

- **FA-MOBX-01 (MOBX-01, banner absence):** both phone orientations and desktop width, plus the reader-facing question of whether portrait genuinely stands on its own now that the rotation suggestion is gone.
- **FA-MOBX-02 (MOBX-02, landing-page degradation):** no-JS, unsupported dialog, long title, 320px sizing, focus return on every close route — plus whether the condensed credit-only dialog is the right scope or the gesture how-to should be duplicated after all.
- **FA-MOBX-03 (MOBX-04, reduced-motion timing):** the in-flight timer case, the module-load snapshot meaning an OS toggle takes effect next load, the paused and surface-open cases, and the throw-decay wording.
- **FA-MOBX-04 (MOBX-05, hidden-page pause):** portrait, landscape, desktop-unaffected, bookmark write intact, and whether pause-without-auto-resume is still the wanted behavior now that the mobile app actually exists.
- **FA-MOBX-05 (MOBX-03, untracked-acquisition phrasing):** zero live examples; confirm the row stays dead code rather than carrying invented copy. Carried with it: the whole announcement phrasing table is proposed copy that Dre has not yet approved.
- **FA-MOBX-06 (MOBX-02, duplicated story URLs):** two hardcoded copies with no module connecting them; confirm accepting the duplication rather than inheriting it silently.
- **FA-MOBX-07 (MOBX-03, audit tool legitimacy):** the SUS verdict ruling and the version pin, already taken at plan 04-05 Task 1 — restated here so the phase record carries it. (Ruling reproduced verbatim in `04-05-SUMMARY.md`: approve, pinned to `lighthouse@13.4.1`.)

### 2. The announcement phrasing table (RESEARCH Assumption A3 / FA-MOBX-05)

Proposed copy grounded in the real 670-roll dataset, not yet Dre-approved: miss ("Roll {n} of {total}. Miss." — 410/670 rolls, deliberately terse), single paid perk, multi-grab ("{firstPerkName} and {k} more, {cp} CP.", 51/670 rolls), free-only fallback (0 live examples, kept for robustness), and the zero-instance `untracked_acquisition` row (dead code, FA-MOBX-05). Each row is a one-line string edit in `web/app.js`'s `mobileRollAnnouncement()` if Dre wants different wording.

### 3. D-49's desktop-mode measurement and D-50's dependent ruling

Turn on Safari's "Request Desktop Website" for the app; read `window.innerWidth` and the app's own `layoutMode` off the device over the CDP bridge. The documentation-only prediction (~980px layout viewport, which our `max-width: 1100px` portrait clause would still match — meaning the app would render mobile scaled down, not switch to desktop) has never been measured. **Then rule on D-50:** if browser-native desktop mode does not serve as the escape hatch, the in-app toggle drops to v2 with the recorded rationale; building it anyway is a scope decision only Dre can make.

### 4. The VoiceOver check (MOBX-03's only real proof)

Enable VoiceOver, perform one gesture that moves the playhead (a swipe-step is clearest), and report two explicit answers: is the announcement spoken at all, and does it stay silent through several rolls of free playback? "Present in the DOM" is not an acceptable answer to either. While there, rule on the announcement wording (item 2 above).

### 5. MOBX-04's throw-decay wording

The feature this clause names (throw-to-scrub inertia) was never built anywhere in the milestone. Rule on amending REQUIREMENTS.md's wording rather than treating the clause as permanently and silently unmet.

### 6. A new requirements-accuracy item surfaced by this sweep: `STORAGE_VERSION` / `bcf:portrait-dismissed`

`INTEGRATION_PLAN.md` §6's Persistence bullet ("`STORAGE_VERSION` bumped; old keys cleared on first load after upgrade") is not satisfied — 04-01 deliberately left the key un-purged (see Decisions Made). Not previously on any FA-MOBX list; surfaced here for Dre's awareness. No functional impact (the key is dead, unreferenced code); a wording/acceptance-checklist note, not a defect.

### 7. The two hardcoded copies of the story URLs (FA-MOBX-06)

`web/app.js`'s `STORY_LINKS` and `index.html`'s dialog hrefs are two independent literals with a red-on-drift test (`test_landing_page_dialog_external_links_are_safe_and_match_app_js`) but no module connecting them. Confirm accepting the duplication as-is, or route it to a follow-up.

### 8. The landing-page dialog's content scope (FA-MOBX-02)

Confirm the condensed credit-and-help block (title, byline, source links, a pointer to in-app Help, the Got-it CTA) is the right scope, or that Dre wants the full seven-row gesture how-to duplicated there after all.

### 9. Every deviation recorded in plans 04-01 through 04-06

- **04-01 (×2):** the freeze-proof test's base-commit design corrected to use two bases instead of one (Rule 1); `tests/test_mobile_plumbing.py`'s stale-key-purge assertion updated to expect survival instead of purge (Rule 3, directly caused by the banner deletion).
- **04-02:** a test-design correction (`window.history.state` vs. `history.length`) — no shipped-behavior change.
- **04-03:** a process deviation — Tasks 1 and 2 landed in one commit instead of two (no functional impact; every acceptance criterion independently satisfied).
- **04-04:** none formally flagged; one test assertion loosened mid-implementation (word-position inequality → presence/stability check) due to expected Phase 1 camera-lock behavior, not a defect.
- **04-05:** none — Task 1 was pre-resolved by Dre ahead of execution; Task 2 matched the plan exactly.
- **04-06 (this plan):** one Rule 1 fix to this plan's own literal verify-command wording (see Deviations from Plan above), matching a precedent 04-01 already flagged and `tests/test_freeze_proof.py` already resolved.

## v2 Deferral List

**This is the final phase of the mobile-ux workstream. Anything not landed at this gate ships as v2.**

1. **In-app desktop-view toggle** — pending D-49's device measurement and D-50's dependent ruling from Dre (Task 2). If browser-native desktop mode does not work as an escape hatch and Dre does not explicitly ask for the in-app toggle to be built anyway, this stays v2 per D-50's own conditional framing.
2. **Spreadsheet export of the curated data** — Dre's own planned separate workstream, and the *right* artifact for non-sighted users who want the underlying curation data (D-45). The mobile live region is deliberately minimal and was never meant to substitute for this.
3. **Large-tablet-portrait ergonomics** — gesture constants are phone-thumb pixel values; an iPad in portrait gets a functional but untuned experience (D-36).
4. **`INTEGRATION_PLAN.md` §8 v2 backlog**, unchanged: pinch-to-zoom on the scrubber (`MOB2-01`), long-press roll-dot preview tooltip (`MOB2-02`), edge swipe-down to peel field log in portrait (`MOB2-03`), throw-to-scrub inertia (`MOB2-04` — the same feature named by MOBX-04's vacuous throw-decay clause, item 5 above), real constellation outlines in the sky (`MOB2-05`, separate workstream), richer mobile cinematic content beyond text (`MOB2-06`... — content), Screen Wake Lock during playthrough.
5. **The two hardcoded `STORY_LINKS` copies (FA-MOBX-06)** — stays as deliberately-accepted duplication (a red-on-drift test guards it) unless Dre asks for consolidation at the gate.
6. **The orphaned `bcf:portrait-dismissed` localStorage key** — stays un-purged by design; zero functional impact, and purging it would require a `STORAGE_VERSION` bump and a 34-fixture-site test rewrite for no behavioral gain.

## Next Phase Readiness

## ✅ PHASE D+E GATE APPROVED — 2026-08-03

Dre signed off, closing the Phase D+E gate and the mobile-ux milestone.

**Approved on automated evidence. The real-device iOS pass was NOT run.** This is recorded precisely because the distinction matters to anyone reading later: 100/100 automated tests pass and the whole-milestone freeze is proven, but four items that were on the agenda remain **device-unverified**, not device-verified:

| Item | Status | What automated evidence does and does not cover |
|---|---|---|
| Banner absent on device, both orientations (MOBX-01, FA-MOBX-01) | Automated only | Playwright asserts `.portrait-banner` is null at both viewports and the CSS is provably deleted (0 added / 38 removed vs `57d2768`). Residual risk: negligible — the element cannot render if neither its markup nor its CSS exists. |
| Landing page `?` dialog on real hardware (MOBX-02, FA-MOBX-02) | Automated only | 14 Playwright tests cover the dialog, its degraded states and the verbatim letter. Residual risk: low — `<dialog>` behavior on iOS Safari differs from headless Chromium, so a rendering quirk is possible. |
| D-49 Safari "Request Desktop Website" measurement | **Unverified inference** | Never measured. The ~980px layout-viewport figure is from documentation, not this device. D-50 (no in-app desktop toggle) therefore rests on an unconfirmed premise — it stays a v2 item and the measurement stays outstanding. |
| VoiceOver announcement (MOBX-03) | **Automated cannot cover this** | The live region's presence, its locked visually-hidden CSS, its trigger set and its silence during playback are all asserted. What is NOT asserted — and cannot be, since no headless browser runs a screen reader — is whether a screen reader actually **speaks** it. A region that is present but never announced would pass all 100 tests. This is the one item where the automated suite gives no signal at all. |

Everything else on the 14-item agenda was a documentation or deferral ruling rather than a device action, and is settled by this sign-off: the flagged assumptions FA-MOBX-01..07, MOBX-04's vacuous throw-decay clause (a requirements-accuracy note, not a defect — throw-to-scrub inertia was never implemented and is v2 backlog §8), the deliberately-orphaned `bcf:portrait-dismissed` key, the two hardcoded `STORY_LINKS` copies, and the v2 deferral list.

**If the VoiceOver behavior is ever checked and found wanting**, that is a gap-closure item (`/gsd-plan-phase 4 --gaps`), not a defect in what shipped — the contract was implemented to the locked spec and verified as far as automation reaches.

### Original readiness note (superseded)

~~**Not ready. Task 2 (the blocking Phase D+E gate review with Dre, including the real-device iOS Safari pass) is outstanding — no agent may approve it.**~~ Held correctly until Dre ruled; approved above.

This is the final phase of the mobile-ux workstream. Once Task 2 is run and Dre approves the gate, the milestone closes: MOBX-01 through MOBX-05 all show as complete in `REQUIREMENTS.md` already (checked off during their originating plans), and this plan's own deliverable is the evidence record and the gate, not new requirement functionality — matching the Phase 2 (`02-05-SUMMARY.md`) and Phase 3 (`03-04-SUMMARY.md`) precedents of leaving `requirements-completed` empty on the closing plan's own frontmatter.

**Carried forward regardless of the gate's outcome:**
- Every item in the v2 Deferral List above.
- If the gate surfaces a defect, it routes to `/gsd-plan-phase 4 --gaps`, not an in-place edit of any already-committed plan (per this plan's own session constraints) — and per this milestone's own three-phases-running pattern, budget for a second device pass after any fix.

---
*Phase: 04-mobile-cutover-accessibility*
*Completed: 2026-08-03 (Task 1 only — plan not yet closed, see Next Phase Readiness)*

## Self-Check: PASSED

- `.planning/workstreams/mobile-ux/phases/04-mobile-cutover-accessibility/COVERAGE.md` verified present on disk with the exact declaration sentence (grep -c == 1).
- Full seven-file suite (100 tests) verified green in this session's own `run_in_background` run (cross-checked against `--collect-only`'s per-file item counts, which sum to exactly 100).
- Freeze-proof diff against `57d2768` (style.css) and `1351450` (mobile-gestures.js) verified clean in this session's own run for both files.
- Dependency scan verified empty in this session's own run.
- Phase-3 baseline (53) verified empirically via a disposable `git worktree add --detach f750a21`, then removed (`git worktree remove --force`) — `git worktree list` confirmed no stray worktree left behind.
