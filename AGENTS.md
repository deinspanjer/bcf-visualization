# Forge Curator

- Run Python commands through the project virtual environment, for example
  `.venv/bin/python` and `.venv/bin/pytest`.
- Use pytest for Python test execution and new Python tests.
- Before reporting code, test, or generated-data changes as complete, run
  `.venv/bin/python scripts/verify.py`. If that command cannot be run, report
  exactly what was run instead and why the full verification gate was skipped.
- Derived JSON is the single source of truth for `forge_curator`.
- TUI code must not reconcile, reinterpret, clamp, or synthesize roll, word, or accounting facts except for direct display formatting.
- If derived facts disagree, fix the derivation pipeline and schema, then regenerate data.
- Tests must assert semantic invariants of the model, not UI symptoms.
- Before reporting a change as complete, self-review any tests you added or
  materially changed. Each such test should protect a meaningful behavior,
  data contract, or model invariant, not merely pin the implementation shape
  just written.
- Prefer tests that would fail for a real regression and survive reasonable
  refactors. If a test would fail after an equivalent implementation change,
  rewrite it around observable behavior or domain semantics.
- Avoid tests that mainly pin literal formatting, incidental constants,
  rendered text, styling details, or UI copy unless that exact output is the
  documented product contract.
- When a change involves UI, separate visual styling contracts from rendering
  details. Prefer testing shared state, token flow, accessibility-relevant
  behavior, or documented interaction semantics before exact rendered text or
  styling literals.
- In the final response for any change that adds or materially changes tests,
  briefly state what behavior or invariant the tests protect.
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
