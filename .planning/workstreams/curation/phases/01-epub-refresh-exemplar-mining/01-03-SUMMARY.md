---
phase: 01-epub-refresh-exemplar-mining
plan: 03
subsystem: data-pipeline
tags: [exemplar-mining, regime-tagging, retrieval, pipeline, curation-infrastructure]

# Dependency graph
requires:
  - phase: 01-02
    provides: "Manifest re-stamped, chapter-alignment drift resolved per Dre's decisions, verify.py results triaged (5 known-accepted Track B failures documented)"
provides:
  - "data/derived/exemplar_index.json — regime-tagged, schema_version-keyed exemplar corpus mined from the 118 hand-curated chapters, with a machine-readable statistics block (regime_distribution, roll_shape_distribution, evidence_quote_stats, cp_ledger_checkpoint usage)"
  - "scripts/build_exemplar_index.py — build script (build_index() pure function + CLI), regime tags sourced only from chapter_facts.json's point_calculation_regime (D-01) / regime_simulator.regime_for_chapter() for boundary chapters (D-02) — never re-derived"
  - "scripts/query_exemplars.py — deterministic same-regime retrieval (retrieve()), no embeddings/fuzzy matching/LLM (D-06)"
  - "build_exemplar_index wired into scripts/pipeline.py's DAG (Step + TARGET_FINAL_STEPS['data']) and picked up by the dev-derived bundle's schema_version auto-discovery"
affects: [01-04, phase-2-mechanical-verifier, phase-3-agent-curation-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "build_* script skeleton (SCHEMA_VERSION constant, pure functions + main(), argparse with standard data/derived + data/manual defaults, stdout summary) — matches scripts/derive_outstanding_perks.py exactly"
    - "Boundary-chapter regime tagging: read regime_simulator.regime_for_chapter() directly for the pre-transition value rather than trusting chapter_facts.json's single-value point_calculation_regime field, which is known-buggy for ch97 (RESEARCH.md Pitfall 1) — this recipe is correct regardless of that separate, deliberately-unfixed bug"
    - "Pure query module pattern: scripts/query_exemplars.py takes an already-loaded index dict, no file I/O in the retrieval path, so Phase 3 can import retrieve() directly"

key-files:
  created:
    - scripts/build_exemplar_index.py
    - scripts/query_exemplars.py
    - tests/test_build_exemplar_index.py
    - tests/test_query_exemplars.py
    - data/derived/exemplar_index.json (gitignored derived artifact)
  modified:
    - scripts/pipeline.py
    - tests/test_pipeline.py

key-decisions:
  - "cp_ledger_checkpoint lives on evidence_quotes in the actual chapter_roll_overrides.json schema, not on the roll object itself (verified via scripts/derive_roll_facts.py's _apply_cp_ledger_checkpoints). build_exemplar_index.py surfaces it at the roll level as a passthrough convenience (_roll_cp_ledger_checkpoint: first quote carrying one, else None) rather than inventing a second roll-level field — a read-only surfacing of already-curated data, not a computation."
  - "data/derived/data_package.json's runtime manifest (the 'manifest' CLI command, bundle_class='pages-runtime') is scoped to a fixed webapp allowlist (visualization_facts + 3 optional scaffold files) and intentionally never lists exemplar_index.json. PATTERNS.md/RESEARCH.md's claim that _top_level_json_files() auto-discovery governs 'the manifest' was only true for the dev-derived bundle (bundle_class='dev-derived', used by the package/check-derived machinery), verified directly this session. exemplar_index.json IS picked up there. Not adding it to RUNTIME_REQUIRED/OPTIONAL was a deliberate choice — that would ship a curation-mining artifact into the production webapp bundle unnecessarily, which is an architectural change (Rule 4) out of this plan's scope."
  - "TDD cadence: both Task 1 and Task 2 (tdd=\"true\") were committed as single feat commits (test + implementation together) rather than separate RED-then-GREEN commits. Documented as a deviation below; both this and the added test-list update to test_missing_output_rebuilds_only_consumers_in_topological_order (a correct, newly-surfaced dependency, not anticipated by the plan's interfaces) are recorded in Deviations."

requirements-completed: []  # CINF-02 is also declared by 01-04-PLAN.md's frontmatter (shared-ID gate, #2388) — stays Pending in REQUIREMENTS.md until 01-04 (ROADMAP success criterion 4 — corpus characterization report) also completes.

coverage:
  - id: D1
    description: "data/derived/exemplar_index.json exists, schema_version-keyed, every one of the 118 hand-curated chapters appears with correct regime tag(s)"
    requirement: "CINF-02"
    verification:
      - kind: unit
        ref: "tests/test_build_exemplar_index.py#test_non_boundary_chapter_gets_single_regime_tag_from_chapter_facts"
        status: pass
      - kind: integration
        ref: ".venv/bin/python scripts/pipeline.py --target data (live regen: 118 exemplars, regime_distribution {1:101,2:9,3:9})"
        status: pass
    human_judgment: false
  - id: D2
    description: "Chapter 97 (documented mid-chapter regime transition) is dual-tagged {2, 3} with is_boundary: true, correct regardless of chapter_facts.json's known-buggy point_calculation_regime value for ch97"
    requirement: "CINF-02"
    verification:
      - kind: unit
        ref: "tests/test_build_exemplar_index.py#test_ch97_boundary_chapter_dual_tagged_regardless_of_buggy_chapter_facts_value"
        status: pass
      - kind: integration
        ref: "live data/derived/exemplar_index.json: ch97 regime_tags=[2,3], is_boundary=true"
        status: pass
    human_judgment: false
  - id: D3
    description: "query_exemplars.retrieve() never returns a cross-regime exemplar; boundary exemplars are visible to both adjacent regimes; retrieval is deterministic"
    requirement: "CINF-02"
    verification:
      - kind: unit
        ref: "tests/test_query_exemplars.py#test_no_cross_regime_exemplar_ever_returned_across_all_regimes"
        status: pass
      - kind: unit
        ref: "tests/test_query_exemplars.py#test_retrieve_is_deterministic_across_repeated_calls"
        status: pass
    human_judgment: false
  - id: D4
    description: "build_exemplar_index wired into scripts/pipeline.py's DAG (Step + TARGET_FINAL_STEPS['data']) and tests/test_pipeline.py reflects the 14-step DAG; check-derived and full pytest remain at the pre-existing known-accepted baseline (no new regressions)"
    requirement: "CINF-02"
    verification:
      - kind: integration
        ref: ".venv/bin/python -m pytest tests/test_pipeline.py -q (14-step DAG, all pass)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python scripts/data_release.py check-derived (exit 0, 'local derived data ok')"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest -q (exactly the same 5 pre-existing Track B failures as 01-02-SUMMARY.md documented; no new failures once a transient 1Password signing wedge cleared)"
        status: pass
    human_judgment: true
    rationale: "The plan's must_have text says the full pytest suite should 'remain green' after wiring; it does not exit 0 (5 pre-existing, documented, unrelated failures per 01-02-SUMMARY.md/deferred-items.md — chapter 79 TUI fixtures, chapter 55.1/56/57 roll-ordinal contract). This plan's own contribution is proven regression-free (identical failure set before and after, confirmed via a clean re-run), but 'is this an acceptable definition of done given the pre-existing gap' is the same judgment call 01-02 already flagged for a human reviewer, not something this plan re-resolves."

duration: 90min
completed: 2026-07-27
status: complete
---

# Phase 1 Plan 3: Regime-Tagged Exemplar Index & Same-Regime Retrieval Summary

**Built `data/derived/exemplar_index.json` (118 curated chapters, ch97 dual-tagged {2,3}) via a new `build_exemplar_index.py`/`query_exemplars.py` pair, wired into `scripts/pipeline.py`'s DAG — regime tags sourced only from the pipeline's existing computation, never re-derived, and full pytest confirms no new regressions beyond the pre-existing 5 known-accepted failures.**

## Performance

- **Duration:** ~90 min
- **Tasks:** 3
- **Files modified:** 6 tracked (2 new scripts + 2 new test files + 2 modified pipeline/test files), 1 gitignored derived artifact regenerated

## Accomplishments

- `scripts/build_exemplar_index.py`: mines `data/manual/chapter_roll_overrides.json`'s 118 curated chapters, tagging each with its CP regime from `chapter_facts.json:point_calculation_regime` (D-01) for the ordinary case, or `{regime_simulator.regime_for_chapter(), transition["new_regime"]}` plus `is_boundary: True` for chapters listed in `regime_transitions.json` (D-02) — verified live: ch97 tags `[2, 3]`, `is_boundary: true`, correct regardless of `chapter_facts.json`'s separately-documented buggy value (RESEARCH.md Pitfall 1, deliberately not fixed here).
- Emits per-roll records (perks, outcome, constellation, `display_position_policy`, `evidence_quotes` verbatim, `cp_ledger_checkpoint`) plus a `statistics` block. Live regen matches RESEARCH.md's pre-verified corpus baseline exactly: `roll_shape_distribution {0:622, 1:25, 2:22, 3:6, 4:2, 5:2, 7:1, 8:1}`, `evidence_quote_stats {min:0, max:22, mean:1.269, total:864}`, `cp_ledger_checkpoint_usage_count: 1`.
- `scripts/query_exemplars.py`: pure `retrieve(target_regime, index, *, k=None, target_chapter=None)` — filters to same-regime exemplars only, sorts deterministically (chapter-proximity to `target_chapter` when given, else chapter_num ascending), truncates to `k`. Boundary exemplars are visible from both adjacent-regime queries. No embeddings, no fuzzy matching, no LLM (D-06).
- Wired `build_exemplar_index` into `scripts/pipeline.py`'s `build_steps()` and `TARGET_FINAL_STEPS["data"]`; updated `tests/test_pipeline.py`'s `DATA_STEP_NAMES` (14 entries) and the dry-run stdout-count assertion.
- Confirmed `data/derived/exemplar_index.json` is picked up by the dev-derived bundle's `_top_level_json_files()` schema_version auto-discovery (verified directly) — the runtime `data_package.json` manifest is a separate, fixed webapp-runtime allowlist that never lists it (see Decisions).
- Live-ran `scripts/pipeline.py --target data`, `scripts/data_release.py manifest`, `scripts/data_release.py check-derived` (exit 0), and the full `pytest` suite: exactly the same 5 pre-existing, known-accepted failures as `01-02-SUMMARY.md` documented, once a transient 1Password commit-signing wedge (unrelated to this repo, root-caused via an isolated `/tmp` reproduction) cleared.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the exemplar index (regime tagging + boundary dual-tagging + statistics)** - `312cb00` (feat)
2. **Task 2: Deterministic same-regime retrieval function** - `2c150e8` (feat)
3. **Task 3: Wire build_exemplar_index into the pipeline DAG and manifest, then verify green** - `5f98389` (feat)

**Plan metadata:** committed separately below (docs: complete plan)

## Files Created/Modified

- `scripts/build_exemplar_index.py` - build script: `build_index()` pure function + CLI (`--overrides`/`--chapter-facts`/`--transitions`/`--output`), `SCHEMA_VERSION = 1`
- `scripts/query_exemplars.py` - pure `retrieve()` function + thin CLI debug wrapper
- `tests/test_build_exemplar_index.py` - 7 tests covering regime tagging, ch97 boundary dual-tag, determinism, malformed-input ValueError, statistics correctness, cp_ledger_checkpoint passthrough
- `tests/test_query_exemplars.py` - 7 tests covering same-regime constraint, boundary dual-visibility, determinism, k-truncation, proximity ranking
- `scripts/pipeline.py` - new `Step(name="build_exemplar_index", ...)`, added to `TARGET_FINAL_STEPS["data"]`
- `tests/test_pipeline.py` - `DATA_STEP_NAMES` now 14 entries, dry-run count 13→14, missing-output-rebuild fixture test updated to include `build_exemplar_index` (a correct new dependency on `chapter_facts.json`, not anticipated by the plan's interfaces)
- `data/derived/exemplar_index.json` - new derived artifact (gitignored), 118 exemplars, `schema_version: 1`

## Decisions Made

- **`cp_ledger_checkpoint` surfaced from `evidence_quotes`, not invented as a roll-level field.** The actual schema nests this metadata on the quote (`scripts/derive_roll_facts.py::_apply_cp_ledger_checkpoints`), not the roll object itself. `build_exemplar_index.py` reads it as a passthrough (`_roll_cp_ledger_checkpoint`) rather than adding a second representation.
- **`data/derived/data_package.json`'s runtime manifest deliberately does NOT list `exemplar_index.json`.** Verified directly this session: the `manifest` CLI command builds a `bundle_class="pages-runtime"` manifest scoped to a fixed allowlist (`visualization_facts` + 3 optional scaffold files) — `_top_level_json_files()`'s `schema_version` auto-discovery only governs the separate `dev-derived` bundle (used by `package`/`.data-release/*.tar.gz`), where `exemplar_index.json` IS picked up. Adding it to the runtime allowlist would ship a curation-mining artifact into the production webapp bundle unnecessarily — an architectural change outside this plan's scope, not undertaken.
- **TDD cadence collapsed to one commit per task.** Both Task 1 and Task 2 (`tdd="true"`) were implemented and tested together and committed as single `feat(...)` commits rather than separate `test(...)` (RED) then `feat(...)` (GREEN) commits. See TDD Gate Compliance below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - test needed updating for a correct new behavior] `test_missing_output_rebuilds_only_consumers_in_topological_order` needed `build_exemplar_index` added to its expected rebuild list**
- **Found during:** Task 3
- **Issue:** This existing fixture test asserts the exact rebuild plan when `roll_text_evidence.json` is missing. Adding `build_exemplar_index` (which depends on `chapter_facts.json`, itself downstream of the missing file via `derive_roll_facts` → `build_chapter_facts`) correctly makes it cascade into the rebuild plan too — the plan's own interfaces only flagged the `DATA_STEP_NAMES` list and dry-run count string as needing updates, not this fixture test.
- **Fix:** Added `"build_exemplar_index"` to the test's expected list.
- **Files modified:** tests/test_pipeline.py
- **Verification:** `.venv/bin/python -m pytest tests/test_pipeline.py -q` passes (4/4)
- **Committed in:** `5f98389` (Task 3 commit)

**2. [Environmental, not a code deviation] Transient 1Password SSH-agent signing wedge blocked git commits mid-session**
- **Found during:** Task 3, after the full pytest run
- **Issue:** `git commit` (and `git commit` in this project's own test fixtures, e.g. `test_release_workflow_regeneration.py`, `test_source_epub_hydration.py`) began failing with `error: 1Password: agent returned an error` / `failed to fill whole buffer` mid-session. First full pytest run showed 8 failures (5 known-accepted + 3 from this signing wedge breaking test-internal `git commit` calls in isolated tmp repos).
- **Investigation:** Reproduced identically in a scratch `/tmp` directory entirely outside this repo, confirming it was a machine-level 1Password SSH-agent issue (matches the user's own documented runtime quirk: "1Password signing can wedge"), not caused by any change in this plan.
- **Resolution:** Waited/retried; the agent recovered after several attempts. Re-ran the full suite cleanly afterward: exactly the same 5 pre-existing failures as `01-02-SUMMARY.md`, no new ones.
- **Files modified:** None — no code or config change; never bypassed signing (`-c commit.gpgsign=false` was correctly not used).
- **Committed in:** N/A (environmental; no file change)

---

**Total deviations:** 1 auto-fixed (test-list update for a correct new dependency), 1 environmental (transient signing wedge, resolved without any workaround, verified regression-free).
**Impact on plan:** No scope creep. The signing wedge caused zero data loss (all commits landed cleanly once it cleared) and is unrelated to this plan's code.

## TDD Gate Compliance

Task 1 and Task 2 carry `tdd="true"` but were each committed as a single `feat(...)` commit (test + implementation together) rather than a separate `test(...)` (RED) commit followed by `feat(...)` (GREEN). Both tasks' tests were written and run to green in one pass without a preceding verified-failing state committed to git history. This is a process deviation from the strict RED→GREEN→REFACTOR cadence documented in `tdd_execution`; the resulting code and tests are correct and verified (all 14 tests across both files pass, malformed-input and determinism cases included), but the gate-sequence git-history proof (a `test(...)` commit preceding a `feat(...)` commit) is absent for both tasks.

## Issues Encountered

- **`scripts/verify.py`/full pytest does not exit 0.** Confirmed via a clean re-run (after the transient 1Password signing wedge cleared) that exactly the 5 pre-existing, known-accepted Track B failures documented in `01-02-SUMMARY.md`/`deferred-items.md` remain (`test_forge_curator.py` x4, `test_roll_ordinal_contract.py` x1) — no new regressions introduced by this plan's changes. Per this phase's established pattern (01-02), this is a known-accepted gap, not silently marked as satisfying the plan's must_have.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `data/derived/exemplar_index.json` and `scripts/query_exemplars.retrieve()` are ready for Plan 01-04 (corpus characterization report, ROADMAP Success Criterion 4) and, downstream, Phase 2 (Mechanical Verifier) and Phase 3 (agent curation) which consume this index's schema as a contract per RESEARCH.md.
- CINF-02 requirement stays "Pending" in REQUIREMENTS.md (shared-ID gate with 01-04-PLAN.md, which also declares it) until 01-04 completes.
- The 5 pre-existing Track B failures (chapter 79 TUI fixtures; chapter 55.1/56/57 roll-ordinal contract) remain open, unrelated to this plan, tracked in `deferred-items.md`.
- Ch 104's alignment anchor remains deliberately stale pending Dre's manual TUI review (unrelated to this plan; tracked since 01-02).

## Self-Check: PASSED

- `[ -f scripts/build_exemplar_index.py ]` → FOUND
- `[ -f scripts/query_exemplars.py ]` → FOUND
- `[ -f tests/test_build_exemplar_index.py ]` → FOUND
- `[ -f tests/test_query_exemplars.py ]` → FOUND
- `[ -f data/derived/exemplar_index.json ]` → FOUND
- `git log --oneline --all` contains `312cb00`, `2c150e8`, `5f98389` → confirmed present
- Re-ran `.venv/bin/python -m pytest tests/test_build_exemplar_index.py tests/test_query_exemplars.py tests/test_pipeline.py -q` → all pass
- Re-ran `.venv/bin/python scripts/data_release.py check-derived` → exit 0, "local derived data ok"
- Re-ran full `.venv/bin/python -m pytest -q` → 5 failures (the known-accepted baseline), matching this SUMMARY's claims exactly

---
*Phase: 01-epub-refresh-exemplar-mining*
*Plan: 03*
*Completed: 2026-07-27*
