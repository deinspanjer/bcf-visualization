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

Author's note in the chapter introduced two modifications, intended to
slow the perk acquisition rate. The note isn't in either EPUB; the
canonical text was relayed via the project Discord.

**Change 1 — slower base rate.** 100 CP now requires **3000 words**
(was 2000), and rolls happen **every 200 CP** = every 6000 words (was
every 4000).

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

**Coverage in our data:** 17 600+ acquisitions occur before chapter 97
(no shadow); 11 are in or after chapter 97 (shadow active). The old
roll-by-roll xlsx stops at chapter 75, so all per-roll data we have
predates both changes. The Reference xlsx logs acquisitions through
chapter 119 but doesn't expose CP banking, so the shadow's effect can't
be measured against the rule directly without parsing chapter prose.

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
```

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
Next: static charts as a sanity gate before going interactive.
