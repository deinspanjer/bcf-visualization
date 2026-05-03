# bcf-visualization

Visualizations and analysis of *Brockton's Celestial Forge (Worm/Jumpchain)* by LordRoustabout — a long-running fanfic that uses a word-count-driven gacha mechanic to award the protagonist new abilities over time.

This is an exploratory project; the plan is iterative and not yet locked down.

## Source material

- Story (SV): https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/
- Story (AO3): https://archiveofourown.org/works/23949661
- Mechanics writeup (reddit): https://www.reddit.com/r/JumpChain/comments/h14tjk/the_weight_of_the_quill_variant_mechanic/
- Celestial Forge source list (pastebin): https://pastebin.com/35AJD9Lj

## Mechanics (per chapter 1)

- 2000 words written = 100 CP earned
- Roll triggered every 100 CP earned
- Power purchased on roll if affordable, otherwise CP banked

### Perk shadow (introduced in chapter 97 "Confrontations")

A modification to the base mechanic, introduced when the first 600-point
perk after a long gap was acquired. Source: author commentary on the
Discord server (the announcement is not in either EPUB).

- Applies only to **600-** and **800-point** perks
- After acquiring such a perk, no new CP is earned for the next
  *half-the-perk's-cost* worth of "shadow" CP
- A 600-point perk produces a 9k-word shadow (3000 words per 100 CP
  shadow); an 800-point perk produces a 12k-word shadow
- Pre-chapter-97 600+ acquisitions are not retroactively shadowed

In our data: 17 600+ acquisitions occur before chapter 97 (no shadow);
11 occur in or after chapter 97 (shadow active). The curator's
roll-by-roll xlsx stops at chapter 75, so all roll data we have
predates the shadow mechanic. The Reference xlsx covers acquisitions
through chapter 119 but doesn't break down per-roll CP, so the shadow's
exact effect can't be measured directly without parsing chapter prose.

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
| `data/derived/rolls.json`         | curator xlsx, "List of Rolls & Perk Order" | 503 rolls, chapters 1–75 |
| `data/derived/perks_catalog.json` | curator xlsx, "Complete List of Perks"     | 651 perks across 14 constellations |
| `data/derived/timeline.json`      | Whamodyne post (sv_page_0233.mht)          | 15 in-world days through ch 93 |

## Running the parsers

```sh
pip install -r requirements.txt
python3 scripts/parse_threadmarks.py
python3 scripts/parse_rolls.py
python3 scripts/parse_timeline.py
python3 scripts/spot_check.py        # cross-source consistency check
```

## Spot-check

`scripts/spot_check.py` cross-references the derived data against
primary sources (the EPUB and the threadmark MHTs). Hard-fail
conditions are reserved for primary-vs-primary disagreement; data
quality issues internal to the curator's xlsx (catalog gaps, cosmetic
naming variants, roll-pace deviations from "100 CP / 2000 words") are
surfaced as informational warnings.

Current state: hard checks pass; the secondary source has 31 perks
acquired in rolls without a catalog entry, 1 roll-vs-catalog cost
disagreement, and 56 cosmetic name variants. Phase 2 consumers should
be aware of these.

## Status

Phase 1 complete (raw assets, structured derivations, schemas, spot-check).
Next: static charts as a sanity gate before going interactive.
