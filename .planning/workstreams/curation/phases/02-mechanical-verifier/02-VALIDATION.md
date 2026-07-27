---
phase: 2
slug: mechanical-verifier
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
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
| **Framework** | pytest (existing, `.venv/bin/python -m pytest`) |
| **Config file** | existing `tests/` suite in repo root |
| **Quick run command** | `.venv/bin/python -m pytest tests/<touched test file> -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~120 seconds (full suite); corpus-wide verifier test adds epub read time |

---

## Sampling Rate

- **After every task commit:** task-scoped quick command
- **After every plan wave:** `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** no NEW failures beyond the known-accepted baseline
- **Max feedback latency:** 180 seconds

---

## Known-accepted failure baseline (do NOT chase)

5 pre-existing failures, unchanged since before Phase 1: 4 in `tests/test_forge_curator.py`, 1 in
`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`.
`scripts/verify.py` exits 1 for this reason. Judge this phase by **no new failures**, not absolute green.
Documented in `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md`.

---

## Per-Task Verification Map

*Filled by planner — every task maps to a requirement and an automated command.*

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| TBD | — | — | CINF-03 | unit / integration | see plan tasks | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test coverage for the extracted tokenizer module (D-01/D-02), proving `find_text_backed_rolls.py` behavior is unchanged after the rewrite
- [ ] Test coverage for Tier-1/Tier-2 quote matching including the reject-word-level-edits boundary (D-03)
- [ ] Corpus-wide baseline test with skip-if-epub-absent marker (D-10) — new infrastructure; no existing test reads the real epub

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The 14 unresolved perk-name additions (D-11) | CINF-03 | Hand-curated data — curation authority; Dre approves each addition | Executor presents each unresolved name with evidence at a checkpoint; Dre approves/edits/rejects |
| Any residual unresolvable name after the D-11 fix | CINF-03 | Must not be worked around by weakening the check (D-08) | Executor surfaces at a checkpoint; Dre decides |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
