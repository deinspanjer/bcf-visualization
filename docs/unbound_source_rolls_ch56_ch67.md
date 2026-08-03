# Unbound source rolls — chapters 56 and 67 (found 2026-08-03)

> Open curation/alignment issue. Surfaced while investigating a long-standing test failure.
> Not urgent — it has been latent for weeks and does not affect the published site — but it is
> a real correctness gap, not a stale fixture.

## The symptom

`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`
has been failing as part of the accepted 5-failure baseline. It was assumed to be derived-data
staleness that the epub refresh would clear. **The epub refresh landed and it still fails**, so that
explanation was wrong.

## What is actually wrong

**22 of 670 source rolls have `predicted_ordinal: null`** — they are not bound to any predicted slot.
Most are isolated, but two chapters are wholly unbound:

| Chapter | Predicted slots | Source rolls | Bound |
|---|---|---|---|
| **56** | 7 | 6 | **0** |
| **67** | 5 | 4 | **0** |

The predictions exist. The source rolls exist. Nothing connects them.

Full list of unbound rolls:

```
ch 14    #1
ch 18    #1
ch 45    #6
ch 51    #6
ch 53    #6
ch 55.1  #6
ch 56    #1,2,3,4,5,6     <-- whole chapter
ch 58.2  #6,7
ch 67    #1,2,3,4         <-- whole chapter
ch 71    #7
ch 74    #7
ch (none) x2
```

The singletons are nearly all a chapter's **last** roll (#6 or #7), which looks like a distinct
end-of-chapter boundary effect worth checking separately from the two whole-chapter cases.

## Why the test fails specifically

The test asserts that chapter 55.1's sixth roll *borrows chapter 56's first prediction*, at
`predicted_ordinal 413`. That borrowing chain is broken in both directions:

- ch 55.1 #6 is unbound (`predicted_ordinal: null`), so it borrows nothing
- `P413` is now held by **chapter 57 #1**

Chapter 55.1 rolls #1–#5 bind normally to P408–P412. The sequence then jumps straight to chapter 57.
Chapter 56 is skipped over entirely.

The test also pins absolute `source_ordinal` values (387/388/393). Those have shifted — ch 55.1 #6
now sits at `source_ordinal` 380, not 387 — so even once the binding is fixed, the test needs
re-anchoring on (chapter, within-chapter ordinal) rather than global ordinals.

## What needs deciding

This is a curation judgment, not a code fix. Chapter 56 has 7 predicted slots against 6 curated
source rolls; chapter 67 has 5 against 4. Someone has to decide what the correct binding is before
anything downstream can be trusted — the same shape as the existing chapter 104 item ("2 curated hit
rolls exceed the model's 1 predicted slot — needs a curator-TUI edit, not a plain re-stamp").

Suggested order:
1. Review chapter 56 in the Forge Curator TUI — does the 7-vs-6 mismatch mean a missed roll, a
   spurious prediction, or a multi-grab that should collapse two slots?
2. Same for chapter 67 (5 vs 4).
3. Check whether the trailing-roll singletons (#6/#7 across ch 45/51/53/55.1/58.2/71/74) share one
   cause — a boundary rule — or are unrelated.
4. Then rewrite `test_chapter_55_1_source_roll_six_borrows_first_56_prediction` against whatever the
   truth turns out to be, anchored on chapter + within-chapter ordinal.

## Related: four stale TUI test fixtures

Separate and much smaller. The other four baseline failures — all in `tests/test_forge_curator.py` —
pin literal rendered strings like `"# 2 (R520/P548)"`. Chapter 79's roll #2 is now `R514/P548`: the
prediction ordinal is unchanged, only the **curator** roll number moved, by 6.

Curator roll numbers renumber whenever earlier chapters are curated, so bumping the literal buys
green only until the next curation session. The durable fix is to look the roll up by chapter and
within-chapter position instead of pinning a global curator ordinal. Roughly an hour, and then they
survive ongoing curation.

## Impact

**None on the published site.** No CI workflow runs `pytest` or `scripts/verify.py` — verified across
`release.yml`, `deploy-pages.yml`, and `data-release.yml` — so these failures have never gated a
publish. `scripts/verify.py` exits 1 locally for this reason; judge it by the failure *set*, not the
exit code.
