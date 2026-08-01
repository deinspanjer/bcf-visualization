---
phase: 02-portrait-layout
plan: 05
subsystem: ui
tags: [playwright, mobile-ux, regression-testing, freeze-proof]

requires:
  - phase: 02-portrait-layout
    plan: 04
    provides: "Complete portrait feature set: render branch, gestures, cluster-binned rail, Settings/About/Help surface stack — the whole MOBP-01..05 surface this sweep proves"
provides:
  - "Full web suite (test_desktop_smoke + test_mobile_plumbing + test_mobile_portrait, 32 tests) green in one run"
  - "Freeze proof: web/style.css and web/mobile-gestures.js byte-identical to the pre-Phase-2 base commit; test_desktop_smoke.py's only phase-wide change is the single F-02 superseded assertion (3 lines)"
  - "test_landscape_fallback_is_unchanged: D-12's interim landscape fallback (desktop shell + portrait banner + Phase-1 gesture probe) proven intact; the portrait surface never mounts at a landscape viewport"
  - "COVERAGE.md: this phase's API-coverage declaration (no external API integration)"
  - "§6 acceptance-checklist evidence table mapping every applicable Layout/Gestures/Scrubber/Persistence/Help bullet to its automated test or hardware-only marker"
affects: [02-portrait-layout-phase-B-gate, 03-landscape-layout]

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/workstreams/mobile-ux/phases/02-portrait-layout/COVERAGE.md
  modified:
    - tests/test_mobile_portrait.py

key-decisions:
  - "requirements-completed left empty on this plan's frontmatter: MOBP-01..05's actual functional work was completed and individually marked by plans 02-01..02-04; this closing plan's own deliverable is the sweep + freeze proof + the Phase B gate, not new requirement functionality. Marking the requirements complete a second time here, before Dre's gate ruling, would be premature."
  - "Used the pre-Phase-2 base commit (1351450, 'docs(02): create phase plan' — the last commit before 02-01's first task commit) as the freeze-proof diff target, not a bare working-tree diff. The plan's literal <verify> command (git diff --exit-code against HEAD) is trivially true once everything is committed; diffing against the phase's actual starting point is what proves the frozen files were never touched across all four prior plans, not just since the last commit."

requirements-completed: []

coverage:
  - id: D1
    description: "Full web suite (test_desktop_smoke.py + test_mobile_plumbing.py + test_mobile_portrait.py, 32 tests) passes in one run"
    verification:
      - kind: integration
        ref: "pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "web/style.css and web/mobile-gestures.js are byte-identical to the pre-Phase-2 base commit (1351450); tests/test_mobile_plumbing.py unmodified"
    verification:
      - kind: other
        ref: "git diff --exit-code 1351450 HEAD -- web/style.css web/mobile-gestures.js tests/test_mobile_plumbing.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/test_desktop_smoke.py's only change across the whole phase is the single F-02 superseded portrait-crossing assertion (3 lines changed)"
    verification:
      - kind: other
        ref: "git diff --numstat 1351450 HEAD -- tests/test_desktop_smoke.py (3 removed / 3 added)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The D-12 interim landscape fallback (desktop shell + portrait banner + Phase-1 gesture probe) is intact at 844x390; the portrait surface (.mobile-app) never mounts there"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_landscape_fallback_is_unchanged"
        status: pass
    human_judgment: false
  - id: D5
    description: "No package.json/lockfile/bundler config exists anywhere under web/; web/index.html's script/stylesheet set is unchanged since pre-Phase-2"
    verification:
      - kind: other
        ref: "os.walk scan of web/ for package.json|package-lock.json|yarn.lock|vite.config.js (empty) + git diff 1351450 HEAD -- web/index.html (empty)"
        status: pass
    human_judgment: false
  - id: D6
    description: "COVERAGE.md exists in the phase directory with the exact API-coverage declaration sentence"
    verification:
      - kind: other
        ref: ".planning/workstreams/mobile-ux/phases/02-portrait-layout/COVERAGE.md"
        status: pass
    human_judgment: false
  - id: D7
    description: "Dre has reviewed the portrait surface against INTEGRATION_PLAN.md §5 Phase B gate and the §6 acceptance checklist on real iOS Safari hardware, and has ruled on all six flagged decisions (D-15, F-04, F-06, F-07/D-19, RESEARCH A1, F-01/F-02)"
    verification: []
    human_judgment: true
    rationale: "This is the plan's own blocking gate (gate=\"blocking\" checkpoint:human-verify). Emulation cannot reproduce the dynamic iOS toolbar, the svh settle, or real touch latency, and this gate exists precisely so a human — never this agent — rules on the six flagged decisions. It is not auto-approvable under any circumstances, including auto mode."

duration: ~10min (Task 1 only; Task 2 is the blocking gate, not yet run)
completed: 2026-07-26
status: blocked
---

# Phase 2 Plan 5: Full-Suite Sweep, Freeze Proof, and Coverage Declaration Summary

**Whole-suite green (32/32) with a diff-based freeze proof against the pre-Phase-2 base commit, a new landscape-fallback regression guard, and the phase's API-coverage declaration — Task 2 (the INTEGRATION_PLAN.md §5 Phase B gate review with Dre) is the one item still outstanding.**

## Performance

- **Duration:** ~10 min (Task 1 only)
- **Completed:** 2026-07-27T01:41:04Z (Task 1)
- **Tasks:** 1 of 2 (Task 2 is a blocking human gate, not run by this agent)
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- Added `test_landscape_fallback_is_unchanged` to `tests/test_mobile_portrait.py`: at 844x390 (`PHONE_LANDSCAPE`), proves the desktop shell root (`.app`) and the portrait banner (`.portrait-banner`) are visible, the Phase-1 gesture probe (`.mobile-gesture-probe`) is attached, and `.mobile-app` never mounts — the D-12 interim fallback survived all four prior plans in this phase untouched, and Phase 3 still has the exact surface it's contracted to replace.
- Ran the full three-file suite (`test_desktop_smoke.py` + `test_mobile_plumbing.py` + `test_mobile_portrait.py`) in one invocation: 32/32 pass, zero failures, zero errors.
- Ran the freeze proof against the actual pre-Phase-2 base commit (`1351450`, the last commit before 02-01's first task), not just the current working tree: `web/style.css` and `web/mobile-gestures.js` are byte-identical to that base; `tests/test_mobile_plumbing.py` is unmodified; `tests/test_desktop_smoke.py`'s only change across the entire phase is the single F-02 superseded portrait-crossing assertion (3 lines removed, 3 added — a comment update plus the `.portrait-banner` → `.mobile-app` assertion swap already recorded in 02-01-SUMMARY.md).
- Confirmed no dependency crept in: an `os.walk` scan of `web/` for `package.json`/`package-lock.json`/`yarn.lock`/`vite.config.js` found none, and `web/index.html`'s `<script>`/`<link>` tag set is byte-identical to the pre-Phase-2 base.
- Wrote `COVERAGE.md` with the exact required declaration: this phase integrates no external API/SDK/service.
- Assembled the §6 acceptance-checklist evidence table below (Layout / Gestures / Scrubber / Persistence / Help), one row per applicable checklist bullet, naming the automated test that proves it or marking it hardware-only / out-of-scope-for-this-phase.

## Task Commits

1. **Task 1: Full-suite sweep, landscape/desktop freeze proof, and the coverage declaration** - `602fb9a` (docs)

**Plan metadata:** Not yet committed — the plan is not complete. Task 2 (the blocking Phase B gate review with Dre) is outstanding; this SUMMARY.md's own commit follows immediately below as a `docs` commit, separate from a plan-completion commit.

## Files Created/Modified

- `.planning/workstreams/mobile-ux/phases/02-portrait-layout/COVERAGE.md` - New. The phase's API-coverage declaration (no external API integration).
- `tests/test_mobile_portrait.py` - Added `PHONE_LANDSCAPE` viewport constant and `test_landscape_fallback_is_unchanged`.

## §6 Acceptance-Checklist Evidence Table

Per `design/mobile-ux/INTEGRATION_PLAN.md` §6, scoped to the groups this plan's `<action>` names (Layout / Gestures / Scrubber / Persistence / Help). Rows outside Phase 2's scope (landscape-specific behavior belonging to Phase C, and the Accessibility group belonging to Phase E) are marked out-of-scope rather than silently omitted.

### Layout

| Checklist item | Automated test / evidence |
|---|---|
| §0.5 desktop smoke test passes at every phase gate | `tests/test_desktop_smoke.py` (8 tests) — green in this sweep |
| Portrait: sky ~60% of viewport, mini-rail dock always visible, top chips never overlap the focal label | `tests/test_mobile_portrait.py::test_portrait_layout_proportions_and_chip_overlap` (390x844 and 320x568) |
| Landscape: sky ~75% width, right rail shows field log | **Out of scope for Phase 2** — landscape stays on the D-12 interim fallback until Phase 3's `renderMobileLandscape()`; fallback proven unchanged by `test_landscape_fallback_is_unchanged` (new) |
| Rotating mid-playback preserves word position/play state/speed/zoom/toggles, no remount visible | Proven at the plumbing layer: `tests/test_mobile_plumbing.py::test_layout_mode_survives_rotation`, `::test_gesture_attach_survives_forced_rerenders_without_double_fire`. Full landscape-side state preservation (a distinct mobile landscape view) is Phase 3 scope — landscape today is still the D-12 fallback, which has no portrait-specific state to lose. |
| Desktop (>=1100px) byte-identical to pre-change | Freeze proof: `git diff --exit-code` against pre-Phase-2 base commit `1351450` for `web/style.css`/`web/mobile-gestures.js` (clean) + `tests/test_desktop_smoke.py` green |

### Gestures (gesture-contract.html §03 constants)

| Checklist item | Automated test / evidence |
|---|---|
| Tap sky toggles pause/play within 250ms | `tests/test_mobile_portrait.py::test_sky_gesture_contract` |
| Tap sky with tap-to-pause off has no effect | `tests/test_mobile_portrait.py::test_sky_tap_is_noop_when_tap_to_pause_off` |
| Double-tap sky snaps playhead to the last roll at/before the current position and resumes | `tests/test_mobile_portrait.py::test_sky_gesture_contract` |
| Horizontal swipe steps ±1 roll per 56px of travel; haptic per roll crossed | `tests/test_mobile_portrait.py::test_sky_gesture_contract` (step mechanics). **Haptic firing itself is hardware-only** — iOS Safari has no Vibration API at all (confirmed in `STACK.md`); haptics are decorative-only by design (D-11) and every gesture also gives visible feedback, which the test suite verifies instead. |
| Drag mini-rail scrubs word position, respects zoom + auto-pan offset | `tests/test_mobile_portrait.py::test_rail_scrub_zoom_aware` (1x/2x/4x/8x) |
| Drag cinema-scrub (landscape) | **Out of scope for Phase 2** — Phase C |
| Landscape chrome auto-hides after 4000ms idle | **Out of scope for Phase 2** — Phase C |

### Scrubber zoom + binning

| Checklist item | Automated test / evidence |
|---|---|
| Settings -> Timeline zoom segmented 1x/2x/4x/8x, selected value persists | `tests/test_mobile_portrait.py::test_settings_about_help_persist_across_reload`, `::test_rail_scrub_zoom_aware` |
| At 1x, rail shows counted cluster diamonds, not a smear of overlapping dots | `tests/test_mobile_portrait.py::test_cluster_binning_at_1x` |
| At 8x, individual rolls visible at thumb resolution, auto-pan keeps playhead centred | `tests/test_mobile_portrait.py::test_rail_scrub_zoom_aware` |
| Active roll always renders as a separate cyan diamond on top of any cluster | `tests/test_mobile_portrait.py::test_cluster_binning_at_1x` |

### Persistence

| Checklist item | Automated test / evidence |
|---|---|
| All `bcf:*` keys listed in §4 are read on init and written on change | `tests/test_mobile_portrait.py::test_settings_about_help_persist_across_reload` (mode/on-roll/speed/zoom/comfort), `::test_dock_speed_cycle_persists_and_hint_row_context` (speed), `::test_first_run_help_auto_opens_once` (help-seen) |
| `STORAGE_VERSION` bumped; old keys cleared on first load after upgrade | Done in Phase 1 (D-09); no new keys introduced this phase, so not re-exercised here |

### Help + credits surfaces

| Checklist item | Automated test / evidence |
|---|---|
| First-run help overlay auto-opens; dismissing sets `bcf:help-seen` so later loads don't reopen it | `tests/test_mobile_portrait.py::test_first_run_help_auto_opens_once` |
| About flyout shows story title/credit/SV-FF-AO3 links/dataset stats; its "Gestures & help" link opens the same Help overlay | `tests/test_mobile_portrait.py::test_settings_about_help_persist_across_reload` |

### Hardware-only items for Task 2 (cannot be emulation-verified)

- iOS Safari dynamic toolbar / `svh` settle behavior and real touch latency (RESEARCH Assumption A1, D7 in 02-01-SUMMARY.md, D8 in 02-04-SUMMARY.md).
- Sky letterboxing at phone aspect ratios reading as cinematic framing vs. a bug (RESEARCH open question 1).
- The first-run Help auto-open reading as a welcome, not an obstacle, on a real device (D8 in 02-04-SUMMARY.md).
- Haptic feedback's absence on iOS Safari feeling acceptable in practice (expected/by-design per D-11, not a defect).

## Decisions Made

See `key-decisions` in frontmatter. Short form:
- `requirements-completed` left empty on this plan's own frontmatter — the functional MOBP-01..05 work was already marked complete by plans 02-01..02-04; this plan's contribution is the sweep, not new requirement delivery.
- The freeze-proof diff was run against the actual pre-Phase-2 base commit (`1351450`), not a bare working-tree diff, since the latter would trivially pass once work is committed and wouldn't prove anything about the whole phase.

## Deviations from Plan

None - Task 1 executed exactly as written. No auto-fixes were needed; the phase's four prior plans had already produced a fully green, freeze-compliant state by the time this sweep ran.

## Known Stubs

Carried forward from prior plans' summaries (none block this plan's own Task 1 acceptance bar; each is explicitly on the Phase B gate agenda or has a named future owner):

- D-15: No distinct mobile "details" view in v1 — the Settings mode toggle persists and takes effect on desktop, but portrait always renders the playthrough presentation. **Phase B gate agenda item 1.**
- D-19: Help overlay scoped to `.mobile-sky` rather than full-portrait, so the dock stays operable while it auto-opens. **Phase B gate agenda item 4.**
- The tension between the UI-SPEC's locked Settings/About flyout `bottom:152px` anchor and the dock's real flex-grown height (resolved pragmatically in 02-04 with a bottom-aligned dock + z-index fix, not a re-litigation of either locked value). **Referenced in the dock/flyout item on the gate agenda.**

## Threat Flags

None — this sweep introduced no new surface; it only proves existing surface (from 02-01..02-04) is unchanged and green. The threat register items T-02-16 (repudiation without hardware evidence) and T-02-17 (regression hidden behind a passing suite) are exactly what this plan's freeze-proof-against-base-commit and blocking Task 2 gate mitigate.

## Issues Encountered

None. The 1Password SSH-signing agent that wedged twice during 02-03/02-04 was not encountered during this session's Task 1 commit.

## User Setup Required

None - no external service configuration required for Task 1. Task 2 requires Dre to serve the app locally and walk the checklist on real iOS Safari hardware — not an environment-configuration step, but the plan's own blocking gate.

## Gate Review — Partial Rulings Received (2026-07-26)

Dre reviewed the gate agenda and ruled on four of the six items. **The gate itself is NOT approved** — Dre has not yet run the real-device iOS Safari walkthrough, and items 3 and 5 are feel/visual judgments that only hardware answers. Phase 2 stays open.

| # | Item | Ruling |
|---|------|--------|
| 1 | D-15 — no mobile details view in v1 | **Confirmed.** Extra details work is explicitly deferred; do not build a mobile details view this milestone. The deferred idea in `02-CONTEXT.md` stands as-is. |
| 2 | F-04 — ½×/1×/2×/4× → 2500/5000/10000/25000 words-per-second | **Confirmed.** Mapping to existing desktop rungs is correct; no exact-4× (20000) rung. |
| 3 | F-06 — rail auto-pan recomputes mid-drag at zoom > 1 | **HELD** — pending Dre's hardware testing results. Do not change the behavior until he reports. |
| 4 | D-19 — Help overlay scoped to `.mobile-sky`, not full-bleed | **Confirmed.** |
| 5 | Sky letterboxing at phone aspect ratios | **HELD** — pending Dre's hardware testing results. Do not pre-build a mobile-specific viewBox crop. |
| 6 | F-01/F-02 — retained Phase-1 gesture probe; one superseded portrait-banner assertion in `test_desktop_smoke.py` | **Confirmed** (both). |

### Second review pass (2026-08-01, after Dre's hardware walkthrough)

Dre ran the phone pass and reported: overall good; help glyph pairs stacked vertically; portrait shows no constellations between roll animations while landscape did.

| Item | Outcome |
|------|---------|
| Help gesture glyph pairs wrapping | **Fixed** (`e314ea1`) — icon grid track was 32px, a pair of 18px glyphs overflowed it. Now 44px + `white-space: nowrap`. Affected the swipe row too. |
| Help CTA scrolled out of sight | **Fixed** (`bf7cedc`) — Dre asked for it visible if it reasonably fits. It does not (655px of content into a 506px sky region at 390×844), so the body now scrolls inside `.mobile-help-body` and the CTA is a static footer outside it. A sticky CTA was tried first and rejected: it covered the Heads-up paragraph mid-sentence at scroll-top. |
| D-05 carousel | Dre: "okay with portrait being like it is" — **but** requests a **fallback to the desktop view** from mobile if D-05 does not already cover one, conditional on it not compromising the mobile design. D-05 contains no such escape hatch. NOT yet built or planned — see New Finding below, which may reopen the underlying question. |

### New finding — portrait's sky is empty between rolls (not merely "no carousel")

Verified structurally, independent of any timing: `app.js:1519` sets `scene = cinematicActive ? focusScene(...) : null`, and portrait renders `frame.scene ? renderSkyCamera(...) : null` (`app.js:3335-3338`). Desktop's playthrough calls `renderCarousel(...)` **unconditionally** alongside the same sky camera (`app.js:1528`). So outside a roll cinematic the desktop always shows constellation cards, while portrait's sky-camera layer has **zero children** — measured in-browser at a non-roll position.

Consequence: portrait's largest region (~60% of the screen) is empty except during roll animations. This is what Dre observed. It follows from D-05 (no carousel) combined with D-13 (use the real sky camera, do not port the prototype's persistent procedural-diamond placeholder) — neither decision anticipated that the two together leave the region blank. **Dre's ruling needed:** accept as-is, render some persistent idle sky (the scene model already carries `ambientStars`), or revisit D-05.

### ⚠ Retracted mid-review: "portrait playback is stalled"

An earlier finding in this review that portrait playback and rail scrubbing were frozen was **an artifact of the automation environment and is withdrawn.** The Claude Browser pane runs its tab with `document.visibilityState === "hidden"`, so `requestAnimationFrame` never fires (measured: 0 frames in 1500ms). Playback advancement, cinematic completion, and the focus-animation lock release all ride that rAF tier. Nothing in the app was implicated. Recorded here so a later reader does not resurrect it as a real defect. **Corollary for future review sessions: the Browser pane cannot verify any animated or time-dependent behavior in this app — those need real hardware or a headed Playwright run.**

### Third pass (2026-08-01) — measured on real hardware over USB/CDP

Dre connected a **Pixel 10 Pro XL** (Android/Chrome 151) via USB debugging; measurements below were taken against the live tab through an `adb forward` CDP bridge (viewport 443×864, dpr 2.44, `layoutMode: portrait`, rAF confirmed at 59fps). Helper scripts are session-scratch only, not committed.

**⚠ Correction to the "empty sky" finding above.** Measured over 30s of *real playback*: the sky camera is populated **88% of the time**, empty ~13%, with 17 cinematic transitions. The earlier "empty most of the time" characterization was an artifact of measuring while playback was frozen — a *paused* playhead sitting between rolls shows an empty sky, but during playback rolls arrive densely enough to keep it occupied. The accurate statement is narrower: portrait shows **transient per-roll cinematics only, with no persistent constellation context** — which is what Dre actually observed versus desktop's always-present carousel. Duty cycle is position-dependent (sampled around word 450–540k, a roll-dense stretch); sparser regions will read emptier. Dre's ruling on whether to add a persistent idle sky still stands open, but the case is weaker than first stated.

**Item 5 — sky letterboxing: measured, looks intentional.** At 443×518 the sky SVG fills the region, and its 1.6:1 viewBox under `xMidYMid meet` draws content 443×277, leaving **121px of empty backdrop above and below** (~47% of the region combined). There is no seam or bar — the backdrop is uniform — and a phone screenshot during a Miss cinematic reads as deliberate cinematic framing, the beam descending into empty space as depth. Recommend confirming as-is; no mobile-specific viewBox crop.

**Item 3 — rail auto-pan at zoom > 1: this is a DEFECT, not a taste question.** Driving a real trusted touch drag (`Input.dispatchTouchEvent`) monotonically left-to-right across the rail, sampling pan offset and word position at each step:

| finger | zoom 4× pan | zoom 4× word | zoom 1× pan | zoom 1× word |
|--------|-------------|--------------|-------------|--------------|
| 30% | −8.58 | 398k | 0 | 815k |
| 40% | 0 | **330k** ⬅ backward | 0 | 1.09M |
| 50% | −3.68 | 340k | 0 | 1.36M |
| 60% | −10 | 407k | 0 | 1.63M |
| 70% | −29.9 | 543k | 0 | 1.90M |

At 1× the mapping is exactly linear (each 10% of rail = 272k words = 10% of 2.72M). At 4× the first rightward move drives the playhead **68k words backward**, because each move recomputes auto-pan from the just-committed position, which shifts the content, which changes what the next finger position maps to — a feedback loop that makes the drag non-monotonic.

This contradicts MOBP-03's literal wording ("scrubs word position **accurately** at every zoom level, **including auto-panned positions**"). `test_rail_scrub_zoom_aware` passes because it asserts **single discrete presses**, which are deterministic — the loop only manifests across successive moves within one drag. Likely fix: freeze the pan offset for the duration of a drag (capture at `pointerdown`, release at `pointerup`), which preserves auto-pan for playback and taps while making drags monotonic. **Recommend routing to gap closure (`/gsd-plan-phase 2 --gaps`) rather than treating as a gate ruling.**

### Item 3 defect — FIXED (`ed59087`)

Fixed while awaiting the iOS pass, on Dre's "do any additional work you can" instruction. `onScrub` now captures the auto-pan offset on the first callback of a drag (pointerdown), reuses it for every move, and clears it in `onScrubEnd` and in `attachMobilePortraitGestures` (a structural render tears listeners down mid-drag without firing `onScrubEnd`). Auto-pan still applies to playback and to taps — each tap is its own drag and re-captures. `web/mobile-gestures.js` untouched (D-17), still a single scrub input path.

Test-first: `test_rail_drag_is_monotonic_at_every_zoom` was written before the fix and **verified failing against the pre-fix code** (zoom 2×: `40.000% → 35.000%` on a rightward drag), then passing after. It reads the live playhead marker rather than the bookmark key, since `persistBookmarkNow()` only runs at `onScrubEnd` and the defect lives strictly mid-drag. Suite: 33/33.

If Dre prefers to accept the original behavior instead, revert `ed59087` — the test is the only other thing it touches.

### iOS Safari pass — DONE (2026-08-01), 4 defects found and fixed

Ran on **Daniel's iPhone, iOS 18.5 / Safari 18.5** (viewport 440×760, dpr 3) over `ios-webkit-debug-proxy` + the target-based WebKit inspector protocol. iOS 12.2+ wraps every command in `Target.sendMessageToTarget`, which is why a plain CDP client gets silence; the session is also single-client, so Safari's own Inspector window must be closed for the proxy to attach.

**What iOS confirmed that Android could not:**

- **`svh` is load-bearing, and D-08 was right.** On device `100vh` = **842px** but `100svh` = `100dvh` = **760px** — the delta is Safari's URL bar. Had Phase 1 used `vh`, the shell would be 82px taller than the screen.
- **`navigator.vibrate` is `undefined`** — D-11 confirmed on real hardware. Any haptic felt during the Android pass was Android-only.
- Sky is exactly 60% of viewport (MOBP-01); safe-area insets read 0px with toolbars visible.

**Defects found and fixed on device:**

| # | Defect | Fix |
|---|--------|-----|
| 1 | Help CTA scrolled out of sight | `bf7cedc` — scrolling body, static footer CTA. Dre confirmed visible without scrolling on device. |
| 2 | Dock buttons painted through the About/Settings panel (14px overlap; the locked `bottom: 152px` anchor assumed the prototype's shorter dock — real dock is 304px with its transport row 112–166px from the bottom) | `763cf5f` — panel scoped to `.mobile-sky` per D-19. **UI-SPEC deviation recorded**, Dre chose this over raising the anchor. |
| 3 | Flyouts unescapable — no close button, control didn't toggle, and (regression from `763cf5f`) the backdrop no longer spanned the dock | `727e846` — backdrop restored to `.mobile-app` while the panel stays in the sky; `openMobileSurface` now toggles and reuses its history sentinel instead of stacking one per press. |
| 4 | Whole app scrolled 82px, pushing the top chip cluster off screen — frozen `style.css:45` sets `body { min-height: 100vh }`, the LARGE viewport on iOS | `727e846` — overridden in the mobile block (frozen rule untouched), scoped to portrait so the landscape fallback's desktop shell stays scrollable until Phase 3. |

Defect 3 is worth noting for process: fixing 2 introduced it, and only a *second* device pass caught it. Emulation found neither — both depend on the real dock height and real touch dismissal.

All verified on device after the fix: `overflowPx: 0`, page not scrollable, top chips on screen, flyout 0px overlap with the transport row, tap-outside dismisses, second press toggles shut. Suite 33/33, desktop freeze intact.

## ✅ PHASE B GATE APPROVED — 2026-08-01

Dre, after the four device-found fixes landed: *"I'm happy with everything (for now) after the four fixes."* Gate closed. Nothing outstanding blocks Phase 2.

Final disposition of all gate items:

| Item | Disposition |
|------|-------------|
| 1 — D-15, no mobile details view in v1 | Confirmed. Extra details work deferred. |
| 2 — F-04, speed multipliers → 2500/5000/10000/25000 rungs | Confirmed. |
| 3 — F-06, rail auto-pan mid-drag | Was a real MOBP-03 defect (rightward drag ran backward at zoom > 1); **fixed** in `ed59087` with a test-first regression proof. |
| 4 — D-19, Help overlay scoped to the sky | Confirmed, and extended: Settings/About panels now scope the same way. |
| 5 — sky letterboxing | Accepted as-is. Measured 121px of uniform backdrop above/below the artwork on device, no seam, reads as intentional cinematic framing. No mobile-specific viewBox crop. |
| 6 — F-01/F-02, retained gesture probe + one superseded desktop-smoke assertion | Confirmed (both). |
| Persistent idle sky | **Not pursued.** The original "sky is empty most of the time" claim was wrong — measured 88% populated during real playback. Portrait shows transient per-roll cinematics with no persistent constellation context, which Dre accepted. |
| Desktop-view fallback from mobile | Requested by Dre, conditional on not compromising the mobile design. **Not in Phase 2.** Carried to Phase 4 (Mobile Cutover), which already reworks the landing page and deletes the rotate banner — an escape hatch belongs with that work. |

**Carried into Phase 3 and beyond:** the desktop-view fallback above; the Phase 3 landscape layout must reuse the D-19 sky-scoping convention for its own flyouts rather than reinventing an anchor (defects 2 and 3 above are exactly what that costs); and iOS remains the platform that finds layout defects Android and emulation cannot — budget a real-device pass into every remaining Track A phase gate.

**iOS coverage — resolved later the same day.** At the time this section was written the 2026-08-01 hardware pass had only run on Android/Chrome, which cannot evidence the dynamic-toolbar / `svh` behavior, safe-area insets, or `navigator.vibrate`'s absence (D-11). An iOS Safari 18.5 pass was subsequently completed — see "iOS Safari pass — DONE" below, which supersedes this note.

**On resume:** re-read this table before re-asking anything — items 1, 2, 4, and 6 are settled and must not be re-litigated. Only items 3 and 5 plus the overall approval remain open. If Dre's testing turns up changes, route them through `/gsd-plan-phase 2 --gaps` rather than editing plans in place.

## Next Phase Readiness

**Ready.** Task 2 (the `INTEGRATION_PLAN.md` §5 Phase B gate review) was a blocking human gate that no agent could auto-approve. It was held open across three device passes and resolved by Dre on 2026-08-01 — see "PHASE B GATE APPROVED" below for the final disposition of all six rulings. Track A may proceed to Phase 3.

> *Historical note:* while this gate was open, this section read "Not ready" and the plan returned `CHECKPOINT REACHED` to the orchestrator on each pass. That was the correct behavior at the time; the text above was updated only once Dre actually approved.

Once approved, the remaining plan-closure work (STATE.md/ROADMAP.md/REQUIREMENTS.md updates, the final `docs(02-05): complete ...` metadata commit) still needs to run — that is expected to happen in the continuation agent spawned after Dre's ruling is recorded.

---
*Phase: 02-portrait-layout*
*Completed: 2026-07-26 (Task 1 only — plan not yet closed, see Next Phase Readiness)*

## Self-Check: PASSED

- `.planning/workstreams/mobile-ux/phases/02-portrait-layout/COVERAGE.md` verified present on disk.
- `tests/test_mobile_portrait.py` verified present on disk with `test_landscape_fallback_is_unchanged`.
- Task 1 commit `602fb9a` verified present in `git log --oneline --all`.
- Full suite (32 tests) verified green in this session's own run, not assumed from a prior summary.
