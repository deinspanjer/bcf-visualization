---
phase: 04-mobile-cutover-accessibility
verified: 2026-08-03T03:01:49Z
status: passed
score: 15/15 must-haves verified (6 via accepted override — device-only backstops explicitly ruled on by Dre at the Phase D+E gate)
behavior_unverified: 0
overrides_applied: 6
overrides:
  - must_have: "The banner is genuinely gone on real hardware in both orientations (MOBX-01, FA-MOBX-01 criterion 5)"
    reason: "Dre approved the Phase D+E gate on automated evidence without running the real-device iOS pass. Recorded explicitly in 04-06-SUMMARY.md's gate-closure table: 'Automated only... Residual risk: negligible — the element cannot render if neither its markup nor its CSS exists.' Playwright asserts `.portrait-banner` is null at all three viewport classes and the CSS is provably deleted (0 added / 38 removed vs 57d2768)."
    accepted_by: "Dre"
    accepted_at: "2026-08-03"
  - must_have: "The landing page's help control opens correctly on a real iPhone (MOBX-02, FA-MOBX-02, D11)"
    reason: "Dre approved the Phase D+E gate on automated evidence without running the real-device iOS pass. Recorded explicitly in 04-06-SUMMARY.md's gate-closure table: '14 Playwright tests cover the dialog, its degraded states and the verbatim letter. Residual risk: low — <dialog> behavior on iOS Safari differs from headless Chromium.'"
    accepted_by: "Dre"
    accepted_at: "2026-08-03"
  - must_have: "A screen reader actually SPEAKS the live region on a real device and stays silent through playback (MOBX-03)"
    reason: "Dre approved the Phase D+E gate on automated evidence without performing the VoiceOver check. Recorded explicitly in 04-06-SUMMARY.md's gate-closure table as the one item automation gives no signal on at all: 'A region that is present but never announced would pass all 100 tests.' This is the single most consequential open item and is surfaced prominently in this report rather than folded into a blanket pass."
    accepted_by: "Dre"
    accepted_at: "2026-08-03"
  - must_have: "D-49's desktop-mode measurement: innerWidth and layoutMode read off a real device with Safari's Request Desktop Website enabled"
    reason: "Never measured on hardware. Dre's approval leaves this an unverified inference (the ~980px figure is documentation-only) and explicitly keeps D-50's in-app-desktop-toggle decision deferred to v2 rather than ruling on it now. Recorded verbatim in 04-06-SUMMARY.md's gate-closure table."
    accepted_by: "Dre"
    accepted_at: "2026-08-03"
  - must_have: "On a real iPhone, tapping the very edge of the cinema-scrub play button registers reliably and creates no dead zone against the adjacent progress track (D-39, MOBX-03 backstop)"
    reason: "Synthetic offset-click Playwright assertions (2px hit / 10px miss) proxy a real thumb but were not confirmed on hardware. Not explicitly re-itemized in 04-06-SUMMARY.md's final 4-row closing table, but it is the same class of device-only backstop truth carried on the same gate agenda (04-04-SUMMARY.md 'Backstop items carried to the device pass') and covered by the same 'approved on automated evidence' sign-off. Flagged here for visibility since it was not individually re-confirmed in the closing summary."
    accepted_by: "Dre (via the general Phase D+E gate approval; not individually re-itemized)"
    accepted_at: "2026-08-03"
  - must_have: "prefers-reduced-motion: reduce disables throw decay (ROADMAP.md Phase 4 Success Criterion 5 / MOBX-04)"
    reason: "Throw-to-scrub inertia was never implemented anywhere in the milestone (v2 backlog item MOB2-04); attachSkyGestures's onSwipeEnd(velocity) ignores velocity by design. There is no feature to disable, so the clause has no referent in the shipped code. Recorded as a requirements-accuracy note (not fabricated) in 04-04-SUMMARY.md and 04-06-SUMMARY.md, carried to the gate, and accepted by Dre's sign-off rather than built to satisfy literal wording."
    accepted_by: "Dre"
    accepted_at: "2026-08-03"
---

# Phase 4: Mobile Cutover & Accessibility — Verification Report

**Phase Goal:** Mobile is the real experience — the fallback banner is gone, desktop is provably untouched, and the app is accessible
**Verified:** 2026-08-03T03:01:49Z
**Status:** passed
**Re-verification:** No — initial verification

## Independent Checks Run by This Verifier (not taken from SUMMARY claims)

| # | Check | Command | Result |
|---|-------|---------|--------|
| 1 | Seven web test suites, one invocation | `pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py tests/test_freeze_proof.py tests/test_landing_page.py tests/test_lighthouse_accessibility.py -q` | **100 passed**, exit 0. Per-file counts independently collected: desktop_smoke=6, plumbing=10, portrait=33, landscape=27, freeze_proof=4, landing_page=14, lighthouse=6 → 100. |
| 2 | Whole-milestone CSS freeze | `git diff --numstat 57d2768 HEAD -- web/style.css` | `0  38` — deletion-only, exactly as claimed. |
| 3 | Gesture file freeze (correct base) | `git diff --exit-code 1351450 HEAD -- web/mobile-gestures.js` | exit 0 (byte-identical). Confirmed `57d2768` is the WRONG base for this file (exit 1 — file didn't exist yet at that commit, created in Phase 1), matching the documented rationale in 04-01/04-06-SUMMARY.md for using two bases. |
| 4 | Banner genuinely deleted, not just hidden | `grep -c 'renderPortraitBanner\|LS_PORTRAIT_DISMISSED\|portraitDismissed' web/app.js`; `grep -c 'portrait-banner' web/style.css web/mobile.css` | All zero matches (grep exit 1) — no live code, no comments referencing the removed symbols in either stylesheet. |
| 5 | Live-region hiding technique | Read `.mobile-live-region` rule in `web/mobile.css` directly | `position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap; margin:-1px; border:0; padding:0` — the locked sr-only pattern. No `display:none`, `visibility:hidden`, `aria-hidden`, or zero-dimension box. |
| 6 | Single window-level keydown listener | `grep -c 'window.addEventListener("keydown"' web/app.js` | `1`. (`document.addEventListener("keydown"` also returns `1`, the pre-existing, separate surface-focus-trap listener — expected and unrelated.) |
| 7 | No npm footprint in `web/` | `find web -iname 'package*.json' -o -iname '*.lock' -o -iname 'vite.config*' -o -iname 'webpack.config*' -o -iname 'rollup.config*'` | Empty — no matches. |
| 8 | Survey letter verbatim | `git diff --numstat 57d2768 HEAD -- index.html` | `158  0` — additions only, zero removals. |
| 9 | FAB tap-target check shape | Read `test_cinema_scrub_fab_offset_click_hit_area` in `tests/test_mobile_landscape.py` directly | Confirmed: click 2px outside the painted edge toggles playback, click 10px outside does not (control), the button's own rect is asserted `== 40x40` **as documentation that a rect check cannot verify it**, and the overlay's computed box is asserted `>= 44x44`. No threshold was relaxed to 40. |
| 10 | Debt-marker scan | `grep -nE 'TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER'` across every file this phase touched (`web/app.js`, `web/style.css`, `web/mobile.css`, `index.html`, all new/modified test files) | Zero matches anywhere. |
| 11 | `STORAGE_VERSION` unchanged | `grep -n 'STORAGE_VERSION = ' web/app.js` | Still `"3"` — not bumped, matching the deliberate design decision (RESEARCH Pitfall 5). |
| 12 | `test_desktop_smoke.py`'s only diff this phase | `git diff --stat 277f8f9 HEAD -- tests/test_desktop_smoke.py` | `8 insertions(+), 8 deletions(-)` — matches the single justified assertion restatement (CSS-hidden → DOM-absence) claimed in 04-01-SUMMARY.md; no other file drift. |
| 13 | Phase D+E gate actually closed | `git log --oneline` | `06048e6 docs(04-06): Phase D+E gate approved — milestone closed` exists as a real commit, consistent with the SUMMARY's recorded sign-off. |

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No rotate-to-landscape banner exists anywhere (render fn, call site, storage constant, state field, migration entry, CSS all deleted) | ✓ VERIFIED | Independent check 4 above; zero references anywhere in `web/app.js`/`web/style.css`/`web/mobile.css`. |
| 2 | Desktop UI at ≥1100px is byte-identical to before ANY mobile work started (whole-milestone freeze, not phase-local) | ✓ VERIFIED | Independent checks 2 and 3; `tests/test_freeze_proof.py` (4/4) re-runs this on every invocation, diffed against the correct pre-Phase-1 bases for each file. |
| 3 | Exactly one breakpoint definition pair remains in the repo (the stale Phase-3-diverged copy in `style.css` is gone) | ✓ VERIFIED | `web/style.css`'s deletion removed the `@media (max-width: 900px)...` wrapper; `web/app.js:91`'s `MOBILE_LAYOUT_QUERY` and `web/mobile.css`'s single `@media` block are the only surviving pair (confirmed by reading both files during plan review; no second `@media` breakpoint query found in `web/style.css`). |
| 4 | Landing page shows a title chip, author credit, and 44×44 `?` button above a byte-verbatim Survey letter | ✓ VERIFIED | Independent check 8 (additions-only diff); `tests/test_landing_page.py` (14/14) covers the meta row, letter-verbatim assertion, and the 44×44 button rect. |
| 5 | One visually-hidden `aria-live="polite"` region mounts on both mobile layouts, never on desktop, using the locked sr-only hiding technique | ✓ VERIFIED | Independent checks 5 and 6 (single region, correct CSS); `tests/test_mobile_portrait.py`/`tests/test_mobile_landscape.py` assert desktop absence and non-zero computed box. |
| 6 | Announcements fire on exactly five user-caused triggers (double-tap, swipe-step, scrub-release, arrow-step, Home) and stay silent during free playback, per-move scrub, and plain tap | ✓ VERIFIED | `tests/test_mobile_portrait.py::test_mobile_live_region_silent_during_free_playback` and companion tests; `grep -c 'innerHTML' web/app.js == 0` (text-only writes). |
| 7 | Mobile keyboard equivalents work (arrows step ±1 roll, Home snaps to live edge, `?` toggles Help, Space already worked) with desktop's word-stepping numerically unchanged | ✓ VERIFIED | Independent check 6 (single listener); portrait/landscape tests assert exact roll-position landings and numeric desktop step sizes (10000/2000/word-0). |
| 8 | Every tappable control clears 44×44 CSS px, with the one locked-visual exception (cinema-scrub FAB) verified by offset-click rather than rect | ✓ VERIFIED | Independent check 9; rect assertions extended across both layouts' other controls. |
| 9 | Lighthouse Accessibility scores ≥90 on the mobile preset, via a committed, pinned, non-skippable gate; the score is never conflated with the 44×44 tap-target clause | ✓ VERIFIED | `tests/test_lighthouse_accessibility.py` (6/6) — scored 0.98, `formFactor:"mobile"` and `lighthouseVersion:"13.4.1"` both asserted from the report itself; independence explicitly recorded in both 04-04-SUMMARY.md and 04-05-SUMMARY.md. |
| 10 | Under `prefers-reduced-motion: reduce`, transitions are silenced (pre-existing, verified not duplicated) and the landscape auto-hide window doubles to 8000ms via the single existing preference constant | ✓ VERIFIED | `tests/test_mobile_landscape.py::test_landscape_transitions_already_silenced_under_reduced_motion`, `::test_landscape_chrome_autohide_doubles_under_reduced_motion`; `grep -c 'matchMedia("(prefers-reduced-motion' web/app.js == 1` (no second query). |
| 11 | `prefers-reduced-motion: reduce` disables throw decay | ✗ NOT SATISFIABLE — PASSED (override) | Throw-to-scrub inertia was never implemented anywhere in the milestone; there is no feature to disable. Recorded as a requirements-accuracy note rather than fabricated. See override. |
| 12 | Playback pauses when the page is hidden, on both mobile layouts, with no auto-resume, and desktop is unaffected | ✓ VERIFIED | `tests/test_mobile_portrait.py::test_mobile_hidden_page_pauses_playback_in_portrait`, `::test_desktop_hidden_page_does_not_pause_playback`; `tests/test_mobile_landscape.py::test_mobile_hidden_page_pauses_playback_in_landscape`. |
| 13 | Real-hardware confirmation: banner absent in both orientations on a real iPhone; landing dialog renders/opens correctly on a real iPhone | PASSED (override) | Never run — Dre approved the gate on automated evidence only. See overrides. |
| 14 | Real-hardware confirmation: VoiceOver actually speaks the live-region announcement and stays silent through playback | PASSED (override) | Never run — the one item automation cannot signal on at all. See overrides; flagged prominently below, not buried. |
| 15 | D-49's desktop-mode measurement (`innerWidth`/`layoutMode` with Safari's Request Desktop Website on) and the cinema-scrub FAB's real-thumb edge-tap reliability | PASSED (override) | Never measured/tested on hardware; D-50's ruling stays deferred to v2. See overrides. |

**Score:** 15/15 truths pass — 9 fully VERIFIED by independent re-execution of automated checks, 6 as PASSED (override), all six overrides tracing to Dre's explicit, dated, and honestly-recorded Phase D+E gate approval (2026-08-03) rather than to any gap this verifier is choosing to overlook.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_freeze_proof.py` | Committed, repeatable whole-milestone freeze gate | ✓ VERIFIED | 4 tests, all pass; correctly uses two base commits (`57d2768` for `style.css`, `1351450` for `mobile-gestures.js`), which is factually necessary since the latter file postdates the former commit — a deviation from the plan's literal single-constant design but the only version that can actually pass, and it's documented as such in 04-01-SUMMARY.md. |
| `web/app.js` (banner deletion) | Render fn, call site, state field, storage constant, migration entry all removed | ✓ VERIFIED | Zero grep matches for any banner symbol. |
| `web/style.css` (deletion-only edit) | Zero added lines, non-zero deleted, nothing else touched | ✓ VERIFIED | `0  38` numstat. |
| `web/app.js` (live region + announcer) | `aria-live` region, `mobileRollAnnouncement()`, `announceMobileRoll()`, `rollMarkerModel` reuse | ✓ VERIFIED | `grep -c 'aria-live'==1`, `grep -c 'rollMarkerModel' >= 2`, `grep -c 'innerHTML'==0`. |
| `web/mobile.css` (`.mobile-live-region`, FAB hit-area) | Locked sr-only CSS; transparent `::before` overlay | ✓ VERIFIED | Both rules read directly and match spec exactly (independent checks 5, 9). |
| `index.html` (landing-page markup) | Meta row, dialog, noscript guard, inline script; letter untouched | ✓ VERIFIED | Additions-only diff (`158  0`); `noscript` present; `<dialog>` + `showModal` feature-check present. |
| `tests/test_landing_page.py` | New test file covering happy path + 4 degraded states | ✓ VERIFIED | 14 tests collected and passing. |
| `tests/test_lighthouse_accessibility.py` | Committed, pinned, non-skippable Lighthouse gate | ✓ VERIFIED | 6 tests, no skip markers, pinned to `13.4.1` (3 occurrences), score 0.98. |
| `COVERAGE.md` | Honest, non-fabricated API-coverage declaration | ✓ VERIFIED | Exact-match grep returns 1. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Five gesture/keyboard trigger sites | `announceMobileRoll()` | Direct call after `setWordPos()` | ✓ WIRED | Confirmed via passing tests asserting exactly-once mutation at scrub-release and zero mutations during playback. |
| `rollMarkerModel(roll)` (viz-model.js) | Announcement's outcome branch | Import block edit | ✓ WIRED | `grep -c 'rollMarkerModel' web/app.js` ≥ 2 (import + use); no second classifier written. |
| Existing keydown handler's editable guard | Mobile branch placement | Inserted after guard, before desktop word-stepping | ✓ WIRED | Test asserts a focused form control blocks mobile keys; desktop numeric stepping (10000/2000) is unaffected. |
| `openMobileSurface("help")` | `?` key | Direct call reuse | ✓ WIRED | Toggle-closes-on-second-press behavior proven via `window.history.state` (not `history.length`, empirically corrected in 04-02). |
| `::before` overlay | Host's `position:relative` | New declaration on host rule | ✓ WIRED | Offset-click test (independent check 9) proves dispatch to host; host rect unchanged at 40×40. |
| Module-level `PREFERS_REDUCED_MOTION` constant | Auto-hide delay doubling | Ternary inside `resetMobileChromeHideTimer()` | ✓ WIRED | `grep -c 'matchMedia("(prefers-reduced-motion' web/app.js == 1` (no second snapshot); boundary tests pass both sides. |
| Staged-site fixture | Lighthouse's target URL | `staged_web_runtime_site()` reused, no bespoke server | ✓ WIRED | `tests/test_lighthouse_accessibility.py` module-scoped fixture confirmed reusing the existing helper. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full seven-suite run | `pytest ... -q` (see Independent Checks #1) | 100 passed, exit 0 | ✓ PASS |
| FAB offset-click dispatches to host | Read test source directly (not re-run headlessly by this verifier, but logic independently traced) | 2px-outside click toggles; 10px-outside does not; rect stays 40×40 | ✓ PASS (traced) |
| Lighthouse gate re-executes fresh, not cached | Part of the 100-test run (`tests/test_lighthouse_accessibility.py`, 6 tests) | Passed in this verifier's own invocation, same run that produced the 100/100 result | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` files and no PLAN/SUMMARY declared probe-based verification. `tests/test_freeze_proof.py` and `tests/test_lighthouse_accessibility.py` are pytest modules, not standalone probe scripts, and were verified directly via pytest (Independent Check #1).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| MOBX-01 | 04-01 | Banner deleted end-to-end; desktop byte-identical | ✓ SATISFIED | Independent checks 2, 3, 4. Device confirmation (both orientations) is override-accepted, not automatable. |
| MOBX-02 | 04-03 | Landing page chip/credit/`?`; letter verbatim | ✓ SATISFIED | Independent check 8; `tests/test_landing_page.py`. Device rendering of native `<dialog>` on iOS Safari is override-accepted. |
| MOBX-03 | 04-02, 04-04, 04-05 | Four independent clauses: aria-live announcements, keyboard equivalents, 44×44 tap targets, Lighthouse ≥90 | ✓ SATISFIED (3 of 4 fully automated-verified; the aria-live clause's real-device speech confirmation is override-accepted) | Each clause has its own citation in the phase's own 04-06-SUMMARY.md closure record, independently re-traced above; the Lighthouse score is explicitly and correctly never offered as evidence for the 44×44 bar (verified by reading both plans' explicit statements to that effect). |
| MOBX-04 | 04-04 | Reduced motion: transitions + throw decay disabled, auto-hide doubles | PARTIALLY SATISFIED — transitions and auto-hide doubling verified; throw-decay clause has no referent in shipped code (feature never built) | Recorded honestly as a requirements-accuracy note, not fabricated or silently marked satisfied. Accepted via override rather than treated as a defect, per Dre's gate sign-off. |
| MOBX-05 | 04-04 | Hidden-page pause on both mobile layouts, desktop unaffected | ✓ SATISFIED | Verified (not re-implemented, per D-51) with dedicated portrait/landscape/desktop tests. |

No orphaned requirements found — all five MOBX-01..05 IDs declared across the phase's plans match `REQUIREMENTS.md`'s Phase 4 mapping exactly.

### Anti-Patterns Found

None. Debt-marker scan (Independent Check #10) found zero `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` matches across every file this phase modified. No stub render functions, no hardcoded-empty stub data, no console-log-only implementations found in the reviewed files.

### Human Verification Required

None outstanding for THIS verification pass — the phase's blocking human checkpoint (`04-06-PLAN.md` Task 2, the Phase D+E gate) was already run and explicitly, knowingly resolved by Dre on 2026-08-03, closing commit `06048e6`. That approval is real human input, dated and reasoned, and this verifier is not re-opening a decision the developer already made. It is not being treated as silent or automatic: the residual gap is called out plainly below rather than folded into an unqualified "passed."

**For the record, the following remain genuinely unverified on real hardware** (all six overrides above), and should be re-checked whenever an iOS device pass becomes convenient, particularly:

1. **VoiceOver announcement speech** — the single item automation gives zero signal on. A live region that is present, correctly hidden, and correctly wired could still be silently unannounced on real assistive tech; only a real screen reader on a real device proves this. This is the highest-value item to close first if a device pass happens later.
2. **D-49's desktop-mode measurement** — `innerWidth`/`layoutMode` with Safari's Request Desktop Website enabled, which gates the v2 D-50 decision.
3. Banner absence and landing-dialog rendering on real iOS Safari (lower residual risk — both are structurally impossible to render given the deletion/DOM proof already established, or are Chromium/WebKit rendering-fidelity questions with a mature native `<dialog>` element).
4. Cinema-scrub FAB real-thumb edge-tap reliability.

### Gaps Summary

No blocking gaps. All roadmap Success Criteria for Phase 4 and all five MOBX-01..05 requirements are satisfied by automated, independently-re-executed evidence, with the sole exception of the throw-decay sub-clause of MOBX-04, which names a feature that was never built anywhere in the milestone (v2 backlog `MOB2-04`) — recorded as a requirements-accuracy note rather than fabricated, and explicitly accepted by Dre at the gate rather than silently marked satisfied.

Six items remain verified only by an accepted human override rather than by direct evidence: banner-on-device (both orientations), landing-dialog-on-device, the VoiceOver announcement check, D-49's desktop-mode measurement, the cinema-scrub FAB's real-thumb reliability, and the throw-decay non-clause. All six are honestly documented in 04-04-SUMMARY.md/04-06-SUMMARY.md, all six were explicitly presented to Dre before his 2026-08-03 sign-off, and none of them contradicts any automated evidence — they are simply beyond what a headless browser or CI can prove. This verifier is reporting them transparently rather than treating an already-made human decision as either a fresh open question (which would incorrectly ask "human_needed" for something already decided) or a silently-absorbed pass (which would hide the residual risk).

**One minor, non-blocking observation for the developer's awareness:** the multi-grab announcement phrasing branch (`"{firstPerkName} and {k} more, {cp} CP."`) is implemented per the locked template but ships with no automated test exercising it — 04-02-SUMMARY.md records this honestly as untested-by-design (no fixture in scope has a roll with 2+ purchased perks). This is a test-coverage gap, not a functional defect, and does not block the phase, but is worth closing opportunistically.
