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
pipeline:

```sh
python3.12 -m venv .venv  # use python3 if python3.12 is unavailable
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

`pyproject.toml` is the only Python dependency manifest. Runtime
dependencies live in `[project].dependencies`; development/test
dependencies live in `[project.optional-dependencies].dev`. Do not add
or use `requirements*.txt` files for this repo.

Typical full regeneration order:

```sh
.venv/bin/python scripts/parse_chapters.py
.venv/bin/python scripts/parse_rolls.py
.venv/bin/python scripts/parse_reference.py
.venv/bin/python scripts/extract_chapter_sections.py
.venv/bin/python scripts/seed_chapter_publication_dates.py
.venv/bin/python scripts/build_section_classifications.py
.venv/bin/python scripts/build_perk_directory.py
.venv/bin/python scripts/predict_rolls.py
.venv/bin/python scripts/find_roll_locations.py
.venv/bin/python scripts/find_text_backed_rolls.py
.venv/bin/python scripts/validate_roll_locations.py
.venv/bin/python scripts/derive_roll_outcomes.py
.venv/bin/python scripts/derive_roll_facts.py
.venv/bin/python scripts/build_chapter_facts.py
.venv/bin/python scripts/build_visualization_facts.py
.venv/bin/python scripts/spot_check.py
.venv/bin/python scripts/make_charts.py
```

`parse_chapters.py` parses the EPUB navigation document for the chapter
list (number, ordinal, title, href, exact word count). `data/raw/`
holds the EPUB plus the AO3 navigate page; the SV threadmark scrape is
no longer part of the pipeline.

### Rebuild constellation assets

After editing any `data/constellations/<slug>/current.svg` or
`metadata.json` (hand-authored inputs), regenerate the derived
lifecycle, wireframe JSON, web bundle, and per-cluster HTML pages with:

```sh
scripts/rebuild_constellation_assets.sh
```

This is the canonical entry point: the per-cluster pages and the
top-level index under `data/constellations/` are generated artifacts
and will be overwritten. `current.svg` and `metadata.json` are never
written by the rebuild.

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
.venv/bin/python scripts/data_release.py manifest --date YYYYMMDD --build-number N
```

Hydrate a fresh checkout from the validated maintainer bundle before
running Forge Curator, data-invariant tests, or release packaging:

```sh
.venv/bin/python scripts/data_release.py download-dev
```

`download-dev` stores the downloaded dev-bundle manifest separately as
`data/derived/_dev_data_package.json` and writes `data_package.json` as
the local runtime manifest consumed by the browser and tests. Check for
mixed or stale local generated data with:

```sh
.venv/bin/python scripts/data_release.py check-derived
```

Codex app environments hydrate data during setup. The local environment
first tries to copy the EPUB and top-level generated JSON from another
registered worktree, then falls back to downloading the EPUB and the
maintainer dev bundle. The cloud environment downloads the EPUB and the
maintainer dev bundle directly. The deployed Pages runtime package is
not sufficient for local tests because it only contains web runtime
entrypoints.

Build release assets from the current derived data:

```sh
.venv/bin/python scripts/data_release.py package \
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
.venv/bin/python scripts/data_release.py download-dev
```

To hydrate from a specific pinned bundle:

```sh
.venv/bin/python scripts/data_release.py download-dev \
  --tag bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER \
  --asset bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER.tar.gz
```

To dry-run old data-release cleanup:

```sh
.venv/bin/python scripts/data_release.py cleanup \
  --keep-tag bcf-visualization-data-vYYYYMMDD.N-chORDINAL-CHAPTER
```

Cleanup protects release tags referenced by workflow defaults and the
deployed Pages `data/packages.json` by default. Add `--delete` only
after reviewing the dry-run output; release assets are immutable and
should be replaced by publishing a new release, not by editing an
existing one.

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

## Testing Design Pattern

The project test surface should be organized by feature and layer. Tests
should protect observable behavior, data contracts, and model invariants
rather than freezing the current curated story data shape or the exact
implementation structure used to produce it.

Aim for complete feature-level coverage across the data pipeline, Forge
Curator TUI, web UI, package/release checks, and shared domain helpers.
Source and line coverage targets should be evaluated separately after the
feature inventory is clear; high source coverage is useful only when the
tests still describe meaningful behavior.

Use these layers:

- Unit tests cover pure functions, small domain helpers, web formatters,
  reducers, render-model builders, and other isolated logic. Fixtures
  should be minimal, explicit, and local to the behavior under test.
- Data pipeline scenario tests create a small prerequisite fixture,
  mutate manual curation data or source data, run the relevant derivation
  stage, and assert that the derived output satisfies the required
  contract. They should not depend on live chapter counts, live curated
  roll order, or incidental current-story details.
- Forge Curator TUI tests cover how `ForgeCuratorApp` reads its inputs,
  presents state to actions, writes manual curation data, invokes the
  appropriate derivation or reload path, and handles errors. They should
  use stable fixtures and should not re-test the data pipeline behavior
  already covered by pipeline scenario tests.
- Web UI unit tests cover web-specific logic with stable fixtures:
  filtering, state transitions, formatters, derived view models, and
  interaction helpers.
- Web UI integration tests load the app against purpose-built runtime
  fixture data and verify user-visible feature behavior. They must not
  rely on the current curated data shape, latest chapter count, exact
  story roll sequence, or other time-coupled generated literals.
- Coherence, smoke, and package tests may read the current generated data,
  but only to verify schema validity, manifest consistency, path safety,
  package completeness, and other global contracts. They should derive
  expectations from the generated JSON instead of pinning exact current
  chapter rows, release dates, tags, or latest chapter numbers.

Every scenario-style test should make its prerequisite state, mutation,
and expected output requirement obvious. Prefer fixture builders when the
same domain setup is needed by multiple tests, but keep each test's
behavioral premise visible at the call site.

Review new tests as production code. A good test should make clear what
real regression it would catch and why that regression matters. Avoid
assertions that simply mirror the implementation just written; constants,
string literals, formatting, and layout details should only be pinned when
they are part of an explicit compatibility or product contract.

UI tests should separate product behavior from rendering details. Prefer
asserting shared state, action effects, accessibility-relevant behavior,
token flow, or documented interaction semantics before exact rendered
text or styling. If exact UI copy or layout must be tested, keep that
assertion narrow and pair it with a semantic assertion that explains the
behavior it protects.

Before handoff for any change that adds or materially changes tests,
summarize the protected behavior, data contract, or invariant. Do not
describe the tests merely as coverage for the edited function or constant.

The active cleanup roadmap lives in
[docs/test_surface_cleanup_plan.md](docs/test_surface_cleanup_plan.md).
The feature-to-test checklist lives in
[docs/test_feature_inventory.md](docs/test_feature_inventory.md). Use
those documents to track feature-level coverage gaps and to break large
test refactors into layer-specific slices.

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

## Verification

Before reporting a curation, data-flow, or static visualization change
as complete, run the default repo verification gate:

```sh
.venv/bin/python scripts/verify.py
```
