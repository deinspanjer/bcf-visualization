---
phase: 3
slug: provenance-schema-deterministic-candidate-assembly
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-01
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded without a RESEARCH.md (`--skip-research`): the phase's technical grounding comes from
> `CURATION-CONVENTIONS.md` and the Phase 2 decisions instead.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `.venv/bin/python -m pytest`, `PYTHONPATH=scripts`) |
| **Config file** | existing `tests/` suite in repo root |
| **Quick run command** | `.venv/bin/python -m pytest tests/<touched test file> -q` |
| **Full suite command** | `.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** task-scoped quick command
- **After every plan wave:** `.venv/bin/python -m pytest -q`
- **Before `/gsd-verify-work`:** no NEW failures beyond the known-accepted baseline
- **Max feedback latency:** 180 seconds

---

## Known-accepted failure baseline (do NOT chase)

5 pre-existing failures: 4 in `tests/test_forge_curator.py`, 1 in
`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`.
`scripts/verify.py` exits 1 for that reason. Judge this phase by **no new failures**.

---

## Per-Task Verification Map

*Filled by planner — every task maps to a requirement and an automated command.*

| Task | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|------|------|------|-------------|-----------|-------------------|--------|
| TBD | — | — | CINF-01 / ACUR-01 | unit / integration | see plan tasks | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Schema/consumer tests proving `curated_by` is REQUIRED (an entry missing it fails validation) and that all 118 existing entries carry `"human"` (CINF-01, D-01)
- [ ] Tests for the Stage 1 candidate assembler over synthetic fixtures — bundle grouping, constellation binding, partial-evidence emission (D-06)
- [ ] The per-evidence-class accuracy measurement itself is a test-visible artifact, not console-only (D-08/D-10)

---

## Manual-Only Verifications

**None.** This phase is zero-LLM and writes no hand-curated data. Stage 1 emits candidates only
(D-04) and never touches `chapter_roll_overrides.json` beyond CINF-01's mechanical `curated_by`
stamp, which is verified by schema tests rather than human review.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
