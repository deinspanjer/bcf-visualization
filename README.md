# bcf-visualization

Visualizations and analysis of *Brockton's Celestial Forge (Worm/Jumpchain)* by LordRoustabout — a long-running fanfic that uses a word-count-driven gacha mechanic to award the protagonist new abilities over time.

This is an exploratory project; the plan is iterative and not yet locked down.

## Documentation map

- [USERS.md](USERS.md) — how to run and use the visualization.
- [DEVELOPERS.md](DEVELOPERS.md) — data pipeline, local development, and maintenance rules.
- [TODO.md](TODO.md) — current future work and deferred design questions.
- [plans/daw_scrubber_v2.md](plans/daw_scrubber_v2.md) — milestone notes for the DAW scrubber work.

## Source material

- Story (SV): https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/
- Story (AO3): https://archiveofourown.org/works/23949661
- Mechanics writeup (reddit): https://www.reddit.com/r/JumpChain/comments/h14tjk/the_weight_of_the_quill_variant_mechanic/
- Celestial Forge source list (pastebin): https://pastebin.com/35AJD9Lj

## Mechanics

### Original rule (per chapter 1)

- 2000 words written = 100 CP earned
- Roll attempted every 100 CP earned
- Perk purchased on roll if banked CP ≥ rolled perk's cost, else miss + CP banked

### Chapter 91 "The Toolkit" rule change

Author's note in the chapter:

> With the perk from this chapter, all non-repeatable 100 point perks
> in the tables have been obtained. As there are no longer any unique
> powers that can be gained for 100 points, I will be changing the
> methodology and rolling for powers every 200 points, meaning rolls
> will occur every 4,000 words. The rate of point gain will remain the
> same, but the lower number of rolls will mean fewer rolls will occur
> where there is no chance of any power being obtained.

So the ch91 change moved the cadence from 100 CP/roll to **200 CP/roll**.
Words-per-CP stayed at 2000. Effective: rolls every 4000 words instead
of every 2000.

The trigger perk was **"The Toolkit" (Sabaton)** at chapter 91, the
last non-repeatable 100-point perk in the catalog. Personal Reality
100-CP perks are repeatable (Workshop, etc.) and cluster bonuses (Star
Trek "Skills:", Percy Jackson "Minor Blessing X") aren't unique
acquisitions, so both continued to appear after ch91 without
contradicting the rule.

### Chapter 97 "Confrontations" rule changes

Second author's note, six chapters later, layered on more changes:

**Change 1 — slower base rate.** 100 CP now requires **3000 words**
(was 2000). Combined with the ch91 cadence, rolls now happen every
6000 words.

**Change 2 — recovery shadow on 600/800 perks.** After a 600- or
800-point perk is acquired, *no CP is banked at all* until words equal
to *half-the-perk's-cost worth of CP at the new rate* have been
written:

- 600-point perk → 300 CP shadow → 9000 words of zero earning
- 800-point perk → 400 CP shadow → 12000 words of zero earning

Words written during the shadow advance the story but don't count
toward the next roll. After the shadow ends, accumulation resumes at
the new base rate.

The ch97 note's "rolls happen every 4000 words" reference to the prior
state confirms that the ch91 cadence change had been in effect since
chapter 91 (matching the empirical roll log evidence for ch 1–75 of
100 CP/roll, with the post-ch91 cadence change happening in the gap
between the curator's last data point and ch97).

The author noted further modifications might follow as more
constellations clear; ch91 and ch97 are the only documented ones so far.

### Mechanic regimes summary

| Chapters | Words / 100 CP | CP / roll | Words / roll | Notes |
|---|---|---|---|---|
| 1 – 91   | 2000 | 100 | 2000 | original |
| 92 – 96  | 2000 | 200 | 4000 | ch91 change applied |
| 97 –     | 3000 | 200 | 6000 | ch97 changes applied + shadow on 600/800 |

**Coverage in our data:** the curator's roll log (`rolls.json`) covers
chapters 1–75 entirely under the original regime. `obtained_perks.json`
covers the full story but logs only successful acquisitions, not roll
attempts or banked CP — so the ch92–96 and ch97+ regimes aren't
directly measurable from our derived data without parsing the EPUB
prose. 17 600+ acquisitions occur before chapter 97 (no shadow); 11
are in or after chapter 97 (shadow active).

## In-world timeline

Reference list. The story actively narrates April 8–25, 2011 (17 days,
14 dated events). Earlier dates are backstory — referenced in dialogue
and exposition but not narrated time. Both lists come from the
Reference xlsx "Timeline of Events" sheet, with attribution: pre-story
entries provided by the author, in-story entries compiled by Whamodyne.

### Backstory references (not narrated)

- **2007-06-01** — Joe graduates from high school
- **2007-09-01** — Joe begins studying engineering at Brockton University
- **2008-11-01** — Joe's faculty advisor dies and is replaced by an associate professor; the combined effect of the death and bad advice causes his academics and personal life to suffer
- **January–March, 2009** — Joe's relationship with Sabah deteriorates, including a public blow up, six-week absence, and her ultimate apology and return
- **2009-04-01** — Sabah's father dies, causing her to trigger; she transfers from Engineering to Fashion and begins operating as Parian
- **June, 2009 – August 2010** — Joe attempts treatment for his depression with little progress; multiple medications are tried before a stable combination is found, though it badly affects his sleep
- **2010-09-01** — Joe begins seeing Dr. Campbell and making progress on strategies for his depression; moves into the city and starts working part-time
- **2011-02-01** — Joe's mother learns about potential changes to his medication after speaking with his psychiatrist and begins heavily advocating for the idea
- **2011-03-04** — Joe has the final therapy session with Dr. Campbell that will be covered by his Q1 insurance, with the next session booked for April 16
- **Mid-March, 2011** — Joe is convinced to change to a new antidepressant
- **2011-04-01** — Joe begins the new medication and attends a family dinner with his parents and one of his sisters; he triggers, leaves the house, and walks home
- **April 2–7, 2011** — Joe cuts off contact with his family and begins planning and training to begin work as a cape

### Narrated in-story days (April 8–25, 2011)

- **2011-04-08 (Fri)** — Story begins
- **2011-04-10 (Sun)** — Joe goes out as a cape for the first time, encounters Oni Lee then the Undersiders (Joe's first fight)
- **2011-04-14 (Thu)** — Joe delivers the knives to the Undersiders in the morning; bank robbery at noon; Joe heals Amy in the afternoon; PRT learns of Joe for the first time
- **2011-04-15 (Fri)** — Joe gets Garment Gloves on his morning run; passes motorcycle DMV test; gets a motorcycle that afternoon
- **2011-04-16 (Sat)** — Dr Campbell appointment; ABB starts the bombing spree; Joe fights Bakuda, Uber and Leet rescuing the Undersiders (second fight, first public appearance)
- **2011-04-17 (Sun)** — Joe rescues Weld from the bottom of Brockton Bay; chats with Director Armstrong; Aisha follows him home into his workshop
- **2011-04-18 (Mon)** — Garment Gloves at Protectorate gym; Joe rescues Aisha from ABB financial center, fights Uber and Leet, repairs/upgrades other tinkers' work mid-combat (third fight); acquires a volcano; first named object (Ren)
- **2011-04-19 (Tue)** — Acquires Veritech VF-2SS Valkyrie II; meets Taylor in the library; fights and defeats Dragon; first 600-point perk (Master Craftsman)
- **2011-04-20 (Wed)** — Talks with Undersiders about debt; gives them omnitool watches; Garment Gloves visits the bank; Joe researches Natural Alchemy
- **2011-04-21 (Thu)** — Joe and Garment make new boots and combat uniforms; mantic energy circuit through the volcano base
- **2011-04-22 (Fri)** — Workshop crew talks over Joe's powers and known fictional universes
- **2011-04-23 (Sat)** — Joe, Tetra and Garment surf the volcano at dawn; Workshop Crew preparation
- **2011-04-24 (Sun)** — Joe attends the Summit at Somers Rock, takes the Celestial Forge public; states he wants peace and no civilian or recovery work
- **2011-04-25 (Mon)** — Joe introduces Aisha to the Laboratorium; gets Titan robots with AI; story currently extends through this day

## Repo layout

```
data/
  raw/                         # source files: EPUB, MHT exports, curator xlsx
  derived/                     # parsed JSON committed for reproducibility
    _schemas/                  # JSON Schema (Draft 2020-12) for each derived file
scripts/                       # parsers + cross-source spot-check
```

## Derived datasets

All produced by scripts in `scripts/`. Each parser is idempotent,
reads only from `data/raw/`, and validates its output against the
matching schema in `data/derived/_schemas/` before writing -
structural drift fails the parser rather than silently shipping
malformed data.

| File                              | From                        | Coverage |
|-----------------------------------|-----------------------------|----------|
| `data/derived/chapters.json`      | 8 SV threadmark MHTs        | 194 chapters, 2020-07 → 2026-04 |
| `data/derived/rolls.json`         | first curator xlsx, "List of Rolls & Perk Order" | 503 rolls (with banked CP, misses), chapters 1–75 |
| `data/derived/perks_catalog.json` | first curator xlsx, "Complete List of Perks"     | 651 perks across 14 constellations |
| `data/derived/obtained_perks.json`| Reference xlsx, "Obtained Perks"                 | 504 acquisitions across 127 chapters (full-story, EPUB seq 1–192) |
| `data/derived/timeline.json`      | Reference xlsx, "Timeline of Events"             | 26 dated entries June 2007 → April 25 2011 (author + Whamodyne attribution) |
| `data/derived/predicted_rolls.json` | regime simulation over chapters.json + obtained_perks.json + chapter_sections.json | predicted roll positions (word offset + chapter), with per-chapter comparison vs actual for the curator-covered range |
| `data/derived/roll_locations_regex.json` | regex/text-window pass over EPUB prose near predicted roll positions | candidate text locations for roll evidence |
| `data/derived/roll_text_evidence.json` | prose-backed roll-location extraction | text snippets and evidence metadata for matched roll events |
| `data/derived/roll_locations_validation.json` | validation of predicted/located rolls against chapter facts | chapter-level coverage and discrepancy findings |
| `data/derived/chapter_last_edited.json` | SV threadmark MHTs | last-edited timestamps for chapters where SV exposes them |
| `data/derived/chapter_sections.json` | walked EPUB chapter HTML, scanned each section's first ~3000 chars | per-section POV classification, CP-earning word count, classification confidence, ~432 sections across 194 chapters |
| `data/derived/extracted_perks.json` | parsed "Jumpchain abilities this chapter:" footer of each EPUB chapter | 481 author-canonical perk listings (name, source, cost, description) keyed by chapter |
| `data/derived/perk_directory.json` | Reference xlsx, "Unabridged List" (Status != Excluded), enriched from perks_catalog.json + obtained_perks.json | 407 perks (one row per perk; multi-perk rows expanded), 252 matched to obtained acquisitions (~62%); spot-check surfaces obtained acquisitions not represented in the directory (mostly free bonus perks the Unabridged List doesn't enumerate) |
| `data/derived/chapter_facts.json` | built from derived and manual inputs above | visualization backbone: chapters, rolls/acquisitions, sections, cooldown shadows, URLs, and display-ready facts |
| `data/manual/section_classifications.json` | rule-based + manual classification of each section's CP-earning status | 432 sections classified (144 MC, 288 non-MC); the rule set is in `scripts/build_section_classifications.py` |
| `data/manual/perk_constellation_overrides.json` | hand-curated constellation classification for the 54 perks the catalog couldn't classify | each entry has a one-line reason; pushes obtained_perks classification coverage from 89% to 100% |

## Running the parsers

```sh
pip install -r requirements.txt
python3 scripts/parse_threadmarks.py
python3 scripts/parse_rolls.py
python3 scripts/parse_reference.py             # obtained_perks + timeline
python3 scripts/extract_chapter_sections.py    # chapter_sections + extracted_perks  (needs EPUB)
python3 scripts/build_section_classifications.py  # manual section classifications -> data/manual
python3 scripts/build_perk_directory.py        # Unabridged List + cost/acquired joins -> perk_directory
python3 scripts/predict_rolls.py               # regime simulation -> predicted_rolls
python3 scripts/extract_last_edited.py         # SV threadmark edit metadata -> chapter_last_edited
python3 scripts/find_roll_locations.py         # text windows around predicted roll positions
python3 scripts/find_text_backed_rolls.py      # prose evidence for roll/acquisition locations
python3 scripts/validate_roll_locations.py     # cross-check located rolls
python3 scripts/build_chapter_facts.py         # final visualization backbone
python3 scripts/spot_check.py                  # cross-source consistency check
python3 scripts/make_charts.py                 # static charts -> figures/
```

`extract_chapter_sections.py` reads the source EPUB
(`data/raw/Brocktons_Celestial_Forge.epub`) to compute per-section
classification and CP-earning word counts. `predict_rolls.py` then
reads only the derived `chapter_sections.json`, so the EPUB is only
needed at extraction time. The other parsers don't need the EPUB at
all; if it's missing, `predict_rolls.py` and `extract_chapter_sections.py`
exit with a clear error and `spot_check.py` skips the corresponding
check.

The EPUBs themselves are not committed to this repo (gitignored under
`data/raw/*.epub`) — they are the author's copyrighted prose. To
re-run the EPUB-dependent parsers, download an export from the SV or
AO3 URLs in **Source material** above and place it at
`data/raw/Brocktons_Celestial_Forge.epub`. The derived JSON in
`data/derived/` was produced from those sources and is sufficient for
all downstream analysis and the scrubber.

## Phase 2: static charts and throughput analytics

`scripts/make_charts.py` reads only `data/derived/*.json` and writes
PNGs to `figures/`. Charts lean on Tufte's principles: minimal grids,
range-frame axes, direct labelling rather than legends, gray for
context, saturated color only where the chart's argument lives.
Stacked area is avoided in favor of small multiples.

| File | What it shows |
|---|---|
| `figures/publish_pace.png` | Cumulative word count vs real-world publish date, with the three mechanic regimes shaded. Year-end totals labelled directly on the curve; ch91 and ch97 rule changes labelled at top. ~1,300 words/day average across 5+ years. |
| `figures/throughput_by_year.png` | Small multiples (one panel per calendar year, same axes). Each panel's slope is the year's writing pace; thin gray lines show all other years for context. Pace declined steadily 2020 → 2025, with a partial uptick in 2026. |
| `figures/throughput_by_regime.png` | Cleveland-style dot plot comparing four throughput metrics across the three mechanic regimes. Headline: words spent per perk acquired tripled from regime 1/2 (~4,200) to regime 3 (~13,300). Words/day and chapters/month both declined ~50% from regime 1 to regime 3. |
| `figures/words_per_perk.png` | Per-acquisition scatter showing words written between consecutive paid acquisitions, with a 21-acquisition rolling median. ch91 and ch97 marked. The rolling median was stable around 5,000 words/perk through mid-2023, then climbed steeply post-ch97 to 20k+ words/perk by 2025 — the regime-3 effect at full resolution. |
| `figures/monthly_throughput.png` | Three-panel monthly bar chart: chapters published, words published, and median chapter word count, all binned by month. Bars colored by regime (blue = 1, brown = 2, magenta = 3). The 2020 launch spike (26 chapters in July) is visible; the post-ch91/ch97 cadence drop is clear; chapter sizes notably grew in regime 3 (median rises from ~10k to ~16k). |
| `figures/rolls_per_chapter.png` | Hits vs misses per chapter for chapters 1–75 (curator coverage). Hit rate ~38% (191/496); chapter 41 outlier is the Felyne Comrade introduction with many free-bonus perks. |
| `figures/acquisitions_per_chapter.png` | Paid vs free perks per chapter for the full story. The chapter 97 mechanic-change line shows a visible flattening of bar heights afterward. |
| `figures/constellation_growth.png` | Small multiples (one panel per constellation, same axes). Each panel shows that constellation's cumulative-acquisition growth across chapters 1–75; the largest constellation (Toolkits) is overlaid in light gray as context. Capstone barely moves until ~ch 64; Personal Reality jumps abruptly near ch 75. |
| `figures/time_dilation.png` | In-world day progression vs real-world days (left) and cumulative words (right), sharing a y-axis. The L-shape is the dilation: the first 11 in-world days unfold in <130 real-world days; the curve flattens dramatically after that as each remaining in-world day takes hundreds more days of writing. Chapter mapping is approximate. |

### Word-count throughput by year

| Year | Chapters | Words | Span (days) | Words / active day | Median words / chapter |
|------|---------|------:|------------:|-------------------:|----------------------:|
| 2020 | 45 | 614,100 | 165 | 3,722 | 13,000 |
| 2021 | 34 | 589,000 | 351 | 1,678 | 17,000 |
| 2022 | 44 | 453,200 | 351 | 1,291 | 10,000 |
| 2023 | 26 | 353,300 | 317 | 1,115 | 13,000 |
| 2024 | 22 | 314,100 | 352 |   892 | 14,000 |
| 2025 | 17 | 268,500 | 344 |   781 | 16,000 |
| 2026 |  6 | 116,000 |  91 | 1,275 | 19,000 |

2020 was the peak (lockdown-era launch). Pace declined steadily through
2025 (≈5× slowdown from 3,722 → 781 words/day), with 2026 showing a
modest recovery so far on partial data.

### Word-count throughput by mechanic regime

| Regime | Chapters | Words | Span (days) | Words / day | Acquisitions | Words / acquisition |
|--------|---------:|------:|------------:|------------:|-------------:|--------------------:|
| 1 (ch 1–91, original) | 128 | 1,702,700 | 935 | 1,821 | 402 | 4,236 |
| 2 (ch 92–96, ch91 cadence) | 13 | 167,200 | 148 | 1,130 | 39 | 4,287 |
| 3 (ch 97+, rate + shadow) | 53 | 838,300 | 987 |   849 | 63 | **13,306** |

The headline finding: the ch97 rule changes more than tripled the
words-per-acquisition (4,236 → 13,306), which is exactly the slowing
effect the author's note said the changes were intended to produce.
The author's writing pace also dropped (1,821 → 849 words/day), so
both the rules and the natural pace contributed to the overall
slowdown of perk acquisitions in regime 3.

## Spot-check

`scripts/spot_check.py` cross-references the derived data against
primary sources (the EPUB and the threadmark MHTs). Hard-fail
conditions are reserved for primary-vs-primary disagreement; data
quality issues internal to the curator's xlsx (catalog gaps, cosmetic
naming variants, roll-pace deviations from "100 CP / 2000 words") are
surfaced as informational warnings.

Current state: hard checks pass. Soft findings (curator data quality):
- 31 perks acquired in rolls without a catalog entry
- 1 roll-vs-catalog cost disagreement (Technosorcery: rolls=400, old
  catalog=300; Reference xlsx confirms 400)
- 56 cosmetic name variants between rolls and catalog
- 7 chapters disagree on paid-perk count between rolls.json and
  obtained_perks for the chapter 1–75 overlap range (98% total
  agreement: 225 vs 229 paid acquisitions)
- 18 of 82 chapters deviate >30% from the original "100 CP / 2000
  words" rule (uncorrected for the chapter-97 mechanic change)

Phase 2 consumers should be aware of these.

## Phase 3: interactive progression visualization

`web/` contains a static, dependency-free single-page site that lets
you review the full story as a DAW-style word-axis timeline. The
scrubber renders real-world publish dates, chapter boundaries, POV /
section spans, recovery cooldowns, roll/acquisition dots, and a word
axis. Dots are constellation-colored and cost-sized; free perks render
as tight child clusters below their purchased perk. The readout and
panels show cumulative state through the current word position:
chapters, words, paid/free perks, hits, misses/unknowns, acquired
counts by constellation, and the most recent 10 acquisitions.

The playhead follows the current word position while playing. Manual
horizontal scrolling is respected while paused; during playback, a
manual scroll holds for three seconds and then gradually catches back
up. If playback is started from the end, the visualization jumps back
to the beginning before replaying. Scrubbing works by mouse drag,
click-anywhere on the track, touch drag, or keyboard (arrow keys,
PageUp/Down, Home/End).

To run locally:

```sh
python3 -m http.server 8000
# open http://localhost:8000/  (root redirects to /web/)
```

The page reads `data/derived/chapter_facts.json`. No build step, no
dependencies, no framework — everything is plain HTML + CSS + vanilla
JavaScript so it can be served from GitHub Pages or any static host.

### GitHub Pages deployment

`.github/workflows/deploy-pages.yml` builds a publishable subset
(`web/`, `data/derived/`, `figures/`, plus the root redirect and
`.nojekyll`) and uploads it via the official `actions/deploy-pages`
flow. The workflow explicitly excludes `data/raw/` so the source
EPUBs and MHTs aren't accidentally published.

The workflow is set to **manual trigger only** (`workflow_dispatch`).
To deploy:

1. In repository **Settings → Pages**, set "Build and deployment"
   source to "GitHub Actions".
2. **Actions → Deploy scrubber to GitHub Pages → Run workflow**.

To enable automatic deploys on every push to main, add a `push:`
trigger to the workflow's `on:` block.

The deployed site will be reachable at the standard
`<owner>.github.io/<repo>/` URL.

Known limitations and future work are tracked in [TODO.md](TODO.md).

## Status

Phase 1 complete (raw assets, structured derivations, schemas, spot-check).
Phase 2 complete (Tufte-style static charts and throughput analytics).
Phase 3 complete (interactive scrubber timeline + GitHub Pages deploy ready).
Open: source-prose decommit (pending permission) and the future work
tracked in [TODO.md](TODO.md).

## Regime simulation

`scripts/predict_rolls.py` simulates CP accumulation through the
documented three-regime model (rate, cadence, 600/800 shadow) and
predicts roll positions across the full story. It reads only the
derived `chapter_sections.json`; the EPUB is parsed once upstream by
`extract_chapter_sections.py`.

`extract_chapter_sections.py` walks each chapter's HTML, splits it
on `<p><strong>X</strong></p>` markers into 432 sections across 194
chapters, and classifies each section by combining:

- **Header rule** — *Preamble/Addendum/Interlude X* (non-MC unless X
  is "Joe"); *Jumpchain abilities*, *New Abilities for*, *Author's
  Note* (always non-MC).
- **Content scan** — first ~3000 characters of the section, with
  pronoun ratios (first-person vs third-person) and structural markers
  (PHO forum posts, newspaper articles, meeting reports).
- **Implicit-section convention** — a chapter's content before any
  marker is always MC (this is the chapter body; the first paragraph
  may be a third-person scene-setter, but the section as a whole is
  the MC narrative).

Each section gets a `confidence` of high/medium/low. Currently
high=362, medium=55, low=15. Of the 432 sections, 81% of total words
(2.17M of 2.69M) fall into MC sections that count toward CP.

Cross-validating against the actual roll log for chapters 1–75:

- **Predicted: 509 roll attempts. Actual: 496. Delta: +13 (+2.6%).**

Down from +18% (header-only) → +10% (header markers + section walk)
→ +3.8% (rule-based content scan) → +2.6% with the per-section
manual classifications in `data/manual/section_classifications.json`.
Remaining variance is bookkeeping: the curator's `rolls.json` tags
some rolls to entire-interlude chapters (43.1, 46.1, 55.1, 58.2, 74.2)
that per the author's rule shouldn't earn CP — likely the author
batches rolls into the next chapter's window during writing.

For chapters 76+ where no actual roll log exists, the simulation
predicts roll positions; future work could validate by reading the
EPUB prose at each predicted offset and looking for a narrative roll
reference.

`extract_chapter_sections.py` also extracts the perk listings from
the *"Jumpchain abilities this chapter:"* footer of each chapter
into `data/derived/extracted_perks.json` (481 perks). This is an
independent author-canonical record — if the curator's
`obtained_perks.json` is missing a constellation classification, the
extracted perks have its name, source, cost, and description, which
can be used to fill catalog gaps. Of the 54 acquisitions still
unclassified after item-2 reconciliation, 49 are present in the
extracted perks with full descriptions ready for further enrichment.

## Future work

Captured here so they aren't lost between phases:

- **Tighten predicted-roll accuracy from +3.8% toward 0%.** Use the
  15 remaining low-confidence sections from `chapter_sections.json`
  (mostly all-caps in-story news headlines and `***` scene-break
  markers) as a manual review list. Also worth investigating whether
  free-perk grants in clusters affect the effective CP rate.
- **Reconciliation pass on the remaining 54 unclassified perks**
  (entire jumps like Bloodborne, Transformers, Lord of Light, KSP
  that the catalog doesn't enumerate at all). Would push the
  scrubber's by-constellation panel from 89% to ~100% coverage.
- **Parsers for the remaining Reference xlsx sheets** (Possible Perks
  + probabilities, Future Capstone Perks, Soundtrack/Felyne perks,
  Excluded Media) when their data becomes relevant to a specific
  visualization.
