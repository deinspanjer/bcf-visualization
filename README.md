# bcf-visualization

## ➡️ [**View the live visualization on GitHub Pages**](https://deinspanjer.github.io/bcf-visualization/) ⬅️

Visualizations and analysis of *Brockton's Celestial Forge (Worm/Jumpchain)* by LordRoustabout.

This repository is organized for quick exploration first, with deeper technical details moved into dedicated docs.

## Start here

- **Use the visualization:** [USERS.md](USERS.md)
- **Develop / maintain the pipeline:** [DEVELOPERS.md](DEVELOPERS.md)
- **Open tasks and future ideas:** [TODO.md](TODO.md)
- **Current DAW scrubber milestone notes:** [plans/daw_scrubber_v2.md](plans/daw_scrubber_v2.md)
- **Point collection/spending rules:** [docs/point_collection_and_spending_regimes.md](docs/point_collection_and_spending_regimes.md)
- **Pre-narrative history dates:** [docs/pre_narrative_history.md](docs/pre_narrative_history.md)
- **Narrative timeline (April 2011):** [docs/narrative_timeline_april_2011.md](docs/narrative_timeline_april_2011.md)
- **Derived dataset inventory:** [docs/derived_dataset_inventory.md](docs/derived_dataset_inventory.md)
- **Chart pack guide:** [docs/chart_pack_guide.md](docs/chart_pack_guide.md)
- **Roll simulation/validation notes:** [docs/roll_simulation_and_validation_notes.md](docs/roll_simulation_and_validation_notes.md)

## What this project includes

- A static, dependency-light web scrubber timeline in `web/`
- Derived story datasets in `data/derived/` (schemas in
  `data/derived/_schemas/`), with a versioned data-package manifest for
  release and Pages publishing
- Parsing, validation, and chart scripts in `scripts/`
- Static output charts in `figures/`
- A parked overhead sky prototype at `/web/?sky=1` for Phase 4
  planetarium iteration

## Source material

- Story (SV): https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/
- Story (AO3): https://archiveofourown.org/works/23949661
- Mechanics writeup (reddit): https://www.reddit.com/r/JumpChain/comments/h14tjk/the_weight_of_the_quill_variant_mechanic/
- Celestial Forge source list (pastebin): https://pastebin.com/35AJD9Lj

## Quick local run

```sh
.venv/bin/python -m http.server 8000
# open http://localhost:8000/  (root redirects to /web/)
```

The app reads `data/derived/data_package.json` first, then loads the
contracted runtime files such as `chapter_facts.json`. The data version
shown in the app combines the package build date/ordinal with the latest
BCF story chapter ordinal and descriptive chapter number.

## Data + parser notes

- Parsers are designed to be idempotent and write validated JSON outputs.
- Most workflows run from committed derived data.
- EPUB-dependent steps are documented in [DEVELOPERS.md](DEVELOPERS.md).

For parser commands, schema validation behavior, and dataset-by-dataset coverage details, use [DEVELOPERS.md](DEVELOPERS.md).

## Project status

- Phase 1: complete (raw assets + structured derivations)
- Phase 2: complete (static charts + throughput analytics)
- Phase 3: complete (interactive scrubber + deploy workflow)
- Phase 4: design/prototype iteration (parked sky view, not primary UI)

For limitations, caveats, and follow-up work, see [TODO.md](TODO.md).
