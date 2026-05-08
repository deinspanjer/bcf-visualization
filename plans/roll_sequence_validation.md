# Roll Sequence Validation & Carousel Data

**Status:** active, pre-implementation
**Owner:** orchestrator + delegated subagents
**Out of scope:** the carousel UI itself, sky-view rework

## Goals

1. **Validate** that the recorded sequence of Forge rolls (hits and misses) is internally consistent: at no point does available CP go negative, and every recorded hit fits in a roll slot whose pre-debit available CP ≥ the perk's cost.
2. **Reconstruct** the per-roll outcome for chapters past the curator's coverage (76+) by constraint-propagating recorded hits against predicted-roll slots — interleaving the right number of misses to make CP arithmetic work.
3. **Triage**: surface any chapter where no feasible assignment exists, with a diagnostic suggesting the most likely cause (regime/section misclassification, hit order, cost typo).
4. **Emit a carousel-ready ordered roll list** driven by `(chapter_num, word_position)`.

## Background

Per-chapter constraint structure: each chapter has K predicted rolls (from `predict_rolls.py`) with deterministic per-roll word offsets and pre-debit `available_cp`. The chapter records N paid hits in curator order with costs. The unknowns are which K-N slots are misses. A feasible assignment exists iff the hits in order can be placed at K monotonically-increasing slot indices such that, at each chosen slot, available CP (after debiting earlier-assigned hits and accumulating word-based earnings) ≥ the hit's cost.

Free perks attach to their parent paid hit's slot and do not consume separate slots. Chapters 1–75 are curator-recorded; chapters 76+ are interpolated.

A prior recon found 39 hit rows where `purchased_perk_cost > available_cp`. All 39 are interpolated rows; root cause is `derive_roll_facts.py` lines ~364, 396 stamping `available_cp = cp_threshold` (the regime trigger amount, 100 or 200) instead of true pre-debit CP. Step 1 fixes this.

## Decisions

- Single-script extension of existing `derive_roll_facts.py` (and supporting scripts), no new pipeline binary.
- Misses with unknown constellation stay `constellation: null`. Carousel renders fuzzy. Hand-curated overrides land in `data/manual/roll_overrides.json`.
- Carousel cue: per-roll word position.
- Scheduler canonical pick: **latest-feasible per hit** — among feasible assignments, choose the one where each hit's slot index is the latest possible. Deterministic, reflects "spend when forced."
- **Shared regime simulator module**: extract `scripts/regime_simulator.py` consumed by both `predict_rolls.py` and `derive_roll_outcomes.py`. Single source of truth, prevents future drift.
- Solver implementation: small backtracking solver; ≤10 rolls per chapter makes exhaustive search trivial. No CSP library needed.

## Steps

### Step 1 — Real `available_cp` on interpolated rolls

**Problem:** `derive_roll_facts.py` interpolated path uses `cp_threshold` as `available_cp`, which is wrong.

**Tasks:**

1. Extract a shared regime simulator module from `scripts/predict_rolls.py`'s `_simulate()` and word-bookkeeping helpers. New file: `scripts/regime_simulator.py`. Public API:
   - `simulate_chapter_rolls(chapter_facts, regime, banked_cp_in, hits_in_chapter)` → list of `{roll_idx, chapter_num, word_position, available_cp_pre_debit, banked_cp_post_debit}`. Pure function, no I/O.
   - `accumulate_cp(words, regime, banked_cp_in, shadow_state)` → `(banked_cp_out, new_shadow_state)`. Word-to-CP arithmetic, regime-aware (incl. regime-3 shadow words for 600/800 CP perks).
2. Refactor `scripts/predict_rolls.py` to import from the new module. Behavior must be byte-identical: re-running it produces the same `predicted_rolls.json` (verify with diff).
3. Update `scripts/derive_roll_outcomes.py` (and/or `derive_roll_facts.py` interpolated path) to use the shared module so interpolated rows carry true `available_cp` and `banked_cp_after_roll`.
4. Re-derive `data/derived/roll_facts.json`.

**Verification:**

- `predicted_rolls.json` byte-identical before and after refactor.
- Count of rows where `outcome == "hit"` AND `purchased_perk_cost > available_cp` drops from 39 to either 0 or whatever is left over after the labeling fix (any residual is a real-data finding for Step 2 to surface).
- All existing tests under `tests/` pass.

### Step 2 — Per-chapter scheduler

New module `scripts/roll_scheduler.py`. Pure function:

```
schedule_chapter(predicted_rolls, hits_in_curator_order, banked_cp_in, regime)
  → { feasible: bool, assignments: [{roll_idx, hit_index_or_None, ...}], slack: int, ambiguity: int, diagnostic: str }
```

**Algorithm (backtracking):**

For each chapter:
- Compute per-slot pre-debit available_cp assuming no in-chapter hits (linear word-based CP accumulation from banked_cp_in).
- Place hits via DFS over slot indices; at each placement, recompute remaining slots' available_cp accounting for the assigned hit's debit at its word offset.
- Latest-feasible pick: try slot indices in descending order during DFS so the first solution found has each hit at its latest slot.
- Track `slack` = sum across hits of `(available_cp_at_slot - cost)` for the assignment (lower = tighter).
- Track `ambiguity` = count of distinct feasible assignments (cap at 50; we only care if it's >1).
- If no feasible assignment exists, emit `feasible: false` and a diagnostic string (see Step 3).

**Integration:**

In `derive_roll_facts.py`, after merging curator + interpolated rows:
- For chapters 1–75 (curator coverage): still run scheduler; cross-check vs. curator's recorded outcomes. Curator wins. Any divergence → soft warning into validation report.
- For chapters 76+: scheduler decides outcomes. Solver-assigned hits get `outcome: "hit"`, `purchased_perk_name`, `purchased_perk_cost` populated; non-hit slots get `outcome: "miss"`, `constellation: null` (unless an override applies).
- New per-row field: `slot_source ∈ { "curator", "solver", "override" }`.

### Step 3 — Validation report

Write `data/derived/roll_validation.json`:

```json
{
  "_generated": "...",
  "_source": "scripts/derive_roll_facts.py",
  "summary": { "chapters_total": N, "feasible": N, "infeasible": N, "curator_divergences": N, "ambiguous": N },
  "infeasible": [
    {
      "chapter_num": 87,
      "banked_cp_in": 350,
      "predicted_rolls": [...],
      "recorded_hits": [...],
      "diagnostic": "regime_or_section_misclassification",
      "explanation": "Chapter has 3 predicted rolls but 4 recorded paid hits. Predicted CP earnings short by ~200."
    }
  ],
  "curator_solver_divergences": [...],
  "ambiguous_chapters": [...],
  "miss_constellation_unsatisfiable": [...]
}
```

Diagnostic priority:
1. `regime_or_section_misclassification` — fewer predicted slots than required hits, or required CP earnings exceed predicted.
2. `hit_order_inconsistency` — feasible only if the curator's hit order is wrong (a permutation works).
3. `cost_typo_suspected` — single hit's cost doesn't match `obtained_perks.json` join.
4. `general_infeasible` — none of the above.

Pipeline exits non-zero on any infeasible chapter.

### Step 4 — Hand-curation override hook

Create empty stub `data/manual/roll_overrides.json`:

```json
{
  "_purpose": "Hand-curated overrides applied after solver, before validation. See plans/roll_sequence_validation.md.",
  "roll_overrides": {},
  "chapter_overrides": {}
}
```

`roll_overrides` keys are `roll_key` strings; value patches an individual row.
`chapter_overrides` keys are `chapter_num` strings; value either marks `skip_solver: true` and provides a hand-curated row list, or supplies a known-good banked_cp_in to override the simulator's value.

`derive_roll_facts.py` applies overrides as a final pass before writing roll_facts.json and before validation. Overridden rows get `slot_source: "override"`.

### Step 5 — Carousel schema confirmation

Verify each row in `roll_facts.json` has:

- `roll_key`, `roll_number`, `chapter_num`, `word_position` (chapter-local) and `cumulative_word_offset` (story-global; add if missing)
- `outcome` ∈ `{"hit", "miss"}`, `constellation` (nullable string)
- `purchased_perk_name`, `purchased_perk_cost` for hits
- `available_cp` (pre-debit), `banked_cp_after_roll` (post-debit)
- `slot_source`
- `free_perks[]`

If `cumulative_word_offset` is missing, derive from `predicted_rolls.json` and add it.

## Files

- New: `scripts/regime_simulator.py`, `scripts/roll_scheduler.py`, `data/manual/roll_overrides.json`
- Modified: `scripts/predict_rolls.py`, `scripts/derive_roll_outcomes.py`, `scripts/derive_roll_facts.py`
- Re-derived: `data/derived/roll_facts.json` (and possibly `data/derived/roll_outcomes.json`)
- New output: `data/derived/roll_validation.json`

## End-to-end verification

1. Re-run the data pipeline cleanly. All scripts exit zero, OR exit non-zero only with infeasible chapters listed in `roll_validation.json`.
2. `tests/` passes.
3. `predicted_rolls.json` is byte-identical to before the refactor.
4. Zero `outcome == "hit"` rows where `purchased_perk_cost > available_cp`.
5. `web/app.js` still loads `roll_facts.json` without schema regressions.
6. Spot-check 3 chapters in 76+: their solver-assigned hits should land at slots with sufficient CP and the slot order should be plausible.

## Out of scope

- Carousel UI implementation.
- Inferring constellation for the 106 unknown-constellation misses (stay null, render fuzzy).
- Sky view 3D renderer rework (deferred to a separate-mode polish later).
