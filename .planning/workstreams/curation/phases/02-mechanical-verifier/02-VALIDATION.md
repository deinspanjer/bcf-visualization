---
phase: 2
slug: mechanical-verifier
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: true
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

Confirmed by `gsd-plan-checker` (2026-07-26): every non-checkpoint task across 02-01/02-03 carries an
`<automated>` block, no watch-mode flags, no unresolved Wave-0 `MISSING` references. (02-02-PLAN.md was removed
2026-08-01 per the D-06(c) CORRECTION — the ~80.8%/"14 unresolvable perk names" finding it existed to remediate
was measured wrong; all 14 names are cost-0 free ride-alongs that resolve against `data/derived/obtained_perks.json`,
and no data fix, alias addition, or Dre-approval checkpoint was ever required.)

| Task | Plan | Wave | Requirement | Test Type | Automated Command (abbrev.) | Status |
|------|------|------|-------------|-----------|------------------------------|--------|
| Tracer: extract + verify_roll core (paid/free perk check) | 02-01 | 1 | CINF-03 | integration | `pytest tests/test_mechanical_verifier.py -k "tracer or ch92"` | ⬜ pending |
| Unit expansion (tiers, tolerance, outcomes, perk resolution) | 02-01 | 1 | CINF-03 | unit | `pytest tests/test_cp_word_index.py tests/test_mechanical_verifier.py` | ⬜ pending |
| `verify_chapter()` + CLI report | 02-03 | 2 | CINF-03 | integration | snapshot diff of `roll_text_evidence.json` | ⬜ pending |
| D-10 corpus baseline (100%, zero fail, zero exceptions) | 02-03 | 2 | CINF-03 | integration | `pytest tests/test_mechanical_verifier.py -k corpus_baseline` | ⬜ pending |
| Full-suite regression (no NEW failures) | 02-03 | 2 | CINF-03 | regression | `pytest -q` diffed against the 5-failure baseline | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Test coverage for the extracted tokenizer module (D-01/D-02), proving `find_text_backed_rolls.py` behavior is unchanged after the rewrite
- [ ] Test coverage for Tier-1/Tier-2 quote matching including the reject-word-level-edits boundary (D-03)
- [ ] Corpus-wide baseline test with skip-if-epub-absent marker (D-10) — new infrastructure; no existing test reads the real epub

---

## Manual-Only Verifications

**None.** The D-06(c) CORRECTION (2026-08-01) found the original D-11 perk-resolution measurement
(~80.8% resolution, "14 unresolvable perk-name" gaps) was wrong: all 14 names are `cost: 0` free
ride-alongs, absent from the rollable roster by design, and resolve cleanly against
`data/derived/obtained_perks.json` (measured 15/15, alongside 99/99 for paid perk mentions via the
existing ladder). The Dre-approval checkpoint and the data fix that would have motivated a
manual-verification entry here (`02-02-PLAN.md`) have both been removed as void. This phase has no
remaining manual-only verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
