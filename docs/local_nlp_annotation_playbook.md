# Annotation playbook + TUI spec

_How to build the labeled dataset, with a specification for the in-repo
review TUI. Pair with `docs/local_nlp_label_schema.md`._

> **What changed in v3:** Layer B gains `PERK_REFERENCE` for in-prose
> mentions of perks already in Joe's possession. The phase-1 quality gate
> for layer-B coverage now requires 5+ examples of `PERK_REFERENCE`
> alongside the existing layer-B labels. The TUI gains an `N` keybinding
> for per-passage notes; notes ride on `SpanRecord` via the new
> `notes: str` field (default empty). The data `schema_version` field
> bumps from `1` to `2`.
>
> **What changed in v2:** Candidates now come from `data/derived/roll_resolutions.json`
> instead of `data/derived/predicted_rolls.json`, and each candidate carries a
> `roll_context` chapter-context block injected into the LLM prompt and displayed
> in the TUI. The system prompt is shorter (2 layer-A labels, 6 layer-B labels).
> Phase 1 quality gates are updated to match the new label set.

## Goal

Produce three artifacts in `data/labeled/`:

| File | Target size | Purpose |
|---|---|---|
| `spans/pilot.jsonl` | ~250 passages | Schema stabilization, IAA check |
| `spans/train.jsonl` | ~1500 passages | MVP span model training |
| `spans/eval.jsonl` | ~300 passages | Held-back-from-train, used during training |
| `spans/heldout.jsonl` | ~150 passages | Blind eval; never seen by LLM or trainer |
| `sections/train.jsonl` | ~400 sections | MVP section classifier training |
| `sections/eval.jsonl` | ~80 sections | Held-back-from-train |

The same passage's section is labeled once. So if you label 1500 passages
drawn from 400 sections, you get the section dataset for free on the side.

## Workflow phases

### Phase 1 — pilot (~250 passages)

Goals: lock the label schema, find edge cases, calibrate yourself against the
guideline.

Steps:

1. Sample candidate passages (see "Candidate selection" below). Use the
   `event_focused` strategy in phase 1.
2. For each candidate, run the labeling assistant to draft proposals.
3. Open the TUI, review and correct proposals one passage at a time.
4. After every ~50 passages, re-read `docs/local_nlp_label_schema.md` and
   update it if you've encountered cases the doc doesn't resolve. Schema
   updates trigger a re-review of all prior pilot passages.
5. After 250 passages, do a second-pass review of the first 50. If your
   second-pass labels disagree with your first-pass labels on more than 10%
   of spans, *discard the first 50 and redo them*. This is your
   inter-annotator-agreement substitute.

Exit: 250 passages with frozen schema (bump `schema_version` if you changed
anything).

### Phase 2 — MVP build-out (~1500 passages)

Goals: enough labeled data to train a credible span model and section
classifier.

Steps:

1. Continue candidate selection, now stratified across:
   - Chapter regimes (1–91, 92–96, 97+) — proportional to roll count, not
     chapter count.
   - Roll density (chapters with many vs few rolls).
   - Event types (`ROLL_HIT` is most common; deliberately over-sample
     `ROLL_MISS`, `PRESENCE_ACTION`, `FLASHBACK_CUE`, `DILATION_CUE` so
     they aren't starved).
2. Continue bootstrap-and-review.
3. Train v1 span model (see `docs/local_nlp_training.md`).
4. Switch to the **active learning** loop (see below).

Exit: span model meets phase-2 acceptance from `docs/local_nlp_plan.md`.

### Phase 3 — hard-case expansion (+400–700 passages)

Active learning end-to-end. Each new candidate is selected by disagreement
between the model and the labeling assistant, or by low model confidence.
Heavy weight on the rare classes that under-perform in eval.

Exit: meets full acceptance criteria.

## Candidate selection

Candidates are passages of 1–3 paragraphs centered on a likely extraction.
The primary source is `data/derived/roll_resolutions.json`, which already
carries predicted roll positions plus chapter context. Take a window of ±250
words around each predicted position; that's one candidate.

`nlp/tui/candidates.py` should expose:

```python
def next_candidate(
    queue_state: QueueState,
    *,
    strategy: str = "event_focused",
) -> Candidate: ...
```

Strategies:

- `event_focused` — candidates from `roll_resolutions.json` predicted-roll
  positions only. **Default for phase 1.** Concentrates labeling effort on
  `ROLL_HIT` and `ROLL_MISS` where the context payload is richest.
- `balanced` — round-robin across all candidate sources, weighted by
  remaining-count quotas. Use in phase 2 once roll events are well covered.
- `low_confidence` — phase-3 active learning; pulls candidates where the
  current span model has low max-token confidence.
- `coverage_gap` — pulls candidates from chapters/regimes where you have the
  fewest labeled passages.

Additional sources (used in `balanced` and `coverage_gap`):

- Existing regex anchors from `roll_locations_regex.json`, especially
  `general` (catch-all) anchors that the current pipeline can't classify.
- Random non-Joe-POV sections (using `chapter_sections.json`'s POV signal)
  for `PRESENCE_ACTION` and `joe_on_screen` coverage.
- Date-rich passages identified by a regex sweep for month names, day names,
  and `\d{1,2}(?:st|nd|rd|th)?` patterns, for time/date label coverage.
- Random passages from each chapter as a tail to prevent over-fitting to
  event-dense windows.

The TUI exposes a strategy picker but persists the most recent choice to
`data/labeled/.tui_state.json`.

## Bootstrap proposals (the labeling assistant)

`nlp/bootstrap.py` calls llama.cpp on `:11434` with a strict prompt that
asks for JSON proposals matching the dataset schema (subset: spans only, no
metadata).

### Recommended models (in priority order)

| Model | When to use |
|---|---|
| `unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF` (Q4_K_M, MoE) | Default for batch passes; fastest tokens/sec. |
| `bartowski/Qwen_Qwen3-32B-GGUF` (Q4_K_M, dense) | Single tricky passage; harder reasoning. Has performed best in dry-runs against the v2 schema. |
| `bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF` (Q4_K_M) | Tie-break / second opinion. |

Only one is loaded at a time given `--models-max 1`. Pick before each batch.

### Prompt template

System prompt (stored as `nlp/prompts/labeling_system.txt`):

```
You are an annotation assistant for the fanfic "Brockton's Celestial
Forge" by LordRoustabout. You read short passages of prose and emit
machine-readable JSON identifying labeled spans of text.

Output a single JSON object matching this schema:

{
  "spans": [
    {"layer": "A" | "B", "start": int, "end": int, "label": "<LABEL>", "confidence": 0.0-1.0}
  ]
}

Allowed layer-A labels: ROLL_HIT, ROLL_MISS.
Allowed layer-B labels: PERK_REFERENCE, PRESENCE_ACTION, DATE_REF,
  TIME_OF_DAY, DURATION, FLASHBACK_CUE, DILATION_CUE.

start and end are character offsets into the passage exactly as provided.
The substring text[start:end] must be the literal text of the labeled span.

Layer-A spans cover roll events (prose only — never label the end-of-chapter
catalog block). Layer-B spans cover narrative anchors (prose only — never
label metadata footers). Layer-A spans may contain layer-B spans. Layer-B
spans should be tight to the action clause or named substring (no articles,
no trailing punctuation).

Do not invent text. Do not paraphrase. Do not output text outside the JSON
object. If unsure, omit the span — false negatives are preferred to false
positives.

Definitions and edge cases (abbreviated):
<INSERT label quickref here at proposal time>
```

User prompt (per passage):

```
Chapter context for the predicted roll near this passage:
  anchor: "<anchor_string>"
  banked CP: <banked_at_roll> (source: <banked_at_roll_source>)
  curator outcome: <curator_outcome or "unknown (ch 76+)">
  curator perk: <curator_perk_name>
  chapter hits in order: <chapter_acquired_perks_in_order>
  outstanding perks (cost > banked): <outstanding_perks_with_cost_gt_banked>
  constellations known: <constellations_known_by_joe>

Passage:
"""
<TEXT>
"""

Emit only the JSON object.
```

Omit any null fields from the context block. For ch 76+, show
`chapter_acquired_perks_in_order` and `outstanding_perks_with_cost_gt_banked`
in place of the curator fields.

`nlp/bootstrap.py` should:

- Strip the system prompt to ≤ 2000 tokens (the quickref is the
  variable-cost section).
- Sanity-check that every proposed `text[start:end]` matches the declared
  substring; reject and re-prompt up to 2 times if not.
- Cap output tokens at 512 — proposal sets are small.
- Set `temperature=0.1`, `top_p=0.9` for stable JSON.
- Always pass `response_format={"type":"json_object"}` if the model supports
  it (Qwen3 does).
- Persist raw model output alongside corrected output for audit
  (`data/labeled/.proposals_raw/<passage_id>.json`, gitignored).

## The review TUI

Single-screen Textual app. Goals: fast keyboard-only review, visible proposal
vs. corrected diff, durable JSONL persistence with crash safety.

### Launch

```sh
uv run python -m nlp.tui.app
```

Or from the iMac, against the Windows endpoint:

```sh
BCF_LLAMACPP_URL=http://<windows-ip>:11434 uv run python -m nlp.tui.app
```

The TUI is a *client* — it can run on the iMac and talk to Windows for
proposals, or run on the Windows box directly.

### Layout

```
┌─ BCF Annotation TUI ─ pilot.jsonl ─────────────── 187/250 ──────┐
│ ch16.1 sec 0  passage_id ch16.1_p07            strategy: event_focused │
│ regime: 2     source: roll_resolutions          confidence: 0.81 │
├─ Chapter context ────────────────────────────────────────────────┤
│ anchor: "…the wheel began to slow near the edge of the cluster"  │
│ banked: 650 CP (curator)  outcome: HIT  perk: Perfect Pitch      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Brockton focused on the wheel, watching it spin and click       │
│  into place. The screen flashed: he'd ⟦gained ⟪Perfect Pitch⟫⟧.  │
│                                                                  │
│  ⟦ ⟧ = layer A (event)        ⟪ ⟫ = layer B (anchor)             │
│                                                                  │
├─ Spans ──────────────────────────────────────────────────────────┤
│ # L Label                start end  text                         │
│ 1 A ROLL_HIT               95  119  gained Perfect Pitch         │
├─ Section labels ─────────────────────────────────────────────────┤
│ [x] pov_joe         [x] joe_on_screen    [ ] joe_mentioned_off   │
│ [x] time_real       [ ] time_flashback   [ ] time_framing        │
│ [ ] time_dilated    [x] counts_for_cp                            │
├─ Status ─────────────────────────────────────────────────────────┤
│ proposal source: Qwen3-30B-A3B   diff vs proposal: +0 span -0   │
│ Last save 0.4s ago.                                              │
└─ Keys: a=add b=edit d=delete s=save&next k=skip r=re-propose ?=help ─┘
```

The chapter-context block is displayed above the passage text so the annotator
sees the same evidence the LLM received. It is read-only and does not affect
saves.

### Keybindings

| Key | Action |
|---|---|
| `↑` / `↓` | Move highlight in span list |
| `←` / `→` | Move text-cursor in passage view (for span editing) |
| `a` | Add span at current text-cursor selection |
| `e` | Edit highlighted span (label + offsets) |
| `d` | Delete highlighted span (asks once if it was a proposal you're rejecting) |
| `l` | Cycle layer-A label on highlighted span (or pop a label-picker) |
| `L` | Cycle layer-B label on highlighted span |
| `Space` (in section labels) | Toggle the focused section flag |
| `Tab` | Cycle focus: passage → spans → section labels → header |
| `s` | Save current passage to JSONL and advance to next candidate |
| `S` | Save without advancing |
| `k` | Skip (record skip reason; do not save labels) |
| `b` | Go back to previous saved passage (read-only review) |
| `r` | Re-propose with the next-priority model |
| `R` | Re-propose with a custom prompt addendum |
| `f` | Flag for follow-up (review later) |
| `N` | Edit per-passage note (free-form text; rides on the saved record) |
| `?` | Help overlay (lists all keys and label definitions) |
| `q` | Quit (warns if unsaved) |

### Mouse

Mouse selection in the passage view selects a character range, then press `a`
(add) and pick a label from the popup. Mouse is optional; keyboard-only must
work.

### JSONL persistence

- Append-only writes. The TUI never rewrites prior lines in place.
- A passage being edited holds an in-memory record. On save:
  1. Write the new line to `pilot.jsonl` (or whichever file is active).
  2. fsync.
  3. Update an in-memory index of `passage_id → byte offset` so "go back"
     can locate prior records.
- Re-saving a passage that was previously saved appends a new record with the
  same `passage_id` and a higher `annotated_at`. A nightly
  `nlp/tui/persist.py compact` collapses dupes, keeping the latest. Compact
  is *manual*; it never runs during a session.
- A `.tui_state.json` next to the JSONL records: current candidate queue,
  last strategy, last model used, "flagged for follow-up" set.

### Crash safety

- Save-on-advance is the default; the only time work can be lost is if you
  crash mid-passage. Even that loses ≤ 1 passage's edits.
- The TUI keeps a tiny WAL at `data/labeled/.tui_wal.jsonl` that records
  every keypress's resulting span list; on launch the TUI offers to restore
  the WAL state if it ended without a clean save.

### Proposal vs. corrected diffing

A green `+` shows spans you added, a red `-` shows ones you deleted, yellow
`Δ` shows ones you edited. The diff is displayed in the status bar; the
persisted record stores both the original proposal (in
`data/labeled/.proposals_raw/`) and the final spans.

### What the TUI does *not* do

- It does not call the trained span model. Use `nlp/evaluate.py` for that.
  The TUI only consults the LLM for proposals.
- It does not edit the EPUB or the `chapter_sections.json` source. Splitting
  a section is a separate operation in the parser scripts.
- It does not auto-merge proposals from multiple models. Use one model at a
  time; switch via `r`.

## Daily annotation loop

A typical session:

1. `uv run python -m nlp.tui.app` (Windows or iMac, your choice).
2. The queue is auto-populated for the active phase. If empty, the TUI shows
   a one-screen "queue refill" panel: pick strategy, pick target count,
   confirm. The candidates are computed from `chapter_sections.json` +
   `data/derived/roll_resolutions.json` + `roll_locations_regex.json`.
3. Press `s` to load the first candidate. The TUI calls the labeling assistant
   in the background while you read the passage and chapter-context block;
   span proposals appear when proposals come back.
4. Review and correct. Pay attention to the curator outcome in the context
   block — if it says HIT with a named perk, look for that perk in the prose
   and confirm the `ROLL_HIT` span lands on the right clause.
5. After ~30 minutes, check the diff stats panel; if you've been making lots
   of `-` edits on layer-B spans, the LLM proposals are over-eager — `r` into
   the dense Qwen3-32B and continue.
6. End session by pressing `q`. The state is durable.

Pace target: ~1.5 minutes per passage in pilot, ~45 seconds in MVP once your
eye is calibrated. Pilot ≈ 6 hours of focused work; MVP ≈ 18 hours total
spread over weeks.

## Quality gates between phases

Before advancing pilot → MVP:

- [ ] Schema unchanged for the last 50 passages.
- [ ] Re-review of first 50 passages: ≥ 90% span agreement.
- [ ] At least 5 distinct chapters per regime represented.
- [ ] At least 10 examples each of `ROLL_HIT` and `ROLL_MISS`.
- [ ] At least 5 examples each of `PERK_REFERENCE`, `DATE_REF`, `TIME_OF_DAY`,
      `DURATION`, `FLASHBACK_CUE`, and `PRESENCE_ACTION`. `DILATION_CUE` is
      rare; aim for 5 but don't block on it.

Before advancing MVP → hard-case expansion:

- [ ] Span model v1 trained and meeting phase-2 thresholds.
- [ ] Per-label F1 within 0.10 of micro-F1 for every label class with ≥ 30
      examples (under-served labels are flagged for the expansion).
- [ ] No label with < 10 examples in the eval split.

## What to do if you fall behind

If labeling is slow and you need to ship something useful:

- **Skip `PRESENCE_ACTION` in the pilot**: if non-Joe-POV passages are
  slowing you down, annotate only roll events and temporal anchors in phase 1.
  Defer `PRESENCE_ACTION` to phase 2. The acquisition path still works, and
  the section `joe_on_screen` signal can be backfilled once you have more
  examples.
- **Cut temporal anchors if needed**: drop `TIME_OF_DAY` and `DURATION` from
  pilot; defer to MVP. `DATE_REF` and `FLASHBACK_CUE` are higher priority.
- **Defer section classifier**: keep using the existing rule-based classifier.
  The span model is the higher-leverage piece.
- **Stop at MVP for v1**: ship the MVP model. The acceptance bar trips on
  hard-case expansion mostly for retrospective references and `DILATION_CUE`
  precision; both are tolerable while `find_text_backed_rolls.py` still runs
  as a fallback.
