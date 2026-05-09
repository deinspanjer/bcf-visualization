# Developer guide

## Architecture

The project is intentionally static:

- `data/raw/` contains local source material such as MHT exports,
  spreadsheets, and optional EPUBs.
- `data/manual/` contains curated inputs and overrides.
- `data/derived/` contains generated JSON outputs after bootstrap or
  regeneration, plus committed schemas in `data/derived/_schemas/`.
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
- `roll_facts.json` via `chapter_facts.json` for curated roll order,
  hit/miss outcome, banked CP, deferred mention/display coordinates,
  and grab-cost context.

Keep it out of the default `/web/` experience until the planetarium
layout direction is settled.

## Regenerate derived data

Run project Python commands through the checked-out virtual environment:
use `.venv/bin/python` for scripts and `.venv/bin/pytest` for tests.
If `.venv` has not been created yet, create/sync it before running the
pipeline.

Typical full regeneration order:

```sh
.venv/bin/python scripts/parse_threadmarks.py
.venv/bin/python scripts/parse_rolls.py
.venv/bin/python scripts/parse_reference.py
.venv/bin/python scripts/extract_chapter_sections.py
.venv/bin/python scripts/build_section_classifications.py
.venv/bin/python scripts/build_perk_directory.py
.venv/bin/python scripts/predict_rolls.py
.venv/bin/python scripts/extract_last_edited.py
.venv/bin/python scripts/find_roll_locations.py
.venv/bin/python scripts/find_text_backed_rolls.py
.venv/bin/python scripts/validate_roll_locations.py
.venv/bin/python scripts/derive_roll_resolutions.py
.venv/bin/python scripts/derive_roll_outcomes.py
.venv/bin/python scripts/derive_roll_facts.py
.venv/bin/python scripts/build_chapter_facts.py
.venv/bin/python scripts/spot_check.py
.venv/bin/python scripts/make_charts.py
```

Each derived JSON file should validate against its schema before being
written. Structural drift should fail loudly.

## Versioned data packages

Top-level `data/derived/*.json` files are generated data and are
distributed through versioned release bundles. The files may exist in a
local checkout after bootstrap or regeneration, but they are ignored by
Git. Release and Pages tooling treats runtime data as a versioned
contract package.
The browser loads `data_package.json` before `chapter_facts.json` and
rejects unsupported contract versions instead of attempting local
fallback reconciliation.

Refresh the local runtime manifest after regenerating web-consumed data:

```sh
python3 scripts/data_release.py manifest --date YYYYMMDD --build-number N
```

Hydrate a fresh checkout from the validated maintainer bundle before
running Forge Curator, data-invariant tests, or release packaging:

```sh
python3 scripts/data_release.py download-dev \
  --tag bcf-visualization-data-v20260509.3-ch194-120.1 \
  --asset bcf-visualization-data-v20260509.3-ch194-120.1.tar.gz
```

Build release assets from the current derived data:

```sh
python3 scripts/data_release.py package \
  --date YYYYMMDD \
  --build-number N \
  --output-dir dist/data-packages
```

The GitHub `Build data release` workflow hydrates from the latest
validated maintainer bundle when needed, then regenerates the roll facts
and chapter facts from committed manual inputs before packaging by
default. Use the workflow's `regenerate=false` input only when you
intentionally want to republish exactly hydrated derived data.

The package command writes two assets:

- `bcf-visualization-runtime-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz`:
  minimal browser payload.
- `bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz`:
  full top-level derived JSON set for maintainer bootstrap.

The matching GitHub Release tag uses the shared data-package identity:

```text
bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER
```

`YYYYMMDD.N` is the build date and build ordinal. `ORDINAL` is the
current BCF fiction chapter count in `chapter_facts.json`; `CHAPTER` is
the latest descriptive chapter number, such as `120.1`. The same fields
are stored in `data_package.json`, copied into `data/packages.json`, and
shown by the web app as the visible data version.

Draft releases are useful for inspecting assets but are not deployable
through the Pages workflow's normal `GITHUB_TOKEN` release download.
Publish the release before using it as a pinned Pages bundle.

To hydrate a fresh checkout from a maintainer bundle:

```sh
python3 scripts/data_release.py download-dev \
  --tag bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER \
  --asset bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz
```

To dry-run old data-release cleanup:

```sh
python3 scripts/data_release.py cleanup \
  --keep-tag bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER
```

Add `--yes` only after reviewing the dry-run output. Do not rewrite
history for derived JSON until this release-backed workflow has been
stable long enough to justify a coordinated migration.

Roll data flow is intentionally layered: `predicted_rolls.json` is the
mechanical threshold-crossing schedule, `chapter_roll_overrides.json`
is manual curation keyed by mechanical chapter, `roll_facts.json`
resolves outcome/accounting/deferral/display fields, and
`chapter_facts.json` is the runtime backbone. Fix disagreements in
that derivation path, not in the web app or Forge Curator display code.
Forge Curator may write manual inputs, but its stats, roll navigation,
CP accounting, and hit/miss/perk/evidence display must render from
regenerated derived JSON rather than overlaying manual edits directly.

## Web app checks

For JavaScript syntax:

```sh
node --check web/app.js
node --check web/data-contract.js
```

For whitespace/conflict issues before committing:

```sh
git diff --check -- web/index.html web/app.js web/style.css
```

Serve locally with:

```sh
.venv/bin/python -m http.server 8001
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
`*_model_not_loaded` body until trained checkpoints exist. Use pytest
for new verification. Run the full suite with `.venv/bin/pytest`, or a
focused module with `.venv/bin/pytest tests/<module>.py`.
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
