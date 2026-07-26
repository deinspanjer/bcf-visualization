---
phase: 1
slug: mobile-state-gesture-plumbing
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-25
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + Playwright (existing, verified in `.venv`; harness at `tests/helpers/web_runtime_site.py`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~60 seconds (Playwright browser launch dominates) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01/T1 | 01-01 | 1 | MOBF-02, MOBF-03, MOBF-04 (impl) | T-01-01 | allow-list readers on all 4 new bcf:* keys | syntax + integration | `node --check web/app.js web/mobile-gestures.js && diff -q design/mobile-ux/prototype/gestures.js web/mobile-gestures.js && .venv/bin/python -m pytest tests/test_web_app_integration.py -q` | ✅ existing suite | ⬜ pending |
| 01-01/T2 | 01-01 | 1 | MOBF-02, MOBF-03, MOBF-04 (proof) | T-01-01, T-01-02 | tamper values fall back to defaults; render-count guard | integration (Playwright) | `.venv/bin/python -m pytest tests/test_mobile_plumbing.py -x -q` | ❌ Wave 0 — created by this task | ⬜ pending |
| 01-02/T1 | 01-02 | 2 | MOBF-05 | T-01-04 | touch-action/overscroll scoped behind mobile query only | integration (computed-style) | `.venv/bin/python -m pytest tests/test_mobile_plumbing.py -k css -x -q` | extends 01-01/T2 file | ⬜ pending |
| 01-02/T2 | 01-02 | 2 | D-02 (MOBX-05 pre-wiring) | T-01-05 | mobile-only guard on layoutMode | integration (Playwright) | `.venv/bin/python -m pytest tests/test_mobile_plumbing.py -k visibility -x -q` | extends 01-01/T2 file | ⬜ pending |
| 01-03/T1 | 01-03 | 2 | MOBF-06 (§0.5 steps 1-4) | T-01-06 | — | integration (Playwright) | `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q` | ❌ Wave 0 — created by this task | ⬜ pending |
| 01-03/T2 | 01-03 | 2 | MOBF-06 (§0.5 steps 5-6) | T-01-06 | spurious-render counter guard | integration (Playwright) | `.venv/bin/python -m pytest tests/test_desktop_smoke.py -x -q` | same file as 01-03/T1 | ⬜ pending |
| 01-04/T1 | 01-04 | 3 | MOBF-01, MOBF-06 (gate) | T-01-08 | dual gate: deterministic + human review | full gate | `.venv/bin/python scripts/verify.py` | ✅ exists | ⬜ pending |
| 01-04/T2 | 01-04 | 3 | MOBF-01, MOBF-06 (review) | T-01-08 | — | checkpoint:human-verify | (blocking review — §5 Phase A) | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_desktop_smoke.py` — scripted §0.5 desktop smoke test (MOBF-06); follows `tests/test_web_app_integration.py` pattern (created by plan 01-03)
- [ ] `tests/test_mobile_plumbing.py` — layout-mode matrix, gesture single-fire, storage round-trip proofs (created by plan 01-01 Task 2, extended by plan 01-02)
- [ ] `tests/helpers/web_runtime_site.py` — `WEB_FILES` must gain `"mobile-gestures.js"` (plan 01-01) and `"mobile.css"` (plan 01-02) so the staged site serves the new files

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-device iOS Safari rotation/toolbar behavior | MOBF-02, MOBF-05 | Emulation does not reproduce dynamic-toolbar `svh` behavior or `orientationchange` timing races | Load staged site on a physical iPhone; rotate mid-playback; confirm layoutMode flips and layout heights track the visible viewport |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
