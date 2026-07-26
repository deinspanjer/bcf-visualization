---
phase: 1
slug: epub-refresh-exemplar-mining
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `.venv/bin/python -m pytest`) |
| **Config file** | existing `tests/` suite in repo root |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -q -x --ignore=tests/test_desktop_smoke.py` (scope to touched contracts per task) |
| **Full suite command** | `.venv/bin/python -m pytest -q` plus `.venv/bin/python scripts/verify.py` |
| **Estimated runtime** | ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the task-scoped quick command
- **After every plan wave:** Run `.venv/bin/python -m pytest -q` and `scripts/verify.py`
- **Before `/gsd-verify-work`:** Full suite must be green (the 24 pre-existing Track B failures MUST be cleared by this phase — they are in-scope, not baseline)
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

*Filled by planner — every task maps to a requirement and an automated command.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | — | EPUB-01 / EPUB-02 / CINF-02 | — | N/A | integration | see plan tasks | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test coverage for the new exemplar-index build + same-regime retrieval (new test file under `tests/`)

*Existing infrastructure (pytest + `scripts/verify.py` + `data_release.py check-derived`) covers the epub-refresh and pipeline-green requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Any fingerprint drift accepted via `scripts/realign_chapters.py` | EPUB-02 | Interactive accept/skip by design — never `--yes` (hand-curated authority) | Dre reviews each flagged chapter alignment interactively |
| Residual failure tracing to hand-curated data (e.g. ch 95.5 override) | EPUB-02 | Curation authority — agents never edit hand-curated entries | Executor surfaces diagnosis; Dre applies/approves the fix |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
