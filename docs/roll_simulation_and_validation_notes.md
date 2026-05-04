# Roll simulation and validation notes

## Simulation pipeline

- `scripts/predict_rolls.py` models CP accumulation and roll timing across the documented rule regimes.
- It uses derived section-level CP-earning word counts and known acquisition data to estimate roll offsets.

## Evidence extraction pipeline

- `scripts/find_roll_locations.py` generates candidate prose windows near predicted roll positions.
- `scripts/find_text_backed_rolls.py` identifies text-backed roll/acquisition evidence.

## Validation pipeline

- `scripts/validate_roll_locations.py` compares predictions/evidence against chapter-level facts.
- Outputs land in `data/derived/roll_locations_validation.json` and are used to track coverage/discrepancies.

## Spot-check context

Historical soft findings included catalog gaps, occasional cost disagreements, naming variants, and small chapter-level mismatch counts in overlap ranges.
For current reconciliation work, use `TODO.md`.
