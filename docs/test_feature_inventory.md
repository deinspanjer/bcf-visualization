# Test Feature Inventory

This inventory maps project features to the intended test layer and the
current owning tests. It is a working checklist for reaching
feature-level coverage without pinning the current curated story data
shape.

Status labels:

- `covered`: has stable feature-level coverage at the intended layer.
- `partial`: has useful coverage, but some tests still depend on live
  generated data, private implementation shape, or incomplete feature
  paths.
- `missing`: feature-level coverage still needs to be added.

## Data Pipeline

| Feature | Layer | Current Tests | Status | Notes |
| --- | --- | --- | --- | --- |
| HTML section splitting and section classification primitives | unit | `tests/test_an_detector.py`, `tests/test_extract_classify_predict_scenarios.py` | covered | Uses fixture HTML and parser functions. |
| Section-classification regeneration | scenario | `tests/test_section_classification_scenarios.py`, `tests/test_extract_classify_predict_scenarios.py` | covered | Covers generated header spans, preserved manual spans, mechanics evidence promotion, and downstream CP counts. |
| CP eligibility span accounting | scenario/unit | `tests/test_an_detector.py`, `tests/test_section_classification_scenarios.py` | covered | Uses temp classifications and span overrides. |
| Roll prediction from classified CP words | scenario/coherence | `tests/test_extract_classify_predict_scenarios.py`, `tests/test_roll_position_invariants.py` | covered | Fixture scenario covers prediction from classified CP words; generated-data simulator checks are coherence only. |
| Outcome slot interpolation | scenario | `tests/test_roll_outcome_scenarios.py` | covered | Covers hit placement, all-miss chapters, synthetic slots, free/multi-grab attachment, miss carry-forward, hit debit, mid-chapter regime transition, and regime-3 shadow carry. |
| Multi-grab and override loading | unit/scenario | `tests/test_chapter_roll_overrides.py`, `tests/test_deferred_rolls.py` | covered | Synthetic helper tests cover override validation/defaults, quote-only non-structural overrides, multi-grab preservation, direct source rows, source deferral metadata, skipped entries, and zero-cost handling. |
| Roll facts derivation | scenario/coherence | `tests/test_chapter_facts_scenarios.py`, `tests/test_deferred_rolls.py`, `tests/test_roll_position_invariants.py`, `tests/test_model_validation.py` | covered | Fixture-backed end-to-end scenario runs `derive_roll_facts.py` into `build_chapter_facts.py` for quote-only metadata, deferred hits, source-roll deferral, skipped slots, and display-position policy; generated-data checks are coherence only. |
| Chapter facts roll projection | scenario/coherence | `tests/test_chapter_facts_scenarios.py`, `tests/test_deferred_rolls.py`, `tests/test_roll_position_invariants.py` | covered | Fixture scenarios cover story-axis projection, skipped predicted markers, discrepancy carry-forward, and pipeline-produced cross-chapter/source-deferred roll facts. |
| Model validation status | unit/coherence | `tests/test_model_validation_scenarios.py`, `tests/test_model_validation.py` | covered | Fixture tests cover raw/effective discrepancy logic; generated-data tests remain as coherence checks. |
| Data package build/release contracts | package/scenario | `tests/test_data_package_contract.py`, `tests/test_pages_smoke.py`, `tests/test_codex_environment_data.py` | covered | Exact identity checks use tiny package fixtures; release download/cleanup tests use synthetic tag strings as API examples. |
| Local generated-data coherence | coherence | `tests/test_model_validation.py`, `tests/test_roll_position_invariants.py`, `tests/test_predicted_roll_field_names.py`, `tests/test_data_package_contract.py` | covered | Current generated data is used only for schema/global invariants, simulator agreement, manifest consistency, and package completeness. |
| Chapter publication-date manual file + bootstrap | scenario | `tests/test_chapter_publication_dates_seed.py`, `tests/test_chapter_facts_scenarios.py` | covered | Seed scenarios cover AO3-source publish + EPUB-source last-edit, missing-from-AO3 fallback to SV provenance, and schema validation. Chapter-facts scenarios assert per-date provenance passes through verbatim and that `edited_lag_days` is computed from the two dates inline. |

## Forge Curator TUI

| Feature | Layer | Current Tests | Status | Notes |
| --- | --- | --- | --- | --- |
| Passage wrapping and cursor movement | unit | `tests/test_passage_view.py` | covered | Stable local text fixtures. |
| Visual selection and text objects | unit | `tests/test_passage_view.py` | covered | Stable local text fixtures. |
| Vim-style find and repeat motions | unit | `tests/test_passage_view.py` | covered | Includes `;`, `,`, visual selection extension, and count handling. |
| Page motions and ctrl page bindings | unit/widget | `tests/test_passage_view.py` | covered | Stable widget tests. |
| ForgeCurator state regex handling | unit | `tests/test_forge_curator_state.py` | covered | Small state fixtures. |
| App navigation and search keybindings | TUI integration | `tests/forge_curator/test_navigation_search.py`, `tests/test_forge_curator.py` | covered | Fixture-backed coverage exists for cursor line motion, chapter/section chords, predicted-roll chords, star regex, regex submit, scorer candidate jumps, and quote-helper motions. |
| Gutter/minimap roll/evidence marks | TUI integration/model | `tests/forge_curator/test_stats_gutter.py`, `tests/test_forge_curator.py` | covered | Fixture-backed semantic mark coverage exists for predicted rolls, curated hits/misses, quote evidence, scorer candidates, user regex, annotation spans, Forge keywords, off-chapter quote suppression, and minimap priority. |
| Stats panel model and formatting | unit/TUI integration | `tests/forge_curator/test_stats_gutter.py`, `tests/test_forge_curator.py` | covered | Fixture-backed target registration and stat-line formatting cover curated/open/deferred rows, quote markers, skipped slots, source markers, click targets, distance statistics, stable target identity, status messages, and cross-chapter evidence wording. |
| Section/span eligibility actions | TUI action scenario | `tests/forge_curator/test_eligibility_actions.py`, `tests/test_forge_curator.py` | covered | Fixture-backed action tests cover section toggling, span eligibility writes, and annotation deletion refresh behavior; span accounting remains covered in pipeline/helper tests. |
| Roll evidence quote actions | TUI action scenario | `tests/forge_curator/test_curation_actions.py`, `tests/test_forge_curator.py` | covered | Fixture-backed tests cover single-quote writes, visual-mode cleanup, selection-start targeting, multi-save, deferred targets, and display-policy preservation; persistence cleanup helpers use stable synthetic data. |
| Source-roll assignment | TUI action scenario | `tests/forge_curator/test_curation_actions.py`, `tests/forge_curator/test_roll_read_model.py`, `tests/forge_curator/test_pickers.py` | covered | Fixture-backed action/read-model/picker coverage exists for open targets, deferred predicted targets, deferred source evidence copying, source-link row normalization, source assignment target rows, and keyboard traversal. |
| Deferral toggle and cross-chapter projection | TUI action/read model | `tests/forge_curator/test_curation_actions.py`, `tests/forge_curator/test_roll_read_model.py`, `tests/forge_curator/test_snapshot.py`, `tests/test_deferred_rolls.py` | covered | Fixture-backed action, snapshot, and read-model coverage exists for deferred predicted slot identity, deferred-row clearing, source deferral to the next chapter, explicit source-roll projection, same-chapter negative cases, deferred quote highlighting, and source projections; pipeline tests cover generated-data coherence. |
| Picker keyboard/focus behavior | TUI integration/unit | `tests/forge_curator/test_pickers.py` | covered | Fixture-backed tests cover SourceLinkPicker focus/traversal/confirm, ConstellationPicker digit chords, RollEvidencePicker labels/toggles/layout, RollVisualizationPicker choices, and PerkPicker keyboard toggles. |
| Snapshot save and ctrl-s binding | TUI integration | `tests/forge_curator/test_snapshot.py`, `tests/helpers/forge_curator_fixture.py` | covered | Fixture-backed tests assert the snapshot contract shape, Ctrl-S binding, and deferred predicted slot rows without live chapter prose. |
| Rebuild/reload/error handling after curation | TUI action scenario | `tests/forge_curator/test_error_handling.py` | covered | Fixture-backed tests cover malformed manual roll-overrides loading, write-failure rollback, full rebuild dispatch, undo refresh, successful reload, and failed derivation without reload. |
| Terminal compatibility checks | unit | `tests/test_forge_curator.py` | covered | Pure environment helper tests. |

## Web UI

| Feature | Layer | Current Tests | Status | Notes |
| --- | --- | --- | --- | --- |
| Data package contract helpers | unit | `tests/test_web_data_contract.py` | covered | Stable inline fixtures. |
| Visualization model helpers | unit | `tests/test_web_viz_model.py` | covered | Stable inline fixtures for marker model and constellation progress. |
| Staged site/package smoke | smoke/package | `tests/test_pages_smoke.py` | covered | Validates deployable package structure and path safety. |
| Browser app load and scrubber render | integration | `tests/test_web_app_integration.py` | covered | Uses synthetic runtime site fixture; skips cleanly when Playwright/Chromium unavailable. |
| Chapter selection details | integration | `tests/test_web_app_integration.py` | covered | Synthetic runtime fixture opens visible selected-chapter details. |
| Package selector URL behavior | integration | `tests/test_web_app_integration.py` | covered | Synthetic fixture covers non-default selection, default query removal, and invalid requested-package fallback. |
| Theme toggle | integration | `tests/test_web_app_integration.py` | covered | Synthetic runtime fixture verifies cycle behavior, document theme state, and local storage. |
| Zoom controls | integration | `tests/test_web_app_integration.py` | covered | Synthetic runtime fixture verifies zoom state, readout, detail token, and local storage. |
| Optional sky data handling | integration | `tests/test_web_app_integration.py`, `tests/helpers/web_runtime_site.py` | covered | Synthetic runtime fixture verifies the sky section stays hidden without optional wireframes and initializes when optional wireframes are present. |
| Scrubber keyboard and bookmark behavior | integration | `tests/test_web_app_integration.py` | covered | Synthetic browser fixture covers Arrow/Home/End movement, clamping, readout updates, bookmark persistence, restore, and reset. |
| Playback controls | integration | `tests/test_web_app_integration.py` | covered | Fixture-backed browser tests cover play/pause state, progress, speed persistence, and restart-from-end behavior. |
| Timeline drag interactions | integration | `tests/test_web_app_integration.py` | covered | Synthetic browser fixture drags the scrubber and asserts semantic word-position, readout, bookmark, and release state without pinning rendered pixels. |
| Roll tooltips and activation | integration | `tests/test_web_app_integration.py` | covered | Synthetic browser fixture covers hover details, normal click activation, touch-style pinning, and outside-click dismissal. |
| Rich track rendering semantics | integration/model | `tests/test_web_viz_model.py`, `tests/test_web_app_integration.py` | covered | Unit model coverage exists for marker basics; synthetic browser fixture covers POV classes, shadow bars, skipped markers, unknown/untracked/free/binary/trinary classes, and fallback display placement. |
| Current-position panels | integration | `tests/test_web_app_integration.py` | covered | Synthetic browser fixture covers pre-roll state, cumulative stats, constellation rows, recent acquisitions, selected-detail close, and clearing selected detail when moving to another chapter/end. |
| Web package/error edge cases | integration/unit | `tests/test_web_data_contract.py`, `tests/test_web_app_integration.py` | covered | Browser fixture covers invalid requested-package fallback, required-doc load errors, and malformed optional wireframes disabling sky without breaking the scrubber. |
| Sky controls | integration | `tests/test_web_app_integration.py` | covered | Synthetic browser fixture covers Focus/Art/Lines/Labels/Rotate state, persisted preferences, HUD/readout updates, and active roll focus. |

## Shared Maintenance

| Feature | Layer | Current Tests | Status | Notes |
| --- | --- | --- | --- | --- |
| Default verification gate | unit/smoke | `tests/test_verify_script.py` | covered | Verifies expected command sequence. |
| Test data isolation | guard | `tests/test_test_data_isolation.py` | covered | Protects against tests mutating live project data. |
| Evidence scorer | unit | `tests/test_evidence_scorer.py` | covered | Stable scorer fixtures. |

## Next High-Value Slices

1. Periodically audit legacy broad TUI smoke tests and generated-data
   coherence checks to keep them from growing into curated-data shape
   locks.
2. Evaluate whether source coverage adds useful signal after the
   feature-level inventory stays green across normal development.
