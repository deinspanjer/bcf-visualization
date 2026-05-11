# Forge Curator

- Run Python commands through the project virtual environment, for example
  `.venv/bin/python` and `.venv/bin/pytest`.
- Use pytest for Python test execution and new Python tests.
- Derived JSON is the single source of truth for `forge_curator`.
- TUI code must not reconcile, reinterpret, clamp, or synthesize roll, word, or accounting facts except for direct display formatting.
- If derived facts disagree, fix the derivation pipeline and schema, then regenerate data.
- Tests must assert semantic invariants of the model, not UI symptoms.
- When testing Forge Curator stats, prefer helper/data semantics
  (predicted vs curated roll vs curated evidence positions, raw/effective
  discrepancy flags, manifest-derived expectations) over rendered text,
  formatted numbers, or snapshot-like UI copy.
- Do not pin package dates, latest chapter numbers, release tags, or
  other time-coupled generated-data literals in tests when the expected
  value can be derived from current generated JSON.
- Do not promise future process behavior in chat unless it is recorded in durable project instructions or implemented immediately.
- If the user asks you to look at a Forge Curator TUI snapshot, load
  `data/manual/.forge_curator_snapshot.json`; F12 in the TUI overwrites that
  fixed snapshot file with the current state.
