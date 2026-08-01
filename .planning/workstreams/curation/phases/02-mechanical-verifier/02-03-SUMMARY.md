---
phase: 02-mechanical-verifier
plan: 03
subsystem: data-pipeline
tags: [python, pytest, mechanical-verifier, corpus-baseline, perk-resolution, quote-verification]

# Dependency graph
requires:
  - phase: 02-mechanical-verifier
    provides: "02-01's verify_roll() pure API + build_obtained_perks_index() + POSITION_TOLERANCE_WORDS"
provides:
  - "scripts/mechanical_verifier.py's verify_chapter() — aggregates verify_roll() over a chapter's rolls into pass/fail/no_evidence counts"
  - "scripts/mechanical_verifier.py's CLI (parse_args/main) — writes data/derived/mechanical_verification_report.json, not DAG-wired, not manifest-registered (D-09)"
  - "tests/test_mechanical_verifier.py's D-10 corpus-wide baseline test — proves ROADMAP success criterion 1 for real, against the real epub"
  - "Two verifier bug fixes (paragraph/entity-spanning quotes; multi-constellation-cataloged paid perks) that make the 100% baseline actually reachable"
affects: [phase-3-confidence-framework]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Prose-search text: HTML tags blanked to same-length whitespace + entities decoded with length-preserving padding, composed before quote search — keeps every match offset valid against word_index while still finding quotes that straddle a </p><p> boundary or an &amp;-style entity"
    - "obtained_perks_index as a secondary/fallback authority for paid-perk resolution, consulted only when the primary perk_name_resolver.py ladder can't disambiguate a directory entry cataloged under a different or multiple constellations"

key-files:
  created: []
  modified:
    - scripts/mechanical_verifier.py
    - tests/test_mechanical_verifier.py

key-decisions:
  - "Corpus-baseline test function renamed from the plan's literal test_verifier_passes_full_hand_curated_corpus to test_corpus_baseline_verifier_passes_full_hand_curated_corpus — the plan's own <verify>/<acceptance_criteria> select the test via `-k corpus_baseline`, which was not a substring of the originally specified name (pytest would collect zero tests, exit 5)."
  - "Fixed two real verifier bugs discovered running the corpus-wide baseline for the first time (D-08: fix the verifier, never the corpus) rather than editing chapter_roll_overrides.json or adding an allowlist (T-02-09 forbids both)."
  - "_verify_perk's fallback to obtained_perks_index presence (any cost, not just cost==0) when the paid-perk ladder can't disambiguate is a resolution-source branch, not a second name-matching implementation — perk_name_resolver.py itself is untouched, matching D-06(c)'s 'unchanged ladder' instruction."

patterns-established:
  - "When a verifier check needs to search decoded/normalized prose but must still report positions valid against a char-offset word index, build the search text via composed length-preserving transforms (tag-to-space, entity-to-decoded-char-plus-padding) rather than a length-changing normalization."

requirements-completed: [CINF-03]

coverage:
  - id: D1
    description: "verify_chapter() aggregates verify_roll() over every roll in a chapter's override entry into a rolls list + pass/fail/no_evidence counts dict"
    requirement: CINF-03
    verification:
      - kind: integration
        ref: "tests/test_mechanical_verifier.py#test_corpus_baseline_verifier_passes_full_hand_curated_corpus (exercises verify_chapter() over all 118 chapters)"
        status: pass
    human_judgment: false
  - id: D2
    description: "CLI (parse_args/main) loads the real corpus and writes data/derived/mechanical_verification_report.json plus a pass/no_evidence/fail stdout summary; not DAG-wired, not manifest-registered, not schema-validated (D-09)"
    requirement: CINF-03
    verification:
      - kind: other
        ref: ".venv/bin/python scripts/mechanical_verifier.py (writes report, prints pass: 591 / no_evidence: 90 / fail: 0)"
        status: pass
      - kind: other
        ref: "grep -n 'write_validated_json|pipeline.py|refresh_current_runtime_manifest' scripts/mechanical_verifier.py returns nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-10 corpus-wide baseline: verify_chapter() looped over all 118 hand-curated chapters against the real epub reports zero fail outcomes, no allowlist, no exceptions"
    requirement: CINF-03
    verification:
      - kind: integration
        ref: "tests/test_mechanical_verifier.py#test_corpus_baseline_verifier_passes_full_hand_curated_corpus"
        status: pass
      - kind: other
        ref: "Real run against real epub: pass=591, no_evidence=90, fail=0 (681 rolls, 118 chapters)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Corpus-baseline test skips cleanly (not ERROR, not a false PASS) when the gitignored epub is absent locally"
    requirement: CINF-03
    verification:
      - kind: other
        ref: "epub temporarily moved aside; pytest -k corpus_baseline reported 1 skipped, 0 errors, 0 passed"
        status: pass
    human_judgment: false
  - id: D5
    description: "No new test regressions: full suite (622 tests) shows only the 5 known-accepted pre-existing failures; scripts/data_release.py check-derived reports 'local derived data ok'"
    verification:
      - kind: other
        ref: ".venv/bin/python -m pytest -q (617 passed, 5 failed — the documented known-accepted baseline, up from 616/5 in 02-01 by exactly the 1 new test this plan added)"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/data_release.py check-derived (prints the known ch95 multi_grab info line, then 'local derived data ok')"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-01
status: complete
---

# Phase 2 Plan 3: Mechanical Verifier CLI + D-10 Corpus-Wide Baseline Summary

**`verify_chapter()` aggregation + CLI report writer, plus two verifier bug fixes (paragraph/entity-spanning quote search, multi-constellation-cataloged perk resolution) that make the D-10 100% corpus baseline actually reach `fail: 0` — 591 pass / 90 no_evidence / 0 fail across 681 rolls in all 118 hand-curated chapters.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-08-01T17:45:00Z
- **Completed:** 2026-08-01T18:40:00Z
- **Tasks:** 3 (2 auto/tdd, 1 auto verification-only)
- **Files modified:** 2

## Accomplishments

- Added `verify_chapter()` to `scripts/mechanical_verifier.py`: loops `verify_roll()` over a chapter's `rolls`, returning `{chapter_num, rolls, counts}` with a `{pass, fail, no_evidence}` tally (D-05's three-outcome model, now chapter-scoped).
- Added the CLI (`parse_args`/`main`/`if __name__ == "__main__":`): loads the real epub, `chapter_roll_overrides.json`, `chapters.json`, `perk_directory.json`, `perk_aliases.json`, and `obtained_perks.json`; builds a lazy-caching `prose_loader`, the directory ladder, and the obtained-perks index; loops every chapter in the overrides file; writes `data/derived/mechanical_verification_report.json` (plain `json.dumps`, no schema registration per D-09) and prints a `pass:`/`no_evidence:`/`fail:` stdout summary. Confirmed unwired from the data-regen DAG and the runtime manifest (`grep` for `write_validated_json`/`pipeline.py`/`refresh_current_runtime_manifest` returns nothing).
- Landed the D-10 corpus-wide baseline test (`test_corpus_baseline_verifier_passes_full_hand_curated_corpus`), skip-guarded on a module-level `EPUB_AVAILABLE` constant, asserting `fail == 0` with zero allowlisted exceptions across all 118 hand-curated chapters.
- **Discovered and fixed two real verifier bugs** while running the CLI/test against the real corpus for the first time — the exact scenario ROADMAP's success criterion 1 anticipates ("a failure means the verifier is wrong, not the corpus"), resolved per D-08 without ever touching `chapter_roll_overrides.json` or adding an allowlist (T-02-09):
  1. **Quote search against raw HTML missed paragraph- and entity-spanning quotes.** 32 evidence quotes (31 spanning a `</p><p>` paragraph boundary with zero literal whitespace between the tags; 1 spanning an `&amp;` entity for a literal "&") could never match under either verification tier because the search ran against raw, un-decoded `chapter_html`. Added `_prose_search_text()`: HTML tags blanked to same-length whitespace (reusing `cp_word_index._strip_to_spaces`) composed with length-preserving entity decoding, keeping every match offset valid against `word_index`.
  2. **Paid-perk resolution failed when `perk_directory.json` catalogs a perk under a different (or multiple) constellation(s) than the roll that granted it.** 9 perk mentions across chapters 88 and 104 (a repeatable facility customization cataloged only under its base name's constellation; a perk cataloged under three constellations, none matching the roll's) failed `directory_index.lookup()`'s hard constellation filter. Added a fallback: when the (unchanged) ladder can't resolve a paid name, `obtained_perks_index` presence — already looked up for the cost determination, an independent authoritative source — confirms the name was genuinely acquired in that chapter.
- Real corpus-wide result after both fixes: **pass=591, no_evidence=90, fail=0** across all 681 rolls in the 118 hand-curated chapters.
- Confirmed no new test regressions: full suite (622 tests, up from 621 by the one new corpus-baseline test) shows only the 5 known-accepted pre-existing failures; `scripts/data_release.py check-derived` reports the same known ch95 informational line and "local derived data ok".

## Task Commits

Each task was committed atomically:

1. **Task 1: verify_chapter() aggregation and the CLI report writer** - `e4c7127` (feat) — includes the two Rule-1 bug fixes found running the CLI's own `<verify>` step against the real corpus
2. **Task 2: The D-10 corpus-wide baseline test** - `582c909` (test)
3. **Task 3: Full-suite regression check and phase-closing verification** - no code changes; results recorded here

**Plan metadata:** committed alongside this SUMMARY

## Files Created/Modified

- `scripts/mechanical_verifier.py` - `verify_chapter()`, CLI (`parse_args`/`main`), `_prose_search_text()`/`_decode_entities_preserving_length()` (quote-search fix), `_verify_perk()`'s obtained-perks fallback (perk-resolution fix)
- `tests/test_mechanical_verifier.py` - `EPUB_AVAILABLE` constant + `test_corpus_baseline_verifier_passes_full_hand_curated_corpus`

## Decisions Made

- Renamed the corpus-baseline test function to include `corpus_baseline` as a literal substring (`test_corpus_baseline_verifier_passes_full_hand_curated_corpus`) — the plan's own `<verify>`/`<acceptance_criteria>` select it via `pytest -k corpus_baseline`, which does not match the plan's literally-specified name.
- Fixed both discovered verifier bugs by consulting only data sources already established in the verifier's contract (the tokenizer's own tag-stripping helper; `obtained_perks_index`, already used for the free-perk path) rather than introducing any new matching technique, fuzzy path, or hardcoded exception — preserving D-06(c)'s "unchanged ladder, no second implementation" instruction and T-02-09's prohibition on allowlists.
- Verified the "skip cleanly without the epub" behavior by temporarily moving the local epub file aside rather than via `BCF_DATA_DIR` (the project's `tests/conftest.py` always copies from the true project `data/` into a per-process temp dir and overrides `BCF_DATA_DIR` itself, so an externally-set `BCF_DATA_DIR` has no effect under this test suite's existing convention — not a gap introduced by this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Quote verification searched raw, un-decoded chapter HTML, missing 32 genuine hand-curated quotes**
- **Found during:** Task 1's own `<verify>` step (running the new CLI against the real corpus for the first time surfaced 32 false `quote_not_found` failures before Task 2's test even existed)
- **Issue:** `_verify_quote` searched both Tier 1 and Tier 2 against raw `chapter_html`. A quote spanning a `</p><p>` paragraph boundary has literal `\n\n` in the curated text but zero literal whitespace in the raw HTML between the tags (Tier 2's `\s+` requires ≥1 whitespace char, so it can't match a zero-width gap). A quote spanning an `&amp;` entity ("Weapon & Item Storage Chest") has the decoded `&` in curated text but the raw HTML has the 5-character entity, which neither tier can match.
- **Fix:** Added `_decode_entities_preserving_length()` (decodes each entity, right-padding with spaces back to the entity's original span) and `_prose_search_text()` (composes entity decoding with `cp_word_index._strip_to_spaces`'s tag-blanking). Both transforms are length-preserving, so every match offset stays valid against `word_index`. `_verify_quote` now searches this text for both tiers instead of raw `chapter_html`.
- **Files modified:** scripts/mechanical_verifier.py
- **Verification:** Re-ran the CLI against the real corpus: all 31 paragraph-spanning + 1 entity-spanning quote now resolve; existing 833 already-passing Tier-1 quotes and 29 pre-existing unit/tracer tests unaffected (the transform only changes characters at tag/entity spans, identical elsewhere).
- **Committed in:** `e4c7127` (Task 1 commit)

**2. [Rule 1 - Bug] Paid-perk resolution failed when perk_directory.json catalogs a perk under a constellation different from (or in addition to) the granting roll's own constellation**
- **Found during:** Task 1's own `<verify>` step (same CLI run)
- **Issue:** `_verify_perk`'s call to `directory_index.lookup(name, jump=None, constellation=roll.get("constellation"))` applies the roll's constellation as a hard filter. 8 "Entrance Hall - `<variant>`" repeatable-facility-customization names (chapter 104, roll constellation "Toolkits") are cataloged in `perk_directory.json` only under "Entrance Hall"'s own constellation ("Personal Reality"), and "Synchronicity Event" (chapter 88, roll constellation "Knowledge") is cataloged under three different constellations (Capstone/Magic/Quality), none matching "Knowledge". Both are genuine paid acquisitions (`obtained_perks.json` cost 50/300 respectively) that the constellation-scoped ladder call could never resolve.
- **Fix:** When the ladder returns `None`, fall back to checking `obtained_perks_index` presence for the same `(chapter_num, name)` (or `mention_chapter_num` fallback) already computed for the cost determination — an independent, authoritative source distinct from the directory ladder. `perk_name_resolver.py` itself is untouched (D-06(c)'s "unchanged ladder" preserved); this is a resolution-source branch, not a second name-matching implementation.
- **Files modified:** scripts/mechanical_verifier.py
- **Verification:** Re-ran the CLI: all 9 previously-unresolved paid mentions (8 in ch104, 1 in ch88) now resolve; existing paid/free-path unit tests (including the spy asserting the directory is never consulted for a cost-0 free perk) unaffected.
- **Committed in:** `e4c7127` (Task 1 commit)

**3. [Rule 3 - Blocking] Plan's `<verify>`/`<acceptance_criteria>` select the corpus-baseline test via `-k corpus_baseline`, which doesn't match the plan's specified test function name**
- **Found during:** Task 2, first run of `.venv/bin/python -m pytest tests/test_mechanical_verifier.py -k corpus_baseline -x -q -s` (exit code 5, "no tests collected")
- **Issue:** The plan's `<action>` names the test `test_verifier_passes_full_hand_curated_corpus`; that string does not contain `corpus_baseline` as a substring, so pytest's `-k` filter selects nothing.
- **Fix:** Renamed the function to `test_corpus_baseline_verifier_passes_full_hand_curated_corpus`, preserving the original descriptive name as a suffix.
- **Files modified:** tests/test_mechanical_verifier.py
- **Verification:** `-k corpus_baseline` now selects and runs exactly the one test, passing.
- **Committed in:** `582c909` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 - bug, 1 Rule 3 - blocking)
**Impact on plan:** Both bug fixes were essential — without them the D-10 baseline (this plan's entire purpose) would not reach `fail: 0`, and per D-08 the corpus itself could never be edited to compensate. The test-name fix was necessary for the plan's own verify command to run at all. No scope creep: all three fixes stayed within `scripts/mechanical_verifier.py`/`tests/test_mechanical_verifier.py`, touched no other files, added no allowlist, added no fuzzy-matching path, and left `perk_name_resolver.py` and `cp_word_index.py` unmodified.

## Issues Encountered

None beyond the three deviations above, all resolved before task completion.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 (Mechanical Verifier) is complete. `verify_roll()`, `verify_chapter()`, `build_obtained_perks_index()`, and the CLI report are all real, tested, and proven against the full 118-chapter hand-curated corpus with a clean zero-fail baseline (591 pass, 90 no_evidence, 0 fail across 681 rolls).
- Phase 3's confidence framework has a real, empirically-proven bar to clear: `verify_chapter()`/`verify_roll()` are importable directly, and the CLI can be pointed at agent-curated chapters once they exist.
- No blockers. Full test suite shows only the 5 known-accepted pre-existing failures (4 in `test_forge_curator.py`, 1 in `test_roll_ordinal_contract.py`), unchanged and unrelated to this plan's work.

## Self-Check: PASSED

- `scripts/mechanical_verifier.py` exists and exports `verify_chapter`, `parse_args`, `main` — FOUND
- `tests/test_mechanical_verifier.py` exists and contains `test_corpus_baseline_verifier_passes_full_hand_curated_corpus` — FOUND
- Commit `e4c7127` — FOUND in `git log --oneline`
- Commit `582c909` — FOUND in `git log --oneline`
- All plan `<acceptance_criteria>` re-verified: CLI runs and writes report with correct stdout format (PASS); no `write_validated_json`/`pipeline.py`/`refresh_current_runtime_manifest` references (PASS); corpus-baseline test passes with real epub present, prints `{pass, no_evidence, fail}` counts with `fail == 0` (PASS); skip-guard verified via temporarily moving the local epub aside (PASS); full-suite `FAILED` lines are exactly the 5 known-accepted IDs (PASS); `scripts/data_release.py check-derived` reports "local derived data ok" (PASS)
- Plan-level `<verification>`: `.venv/bin/python -m pytest tests/test_mechanical_verifier.py -x -q -s` → all pass including corpus baseline; CLI runs standalone and writes a report — both PASS

---
*Phase: 02-mechanical-verifier*
*Completed: 2026-08-01*
