---
phase: 01-epub-refresh-exemplar-mining
plan: 02
subsystem: data-pipeline
tags: [epub, chapter-alignment, curation-authority, multi-grab, manifest, verify]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Fully force-regenerated data/derived/*.json tree at 198 chapters through 121.1"
provides:
  - "Dre-approved ch 121.1 curator section toggles (121.1@2, 121.1@9 counts_for_cp: true) applied and reflected in a clean pipeline regen"
  - "Manifest re-stamped: data/derived/data_package.json's perk_directory entry sha256 verified fresh"
  - "Chapter-alignment drift root-caused (via isolated, read-only experiment) to the ch 95.5 multi_grab fix, not the epub refresh; 4 of 5 drifted chapters (100, 109, 112, 114) re-stamped per Dre's explicit interactive review; ch 104 deliberately held pending TUI edit"
  - "scripts/verify.py executed to completion; results triaged and captured — 5 pre-existing, unrelated Track B failures remain (down from 24 previously documented across 7 files; 5 of those files now fully green)"
affects: [01-03, 01-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "BCF_DATA_DIR env-var redirect (already supported by scripts/data_paths.py) used to run pipeline scripts against an isolated scratch data directory for read-only root-cause investigation, without ever touching the real repo's tracked or gitignored files"
    - "Monkey-patching module-level path constants (EPUB/OUT_PATH/etc.) in-process on scripts that don't use data_paths.py, to redirect their writes to a scratch location for the same isolated-investigation purpose"

key-files:
  modified:
    - data/manual/section_classifications.json
    - data/manual/chapter_roll_overrides.json
    - .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md

key-decisions:
  - "Dre-approved (pre-task): ch 121.1@2 (Interlude Jack Slash) and 121.1@9 (Addendum Apeiron) set counts_for_cp: true per author Word-of-God (WOG-NOTES.md) — curator toggle convention, preserved across future section_classifications.json regeneration."
  - "Root cause of the 5-chapter alignment drift confirmed via controlled experiment (old 195-ch epub + ch95.5 fix reproduces byte-identical fingerprints to new 198-ch epub + same fix): the drift is caused entirely by the Dre-approved ch 95.5 mention_chapter_num fix (01-01), not by epub content growth. The problematic ch 95.5 override was itself added 2026-06-01, a week after these 5 fingerprints were stamped 2026-05-23 — pre-existing curation drift the epub refresh surfaced, not something it introduced."
  - "Dre reviewed each of the 5 drifted chapters' diff interactively via scripts/realign_chapters.py (never --yes) and accepted 100, 109, 112, 114; deliberately skipped 104 — its 2 curated hit rolls no longer fit the model's 1 predicted slot (paid_rolls_exceed_predicted_slots), which a plain re-stamp would silently paper over. Needs a curator-TUI edit first; Dre will review manually."
  - "Task 3's scripts/verify.py does not exit 0 (5 pre-existing test failures, verified unrelated to the ch 104 skip and to this plan's changes). Per explicit instruction, this is documented as a known-accepted gap, not silently marked satisfied and not forced green by editing hand-curated data."

requirements-completed: [EPUB-02]

coverage:
  - id: D1
    description: "Dre-approved 121.1 curator section toggles (WoG) applied to section_classifications.json and reflected in a clean derived-data regen (121.1 cp_earning_word_count now 23,917, nonzero, matching sections @2+@9)"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/pipeline.py --target data --force (exit 0) + python3 chapter_facts.json spot-check"
        status: pass
    human_judgment: false
  - id: D2
    description: "Manifest re-stamped with fresh sha256 for every data/derived/*.json file, including perk_directory.json"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/data_release.py manifest; sha256 cross-check against on-disk perk_directory.json"
        status: pass
    human_judgment: false
  - id: D3
    description: "Chapter-alignment drift (5 chapters) investigated, root-caused, and resolved per Dre's explicit per-chapter interactive decision (100/109/112/114 accepted, 104 held)"
    requirement: "EPUB-02"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/chapter_alignment.py check (post-restamp: only ch 104 remains, exit 1 — expected)"
        status: pass
    human_judgment: false
  - id: D4
    description: "scripts/verify.py executed to completion; git diff --check and check-derived pass; full pytest run captured and triaged (5 pre-existing failures, verified unrelated to this plan's changes, documented as known-accepted gap per explicit instruction not to force green)"
    requirement: "EPUB-02"
    verification:
      - kind: integration
        ref: ".venv/bin/python scripts/verify.py (exit 1: git diff --check pass, check-derived pass, pytest 5 failed / 573 passed)"
        status: fail
    human_judgment: true
    rationale: "The plan's must_have expects verify.py to exit 0. It does not, by design and explicit orchestrator instruction — the 5 remaining failures are pre-existing Track B staleness (chapter 79 TUI fixtures, chapter 55.1/56/57 roll-ordinal contract) verified unrelated to the ch 104 skip or to any change in this plan, but this is a judgment call about whether the plan's must_have is satisfiable under those terms, and should be visible to a human reviewer rather than silently marked pass."

duration: 165min
completed: 2026-07-26
status: complete
---

# Phase 1 Plan 2: Chapter-Alignment Drift Root-Caused and Resolved; Manifest Re-Stamped; verify.py Results Triaged Summary

**Manifest re-stamped and 121.1 CP toggles regenerated cleanly; a 5-chapter alignment-fingerprint drift was root-caused via an isolated, read-only experiment to the Dre-approved ch 95.5 multi_grab fix (not the epub refresh) and resolved per Dre's explicit per-chapter decision (4 accepted, 1 deliberately held); `scripts/verify.py` does not exit 0 — 5 pre-existing, unrelated Track B failures remain and are documented as a known-accepted gap, not forced green.**

## Performance

- **Duration:** 165 min
- **Started:** 2026-07-26T22:57:32Z (per workstream STATE.md session continuity)
- **Completed:** 2026-07-27
- **Tasks:** pre-task (Dre-approved) + 3 plan tasks (Task 2 was a checkpoint, resolved across two rounds of investigation and one interactive `realign_chapters.py` session)
- **Files modified:** 3 tracked files (2 manual data files, 1 phase-scoped deferred-items.md) + gitignored `data/derived/*.json` regenerated twice

## Accomplishments

- Applied Dre's pre-approved ch 121.1 curator section toggles (`121.1@2` Interlude Jack Slash, `121.1@9` Addendum Apeiron → `counts_for_cp: true`, both citing the author's Word-of-God in `WOG-NOTES.md`) to `section_classifications.json`, verified only those two entries changed (no POV labels, no other sections touched), and re-ran the full pipeline force-regen cleanly (exit 0) — `chapter_facts.json`'s 121.1 entry now reports a nonzero `cp_earning_word_count` of 23,917 reflecting sections @2+@9.
- Re-stamped the manifest (`scripts/data_release.py manifest`) and verified `perk_directory.json`'s sha256 entry matches the on-disk file exactly (the plan's own `<verify>` command had a stale key-format assumption — `'perk_directory.json'` vs the actual key `'perk_directory'` — documented as a deviation, verified manually instead).
- `scripts/chapter_alignment.py check` flagged 5 chapters (100, 104, 109, 112, 114) with stale fingerprints. Rather than accepting the plan's own hypothesis at face value, ran a fully read-only, isolated investigation: reconstructed the pre-refresh 195-chapter epub state from `data/private-source`'s own git history (`git show`, sha256-verified against that commit's metadata) and re-ran `predict_rolls.py` against it via a scratch `BCF_DATA_DIR`, both with and without the ch 95.5 fix. This conclusively proved the drift is caused entirely by the Dre-approved ch 95.5 `mention_chapter_num` fix (01-01) — NOT by epub content growth, and NOT by the 121.1 curator toggles (separately isolated and ruled out). Further git-blame archaeology showed the ch 95.5 override that trips this was added 2026-06-01, a week after these 5 fingerprints were stamped 2026-05-23 — this is pre-existing curation-data drift the epub refresh happened to be the first `--force` regen to surface, not something the refresh introduced.
- Presented Dre with a per-chapter table (drift class, root cause, curation exposure, safe-to-restamp assessment cross-referenced against `roll_validation.json`'s independent capacity checks) at a `checkpoint:human-verify`. Dre decided: accept 100, 109, 112, 114 (all capacity-clean); skip 104 (its 2 curated hit rolls exceed the model's 1 predicted slot — `paid_rolls_exceed_predicted_slots` — a plain re-stamp would silently paper over a real mismatch).
- Ran `scripts/realign_chapters.py` interactively (never `--yes`), entering exactly Dre's five decisions in the order the tool presented them; confirmed post-run that only ch 104 remains flagged by `chapter_alignment.py check`.
- Ran `scripts/verify.py` to completion: `git diff --check` and `check-derived` both pass; full pytest reports 5 failures (down from the previously-documented ~24 across 7 files — 5 of those files, including `test_chapter_alignment_fingerprints.py`, are now fully green). Verified the 5 remaining failures are NOT caused by the ch 104 skip (the alignment guard is a soft per-chapter annotation in `build_chapter_facts.py`, never a hard pytest gate) and traced them to pre-existing, unrelated Track B staleness (chapter 79 TUI fixtures; chapter 55.1/56/57 roll-ordinal contract) — documented as a known-accepted gap per explicit instruction, not forced green.

## Task Commits

Each task was committed atomically:

1. **Pre-task (Dre-approved):** Apply ch 121.1 curator section toggles per WoG - `6886704` (fix)
2. **Task 1 + investigation + Task 2 resolution:** Re-stamp alignment fingerprints for ch 100/109/112/114 (ch 104 deliberately skipped) - `cc84f84` (fix)
3. **Task 2/3 documentation:** Record ch 104 skip, latent-risk chapters, realign_chapters.py ensure_ascii bug, and Task 3 verify.py results - `01cc512` (docs)

**Plan metadata:** committed separately below (docs: complete plan)

_Note: `data/derived/data_package.json`'s manifest re-stamp (Task 1) produced no tracked-file commit — that file is gitignored._

## Files Created/Modified

- `data/manual/section_classifications.json` - `121.1@2`/`121.1@9` set `counts_for_cp: true` per Dre-approved WoG curator toggle
- `data/manual/chapter_roll_overrides.json` - `_fingerprint` re-stamped for ch 100, 109, 112, 114 (ch 104 left stale by choice)
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md` - appended: ch 104 skip + rationale, latent-risk uncurated-chapter note, `realign_chapters.py` `ensure_ascii` bug, Task 3 `verify.py` triage results

## Decisions Made

- **121.1 curator toggles (Dre-approved, pre-task):** `counts_for_cp: true` for `121.1@2` and `121.1@9`, reason strings prefixed `"curator toggle:"` so `build_section_classifications.py`'s `curator_section_toggle()` preserves them across future regeneration.
- **Alignment-drift root cause (established via controlled experiment, not assumption):** entirely the ch 95.5 fix's downstream ripple through regime-3 slot-boundary math; epub growth and the 121.1 toggles are both ruled out.
- **Per-chapter re-stamp decision (Dre, interactive `realign_chapters.py` session):** accept 100, 109, 112, 114; skip 104 pending a curator-TUI edit to its `rolls` array.
- **verify.py's 5 remaining failures are a known-accepted gap, not a regression:** confirmed via cross-reference against the mobile-ux workstream's previously-documented 24-failure baseline and via checking that `chapter_alignment`'s guard never hard-fails pytest. Not fixed here, per explicit instruction not to edit hand-curated data to force green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - plan-verify bug] Task 1's `<verify>` command used a stale manifest key-format assumption**
- **Found during:** Task 1
- **Issue:** The plan's automated verify checked for key `'perk_directory.json'` in the manifest's `files` dict; the actual on-disk schema keys files without the `.json` suffix (`'perk_directory'`), so the literal command as written returns exit 1 even on a correctly re-stamped manifest.
- **Fix:** Verified manually instead — compared the manifest's stored sha256 for the `perk_directory` key against a fresh sha256 of the on-disk `perk_directory.json` file; confirmed exact match.
- **Files modified:** None (verification-only; no plan file edited)
- **Verification:** `python3 -c "...hashlib.sha256(open('data/derived/perk_directory.json','rb').read())..."` matches manifest entry exactly
- **Committed in:** N/A (no file change; noted here and in the first checkpoint response)

### Checkpoint-Gated Discoveries

**2. [Plan's own conditional checkpoint, resolved via extended read-only investigation] 5-chapter alignment-fingerprint drift**
- **Found during:** Task 1 (`chapter_alignment.py check`)
- **Issue:** Chapters 100, 104, 109, 112, 114 showed stored-vs-current fingerprint mismatches after the force-regen.
- **Investigation:** Reconstructed the pre-refresh 195-chapter epub state read-only from `data/private-source` git history; ran `predict_rolls.py` against it via a scratch `BCF_DATA_DIR` with and without the ch 95.5 fix; confirmed the drift is caused entirely by that fix, not epub growth. Git-blame showed the fix's target override predates the epub refresh work by nearly 2 months of ordinary curation.
- **Resolution:** Dre's explicit per-chapter decision via `scripts/realign_chapters.py` (interactive, never `--yes`): accept 100/109/112/114, skip 104.
- **Files modified:** `data/manual/chapter_roll_overrides.json` (4 `_fingerprint` fields)
- **Verification:** Post-restamp `chapter_alignment.py check` reports only ch 104 remaining (expected).
- **Committed in:** `cc84f84`

**3. [Discovered during investigation, not fixed] `scripts/realign_chapters.py` writes JSON with `ensure_ascii=True`**
- **Found during:** Task 2's interactive `realign_chapters.py` run
- **Issue:** The tool's `_restamp()` rewrites the entire overrides file via `json.dumps(doc, indent=2)`, which defaults to `ensure_ascii=True`, escaping ~14 unrelated lines of literal unicode (en-dash, ellipsis) in hand-curated evidence quotes/perk names — diverging from the codebase's `ensure_ascii=False` convention.
- **Fix:** Manually reverted the unrelated escaping before committing (diff reduced to exactly the 4 intended fingerprint lines); did not touch `realign_chapters.py`'s code (out of this data-curation plan's scope).
- **Files modified:** None (code fix deferred; recorded in `deferred-items.md`)
- **Verification:** `git diff --stat` showed exactly `4 insertions(+), 4 deletions(-)` before commit
- **Committed in:** Not applicable (deferred; documented in `01cc512`)

---

**Total deviations:** 1 auto-fixed (plan-verify command bug), 2 checkpoint-gated discoveries (1 fully resolved this plan via Dre's decision, 1 recorded as a deferred script bug).
**Impact on plan:** No scope creep — every discovery was either resolved via Dre's explicit decision or documented as an out-of-scope follow-up, per this plan's threat model and prohibitions (no hand-patching of derived sha256/fingerprint values, no `--yes` on `realign_chapters.py`, no silencing of failing tests).

## Issues Encountered

- **`scripts/verify.py` does not exit 0.** `git diff --check` and `check-derived` pass; the full pytest run reports 5 failures (`test_forge_curator.py` x4, `test_roll_ordinal_contract.py` x1). These are verified, pre-existing, unrelated Track B staleness (chapter 79 TUI fixtures; chapter 55.1/56/57 roll-ordinal contract), NOT caused by the ch 104 alignment skip (the guard is a soft chapter-scoped annotation, never a hard pytest assertion) and NOT caused by anything else in this plan's scope. Per explicit instruction, this is a **known-accepted gap**, documented verbatim in `deferred-items.md`, and is **not** silently marked as satisfying the plan's must_have "verify.py exits 0 with zero failures." Of the previously-documented ~24 failures across 7 files (mobile-ux workstream's Phase 1 `deferred-items.md`), 5 files are now fully green; only `test_forge_curator.py` (unchanged count, 4) and `test_roll_ordinal_contract.py` (down from 9 to 1) remain, both pre-dating and unrelated to this phase's epub-refresh work.
- **Ch 104's alignment anchor remains deliberately stale**, pending Dre's manual curator-TUI review of its `rolls` array (2 curated hits vs. 1 predicted slot). Tracked in `deferred-items.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The epub-refresh hard gate (EPUB-01, EPUB-02) is now as complete as it can be without further hand-curation: the pipeline runs green on `git diff --check` and `check-derived`, and the previously-documented Track B test debt is reduced from ~24 failures to 5, all pre-existing and unrelated to this phase's work.
- **Not fully green**: `scripts/verify.py` exits 1. Whoever picks up Phase 2/3 work should be aware that a full "zero failures" pytest run is not currently achievable without (a) Dre's manual ch 104 TUI edit, and (b) separate, unrelated Track B debt in chapter 79 and chapter 55.1/56/57 data — none of which block Phase 1's remaining plans (01-03, 01-04 build the exemplar index from the *already-curated* 118-chapter corpus and don't depend on ch 100-114 or ch 79/55.1's specific data).
- Latent risk flagged for Phases 3-4: uncurated chapters 98, 99.1, 110, 110.3, 113, 115, 116.3 have no alignment anchor and may carry the same ch95.5-fix ripple invisibly — worth a `roll_validation.json` re-check when those chapters are curated.
- Follow-ups recorded in `deferred-items.md`, not blocking: the 01-01 DAG-ordering gap (`build_chapter_facts.py`/`data_release.py`), ch 104's pending TUI edit, and `realign_chapters.py`'s `ensure_ascii=True` bug.

## Self-Check: PASSED

- `[ -f data/manual/section_classifications.json ]` → FOUND
- `[ -f data/manual/chapter_roll_overrides.json ]` → FOUND
- `[ -f .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md ]` → FOUND
- `git log --oneline` contains `6886704`, `cc84f84`, `01cc512` → confirmed present
- Re-ran `scripts/chapter_alignment.py check` → confirms exactly 1 remaining mismatch (ch 104), matching this SUMMARY's claims
- Re-ran plan-level `<verification>` commands: `data_release.py manifest` (pass), `chapter_alignment.py check` (result recorded: ch 104 only), `scripts/verify.py` (exit 1, results captured and triaged per above — NOT silently marked as pass)

---
*Phase: 01-epub-refresh-exemplar-mining*
*Plan: 02*
*Completed: 2026-07-26*
