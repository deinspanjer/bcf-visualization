---
name: forge-curator-review
description: Review Forge Curator chapters by driving ForgeCuratorApp headlessly, reconciling trigger perks, predicted rolls, source rolls, saved narrative evidence, scored evidence candidates, and narrative-vs-predicted drift without mutating curation data unless explicitly approved.
metadata:
  short-description: Headless Forge Curator chapter review
---

# Forge Curator Review

Use this skill when reviewing curated Forge Curator chapter data in `/home/dre/src/bcf-visualization`, especially when asked to compare what the TUI shows against derived/manual curation state.

## Rules

- Work through `ForgeCuratorApp` and its loaded chapter state; avoid ad hoc full-chapter reasoning from raw text dumps.
- Treat the review as read-only unless the user explicitly approves a specific change.
- If a change is approved, prefer Forge Curator actions/persistence paths and regenerated derived data. Do not edit derived JSON directly.
- Keep the recap tight. Do not mention scorer false positives unless they affect a proposed data change.
- Include narrative evidence distance from predicted/mechanical position for each curated roll.
- Comment briefly on whether narrative evidence appears to be drifting farther from predicted positions over time.
- Prefer alignments where the first narrative evidence appears after the predicted roll. Significant negative deltas are suspicious and should trigger an alignment check.
- When the model has `ambiguous_schedule`, or when curation uses skipped, inserted, deferred, or source-linked rolls, check whether another feasible alignment would make the narrative flow better before recommending new skips or inserted rolls. Do not report pure scheduler/accounting ambiguity when every alternate would violate the curated source or narrative evidence order; that is not an actionable review issue.
- Call out “valid but suspicious” separately from “likely wrong”; wait for approval before changing anything.
- Refer to rolls as `#<local>/<global>` whenever both numbers are available.
- Use compact predicted positions such as `6k`, `23k`, or `23.5k` for cumulative predicted/mechanical CP-word positions.
- Include the narrative chapter word location and visualization placement for each roll.
- Always call out predicted slots that are blank, open, or skipped. These are
  important follow-up signals because the next chapter may need to defer or
  source-link evidence back to the open prediction.
- Quotes are assumed present; mention quote status only when a quote is missing or cannot be found where expected.

## Headless Workflow

From the repo root, use `.venv/bin/python`.

Resolve chapter references before loading:

- `ch 4`, `chapter 4`, `ch 3.1`, and similar bare chapter references mean the
  author's chapter label. Pass that exact label string to `ForgeCuratorApp` and
  `_load_chapter`, for example `"4"` or `"3.1"`.
- `ch #4`, `chapter #4`, `ordinal 4`, and similar `#`/ordinal references mean
  the fourth chapter in the app's ordered chapter list, not the author label
  `"4"`.
- For ordinal references, resolve with the app's chapter order before loading:

```python
from scripts.forge_curator.app import ForgeCuratorApp

app = ForgeCuratorApp()
chapter_label = app.data.chapter_order[4 - 1]
app._load_chapter(chapter_label)
cs = app.state.chapter
```

Load a chapter:

```python
from scripts.forge_curator.app import ForgeCuratorApp

app = ForgeCuratorApp(start_chapter="2")
app._load_chapter("2")
cs = app.state.chapter
```

Use app-level views:

- `app._unified_rolls(cs)` for current chapter displayed roll facts.
- `app._deferred_predicted_slot_rolls(cs, unified)` for deferred predicted slots visible in this chapter.
- `cs.derived.predicted_rolls` for predicted slots.
- `cs.derived.roll_facts` and `cs.derived.chapter_facts` for source/model status.
- `cs.evidence_candidates` for scored narrative-evidence navigation anchors.
- `app.action_snapshot()` only when a snapshot artifact is useful; for temporary snapshots, monkeypatch `scripts.forge_curator.app.SNAPSHOT_PATH` to a temp path.

## Distance Calculation

For each non-trigger displayed roll, compute:

- `predicted_cumulative`: prefer `mechanical_cumulative_word_offset`; otherwise use `predicted_word_position_epub`; otherwise `chapter_cp_start(mechanical_chapter) + mechanical_word_position`.
- `evidence_cumulative`: prefer first saved quote `chapter_cp_start(mention_chapter_num) + mention_word_position`; otherwise use display/source cumulative offsets.
- `delta = evidence_cumulative - predicted_cumulative`.
- `visualization`: report `viz=pred` when `display_position_policy` is `mechanical` or the display position matches the mechanical/predicted position; `viz=nar` when it is `mention` or matches the first narrative evidence; otherwise use `viz=<policy>` or `viz=other`.

Interpretation:

- Positive delta: narrative evidence appears after the predicted slot.
- Negative delta: narrative evidence appears before the predicted slot.
- Cross-chapter deferrals should still use cumulative CP-word coordinates.

## Recap Format

Use this shape:

```text
Chapter N: Title

Status: no recommended changes / review needed

Rolls:
- #L/G Constellation outcome, pred Pk, nar chC:W, delta +/-D, viz=pred/nar/other.

Open predicted:
- #L/G pred Pk, status blank/skipped/open, follow-up: check next chapter for deferred evidence.

Drift read: one short sentence comparing this chapter's deltas to nearby prior chapters when known.
```

If proposing a change, use:

```text
Possible change:
- Current: ...
- Inference: ...
- Recommended action: ...
```

Stop there and wait for approval before mutating data.

## Alignment Review

When a roll has a negative delta, inspect nearby predicted slots before and after the current mechanical slot. Include open prior-chapter slots when the narrative appears early in the next chapter.

For each plausible alternative, compare:

- Whether source/narrative order is preserved.
- Whether the evidence lands after the predicted slot.
- Whether the change would require a skip, inserted roll, deferral, or source-link change.
- Whether it reduces the need to invent or skip rolls.

In the recap, include a short `Alignment note:` only when there is something suspicious or actionable.

Treat `ambiguous_schedule` as actionable only if at least one alternate mapping
preserves source roll order, preserves first-evidence narrative order, and
could plausibly reduce skips, inserted rolls, deferrals, source links, or
large negative deltas. If the ambiguity exists only because the cost solver can
reorder hits in a way the narrative rules out, omit it from the recap.
