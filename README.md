# bcf-visualization

Visualizations and analysis of *Brockton's Celestial Forge (Worm/Jumpchain)* by LordRoustabout — a long-running fanfic that uses a word-count-driven gacha mechanic to award the protagonist new abilities over time.

This is an exploratory project; the plan is iterative and not yet locked down.

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

### Chapter 97 "Confrontations" rule changes

Author's note in the chapter introduced modifications intended to slow
the perk acquisition rate. The note isn't in either EPUB; the canonical
text was relayed via the project Discord.

**Change 1 — slower base rate.** 100 CP now requires **3000 words**
(was 2000).

**Change 2 — recovery shadow on 600/800 perks.** After a 600- or
800-point perk is acquired, *no CP is banked at all* until words equal
to *half-the-perk's-cost worth of CP at the new rate* have been
written:

- 600-point perk → 300 CP shadow → 9000 words of zero earning
- 800-point perk → 400 CP shadow → 12000 words of zero earning

Words written during the shadow advance the story but don't count
toward the next roll. After the shadow ends, accumulation resumes at
the new base rate.

The author noted further modifications might follow as more
constellations clear; this is the only documented one so far.

### Roll cadence (open question)

The chapter 97 author note also describes the *prior* roll cadence as
"rolls every 200 points," in tension with chapter 1's "roll attempted
every 100 CP" and the curator's xlsx rules box ("Every 100 Points
gained, LordRoustabout will stop writing and roll dice"). Empirical
analysis of `rolls.json` settles this for the curator-covered range:

> Across 487 consecutive numbered-roll pairs in chapters 1–75, **472
> (97%) differ by exactly 100 CP**. The 15 outliers are sheet typos or
> cluster-purchase artifacts. The 100 CP cadence is stable across
> every roll-number sub-range (1–100, 100–200, …, 400–503).

Chapters 76–96 are not covered by `rolls.json`, so any silent shift
between the curator's last data point and the ch97 announcement would
fall in that gap. Two interpretations:

1. **Trust the data:** the cadence stayed at 100 CP/roll through
   chapter 96, and the ch97 change moved it to 200 CP/roll along with
   the words-per-CP rate. The author's wording in the ch97 note is a
   simplification.
2. **Trust the author note:** the cadence shifted to 200 CP/roll
   somewhere in chapters 76–96 and the ch97 change is words-per-CP
   only. We can't verify this from current data.

Phase 2 modeling defaults to interpretation 1 (direct evidence), with
the caveat that the regime in chapters 76–96 is empirically unknown.

**Coverage in our data:** 17 600+ acquisitions occur before chapter 97
(no shadow); 11 are in or after chapter 97 (shadow active). The old
roll-by-roll xlsx stops at chapter 75, so all per-roll data we have
predates both changes. The Reference xlsx logs acquisitions through
chapter 119 but doesn't expose CP banking, so the shadow's effect
can't be measured against the rule directly without parsing chapter
prose.

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

## Running the parsers

```sh
pip install -r requirements.txt
python3 scripts/parse_threadmarks.py
python3 scripts/parse_rolls.py
python3 scripts/parse_reference.py   # obtained_perks + timeline
python3 scripts/spot_check.py        # cross-source consistency check
python3 scripts/make_charts.py       # static charts -> figures/
```

## Phase 2: static charts

`scripts/make_charts.py` reads only `data/derived/*.json` and writes
five PNGs to `figures/`. They serve as a sanity gate over the parsed
data and surface findings worth keeping in mind:

| File | What it shows |
|---|---|
| `figures/publish_pace.png` | Cumulative word count vs real-world publish date. ~1,300 words/day average across 5+ years; visible acceleration through 2024–2026. |
| `figures/rolls_per_chapter.png` | Hits vs misses per chapter for chapters 1–75 (curator coverage). Hit rate ~38% (191/496); the chapter 41 outlier is the Felyne Comrade introduction with many free-bonus perks. |
| `figures/acquisitions_per_chapter.png` | Paid vs free perks per chapter for the full story. The chapter 97 mechanic-change line shows a visible flattening of bar heights afterward. |
| `figures/constellation_growth.png` | Stacked area of cumulative perks per constellation through chapter 75. Toolkits, Knowledge, and Quality dominate; Capstone activates around chapter 64. |
| `figures/time_dilation.png` | Real-world publish date by chapter (top) alongside in-world dated events (bottom). 2096 real-world days of writing cover 1424 in-world days; 13 of the 26 dated events are within a 17-day window in April 2011. |

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

## Status

Phase 1 complete (raw assets, structured derivations, schemas, spot-check).
Phase 2 complete (five static charts as a sanity gate; see above).
Next: interactive scrubber timeline (Phase 3).

## Future work

Captured here so they aren't lost between phases:

- **Deterministic word-count → roll matching.** Walk the EPUB chapter
  prose, accumulate exact running word counts, and at each predicted
  threshold (100 CP under the original rule, 200 CP after ch97, with
  shadow blocks subtracted) read the surrounding text for narrative
  references to a roll occurring. Would let us:
  - verify or falsify the ch1–96 cadence ambiguity (whether rolls
    silently shifted from 100 to 200 CP/roll somewhere in 76–96)
  - cross-validate the Reference xlsx's chapter-97-onward acquisitions
    against the actual prose
  - locate the precise word offset of every roll, useful for
    visualization (a true word-level timeline rather than chapter-level)
  - extract roll-by-roll banked CP for chapters 76+ where the curator
    stopped maintaining
- **Reconciliation pass on the 31 catalog gaps and 56 cosmetic name
  variants** before any Phase 2 chart that joins rolls.json against
  perks_catalog.json.
- **Parsers for the remaining Reference xlsx sheets** (Possible Perks
  + probabilities, Future Capstone Perks, Soundtrack/Felyne perks,
  Excluded Media) when their data becomes relevant to a specific
  visualization.
