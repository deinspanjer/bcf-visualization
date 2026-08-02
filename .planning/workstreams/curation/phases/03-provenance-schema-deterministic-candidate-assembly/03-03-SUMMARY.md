---
phase: 03-provenance-schema-deterministic-candidate-assembly
plan: 03
subsystem: data-pipeline
tags: [python, measurement, curation, deterministic, matching, pytest]

# Dependency graph
requires:
  - phase: 03-provenance-schema-deterministic-candidate-assembly
    provides: "Plan 03-01's schema-validated curated_by-stamped corpus loader (multi_grab.load_overrides) and Plan 03-02's data/derived/candidate_rolls.json (718 Stage 1 candidates)"
provides:
  - "scripts/measure_candidate_accuracy.py — derive_stub_chapters/match_candidates_to_curated/compute_accuracy: deterministic, zero-LLM accuracy measurement of Stage 1 candidates against the hand-curated corpus, per evidence class"
  - "candidate-accuracy-report.json + candidate-accuracy-report.md — the committed, per-evidence-class Stage 1 accuracy baseline Phase 4 reads to size its inference spend"
affects: [phase-4-inference-refinement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chapter-local greedy nearest-position bipartite matching (distance primary signal, perk-name-overlap tiebreaker only) as the deterministic candidate-to-curated pairing rule, explicitly never joining on roll_number/source_ordinal identity across the diverging predictor/curator numbering sequences."
    - "A stub-chapter predicate (D-09) re-derived live from data on every call — a chapter is a stub iff ALL its curated rolls (vacuously true for zero rolls) carry empty evidence_quotes — never a hardcoded chapter-number list."
    - "Per-evidence-class accuracy reporting (D-08): never a single headline number: matched/partial/missed/unmatched_candidates counters broken out per evidence_kind class, so a majority class (forward_ref, 68% of the corpus) can never mask where Stage 1 actually performs."
    - "A hand-authored markdown report sourced only from a script-generated JSON's own numbers (mirroring Phase 1's corpus-analysis-report.md), rather than a second code-generated prose path — one machine-readable source of truth, one prose read of it."

key-files:
  created:
    - scripts/measure_candidate_accuracy.py
    - tests/test_measure_candidate_accuracy.py
    - .planning/workstreams/curation/phases/03-provenance-schema-deterministic-candidate-assembly/candidate-accuracy-report.json
    - .planning/workstreams/curation/phases/03-provenance-schema-deterministic-candidate-assembly/candidate-accuracy-report.md
  modified: []

key-decisions:
  - "The matching algorithm's position comparison switches units per curated roll: when a curated roll's own word_position is set (2 of 681 curated rolls corpus-wide), both sides compare in raw word-count units; when it's null (the dominant case, 679/681), BOTH sides fall back to their own 0-based ordinal rank within their chapter-local list — never comparing a raw word_position against an ordinal-rank pseudo-position, which would be apples-to-oranges."
  - "A curated roll left unmatched after 1:1 greedy assignment ('missed') is still bucketed into a per-evidence-class total, attributed to its single nearest candidate's evidence_kind (computed ignoring the claim constraint) — this is classification-only, distinct from whether the pairing counted as a real match, and is what makes the 5-counter-per-class shape (curated_rolls/matched/partial/missed/unmatched_candidates) well-defined for every measured curated roll, not just the ones that got claimed."
  - "derive_stub_chapters treats a chapter with zero rolls (chapter 55.1, whose entry is `{\"rolls\": []}` plus only model_validation_resolution metadata) as a stub via vacuous truth (`all()` over an empty list), not as an excluded special case — required to match D-09's originally-flagged 11-chapter list exactly (minus 104)."

requirements-completed: [ACUR-01]

coverage:
  - id: D1
    description: "derive_stub_chapters() re-derives the stub-chapter set live from the corpus (never hardcoded); against the real corpus it returns the 10 originally-flagged chapters minus 104, including 55.1's zero-roll vacuous-truth case"
    requirement: ACUR-01
    verification:
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_stub_chapter_with_all_empty_evidence_quotes_is_derived"
        status: pass
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_live_stub_chapters_exclude_104_include_the_rest"
        status: pass
    human_judgment: false
  - id: D2
    description: "match_candidates_to_curated() pairs curated rolls to candidates via deterministic chapter-local position proximity plus perk-name-overlap tiebreaker, and NEVER relies on roll_number/source_ordinal identity"
    requirement: ACUR-01
    verification:
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_matching_never_relies_on_roll_number_equality"
        status: pass
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_partial_match_counted_separately_from_full_match"
        status: pass
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_curated_roll_with_no_candidate_counted_as_missed"
        status: pass
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_candidate_with_no_curated_roll_counted_as_unmatched"
        status: pass
    human_judgment: false
  - id: D3
    description: "compute_accuracy() returns per-evidence-class totals (direct/general_only/forward_ref/no_evidence), each with the 5 D-08 counters, deterministic across repeated runs (sorted iteration everywhere, never dict/set order)"
    requirement: ACUR-01
    verification:
      - kind: unit
        ref: "tests/test_measure_candidate_accuracy.py#test_determinism_rerun_produces_identical_totals"
        status: pass
      - kind: integration
        ref: "re-ran .venv/bin/python scripts/measure_candidate_accuracy.py against unchanged inputs -> git diff on candidate-accuracy-report.json is empty (byte-identical)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Committed candidate-accuracy-report.json + candidate-accuracy-report.md exist under the phase directory (git-trackable, not caught by data/derived/*.json's gitignore), with by_evidence_class covering all 4 classes and the markdown's numbers matching the JSON's exactly"
    requirement: ACUR-01
    verification:
      - kind: other
        ref: "test -f .../candidate-accuracy-report.json && test -f .../candidate-accuracy-report.md && python -c \"assert set(json['by_evidence_class'])=={'direct','general_only','forward_ref','no_evidence'}\" -> OK"
        status: pass
      - kind: other
        ref: "git status --short shows both report files as newly added (A), tracked, not ignored"
        status: pass
    human_judgment: false
  - id: D5
    description: "The report honestly states Stage 1's real accuracy, including that direct-class outperformance is real but small (4/131 = 3.1% fully anchor-confirmed, vs 0% for the other three classes) — no tuning of build_candidate_rolls.py to flatter the numbers"
    requirement: ACUR-01
    verification: []
    human_judgment: true
    rationale: "Whether the report's D-07 interpretation paragraph is honest/non-misleading prose is a judgment call best confirmed by a human read of candidate-accuracy-report.md's §3, not something a test can assert."
  - id: D6
    description: "No new test failures beyond the 5 known-accepted pre-existing baseline; mechanical_verifier.py unchanged at pass=593/no_evidence=88/fail=0"
    requirement: ACUR-01
    verification:
      - kind: integration
        ref: "PYTHONPATH=scripts .venv/bin/python -m pytest -q -> exactly the same 5 baseline failures (4 test_forge_curator.py, 1 test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction), no new ones"
        status: pass
      - kind: other
        ref: "PYTHONPATH=scripts .venv/bin/python scripts/mechanical_verifier.py -> pass: 593, no_evidence: 88, fail: 0"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-08-02
status: complete
---

# Phase 3 Plan 3: Stage 1 Candidate-Assembly Accuracy Measurement Summary

**Deterministic, zero-LLM measurement of Stage 1's 718 candidates against the hand-curated corpus, broken out per evidence class: Stage 1 proposes a candidate for 96.5% of the 663 measured curated rolls but is anchor-confirmed on only 4 (0.6%), all in the `direct` class — a committed JSON+markdown report for Phase 4 to size its inference spend against.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-08-02
- **Tasks:** 3 (Task 1 was `tdd="true"`: RED then GREEN commits)
- **Files modified:** 4 (all created; no existing files touched)

## Accomplishments

- Added `scripts/measure_candidate_accuracy.py`: `derive_stub_chapters()` (D-09, re-derived live from the corpus every run — correctly excludes chapter 104 as genuinely curated and includes chapter 55.1 via vacuous truth on its zero-roll entry), `match_candidates_to_curated()` (deterministic chapter-local greedy nearest-position bipartite matching, position proximity primary / perk-name overlap tiebreaker, never comparing `roll_number`/`source_ordinal`), and `compute_accuracy()` (D-08's per-evidence-class totals: `curated_rolls`/`matched`/`partial`/`missed`/`unmatched_candidates` for each of `direct`/`general_only`/`forward_ref`/`no_evidence`).
- Ran the measurement against the real corpus: 663 of 681 curated rolls measured (18-roll gap is entirely the 10 excluded stub chapters). 640/663 (96.5%) got some Stage 1 candidate proposed (matched+partial); only 4 (0.6%) were fully anchor-confirmed, and all 4 are in the `direct` class — `general_only`, `forward_ref`, and `no_evidence` each measure exactly 0 full matches.
- Wrote `candidate-accuracy-report.json` (bare `json.dumps` write, not schema-validated/manifest-registered — same standalone QA-instrument posture as Phase 2's `mechanical_verifier.py`, per D-04's discretion note) with `_source`/`_method`/`_stub_chapters_excluded`/`by_evidence_class`/`_generated_from`.
- Authored `candidate-accuracy-report.md`, sourced only from that JSON's own numbers (mirroring Phase 1's `corpus-analysis-report.md`'s "sourcing constraint" discipline): overview, the 4-class × 5-counter table, and an honest interpretation of D-07 — Stage 1's `direct`-class advantage is real (100% of full matches land there) but numerically thin (3.1% of `direct` rolls), and its raw "proposed something" coverage is nearly uniform across all four classes because that coverage comes from the mechanical positional cursor-advance, not evidence-class-aware reasoning.
- Added `tests/test_measure_candidate_accuracy.py`: the 7 named tests the plan specified (stub derivation, roll-number-never-a-signal in both directions, partial-vs-full, missed, unmatched, determinism, live-corpus stub-set assertion) plus one extra full-match sanity check, all pure synthetic-fixture tests except the one required live-corpus assertion.
- Re-ran `scripts/measure_candidate_accuracy.py` against unchanged inputs: `candidate-accuracy-report.json` is byte-identical (empty `git diff`), confirming the sorted-iteration determinism must-have.
- Full suite (`pytest -q`) shows exactly the same 5 known-accepted pre-existing failures, no new ones; `mechanical_verifier.py` unchanged at pass=593/no_evidence=88/fail=0.

## Task Commits

Each task was committed atomically:

1. **Task 1: Stub-chapter derivation + deterministic matching + per-class totals** - `c57693e` (test, RED) then `9c90f41` (feat, GREEN)
2. **Task 2: Run against the real corpus, write the committed JSON + markdown report** - `e8c62cc` (feat)
3. **Task 3: Synthetic-fixture tests for stub derivation and matching** - `9981fc5` (test)

_Note: Task 1 is `tdd="true"` — RED commit (`c57693e`) added a single failing test for `derive_stub_chapters` (module didn't exist yet); GREEN commit (`9c90f41`) implemented all three functions (`derive_stub_chapters`/`match_candidates_to_curated`/`compute_accuracy`) and made it pass. Task 3's commit replaced the minimal RED-phase test file with the plan's full 7-named-test suite (plus one extra), which was already passing against the GREEN implementation._

## Files Created/Modified

- `scripts/measure_candidate_accuracy.py` - New: `derive_stub_chapters`, `match_candidates_to_curated`, `compute_accuracy`, `main()`/CLI writing the committed report
- `tests/test_measure_candidate_accuracy.py` - New: 8 tests (7 named per the plan + 1 extra), synthetic fixtures except one live-corpus assertion
- `.planning/workstreams/curation/phases/03-provenance-schema-deterministic-candidate-assembly/candidate-accuracy-report.json` - New: the committed per-evidence-class accuracy measurement
- `.planning/workstreams/curation/phases/03-provenance-schema-deterministic-candidate-assembly/candidate-accuracy-report.md` - New: prose summary sourced only from the JSON's numbers

## Decisions Made

- Position comparison mode is chosen per curated roll, not per chapter: a curated roll with a real `word_position` (2 of 681 corpus-wide) compares in raw word-count units against a candidate's real `word_position`; a curated roll without one (679/681 — the dominant case) falls back to comparing its own ordinal rank against the candidate's own ordinal rank within its `slot_index`-sorted list, never mixing the two scales.
- A "missed" curated roll (unclaimed after the 1:1 greedy assignment) is still attributed to an evidence-class bucket via its single nearest candidate (computed ignoring the claim constraint) — this classification step is independent from the matched/partial/missed status itself, and is what makes the per-class `curated_rolls` total well-defined for every measured curated roll rather than only the claimed ones.
- `derive_stub_chapters` uses vacuous truth (`all()` over an empty `rolls` list) rather than requiring at least one roll — required for chapter 55.1 (zero rolls, `model_validation_resolution` metadata only) to correctly land in the stub set matching D-09's originally-flagged 11-chapter list.

## Deviations from Plan

None - plan executed exactly as written, including its own explicit discretion notes on matching methodology (position proximity primary, perk-overlap tiebreaker, never `roll_number`/`source_ordinal`) and report format (standalone, not DAG-wired, JSON+markdown pair mirroring Phase 1's and Phase 2's precedents).

## Issues Encountered

- Initial `derive_stub_chapters` implementation required a chapter to have at least one roll before considering it a stub (`rolls and all(...)`), which excluded chapter 55.1 (an entry with zero rolls, only `model_validation_resolution` metadata) from the stub set — failing the acceptance criterion that the derived set exactly match the 10 originally-flagged chapters (minus 104). Fixed by removing the non-empty-rolls guard: an empty `rolls` list is vacuously "all rolls have empty evidence_quotes," which is exactly D-09's literal predicate, not a special case requiring exclusion. Re-verified against the live corpus after the fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 is complete: CINF-01 (Plan 03-01) and ACUR-01 (Plans 03-02/03-03) are both delivered.
- Phase 4 (inference refinement) has its sizing input: `candidate-accuracy-report.json`/`.md` shows Stage 1 narrows the search space well across all evidence classes (96.5% proposed-something coverage) but resolves almost nothing with confidence (0.6% anchor-confirmed overall, 3.1% even within its best class, `direct`) — inference should expect real confirmation work across every class, not just the classes Stage 1 handles worst.
- No blockers.

## Self-Check: PASSED

- All files listed under `key-files.created` verified present on disk (`scripts/measure_candidate_accuracy.py`, `tests/test_measure_candidate_accuracy.py`, `candidate-accuracy-report.json`, `candidate-accuracy-report.md`).
- All 4 commit hashes (`c57693e`, `9c90f41`, `e8c62cc`, `9981fc5`) verified present via `git log --oneline`.
- All plan `<acceptance_criteria>` re-run and passing: `derive_stub_chapters()` against the live corpus returns exactly the 10-chapter set (minus 104); `compute_accuracy()` returns all 4 evidence classes with the 5 named counters each; both report files exist and are git-trackable; the JSON's `by_evidence_class` has all 4 classes; markdown numbers spot-check against the JSON (grep confirms 131/461/663 all present); all 7 named tests plus 1 extra pass; full suite shows exactly the 5-failure known-accepted baseline.
- Plan-level `<verification>` re-run: `.venv/bin/python scripts/measure_candidate_accuracy.py` completes and writes both report files (re-run confirmed byte-identical, empty `git diff`); `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_measure_candidate_accuracy.py -q` green (8 passed); full suite shows no new failures beyond the 5 known-accepted baseline; `mechanical_verifier.py` unchanged at pass=593/no_evidence=88/fail=0.

---
*Phase: 03-provenance-schema-deterministic-candidate-assembly*
*Completed: 2026-08-02*
