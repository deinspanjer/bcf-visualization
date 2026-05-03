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

## Repo layout (planned)

```
data/
  raw/          # source files: EPUB, exported SV/AO3/pastebin pages
  derived/      # parsed JSON committed for reproducibility
scripts/        # Python parsers (ebooklib + bs4)
web/            # static HTML/JS visualization site (GitHub Pages target)
notebooks/      # exploratory analysis
```

## Status

Phase 0 — scaffolding and raw asset collection.
