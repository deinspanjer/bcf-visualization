---
phase: 01-epub-refresh-exemplar-mining
plan: 04
subsystem: data-pipeline
tags: [corpus-documentation, exemplar-mining, curation-infrastructure, manifest]

# Dependency graph
requires:
  - phase: 01-03
    provides: "data/derived/exemplar_index.json (118-chapter regime-tagged exemplar corpus + statistics block), scripts/query_exemplars.retrieve()"
provides:
  - "corpus-analysis-report.md — human-readable characterization of the hand-curated corpus's roll-shape distribution, evidence-quote patterns, cp_ledger_checkpoint usage, perk-link conventions, and regime-boundary handling, sourced entirely from exemplar_index.json's statistics block (no epub prose read)"
  - "Confirmation that scripts/verify.py's failure set is unchanged at the 5 pre-existing known-accepted failures (no new regressions across all four Phase 1 plans)"
  - "Confirmation that exemplar_index.json is manifest-registered — via the dev-derived bundle manifest (schema_version: 1), not the pages-runtime data_package.json, per Plan 01-03's already-made architectural decision"
affects: [phase-2-mechanical-verifier, phase-3-agent-curation-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Corpus-characterization documentation sourced strictly from already-computed derived-artifact statistics, never recomputed and never by reading source prose (D-04) — a pattern for any future human-readable report over gitignored/copyright-sensitive source material"

key-files:
  created:
    - .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md
  modified: []

key-decisions:
  - "Task 2's literal <verify> command checked exemplar_index.json's presence in data/derived/data_package.json's files list, but that file is the pages-runtime manifest, which Plan 01-03 already decided (documented in 01-03-SUMMARY.md) should NOT list exemplar_index.json, to avoid shipping a curation-mining artifact into the production webapp bundle. Manifest-registration (D-03) is satisfied instead via the dev-derived bundle manifest (data_release.build_manifest(bundle_class='dev-derived')), confirmed directly: exemplar_index.json present with schema='exemplar_index', schema_version=1, sha256 recorded. No file was changed to force the literal check to pass — the prior plan's architectural decision stands."

requirements-completed: [CINF-02]

coverage:
  - id: D1
    description: "corpus-analysis-report.md exists, covers all six required sections (Overview, Roll-shape distribution, Evidence-quote patterns, cp_ledger_checkpoint usage, Perk-link/naming conventions, Regime-boundary handling), sourced from exemplar_index.json's statistics block, with the one illustrative quote copied verbatim from an existing chapter_roll_overrides.json evidence_quotes entry (no epub prose read)"
    requirement: "CINF-02"
    verification:
      - kind: other
        ref: "test -f corpus-analysis-report.md && grep -ci regime corpus-analysis-report.md (204 lines, 20 regime-mentioning lines)"
        status: pass
      - kind: other
        ref: "grep -n 'the Magitech constellation passed by' data/manual/chapter_roll_overrides.json (verbatim match confirmed at 4 locations)"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/verify.py re-run as the phase's final closing gate: confirms Plan 01-03's pipeline.py edit and new exemplar_index.json artifact did not regress the green state Plan 01-02 established — exactly the same 5 pre-existing known-accepted failures, no new ones"
    requirement: "CINF-02"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/verify.py (5 failed, 587 passed — test_forge_curator.py x4, test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction x1; identical to 01-02/01-03's documented baseline)"
        status: fail
    human_judgment: true
    rationale: "scripts/verify.py does not exit 0 by design of the known-accepted baseline (5 pre-existing Track B failures unrelated to this phase's work, per deferred-items.md and 01-02/01-03-SUMMARY.md). This plan's contribution is proven regression-free (identical failure set), but whether 'exactly the known baseline, no worse' is an acceptable phase-closing state is the same human judgment call 01-02/01-03 already flagged, not re-resolved here."
  - id: D3
    description: "data/derived/exemplar_index.json confirmed manifest-registered with a schema_version, closing CINF-02's manifest-registration requirement (D-03)"
    requirement: "CINF-02"
    verification:
      - kind: other
        ref: "data_release.build_manifest(source_dir=DERIVED, bundle_class='dev-derived', ...)['files']['exemplar_index'] == {path: 'exemplar_index.json', schema: 'exemplar_index', schema_version: 1, sha256: ...}"
        status: pass
    human_judgment: true
    rationale: "The plan's literal verify command checks the wrong manifest file (data_package.json / pages-runtime bundle, which Plan 01-03 deliberately excludes exemplar_index.json from). Confirming the intent (manifest registration) required checking the dev-derived bundle manifest instead — a methodology correction, not a code change, worth a human's eyes given it deviates from the plan's literal text."

duration: 20min
completed: 2026-07-27
status: complete
---

# Phase 1 Plan 4: Corpus-Analysis Report & Phase-Closing Verification Summary

**Authored `corpus-analysis-report.md` (roll-shape, evidence-quote, perk-link, and regime-boundary characterization sourced entirely from `exemplar_index.json`'s statistics, no epub prose read) and confirmed the phase's closing gate: `scripts/verify.py` shows zero new regressions beyond the 5 pre-existing known-accepted failures, and `exemplar_index.json` is manifest-registered via the dev-derived bundle.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-27
- **Tasks:** 2
- **Files created:** 1 (corpus-analysis-report.md)

## Accomplishments

- `corpus-analysis-report.md` (204 lines): six sections covering (1) Overview — 118 curated chapters, regime distribution 101/9/9; (2) Roll-shape distribution — 681 total rolls, 91.3% miss/8.7% hit, and within hits 57.6% are multi-grab (2+ perks) — the single most load-bearing fact for Phase 3 prompt design; (3) Evidence-quote patterns — min/max/mean (0/22/1.269) and `display_position_policy_distribution` (null 598, mechanical 82, source_marker 1), with one illustrative quote copied verbatim from an existing `chapter_roll_overrides.json` entry (chapter 67); (4) `cp_ledger_checkpoint` usage — exactly 1 of 864 quotes carries the marker; (5) Perk-link/naming conventions — points at the existing exact/normalized/separator-split/word-prefix/alias resolution pipeline (`perk_name_resolver.py`, `build_perk_directory.py`) rather than inventing a new one; (6) Regime-boundary handling — chapter 97's dual `regime_tags: [2, 3]`, `is_boundary: true`, two rolls (an Additional Space multi-grab and a Nano-Forge hit), both with zero evidence quotes — illustrating that "hit" and "well-evidenced" are independent in this corpus.
- Re-ran `scripts/verify.py` (git diff --check, `data_release.py check-derived`, full pytest) as the phase's final closing gate: exit 1, but the failure set is byte-identical to the documented known-accepted baseline — `test_forge_curator.py` (4 chapter-79 TUI stats-panel fixtures) and `test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction` (1). No new failures across any of Phase 1's four plans.
- Confirmed `data/derived/exemplar_index.json` is manifest-registered with `schema_version: 1` — via the dev-derived bundle manifest (`data_release.build_manifest(bundle_class="dev-derived")`), not the pages-runtime `data_package.json` (which Plan 01-03 deliberately excludes it from; see Decisions).

## Task Commits

1. **Task 1: Author the human-readable corpus-analysis report** - `167c046` (docs)
2. **Task 2: Final phase-closing verification** - no commit (verification only; no files modified)

**Plan metadata:** committed separately below (docs: complete plan)

## Files Created/Modified

- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` - new file, six-section corpus characterization for Phase 3 prompt design

## Decisions Made

- **Task 2's literal manifest-registration check targets the wrong file.** The plan's `<verify>` command checks `data/derived/data_package.json`'s `files` list for `exemplar_index.json`, but that file is the `pages-runtime` bundle manifest, which Plan 01-03 already and deliberately decided should NOT list `exemplar_index.json` (to avoid shipping a curation-mining artifact into the production webapp bundle — see `01-03-SUMMARY.md`'s Decisions). The actual manifest-registration requirement (D-03) is satisfied via the separate `dev-derived` bundle manifest, confirmed directly by invoking `data_release.build_manifest(bundle_class="dev-derived")`: `exemplar_index` appears with `path: "exemplar_index.json"`, `schema: "exemplar_index"`, `schema_version: 1`, and a `sha256`. No file was edited to force the literal check to pass — Plan 01-03's architectural decision stands unchanged, and re-litigating it is out of this plan's scope (Rule 4 territory, already resolved by a prior plan).

## Deviations from Plan

### Auto-fixed Issues

None — no code was written or fixed by this plan (documentation + verification only).

### Verification Methodology Correction (not a code deviation)

**1. Task 2's manifest-registration `<verify>` command checks the wrong manifest file**
- **Found during:** Task 2
- **Issue:** The plan's automated verify command (`python3 -c "... d.get('files', {}) ..."` against `data/derived/data_package.json`) exits 1 because that manifest deliberately never lists `exemplar_index.json` — an explicit, already-made architectural decision from Plan 01-03, not a bug introduced here.
- **Fix:** None applied to code/data. Verified the actual manifest-registration intent (D-03) against the correct artifact instead: `data_release.build_manifest(source_dir=DERIVED, bundle_class="dev-derived", ...)['files']['exemplar_index']` returns `{'path': 'exemplar_index.json', 'schema': 'exemplar_index', 'schema_version': 1, 'sha256': '5e6c2f...', 'size_bytes': 427618}`.
- **Files modified:** None.
- **Verification:** Direct Python invocation of `build_manifest`, output pasted above; also confirmed the literal (failing) check's output for the record.
- **Committed in:** N/A — no code change.

---

**Total deviations:** 0 code auto-fixes; 1 verification-methodology correction (documented, no files changed).
**Impact on plan:** None on scope. The corrected verification confirms D-03's actual intent is satisfied; the plan's literal check text is stale relative to Plan 01-03's already-made (and correct) architectural decision.

## Issues Encountered

- **`scripts/verify.py` does not exit 0.** Confirmed via a clean re-run: exactly the 5 pre-existing, known-accepted Track B failures documented in `01-02-SUMMARY.md`/`01-03-SUMMARY.md`/`deferred-items.md` remain (`test_forge_curator.py` x4 — chapter-79 TUI stats-panel fixtures; `test_roll_ordinal_contract.py` x1 — chapter 55.1/56/57 roll-ordinal contract). No new regressions introduced by this plan's report-authoring or by any of the prior three plans' work. Per this phase's established pattern (01-02, 01-03), this is a known-accepted gap, not silently marked as satisfying the plan's must_have that `scripts/verify.py` "exits 0."
- **Task 2's manifest check required checking the dev-derived bundle manifest instead of the literal `data_package.json` path** — see Decisions/Deviations above. Not an issue with this plan's own work; a discrepancy between the plan text (authored before Plan 01-03's architectural decision was finalized) and the actual, correct implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ROADMAP Phase 1 Success Criteria 1-4 are all satisfied and observable: epub refreshed (01-01), full pipeline re-run green modulo the 5 known-accepted failures (01-02/01-03), regime-tagged exemplar index with same-regime retrieval (01-03), and corpus documentation (this plan).
- `corpus-analysis-report.md` and `data/derived/exemplar_index.json` (+ `scripts/query_exemplars.retrieve()`) are ready for Phase 2 (Mechanical Verifier) and Phase 3 (agent curation), which consume the index's schema and this report's characterization as a contract.
- CINF-02 marked complete in REQUIREMENTS.md by this plan (shared-ID gate with 01-03-PLAN.md now cleared — both declaring plans have completed).
- Remaining known-accepted gaps, unrelated to this phase's scope, continue to be tracked in `deferred-items.md`: the 5 pre-existing Track B pytest failures (chapter 79 TUI fixtures; chapter 55.1/56/57 roll-ordinal contract), chapter 104's stale alignment anchor (needs Dre's curator-TUI review), and the 7 uncurated chapters that may carry an invisible ch95.5-fix ripple.
- This closes Phase 1 (epub-refresh-exemplar-mining) — all 4 plans complete.

## Self-Check: PASSED

- `[ -f corpus-analysis-report.md ]` → FOUND (204 lines)
- `git log --oneline --all` contains `167c046` → confirmed present
- Re-ran `grep -n "the Magitech constellation passed by" data/manual/chapter_roll_overrides.json` → 4 verbatim matches confirmed
- Re-ran `.venv/bin/python scripts/verify.py` → 5 failed / 587 passed, identical failure set to the documented baseline
- Re-ran the dev-derived manifest check via direct `build_manifest()` invocation → `exemplar_index` present with `schema_version: 1`

---
*Phase: 01-epub-refresh-exemplar-mining*
*Plan: 04*
*Completed: 2026-07-27*
