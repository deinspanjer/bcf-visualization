# Canonical CP / Word / Roll Accounting

**Status:** active, pre-implementation
**Driver:** parallel implementations of CP-eligible word counting + CP accumulation across the pipeline and the TUI have already started to drift. Consolidate to one canonical path; delete the duplicates.

## Goals

1. **One canonical CP-eligible word count per (chapter, section)**, computed by the pipeline. Subtracts: ineligible sections, author notes, manual header corrections, auto-detected section headers.
2. **One canonical banked-CP function** keyed on `(chapter_num, raw_word_offset)` — the simulator computes a per-chapter banked-CP table during `simulate_story` and exposes it. No re-derivation in the TUI.
3. **One canonical `predicted_rolls.json`** with roll positions at exact threshold-crossings, not at event boundaries.
4. **Curated overrides take priority** over auto-detection when both are present.

## Steps

### 1. Move auto-header detection into the pipeline

- `extract_chapter_sections.py` runs the same regex-based "first N words of each section match the section's `header` field" detection that `data_loader._detect_section_headers` does today.
- Per-section field added: `auto_header_word_count`.
- Output: `chapter_sections.json` carries `word_count`, `author_note_word_count`, `auto_header_word_count`.

### 2. Pipeline consumes manual header_corrections

- `_load_cp_words_per_chapter` reads `data/manual/header_corrections.json`.
- Subtracts manual header-span word ranges from the per-chapter total, after AN and auto-header.
- Manual entries override auto-detected ones at the same span (de-dup by overlap).

### 3. Simulator fires rolls at threshold-crossings

- `simulate_story` walks events and, between events, fires rolls at the exact word offset where banked CP crosses threshold.
- Math in cp×100 units; ceil-division to find crossing word; verify post-state against threshold.
- Shadow words still burn first.
- Output `predicted_rolls.json` will change position values across the dataset.

### 4. Simulator exposes canonical banked-CP lookup

- During `simulate_story`, build a per-chapter list of `(word_offset, banked_cp_x100)` checkpoints — one entry per event/roll firing within the chapter.
- New top-level field in `chapter_facts.json`: `cp_checkpoints: [{word, banked_cp}, ...]` per chapter.
- Helper: `cp_at_chapter_word(chapter_num, raw_word_offset) -> int` walks checkpoints + applies regime-rate accumulation between them. Single canonical implementation.

### 5. TUI consumes canonical outputs

- Delete `data_loader._detect_section_headers`. Read `auto_header_word_count` from the loaded chapter_sections data.
- Delete `app._cp_at_cursor`, `app._excluded_word_ranges`, `app._cp_earning_word_offset`. TUI calls `cp_at_chapter_word` and a sibling `cp_earning_word_offset(chapter_num, raw_word_offset)`.
- Stats panel pulls from canonical functions; gutter computes word indices the same way.

### 6. Tests

- Simulator: assert that re-running `predict_rolls.py` produces the same `predicted_rolls.json` regardless of acquisition placement (only chapter eligible word count and regime should affect roll positions).
- Pipeline: round-trip test that `_load_cp_words_per_chapter` totals match section sums after AN/header subtraction.
- TUI: cursor-CP-words and banked-CP at known positions match canonical functions.

## Order of operations

1. Step 1 (auto-header in pipeline) — produces new `chapter_sections.json` field. No behavior change in simulator yet.
2. Step 2 (manual header_corrections in pipeline) — `_load_cp_words_per_chapter` updates. Causes `predicted_rolls.json` to change for any chapter with header_corrections (currently empty file, so likely no-op in practice).
3. Step 3 (threshold-crossing) — large change to `predicted_rolls.json` positions. Validate solver still passes; expect curator/solver divergence count to shift.
4. Step 4 (cp_at_word canonical) — new helper, no removals yet.
5. Step 5 (TUI consumes; remove duplicates) — delete TUI's parallel logic.
6. Step 6 (tests) — update expected fixtures; add canonical-only tests.

## Out of scope

- Curated `word_position` overrides at simulator level (chapter_roll_overrides setting roll positions). Useful but a separate concern; the canonical positions from simulator are good first-pass and the override layer can refine them later.
- Performance: per-chapter checkpoint walks are O(rolls_in_chapter), trivial.

## Future open question — partially-eligible sections

Some non-MC-POV sections include scenes where the alt-POV is interacting with Joe directly (Joe is "on screen by name/cape"). The author's stated rule for CP earning was originally "Joe POV" but later clarification suggests "Joe on screen by name/cape" — meaning a portion of an otherwise-ineligible section may legitimately count for CP.

Today, sections are eligibility-binary (`counts_for_cp: true|false`). We have no schema for "the first 5k words of this 15k-word section count for CP, the rest don't."

**Don't pre-build this.** Wait until a real chapter surfaces as a problem (likely visible as an infeasible chapter the curator can pin to a known partial-POV section), then decide whether to add a `partial_eligibility` field, an `eligible_word_ranges` per section, or a different shape entirely.

For now, when investigating an infeasible chapter that involves a non-Joe-POV section, the curator should ask whether part of that section was actually Joe-on-screen and consider it as a candidate for this kind of refinement.
