# Hand-Curated Corpus Analysis Report

**Purpose:** This report characterizes the 118-chapter hand-curated exemplar corpus
(`data/manual/chapter_roll_overrides.json`, mined into `data/derived/exemplar_index.json`
by `scripts/build_exemplar_index.py`) so that Phase 3's agent curation prompt design has
a concrete, statistics-grounded picture of "what a well-formed hand-curated chapter looks
like" before it starts writing extraction prompts for the ~80 remaining chapters.

**Sourcing constraint (D-04):** Every number below is read directly from
`data/derived/exemplar_index.json`'s `statistics` block — nothing here is recomputed
independently, and nothing here was derived by reading the epub. The one illustrative
quote in this report (§3) is copied verbatim from an `evidence_quotes[].text` entry
already committed in `data/manual/chapter_roll_overrides.json` (chapter 67, roll 0) — no
epub prose was opened to produce this document.

---

## 1. Overview

The exemplar index covers all **118** hand-curated chapters in
`data/manual/chapter_roll_overrides.json`. Each chapter is tagged with the CP-earning
regime(s) it falls under, sourced from the pipeline's existing `point_calculation_regime`
computation (never re-derived by the mining code, per D-01):

| Regime | Chapter count |
|---|---|
| 1 | 101 |
| 2 | 9 |
| 3 | 9 |

Regime 1 dominates the curated corpus (101 of 118 chapters, ~85.6%); regimes 2 and 3 are
much thinner slices (9 chapters / ~7.6% each). One chapter — **97** — straddles a
mid-chapter regime transition and is dual-tagged; see §6 for how the index represents it.

This skew matters for Phase 3 exemplar selection: same-regime retrieval (D-06,
`scripts/query_exemplars.retrieve()`) for a target chapter in regime 2 or 3 draws from a
pool of only 9 hand-curated chapters (10 if the boundary chapter counts for both), versus
101 for regime 1. Prompt design should expect thinner, more repetitive exemplar sets when
curating regime-2/3 chapters, and should not assume retrieval will always return a large
`k`.

## 2. Roll-Shape Distribution

The corpus contains **681** total roll records across the 118 chapters. `roll_shape_distribution`
buckets rolls by perk count (`0` = a miss/empty roll; `1`+ = a hit with that many perks
attached, including multi-grab hits from Personal Reality/Additional Space-style bundled
rolls):

| Perks per roll | Roll count | % of all rolls |
|---|---|---|
| 0 (miss) | 622 | 91.3% |
| 1 | 25 | 3.7% |
| 2 | 22 | 3.2% |
| 3 | 6 | 0.9% |
| 4 | 2 | 0.3% |
| 5 | 2 | 0.3% |
| 7 | 1 | 0.1% |
| 8 | 1 | 0.1% |

Of the 681 rolls, **59 are hits** (8.7% of all rolls) and **622 are misses** (91.3%).
Within the 59 hits, **34 are multi-grab** (2+ perks bundled into a single roll — 57.6% of
all hits, 5.0% of all rolls), and 25 are single-perk hits (42.4% of hits). In other words:
when a chapter's paid roll actually connects, it is *more likely than not* to be a
multi-grab bundle rather than a lone perk. This is the single most important shape fact
for Phase 3's extraction prompt — an agent that defaults to "one perk per hit" will
misparse the majority of hits in this corpus. The long tail (4, 5, 7, 8 perks in one roll)
is rare but real, and corresponds to the project's documented "multi-grab" mechanic
(Personal Reality / Additional Space clusters where several small bundled motes land in
one connection).

## 3. Evidence-Quote Patterns

`evidence_quote_stats` (computed over all 681 rolls, including the 622 that carry zero
quotes):

| Stat | Value |
|---|---|
| Min quotes per roll | 0 |
| Max quotes per roll | 22 |
| Mean quotes per roll | 1.269 |
| Total quotes in corpus | 864 |

Most rolls (the 622 misses) carry 0 or few quotes — a miss is often evidenced by a single
short quote confirming the constellation was rolled and missed, or none at all. Hits
carry proportionally more evidence, and the max of 22 quotes on a single roll reflects a
chapter where the author's prose narrates an extended, heavily-cross-referenced sequence
(the mining code does not cap quote count per roll).

`display_position_policy_distribution` — where in the prose a roll's evidence is anchored:

| Policy | Count | % of all rolls |
|---|---|---|
| `null` (no explicit anchor; defaults to the mechanical position) | 598 | 87.8% |
| `mechanical` | 82 | 12.0% |
| `source_marker` | 1 | 0.1% |

The schema (`chapter_roll_overrides.json`'s `_purpose` header) also permits `mention`,
`section_start`, and `section_end`, but none of the 118 curated chapters currently use
them — the corpus's actual usage is concentrated on `null`/`mechanical`, with
`source_marker` reserved for a single edge case. Phase 3 prompt design should treat the
unused policy values as valid-but-rare, not as dead schema.

**Illustrative example** (verbatim from an already-committed evidence quote, chapter 67,
roll 0 — a miss roll, quoted directly from `data/manual/chapter_roll_overrides.json`, not
the epub):

> "the Magitech constellation passed by"

This is typical of a miss-roll quote: short, confirms only that the constellation was in
play and nothing was obtained, `mention_chapter_num` matching the mechanical chapter.
Hit-roll quotes tend to be substantially longer and more numerous (see the chapter-67 hit
roll in the same file, which carries three quotes narrating the Personal Reality
multi-grab in detail) — consistent with the mean/max spread above.

## 4. `cp_ledger_checkpoint` Usage

`cp_ledger_checkpoint_usage_count: 1` — across the entire 118-chapter corpus and its 864
evidence quotes, exactly **one** quote carries a `cp_ledger_checkpoint` marker (a
banked-CP-reset attestation). This confirms the schema note from Plan 01-03: the field
lives on an individual `evidence_quotes[]` entry, not on the roll object itself (the index
surfaces it at the roll level as a read-only passthrough — `_roll_cp_ledger_checkpoint` —
picking the first quote that carries one, but this is a convenience view, not a second
representation of the data).

For Phase 3 prompt design: this is an extremely rare marker. An extraction prompt should
treat it as an opt-in signal an agent only sets when a quote *explicitly* narrates a
banked-CP-ledger reset event — not something to infer or default to "true" absent direct
textual evidence. The corpus's near-total absence of this marker (1 in 864 quotes) is
itself evidence that most chapters never need it.

## 5. Perk-Link/Naming Conventions

Each roll's `perks` array holds plain-string perk names (e.g. `"The Pond"`,
`"Additional Space - Starting Area"`, `"Minor Blessing Zeus – Lightning"`). These strings
are expected to resolve against `data/derived/perk_directory.json`'s `perks[].name` field
using the existing, already-established matching convention documented in that directory's
own `_note` field and implemented in `scripts/perk_name_resolver.py` /
`scripts/build_perk_directory.py` — this report does not invent a new convention, only
points at the one already in use:

1. **Exact match** on `(name, jump)`.
2. **Normalized match** — case- and punctuation-insensitive comparison of `(name, jump)`
   (handles cosmetic drift like en-dash `–` vs hyphen `-`, which appears throughout the
   corpus's hand-typed perk names).
3. **Separator-prefix/suffix-split matching** — e.g. `"Additional Space - Starting Area"`
   resolves against a base perk `"Additional Space"` plus a variant/instance suffix; this
   is the mechanism behind the multi-grab example in §2 and §6, where multiple
   `Additional Space - <variant>` strings in one roll's `perks` array are all instances of
   the same underlying rollable perk.
4. **Normalized word-prefix matching** and **`JUMP_ALIASES`/`data/manual/perk_aliases.json`**
   fold cosmetic jump-name drift and known typo/sub-instance variants to a single canonical
   directory entry.

Phase 3 prompt design should assume agent-extracted perk names will need to survive this
same resolution pipeline — an agent introducing a genuinely novel separator style or
un-aliased typo will silently fail to resolve, which is a correctness risk worth flagging
explicitly in the extraction prompt's output-format instructions (match the corpus's own
typed conventions rather than inventing new ones).

## 6. Regime-Boundary Handling

Exactly one chapter in the corpus — **97** — spans a mid-chapter regime transition, per
`data/manual/regime_transitions.json` (the Nano-Forge transition). The exemplar index
represents this as:

```json
{
  "chapter_num": "97",
  "regime_tags": [2, 3],
  "is_boundary": true,
  "rolls": [
    {"perks": ["Additional Space - Starting Area", "Additional Space – Lofty Loft"], "outcome": "hit", ...},
    {"perks": ["Nano-Forge"], "outcome": "hit", ...}
  ]
}
```

Both fields — `regime_tags` (a list, not a single value) and `is_boundary: true` — are
computed once at index-build time from the pipeline's own regime computation
(`chapter_facts.json:point_calculation_regime` for the ordinary case, or
`regime_simulator.regime_for_chapter()` plus the transition record for boundary chapters —
D-02), never re-derived by the report or by retrieval. `scripts/query_exemplars.retrieve()`
honors this by returning chapter 97 as a valid exemplar for *either* a regime-2 or a
regime-3 query target — it is the only chapter visible from both regime pools.

Chapter 97's two rolls are also a live illustration of §2's multi-grab point: the first
roll bundles two `Additional Space` variants into one hit (a clean multi-grab example),
and neither of its rolls carries any evidence quotes (`evidence_quote_count: 0` for both) —
a reminder that "hit" and "well-evidenced" are independent properties in this corpus; a
roll can be a confirmed hit purely from the curator's structural knowledge of the chapter,
without a supporting narrated quote.

**Why this matters for Phase 3:** when the agent curation pipeline encounters a chapter
straddling a regime transition, it should expect (a) the exemplar pool for that chapter to
draw from both adjacent regimes' hand-curated examples, and (b) the possibility of
zero-evidence, structurally-confirmed hits — an extraction prompt that requires at least
one evidence quote per hit would be stricter than the hand-curated corpus's own actual
practice, at least for boundary chapters.

---

*Report generated from `data/derived/exemplar_index.json` (`schema_version: 1`), built by
`scripts/build_exemplar_index.py` from `data/manual/chapter_roll_overrides.json`. No epub
prose was read to produce this document (D-04).*
