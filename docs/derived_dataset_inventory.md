# Derived dataset inventory

High-level map of the derived data used by the visualization and analytics.

| File | Purpose |
|---|---|
| `data/derived/chapters.json` | Chapter metadata and publish timeline |
| `data/derived/rolls.json` | Curator roll log (ch 1–75), misses and banked CP |
| `data/derived/perks_catalog.json` | Curator perk catalog |
| `data/derived/obtained_perks.json` | Full-story acquisition log |
| `data/derived/timeline.json` | **Canonical** in-world timeline merged from all sources (xlsx + wiki + TUI + manual). Built by `scripts/derive_timeline.py`; embedded into `chapter_facts.json` as `in_world_timeline`. Schema v2 — atomic single-event entries; `chapter_num` is null unless a source explicitly attests it. |
| `data/derived/timeline_xlsx.json` | Raw timeline rows from the curator xlsx `Reference#Timeline of Events` sheet. Input to the canonical merge — not consumed directly by the app. |
| `data/derived/timeline_wiki.json` | Raw dated bullets from the Celestial Forge Fandom Wiki page (`data/raw/wiki/bcf_wiki_timeline.html`). Input to the canonical merge — not consumed directly by the app. |
| `data/manual/timeline_manual.json` | Hand-curated timeline entries. The only place (besides TUI annotations) where `chapter_num` may be explicitly set. Input to the canonical merge. |
| `data/derived/chapter_sections.json` | Section extraction + CP-earning classification inputs |
| `data/derived/predicted_rolls.json` | Mechanical predicted roll locations, one row per CP threshold crossing with `cp_rule_regime` and `roll_trigger_cp_threshold`. |
| `data/manual/chapter_roll_overrides.json` | Manual roll curation keyed by mechanical chapter. Encodes hit/miss, multi-grabs, optional evidence text, and deferred mention/display metadata. |
| `data/derived/roll_locations_regex.json` | Regex anchor catalog for roll-evidence discovery |
| `data/derived/roll_text_evidence.json` | Text-backed windows around predicted roll positions. Supports evidence review; not canonical roll ownership. |
| `data/derived/roll_outcomes.json` | Interpolated fallback roll sequence for chapters not covered by the curator log. Input to `roll_facts.json`, not consumed directly by the app. |
| `data/derived/roll_facts.json` | **Canonical** roll-attempt stream joined into `chapter_facts.json`. Curator rows from `rolls.json` win where present; `roll_outcomes.json` rows are provenance-marked fallback. Free perks attach to paid hits. Rows separate owner/listing chapter (`chapter_num`), mechanical predicted-slot chapter (`mechanical_chapter_num`), and visualization coordinate (`display_*`) so deferred roll mentions can be modeled without UI reconciliation. |
| `data/derived/roll_locations_validation.json` | Validation + discrepancy summary |
| `data/manual/chapter_publication_dates.json` | Single source of truth for per-chapter first-publication and last-edit dates. Each date carries its own provenance (`manual`/`ao3`/`sv`/`epub`). Bootstrapped from AO3 + EPUB by `scripts/seed_chapter_publication_dates.py`; hand-owned thereafter. |
| `data/derived/extracted_perks.json` | Perk footer extraction from chapter exports |
| `data/derived/perk_directory.json` | Joined directory view for lookup/enrichment |
| `data/derived/chapter_facts.json` | Pipeline intermediate. Embeds the canonical `in_world_timeline` and roll facts. Consumed by `build_visualization_facts.py` and `data_release.py`; not fetched by the web layer. |
| `data/derived/visualization_facts.json` | **Bundled web payload.** Produced by `scripts/build_visualization_facts.py`; bundles `chapter_facts.json`, `constellation_wireframes.json`, and `predicted_rolls.json` into a single file. This is the sole required runtime file the web app fetches (alongside `data_package.json` for the package picker). |

## Build order

```
parse_reference.py         -> timeline_xlsx.json, obtained_perks.json
parse_wiki_timeline.py     -> timeline_wiki.json
(human edits)              -> data/manual/timeline_manual.json
            ↓
derive_timeline.py         -> timeline.json (canonical, schema-validated)
predict_rolls.py           -> predicted_rolls.json (mechanical schedule)
find_roll_locations.py     -> roll_locations_regex.json (evidence anchors)
find_text_backed_rolls.py  -> roll_text_evidence.json (evidence windows)
derive_roll_outcomes.py    -> roll_outcomes.json (fallback interpolation)
derive_roll_facts.py       -> roll_facts.json (canonical, schema-validated)
            ↓
build_chapter_facts.py         -> chapter_facts.json (embeds in_world_timeline + roll_facts)
build_constellation_wireframes.py -> constellation_wireframes.json
predict_rolls.py               -> predicted_rolls.json
data_release.py manifest --bootstrap -> data_package.json (pass 1, version metadata only)
build_visualization_facts.py   -> visualization_facts.json (bundled web payload)
data_release.py manifest       -> data_package.json (pass 2, adds visualization_facts hash/size)
```

The canonical timeline merger never invents data: `xlsx` and `wiki` entries always carry `chapter_num=null`; only `manual` and (future) `tui` entries may attest a chapter. Multiple entries on the same in-world date from different sources are kept separate — no automated dedup.

The canonical roll facts merger preserves source provenance: curator
roll rows are trusted where available, including misses, banked CP, and
duplicate source rows; interpolated rows remain a fallback until later
chapters get text-backed or manually curated roll attempts. Manual
chapter-roll overrides are keyed by mechanical chapter; `mention_chapter_num`
only moves derived ownership/listing, while validation and CP scheduling
continue to consume the mechanical predicted slot. TUI and web consumers read
these derived facts; they should not repair, reinterpret, or synthesize roll
accounting locally.
