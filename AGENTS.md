# Forge Curator

- Run Python commands through the project virtual environment, for example
  `.venv/bin/python` and `.venv/bin/pytest`.
- If `.venv/bin/python` is missing, bootstrap it with
  `python3.12 -m venv .venv` when available, otherwise `python3 -m venv .venv`,
  then run `.venv/bin/python -m pip install -e '.[dev]'`.
  `pyproject.toml` is the dependency source of truth; do not add
  `requirements*.txt` files or install dependencies from a second manifest.
- Hydrate ignored generated data before running tests that read
  `data/derived/*.json`: prefer `.venv/bin/python scripts/data_release.py
  download-dev` for a fresh checkout, or use the Codex local environment's
  worktree-copy fast path when it succeeds.
- Regenerate generated data through the dependency-aware pipeline wrapper.
  For normal data regeneration after curation or derivation changes, run
  `.venv/bin/python scripts/pipeline.py --target data`; add `--force` when a
  full rebuild is needed. Manual one-off scripts such as `parse_rolls.py`,
  `derive_roll_outcomes.py`, `derive_roll_facts.py`, and
  `build_chapter_facts.py` are acceptable only for focused investigation, and
  should not be treated as the final regeneration path.
- Use pytest for Python test execution and new Python tests.
- Before reporting code, test, or generated-data changes as complete, run
  `.venv/bin/python scripts/verify.py`. If that command cannot be run, report
  exactly what was run instead and why the full verification gate was skipped.
- Derived JSON is the single source of truth for `forge_curator`.
- TUI code must not reconcile, reinterpret, clamp, or synthesize roll, word, or accounting facts except for direct display formatting.
- If derived facts disagree, fix the derivation pipeline and schema, then regenerate data.
- When refactoring a data model or source-of-truth path, remove obsolete fields, files, actions, tests, and compatibility shims in the same change unless a real external contract requires a transition. Do not preserve dead code or empty generated fields just to avoid touching call sites.
- Before changing any data model, generated JSON contract, accounting
  semantics, roll/source identity, or source-of-truth path, ask an explorer
  subagent to review the existing code, schemas, tests, and docs for an
  already-suitable contract. If the subagent has high confidence that an
  existing contract covers the need, adapt the plan to use that contract. If
  the subagent has low confidence or finds no suitable contract, provide the
  user with a brief proposal for the data-model change and wait for approval
  before implementing it.
- When implementing a supplied plan, convert the plan into an acceptance
  matrix before coding and keep it current through final verification. Before
  reporting completion, every plan requirement must be marked implemented,
  intentionally changed with the reason, or not done; for requirements that
  say to remove, retire, collapse, or replace behavior, also audit the
  obsolete terms/actions/tests and remove or explicitly justify every
  remaining reference.
- Tests must assert semantic invariants of the model, not UI symptoms.
- Before adding or materially changing tests, read the project-specific
  testing pattern in `DEVELOPERS.md` under `Testing Design Pattern`.
  This section is the canonical progressive-disclosure guidance for test
  layer boundaries, stable fixtures, web UI tests, and feature-level
  coverage expectations.
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
