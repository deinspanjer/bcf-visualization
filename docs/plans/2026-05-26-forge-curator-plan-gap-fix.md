# Forge Curator Plan Gap Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the unimplemented requirements from the `019e65bb-2e85-72e2-8de8-986d625c48be` roll ordinal refactor without disturbing the accepted `source_ordinal` / `S#` model.

**Architecture:** Treat derived facts as the source of truth. Replace explicit manual deferral as a required workflow with derived/read-model availability of unmatched, unskipped prior predicted slots. Keep legacy deferral fields only long enough to migrate existing data into the cleaner model, then remove the action, persistence paths, tests, UI labels, and stale manual fields.

**Tech Stack:** Python derivation pipeline, Forge Curator Textual TUI, JSON schemas, vanilla web runtime tests, pytest.

---

## Acceptance Matrix

| Requirement | Current Status | Target |
| --- | --- | --- |
| `source_ordinal` / `S#` source identity | Implemented and accepted | Preserve; do not redesign |
| `_d` no longer required | Implemented | Removed user action and dependency |
| Unmatched unskipped `P#` available in later `_S`/quote workflows | Implemented | Read model exposes valid prior open targets without deferral override |
| Open/deferred collapsed into `P#` status, not separate mechanisms | Implemented | Removed `deferred_in` / `source_deferred` display mechanisms |
| Legacy deferral metadata migration-only | Implemented | Migrated manual state and removed stale fields |
| Review invalidation after reviewed-through marker | Implemented | Chapter-level model-validation warning detects baseline drift |
| Remove old `roll_number` from final derived runtime contract | Implemented | Runtime artifacts use explicit predicted/source/roll/chapter ordinals |
| Survey designation display | Out of scope | Added TODO only |

## Files

- Modify `scripts/forge_curator/app.py`: remove `_d` action and explicit deferral target discovery; add unified open-target discovery.
- Modify `scripts/forge_curator/persistence.py`: remove deferral writers after migration; keep source assignment and quote persistence keyed by chapter/index and source ordinal.
- Modify `scripts/derive_roll_facts.py`: make open prior predicted slots and source association state explicit enough for consumers; add association review invalidation inputs.
- Modify `scripts/build_chapter_facts.py`: expose chapter/read-model fields needed by Forge Curator without TUI synthesis.
- Modify `scripts/multi_grab.py`: remove defaulting/preserving obsolete deferral fields.
- Modify schemas in `data/derived/_schemas/*.schema.json`: remove obsolete final-contract fields and add review status fields where required.
- Modify `data/manual/chapter_roll_overrides.json`: migrate active `source_deferred_to_chapter` and stale `deferred_to_later_chapter` fields.
- Modify Forge Curator tests under `tests/forge_curator/`.
- Modify pipeline/model tests under `tests/test_*roll*`, `tests/test_chapter_facts_scenarios.py`, and `tests/test_model_validation.py`.
- Modify web tests only if final runtime contract changes.
- Modify `USERS.md` if operator-visible key bindings or workflow docs mention deferral.
- Modify `TODO.md` only for the out-of-scope Survey display item.

## Task 1: Lock The Missing Behavior With Failing Tests

- [x] Add a Forge Curator read-model test in `tests/forge_curator/test_roll_read_model.py`: a prior chapter has an unmatched, unskipped predicted slot with no legacy deferral field; loading a later chapter shows that prior `P#` as an `_S` target.
- [x] Add a quote-targeting test in `tests/forge_curator/test_curation_actions.py`: `_Q` can attach selected text in the later chapter to that prior open `P#` without first invoking `_d`.
- [x] Add a negative test: skipped prior `P#` slots are not source or quote targets.
- [x] Run the new tests and confirm they fail for the previous implementation.

## Task 2: Replace Deferral-Based Target Discovery

- [x] Add a derived/read-model helper that returns unmatched, unskipped predicted targets before the current chapter according to chapter order.
- [x] Use that helper in `_source_assignment_target_rows()` and quote target construction.
- [x] Remove the previous-chapter-only patch after the generalized helper passes tests.
- [x] Ensure target identity is always `(target_chapter_num, target_roll_index)` plus P label context, not display-kind-specific deferral identity.

## Task 3: Remove `_d` As A Required/User Workflow

- [x] Remove `<space>d` from the help text and key dispatch in `scripts/forge_curator/app.py`.
- [x] Remove `_action_defer_roll_to_next_chapter()` after replacement workflows pass.
- [x] Remove or migrate tests that assert toggling legacy deferral fields through `_d`.
- [x] `USERS.md` had no operator-visible deferral workflow reference to update.

## Task 4: Migrate And Remove Legacy Deferral Metadata

- [x] Wrote a focused one-off migration for `data/manual/chapter_roll_overrides.json`.
- [x] Preserved existing source assignments/evidence placement on the owning target and removed the separate projection marker.
- [x] Removed false/null legacy deferral fields.
- [x] Removed persistence methods that create legacy fields once no tests or data depend on them.
- [x] Added an invariant test that manual overrides contain no legacy deferral fields.

## Task 5: Implement Association Review Invalidation

- [x] Added a scenario test: with `association_review.reviewed_through_chapter_num` set, baseline drift produces review invalidation.
- [x] Defined the output contract as a chapter-level model-validation warning.
- [x] Implemented baseline comparison against the stored fingerprint/count.
- [x] Existing schema issue shape covers the warning; Forge Curator model status surfaces the discrepancy.
- [x] Kept reviewed auto links as `association_source: auto`; accepted auto links are not converted into curated links.

## Task 6: Finish Old `roll_number` Contract Cleanup

- [x] Classified remaining top-level derived `roll_number` occurrences as internal pipeline state or final runtime contract.
- [x] For final runtime consumers, replaced `roll_number` with explicit `predicted_ordinal` / `predicted_label` or `roll_ordinal` / `roll_label`.
- [x] Kept `predicted_rolls.json` as internal model input; `visualization_facts.predicted_rolls` now uses explicit predicted identity.
- [x] Added contract tests covering the actual final runtime artifacts.

## Task 7: Regenerate And Verify

- [x] Run `.venv/bin/python scripts/pipeline.py --target data`.
- [x] Run targeted tests added/changed in the tasks above.
- [x] Run `.venv/bin/python scripts/verify.py`.
- [x] Before final reporting, update the acceptance matrix with implemented/changed/not-done status and include the obsolete-term audit results for `_d`, legacy deferral fields, `deferred_in`, and `source_deferred`.

## Obsolete-Term Audit

- `_d` / `_action_defer_roll_to_next_chapter`: removed from key dispatch, action implementation, and tests.
- `deferred_to_later_chapter` / `source_deferred_to_chapter`: removed from manual data, persistence writers, derivation propagation, and production code. The only remaining references are in `tests/test_roll_ordinal_contract.py`, where they are forbidden by invariant.
- `deferred_in` / `source_deferred`: removed from Forge Curator display/read-model production code, generated data, and tests.
- `roll_number`: absent from final runtime roll contracts in `roll_facts.json`, `chapter_facts.json`, and `visualization_facts.json`; remaining usage is internal predicted-roll pipeline input or tests asserting absence.
