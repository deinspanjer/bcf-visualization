---
phase: 2
slug: portrait-layout
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (Python) via pytest |
| **Config file** | none — plain pytest fixtures in `tests/conftest.py` + `tests/helpers/web_runtime_site.py` (Phase 1 pattern) |
| **Quick run command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_portrait.py -x` |
| **Full suite command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_portrait.py -x`
- **After every plan wave:** Run `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(seeded by planner)* | | | MOBP-01 | — | N/A | integration | `pytest tests/test_mobile_portrait.py::test_portrait_layout_proportions_and_chip_overlap -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBP-02 | — | N/A | integration | `pytest tests/test_mobile_portrait.py::test_sky_gesture_contract -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBP-03 | — | N/A | integration | `pytest tests/test_mobile_portrait.py::test_rail_scrub_zoom_aware -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBP-04 | — | N/A | unit/integration | `pytest tests/test_mobile_portrait.py::test_cluster_binning_at_1x -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBP-05 | — | N/A | integration | `pytest tests/test_mobile_portrait.py::test_settings_about_help_persist_across_reload -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | regression | — | N/A | integration | `pytest tests/test_mobile_portrait.py::test_portrait_playback_has_no_recursive_renders -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | regression | — | N/A | integration | `pytest tests/test_mobile_plumbing.py -x` (unmodified, must stay green) | ✅ | ⬜ pending |
| *(seeded by planner)* | | | gate | — | N/A | integration | `pytest tests/test_desktop_smoke.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mobile_portrait.py` — new file covering MOBP-01..05 plus the no-recursive-renders regression check
- [ ] Reuse `tests/helpers/web_runtime_site.py`'s existing `PHONE_PORTRAIT` viewport fixture (do not redefine)
- [ ] No framework install needed — Playwright already present from Phase 1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| iOS Safari toolbar/`svh` behavior, real-device gesture feel | MOBP-01, MOBP-02 | Emulation does not reproduce dynamic toolbar / `100vh` behavior or real touch latency | Dre verifies on hardware at the §5 Phase B gate review (serve via port 8001 preview) |
| Sky letterboxing at portrait aspect ratios (RESEARCH open question 1) | MOBP-01 | Visual judgment call on `renderSkyCamera` viewBox at phone aspect | Inspect during Phase B gate review; file follow-up if viewBox adjustment needed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
