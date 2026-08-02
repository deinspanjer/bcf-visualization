---
phase: 4
slug: inference-refinement-confidence-gate-routing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`.venv/bin/python -m pytest`, `PYTHONPATH=scripts`) |
| **Quick run** | `pytest tests/<touched file> -q` |
| **Full suite** | `pytest -q` |
| **Estimated runtime** | ~120s full suite |

## Sampling Rate

- After every task commit: task-scoped quick command
- After every wave: full suite
- Before verify: no NEW failures beyond the known baseline

## Known-accepted failure baseline (do NOT chase)

5 pre-existing: 4 `tests/test_forge_curator.py`, 1
`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`.
`scripts/verify.py` exits 1 for that reason. Judge by **no new failures**.

## Live-API testing policy (phase-specific)

This is the first phase making real API calls. Unit and integration tests MUST NOT hit the
live API — mock the client. Exactly one deliberately-gated path may spend: the calibration
run, which is operator-invoked, emits a dry-run cost estimate first (D-23), and is bounded
by an explicit ceiling. No test in the default `pytest` run may cost money.

## Wave 0 Requirements

- [ ] Mocked-client fixture so Stage 2 logic is testable without spend
- [ ] Deterministic candidate-retrieval tests (scorer ∪ perk-name union, D-01)
- [ ] Confidence-gate tests proving verifier-reject can never be promoted by self-report (D-15)
- [ ] Idempotency test: same inputs → byte-identical output; changed prompt/model → fingerprint invalidates (D-20)

## Manual-Only Verifications

| Behavior | Requirement | Why Manual |
|----------|-------------|------------|
| Calibration cost estimate reviewed before the batch runs | ACUR-02 | Spend gate — operator judgment (D-23) |
| Approval before the first run against uncurated chapters | ACUR-03 | No ground truth past that line (D-24) |

## Per-Task Verification Map

*Filled by planner.*

| Task | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|------|------|------|-------------|-----------|-------------------|--------|
| TBD | — | — | CINF-04 / ACUR-01/02/03 | unit / integration | see plan tasks | ⬜ pending |

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] No test in the default suite spends money
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] `nyquist_compliant: true` set

**Approval:** pending
