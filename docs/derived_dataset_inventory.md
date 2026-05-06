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
| `data/derived/predicted_rolls.json` | Simulated roll positions |
| `data/derived/roll_locations_regex.json` | Candidate prose windows for roll evidence |
| `data/derived/roll_text_evidence.json` | Text-backed roll/acquisition evidence |
| `data/derived/roll_locations_validation.json` | Validation + discrepancy summary |
| `data/derived/chapter_last_edited.json` | Threadmark last-edited metadata |
| `data/derived/extracted_perks.json` | Perk footer extraction from chapter exports |
| `data/derived/perk_directory.json` | Joined directory view for lookup/enrichment |
| `data/derived/chapter_facts.json` | Visualization backbone consumed by web app. Embeds the canonical `in_world_timeline` so the front-end loads a single file. |

## Build order

```
parse_reference.py         -> timeline_xlsx.json, obtained_perks.json
parse_wiki_timeline.py     -> timeline_wiki.json
(TUI annotation work)      -> data/labeled/spans/*.jsonl
(human edits)              -> data/manual/timeline_manual.json
            ↓
derive_timeline.py         -> timeline.json (canonical, schema-validated)
            ↓
build_chapter_facts.py     -> chapter_facts.json (embeds in_world_timeline)
```

The canonical timeline merger never invents data: `xlsx` and `wiki` entries always carry `chapter_num=null`; only `manual` and (future) `tui` entries may attest a chapter. Multiple entries on the same in-world date from different sources are kept separate — no automated dedup.
