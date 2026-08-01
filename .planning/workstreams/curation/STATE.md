---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 3 — Provenance Schema & Agent Curation Pipeline
current_plan: Not started
status: planning
stopped_at: Completed 02-03-PLAN.md
last_updated: "2026-08-01T18:38:43.000Z"
last_activity: 2026-08-01
last_activity_desc: Phase 2 complete, transitioned to Phase 3
progress:
  total_phases: 2
  completed_phases: 2
  total_plans: 6
  completed_plans: 6
workstream: curation
created: 2026-07-26
---

# Project State

## Current Position

**Status:** Ready to plan
**Current Phase:** 3 — Provenance Schema & Agent Curation Pipeline
**Current Plan:** Not started
**Last Activity:** 2026-08-01
**Last Activity Description:** Phase 2 complete, transitioned to Phase 3

## Progress

**Phases Complete:** 2 / 2
**Plans Complete:** 6 / 6
**Current Plan:** None — Phase 2 complete, Phase 3 not yet planned

## Performance Metrics

**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| 01-01 | 50 min | 3 tasks (1 checkpoint:decision) | 8 tracked files + 13 gitignored derived files |
| 01-02 | 165 min | pre-task + 3 tasks (1 checkpoint, resolved after read-only investigation) | 3 tracked files + gitignored derived files regenerated twice |
| Phase 1 P03 | 60min | 3 tasks | 6 files |
| Phase 1 P04 | 20min | 2 tasks | 1 files |
| Phase 2 P01 | 25 min | 2 tasks | 6 files |
| Phase 2 P03 | 55min | 3 tasks | 2 files |

## Accumulated Context

### Decisions

- [01-01]: Ch 95.5 `multi_grab` override — Dre approved option-a: `mention_chapter_num` set to `"95"` (matches `obtained_perks.json`'s live mechanical attribution), not option-b (`"96"`, evidence-quote chapter) or option-c (defer).
- [01-01]: `section_classifications.json` regenerated via its own `build_section_classifications.py` script for the new chapter 121.1 (Dre-approved dynamic checkpoint) — safe/idempotent, preserves curator toggles, verified via before/after diff.
- [01-01]: `chapter_publication_dates.json` gap for ch 121.1 fixed by hand-appending one Dre-provided row (published 2026-07-23 00:48 EST), NOT by re-running the destructive `seed_chapter_publication_dates.py` bootstrap (stale AO3 snapshot + full-file overwrite risk).
- [01-01]: A DAG ordering gap in `build_chapter_facts.py`/`data_release.py` (manifest freshness checked against not-yet-rebuilt `visualization_facts.json`) was worked around by running `build_visualization_facts.py` once manually (orchestrator-approved, no code change) rather than fixed — recorded in `phases/01-epub-refresh-exemplar-mining/deferred-items.md` as a follow-up.
- [01-02]: Ch 121.1@2 (Interlude Jack Slash) and 121.1@9 (Addendum Apeiron) curator-toggled to `counts_for_cp: true` per author Word-of-God relayed by Dre (`WOG-NOTES.md`) — Dre-approved pre-task, applied before the plan's own tasks.
- [01-02]: 5-chapter alignment-fingerprint drift (100, 104, 109, 112, 114) root-caused via an isolated, read-only experiment (reconstructed pre-refresh epub from `data/private-source` git history, compared with/without the ch95.5 fix) to the Dre-approved ch95.5 `mention_chapter_num` fix alone — not the epub refresh, not the 121.1 toggles. The problematic ch95.5 override predates the fingerprint stamps by ~1 week, meaning this is pre-existing curation drift the refresh surfaced, not introduced.
- [01-02]: Dre reviewed each drifted chapter's diff interactively via `scripts/realign_chapters.py` (never `--yes`) and decided: accept 100, 109, 112, 114 (re-stamped); skip 104 (2 curated hits exceed the model's 1 predicted slot — needs a curator-TUI edit first, not a plain re-stamp).
- [01-02]: `scripts/verify.py` does not exit 0 (5 pre-existing, unrelated Track B failures remain: `test_forge_curator.py` x4 unchanged, `test_roll_ordinal_contract.py` down from 9 to 1). Documented as a known-accepted gap per explicit instruction — not forced green by editing hand-curated data, not silently marked as satisfying the plan's must_have.
- [Phase 1]: Exemplar index (data/derived/exemplar_index.json) built from the 118-chapter hand-curated corpus: regime tags sourced from chapter_facts.json's point_calculation_regime (D-01), ch97 dual-tagged {2,3} via regime_simulator.regime_for_chapter() for the boundary case (D-02), never a second regime implementation.
- [Phase 1]: data/derived/data_package.json's runtime manifest (written by 'manifest' CLI) is scoped to a fixed webapp-runtime allowlist and does not list exemplar_index.json by design; manifest tracking for the new artifact comes from the dev-derived bundle's schema_version auto-discovery (_top_level_json_files), verified directly rather than assumed from PATTERNS.md.
- [01-04]: corpus-analysis-report.md authored from exemplar_index.json statistics only (no epub prose); multi-grab hits are 57.6% of all hits (34/59), the load-bearing fact for Phase 3 prompt design.
- [01-04]: Task 2's manifest-registration check was corrected to the dev-derived bundle manifest (exemplar_index schema_version:1 confirmed there), not data_package.json's pages-runtime manifest — consistent with Plan 01-03's already-made architectural decision to exclude it from the runtime bundle.
- [02-01]: Tier-2 tolerant-regex builder implemented as a character-walk over quote_text (not a re.escape()-then-.replace() chain), avoiding self-referential replacement collisions where a confusable's replacement text contains other confusable characters.
- [02-03]: Fixed two real mechanical-verifier bugs (paragraph/entity-spanning quote search; multi-constellation-cataloged paid perk resolution) discovered running the D-10 corpus-wide baseline for the first time, per D-08 (fix the verifier, never the corpus) — no allowlist, no data edits.
- [02-03]: D-10 corpus-wide baseline achieved: pass=591, no_evidence=90, fail=0 across all 681 rolls in the 118 hand-curated chapters — Phase 2 complete, agent output (Phase 3) now has a real, proven bar to clear.

### Pending Todos

- Dre to manually review chapter 104's `rolls` array in the curator TUI (2 curated hit rolls vs. 1 predicted slot) before its alignment anchor can be safely re-stamped.

### Blockers/Concerns

- The `build_chapter_facts.py`/`data_release.py` DAG ordering gap (see Decisions above) will resurface on the next epub chapter-count change unless fixed properly; the workaround is documented in `deferred-items.md`.
- Ch 104's alignment anchor remains deliberately stale pending Dre's manual TUI review — `chapter_alignment.py check` will keep reporting 1 mismatch until resolved.
- `scripts/verify.py` does not exit 0: 5 pre-existing, unrelated Track B failures remain (chapter 79 TUI fixtures in `test_forge_curator.py`; chapter 55.1/56/57 roll-ordinal contract) — out of scope for this phase, unrelated to the epub refresh or ch 104.
- Latent risk: uncurated chapters 98, 99.1, 110, 110.3, 113, 115, 116.3 have no alignment anchor and may carry the same ch95.5-fix ripple invisibly — worth a `roll_validation.json` re-check when curated in Phases 3-4.
- `scripts/realign_chapters.py` writes JSON with `ensure_ascii=True`, causing whole-file unicode-escaping churn on hand-curated data every time it runs — one-line fix deferred (`ensure_ascii=False`).

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| pipeline-code | `build_chapter_facts.py` refreshes runtime manifest before `visualization_facts.json` is rebuilt in the same `--force` run; bootstrap fallback triggers on absence, not staleness | Open | 01-01 |
| curation-data | Ch 104's alignment anchor left stale; needs curator-TUI edit to `rolls` array (2 hits vs 1 predicted slot) before re-stamping | Open | 01-02 |
| curation-data | Uncurated chapters 98, 99.1, 110, 110.3, 113, 115, 116.3 have no alignment anchor; may carry the same ch95.5-fix ripple invisibly | Open | 01-02 |
| tooling-bug | `scripts/realign_chapters.py::_restamp()` writes with `ensure_ascii=True`, diverging from codebase convention | Open | 01-02 |
| test-debt | `test_forge_curator.py` (4 failures, chapter 79 TUI fixtures) and `test_roll_ordinal_contract.py` (1 failure, chapter 55.1/56/57) remain from the previously-documented Track B baseline; pre-existing, unrelated to epub refresh | Open | 01-02 |

## Session Continuity

Last session: 2026-08-01T18:21:39.605Z
Stopped at: Completed 02-03-PLAN.md
Resume file: None
