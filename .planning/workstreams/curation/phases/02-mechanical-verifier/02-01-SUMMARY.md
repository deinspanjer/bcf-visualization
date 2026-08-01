---
phase: 02-mechanical-verifier
plan: 01
subsystem: data-pipeline
tags: [python, pytest, tokenizer, quote-verification, perk-resolution, mechanical-verifier]

# Dependency graph
requires:
  - phase: 01-epub-refresh-exemplar-mining
    provides: hand-curated 118-chapter corpus (data/manual/chapter_roll_overrides.json), perk_name_resolver.py ladder, data/derived/chapters.json + obtained_perks.json + perk_directory.json
provides:
  - "scripts/cp_word_index.py — shared CP-earning-word tokenizer (D-01/D-02), sourced through data_paths.RAW"
  - "scripts/mechanical_verifier.py — verify_roll() pure API covering all four D-06 checks (quote text/position, word_position range, paid/free-aware perk resolution, null-tolerant enum sanity)"
  - "scripts/find_text_backed_rolls.py rewritten to consume the extracted tokenizer, zero output drift"
  - "23 synthetic-fixture unit tests + 4 tokenizer regression tests + 2 real-corpus tracer tests, all green"
affects: [02-03-mechanical-verifier-cli-and-corpus-baseline, phase-3-confidence-framework]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-module + thin-CLI split (query_exemplars.py convention) — verify_roll() has no argparse/file I/O"
    - "Structured {code, severity, message} issue triple reused verbatim from derive_roll_facts.py::_manual_override_issues"
    - "Tier-2 tolerant regex built via character-walk over quote_text (not a .replace() chain on the pre-escaped string), avoiding self-referential replacement collisions when a confusable's replacement text itself contains other confusable characters"

key-files:
  created:
    - scripts/cp_word_index.py
    - scripts/mechanical_verifier.py
    - tests/test_cp_word_index.py
    - tests/test_mechanical_verifier.py
    - .planning/workstreams/curation/phases/02-mechanical-verifier/deferred-items.md
  modified:
    - scripts/find_text_backed_rolls.py

key-decisions:
  - "Tier-2 confusable/whitespace tolerant regex is built by walking quote_text character-by-character and emitting escaped-literal / \\s+ / confusable-class tokens directly — NOT by re.escape()-then-.replace() chaining, because a naive .replace() chain re-scans its own inserted replacement text (e.g. replacing bare '–' with '[-–—]' would then match the '–' it just inserted on a later pass), silently corrupting the pattern."
  - "verify_roll()'s quote-verification helper checks quote_text_empty and position_missing before attempting any search (both return immediately with a distinct reason code) — matches the plan's defensive-case spec even though 0/864 real quotes currently hit either path."
  - "No CLI added in this plan — verify_roll()/build_obtained_perks_index() are the whole deliverable per D-09; the thin CLI convenience wrapper is explicitly out of this plan's scope."

patterns-established:
  - "Real-corpus tracer/integration tests live alongside synthetic unit tests in the same test file, clearly banner-separated, with a comment noting which tests touch the real epub"

requirements-completed: [CINF-03]

coverage:
  - id: D1
    description: "CP-earning-word tokenizer extracted into scripts/cp_word_index.py (D-01/D-02); find_text_backed_rolls.py rewritten to import it with zero shim/re-export and zero output drift"
    requirement: CINF-03
    verification:
      - kind: unit
        ref: "tests/test_cp_word_index.py#test_two_section_chapter_returns_only_counted_section_words"
        status: pass
      - kind: unit
        ref: "tests/test_cp_word_index.py#test_preamble_section_before_body_tag_is_clamped_to_empty"
        status: pass
      - kind: other
        ref: "diff -q pre/post regenerated data/derived/roll_text_evidence.json (byte-identical)"
        status: pass
    human_judgment: false
  - id: D2
    description: "verify_roll() pure API implements all four D-06 checks: two-tier quote verification (byte-exact then whitespace/confusable-tolerant, never fuzzy), per-quote position tolerance via nearest-occurrence disambiguation, paid/free-aware perk resolution (D-06(c) CORRECTION), and null-tolerant outcome/display_position_policy enum sanity"
    requirement: CINF-03
    verification:
      - kind: unit
        ref: "tests/test_mechanical_verifier.py (23 synthetic-fixture tests: Tier-1/Tier-2 match, reject-on-word-edit, duplicate-quote disambiguation, cross-chapter resolution, different-chapter-always-fails, null-tolerant enums, word_position range, paid/free perk branches, no_evidence/fail aggregation)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Real-corpus tracer proof: chapter 67 roll 1 (five-perk Personal Reality multi-grab, 4 paid + 1 free) and chapter 92 roll 1 (seven-perk Transformers bundle, 1 paid + 6 free ride-alongs that all miss the directory) both verify as status=pass, issues=[] against the real epub"
    requirement: CINF-03
    verification:
      - kind: integration
        ref: "tests/test_mechanical_verifier.py#test_tracer_ch67_roll1_personal_reality_multigrab_passes_end_to_end"
        status: pass
      - kind: integration
        ref: "tests/test_mechanical_verifier.py#test_ch92_roll1_transformers_bundle_free_ride_alongs_resolve"
        status: pass
    human_judgment: false
  - id: D4
    description: "No fuzzy/similarity/edit-distance matching path exists anywhere in the touched files — a structural property, not merely an unused option"
    requirement: CINF-03
    verification:
      - kind: other
        ref: "grep -v '^[[:space:]]*#' scripts/cp_word_index.py scripts/mechanical_verifier.py scripts/find_text_backed_rolls.py | grep -ci 'rapidfuzz\\|difflib' == 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "No new test regressions: full suite (616 passed) shows only the 5 known-accepted pre-existing failures"
    verification:
      - kind: other
        ref: ".venv/bin/python -m pytest -q (616 passed, 5 failed — the documented known-accepted baseline)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-01
status: complete
---

# Phase 2 Plan 1: Mechanical Verifier Core (Tracer + Unit Tests) Summary

**`verify_roll()` pure API implementing byte-exact/confusable-tolerant quote verification, D-06(c) paid/free-aware perk resolution, and null-tolerant enum sanity — proven end-to-end against two real hand-curated rolls before any corpus-wide loop exists.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-01T17:15:09Z
- **Completed:** 2026-08-01T17:39:28Z
- **Tasks:** 2 (1 tracer, 1 auto/tdd)
- **Files modified:** 6 (5 created, 1 modified)

## Accomplishments

- Extracted the CP-earning-word tokenizer (`_chapter_word_index`, `_split_sections`, `_strip_to_spaces`, `load_chapter_html`) into `scripts/cp_word_index.py`, routed through `data_paths.RAW` instead of a hardcoded path (D-01/D-02); `find_text_backed_rolls.py` rewritten to import it, with a `diff -q` before/after regeneration proving zero behavioral drift
- Built `scripts/mechanical_verifier.py`'s `verify_roll()` — a pure, importable per-roll check covering all four D-06 dimensions: two-tier quote verification (byte-exact substring, then a single whitespace/confusable-tolerant regex — never fuzzy), per-quote position tolerance (nearest-occurrence disambiguation within `POSITION_TOLERANCE_WORDS = 50`), paid/free-aware perk resolution (D-06(c) CORRECTION: cost>0 or absent-from-`obtained_perks.json` names resolve through the existing `perk_name_resolver.py` ladder unchanged; cost==0 names resolve by presence in `obtained_perks.json` alone, directory never consulted), and null-tolerant `outcome`/`display_position_policy` enum sanity
- Proved the whole path end-to-end against two real hand-curated rolls before any expansion: chapter 67 roll 1 (four paid perks + one cost-0 free ride-along) and chapter 92 roll 1 (the D-06(c) CORRECTION's canonical seven-perk Transformers bundle, where all six free ride-alongs miss the directory ladder entirely) — both `status: pass`, `issues: []`
- Added 27 automated tests total (4 tokenizer regression + 23 synthetic-fixture unit tests covering the Tier-2 tolerant-match edge cases, duplicate-quote nearest-occurrence disambiguation, cross-chapter quote resolution, the "different chapter always fails" invariant, and every perk-resolution branch) — all green, none touching the real epub except the two Task 1 tracer tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract the tokenizer and wire verify_roll() end-to-end against one real hand-curated roll** - `4377dd9` (feat)
2. **Task 2: Unit-test the four D-06 checks against synthetic fixtures** - `d3d5c97` (test)

**Plan metadata:** committed alongside this SUMMARY

## Files Created/Modified

- `scripts/cp_word_index.py` - shared CP-earning-word tokenizer module (D-01/D-02 extraction)
- `scripts/mechanical_verifier.py` - `verify_roll()` pure API + `build_obtained_perks_index()` + `POSITION_TOLERANCE_WORDS`
- `scripts/find_text_backed_rolls.py` - rewritten import block, own `_chapter_word_index` deleted (no shim)
- `tests/test_cp_word_index.py` - tokenizer regression tests
- `tests/test_mechanical_verifier.py` - 2 real-corpus tracer tests + 23 synthetic unit tests
- `.planning/workstreams/curation/phases/02-mechanical-verifier/deferred-items.md` - records the now-three-way `_split_sections`/`_strip_to_spaces` duplication as future work

## Decisions Made

- Tier-2's tolerant regex is built via a character-walk over the raw quote text rather than a `re.escape()`-then-`.replace()` chain, because the naive chain approach re-scans its own inserted replacement text and silently corrupts the pattern (a replacement like `[-–—]` contains the very characters a later `.replace()` call would match again). This is a correctness fix applied during implementation, not a plan deviation — the plan's `<action>` left the exact regex-construction technique to Claude's discretion.
- `quote_text_empty`/`position_missing` are checked before any search attempt, matching the plan's defensive-case spec exactly (0/864 real quotes hit either path today, but the code path is real and tested).

## Deviations from Plan

None - plan executed exactly as written. The Tier-2 regex-construction technique (character-walk vs. `.replace()` chain) was left to Claude's discretion by the plan's own `<action>` text ("Claude's Discretion" section of 02-CONTEXT.md explicitly lists "Whether the confusable-folding table is hand-written or unicodedata-based") and is not a deviation from any specified behavior.

## Issues Encountered

None. Both real-data tracer tests passed on first run against real corpus data; all 23 synthetic unit tests passed after one iteration to correct the Tier-2 pattern-building approach described above (caught before any commit, not a post-hoc fix).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `verify_roll()` and `build_obtained_perks_index()` are ready for Plan 02-03 to build the CLI + D-10 corpus-wide baseline test (100% pass/no_evidence over all 118 hand-curated chapters) and for Phase 3's confidence gate to import directly.
- No blockers. Full test suite shows only the 5 known-accepted pre-existing failures (4 in `test_forge_curator.py`, 1 in `test_roll_ordinal_contract.py`) — unchanged, unrelated to this plan's work.

## Self-Check: PASSED

- `scripts/cp_word_index.py` exists — FOUND
- `scripts/mechanical_verifier.py` exists — FOUND
- `tests/test_cp_word_index.py` exists — FOUND
- `tests/test_mechanical_verifier.py` exists — FOUND
- `.planning/workstreams/curation/phases/02-mechanical-verifier/deferred-items.md` exists — FOUND
- Commit `4377dd9` — FOUND in `git log --oneline`
- Commit `d3d5c97` — FOUND in `git log --oneline`
- All plan `<acceptance_criteria>` re-verified: tokenizer exports, zero-drift regeneration, tracer/ch92 tests pass, zero fuzzy-matching grep hits — all PASS
- Plan-level `<verification>`: `.venv/bin/python -m pytest tests/test_cp_word_index.py tests/test_mechanical_verifier.py -x -q` → 29 passed; full suite → 616 passed, 5 known-accepted failures, no new regressions

---
*Phase: 02-mechanical-verifier*
*Completed: 2026-08-01*
