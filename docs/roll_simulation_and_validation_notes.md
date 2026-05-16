# Roll Simulation And Validation Notes

## Model Grain

- `data/derived/predicted_rolls.json` is the mechanical schedule: one row per CP threshold crossing. Rows carry `roll_number`, mechanical `chapter_num`, global `word_position`, `cp_rule_regime`, and `roll_trigger_cp_threshold`.
- `data/manual/chapter_roll_overrides.json` is keyed by mechanical chapter. It records curated roll outcomes, grouped perks, evidence text, and optional deferral/display metadata.
- `data/derived/roll_facts.json` is the canonical roll-result stream. Its `chapter_num` is the narration/listing owner, while `mechanical_chapter_num` keeps the predicted slot used for CP scheduling and validation.
- `data/derived/chapter_facts.json` embeds `roll_facts` for runtime use. Consumers should not rejoin predictions to perks themselves.

Deferred rolls are modeled as one mechanical predicted slot plus one narrated/listed roll fact. `mention_chapter_num` says where the author narrates or lists the result; `display_position_policy` selects whether visualization uses the mention, the mechanical slot, or the start of the mention chapter.

## Pipeline

1. `scripts/predict_rolls.py` simulates CP accumulation across the documented rule regimes and writes `predicted_rolls.json`.
2. `scripts/derive_roll_outcomes.py` creates fallback hit/miss rows for chapters without curator coverage.
3. `scripts/derive_roll_facts.py` merges curator rows, manual chapter-roll overrides, fallback rows, predicted slots, and scheduler accounting into `roll_facts.json` plus `roll_validation.json`.
4. `scripts/build_chapter_facts.py` groups canonical roll facts by narration/listing chapter and embeds them into `chapter_facts.json`.

`scripts/find_roll_locations.py` and `scripts/find_text_backed_rolls.py` support evidence discovery. They are not the canonical source for roll ownership or accounting.

## Validation Rules

- Predicted-slot capacity is counted by `mechanical_chapter_num`.
- CP feasibility debits hits at the mechanical predicted slot, even when narration is deferred.
- Perk counters and chapter-owned roll lists follow the narration/listing chapter.
- Existing `word_position` and `cumulative_word_offset` in `roll_facts.json` are display coordinates. Use `mechanical_*` for accounting diagnostics.

Historical soft findings included catalog gaps, occasional cost disagreements, naming variants, and chapter-level mismatch counts in overlap ranges. Current reconciliation should fix the derivation pipeline and schemas first, regenerate derived data, then update the TUI or visualization only as display consumers.
