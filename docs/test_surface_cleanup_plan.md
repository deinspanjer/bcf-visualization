# Test Surface Cleanup Plan

This plan tracks the long-term goal of organizing the project test
surface by layer, replacing current-story-shape assertions with stable
fixtures, and reaching feature-level coverage for data pipeline, Forge
Curator TUI, web UI, release/package, and shared helper behavior.

The current feature-to-test matrix is maintained in
[test_feature_inventory.md](test_feature_inventory.md). Update it when
adding, moving, rewriting, or retiring feature-level tests.

## Success Criteria

- Every product feature has at least one test at the appropriate layer.
- Data pipeline tests use purpose-built input fixtures and verify derived
  output contracts after explicit source or manual-curation mutations.
- Forge Curator TUI tests cover app input loading, action behavior,
  curation writes, rebuild/reload invocation, and error handling without
  re-testing derivation internals.
- Web UI unit tests cover web-specific pure logic such as state
  transitions, formatters, data-contract helpers, and render-model
  builders with stable fixtures.
- Web UI integration tests load the app against a purpose-built runtime
  data package and verify user-visible behavior without depending on the
  current curated chapter or roll shape.
- Coherence and smoke tests may inspect current generated data only for
  global contracts such as schema validity, manifest consistency, path
  safety, package completeness, and runtime entrypoint availability.
- Source coverage targets are evaluated after feature coverage is mapped;
  source coverage must not drive tests that pin incidental implementation
  details.

## Current Inventory

- Data pipeline scenario tests cover the main derivation capabilities;
  current generated data checks are kept as coherence tests for global
  contracts such as simulator agreement and schema consistency.
- Forge Curator TUI tests cover many actions and display states, but the
  large historical test file still contains tests that should be split by
  capability and checked for current-story-shape assumptions.
- Web UI unit tests currently cover `web/data-contract.js` and
  `web/viz-model.js` helper behavior with inline stable fixtures.
- Web UI integration uses a fixture-backed browser test file against
  synthetic runtime data and covers the main documented interactions.
- Release/package tests cover several real package contracts and should
  stay focused on manifest, hash, path-safety, and deployable bundle
  behavior rather than exact generated story contents.

## Parallel Workstreams

These workstreams can be parallelized because they have mostly disjoint
file ownership.

### Data Pipeline

Primary files:

- `tests/test_an_detector.py`
- `tests/test_chapter_roll_overrides.py`
- `tests/test_deferred_rolls.py`
- `tests/test_roll_position_invariants.py`
- `tests/test_predicted_roll_field_names.py`
- `tests/test_model_validation.py`
- pipeline scripts under `scripts/`

Keep the fixture-based parser, override-loader, and helper-level
deferred-roll tests that already use explicit local data. Rewrite or
replace tests that discover live current-story rows, pin specific
chapter numbers, or require current cross-chapter curation state.

Needed scenario coverage:

- `build_section_classifications.py` with tiny sections and manual span
  overrides. Initial coverage exists in
  `tests/test_section_classification_scenarios.py` for generated header
  spans, preserved curated spans, and mechanics-evidence promotion.
- `extract_chapter_sections.py` into `build_section_classifications.py`
  into `predict_rolls.py` using a tiny story fixture. Initial coverage
  exists in `tests/test_extract_classify_predict_scenarios.py` for
  fixture HTML section splitting, regenerated section classifications,
  CP-eligible word counting, and predicted roll positions.
- `derive_roll_outcomes.py` for zero hits, all hits, synthetic slots,
  free perks, and banked CP/regime continuity. Initial coverage exists
  in `tests/test_roll_outcome_scenarios.py` for proportional hit
  placement, all-miss chapters, synthetic slots, multi-grab/free perk
  attachment, miss carry-forward, hit debit, mid-chapter regime
  transition, and regime-3 shadow carry.
- `derive_roll_facts.py` plus `build_chapter_facts.py` for deferred
  rows, cross-chapter projections, skipped slots, source-roll deferral,
  quote-only overrides, and display-position policy. Coverage exists in
  `tests/test_chapter_facts_scenarios.py` for both hand-written
  `roll_facts.json` projection and a direct `derive_roll_facts.py` to
  `build_chapter_facts.py` fixture flow.
- Validation discrepancy fixtures for raw/effective mismatch behavior.
  Initial coverage exists in `tests/test_model_validation_scenarios.py`
  for unresolved blocking issues, curator-resolved blocking issues that
  retain raw discrepancy state, and info-only ambiguity.

### Forge Curator TUI

Primary files:

- `tests/test_forge_curator.py`
- `tests/test_forge_curator_roll_labels.py`
- `tests/test_forge_curator_state.py`
- `tests/test_passage_view.py`

Keep `PassageView` and state-model unit tests that are already small and
stable. Split the large app test file by capability before doing broad
rewrites.

Initial fixture infrastructure exists in
`tests/helpers/forge_curator_fixture.py`. Snapshot behavior has moved to
`tests/forge_curator/test_snapshot.py` and no longer depends on live
chapter prose or current curated roll data. Initial curation-action
coverage exists in `tests/forge_curator/test_curation_actions.py` for
quote evidence writes, deferral toggling, and source-roll assignment
through the app action layer. Initial roll read-model coverage exists in
`tests/forge_curator/test_roll_read_model.py` for open predicted slots,
deferred predicted targets, deferred source rows, and source-link pair
normalization. Initial stats/gutter semantic coverage exists in
`tests/forge_curator/test_stats_gutter.py` for roll target registration
and gutter marks from fixture data.

Suggested target files:

- `tests/forge_curator/test_navigation.py`
- `tests/forge_curator/test_search.py`
- `tests/forge_curator/test_pickers.py`
- `tests/forge_curator/test_curation_actions.py`
- `tests/forge_curator/test_roll_read_model.py`
- `tests/forge_curator/test_stats_model.py`
- `tests/forge_curator/test_panels.py`

Rewrite tests that depend on live chapters such as current `8.1/9/19/20`
or `97` data, current quote text, current unresolved model issues, or
exact rendered stats text. Preserve narrow copy/layout tests only where
the exact UI output is the product contract.

Needed feature coverage:

- Purpose-built `ForgeCuratorApp` fixture data.
- Snapshot behavior for F12/Ctrl-S using fixture-backed data and the
  fixed overwrite path.
- Keyboard flows for roll curation actions and picker confirm/cancel
  paths through `run_test`. Initial source-link picker coverage exists
  in `tests/forge_curator/test_pickers.py` for initial focus, Escape
  dismissal, keyboard traversal, and keyboard-only confirm.
- Action tests proving manual curation writes invoke the intended refresh
  path without re-testing the downstream pipeline.
- Persistence write failure handling.
- Malformed manual data handling. Initial coverage exists in
  `tests/forge_curator/test_error_handling.py` for malformed manual
  roll-overrides loading.
- Modal focus and keyboard-only traversal behavior.

### Web UI And Release

Primary files:

- `tests/test_web_data_contract.py`
- `tests/test_web_viz_model.py`
- `tests/test_pages_smoke.py`
- `tests/test_data_package_contract.py`
- `web/app.js`
- `web/data-contract.js`
- `web/viz-model.js`
- `scripts/smoke_pages_site.py`

Keep current web unit tests for `data-contract.js` and `viz-model.js`.
Keep staged-site validation focused on package/runtime contracts. Keep
browser integration coverage in `tests/test_web_app_integration.py`
rather than expanding package smoke tests into app behavior tests.

Completed feature coverage:

- Scrubber keyboard behavior. Initial coverage exists in
  `tests/test_web_app_integration.py` for Arrow/Home/End movement,
  clamping, readout updates, bookmark persistence, restore, and reset.
- Playback and bookmark behavior. Initial coverage exists in
  `tests/test_web_app_integration.py` for play/pause state, progress over
  time, speed persistence, restart-from-end behavior, reload restore, and
  reset.
- Timeline click/drag behavior. Initial coverage exists in
  `tests/test_web_app_integration.py` for chapter tick selection and
  pointer dragging with semantic word-position/readout/bookmark
  assertions rather than pixel snapshots.
- Roll tooltip behavior. Initial coverage exists in
  `tests/test_web_app_integration.py` for hover details and normal
  click/open behavior, touch-style pinning, and outside-click dismissal.
- Rich track rendering semantics. Initial coverage exists in
  `tests/test_web_app_integration.py` for POV sections, skipped markers,
  shadow bars, unknown/untracked/free/binary/trinary roll markers, and
  display-position fallback placement.
- Current-position panels. Initial coverage exists in
  `tests/test_web_app_integration.py` for pre-roll state, cumulative
  stats, constellation rows, recent acquisitions, selected detail close,
  and selected chapter clearing when moving to another chapter/end.
- Package selector edge cases. Initial coverage exists in
  `tests/test_web_app_integration.py` for selecting the default removing
  `dataPackage` and invalid requested packages falling back cleanly.
- App-level contract behavior. Initial coverage exists in
  `tests/test_web_app_integration.py` for unsupported required docs
  showing a load error and bad optional wireframes disabling the sky
  view without breaking the scrubber.
- Sky controls. Coverage exists in `tests/test_web_app_integration.py`
  for Focus/Art/Lines/Labels/Rotate state, persistence, HUD updates,
  and active hit/miss roll focus.
- Browser-backed web app load against a synthetic runtime package.
  Initial coverage exists in `tests/test_web_app_integration.py`.
- Scrubber rendering from tiny chapter facts. Initial coverage exists in
  `tests/test_web_app_integration.py`.
- Chapter selection opening selected-chapter details. Initial coverage
  exists in `tests/test_web_app_integration.py`.
- Package selector URL rewrite for non-default packages. Initial
  coverage exists in `tests/test_web_app_integration.py`.
- Theme toggle state. Initial coverage exists in
  `tests/test_web_app_integration.py`.
- Zoom control behavior. Initial coverage exists in
  `tests/test_web_app_integration.py`.
- Optional sky data handling. Initial coverage exists in
  `tests/test_web_app_integration.py` using the synthetic runtime
  fixture with and without `constellation_wireframes.json`.

## Cleanup Slices

1. Build shared fixture helpers for tiny runtime data packages, tiny
   source/manual curation inputs, and Forge Curator app state.
2. Split current generated-data coherence tests from fixture-based
   scenario tests so routine data curation does not break behavior tests.
3. Rework data pipeline tests into scenario files named by capability:
   section eligibility, roll prediction, roll overrides, deferred rolls,
   evidence quotes, package contracts, and validation.
4. Rework Forge Curator TUI tests into capability files: navigation,
   search, visual selection, section eligibility actions, roll evidence
   actions, source assignment, deferral, rebuild/reload, snapshot, and
   display formatting.
5. Maintain web UI integration tests against the tiny synthetic runtime
   package as web interactions evolve.
6. Keep [test_feature_inventory.md](test_feature_inventory.md) current
   as the feature-to-test checklist.
7. Assess source/line coverage once the feature inventory is covered,
   then decide whether extra coverage is useful or would only pin
   incidental implementation shape.

## Web UI Integration Fixture Requirements

The web UI integration fixture should create a temporary staged site with:

- `web/index.html`, `web/app.js`, `web/data-contract.js`,
  `web/viz-model.js`, and `web/style.css` copied or served from the
  working tree.
- `data/packages.json` containing one default package and, for selector
  tests, a second package.
- `data/packages/<package-id>/data_package.json` with the web runtime
  entrypoint contract.
- `data/packages/<package-id>/chapter_facts.json` containing two or
  three tiny chapters, at least one hit, one miss, one skipped predicted
  slot, and one visible constellation progress row.
- Optional `constellation_wireframes.json` only for sky-view tests.

Tests should assert stable behavior such as "the selected chapter panel
opens for the clicked chapter" or "the package selector rewrites the URL
for a non-default package." They should not assert that a live BCF
chapter, current global roll number, or current latest release appears.

## Audit Notes

When touching tests, classify each test as one of:

- `keep`: already protects a meaningful feature or invariant with stable
  fixtures or derived expectations.
- `update`: useful behavior, but the fixture or assertion should be made
  less coupled to current curated data.
- `rewrite`: valid target behavior, but the test shape mostly pins
  implementation or current-story data.
- `remove`: no longer covers active behavior, duplicates another test, or
  only preserves obsolete compatibility.

Do not remove a behavior test until the replacement scenario exists or
the covered behavior is intentionally retired.
