# Stage 1 Candidate-Assembly Accuracy Report

**Purpose:** This report measures `scripts/build_candidate_rolls.py`'s (Plan 03-02) Stage 1
deterministic, zero-LLM candidate assembly against the hand-curated corpus
(`data/manual/chapter_roll_overrides.json`), broken out **per evidence class** (ACUR-01,
ROADMAP success criterion 3, D-08). Phase 4 reads this report to size its own inference
spend — this is the load-bearing deliverable of Phase 3, not a side artifact.

**Sourcing constraint:** Every number below is read directly from
`candidate-accuracy-report.json`'s `by_evidence_class` and `_generated_from` blocks —
nothing here is recomputed independently, and nothing here was derived by reading the
epub or `data/manual/chapter_roll_overrides.json` directly. That JSON file is produced by
`scripts/measure_candidate_accuracy.py`, re-runnable at any time
(`.venv/bin/python scripts/measure_candidate_accuracy.py`), and re-running it against
unchanged inputs reproduces this report's numbers byte-for-byte (deterministic, sorted
iteration throughout — no dict/set-order nondeterminism).

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
- **Matching methodology:** deterministic chapter-local position proximity (curated
  `word_position` when set, else ordinal chapter-local sequence rank — 679 of 681 curated
  rolls have no `word_position` at all, so the ordinal fallback is the dominant mode in
  practice) plus perk-name-set overlap as a tiebreaker. **Never** joins on `roll_number` or
  `source_ordinal` — those predictor/curator sequences diverge by construction (project
  convention) and are never used as an identity key. Full algorithm is documented in the
  JSON report's `_method` field and in `scripts/measure_candidate_accuracy.py`'s module
  docstring.

## 2. Per-Evidence-Class Results

Per D-08, this is deliberately **not** a single headline number — a global figure would be
dominated by the 68%-of-corpus `forward_ref` share (D-07) and would hide where Stage 1
actually performs well.

| Evidence class | Curated rolls | Matched (full) | Partial | Missed | Unmatched candidates | Proposed (matched+partial) | Missed rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| `direct` | 131 | 4 (3.1%) | 122 (93.1%) | 5 (3.8%) | 0 | 126 (96.2%) | 3.8% |
| `general_only` | 26 | 0 (0.0%) | 26 (100.0%) | 0 (0.0%) | 0 | 26 (100.0%) | 0.0% |
| `forward_ref` | 461 | 0 (0.0%) | 446 (96.7%) | 15 (3.3%) | 0 | 446 (96.7%) | 3.3% |
| `no_evidence` | 45 | 0 (0.0%) | 42 (93.3%) | 3 (6.7%) | 1 | 42 (93.3%) | 6.7% |
| **Total** | **663** | **4** | **636** | **23** | **1** | **640 (96.5%)** | **3.5%** |

Column definitions (D-08): **Curated rolls** — hand-curated rolls in that class measured
(after stub exclusion). **Matched (full)** — Stage 1 proposed a candidate for that curated
roll with zero `_derivation.unfilled_fields` (a fully-bound, anchor-confirmed candidate).
**Partial** — Stage 1 proposed a candidate, but that candidate carries at least one
`unfilled_fields` entry (D-06's first-class partial-evidence outcome — e.g. a
positionally-bound hit that never got a local `"acquisition"` anchor). **Missed** — no
Stage 1 candidate was proposed for that curated roll at all. **Unmatched candidates** —
Stage 1 candidates in that chapter with no curated-roll counterpart.

## 3. Interpretation: Does Stage 1 Perform on the `direct` Class (D-07)?

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
four classes — `general_only` has a 0.0% missed rate, and `forward_ref`'s (3.3%) is
actually slightly lower than `direct`'s. Raw "did Stage 1 propose *something*" coverage
(matched+partial) is uniformly high across all four classes (93–100%), because that
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
but does not come close to solving even its best class.

---

*Report generated by `scripts/measure_candidate_accuracy.py` from
`data/derived/candidate_rolls.json` and `data/manual/chapter_roll_overrides.json`.*
*Phase: 03-provenance-schema-deterministic-candidate-assembly*
