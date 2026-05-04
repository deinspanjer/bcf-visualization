# Project reference archive

This page preserves the high-signal project context that used to live in `README.md` but was too detailed for a landing page.

## Mechanics and regime history

### Original rule (chapter 1)

- 2000 words written = 100 CP earned
- Roll attempted every 100 CP earned
- Perk purchased on roll if banked CP ≥ rolled perk cost, else miss + CP banked

### Chapter 91 "The Toolkit" change

- Roll cadence changed from 100 CP/roll to 200 CP/roll.
- Words-per-CP remained 2000.
- Effective roll cadence became 4000 words per roll.

### Chapter 97 "Confrontations" changes

1. Base rate slowed from 2000 words/100 CP to 3000 words/100 CP (with ch91 cadence, this becomes 6000 words/roll).
2. Added "shadow" cooldown on 600/800-cost perk acquisitions:
   - 600-point perk → 300 CP shadow → 9000 words with zero CP banking.
   - 800-point perk → 400 CP shadow → 12000 words with zero CP banking.

### Mechanic regimes summary

| Chapters | Words / 100 CP | CP / roll | Words / roll | Notes |
|---|---|---|---|---|
| 1–91 | 2000 | 100 | 2000 | Original |
| 92–96 | 2000 | 200 | 4000 | ch91 change applied |
| 97+ | 3000 | 200 | 6000 | ch97 rate + shadow |

Coverage note: `rolls.json` directly covers chapters 1–75 under the original regime; chapters 76+ rely on derived/reconstructed evidence paths.

## In-world timeline reference

The story actively narrates **April 8–25, 2011** (14 dated events in-story), while earlier dates are backstory references.

### Backstory (not narrated)

- 2007-06-01 — Joe graduates high school
- 2007-09-01 — Joe begins engineering at Brockton University
- 2008-11-01 — Advisor death/replacement; academic and personal decline
- Jan–Mar 2009 — Relationship deterioration and reconciliation with Sabah
- 2009-04-01 — Sabah's father dies; she triggers and later becomes Parian
- Jun 2009–Aug 2010 — Depression treatment period; meds trials
- 2010-09-01 — Joe starts with Dr. Campbell; progress begins
- 2011-02-01 — Family pressure about med changes intensifies
- 2011-03-04 — Last covered Q1 therapy session; next set for Apr 16
- Mid-March 2011 — Joe changes antidepressants
- 2011-04-01 — Trigger event after family dinner
- Apr 2–7, 2011 — Joe cuts contact and prepares for cape work

### Narrated days (April 8–25, 2011)

- 2011-04-08 (Fri) — Story starts
- 2011-04-10 (Sun) — First cape outing/fight
- 2011-04-14 (Thu) — Undersiders/PRT inflection day
- 2011-04-15 (Fri) — Garment Gloves + motorcycle milestones
- 2011-04-16 (Sat) — Bakuda arc kickoff (public visibility)
- 2011-04-17 (Sun) — Weld rescue; Aisha enters workshop orbit
- 2011-04-18 (Mon) — Financial-center fight; volcano acquisition
- 2011-04-19 (Tue) — Dragon fight; first 600-point perk
- 2011-04-20 (Wed) — Undersiders debt/watch thread
- 2011-04-21 (Thu) — Workshop buildout day
- 2011-04-22 (Fri) — Crew universe/power discussion
- 2011-04-23 (Sat) — Volcano prep/surfing
- 2011-04-24 (Sun) — Somers Rock summit, public reveal
- 2011-04-25 (Mon) — Laboratorium intro; Titan AI robots

## Derived data inventory (quick reference)

| File | Purpose |
|---|---|
| `data/derived/chapters.json` | Chapter metadata and publish timeline |
| `data/derived/rolls.json` | Curator roll log (ch 1–75) including misses/banked CP |
| `data/derived/perks_catalog.json` | Curator catalog of listed perks |
| `data/derived/obtained_perks.json` | Full-story acquisition log |
| `data/derived/timeline.json` | Dated in-world events reference |
| `data/derived/chapter_sections.json` | Per-section extraction and CP-earning classification inputs |
| `data/derived/predicted_rolls.json` | Simulated roll positions from the three-regime model |
| `data/derived/roll_locations_regex.json` | Candidate roll text windows in prose |
| `data/derived/roll_text_evidence.json` | Text-backed roll/acquisition evidence snippets |
| `data/derived/roll_locations_validation.json` | Validation/discrepancy report |
| `data/derived/chapter_last_edited.json` | Threadmark last-edited metadata |
| `data/derived/extracted_perks.json` | Chapter-footer extracted author-canonical perk list |
| `data/derived/perk_directory.json` | Joined directory view for visualization lookups |
| `data/derived/chapter_facts.json` | Web visualization backbone |

## Chart pack summary (`figures/`)

- `publish_pace.png` — cumulative words vs publish date, with mechanic-change context.
- `throughput_by_year.png` — per-year pace small multiples.
- `throughput_by_regime.png` — regime comparison across throughput metrics.
- `words_per_perk.png` — words between paid acquisitions over time.
- `monthly_throughput.png` — monthly chapters/words/chapter-size panels.
- `rolls_per_chapter.png` — curator-range hit/miss distribution.
- `acquisitions_per_chapter.png` — paid vs free acquisitions by chapter.
- `constellation_growth.png` — constellation growth small multiples.
- `time_dilation.png` — in-world day progression vs real-world time and words.

## Regime simulation + validation notes

- `predict_rolls.py` models CP/roll progression across the three rule regimes using derived section-level CP-earning word counts.
- `find_roll_locations.py` and `find_text_backed_rolls.py` locate prose evidence around predicted offsets.
- `validate_roll_locations.py` compares predicted/located roll evidence against chapter-level facts.

## Spot-check snapshot (historical summary)

Primary-vs-primary checks passed; soft curator-data quality findings historically included:

- missing catalog rows for some rolled acquisitions,
- occasional cost disagreements,
- cosmetic naming variants,
- and a small number of chapter-level paid-acquisition count mismatches in overlap ranges.

For current, actionable reconciliation work, use `TODO.md`.
