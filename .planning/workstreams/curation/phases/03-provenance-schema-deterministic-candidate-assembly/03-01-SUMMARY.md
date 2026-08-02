---
phase: 03-provenance-schema-deterministic-candidate-assembly
plan: 01
subsystem: data-pipeline
tags: [python, jsonschema, provenance, chapter_roll_overrides, forge-curator, pytest]

# Dependency graph
requires:
  - phase: 02-mechanical-verifier
    provides: "the hand-curated 118-chapter corpus as the trusted baseline this plan stamps and re-validates"
provides:
  - "data/derived/_schemas/chapter_roll_overrides.schema.json — requires curated_by (enum human|agent) + rolls on every chapter entry"
  - "scripts/chapter_roll_overrides_io.py:load_chapter_roll_overrides_doc — the ONE schema-validating read of chapter_roll_overrides.json, consumed by all four in-repo readers"
  - "scripts/stamp_curator_provenance.py — idempotent one-time bulk stamp script"
  - "_common.py:read_validated_json — read-side counterpart to write_validated_json; missing file defaults without validation, existing file always validates"
  - "All 118 existing chapter_roll_overrides.json entries stamped curated_by: \"human\""
  - "forge_curator/persistence.py's data-destruction bug fixed: a malformed existing overrides file now raises instead of silently becoming an empty document a later auto-save would overwrite the corpus with"
affects: [phase-3-plan-2-candidate-assembly, phase-3-plan-3-accuracy-measurement, phase-4-inference-refinement]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "read_validated_json(path, schema_name, default=...): missing file -> deepcopy(default), no validation; existing file -> always parsed + schema-validated, raises on syntax error or schema violation. Read-side mirror of the existing write_validated_json."
    - "A shared io module (chapter_roll_overrides_io.py) as the single consolidation point for a manual/ data file with four independent historical readers — same shape as Phase 2's tokenizer consolidation."
    - "Dual-context bare-import fallback (try bare sibling import, except ImportError fall back to scripts.<sibling>) for a scripts/ module that must resolve both when scripts/ is on sys.path (PYTHONPATH=scripts) and when imported package-qualified from the forge_curator TUI package (python -m scripts.forge_curator, repo root only on sys.path)."

key-files:
  created:
    - data/derived/_schemas/chapter_roll_overrides.schema.json
    - scripts/chapter_roll_overrides_io.py
    - scripts/stamp_curator_provenance.py
    - tests/test_chapter_roll_overrides_io.py
  modified:
    - scripts/_common.py
    - scripts/multi_grab.py
    - scripts/build_chapter_facts.py
    - scripts/forge_curator/data_loader.py
    - scripts/forge_curator/persistence.py
    - data/manual/chapter_roll_overrides.json
    - tests/test_chapter_roll_overrides.py
    - tests/test_deferred_rolls.py
    - tests/test_chapter_facts_scenarios.py
    - tests/test_forge_curator.py
    - tests/forge_curator/test_error_handling.py
    - tests/forge_curator/test_curation_actions.py
    - tests/forge_curator/test_stats_gutter.py

key-decisions:
  - "chapter_roll_overrides_io.py's internal imports of _common/data_paths use a try/except ImportError fallback to scripts._common/scripts.data_paths, discovered as a real bug during Task 2 verification (not anticipated by the plan): the forge_curator TUI runs as `python -m scripts.forge_curator` with only the repo root on sys.path, so the bare-import convention used by top-level scripts/*.py siblings does not resolve when the module is imported package-qualified from within the forge_curator subpackage."
  - "Rewrote the write to data/manual/chapter_roll_overrides.json via write_validated_json, which serializes with ensure_ascii=False — this re-encodes previously \\uXXXX-escaped non-ASCII characters (em dashes, ellipses) to literal UTF-8 in entries the stamp script touched. Verified content-identical via a JSON-level diff (parsed old vs. new, chapter-by-chapter, ignoring curated_by) before committing: zero semantic differences beyond the additive curated_by field. This is a formatting-only side effect of going through the canonical write path (already the convention elsewhere in the codebase, e.g. persistence.py's own _atomic_write_json), not a content change."

patterns-established:
  - "A manual/ (hand-curated) data file gets the same schema-validated read/write treatment as data/derived/ artifacts once more than one call site needs a shared invariant — the schema lives in data/derived/_schemas/ regardless of where the data file itself lives."

requirements-completed: [CINF-01]

coverage:
  - id: D1
    description: "New JSON schema requires curated_by (enum human|agent) and rolls on every chapter_roll_overrides chapter entry; absent/invalid curated_by is a validation error, never a default"
    requirement: CINF-01
    verification:
      - kind: unit
        ref: "tests/test_chapter_roll_overrides_io.py#test_missing_curated_by_raises"
        status: pass
      - kind: unit
        ref: "tests/test_chapter_roll_overrides_io.py#test_invalid_curated_by_enum_raises"
        status: pass
      - kind: unit
        ref: "tests/test_chapter_roll_overrides.py#test_load_overrides_missing_curated_by_raises"
        status: pass
    human_judgment: false
  - id: D2
    description: "All 118 pre-existing chapter_roll_overrides.json entries stamped curated_by: \"human\"; live corpus loads through the consolidated loader with zero errors"
    requirement: CINF-01
    verification:
      - kind: unit
        ref: "tests/test_chapter_roll_overrides_io.py#test_live_corpus_loads_and_all_118_entries_are_human"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c \"...load_chapter_roll_overrides_doc(); assert len==118 and all curated_by=='human'\" -> OK"
        status: pass
      - kind: other
        ref: "PYTHONPATH=scripts .venv/bin/python -c \"from stamp_curator_provenance import stamp; print(stamp())\" second run -> (0, 118) idempotent"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/multi_grab.py, scripts/build_chapter_facts.py, scripts/forge_curator/data_loader.py, and scripts/forge_curator/persistence.py all read chapter_roll_overrides.json exclusively through chapter_roll_overrides_io.load_chapter_roll_overrides_doc — no bare json.loads of that file remains in any of the four; no fifth loader added"
    requirement: CINF-01
    verification:
      - kind: other
        ref: "grep -rn 'json.loads(.*CHAPTER_ROLL_OVERRIDES|json.loads(.*chapter_roll_overrides_path|json.loads(.*_OVERRIDES_PATH' scripts/multi_grab.py scripts/build_chapter_facts.py scripts/forge_curator/data_loader.py scripts/forge_curator/persistence.py -> zero matches"
        status: pass
    human_judgment: false
  - id: D4
    description: "forge_curator/persistence.py's CurationPersistence.__init__ raises on an existing-but-malformed overrides file (JSON syntax error or missing curated_by) instead of silently defaulting to an empty document; a genuinely missing file still starts cleanly"
    requirement: CINF-01
    verification:
      - kind: unit
        ref: "tests/forge_curator/test_error_handling.py#test_malformed_manual_roll_overrides_raises_on_load"
        status: pass
      - kind: other
        ref: "manual construction test: malformed-JSON path raises JSONDecodeError; genuinely-missing path defaults to {chapter_roll_overrides: {}}"
        status: pass
    human_judgment: false
  - id: D5
    description: "New TUI-created chapter entries (_ensure_chapter_entry) stamp curated_by: \"human\" immediately, matching the one human-facing write path in this phase"
    requirement: CINF-01
    verification:
      - kind: other
        ref: "manual construction test: p._ensure_chapter_entry('999-test-only')['curated_by'] == 'human'"
        status: pass
    human_judgment: false
  - id: D6
    description: "No new test failures beyond the 5 known-accepted pre-existing baseline; mechanical_verifier.py unchanged at pass=593/no_evidence=88/fail=0"
    requirement: CINF-01
    verification:
      - kind: integration
        ref: "PYTHONPATH=scripts .venv/bin/python -m pytest -q — 5 failed (baseline names exactly), 623 passed"
        status: pass
      - kind: other
        ref: ".venv/bin/python scripts/verify.py — 5 failed, 623 passed (exit 1, expected per known-accepted baseline)"
        status: pass
      - kind: other
        ref: "PYTHONPATH=scripts .venv/bin/python scripts/mechanical_verifier.py — pass: 593, no_evidence: 88, fail: 0"
        status: pass
    human_judgment: false

# Metrics
duration: 20min
completed: 2026-08-02
status: complete
---

# Phase 3 Plan 1: Provenance Schema & Consolidated Overrides Loader Summary

**Schema-validating `chapter_roll_overrides.json` loader (`curated_by` required, enum `human`\|`agent`) replaces four independent bare-`json.loads` call sites, all 118 hand-curated entries stamped `human`, and a real silent-data-loss bug in the Forge Curator TUI's persistence layer is fixed.**

## Performance

- **Duration:** ~20 min (measured from first implementation commit to last)
- **Completed:** 2026-08-02
- **Tasks:** 3
- **Files modified:** 17 (4 created, 13 modified)

## Accomplishments

- Added `data/derived/_schemas/chapter_roll_overrides.schema.json`, requiring `curated_by` (enum `["human", "agent"]`) and `rolls` on every chapter entry, `additionalProperties: true` elsewhere so no unrelated sibling key (`_fingerprint`, `model_validation_resolution`) needs enumerating.
- Extended `scripts/_common.py` with `read_validated_json` (the read-side counterpart to the existing `write_validated_json`): a missing file defaults without validation; an existing file always parses and validates, raising `ValueError`/`json.JSONDecodeError` on any problem.
- Added `scripts/chapter_roll_overrides_io.py` — the one place that reads `chapter_roll_overrides.json` going forward — and rewired all four historical readers (`multi_grab.load_overrides`, `build_chapter_facts._load_chapter_roll_overrides`/`_load_association_review_marker`, `forge_curator/data_loader.py`'s `chapter_roll_overrides` property, `forge_curator/persistence.py`'s `CurationPersistence.__init__`) through it. `grep` confirms zero bare `json.loads` of the overrides file remains in any of them.
- Added `scripts/stamp_curator_provenance.py` (idempotent, mirrors `bootstrap_chapter_alignment_anchors.py`'s one-time-stamp shape) and ran it against the real corpus: all 118 chapter entries now carry `curated_by: "human"`. Verified via JSON-level diff that the only semantic change is the additive field (`git diff --stat` shows a larger byte diff from `write_validated_json`'s `ensure_ascii=False` re-encoding of existing non-ASCII characters, which is content-identical — verified programmatically).
- Fixed the real data-destruction bug found during pattern mapping: `persistence.py`'s `CurationPersistence.__init__` no longer routes the overrides load through `_load_or_default`'s broad `except Exception: return default`. An existing-but-malformed file (parse error, or now, a chapter entry missing `curated_by`) raises and aborts TUI startup instead of silently collapsing to an empty document that the next auto-save would overwrite the real corpus with. A genuinely absent file still defaults cleanly.
- `_ensure_chapter_entry` now stamps `curated_by: "human"` on any brand-new chapter entry the TUI creates — the only human-facing write path for the field in this phase.
- Updated every synthetic test fixture across 7 test files that writes its own `chapter_roll_overrides.json` content with a real chapter entry, adding `curated_by: "human"`. Added `tests/test_chapter_roll_overrides_io.py` with D-12's required test pairing (missing/invalid `curated_by` raises; the live 118-chapter corpus loads and validates; a missing file still defaults) plus enum-violation coverage.
- Discovered and fixed a real dual-import-context bug during Task 2 verification: `chapter_roll_overrides_io.py`'s bare sibling imports (`from _common import ...`, `from data_paths import ...`) failed when the module was imported package-qualified (`scripts.chapter_roll_overrides_io`) from the forge_curator TUI package, which runs as `python -m scripts.forge_curator` with only the repo root — not `scripts/` — on `sys.path`. Fixed with a try/except fallback to `scripts._common`/`scripts.data_paths`; verified both import contexts explicitly.

## Task Commits

Each task was committed atomically:

1. **Task 1: Schema-validated overrides loader, proven read/write round-trip, live-corpus stamp** - `2f5cfb0` (feat)
2. **Task 2: Rewire the four consumers; fix persistence.py's silent-default bug** - `2285460` (test, RED) then `6ac3dd4` (feat, GREEN)
3. **Task 3: Update pre-existing test fixtures for the new required field; add D-12 validation tests** - `3b8e5a0` (test)

_Note: Task 2 is `tdd="true"` — RED commit (`2285460`) added a failing test for `load_overrides`'s new required-field behavior before the rewire; GREEN commit (`6ac3dd4`) implemented the rewire and made it pass. No REFACTOR commit was needed._

## Files Created/Modified

- `data/derived/_schemas/chapter_roll_overrides.schema.json` - New schema: `curated_by` (enum human\|agent) + `rolls` required per chapter entry
- `scripts/_common.py` - Factored `_validate` helper; added `read_validated_json`
- `scripts/chapter_roll_overrides_io.py` - New consolidated loader (`load_chapter_roll_overrides_doc`)
- `scripts/stamp_curator_provenance.py` - New idempotent one-time bulk-stamp script
- `data/manual/chapter_roll_overrides.json` - All 118 entries stamped `curated_by: "human"`
- `scripts/multi_grab.py` - `load_overrides` rewired through the consolidated loader; removed `_OVERRIDES_PATH`
- `scripts/build_chapter_facts.py` - `_load_chapter_roll_overrides`/`_load_association_review_marker` rewired
- `scripts/forge_curator/data_loader.py` - `chapter_roll_overrides` property rewired
- `scripts/forge_curator/persistence.py` - `__init__` rewired (bug fix), `_ensure_chapter_entry` stamps `curated_by`
- `tests/test_chapter_roll_overrides.py` - Fixed roll-dict-shape fixture; added `test_load_overrides_missing_curated_by_raises`
- `tests/test_chapter_roll_overrides_io.py` - New: D-12 test pairing
- `tests/test_deferred_rolls.py`, `tests/test_chapter_facts_scenarios.py`, `tests/test_forge_curator.py`, `tests/forge_curator/test_curation_actions.py`, `tests/forge_curator/test_stats_gutter.py` - Synthetic override fixtures stamped `curated_by: "human"`
- `tests/forge_curator/test_error_handling.py` - Renamed/rewrote the malformed-overrides test to assert raising instead of silent-empty-default

## Decisions Made

- `chapter_roll_overrides_io.py`'s sibling imports need a dual-context fallback (bare, then `scripts.*`) because the module is consumed both by top-level scripts run with `PYTHONPATH=scripts` and by the forge_curator TUI package, which runs with only the repo root on `sys.path`. This was discovered empirically during Task 2 (not anticipated in the plan) and fixed with a try/except ImportError pattern, documented inline.
- The stamp script's write via `write_validated_json` re-encodes pre-existing `\uXXXX`-escaped non-ASCII characters to literal UTF-8 (matching the project's established `ensure_ascii=False` convention, e.g. `persistence.py`'s `_atomic_write_json`). Verified content-identical via a JSON-level (not text-level) diff before committing — no roll content, evidence quotes, or `association_review` fields changed in meaning.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed dual-import-context failure in chapter_roll_overrides_io.py**
- **Found during:** Task 2 verification (after rewiring `forge_curator/data_loader.py` to import the new module package-qualified)
- **Issue:** `chapter_roll_overrides_io.py`'s bare `from _common import ...` / `from data_paths import ...` imports (matching the top-level `scripts/*.py` sibling-import convention) raised `ModuleNotFoundError: No module named '_common'` when the module was imported as `scripts.chapter_roll_overrides_io` from within the forge_curator TUI package — which runs via `python -m scripts.forge_curator` with only the repo root (not `scripts/`) on `sys.path`. This would have broken the real TUI at startup, not just tests (tests happen to put both the repo root and `scripts/` on `sys.path` simultaneously, masking the bug).
- **Fix:** Wrapped the two imports in try/except ImportError, falling back to `scripts._common`/`scripts.data_paths`. Documented the reason inline in the module docstring/comment.
- **Files modified:** `scripts/chapter_roll_overrides_io.py`
- **Verification:** Directly tested both invocation contexts — `import scripts.forge_curator.data_loader` from repo root (no `sys.path.insert`) succeeds; bare `import chapter_roll_overrides_io` with `scripts/` on `sys.path` also succeeds.
- **Committed in:** `6ac3dd4` (part of Task 2's GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — import resolution)
**Impact on plan:** Necessary for correctness — without the fix, the consolidated loader would work in every test but break the real Forge Curator TUI at startup, the opposite of a "no-fifth-loader" consolidation. No scope creep: the fix is confined to `chapter_roll_overrides_io.py`'s import statements.

## Issues Encountered

- `git diff --stat data/manual/chapter_roll_overrides.json` initially looked alarming (382 changed lines for a "just add one field" edit) because `write_validated_json`'s `ensure_ascii=False` re-encodes existing `\uXXXX` escapes to literal UTF-8 characters throughout the file. Resolved by writing a JSON-level (parse-then-compare, not text-diff) verification script before committing: confirmed zero semantic differences beyond the additive `curated_by` field across all 118 entries, `_purpose`, and `association_review`. Documented as a formatting-only side effect, not a content change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 03-02 (Stage 1 deterministic candidate assembler) and 03-03 (accuracy measurement) can proceed — the consolidated loader is stable, the corpus is fully stamped, and `mechanical_verifier.py` is unchanged at pass=593/no_evidence=88/fail=0.
- No blockers.

## Self-Check: PASSED

- All files listed under `key-files.created` verified present on disk (`data/derived/_schemas/chapter_roll_overrides.schema.json`, `scripts/chapter_roll_overrides_io.py`, `scripts/stamp_curator_provenance.py`, `tests/test_chapter_roll_overrides_io.py`).
- All 4 commit hashes (`2f5cfb0`, `2285460`, `6ac3dd4`, `3b8e5a0`) verified present via `git log --oneline --all`.
- All plan `<acceptance_criteria>` re-run and passing (schema loadable, live corpus 118/118 human, idempotent re-stamp, zero bare `json.loads` remaining, malformed file raises, full suite at exactly the 5-failure known-accepted baseline).
- Plan-level `<verification>` commands re-run: `pytest -q` (5 failed / 623 passed, baseline names match exactly), `scripts/verify.py` (exit 1, same 5 failures — expected).

---
*Phase: 03-provenance-schema-deterministic-candidate-assembly*
*Completed: 2026-08-02*
