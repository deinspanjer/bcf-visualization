---
phase: 01-epub-refresh-exemplar-mining
plan: 01
subsystem: data-pipeline
tags: [epub, hydration, pipeline, chapter-publication-dates, section-classifications, multi-grab, curation-authority]

# Dependency graph
requires: []
provides:
  - "scripts/verify_epub_freshness.py — mechanical D-09 freshness check (source.json vs private-source metadata.json)"
  - "Fully force-regenerated data/derived/*.json tree at 198 chapters through 121.1"
  - "Ch 95.5 multi_grab hand-curated data gap resolved (mention_chapter_num: null -> \"95\")"
  - "Ch 121.1 rows added to section_classifications.json and chapter_publication_dates.json"
affects: [01-02, 01-03, 01-04]

# Tech tracking
tech-stack:
  added: []
  patterns: ["small-utility CLI script shape (argparse + pure function + main()), matching scripts/hydrate_source_epub.py"]

key-files:
  created:
    - scripts/verify_epub_freshness.py
    - .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md
  modified:
    - tests/test_source_epub_hydration.py
    - data/manual/section_classifications.json
    - data/manual/chapter_roll_overrides.json
    - data/manual/chapter_publication_dates.json
    - data/derived/*.json (13 files, gitignored, force-regenerated)

key-decisions:
  - "Ch 95.5 roll #0 mention_chapter_num set to \"95\" (Dre-approved, option-a): matches obtained_perks.json's live mechanical attribution for both perk names."
  - "section_classifications.json regenerated via its own build script (Dre-approved dynamic checkpoint): safe/idempotent, preserves curator toggles, adds only the 10 new ch 121.1 sections."
  - "Ch 121.1 publication date (2026-07-23 00:48 EST) hand-entered by Dre directly into chapter_publication_dates.json rather than re-running the destructive seed_chapter_publication_dates.py bootstrap script (stale AO3 snapshot + full-file overwrite risk)."
  - "build_visualization_facts.py run manually, once, ahead of its normal DAG position (orchestrator-approved) to break a chicken-and-egg manifest-freshness check in build_chapter_facts.py; the underlying DAG ordering gap is recorded in deferred-items.md, not fixed in this plan."

patterns-established:
  - "Pattern: manual-but-mechanically-regenerable files (section_classifications.json) are safe to regenerate via their own build_*.py script even outside curation-authority scope, because the script itself preserves curator toggles/overrides by design — verify via before/after diff (added keys only, zero removed, no unexplained value changes) before committing."
  - "Pattern: any pipeline failure outside the plan's one documented, anticipated blocker is treated as new information requiring a checkpoint — never silently routed around, even when the fix looks obviously safe."

requirements-completed: [EPUB-01]

coverage:
  - id: D1
    description: "verify_epub_freshness.py mechanically proves the hydrated epub matches the private-source clone's release (EPUB-01, D-09)"
    requirement: "EPUB-01"
    verification:
      - kind: unit
        ref: "tests/test_source_epub_hydration.py#test_verify_epub_freshness_* (5 new tests)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python scripts/verify_epub_freshness.py (live repo data)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Ch 95.5 multi_grab hand-curated data gap resolved via an explicit, Dre-approved decision, never an autonomous edit"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/pipeline.py --target data --force (predict_rolls step no longer raises)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full derived-data pipeline force-regen completes; data/derived/chapters.json reports 198 chapters through 121.1"
    requirement: "EPUB-01"
    verification:
      - kind: integration
        ref: "test -f data/derived/chapters.json && python3 -c \"...chs[-1]['chapter_num']=='121.1'...\" (plan's own <verify> command)"
        status: pass
    human_judgment: false

duration: 50min
completed: 2026-07-26
status: complete
---

# Phase 1 Plan 1: Epub Refresh Verification & Full Pipeline Regen Summary

**Mechanical epub-freshness proof (`verify_epub_freshness.py`) plus a fully force-regenerated 198-chapter derived-data tree, unblocked through three Dre-gated data fixes and one orchestrator-approved DAG-ordering workaround.**

## Performance

- **Duration:** 50 min
- **Started:** 2026-07-26T22:05:18Z
- **Completed:** 2026-07-26T22:55:24Z
- **Tasks:** 3 (Task 2 was a checkpoint:decision)
- **Files modified:** 8 tracked files (2 created, 6 modified) + 13 gitignored derived-data files regenerated

## Accomplishments
- Built and tested `scripts/verify_epub_freshness.py`: mechanically confirms `data/raw/Brocktons_Celestial_Forge.source.json` matches `data/private-source/Brocktons_Celestial_Forge.metadata.json` on `chapter_count`, `last_chapter_num`, and `epub_sha256` — live repo confirmed fresh (198 chapters, last `121.1`) without any re-sync/re-hydrate, per D-10.
- Resolved the one known, pre-existing blocker to the pipeline regen: chapter 95.5's `multi_grab` override referenced a perk with no matching mechanical/mention-chapter attribution. Dre selected option-a (set `mention_chapter_num` to `"95"`, matching `obtained_perks.json`'s live mechanical attribution) at an explicit checkpoint:decision — applied as exactly one field edit.
- Discovered and resolved (via two further Dre/orchestrator-gated checkpoints) two additional staleness gaps the plan's research hadn't anticipated, both surfaced only because this was the first `--force` regen after real chapter-count growth (195→198):
  1. `data/manual/section_classifications.json` was missing all 10 sections of the new chapter 121.1 (blocking `predict_rolls.py`). Regenerated via its own `scripts/build_section_classifications.py` — verified 513→523 entries, zero removed, curator toggles preserved.
  2. `data/manual/chapter_publication_dates.json` was missing a row for chapter 121.1 (blocking `build_chapter_facts.py`). Appended one Dre-provided row (`published_at: "2026-07-23"`, `published_source: "manual"`) rather than re-running the destructive, full-overwrite `seed_chapter_publication_dates.py` bootstrap script against its own-stale AO3 snapshot.
- Discovered a fourth gap — a DAG-ordering chicken-and-egg bug in `build_chapter_facts.py`/`data_release.py` (manifest freshness validated against a not-yet-rebuilt `visualization_facts.json`) — worked around (orchestrator-approved, no code change) by running `scripts/build_visualization_facts.py` once ahead of its normal DAG position; recorded as an out-of-scope follow-up in `deferred-items.md`, not fixed in this plan.
- `.venv/bin/python scripts/pipeline.py --target data --force` now completes cleanly end-to-end (its `--target data` closure ends at `build_visualization_facts`); `data/derived/chapters.json` reports 198 chapters through `121.1`, exceeding the pre-refresh baseline of 195 chapters / `120.2`.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED):** Add failing tests for `verify_epub_freshness` - `6da33da` (test)
2. **Task 1 (GREEN):** Implement `verify_epub_freshness` mechanical D-09 check - `81a1566` (feat)
3. **Task 1 (addendum, Dre-approved dynamic checkpoint):** Regenerate `section_classifications.json` for ch 121.1 - `10665b4` (chore)
4. **Task 2/3 (Dre-approved, option-a):** Set ch 95.5 roll #0 `mention_chapter_num` to `"95"` - `1a2c9da` (fix)
5. **Task 3 (Dre-provided date):** Append ch 121.1 publication date - `8ab78b1` (fix)
6. **Task 3 (orchestrator-approved discovery record):** Document the DAG ordering gap - `e0bd369` (docs)

**Plan metadata:** committed separately below (docs: complete plan)

_Note: Task 1 used TDD (test → feat). Tasks 2 and 3 each required an additional Dre/orchestrator-gated data fix beyond the plan's anticipated single blocker._

## Files Created/Modified
- `scripts/verify_epub_freshness.py` - mechanical D-09 freshness check; pure `verify_epub_freshness(*, data_dir) -> dict` + `main()` CLI
- `tests/test_source_epub_hydration.py` - 5 new tests covering fresh/stale detection and `main()` exit-code behavior
- `data/manual/section_classifications.json` - regenerated to include chapter 121.1's 10 sections (513→523 entries)
- `data/manual/chapter_roll_overrides.json` - one field: ch 95.5 roll #0 `mention_chapter_num` set to `"95"`
- `data/manual/chapter_publication_dates.json` - one row appended for chapter `121.1` (197→198 entries)
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md` - new; records the DAG ordering gap follow-up
- `data/derived/*.json` (13 files, gitignored) - fully force-regenerated: `chapters.json`, `chapter_sections.json`, `predicted_rolls.json`, `roll_text_evidence.json`, `roll_outcomes.json`, `timeline.json`, `perk_directory.json`, `outstanding_perks_by_chapter.json`, `roll_facts.json`, `roll_validation.json`, `chapter_facts.json`, `constellation_lifecycle.json`, `constellation_wireframes.json`, `visualization_facts.json`, `data_package.json`

## Decisions Made
- **Ch 95.5 fix (Dre, checkpoint:decision, option-a):** `mention_chapter_num` → `"95"`, matching `obtained_perks.json`'s mechanical attribution for both perks and the accompanying "ch 95 override drops" warning.
- **Section-classifications regen (Dre, dynamic checkpoint):** approved running `build_section_classifications.py` after confirming it only adds the 10 new ch 121.1 sections and preserves all curator toggles.
- **Publication-date fix (Dre, dynamic checkpoint):** hand-append one row with Dre-provided date (2026-07-23 00:48 EST) rather than re-running the destructive full-overwrite seed script against a stale AO3 snapshot; used the schema's established `"manual"` enum value rather than inventing a new one.
- **DAG-ordering workaround (orchestrator, dynamic checkpoint):** running `build_visualization_facts.py` early is a data/process action, not a hand-curated-data edit or source-code change, so it did not require Dre's sign-off under curation authority — Dre was informed via the session log. The gap itself is recorded, not fixed, in this plan.

## Deviations from Plan

### Auto-fixed Issues

None — every unplanned action in this plan required a checkpoint (Rule 4 territory: new information / architectural-adjacent decisions), not an autonomous Rules 1-3 fix. See "Decisions Made" and the three checkpoint round-trips below.

### Checkpoint-Gated Discoveries (not anticipated by the plan's research)

**1. [Dynamic checkpoint] `section_classifications.json` stale for ch 121.1**
- **Found during:** Task 1 (first `pipeline.py --target data --force` attempt)
- **Issue:** `predict_rolls.py` failed with `missing section classification for 121.1@0` — a manual-but-mechanically-regenerable file (distinct from `chapter_roll_overrides.json`) hadn't caught up to the epub refresh's new chapter.
- **Fix:** Ran `scripts/build_section_classifications.py` (the script's own documented remediation); verified 513→523 entries added, zero removed, one pre-existing key touched only by legitimate span-merge logic.
- **Files modified:** `data/manual/section_classifications.json`
- **Verification:** Diff reviewed before commit; retry got past `predict_rolls.py`.
- **Committed in:** `10665b4`

**2. [Plan's own checkpoint:decision] Ch 95.5 multi_grab hand-curated data gap**
- **Found during:** Task 1 (confirmed the documented, anticipated blocker) / Task 2 (decision)
- **Issue:** `merge_paid_units` `ValueError` for ch 95.5 roll #0 (`mention_chapter_num: null` defaulted to mechanical ch 95.5, which mechanically has neither perk).
- **Fix:** Dre selected option-a: `mention_chapter_num` → `"95"`.
- **Files modified:** `data/manual/chapter_roll_overrides.json` (exactly one field)
- **Verification:** Retry got past `predict_rolls.py`/`derive_roll_outcomes.py` with only the expected informational warning.
- **Committed in:** `1a2c9da`

**3. [Dynamic checkpoint] `chapter_publication_dates.json` stale for ch 121.1**
- **Found during:** Task 3 (retry after fix #2)
- **Issue:** `build_chapter_facts.py` failed with `KeyError: '121.1'` — no publication-date row for the new chapter. The generating script (`seed_chapter_publication_dates.py`) is a destructive full-file-overwrite bootstrap, and its AO3 source snapshot was itself stale (no 121.1 entry).
- **Fix:** Dre provided the actual publish date (2026-07-23 00:48 EST); appended one schema-conformant row rather than re-running the destructive seeder.
- **Files modified:** `data/manual/chapter_publication_dates.json`
- **Verification:** Schema-validated (0 errors against `chapter_publication_dates.schema.json`); retry got past `build_chapter_facts.py`'s `pub_by_chap` lookup.
- **Committed in:** `8ab78b1`

**4. [Dynamic checkpoint, orchestrator-approved] DAG ordering gap in manifest freshness**
- **Found during:** Task 3 (retry after fix #3)
- **Issue:** `build_chapter_facts.py` unconditionally refreshes the runtime manifest against `visualization_facts.json`, which is only rebuilt by a later DAG step — first `--force` regen after genuine chapter-count growth (195→198) exposed this circularity as `ValueError: source EPUB chapter_count 198 does not match package story_chapter_ordinal 195`.
- **Fix:** Ran `scripts/build_visualization_facts.py` once, manually, ahead of its normal DAG position (inputs already fresh on disk) to break the circularity. Underlying code gap NOT fixed — recorded as a deferred follow-up.
- **Files modified:** none (data-derived files only, gitignored); `deferred-items.md` created to record the gap.
- **Verification:** `pipeline.py --target data --force` retry then completed with exit 0.
- **Committed in:** `e0bd369` (deferred-items.md); no code change made.

---

**Total deviations:** 0 auto-fixed; 4 checkpoint-gated discoveries (1 was the plan's own anticipated checkpoint; 3 were new, unanticipated staleness/ordering gaps surfaced by this being the first `--force` regen after real epub content growth).
**Impact on plan:** All four resolutions were necessary to reach a fully green pipeline regen; none touched anything beyond the plan's stated boundaries (no unapproved edits to `chapter_roll_overrides.json`, no new epub download path, no LLM calls). The fourth (DAG ordering) is explicitly deferred as a code-level follow-up, not resolved in this plan.

## Issues Encountered
None beyond the checkpoint-gated discoveries documented above, all resolved via explicit Dre/orchestrator approval before proceeding.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `data/derived/*.json` is now fully regenerated and consistent at 198 chapters through `121.1` — EPUB-01's mechanical proof is complete, and the hard gate for Phases 2-4 (exemplar mining, corpus characterization, retrieval) is cleared on the epub-freshness front.
- `data/manual/chapter_roll_overrides.json`, `section_classifications.json`, and `chapter_publication_dates.json` are all current for the refreshed chapter set.
- Follow-up recorded (not blocking): the `build_chapter_facts.py`/`data_release.py` DAG ordering gap (`deferred-items.md`) should be fixed properly before the next epub chapter-count change, to avoid needing the manual `build_visualization_facts.py` workaround again.
- Pre-existing, out-of-scope `roll_validation.json` `INFEASIBLE`/discrepancy warnings (ch56, 98, 99.1, 104, 110, 110.3, 113, 115, 116.3) and the informational ch 95/ch 55.1 `multi_grab`/`derive_roll_facts` warnings are unrelated to this plan's scope and were left untouched.

---
*Phase: 01-epub-refresh-exemplar-mining*
*Plan: 01*
*Completed: 2026-07-26*
