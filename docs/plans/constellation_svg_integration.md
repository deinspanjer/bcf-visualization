# Constellation SVG integration plan

Status: locked, deferred. Do not execute until the design-folder
restructure / pipeline-integration plan is also written, so the two
can land together.

## Goal

Make `design/constellations/NN-<slug>/current.svg` the source of truth
for cluster-constellation **shape** (silhouette + vertex positions) on
both sides of the bundle:

- Drop the heuristic, hand-coded shape tables that the web and the
  wireframe builder each carry today.
- Have the bundle carry only what the SVGs say.
- Have the web sky view render directly from the bundle, using the
  same star-mark symbol the design SVGs use.

The work explicitly **does not**:

- introduce a new per-constellation color palette (web `HUES` stays
  canonical; all 14 SVGs already agree with it),
- add a background starfield to the web,
- surface any prose from the per-constellation `index.html` files
  (no current consumer reads `shape_concept`; the `index.html` files
  are out of scope).

## Locked decisions

### Sources of truth

| Domain quantity | Source of truth | Notes |
|---|---|---|
| Cluster shape (silhouette + vertex positions) | `design/constellations/NN-<slug>/current.svg` | Hand-curated; may originate from a tracing workbench. |
| Cluster hue (`H` in `oklch(0.82 0.14 H)`) | `web/app.js` `HUES` table | All 14 design SVGs already match this table; the extractor does **not** read color from SVG. |
| Per-jump constellation data (`jump_constellations[]`) | `data/derived/perk_directory.json` (unchanged) | Out of scope. |

### Bundle field shape

Per cluster in `constellation_wireframes.cluster_constellations[]`:

```json
{
  "name": "Toolkits",
  "shape_concept": "open-end wrench / spanner: ...",
  "marker_positions": [[0.220, 0.410], [0.220, 0.725], ...],
  "silhouette":      [[0.220, 0.410], ...,  [0.220, 0.410]]
}
```

- `marker_positions`: ordered list of vertex **centers**, normalized to
  `[0, 1]` in both axes, y-down. Length = N (whatever the SVG carries).
- `silhouette`: ordered polyline of points in the same coordinate
  system. May or may not pass through every marker. May be `[]` if the
  SVG carries no `cluster-outline` element.
- `cluster_vertices` (today's field) is **removed**, not renamed.

### Vertex count is SVG-determined, not derived

The constellation workbench lets each cluster pick **jumps or perks**
as the vertex driver. Personal Reality (1 jump / 124 perks) and a
handful of other clusters use perks, so their vertex counts diverge
from their jump counts. Implications:

- The extractor accepts whatever N markers the SVG provides.
- The bundle schema accepts any `N >= 1`.
- The renderer treats `N` as opaque (no `N==1` special-case promoted
  to first-class behavior).
- No test asserts `marker_positions count == jump count`.
- The mapping between markers and jumps/perks is **not** carried in
  the bundle. No web consumer needs it at the cluster level.

### Mechanical convention: marker-center offset

In `current.svg`:

```xml
<use href="#star-mark" x="55.3" y="116.1" width="30" height="30"/>
```

The `x`/`y` are the **top-left** of a 30×30 box, but the symbol's
internal `viewBox="-50 -50 100 100"` is centered on the origin. The
visual center is `(x + 15, y + 15)`.

Conventions:

- **Bundle stores centers.** The extractor records
  `((x + w/2) / 320, (y + h/2) / 320)`.
- **Web renders from centers** by emitting `<use>` at
  `(center.x * size - markerSize/2, center.y * size - markerSize/2)`.
- The extractor asserts that every center lands inside the visible
  region (loose bounds in the 320 viewBox; see "stop and report"
  below). Drift from the +15 rule fails loudly rather than silently
  shifting markers inward.

### Star-mark symbol

The design `<symbol id="star-mark">` (6+6 diffraction-ray cross, dual
center circles, depends on `<linearGradient id="ray-grad">`) becomes
the **default** zoomed-out star marker in the web's cluster cards.
Lift both elements into the web's card SVG `<defs>` (inline per card
is simplest; a shared root sprite is an acceptable optimization).

The symbol uses `currentColor` for ray tint, so setting
`color: oklch(0.82 0.14 <hue>)` on the card root propagates correctly.

Other star markers in the web (`simpleStar`, `diffractionMarker`) stay
where they are — they serve per-roll markers in the timeline / perk
list / roll log, which is outside the scope of this change.

## File-level changes

### Add

- `scripts/extract_constellation_svgs.py` — single-purpose parser.
  Reads each `design/constellations/NN-<slug>/current.svg`; returns a
  dict keyed by constellation name with `marker_positions` and
  `silhouette`. Includes the bbox sanity check (see below).

### Modify

- `scripts/build_constellation_wireframes.py`
  - **Delete** the `CLUSTER_SHAPES` heuristic table (~lines 76+).
  - For each cluster, populate the new fields by calling the
    extractor.
  - Jump-level construction is untouched.
- `data/derived/_schemas/constellation_wireframes.schema.json`
  - Replace `cluster_vertices` with `marker_positions` + `silhouette`.
  - Bump `schema_version` (full break, no shim — see no-backwards-compat
    rule in `MEMORY.md`).
- `data/derived/_schemas/visualization_facts.schema.json`
  - Mirror the schema version bump.
- `tests/helpers/web_runtime_site.py` (~line 238)
- `tests/test_build_visualization_facts.py` (~lines 38–104)
- `tests/test_data_package_contract.py` (~lines 52, 194, 266)
- `tests/test_visualization_facts_schema.py` (~lines 23–50)
  - All fabricate wireframes — produce the new fields, drop the old.
- `web/app.js`
  - **Delete** `HUES` is **not** what changes; **delete** the
    `SHAPES` constant at lines 62–77.
  - Update `buildConstellations()` (~line 421) to read
    `marker_positions` and `silhouette` from the bundle. Returned
    shape becomes `{ name, hue, shape_concept, marker_positions,
    silhouette }`.
  - Rewrite `renderConstellationCard()` (~line 1174):
    - Inline `<symbol id="star-mark">` + `<linearGradient
      id="ray-grad">` in the card SVG `<defs>`.
    - Render silhouette as a `<polyline>` from `con.silhouette` in
      0..size space.
    - Render markers as `<use href="#star-mark">` with the
      center-to-top-left translation noted above.
    - Drop `simpleStar()` calls **inside this function only**.
  - Bump `DATA_VERSION` (line 20) so cached bundles are re-fetched.

### Delete

- `scripts/scaffold_constellation_pages.py` — it regenerated the
  design pages we now treat as authoritative; keeping it invites
  accidental overwrite of hand work.
- `cluster_constellations[].cluster_vertices` in the bundle and
  schema (covered above).

### Flag, do not change in this pass

- `scripts/scaffold_design_wireframes.py` references a
  `design/wireframes/` tree that does not exist on disk. Its
  `cluster_vertices` reads will become dead code once the field is
  removed. Slate it for a separate cleanup task; do not touch in
  this change.

## Future update workflow

When a new SVG lands (tracing workbench, hand edit, anything else):

```sh
# overwrite design/constellations/NN-<slug>/current.svg
python3 scripts/build_constellation_wireframes.py
python3 scripts/build_visualization_facts.py
# reload web
```

Two commands. No JSON hand-editing. No web code change. This is the
"relatively straightforward to update" requirement.

## Sequencing

1. Add `scripts/extract_constellation_svgs.py`.
2. Rewrite `scripts/build_constellation_wireframes.py` to use it.
3. Update both schemas + bump `schema_version`.
4. Update fixtures + tests. (Tests gate the contract.)
5. Delete `scripts/scaffold_constellation_pages.py`.
6. Web rewrite (`SHAPES` deletion, `renderConstellationCard`,
   `star-mark` symbol lift, `DATA_VERSION` bump).
7. Visual diff pass: load `/web/index.html`, scrub through each of
   the 14 clusters, compare carousel cards against
   `design/constellations/NN-*/current.svg`.

Each step keeps the app loadable except step 3, where the schema
version bump is intentionally breaking and gated by step 4's fixture
updates.

## Stop-and-report cases

Per the user's "don't vibe a quick hack" rule, the parser should
**stop and surface a clear error** (not silently coerce) on:

- Marker bbox falls outside loose bounds in the 320 viewBox
  (e.g. any center outside `[15/320, 305/320]` in either axis). Likely
  cause: a hand edit forgot the +15 top-left → center offset.
- A `current.svg` has zero `<use href="#star-mark">` elements. Empty
  constellation is not a valid state in this pipeline.
- `cluster-outline` is encoded as a `<path d="...">` instead of
  `<polyline>` or `<circle>`. Today the design language is polyline
  (or circle for N==1). A path would be a meaningful design widening
  worth a human decision, not a regex extension.
- An `oklch` color in the SVG disagrees with the web `HUES` table.
  (Today they all agree.) Disagreement means one side drifted; the
  parser should fail and the human decides which side to fix —
  presumably by re-aligning the SVG, since web is canonical.

## Out of scope, flagged for later

- Surfacing `shape_concept` or per-jump prose from
  `design/constellations/NN-<slug>/index.html` in web tooltips.
- Re-flowing the design palette (`--void`, `--ink`, `--cyan`, …) into
  `web/style.css` tokens.
- `design/constellations/tracing-workbench.html`.
- The `design/wireframes/` per-jump SVG tree referenced by
  `scripts/scaffold_design_wireframes.py` (does not exist on disk
  today; the script is effectively orphaned at the cluster level).

## Why this plan is deferred

The user signaled a separate pipeline-integration plan that will
likely change:

- Where `design/constellations/` lives.
- Possibly what files sit alongside `current.svg` (e.g., a workbench
  config recording whether the cluster's vertices were driven by
  jumps or perks, or other metadata).

If the new structure adds files the extractor should ingest in one
pass, designing the extractor against the final structure is cheaper
than designing it twice. This plan should be re-read in light of the
restructure plan before execution; the **decisions** above (sources
of truth, bundle field shape, mechanical conventions, web changes)
are expected to survive intact — only the **paths** and possibly the
**inputs** to the extractor should shift.
