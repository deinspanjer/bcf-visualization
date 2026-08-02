---
phase: 03-provenance-schema-deterministic-candidate-assembly
plan: 02
subsystem: data-pipeline
tags: [python, jsonschema, curation, deterministic, roll-binding, pytest]

# Dependency graph
requires:
  - phase: 02-mechanical-verifier
    provides: "cp_word_index.py's tokenizer/prose loader and mechanical_verifier.py's offset-preserving prose-search text, reused verbatim for the free-perk forward search"
provides:
  - "data/derived/_schemas/candidate_rolls.schema.json — the candidate-roll shape (chapter_roll_overrides.json's roll-object fields verbatim + a _derivation provenance sub-object), additionalProperties: false at both levels"
  - "scripts/build_candidate_rolls.py:assemble_candidate / assemble_all_candidates — the deterministic, zero-LLM Stage 1 binder: chapter-local POSITIONAL cursor advance through multi_grab.merge_paid_units(overrides=None)'s default bundle units, corrected off the rejected anchor-gated rule that only ever bound 36/718 rolls"
  - "data/derived/candidate_rolls.json (gitignored, regenerable) — 718 candidates: 318 hit (6 anchor-confirmed, 312 positional-only and marked evidence_for:outcome), 24 miss, 376 fully unfilled"
affects: [phase-3-plan-3-accuracy-measurement, phase-4-inference-refinement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chapter-local positional cursor advance as the PRIMARY binding signal (not local per-roll anchor presence) — a roll's own matching_anchor_kinds only classifies outcome (miss) or marks confidence (evidence_for:outcome), it never gates whether a unit-consumption attempt happens at all."
    - "Two-tier liberal forward search (Stage 1 discovery, D-13) mirroring the mechanical verifier's own offset-preserving prose-search text (mechanical_verifier._prose_search_text, reused not reimplemented) so every emitted quote is, by construction, an exact substring that would also pass the verifier's exact-or-reject Tier 1 check."
    - "assemble_candidate's chapter_html/word_index parameters are optional (default None) — the same pure function serves Task 1's no-prose synthetic fixture and Task 2/3's prose-search-enabled callers without a second code path."

key-files:
  created:
    - data/derived/_schemas/candidate_rolls.schema.json
    - scripts/build_candidate_rolls.py
    - tests/test_build_candidate_rolls.py
  modified: []

key-decisions:
  - "The free-perk forward search's Tier 2 fallback drops the perk name's own spaces/hyphens and re-joins each remaining character with an OPTIONAL [\\s-]* connector (not a token-level join). A token-level join only tolerates a variant that ALREADY has a space/hyphen at the same position as the perk name (e.g. multi-word names); it cannot match the plan's own cited example, obtained-perks name \"Altmode\" (no internal separator at all) against prose \"alt-mode\" (a hyphen inserted mid-word). The per-character connector generalizes both cases and is still ReDoS-safe (fixed literal chars + one bounded class quantifier per gap, mirroring mechanical_verifier._build_tier2_pattern's shape) — discovered empirically while making the RED test's hyphen-variant assertion pass."
  - "evidence_quotes are populated ONLY from the free-perk forward search, never from the roll's own connection narration (the roll_text_evidence.json prose_window). The plan's Task 2 action text scopes the forward search explicitly to 'each free perk name in a bound bundle' and the frontmatter's must-haves attribute every evidence_quotes[].text to 'Stage 1's free-perk name search' — adding a second quote source (a paid-perk connection sentence) was out of scope and would have been an uncalled-for second search implementation."
  - "assemble_candidate takes optional chapter_html/word_index (default None) rather than being split into a 'binder' and a separate 'evidence attacher' function. When omitted, no evidence_for:<perk> claim is added for that hit's free perks either — a search that never ran makes no honesty claim about its result, distinct from a search that ran and found nothing."

requirements-completed: [ACUR-01]

coverage:
  - id: D1
    description: "candidate_rolls.schema.json declares the candidate shape (chapter_roll_overrides.json's roll-object fields verbatim + _derivation provenance sub-object), additionalProperties: false at both the document and candidate level"
    requirement: ACUR-01
    verification:
      - kind: other
        ref: "jsonschema.Draft202012Validator.check_schema() on the file -> valid; top and $defs.candidate additionalProperties both False"
        status: pass
      - kind: integration
        ref: "write_validated_json(OUT, payload, 'candidate_rolls') succeeds over the full 718-candidate corpus (main() run) with zero schema violations"
        status: pass
    human_judgment: false
  - id: D2
    description: "assemble_candidate implements the corrected chapter-local POSITIONAL cursor-advance rule (miss anchor skips consumption; else consume-if-available regardless of local anchor presence, marking evidence_for:outcome when unconfirmed; else fully unfilled) as a pure, no-file-I/O function"
    requirement: ACUR-01
    verification:
      - kind: unit
        ref: "Task 1 <verify> inline script: miss-anchored row skips consumption + binds constellation; anchor-less row still binds positionally, marked evidence_for:outcome"
        status: pass
      - kind: unit
        ref: "tests/test_build_candidate_rolls.py#test_positional_binding_binds_hit_without_local_anchor_evidence"
        status: pass
      - kind: unit
        ref: "tests/test_build_candidate_rolls.py#test_miss_anchor_skips_unit_consumption_leaves_it_for_next_roll"
        status: pass
      - kind: unit
        ref: "tests/test_build_candidate_rolls.py#test_units_exhausted_yields_unfilled_not_guessed"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full-corpus assembly (assemble_all_candidates + main()) emits exactly 718 candidates — one per roll_text_evidence.json row, chapter-by-chapter with the unit cursor reset per chapter — matching the plan's live-data regression totals exactly: 318 hit (6 anchor-confirmed, 312 positional-only), 24 miss, 376 unfilled; ch 92's own worked example now binds Cybertronian Forge/Size to roll 1 instead of binding nothing"
    requirement: ACUR-01
    verification:
      - kind: integration
        ref: "Task 2 <verify> inline script against data/derived/candidate_rolls.json: len==718, n_hit==318, n_miss==24, n_unfilled==376, n_hit_confirmed==6, ch92 sanity check"
        status: pass
      - kind: integration
        ref: "re-run diff: candidate_rolls_run1.json vs. regenerated candidate_rolls.json, sort_keys JSON comparison -> clean diff (byte-identical)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every bound hit candidate gets a liberal (Tier 1 exact / Tier 2 hyphen-space-tolerant) forward search for each free perk's name; every emitted evidence_quotes[].text is a literal substring of its chapter's real epub prose, never composed"
    requirement: ACUR-01
    verification:
      - kind: unit
        ref: "tests/test_build_candidate_rolls.py#test_evidence_quote_text_is_always_a_literal_prose_substring"
        status: pass
      - kind: unit
        ref: "tests/test_build_candidate_rolls.py#test_partial_bundle_marks_unmatched_free_perk_unfilled"
        status: pass
      - kind: other
        ref: "ad hoc script: all 155 evidence_quotes emitted across the live 718-candidate run verified as literal substrings of mechanical_verifier._prose_search_text(chapter_html) for their own chapter -> 0 mismatches"
        status: pass
    human_judgment: false
  - id: D5
    description: "build_candidate_rolls.py never reads or writes data/manual/chapter_roll_overrides.json (D-04) — writes exclusively to data/derived/candidate_rolls.json"
    requirement: ACUR-01
    verification:
      - kind: other
        ref: "grep -n 'chapter_roll_overrides|persistence' scripts/build_candidate_rolls.py -> only docstring prose mentions, zero code references; merge_paid_units called with overrides=None (never load_overrides)"
        status: pass
    human_judgment: false
  - id: D6
    description: "No new test failures beyond the 5 known-accepted pre-existing baseline; mechanical_verifier.py unchanged at pass=593/no_evidence=88/fail=0; data_release.py check-derived still passes"
    requirement: ACUR-01
    verification:
      - kind: integration
        ref: "PYTHONPATH=scripts .venv/bin/python -m pytest -q -> exactly the same 5 baseline failures (4 test_forge_curator.py, 1 test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction), no new ones"
        status: pass
      - kind: other
        ref: "PYTHONPATH=scripts .venv/bin/python scripts/mechanical_verifier.py -> pass: 593, no_evidence: 88, fail: 0"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/data_release.py check-derived -> 'local derived data ok'"
        status: pass
    human_judgment: false

# Metrics
duration: 19min
completed: 2026-08-02
status: complete
---

# Phase 3 Plan 2: Deterministic Candidate Assembly (Stage 1) Summary

**Zero-LLM candidate roll assembler binds all 718 predicted rolls via chapter-local positional cursor advance through `merge_paid_units`, not gated on local anchor evidence — 318 hit (only 6 anchor-confirmed), 24 miss, 376 honestly unfilled, byte-identical on re-run.**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-08-02T18:24:17Z
- **Completed:** 2026-08-02T18:43:26Z
- **Tasks:** 3
- **Files modified:** 3 (all created; no existing files touched)

## Accomplishments

- Added `data/derived/_schemas/candidate_rolls.schema.json`: reuses `chapter_roll_overrides.json`'s roll-object field set verbatim (D-05) plus a `_derivation` provenance sub-object (`evidence_kind`, `matched_anchor_kinds`, `bundle_source`, `unfilled_fields`), `additionalProperties: false` at both the document and candidate level.
- Added `scripts/build_candidate_rolls.py:assemble_candidate` — the pure, no-file-I/O core binder implementing the plan's **corrected** binding rule: chapter-local POSITIONAL cursor advance through `multi_grab.merge_paid_units(overrides=None)`'s default bundle units is the primary signal. A `"miss"` anchor is the only thing that skips unit consumption; `"acquisition"` presence/absence only controls whether `"evidence_for:outcome"` is added to `_derivation.unfilled_fields`, never whether binding is attempted.
- Wired `assemble_all_candidates`/`main()` to walk the full corpus chapter-by-chapter (numeric order, `slot_index` ascending within a chapter), resetting the unit cursor at every chapter boundary. Live run: **718/718 candidates** — 318 hit (6 anchor-confirmed via a local `"acquisition"` tag, 312 positional-only), 24 miss, 376 fully unfilled — matching the plan's live-data regression totals exactly. Chapter 92 (CURATION-CONVENTIONS' own worked example, both rows anchor-empty) now binds its Cybertronian Forge/Size unit to roll 1 instead of binding nothing under the old anchor-gated rule.
- Added the free-perk forward search (`_find_free_perk_evidence`): Tier 1 exact case-insensitive substring, Tier 2 a per-character hyphen/space-tolerant variant match (generalizes the plan's own cited example, `"Altmode"` vs. prose `"alt-mode"`) — searched against `mechanical_verifier._prose_search_text`'s offset-preserving, tag-stripped/entity-decoded prose (reused, not reimplemented), so every emitted quote is, by construction, an exact substring that would also pass the verifier's Tier 1 check. All 155 quotes emitted across the real 718-candidate run were spot-checked programmatically as literal substrings of their chapter's real prose — 0 mismatches.
- Re-running `build_candidate_rolls.py` against unchanged inputs produces byte-identical `candidate_rolls.json` (`candidates` explicitly sorted by `(chapter_num, slot_index)`, never raw dict/set order).
- `build_candidate_rolls.py` never reads or writes `data/manual/chapter_roll_overrides.json` — `merge_paid_units` is called with `overrides=None` directly, never through `load_overrides`.
- Added `tests/test_build_candidate_rolls.py` with 10 tests total (1 full-corpus-wiring test from Task 2's TDD RED/GREEN pairing + 9 named synthetic-fixture tests from Task 3), all pure — no epub or `data/derived`/`data/manual` file access anywhere in the file.

## Task Commits

Each task was committed atomically:

1. **Task 1: Bind rolls end-to-end via POSITIONAL cursor advance — schema, script skeleton, proven against a synthetic fixture** - `4a5410d` (feat)
2. **Task 2: Full-corpus assembly — free-perk forward search, partial-evidence marking, write candidate_rolls.json** - `7440f42` (test, RED) then `7f8afff` (feat, GREEN)
3. **Task 3: Synthetic-fixture tests — positional binding, bundle grouping, constellation binding, partial evidence** - `f29998b` (test)

_Note: Task 2 is `tdd="true"` — RED commit (`7440f42`) added a failing test for `assemble_all_candidates` (which didn't exist yet) before implementing full-corpus wiring; GREEN commit (`7f8afff`) implemented it and made the test pass. No REFACTOR commit was needed._

## Files Created/Modified

- `data/derived/_schemas/candidate_rolls.schema.json` - New schema: candidate-roll shape (roll-object fields + `_derivation` provenance)
- `scripts/build_candidate_rolls.py` - New: `assemble_candidate` (pure binder), `assemble_all_candidates`/`main()` (full-corpus wiring + write), `_find_free_perk_evidence` (liberal forward search), `_extract_constellation_from_anchor_phrase`, `_build_prose_loader`, `_chapter_sort_key`
- `tests/test_build_candidate_rolls.py` - New: 10 tests over synthetic fixtures (no epub/data-file access)
- `data/derived/candidate_rolls.json` - New derived artifact (gitignored, regenerable): 718 candidates from the live corpus

## Decisions Made

- The free-perk forward search's Tier 2 fallback uses a per-character (not per-token) hyphen/space-tolerant connector — the only construction that generalizes the plan's own cited example ("Altmode" vs. "alt-mode", where the prose variant inserts a separator the perk name never had at all). Still ReDoS-safe: every connector is a single bounded character class, mirroring `mechanical_verifier._build_tier2_pattern`'s shape.
- `evidence_quotes` are populated exclusively from the free-perk forward search — never from the roll's own connection narration. The plan's Task 2 action text and frontmatter must-haves both scope quote emission to "Stage 1's free-perk name search"; adding a second quote source would have been an uncalled-for second search path.
- `assemble_candidate` takes optional `chapter_html`/`word_index` parameters (default `None`) rather than being split into separate binder/evidence-attacher functions — the same pure function serves Task 1's no-prose synthetic fixture and Task 2/3's prose-search-enabled callers. When prose access is omitted, no `evidence_for:<perk>` claim is added either (a search that never ran makes no honesty claim about its result).

## Deviations from Plan

None - plan executed exactly as written, including the plan's own explicit revision note (binding rule corrected from anchor-gated to positional cursor advance before this plan was executed).

## Issues Encountered

- The first Tier 2 forward-search implementation (token-level hyphen/space join) failed the RED test's hyphen-variant assertion — it only tolerates a variant with a separator at the SAME position the perk name already has one, which cannot match "Altmode" (no internal separator) against "alt-mode" (separator inserted mid-word). Resolved by switching to a per-character connector (see Decisions Made above); re-ran the RED test to confirm GREEN before proceeding.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-03 (accuracy measurement) can proceed: `data/derived/candidate_rolls.json` (718 candidates, full `_derivation` provenance) is stable and reproducible.
- Phase 4 (inference refinement) has a measured deterministic baseline to size its own scope against: 318/718 (44%) bind a hit positionally, only 6 of those anchor-confirmed; 24/718 (3%) bind a miss; 376/718 (52%) are honestly unfilled.
- No blockers.

## Self-Check: PASSED

- All files listed under `key-files.created` verified present on disk (`data/derived/_schemas/candidate_rolls.schema.json`, `scripts/build_candidate_rolls.py`, `tests/test_build_candidate_rolls.py`).
- All 4 commit hashes (`4a5410d`, `7440f42`, `7f8afff`, `f29998b`) verified present via `git log --oneline --all`.
- All plan `<acceptance_criteria>` re-run and passing (schema loadable/`additionalProperties: false`, synthetic-fixture binding rule proven, 718-candidate live run matching exact regression totals, deterministic re-run diff-clean, quotes verified as literal prose substrings, 9/9 named Task 3 tests passing).
- Plan-level `<verification>` commands re-run: `.venv/bin/python scripts/build_candidate_rolls.py` completes without exception (718 candidates); `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_build_candidate_rolls.py -q` green (10 passed).
- Full suite (`PYTHONPATH=scripts .venv/bin/python -m pytest -q`) shows exactly the same 5 known-accepted baseline failures, no new ones; `mechanical_verifier.py` unchanged at pass=593/no_evidence=88/fail=0; `data_release.py check-derived` passes.

---
*Phase: 03-provenance-schema-deterministic-candidate-assembly*
*Completed: 2026-08-02*
