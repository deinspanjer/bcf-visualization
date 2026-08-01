---
phase: 3
slug: landscape-layout
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (Python) via pytest — same harness as Phases 1–2 |
| **Config file** | none — plain pytest fixtures in `tests/conftest.py` + `tests/helpers/web_runtime_site.py` |
| **Quick run command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_landscape.py -x` |
| **Full suite command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py` |
| **Baseline** | 33 passing at Phase 2 close (6 + 10 + 17) |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** `pytest tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py -x`
- **After every plan wave:** full suite including `tests/test_desktop_smoke.py`
- **Before `/gsd-verify-work`:** full suite green, plus D-23's two-pronged rotation proof
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(seeded by planner)* | | | MOBL-01 | — | N/A | e2e | `pytest tests/test_mobile_landscape.py::test_landscape_layout_proportions -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBL-02 | — | N/A | e2e | `pytest tests/test_mobile_landscape.py::test_chrome_autohide_and_reveal -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBL-03 | — | N/A | e2e | `pytest tests/test_mobile_landscape.py::test_rotation_preserves_state -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBL-04 | — | N/A | e2e | `pytest tests/test_mobile_landscape.py::test_landscape_surface_stack -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | regression | — | N/A | e2e | `pytest tests/test_mobile_portrait.py -k landscape` (rewritten, see Wave 0) | ✅ needs rewrite | ⬜ pending |
| *(seeded by planner)* | | | regression | — | N/A | e2e | `pytest tests/test_mobile_plumbing.py -x` — **must stay green with ZERO edits** | ✅ | ⬜ pending |
| *(seeded by planner)* | | | gate | — | N/A | e2e | `pytest tests/test_desktop_smoke.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] New `tests/test_mobile_landscape.py` covering MOBL-01..04, reusing the established harness (`staged_web_runtime_site`, `_page_with_console_capture`, `_chromium_browser_or_skip`) and the `PHONE_LANDSCAPE = {"width": 844, "height": 390}` viewport already defined in both existing mobile test files.
- [ ] Rewrite `tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` (lines 1264–1298). Its premise inverts: `.app` and `.portrait-banner` stop mounting in landscape, and a mobile surface starts mounting. Restate as "landscape mounts its own mobile surface and never `renderAppShell()`'s markup." The test's own comment already anticipates this.
- [ ] **Do NOT edit `tests/test_mobile_plumbing.py`.** Research confirmed every landscape assertion there checks only `__bcfLayoutMode` and the layout-agnostic `.mobile-gesture-probe`, never desktop-shell markup. It must stay green unmodified — that is the Phase 1 gesture-probe contract.
- [ ] No new fixtures or conftest changes — the existing `tiny-default` package fixture covers this phase.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rotation hand-off on real hardware | MOBL-03 | D-23 mandates both proofs; the roadmap notes the `resize`/`orientationchange` race does not reproduce in emulation | Rotate mid-playback on a real device and confirm word position, play state, speed, zoom and toggles all survive |
| iOS Safari layout + safe areas in landscape | MOBL-01 | Phase 2 found four defects on hardware that a green suite missed; landscape adds a notch-side rail, which is new safe-area territory | Run the pass on iOS specifically (see `reference_device_debugging`); check the right rail clears the notch in both rotation directions |
| Auto-hide feel | MOBL-02 | 4000ms idle and the reveal-vs-pause double-tap are timing judgments a test can assert but not evaluate | Watch chrome hide during playback, confirm first tap reveals without pausing |
| iOS swipe-back vs. history sentinel | MOBL-04 | Research Pitfall 5 (WebKit bug 248303) is WebSearch-sourced and not independently reproduced | Open a flyout, use the iOS edge swipe-back gesture, confirm it closes the surface rather than leaving the app |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
