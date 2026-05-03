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

## Repo layout

```
data/
  raw/          # source files: EPUB, MHT exports, curator xlsx
  derived/      # parsed JSON committed for reproducibility
scripts/        # Python parsers (stdlib + openpyxl)
```

## Derived datasets

All produced by scripts in `scripts/`. Each parser is idempotent and
reads only from `data/raw/`; rerun any parser to regenerate its output.

| File                              | From                        | Coverage |
|-----------------------------------|-----------------------------|----------|
| `data/derived/chapters.json`      | 8 SV threadmark MHTs        | 194 chapters, 2020-07 → 2026-04 |
| `data/derived/rolls.json`         | curator xlsx, "List of Rolls & Perk Order" | 503 rolls, chapters 1–75 |
| `data/derived/perks_catalog.json` | curator xlsx, "Complete List of Perks"     | 651 perks across 14 constellations |
| `data/derived/comments.json`      | curator xlsx, "Comment Analysis"           | per-chapter AO3+SV stats; AO3 last_checked 12/5/23, SV 2/23/25 |
| `data/derived/timeline.json`      | Whamodyne post (sv_page_0233.mht)          | 15 in-world days through ch 93 |

## Running the parsers

```sh
pip install -r requirements.txt
python3 scripts/parse_threadmarks.py
python3 scripts/parse_rolls.py
python3 scripts/parse_comments.py
python3 scripts/parse_timeline.py
```

## Status

Phase 1 complete (raw asset collection + structured derivations).
Next: static charts as a sanity gate before going interactive.
