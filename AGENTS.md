# Forge Curator

- Run Python commands through the project virtual environment, for example
  `.venv/bin/python` and `.venv/bin/pytest`.
- Use pytest for Python test execution and new Python tests.
- Derived JSON is the single source of truth for `forge_curator`.
- TUI code must not reconcile, reinterpret, clamp, or synthesize roll, word, or accounting facts except for direct display formatting.
- If derived facts disagree, fix the derivation pipeline and schema, then regenerate data.
- Tests must assert semantic invariants of the model, not UI symptoms.
- Do not promise future process behavior in chat unless it is recorded in durable project instructions or implemented immediately.
