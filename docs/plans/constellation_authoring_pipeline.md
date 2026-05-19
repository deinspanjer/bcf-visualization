# Constellation authoring pipeline plan (revised)

Status: revised after three adversarial reviews and user adjudication.
Awaiting one more focused review pass + sign-off before execution.

## Adjudicated decisions (locked)

These were the open questions after the first review round. They are
now locked.

1. **Slot 13/14 timing.** Both Capstone and Personal Reality entered
   the active pool at chapter 62, after Clothing's completion in
   chapter 61. Their `revealed_at_chapter` values remain derived from
   first-perk-acquired (62 for PR, 63 for Capstone). They share
   `entered_pool_at_chapter: 62`. Slot positions are 13 (Capstone) and
   14 (Personal Reality) by folder-name decree.
2. **Felyne Perks excluded.** No 15th-constellation folder, no bundle
   entry, no schema accommodation. The 14-constellation set holds.
   When Felyne Perks appears in-story, a separate small refactor
   adds it.
3. **Undiscovered display in sky view.** Each carousel card draws
   marker stars **always**. Silhouette polylines are drawn **only**
   once `revealed_at_chapter <= current_chapter`. Pre-reveal cards
   show vertices without edges.
4. **Schema and data move together.** The schema bump and the new
   field shape land in a single atomic phase.
5. **Silhouettes are multi-stroke.** A `current.svg` may carry many
   open `<polyline class="cluster-outline">` elements; each is an
   independent stroke. The bundle preserves them as an array of
   point-arrays.
6. **Vertex-source attribute in SVG.** `<svg data-vertex-source="jumps|perks">`
   is the durable signal. The extractor reads it; no count-matching
   heuristic.
7. **Phase 9 visual review is a human checkpoint.** Plan execution
   halts at Phase 9 for the user to review before merging.
8. **Scaffolder is rewritten, not preserved.** The HTML generator at
   Phase 7 replaces `scripts/scaffold_constellation_pages.py` outright.
   There is no "Phase 1 done-criterion: scaffolder still works
   unchanged" — that constraint is dropped.

## Goal

Restructure constellation assets so that `data/constellations/` is the
single authoring surface for cluster shapes and curator-editable
metadata, fed by the existing spreadsheet-derived perk roster, and
consumed downstream by `visualization_facts.json` and the web. The
tracing-workbench becomes the canonical editor; per-constellation HTML
pages become regenerated browsing artifacts; the web stops carrying
hand-coded shape/order tables.

## Sources of truth, after this work

| Domain quantity | Source of truth | Notes |
|---|---|---|
| Perk roster | `data/raw/Brocktons_Celestial_Forge_Reference.xlsx` via `data/derived/perk_directory.json` | Already plumbed. Untouched. |
| Reveal events (first-perk chapter) | Derived from `data/derived/constellation_knowledge_by_chapter.json` | Already plumbed. Untouched. |
| Completion events (outstanding → 0) | Derived from `data/derived/outstanding_perks_by_chapter.json` | Already plumbed. Untouched. |
| Pool-entry event for slots 13/14 | A single field in `scripts/derive_constellation_lifecycle.py` (constant), since both slots entered at ch 62 | Not a separate manual file. |
| Slot number (1–14) | Folder name prefix (`NN-<slug>`) | No separate slots.json. |
| Cluster shape (markers + silhouette strokes) | `data/constellations/NN-<slug>/current.svg` | Curator-edited via workbench. |
| Vertex-source preference (jumps/perks) | `data-vertex-source` attribute on the SVG root | Curator-edited via workbench. |
| Intended-image text | `data/constellations/NN-<slug>/metadata.json` | Curator-edited via workbench. |
| Cluster hue | `web/app.js` `HUES` table | Untouched (already in sync with SVGs). |
| Display order in web | Derived from `slot_position` in the bundle | Web's hardcoded list is removed. |

## New bundle field shape

In `constellation_wireframes.cluster_constellations[]`:

```json
{
  "name": "Personal Reality",
  "slug": "14-personal-reality",
  "slot_position": 14,
  "shape_concept": "planet in a nested hypercube ...",
  "vertex_source": "perks",
  "revealed_at_chapter": "62",
  "completed_at_chapter": null,
  "entered_pool_at_chapter": "62",
  "marker_positions": [[0.220, 0.410], ...],
  "silhouette": [
    [[0.220, 0.410], [0.450, 0.610]],
    [[0.450, 0.610], [0.330, 0.220]],
    ...
  ]
}
```

- `marker_positions`: N centers, normalized to `[0, 1]`, y-down.
  N is whatever the SVG carries.
- `silhouette`: array of polylines, each a list of `[x, y]` points
  (≥2). May be `[]` if the SVG carries no `cluster-outline`. No
  closure assumption. Each polyline renders as one `<polyline>` in
  the web.
- `cluster_vertices` (today's field) is **removed**, not renamed.
- `entered_pool_at_chapter` is equal to `revealed_at_chapter` for
  slots 1–12, and is `"62"` for slots 13 and 14.

## Phases

Each phase has explicit **Inputs**, **Outputs**, and **Done criteria**
that an agent can verify mechanically without further user input.

---

### Phase 0 — Pre-work and snapshots

**Inputs:** current main branch state. **Outputs:** baseline artifacts.

1. Capture the current `data/derived/visualization_facts.json` to
   `/tmp/visualization_facts_pre.json` for before/after structural
   comparison at Phase 5/6.
2. Run the web app locally and capture screenshots:
   - Start dev preview via the existing `preview_start` flow (the web
     app loads from `web/index.html`).
   - Take one screenshot per cluster card in the carousel by scrubbing
     to a chapter where each cluster has been revealed. Save as
     `/tmp/constellation_baseline_<slug>.png`.
   - Take one screenshot of the detail-mode constellation-bars panel
     for end-state coverage.

**Done:** 14 cluster screenshots + 1 detail-panel screenshot saved to
`/tmp/`, plus `/tmp/visualization_facts_pre.json`. No code touched.

---

### Phase 1 — Move and update references

**Inputs:** `design/constellations/` (current location).
**Outputs:** `data/constellations/` (new location), all path references
updated.

1. `git mv design/constellations data/constellations`.
2. Run a fresh grep:
   ```sh
   grep -rln "design/constellations" . \
     --include="*.py" --include="*.js" --include="*.html" \
     --include="*.md" --include="*.json"
   ```
   Update every hit. Expected hits include (but may not be limited to):
   - `scripts/scaffold_constellation_pages.py` (hardcoded `OUT` path)
   - `scripts/scaffold_design_wireframes.py` (docs/references; will be
     deleted at Phase 10 anyway, update for consistency)
   - `data/constellations/tracing-workbench.html` itself (any
     hardcoded path messages in user-facing strings)
   - `docs/data_file_audit.md`, `docs/derived_dataset_inventory.md`
   - `TODO.md`, `DEVELOPERS.md`, `USERS.md`
   - `tests/test_chapter_facts_scenarios.py`,
     `tests/test_data_package_contract.py`
3. Verify zero remaining hits:
   ```sh
   grep -rln "design/constellations" .
   ```
   Should return nothing.

**Done:** zero references to the old path remain; the web app still
loads and tests still pass against the move alone (no other changes
yet).

---

### Phase 2 — Inject `data-vertex-source` and seed metadata sidecars

**Inputs:** 14 `data/constellations/NN-<slug>/current.svg` files,
`data/derived/perk_directory.json`.
**Outputs:** 14 SVGs annotated with `data-vertex-source`, 14 sibling
`metadata.json` files.

1. Add a one-time migration script `scripts/migrate_vertex_source.py`:
   - **Two-pass / atomic**. First pass: resolve `vertex_source` for
     every cluster without writing any file. If any cluster fails to
     resolve (count match is ambiguous or zero), the script halts and
     reports all unresolved clusters at once — no SVG is modified.
     Second pass (only if first pass resolved all 14): write the
     `data-vertex-source` attribute to all 14 SVGs.
   - Resolution rule per cluster:
     - Count `<use href="#star-mark">` elements in `current.svg`.
     - Look up `jump_count` and `perk_count` from `perk_directory.json`.
     - If marker count == perk count and != jump count → `perks`.
     - If marker count == jump count and != perk count → `jumps`.
     - Otherwise → unresolved.
   - On the write pass, inject `data-vertex-source="<inferred>"` on
     the root `<svg>` element (immediately after the existing
     `viewBox` attribute).
   - Run once; commit. The script then becomes dead code (Phase 10
     deletes it).
2. For each cluster folder, write `metadata.json`:
   - Parse `<p class="shape-concept">` from the existing `index.html`
     for `intended_image` text.
   - Write:
     ```json
     {
       "schema_version": 1,
       "intended_image": "..."
     }
     ```
   - `vertex_source` lives in the SVG, not here.

**Done:** all 14 SVGs carry `data-vertex-source`. All 14 cluster
folders have a valid `metadata.json`. Web app still loads (none of
these files are read by the bundle yet).

---

### Phase 3 — Lifecycle derivation

**Inputs:** `data/derived/constellation_knowledge_by_chapter.json`,
`data/derived/outstanding_perks_by_chapter.json`, folder names in
`data/constellations/NN-<slug>/`.
**Outputs:** `data/derived/constellation_lifecycle.json` and its
schema.

1. Add `scripts/derive_constellation_lifecycle.py`:
   - For each of the 14 constellation folders, derive:
     - `slot_position`: integer from folder-name prefix (`13-capstone` → 13).
     - `revealed_at_chapter`: first chapter listing the constellation
       in `revealed_in_chapter`. Null if never revealed (won't apply
       to the locked 14-set).
     - `completed_at_chapter`: first chapter where `after_chapter`
       has an empty list for the constellation **and** `before_chapter`
       had a non-empty list. Null if never completed.
     - `entered_pool_at_chapter`: equal to `revealed_at_chapter` for
       slots 1–12; hardcoded as `"62"` for slots 13 and 14.
   - Validate: every of the 14 folders maps to exactly one slot;
     slots 1–14 are contiguous and unique; every constellation has a
     `revealed_at_chapter` (none should be null in the locked set).
   - Output schema-validated JSON to
     `data/derived/constellation_lifecycle.json`.
2. Add `data/derived/_schemas/constellation_lifecycle.schema.json`.

**Done:** lifecycle JSON regenerates cleanly. Invariants hold. No
consumer reads it yet.

---

### Phase 4 — SVG extractor

**Inputs:** 14 cluster folders.
**Outputs:** Python function returning an in-memory dict (no JSON
file); consumed directly by Phase 5's builder.

1. Add `scripts/extract_constellation_svgs.py` exposing a single
   function `extract(constellations_dir: Path) -> dict[str, dict]`:
   - For each cluster folder:
     - Parse the `<svg>` root for `data-vertex-source`. If absent →
       **halt with a clear error** naming the offending folder.
     - Parse `<use href="#star-mark">` elements; for each, record the
       center as `((x + 15) / 320, (y + 15) / 320)`. (Coordinates may
       legitimately fall outside `[0, 1]` due to artistic overflow;
       do not validate bounds.)
     - Parse every `<polyline class="cluster-outline">` element. For
       each, parse `points="..."` into a list of `[x, y]` pairs, then
       normalize each by dividing by 320. Treat each polyline as an
       independent stroke. The function returns the silhouette as
       `list[list[[float, float]]]`.
     - Parse `metadata.json` for `intended_image`.
   - Stop-and-halt conditions (whole extraction halts on any one;
     do not skip-and-continue):
     - `data-vertex-source` missing from any SVG root.
     - Marker count is zero.
     - A `<cluster-outline>` element is anything other than `<polyline>`
       (e.g., a raw `<path>`).
     - `metadata.json` missing or fails to parse.

**Done:** running the extractor prints a per-cluster summary (slug,
marker count, polyline count, vertex_source, intended_image preview)
matching the on-disk reality.

---

### Phase 5 — Schema + builder + fixtures (single atomic phase)

**Inputs:** Phase 3 lifecycle + Phase 4 extractor.
**Outputs:** new schemas, rewritten builder, updated fixtures, `pytest`
green.

This phase intentionally bundles schema and data changes so the build
never produces an output that fails validation.

1. **Schema updates:**
   - `data/derived/_schemas/constellation_wireframes.schema.json`:
     - Drop the `cluster_vertices` field.
     - Add `marker_positions`, `silhouette`, `vertex_source`,
       `revealed_at_chapter`, `completed_at_chapter`,
       `entered_pool_at_chapter`, `slot_position`, `slug`.
     - The `minItems: 14, maxItems: 14` constraint on the cluster
       array stays (still 14 clusters).
     - The 14-name enum on `cluster_constellations[].name` stays.
     - Bump the schema's top-level `schema_version`.
   - `data/derived/_schemas/visualization_facts.schema.json`:
     - Mirror the wireframe shape changes (the `cluster.$defs` block).
     - Bump top-level `schema_version`.
2. **Cascade audit:** before writing builder, grep for every pinned
   `schema_version` and `contract_version` and update each that gates
   wireframes or visualization_facts:
   ```sh
   grep -rn "schema_version" --include="*.json" --include="*.py" data/ scripts/ tests/ web/
   grep -rn "contract_version" --include="*.json" --include="*.py" --include="*.js" data/ scripts/ tests/ web/
   ```
   Update `data/derived/data_package.json`, `data/packages.json`,
   `scripts/data_release.py`, `web/data-contract.js`, and every test
   that asserts a specific version.
3. **Builder rewrite:** `scripts/build_constellation_wireframes.py`:
   - **Delete** `CLUSTER_SHAPES` and related normalization code.
   - For each cluster: call the Phase 4 extractor, look up the Phase 3
     lifecycle row, emit the new `cluster_constellations[]` shape.
   - `jump_constellations[]` construction is unchanged.
4. **Fixture updates** (verify line numbers freshly; cited as a
   starting point, not a contract):
   - `tests/helpers/web_runtime_site.py`: stop producing
     `cluster_vertices`; produce the new fields.
   - `tests/test_build_visualization_facts.py`: same.
   - `tests/test_data_package_contract.py`: update any wireframe
     fixture that asserts the old shape; update the pinned
     `schema_version` assertion.
   - `tests/test_visualization_facts_schema.py`: update enum/required
     assertions to match the new schema.
5. Run the full builder pipeline:
   ```sh
   python3 scripts/derive_constellation_lifecycle.py
   python3 scripts/build_constellation_wireframes.py
   python3 scripts/build_visualization_facts.py
   ```
   Then `pytest`.

**Done:** `pytest` is green. Diff between `/tmp/visualization_facts_pre.json`
and the new output shows: `cluster_vertices` gone; `marker_positions`,
`silhouette`, `vertex_source`, lifecycle fields, `slot_position`,
`slug` added. Nothing else changed structurally.

---

### Phase 6 — Rebuild orchestration helper (lands with Phase 7)

**Inputs:** the four build/derive scripts including the rewritten
scaffolder. **Outputs:** a tiny shell script that runs them in order.

This phase is sequenced immediately after Phase 7 to avoid the script
referencing a not-yet-written scaffolder. Do not commit Phase 6 alone
without Phase 7.

1. After Phase 7's `scripts/scaffold_constellation_pages.py` rewrite
   lands, add `scripts/rebuild_constellation_assets.sh`:
   ```sh
   #!/usr/bin/env bash
   set -euo pipefail
   python3 scripts/derive_constellation_lifecycle.py
   python3 scripts/build_constellation_wireframes.py
   python3 scripts/build_visualization_facts.py
   python3 scripts/scaffold_constellation_pages.py
   ```
2. Document the script in `DEVELOPERS.md` as the canonical "rebuild
   after editing a current.svg or metadata.json" command.

**Done:** the script runs cleanly; running it twice in a row is
idempotent (no diff in outputs).

---

### Phase 7 — HTML generator (rewrite of scaffolder)

**Inputs:** `perk_directory.json`, `constellation_lifecycle.json`, each
cluster's `metadata.json`, each cluster's `current.svg`.
**Outputs:** 14 per-cluster `index.html` + one top-level `index.html`
in `data/constellations/`.

1. Rewrite `scripts/scaffold_constellation_pages.py` end-to-end. New
   responsibilities:
   - Read all four input sources.
   - For each of 14 clusters, emit `data/constellations/NN-<slug>/index.html`:
     - `<h1>` constellation name + slot position
     - Meta block: slot, jump count, perk count,
       `revealed_at_chapter`, `completed_at_chapter` (or "incomplete"),
       `entered_pool_at_chapter`
     - `intended_image` text (paragraph)
     - Embedded `current.svg`, with all `id`s prefixed by the slug to
       avoid collisions when multiple SVGs appear on the same page or
       across linked pages (e.g., `ray-grad` → `<slug>-ray-grad`).
     - Jumps table (sorted by perk count desc) from
       `perk_directory.json`
     - Perks table (collapsed by jump, with expandable rows) from
       `perk_directory.json`
     - "Edit in workbench" link → `../tracing-workbench.html?constellation=<slug>`
     - Back-link → `../index.html`
   - Emit `data/constellations/index.html`:
     - One row per constellation, sorted by `slot_position`
     - Columns: slot, name, thumbnail (embedded `current.svg` with
       prefixed ids), jumps, perks, status,
       "Edit" → `tracing-workbench.html?constellation=<slug>`
2. Every generated file opens with
   `<!-- generated by scripts/scaffold_constellation_pages.py; do not edit -->`.
3. Each per-cluster `index.html` reaches the top via `../index.html`.

**Done:** running the script produces 1 top-level + 14 per-cluster
HTML files. Each per-cluster page renders the embedded SVG correctly
(verified by manual open). The top-level index renders all 14
thumbnails simultaneously without `id` collisions (the critical
correctness check).

---

### Phase 8 — Tracing-workbench extensions

**Inputs:** existing `data/constellations/tracing-workbench.html`,
plus new metadata files.
**Outputs:** extended workbench supporting metadata + vertex_source
round-trip + ephemeral reference image.

1. Update workbench folder-scan logic: enumerate `NN-*` subfolders of
   the workbench's parent directory.
2. Add `?constellation=<slug>` query-param handling:
   - On load, if param is present AND the curator has previously
     granted FSA access to `data/constellations/`, auto-resolve the
     subfolder handle from IndexedDB.
   - If no prior grant: prompt the curator to grant access once; the
     deep-link works on subsequent visits.
3. When a folder is selected (deep-linked or manually):
   - Load `current.svg`. Read `data-vertex-source` attribute from the
     root and populate the new "Vertex source" radio (jumps / perks).
     The radio is the canonical UI; saving writes back to the SVG
     root.
   - Load `metadata.json`. Validate `schema_version == 1`; on
     mismatch, surface a clear error and refuse to load (prevents
     silent data loss). Populate the new "Intended image" textarea.
   - Set the tracing canvas background to the loaded `current.svg`.
4. Add reference-image UI:
   - URL input + file upload, both **ephemeral** (in-memory only;
     never persisted to disk or `metadata.json`).
   - Render as a semi-transparent layer beneath the tracing canvas.
5. Empty state (no folder selected yet):
   - Display "Connect a folder to begin" prompt. No background SVG.
6. On save:
   - Write `current.svg` with the updated `data-vertex-source`
     attribute on the root via FSA.
   - Write `metadata.json` ({ schema_version: 1, intended_image })
     via FSA.
   - **Download fallback** (browsers without FSA): two sequential
     downloads with filenames `<slug>-current.svg` and
     `<slug>-metadata.json`. A toast tells the curator to drop both
     into `data/constellations/<slug>/` and rename to `current.svg`
     and `metadata.json` respectively.
   - **Clipboard fallback** (existing): exports only the SVG; the
     existing message is updated to remind the curator that metadata
     must be hand-edited separately.

**Done:** workbench round-trips both files for any cluster; deep-link
from the generated HTML works end-to-end; reference image is
in-memory only; FSA save tested in Chrome/Edge; download fallback
tested in Firefox/Safari.

---

### Phase 9 — Web rewrite (human checkpoint after)

**Inputs:** bundle with new fields.
**Outputs:** web app reading shape + display order from the bundle.

1. In `web/app.js`:
   - **Delete** `SHAPES` constant (lines 62–77).
   - **Keep** `HUES` (canonical).
   - Rewrite `buildConstellations()`:
     - Drive from the bundle: iterate
       `wireframes.cluster_constellations` (already in `slot_position`
       order from the builder).
     - For each cluster, produce
       `{ name, slug, hue, shape_concept, slot_position,
          revealed_at_chapter, completed_at_chapter,
          entered_pool_at_chapter, vertex_source, marker_positions,
          silhouette }`.
     - Construct `conByName` as `Object.fromEntries(list.map(c => [c.name, c]))`
       — preserving the existing bracket-access lookups
       `app.data.conByName[roll.constellation]` at `web/app.js:1165`
       and `:1200`. Do **not** introduce a `Map` here; the existing
       call sites assume plain-object access.
   - Rewrite `renderConstellationCard()`:
     - Inline `<symbol id="star-mark">` + `<linearGradient id="ray-grad">`
       in the card's `<defs>` (copy from a design SVG). Prefix the IDs
       with `card-` to scope them locally to the card.
     - **Always** render markers as `<use href="#card-star-mark">` at
       `(center.x * size - 15, center.y * size - 15)` with `width="30"`.
     - Render silhouette polylines **only if** `revealed_at_chapter`
       is non-null and `<= current_chapter`. Each polyline as its own
       `<polyline points="...">`.
   - Bump `DATA_VERSION` (line 20).
2. In `web/viz-model.js`:
   - **Delete** `DEFAULT_CONSTELLATION_ORDER` constant.
   - Replace `buildConstellationProgressIndex(facts, constellationOrder = DEFAULT_CONSTELLATION_ORDER)`
     with a version that takes `constellationOrder` as a required
     parameter (or accepts the bundle and derives order from it
     itself; pick the simpler call-site refactor).
   - Update both call sites in `app.js` (lines 423, 1324 — verify with
     a fresh grep) to pass a list derived from
     `app.data.constellations.map(c => c.name)`.
3. The `renderUnresolvedCard` function is no longer needed for the
   "constellation not yet known to Joe" case (markers always render).
   It may still be used for "roll resolved to no constellation"; audit
   and remove only if unused.

**Done — HUMAN CHECKPOINT.** Pause execution. The user manually:
- Compares each cluster card in the running web app against
  `/tmp/constellation_baseline_<slug>.png` from Phase 0.
- Compares pre-reveal card behavior (vertices visible, no silhouette
  edges) against the new directive.
- Spot-checks slot-13/14 carousel ordering at chapters 61, 62, 63 to
  confirm Capstone and PR appear at the correct times.
- Spot-checks ID collisions / browser DevTools console for SVG
  warnings.

Sign-off: the user explicitly approves moving to Phase 10. No agent
auto-advances.

---

### Phase 10 — Cleanup

**Inputs:** signed-off Phase 9. **Outputs:** clean tree.

1. Verify no remaining references to `SHAPES`, `DEFAULT_CONSTELLATION_ORDER`,
   `cluster_vertices`, `CLUSTER_SHAPES`:
   ```sh
   grep -rn -E "SHAPES|DEFAULT_CONSTELLATION_ORDER|cluster_vertices|CLUSTER_SHAPES" \
     --include="*.py" --include="*.js" --include="*.json" --include="*.html" \
     --include="*.md" .
   ```
   Each hit gets resolved (most should be in comments or docs;
   any in code is a Phase-9 follow-up).
2. Delete `scripts/scaffold_design_wireframes.py` if no production
   import:
   ```sh
   grep -rn "scaffold_design_wireframes" --include="*.py" --include="*.json" .
   ```
   Should match only the file itself. If so, delete; otherwise, fix
   the import sites first.
3. Delete `scripts/migrate_vertex_source.py` (one-time migration).
4. Delete this plan doc.
5. Run full test suite. Run the rebuild script. Confirm clean diff.

**Done:** no dangling references; all tests green; rebuild script
idempotent.

---

## Mechanical conventions

- SVG viewBox is `0 0 320 320`. Bundle coords normalized to `[0,1]`,
  y-down.
- `<use href="#star-mark" x="X" y="Y" width="30" height="30">` places
  the **top-left** of a 30×30 box. The symbol's viewBox is centered
  on origin, so the visual center is `(X+15, Y+15)`.
- Bundle stores **centers** (`((X+15)/320, (Y+15)/320)`).
- Web renders by emitting `<use>` at
  `(center.x*size - markerSize/2, center.y*size - markerSize/2)`.
- **Silhouettes are multi-stroke.** A `current.svg` may carry many
  separate `<polyline class="cluster-outline">` elements. Each is an
  independent stroke; none assumed closed. Bundle preserves them as
  `silhouette: list[list[[float, float]]]`.
- **No coordinate-bounds validation.** Hand-traced shapes legitimately
  overflow `[0, 320]`. Visual review at Phase 9 catches misplaced
  shapes; the extractor does not.
- **Vertex-source lives in the SVG.** `<svg data-vertex-source="jumps|perks">`
  is the durable signal. The workbench writes it on save; the
  extractor reads it.

## Stop-and-halt conditions

Phase 4 extractor halts the whole run (no skip-and-continue) on:

- Any SVG root missing `data-vertex-source`.
- Any SVG with zero `<use href="#star-mark">` elements.
- Any `cluster-outline` element that is anything other than
  `<polyline>`.
- Any cluster folder missing `metadata.json`.
- `metadata.json` `schema_version` mismatch.

Phase 3 lifecycle deriver halts on:

- A cluster folder whose name does not match `NN-<slug>` format.
- Slot positions are not 1..14 contiguous (some missing or duplicated).
- A constellation in the lifecycle has no `revealed_at_chapter` (every
  one of the 14 must have been revealed by now).

## Risks still open

- **Pipeline-step skew between curator edits and rebuild.** The
  curator may edit a `current.svg` or `metadata.json` without running
  `rebuild_constellation_assets.sh`. The published HTML and the
  bundle would then drift. Mitigation: document the rebuild command
  prominently in `DEVELOPERS.md`. A pre-commit hook is out of scope
  but worth noting.
- **FSA browser support.** Chrome/Edge only for direct save. Safari
  and Firefox curators are limited to download fallback. Acceptable
  given curator pool is small.
- **One-time migration timing.** `migrate_vertex_source.py` (Phase 2)
  halts on any cluster whose marker count matches both jumps and
  perks. Today, the marker-count diagnostic in this conversation
  shows no such collision, but the curator should verify before
  running.
