---
phase: 04-mobile-cutover-accessibility
plan: 05
subsystem: testing
tags: [lighthouse, accessibility, axe-core, npm-supply-chain, pytest, playwright-fixture-reuse]

# Dependency graph
requires:
  - phase: 04-04
    provides: the 44x44 tap-target clause closed independently, and the explicit written statement that Lighthouse's target-size audit (24x24) is not evidence for that clause
provides:
  - "tests/test_lighthouse_accessibility.py — a committed, re-runnable pytest module that shells to the pinned lighthouse@13.4.1 CLI against the real staged app and asserts the mobile-preset Accessibility score, form factor, and tool version straight from the report"
  - "the recorded package-legitimacy ruling for the Lighthouse CLI (approved, pinned to 13.4.1), carried verbatim from Task 1's pre-resolved checkpoint"
  - "D-03 re-verified against a real Lighthouse run: the viewport meta permits zoom, both by direct HTML inspection and by the report's own meta-viewport audit"
affects: [phase-d-e-gate]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Browser-free pytest module shelling to an external CLI via subprocess (mirroring tests/test_freeze_proof.py's shape), reusing the existing staged_web_runtime_site() fixture for a real http:// target rather than a bespoke server"
    - "A module-scoped pytest fixture running the (slow, real) subprocess invocation exactly once and handing the parsed JSON report to every test in the file"
    - "Pinning a CLI version as a module-level constant with a comment tying it to the exact package-legitimacy checkpoint that reviewed it"

key-files:
  created:
    - tests/test_lighthouse_accessibility.py
  modified: []

key-decisions:
  - "Task 1's SUS-verdict package-legitimacy checkpoint was already ruled on by Dre ahead of execution (2026-08-02): approve, pinned to lighthouse@13.4.1. Recorded verbatim below, not re-raised."
  - "No remediation was needed: the mobile-preset accessibility score came back 0.98 on the first run, well above the 0.90 threshold, so web/mobile.css and index.html were not touched by this plan."
  - "The gate closes only MOBX-03's Lighthouse score clause. Its 44x44 tap-target clause is a separate, independent check closed in plan 04-04 — Lighthouse's own target-size audit defaults to 24x24 (WCAG 2.5.8 AA), a lower bar, and a passing score here is never offered as evidence for the 44x44 floor."
  - "D-03 (page zoom stays enabled) is re-verified two ways in this gate: a direct regex check on web/index.html's viewport meta content, and an assertion on the report's own meta-viewport audit (WCAG 1.4.4) — both pass, closing the ROADMAP's Phase 4 note with a number instead of an inference."

patterns-established:
  - "A CLI-driven accessibility gate is a subprocess test in the shape of test_freeze_proof.py, not a Playwright test — no browser automation library needed at the pytest level, since Lighthouse launches its own headless Chrome"

requirements-completed: [MOBX-03]

coverage:
  - id: D1
    description: "Package legitimacy of the Lighthouse CLI ruled on by Dre before its first execution, pinned to lighthouse@13.4.1 (Task 1, pre-resolved)"
    requirement: MOBX-03
    verification: []
    human_judgment: true
    rationale: "A supply-chain legitimacy ruling on a SUS-verdict package is, by the plan's own explicit prohibition, never auto-approvable by an agent — Dre's ruling is the verification, already recorded in the plan's <resolution> block and reproduced verbatim below."
  - id: D2
    description: "tests/test_lighthouse_accessibility.py asserts the mobile-preset Lighthouse Accessibility score is >= 0.90, with a failing run listing every non-perfect audit as a work list"
    requirement: MOBX-03
    verification:
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_accessibility_score_at_or_above_threshold"
        status: pass
    human_judgment: false
  - id: D3
    description: "The report's own recorded form factor (mobile) and tool version (13.4.1) are asserted from the JSON report, proving the preset and the reviewed artifact rather than assuming either"
    requirement: MOBX-03
    verification:
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_report_form_factor_is_mobile"
        status: pass
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_report_tool_version_matches_pinned_version"
        status: pass
    human_judgment: false
  - id: D4
    description: "The ephemeral npx invocation leaves web/ and the repo root free of any package manifest, lockfile, or bundler config"
    requirement: MOBX-03
    verification:
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_web_gains_no_dependency_surface"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-03 re-verified: the viewport meta never disables zoom, checked both directly (HTML regex) and against the real audit's meta-viewport score"
    requirement: MOBX-03
    verification:
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_viewport_meta_permits_zoom"
        status: pass
      - kind: e2e
        ref: "tests/test_lighthouse_accessibility.py#test_report_meta_viewport_audit_does_not_flag_zoom_disabled"
        status: pass
    human_judgment: false
  - id: D6
    description: "The gate never skips: no skip marker of any kind exists in the module, and prior test_freeze_proof.py + test_desktop_smoke.py regression suite stays green after this plan's addition"
    requirement: MOBX-03
    verification:
      - kind: other
        ref: "grep -c 'pytest.skip\\|@pytest.mark.skip\\|pytest.importorskip' tests/test_lighthouse_accessibility.py == 0"
        status: pass
      - kind: integration
        ref: "pytest tests/test_freeze_proof.py tests/test_desktop_smoke.py -x -q"
        status: pass
    human_judgment: false

duration: 24min
completed: 2026-08-03
status: complete
---

# Phase 4 Plan 5: Lighthouse Accessibility Gate Summary

**A committed, re-runnable `tests/test_lighthouse_accessibility.py` shells to the pinned `lighthouse@13.4.1` CLI (approved by Dre against a SUS package-legitimacy verdict ahead of execution) against the real staged app, scoring 0.98 on the mobile Accessibility preset — above the 0.90 floor, so no remediation was needed — and re-verifies D-03's zoom-stays-enabled decision against the real audit.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-08-03T01:42:04Z (immediately following 04-04's completion)
- **Completed:** 2026-08-03T02:06:00Z
- **Tasks:** 2 (Task 1 pre-resolved by Dre before this run; Task 2 executed)
- **Files modified:** 1 (`tests/test_lighthouse_accessibility.py`, new)

## Task 1 — Package Legitimacy Ruling (pre-resolved, recorded verbatim)

**This checkpoint was already ruled on by Dre on 2026-08-02, ahead of execution. It was NOT re-raised.**

> **Ruling: approve, pinned to `lighthouse@13.4.1`.** This is a real human decision recorded in advance, not an agent self-approval; the checkpoint's prohibition against an agent clearing its own supply-chain review is untouched and still binds.
>
> Evidence presented to Dre (npm registry, queried 2026-08-02): package first published 2012-03-28 (~14 years), 1,989 published versions, maintainers `paulirish`/`hoten`/`lusayaa` (Chrome/Chrome DevRel), repository `github.com/GoogleChrome/lighthouse`, Apache-2.0 license, no install hooks (`preinstall`/`install`/`postinstall` all absent), version `13.4.1` published 2026-07-20 (13 days before the ruling).
>
> This confirmed the planner's inference: the automated seam's `too-new` verdict keys on the most recent RELEASE date, not package age. Dre was told the heuristic is not nonsense — a compromised release of a legitimate popular package is a real pattern, and 13 days is inside the window a bad release might not yet be caught — and accepted the residual risk against: no install hooks, `npx --yes` ephemeral invocation never entering a `package.json`/lockfile, a target that is a local static page with no access to `data/`/`scripts/`, and research having already fetched and executed this exact version once this cycle.
>
> Two alternatives were offered and declined: pinning an older release to clear the too-new window (rejected — would require re-verifying the 24x24 target-size finding research established by reading 13.4.1's bundled axe-core source), and dropping npm for Chrome DevTools' built-in Lighthouse (rejected — would make the gate manual, against D-40's repeatability requirement).

## Accomplishments

- Wrote `tests/test_lighthouse_accessibility.py`, a browser-free pytest module (shape of `test_freeze_proof.py`, not the Playwright suite) that reuses `staged_web_runtime_site()` for a real `http://` target and invokes `npx --yes lighthouse@13.4.1` restricted to the accessibility category.
- Ran the gate: **score 0.98** at `formFactor: "mobile"`, `lighthouseVersion: "13.4.1"` — both asserted directly from the JSON report, not assumed. Two non-perfect audits were present in the report (`heading-order`, `label-content-name-mismatch`) but did not pull the composite score below the 0.90 threshold, so no remediation was required this plan.
- Asserted D-03 two independent ways: a direct regex check on `web/index.html`'s `<meta name="viewport">` content (no `user-scalable=no`, no `maximum-scale=1`), and the report's own `meta-viewport` audit (WCAG 1.4.4), which scored 1 (pass).
- Asserted `web/` and the repo root gained no `package.json`/lockfile/bundler-config footprint after the ephemeral `npx` invocation.
- Verified the module contains no skip marker of any kind (grep count 0) and that the pinned version string `13.4.1` appears in the file (grep count 3).
- Confirmed the whole-milestone regression suite (`test_freeze_proof.py` + `test_desktop_smoke.py`) and the full six-file web suite (94 baseline + 6 new = 100 tests) remain green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Package legitimacy review of the Lighthouse CLI** — pre-resolved by Dre ahead of execution; no commit (nothing to build, per the `<resolution>` block).
2. **Task 2: The committed mobile-preset Lighthouse Accessibility gate** - `567b6ae` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `tests/test_lighthouse_accessibility.py` (new) - the committed, re-runnable pytest module: a module-scoped fixture runs the pinned Lighthouse CLI once against the staged app and hands the parsed JSON report to six tests covering score, form factor, tool version, dependency-footprint, and D-03's viewport-zoom re-verification (both HTML-level and report-level).

## Decisions Made

- **Task 1's SUS-verdict checkpoint was pre-resolved, not re-raised.** Dre's ruling (approve, pinned to `13.4.1`) is reproduced verbatim above and was not re-litigated or re-run through the automated legitimacy seam.
- **No remediation was performed.** The score (0.98) cleared the 0.90 threshold on the first run, so `web/mobile.css` and `index.html` were not touched — D-41's "fix, re-run, iterate" work-list flow was not triggered.
- **This gate closes only MOBX-03's Lighthouse score clause, not its 44x44 tap-target clause.** Lighthouse's bundled `target-size` audit defaults to 24x24 CSS px (WCAG 2.5.8 AA) — a lower, different threshold that plan 04-04 closed independently via direct `getBoundingClientRect()`/offset-click assertions. Neither check is offered as evidence for the other, matching `04-VALIDATION.md` finding 1 and 04-04's own recorded decision.
- **D-03 (page zoom stays enabled) is re-verified against the real audit, not just the Phase 1 decision.** Both the static HTML check and the report's own `meta-viewport` audit confirm zoom was never disabled; the audit raised no viewport-related finding, so no tension needed recording for Dre.

## Deviations from Plan

None - plan executed exactly as written. Task 1 required no new work since its checkpoint was pre-resolved by Dre; Task 2's implementation matched the plan's `<action>` steps directly, and the score cleared the threshold on the first run so no remediation iteration was needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. `node`, `npx`, and system Google Chrome were all confirmed present in this environment (matching `04-RESEARCH.md`'s "Environment Availability" table) before the gate was written.

## Next Phase Readiness

- MOBX-03 is now fully closed across all three plans: live region + keyboard (04-02), 44x44 tap targets (04-04), and Lighthouse >= 90 (this plan, scored 0.98).
- Gate agenda items carried to the Phase D+E review (per 04-04-SUMMARY.md, unchanged by this plan): MOBX-04's throw-decay wording (feature never existed) and MOBX-05's pause-without-auto-resume behavior.
- The two non-perfect audits observed in this run (`heading-order`, `label-content-name-mismatch`) did not block the gate but are noted here for visibility — they are pre-existing conditions on the app shell, not introduced by this plan, and did not require remediation since the composite score cleared 0.90.
- All six web pytest suites (94 baseline + 6 new) pass: 100 total, exit 0.
- `web/style.css` diff against the whole-milestone base remains exactly `0 added / 38 deleted` — unchanged by this plan, confirming no remediation touched the frozen stylesheet.
- Plan 04-06 (or the phase's closing plan) can proceed to the Phase D+E gate review with Dre, plus the real-device iOS pass.

---
*Phase: 04-mobile-cutover-accessibility*
*Completed: 2026-08-03*

## Self-Check: PASSED

- FOUND: `tests/test_lighthouse_accessibility.py`
- FOUND: commit `567b6ae` (Task 2)
