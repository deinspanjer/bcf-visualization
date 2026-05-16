# Data File Audit

This audit classifies repository data by release responsibility, not just by
directory name.

## Intended Categories

| Category | Git treatment | Release treatment | Notes |
|---|---|---|---|
| Source EPUB | Not committed | Must be provided by a stable maintainer-controlled source | The EPUB is copyrighted prose and is ignored by `data/raw/*.epub`. CI currently downloads it from FicHub when regenerating data, which is convenient but not a stable source-of-truth flow. |
| Other source snapshots | Committed | Used as derivation inputs | These are rare-changing xlsx, MHT, HTML, and manifest snapshots under `data/raw/`, excluding EPUB files. |
| Curated files | Committed | Used as derivation inputs | Human-maintained JSON under `data/manual/` plus committed label files under `data/labeled/`. |
| Local/editor state | Not committed | Never released | Forge Curator state, session journals, proposal staging files, WAL files, and OS/editor files. |
| Derived intermediate files | Not committed | Included in dev-derived release bundles | Top-level `data/derived/*.json` files other than the runtime contract are generated. |
| Final runtime data | Not committed | Included in runtime and dev-derived release bundles | `data/derived/chapter_facts.json` is the current runtime contract file. A future cleanup should rename it to `bcf-visualization-data.json` or equivalent. |
| Schemas | Committed | Used by local tests and release validation | `data/derived/_schemas/*.schema.json` are source-controlled contracts, not generated payloads. Their current path is historical; they probably belong under a non-`derived` contract/schema directory. |

## Current File Classification

### Ignored Local Source

- `data/raw/Brocktons_Celestial_Forge.epub`
- `data/private-source/`

`data/private-source/` is a local clone of the private companion repository
`deinspanjer/bcf-visualization-private-source`. It stores the EPUB plus metadata
outside the public repo. The data-release workflow checks out that private repo
when `BCF_PRIVATE_SOURCE_DEPLOY_KEY` is configured.

Fallback issue: `.github/workflows/data-release.yml` can still regenerate data
by running `scripts/download_bcf_epub.py`, which downloads from FicHub, when the
private source repo input is intentionally blank or unavailable. That fallback
is convenient but not the preferred source-of-truth flow.

### Committed Source Snapshots

- `data/raw/Brocktons_Celestial_Forge_Reference.xlsx`
- `data/raw/Brocktons_Celestial_Forge_Rolls_List.xlsx`
- `data/raw/info_posts/info_index.mht`
- `data/raw/info_posts/manifest.json`
- `data/raw/info_posts/sv_page_0013.mht`
- `data/raw/info_posts/sv_page_0171.mht`
- `data/raw/info_posts/sv_page_0233.mht`
- `data/raw/info_posts/sv_page_0277.mht`
- `data/raw/info_posts/sv_page_0403.mht`
- `data/raw/info_posts/sv_page_0649.mht`
- `data/raw/info_posts/sv_page_0847.mht`
- `data/raw/tvtropes_wog.mht`
- `data/raw/wiki/bcf_wiki_timeline.html`

These are source snapshots, not derived outputs. They are currently tracked and
should remain committed unless a separate source-snapshot release mechanism is
introduced.

### Committed Curated Inputs

- `data/manual/author_roll_table_2026-05-09.json`
- `data/manual/chapter_roll_overrides.json`
- `data/manual/perk_constellation_overrides.json`
- `data/manual/regex_hit_review.json`
- `data/manual/regime_transitions.json`
- `data/manual/roll_overrides.json`
- `data/manual/section_classifications.json`
- `data/manual/timeline_manual.json`
- `data/labeled/spans/pilot.jsonl`
- `data/labeled/sections/.gitkeep`
- `data/labeled/spans/.gitkeep`

These are intended to be committed. Forge Curator edits in `data/manual/*.json`
are release inputs and must be pushed before CI regeneration can reproduce them.

### Ignored Local Curator And Proposal State

- `data/manual/.forge_curator_state.json`
- `data/manual/.session_journals/*.jsonl`
- `data/labeled/.proposals_raw/*.json`
- `data/labeled/.tui_wal.jsonl`
- `data/labeled/**/.tui_state.json`
- `data/labeled/**/_*.jsonl`
- `.DS_Store` files such as `data/.DS_Store` and `data/raw/.DS_Store`

These are correctly ignored. They are local working state or proposal staging,
not release inputs.

### Committed Schemas

- `data/derived/_schemas/chapter_facts.schema.json`
- `data/derived/_schemas/chapter_publication_dates.schema.json`
- `data/derived/_schemas/chapter_sections.schema.json`
- `data/derived/_schemas/chapters.schema.json`
- `data/derived/_schemas/constellation_wireframes.schema.json`
- `data/derived/_schemas/extracted_perks.schema.json`
- `data/derived/_schemas/obtained_perks.schema.json`
- `data/derived/_schemas/perk_directory.schema.json`
- `data/derived/_schemas/perks_catalog.schema.json`
- `data/derived/_schemas/predicted_rolls.schema.json`
- `data/derived/_schemas/roll_facts.schema.json`
- `data/derived/_schemas/roll_locations_regex.schema.json`
- `data/derived/_schemas/roll_locations_validation.schema.json`
- `data/derived/_schemas/roll_text_evidence.schema.json`
- `data/derived/_schemas/rolls.schema.json`
- `data/derived/_schemas/timeline.schema.json`
- `data/derived/_schemas/timeline_manual.schema.json`
- `data/derived/_schemas/timeline_xlsx.schema.json`

These are not data payloads. They define contracts and should stay committed.

### Ignored Derived Intermediate Payloads

- `data/derived/chapter_sections.json`
- `data/derived/chapters.json`
- `data/derived/constellation_knowledge_by_chapter.json`
- `data/derived/constellation_wireframes.json`
- `data/derived/extracted_perks.json`
- `data/derived/obtained_perks.json`
- `data/derived/outstanding_perks_by_chapter.json`
- `data/derived/perk_directory.json`
- `data/derived/perks_catalog.json`
- `data/derived/predicted_rolls.json`
- `data/derived/roll_facts.json`
- `data/derived/roll_locations_regex.json`
- `data/derived/roll_locations_validation.json`
- `data/derived/roll_outcomes.json`
- `data/derived/roll_text_evidence.json`
- `data/derived/roll_validation.json`
- `data/derived/rolls.json`
- `data/derived/timeline.json`
- `data/derived/timeline_wiki.json`
- `data/derived/timeline_xlsx.json`

These are correctly ignored by `data/derived/*.json`. They should be
regenerated from committed source snapshots plus curated inputs, or hydrated
from a published dev-derived release bundle.

### Ignored Runtime Payloads

- `data/derived/chapter_facts.json`
- `data/derived/data_package.json`

`chapter_facts.json` is currently the final web runtime data file. The name is
historical and narrower than its current role. `data_package.json` is the local
manifest for the hydrated runtime/dev bundle and is generated by
`scripts/data_release.py`.

## Current Layout Notes And Risks

1. The data-release workflow depends on FicHub for EPUB regeneration.
   This is the main unstable point. GitHub Actions cannot see a local ignored
   EPUB unless it is uploaded or published somewhere.
2. `data/raw/` contains two correctly treated categories: ignored copyrighted
   EPUB input and committed source snapshots. This is acceptable, but the
   directory name alone does not communicate the different release policies.
3. `chapter_facts.json` is the final runtime data contract despite its name.
   Rename later, with a compatibility transition in `web/`, schemas, tests, and
   release packaging.
4. `data/derived/_schemas/` contains committed source-controlled schema
   contracts. The git treatment is correct; the path is only a layout smell
   because these files are not derived.
