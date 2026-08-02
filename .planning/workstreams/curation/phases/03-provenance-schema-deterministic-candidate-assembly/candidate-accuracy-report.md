# Stage 1 Candidate-Assembly Accuracy Report

**Purpose:** This report measures `scripts/build_candidate_rolls.py`'s (Plan 03-02) Stage 1
deterministic, zero-LLM candidate assembly against the hand-curated corpus
(`data/manual/chapter_roll_overrides.json`), broken out **per evidence class** (ACUR-01,
ROADMAP success criterion 3, D-08). Phase 4 reads this report to size its own inference
spend — this is the load-bearing deliverable of Phase 3, not a side artifact.

**Sourcing constraint:** Every number below is read directly from
`candidate-accuracy-report.json`'s `by_evidence_class`, `_position_tier_counts`, and
`_generated_from` blocks — nothing here is recomputed independently, and nothing here was
derived by reading the epub or `data/manual/chapter_roll_overrides.json` directly. That
JSON file is produced by `scripts/measure_candidate_accuracy.py`, re-runnable at any time
(`.venv/bin/python scripts/measure_candidate_accuracy.py`), and re-running it against
unchanged inputs reproduces this report's numbers byte-for-byte (deterministic, sorted
iteration throughout — no dict/set-order nondeterminism; verified for this run).

**Methodology-fix note (this revision):** A prior version of this report scored curated-side
position almost entirely via ordinal rank ("the Nth candidate lines up with the Nth curated
roll"), because only 2 of 681 curated rolls carry a real `word_position`. That measured
whether Stage 1 emits the right *count* of candidates per chapter, not whether it identified
the right rolls. This revision fixes the ruler — see Section 1a — without touching
`build_candidate_rolls.py` or any Stage 1 assembly logic in any way.

---

## 1. Overview

- **Total Stage 1 candidates (whole corpus):** 718 (`data/derived/candidate_rolls.json`,
  Plan 03-02).
- **Total hand-curated chapters:** 118 (`data/manual/chapter_roll_overrides.json`).
- **Stub chapters excluded from the denominator (D-09):** 10 —
  `35.1, 55.1, 97, 100, 103, 106, 109, 112, 114, 116.2`. A stub chapter is one whose
  curated rolls all carry zero `evidence_quotes` (including chapter 55.1, whose entry has
  zero rolls at all — vacuously true, not a special case). Chapter **104** is **not**
  excluded: it was genuinely hand-curated with real evidence quotes on 2026-08-01, and the
  live predicate (re-derived from the data on every run, never hardcoded) correctly drops
  it from the stub set.
- **Curated rolls measured (non-stub chapters, intersected with candidate chapters):** 663
  of 681 total curated rolls (the 18-roll gap is entirely the excluded stub chapters — 55.1
  contributes 0, the other 9 stub chapters contribute the remaining 18).

### 1a. Curated-side position: a three-tier ladder

Matching pairs each curated roll to a candidate by chapter-local position proximity (plus
perk-name overlap as a tiebreaker — see `_method` in the JSON for the full algorithm). The
curated side of that comparison is resolved via a documented precedence ladder, in order:

1. **`word_position`** — the roll's own `word_position` field, when non-null. Most
   authoritative: the curator's own hand-set mechanical position.
2. **`quote_position`** — else the **minimum** `mention_word_position` across the roll's
   `evidence_quotes` whose `mention_chapter_num` matches the roll's own chapter. Minimum,
   not first-in-list order, because `CURATION-CONVENTIONS.md` §2/§3 documents that the
   *connection* quote (naming the mote/constellation, placed "immediately before and close
   to" the roll) comes first in narrative position, while later per-perk-name quotes can
   trail the roll by thousands of words (intra-roll quote span up to 7,392 words per §2). A
   quote naming a **different chapter** than the roll (~8% of corpus quotes per §3) is a
   different coordinate space and is excluded from this comparison, never mixed in.
3. **`ordinal`** — else the roll's 0-based ordinal rank within the chapter's curated
   `rolls[]` list (the curator's own list order is already narrative reading order) — the
   fallback of last resort, for rolls with no positional evidence at all.

**Tier counts, measured across all 663 curated rolls in this report's denominator**
(`_position_tier_counts` in the JSON):

| Tier | Count | Share |
|---|---:|---:|
| `word_position` | 2 | 0.3% |
| `quote_position` | 542 | 81.8% |
| `ordinal` | 119 | 17.9% |

**This is the headline transparency number for this revision.** In the prior measurement,
679 of 681 corpus-wide curated rolls (99.7%) rested on ordinal fallback — "proximity" was
almost entirely a count-alignment artifact. In this measurement, 82.1% of measured curated
rolls (`word_position` + `quote_position`) now rest on a real, quote-derived narrative
position, and only 17.9% fall back to ordinal rank (rolls with no positional evidence
recorded at all — genuinely undated in the corpus, not a measurement shortfall).

## 2. Per-Evidence-Class Results

Per D-08, this is deliberately **not** a single headline number — a global figure would be
dominated by the 68%-of-corpus `forward_ref` share (D-07) and would hide where Stage 1
actually performs well.

| Evidence class | Curated rolls | Matched (full) | Partial | Missed | Unmatched candidates | Proposed (matched+partial) | Missed rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| `direct` | 131 | 4 (3.1%) | 122 (93.1%) | 5 (3.8%) | 0 | 126 (96.2%) | 3.8% |
| `general_only` | 26 | 0 (0.0%) | 26 (100.0%) | 0 (0.0%) | 0 | 26 (100.0%) | 0.0% |
| `forward_ref` | 463 | 0 (0.0%) | 446 (96.3%) | 17 (3.7%) | 0 | 446 (96.3%) | 3.7% |
| `no_evidence` | 43 | 0 (0.0%) | 42 (97.7%) | 1 (2.3%) | 1 | 42 (97.7%) | 2.3% |
| **Total** | **663** | **4** | **636** | **23** | **1** | **640 (96.5%)** | **3.5%** |

Column definitions (D-08): **Curated rolls** — hand-curated rolls in that class measured
(after stub exclusion). **Matched (full)** — Stage 1 proposed a candidate for that curated
roll with zero `_derivation.unfilled_fields` (a fully-bound, anchor-confirmed candidate).
**Partial** — Stage 1 proposed a candidate, but that candidate carries at least one
`unfilled_fields` entry (D-06's first-class partial-evidence outcome — e.g. a
positionally-bound hit that never got a local `"acquisition"` anchor). **Missed** — no
Stage 1 candidate was proposed for that curated roll at all. **Unmatched candidates** —
Stage 1 candidates in that chapter with no curated-roll counterpart.

## 3. What changed versus the prior (ordinal-dominated) measurement

The prior run reported **4 matched / 636 partial / 23 missed across 663 curated rolls**
(96.5% proposed, 3.5% missed rate). This run reports the **identical totals**: 4 matched,
636 partial, 23 missed, 640 proposed (96.5%), 3.5% missed rate.

That is not because the fix changed nothing. A direct comparison of the per-roll
candidate assignment (old ordinal-only ladder vs. this revision's three-tier ladder,
computed for the same 663 curated rolls) shows **491 of 663 curated rolls (74.1%) were
paired with a different candidate** once real quote-derived positions replaced ordinal
rank. **92 of the measured chapters** had at least one reassignment. The aggregate
matched/partial/missed totals held steady because `matched` vs. `partial` status depends
only on whether *whichever* candidate ends up assigned carries `unfilled_fields` — and
96.9% of all candidates in this corpus are `partial` regardless of which one gets picked
(Section 2's `general_only`/`forward_ref`/`no_evidence` rows show 0 full matches
corpus-wide; only `direct` has any at all, and only 4). Reassigning most of the pairings
therefore mostly reassigns which `partial` candidate a roll is credited against, not
whether it counts as `partial` — so the coarse-grained totals were largely insensitive to
the fix even though the underlying "did Stage 1 identify *this* roll" answer changed for
three-quarters of the corpus.

The two visible bucketing changes are both in the **per-evidence-class attribution of
missed rolls** (evidence-class bucketing for a `missed` roll is assigned by its single
nearest candidate's `evidence_kind`, per the `_method` algorithm — this is bucketing only,
never the matched/partial/missed status itself):

- `forward_ref`: curated-roll count rose from 461 to 463, missed rose from 15 (3.3%) to 17
  (3.7%).
- `no_evidence`: curated-roll count fell from 45 to 43, missed fell from 3 (6.7%) to 1
  (2.3%).

Two missed rolls' nearest-candidate class flipped from `no_evidence` to `forward_ref` once
their curated position moved from ordinal rank to a real quote-derived position — the
candidate that is now geometrically closest to them carries a different `evidence_kind`
than the one that was closest under the old ordinal scale. Everything else in Section 2 —
`direct` and `general_only` — is numerically unchanged from the prior run.

**Bottom line: same headline numbers, substantially different (and now trustworthy)
pairings underneath them.** The prior 96.5%/3.5% split was real in aggregate, but a reader
could not tell from it whether Stage 1 was identifying the right rolls or merely emitting
the right count per chapter. This revision confirms — via the tier counts in Section 1a and
the 74.1% reassignment rate above — that the aggregate numbers are now anchored in real
narrative position for 82.1% of the corpus, not ordinal coincidence.

## 4. Interpretation: Does Stage 1 Perform on the `direct` Class (D-07)?

D-07 states Stage 1 "should be expected to perform on the `direct` class and to *usefully
narrow* the others, not to solve them." The measured numbers support this **directionally,
but only modestly** — the honest reading is that Stage 1's real accuracy gain on `direct`
is small in absolute terms, even though it is the only class where it shows up at all.

**Where `direct` does lead:** all 4 fully-matched (anchor-confirmed, zero
`unfilled_fields`) curated rolls in this entire measurement come from the `direct` class —
`general_only`, `forward_ref`, and `no_evidence` each measure exactly **0** full matches.
This is consistent with `direct` rolls being the ones most likely to have a local
`"acquisition"` anchor in their own prose window (`roll_text_evidence.json`'s per-row
evidence), which is the only thing that upgrades a candidate from "positional-only" to
"anchor-confirmed" in Stage 1's binding rule. It also tracks Plan 03-02's own corpus-wide
finding that only 6 of 718 candidates are anchor-confirmed at all — `direct` capturing all
4 of the ones that survived stub exclusion is a real, if numerically thin, signal.

**Where `direct` does *not* clearly lead:** its missed rate (3.8%) is not the lowest of the
four classes — `general_only` has a 0.0% missed rate, and `no_evidence`'s (2.3%) is now
also lower than `direct`'s. Raw "did Stage 1 propose *something*" coverage
(matched+partial) is uniformly high across all four classes (96–100%), because that
coverage is driven almost entirely by the chapter-local positional cursor-advance through
`merge_paid_units` (Plan 03-02's binding rule) — a mechanical process that does not
consult a roll's own evidence class at all. Evidence class only starts to matter at the
much stricter "was this candidate anchor-confirmed, not just positionally guessed" bar,
and at that bar, 96.9% of even `direct`-class candidates are still only `partial` — Stage
1's own `unfilled_fields` honesty markers are doing more of the real work here than any
evidence-class-specific accuracy is.

**Bottom line for Phase 4:** Stage 1 narrows the search space almost uniformly well across
all four classes (proposing *a* candidate for 96.5% of measured curated rolls), but its
ability to say "and I'm confident this is right, not just positionally plausible" is
concentrated almost entirely in the `direct` class, and even there it only fires for about
3% of `direct` rolls. Phase 4's inference should expect to do real confirmation work across
every evidence class, including `direct` — Stage 1 usefully narrows the question, per D-07,
but does not come close to solving even its best class. This revision adds one further
caveat for Phase 4: the *coverage* numbers above (96.5% proposed) are now grounded in real
narrative position for 82.1% of the measured corpus rather than resting almost entirely on
ordinal count-alignment, which is what makes them safe to use for sizing inference spend.

---

*Report generated by `scripts/measure_candidate_accuracy.py` from
`data/derived/candidate_rolls.json` and `data/manual/chapter_roll_overrides.json`.*
*Phase: 03-provenance-schema-deterministic-candidate-assembly*
