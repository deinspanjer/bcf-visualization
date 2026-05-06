# Developer guide

## Architecture

The project is intentionally static:

- `data/raw/` contains local source material such as MHT exports,
  spreadsheets, and optional EPUBs.
- `data/manual/` contains curated inputs and overrides.
- `data/derived/` contains committed JSON outputs and matching schemas.
- `scripts/` contains parser, enrichment, validation, and chart scripts.
- `web/` contains the dependency-free visualization.

The web app should consume structured derived data. Keep prose parsing,
classification, and cross-source reconciliation in scripts so the
runtime stays pure and inspectable.

The parked Phase 4 circle-sky prototype is still dependency-free and
query-gated behind `/web/?sky=1`. It renders to `#sky-canvas` with
Canvas 2D, using:

- `chapter_facts.json` for chapter state and scrubber integration.
- `constellation_wireframes.json` for cluster and jump geometry.
- `roll_facts.json` for curated roll order, hit/miss outcome, banked
  CP, and grab-cost context.

Keep it out of the default `/web/` experience until the planetarium
layout direction is settled.

## Regenerate derived data

Use a virtual environment when available. If not in a venv, use
`python3`.

Typical full regeneration order:

```sh
python3 scripts/parse_threadmarks.py
python3 scripts/parse_rolls.py
python3 scripts/parse_reference.py
python3 scripts/extract_chapter_sections.py
python3 scripts/build_section_classifications.py
python3 scripts/build_perk_directory.py
python3 scripts/predict_rolls.py
python3 scripts/extract_last_edited.py
python3 scripts/find_roll_locations.py
python3 scripts/find_text_backed_rolls.py
python3 scripts/validate_roll_locations.py
python3 scripts/derive_roll_outcomes.py
python3 scripts/derive_roll_facts.py
python3 scripts/build_chapter_facts.py
python3 scripts/spot_check.py
python3 scripts/make_charts.py
```

Each derived JSON file should validate against its schema before being
written. Structural drift should fail loudly.

## Web app checks

For JavaScript syntax:

```sh
node --check web/app.js
```

For whitespace/conflict issues before committing:

```sh
git diff --check -- web/index.html web/app.js web/style.css
```

Serve locally with:

```sh
python3 -m http.server 8001
```

Then open <http://127.0.0.1:8001/web/>.

## Documentation placement rules

- `README.md`: high-level project description, source material,
  capability summary, and links to deeper docs.
- `USERS.md`: runtime behavior, startup, UI controls, troubleshooting,
  and operator workflows.
- `DEVELOPERS.md`: architecture, local setup, data regeneration,
  testing, implementation notes, and documentation rules.
- `TODO.md`: future work, known gaps, deferred design questions, and
  follow-up research.

Change-driven update matrix:

- New or changed runtime behavior: update `USERS.md`.
- New major capability: update `README.md`, `USERS.md`, and
  `DEVELOPERS.md`; add follow-ups to `TODO.md` if needed.
- New derived artifact or script: update `README.md` and
  `DEVELOPERS.md`.
- Internal refactor with no user impact: update `DEVELOPERS.md` only if
  it affects future maintenance.
- Deferred work or open design question: update `TODO.md`.

## Implementation notes

- Keep `chapter_facts.json` as the web app's backbone unless there is a
  strong reason to split runtime data again.
- Store reusable domain logic in scripts, not in `web/app.js`.
- Do not rely on raw EPUB prose at runtime.
- When adding user-facing track encodings, update both the legend and
  `USERS.md`.

## Roadmap: local NLP extraction

A model-based extraction layer is being planned to replace the
regex-heavy parts of the current pipeline (event detection in
`find_text_backed_rolls.py`, POV classification in
`build_section_classifications.py`) and to add new derivations
(in-world dates, Joe-on-screen flags, time-mode classification).

Architecture: a llama.cpp labeling-assistant lane plus two fine-tuned
encoder models (span extractor + section classifier) served from a
FastAPI process on a local GPU box, with iMac-side scripts calling the
endpoints over LAN. The existing deterministic parsers stay in place
as fallbacks; the new layer is additive.

**Phase 0 status: scaffolded.** The `nlp/` package, FastAPI server,
client wrapper, smoke test, and Windows setup scripts are in place.
`/health` and `/version` work on a fresh checkout; `/extract` and
`/classify_section` return 503 with the documented
`*_model_not_loaded` body until trained checkpoints exist. Run
`python3 -m pytest tests/` to exercise the scaffold without a GPU.
For the operator workflow (Windows install, smoke test, what to do
when a check fails), see the runbook below.

Reference docs:

- Operator runbook (Phase 0): [docs/local_nlp_runbook.md](docs/local_nlp_runbook.md)
- Feasibility study: [docs/local_nlp_research.md](docs/local_nlp_research.md)
- Master plan: [docs/local_nlp_plan.md](docs/local_nlp_plan.md)
- Companion docs: [label schema](docs/local_nlp_label_schema.md),
  [setup](docs/local_nlp_setup.md),
  [annotation playbook](docs/local_nlp_annotation_playbook.md),
  [training](docs/local_nlp_training.md),
  [serving](docs/local_nlp_serving.md)
- Phased build tasks tracked in [TODO.md](TODO.md).
