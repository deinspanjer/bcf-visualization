# Label schema for BCF span and section models

_Annotation guideline. Treat this doc as authoritative for what
counts as a span and what doesn't. Update via PR; never silently._

> **What changed in v3:** Layer B gains `PERK_REFERENCE` for in-prose
> retrospective / in-action / post-hoc mentions of perks already in Joe's
> possession (e.g. "the new power was called Mixing Mixtures"). The
> existing `ROLL_HIT` definition is unchanged: it still narrowly covers
> the Forge reaching and grabbing — naming a recently-acquired perk in
> the narrator's thoughts is now `PERK_REFERENCE`, not `ROLL_HIT`. A new
> per-passage `notes: str` field rides on `SpanRecord` for inline
> schema-calibration observations (default empty; never required). The
> `JsonlAnnotationStore` serializer stays additive, so v2 records load
> cleanly into v3 models with `notes == ""`. The data
> `schema_version` field bumps from `1` to `2`; the label-guide
> revision is informally "v3" but that's a doc-level concept distinct
> from the JSONL `schema_version` integer.

> **What changed in v2:** The label set is narrowed to prose-narrative
> signals that existing parsers cannot derive deterministically. `ACQUISITION`
> and `MISS` are replaced by `ROLL_HIT` and `ROLL_MISS` (prose-only, same
> events, clearer names). `ROLL_ATTEMPT`, `CONSTELLATION_REVEAL`, `PERK_NAME`,
> `CONSTELLATION_NAME`, `JOE_NAME`, `JOE_CAPE_NAME`, and `OTHER_CAPE_NAME` are
> all dropped. Layer B gains `PRESENCE_ACTION` (non-Joe-POV on-screen
> observation). The chapter-context payload from `data/derived/roll_resolutions.json`
> is now injected into every LLM prompt. See the migration note at the bottom
> for details.

## Goal

The labeler finds **prose-narrative signals that are not deterministically
derivable from existing pipeline data.** Three parsers already cover:

- The end-of-chapter "Jumpchain abilities this chapter:" catalog block.
- Publication and edit metadata (date fields in the footer, word counts).
- Per-chapter perk acquisition order (from `data/derived/obtained_perks.json`).

The LLM annotator's job is to find what those parsers cannot:

1. **Where in the prose body** a roll is *narratively described* (hit or miss).
2. **In-world dates and time markers** inside body prose.
3. **Joe (or his peers Mr. Duris / Apeiron) being observed** in someone else's
   POV, tied to concrete in-scene action.

**Out of scope for LLM labeling:**

- The catalog block at chapter end — do not label anything in it.
- Metadata footers — skip publication dates, word counts, chapter notes.
- Perk names, constellation names, or cape names as standalone entities —
  already covered by `obtained_perks.json` and `perk_directory.json`.

## Two datasets, two label spaces

### Span dataset (`data/labeled/spans/*.jsonl`)

Per-token labels over passage text. Used to train the **span model**
(`POST /extract`).

### Section dataset (`data/labeled/sections/*.jsonl`)

Multi-label flags over a whole section. Used to train the **section
classifier** (`POST /classify`).

A single annotation session usually labels both at once: you annotate
a passage's spans, then tick the section flags for the section that
passage belongs to.

## Span labels

Span labels are split into two parallel layers because event spans and
anchor spans frequently overlap.

### Layer A — narrative roll events (PROSE ONLY)

These labels fire **only** on prose body text. Never label the catalog block
at chapter end or any metadata footer.

| Label | Definition | Positive examples | Negative examples |
|---|---|---|---|
| `ROLL_HIT` | Clause narrating the Forge reaching for and grabbing a perk — the act of acquisition as described in prose. Includes paid and free acquisitions. | `"gained Perfect Pitch"`, `"the wheel landed on Iron Lung"`, `"received [Workshop] as a bonus"`, `"the Forge closed around it"` | Catalog entry `"Iron Lung (600 CP)"` — that's the end-of-chapter block, out of scope; `"the Iron Lung perk had been useful last week"` — recall, not the prose event |
| `ROLL_MISS` | Clause narrating the Forge reaching but failing to grab — the act of missing as described in prose. | `"the wheel slowed and stopped on nothing"`, `"a familiar sense of failure"`, `"missed again"`, `"the Forge grasped and found only void"` | `"would have missed if not for"` (counterfactual); `"missed"` in a non-roll context |

Free perks (cluster bonuses, free pulls) are still `ROLL_HIT`. The
distinction "free vs paid" is a downstream linker concern, derivable from
chapter facts and the perk directory.

Every roll resolves to `ROLL_HIT` or `ROLL_MISS`. If the prose narrates the
attempt but the outcome isn't stated in the same span, hold off and label the
outcome sentence when you reach it; if it never appears in the passage window,
leave the attempt unlabeled. There is no `ROLL_ATTEMPT` label — resolved spans
are what we want.

### Layer B — narrative anchors (PROSE ONLY)

These labels fire **only** on prose body text. Never label metadata footers or
chapter catalog blocks.

| Label | Definition | Positive examples | Negative examples |
|---|---|---|---|
| `PERK_REFERENCE` | A clause naming a specific perk in narrative body prose, where the mention serves as a marker that the perk is in Joe's possession or context. Includes retrospective references, in-action mentions, and post-hoc naming of recently-acquired perks. Span the named substring tightly. | `"the new power was called Mixing Mixtures"` → span `"Mixing Mixtures"`; `"Iron Lung had been useful"` → span `"Iron Lung"`; `"I activated my Workshop"` → span `"Workshop"`; `"the [Workshop] hummed"` → span `"[Workshop]"` (include bracket markers when they appear in prose) | The end-of-chapter `"Jumpchain abilities this chapter:"` catalog block (deterministic data; not labelable). Constellation names are not `PERK_REFERENCE` (no Layer-B label currently — pending future schema bump). |
| `PRESENCE_ACTION` | In a **non-Joe-POV** section, a clause where Joe / Mr. Duris / Apeiron is observed doing something in the scene's now: action, dialogue, or observed posture. Does NOT fire in Joe-POV sections, and does NOT fire on recalled or reported action (things they did off-screen or in the past). | `"Apeiron stepped forward"`, `"Mr. Duris set the container on the table"`, `"Joe caught her eye and nodded"`, `"the Forge's voice came from the side of the room"` | `"she'd heard Apeiron had fixed it last week"` (reported, off-screen); `"Joe noticed the pattern"` (Joe is the POV here — don't fire in Joe-POV sections); `"Mr. Duris would probably agree"` (hypothetical, not in-scene now) |
| `DATE_REF` | Explicit calendar reference inside body prose, full or partial. | `"April 14th"`, `"that Friday the 8th"`, `"2011"`, `"the morning of the 17th"` | `"the next day"` (use `DURATION`); `"Friday"` alone in dialogue with no anchor; footer date fields |
| `TIME_OF_DAY` | In-world diurnal reference inside body prose. | `"that morning"`, `"after sunset"`, `"around noon"` | `"morning person"` (descriptive, not a time reference); overlap with `DATE_REF` is fine — label both when both apply |
| `DURATION` | In-world passage of time inside body prose. | `"two hours later"`, `"the next day"`, `"after a week"`, `"by the end of the afternoon"` | Distance or length metaphors unrelated to time |
| `FLASHBACK_CUE` | In-prose marker of recollection or shift into an earlier scene. | `"he remembered"`, `"two years earlier"`, `"back when he was at Brockton U"` | A flashback signaled only by chapter framing and a line break — those are section-level, not span-level |
| `DILATION_CUE` | In-prose marker of in-power time dilation — in-story time running differently than wall time due to a power, location, or device. | `"the dilation field engaged"`, `"a heartbeat that lasted minutes"` | Mundane `"it felt like forever"` (use `DURATION` if anything) |

#### `PRESENCE_ACTION` — extended examples

The non-Joe-POV / scene-now distinction is the hardest judgment call in layer B.
Study these before labeling:

**Positive — fire `PRESENCE_ACTION`:**

- `"Apeiron stepped forward and extended his hand."` — Other-POV section,
  in-scene, present action.
- `"Mr. Duris set the container on the table without looking up."` — Same.
- `"Joe caught her eye and nodded once."` — Other-POV section; Joe is
  observed in the moment.
- `"The Forge's voice came from the side of the room, quiet and measured."` —
  Cape-name stand-in; in-scene observation.

**Negative — do not fire:**

- `"She'd heard Apeiron had repaired the device last week."` — Reported
  off-screen; not observed now.
- `"Joe noticed the pattern first."` — Joe is the POV subject; `PRESENCE_ACTION`
  does not fire in Joe-POV sections.
- `"Mr. Duris would probably agree with that assessment."` — Hypothetical
  attribution; not in-scene action.
- `"Apeiron had to have known."` — Inference about past state; not an
  observed action.

#### `PERK_REFERENCE` — extended examples

This label fires often once a chapter has accumulated perks Joe owns:
the narrator names a perk in the body prose to mark it as "in play."

**Positive — fire `PERK_REFERENCE`:**

- `"the new power was called Mixing Mixtures"` — span `"Mixing Mixtures"`.
  Retrospective naming of a recently-acquired perk.
- `"Iron Lung had been useful when the smoke rolled in"` — span `"Iron Lung"`.
  Past-tense retrospective; the perk is named to mark its use.
- `"I activated my Workshop and let it pull the schematic together"` — span
  `"Workshop"`. In-action mention; the perk is being used in the scene.
- `"He still hadn't gotten the hang of [Tinker Specialization]"` — span
  `"[Tinker Specialization]"`. Bracket markers in prose are part of the span.

**Negative — do not fire:**

- `"Iron Lung (600 CP)"` inside the end-of-chapter catalog block — out of
  scope; the catalog is parsed deterministically.
- `"the Forge snatched Mixing Mixtures from the wheel"` — that's a
  `ROLL_HIT` clause; the perk-name substring inside it can additionally be
  labeled `PERK_REFERENCE` (cross-layer overlap allowed) but the outer
  grab-clause is `ROLL_HIT`, not `PERK_REFERENCE`.
- A constellation name standing alone (e.g. `"the Tinker constellation"`)
  — there is no Layer-B label for constellations yet; do not stretch
  `PERK_REFERENCE` to cover them.

### Span boundary conventions

- **Events** (`ROLL_HIT`, `ROLL_MISS`): span the smallest natural clause
  that carries the event meaning, including an adjacent perk reference if
  the name is part of the same clause. Do not span entire paragraphs.
  - ✅ `"gained Perfect Pitch"`
  - ❌ `"He took a breath, focused, and then gained Perfect Pitch as the wheel clicked into place."`

- **Anchors** (`PERK_REFERENCE`, `PRESENCE_ACTION`, `DATE_REF`, `TIME_OF_DAY`,
  `DURATION`, `FLASHBACK_CUE`, `DILATION_CUE`): `PRESENCE_ACTION` uses the
  same action-clause boundary as events. The remaining six anchor labels use
  a tight named-substring boundary — no articles, no surrounding punctuation,
  no trailing characters. For `PERK_REFERENCE`, *do* include bracket markers
  when the prose itself wraps the name in brackets.
  - ✅ `"April 14th"`, `"two hours later"`, `"he remembered"`,
       `"Mixing Mixtures"`, `"[Workshop]"`
  - ❌ `"the April 14th incident"`, `"about two hours later or so"`,
       `"the Mixing Mixtures power"`, `"my Workshop"`

- **Capitalization**: span as the prose appears. Do not normalize.

- **Overlap is allowed across layers, not within.** A `ROLL_HIT` span can
  contain an incidentally useful anchor span — including a `PERK_REFERENCE`
  on the perk name nested inside the grab clause. Two layer-A spans may not
  overlap; two layer-B spans may not overlap.

### Edge cases (review before labeling)

- **Retrospective `ROLL_HIT`.** `"Earlier that day Joe had gained Iron Lung"`
  — label as `ROLL_HIT` if the *grant* is the topic of this sentence and
  there is no in-scene narration of it earlier in the passage window.
  The `data/derived/roll_resolutions.json` `anchor_string` field is provided
  as context to help you judge whether an earlier scene already covered it.
- **Retrospective `ROLL_MISS`.** Same logic — label if this sentence is the
  only narration of the miss event.
- **Negated acquisitions.** `"He could have rolled for X but didn't"` — no
  `ROLL_HIT` or `ROLL_MISS`; the Forge did not actually reach.
- **Multiple rolls in one sentence.** Label each event span separately.
  Do not merge.
- **In-dialogue dates.** `"It's April 14th, isn't it?"` — yes, label
  `DATE_REF` on `"April 14th"`. Section-level time-mode is a separate
  decision.
- **Power-induced time skips.** `"Joe spent what felt like an hour in the
  field, but only seconds passed"` — `DILATION_CUE` over the whole clause;
  `DURATION` on `"an hour"` and `"seconds"` if you want the detail.
- **`PRESENCE_ACTION` and dialogue.** Dialogue spoken by Joe *in the scene*
  fires `PRESENCE_ACTION` — it's observable. Dialogue merely reported by
  another character (`"she said Joe had told her..."`) does not.
- **`PRESENCE_ACTION` and ambiguous POV.** If a section's POV is unclear,
  check `chapter_sections.json`'s `pov_joe` flag for the section. When in
  doubt, consult the section labels panel in the TUI before deciding.

## Section labels

Section = one entry of `data/derived/chapter_sections.json`. Already
keyed by `(chapter_num, section_index)`.

Multi-label, independent sigmoids:

| Label | Definition | True when |
|---|---|---|
| `pov_joe` | Section is narrated from Joe's POV (first-person or close third) | Existing `counts_for_cp` true cases will mostly map here, but recheck |
| `joe_on_screen` | Joe is physically/causally present in the scene, regardless of POV | Joe is acting, speaking, or being described as present in the same scene; *not* mere mention or recall |
| `joe_mentioned_offscreen` | Joe is named or referenced but is not present in the scene | Other-cape POV section talking about Joe |
| `time_real` | Scene happens in current real-time narrative present | Default for most POV sections |
| `time_flashback` | Scene is a recollection of an earlier event | Marked by `FLASHBACK_CUE` spans or by chapter framing |
| `time_framing` | Scene is a framing/exposition device (PHO posts, news articles, meeting reports, in-world documents) | The existing `pho`, `news`, `meeting_report` markers usually imply this |
| `time_dilated` | Scene includes meaningful in-power time dilation that affects the chapter timeline | Marked by `DILATION_CUE`; usually short |
| `counts_for_cp` | Inherits the existing rule: Joe-POV scenes the author counts for word-budget purposes | Same as the current rule output, kept for regression checks |

Note: once `PRESENCE_ACTION` labeling produces evidence about non-Joe-POV
sections where Joe is on screen, we will revisit whether `counts_for_cp` should
expand. For now, keep the existing rule output and do not adjust it manually.

Each section gets a dict like:

```json
{
  "chapter_num": "16.1",
  "section_index": 0,
  "labels": {
    "pov_joe": false,
    "joe_on_screen": false,
    "joe_mentioned_offscreen": true,
    "time_real": true,
    "time_flashback": false,
    "time_framing": false,
    "time_dilated": false,
    "counts_for_cp": false
  },
  "annotator": "deinspanjer",
  "annotated_at": "2026-05-04T15:32:11Z",
  "schema_version": 2
}
```

The four `time_*` labels should sum to 1 for any non-mixed section; mixed
sections (e.g. flashback inside real-time) can set both. If a section is
genuinely split, prefer to split the section in `extract_chapter_sections.py`
rather than training the model to disambiguate within one chunk.

## Span dataset JSONL schema

One line per labeled passage:

```json
{
  "passage_id": "ch16.1_p07",
  "chapter_num": "16.1",
  "section_index": 0,
  "epub_char_start": 482311,
  "epub_char_end": 482729,
  "text": "Brockton focused on the wheel...",
  "spans": [
    {"layer": "A", "start": 95,  "end": 119, "label": "ROLL_HIT"},
    {"layer": "B", "start":  0,  "end":  22, "label": "PRESENCE_ACTION"}
  ],
  "source": "llm_proposal_reviewed",
  "model_proposal_score": 0.81,
  "annotator": "deinspanjer",
  "annotated_at": "2026-05-04T15:32:11Z",
  "notes": "",
  "schema_version": 2
}
```

Field rules:

- `passage_id` — stable identifier; convention is `ch<chapter>_p<index>`
  where `index` is 0-based within the chapter pre-section split.
- `epub_char_start` / `epub_char_end` — offset back into the source EPUB.
  Lets us re-extract the passage if needed.
- `text` — verbatim passage text, exactly as it appears in the EPUB
  (including whitespace).
- `spans[].start` / `spans[].end` — character offsets *into `text`*, not
  into the EPUB. End is exclusive (Python slice semantics).
- `spans[].layer` — `"A"` for roll events, `"B"` for anchors. Keeps the
  two-head training trivial.
- `source` — one of `llm_proposal_reviewed`, `manual`, `corrected`,
  `imported`. Drives active-learning sampling.
- `model_proposal_score` — only present when `source` starts with `llm_`.
  The LLM's stated confidence (0.0–1.0).
- `notes` — optional free-form annotator note attached to this passage
  (default `""`). Used for inline schema-calibration observations
  ("revisit later", "ambiguous PERK_REFERENCE boundary", etc.). Not
  shown in any UI listing when empty. Editable in the TUI via `N`.
- `schema_version` — `2` for all records created under this schema.

## Section dataset JSONL schema

```json
{
  "chapter_num": "16.1",
  "section_index": 0,
  "header": "16.1 Interlude Weld",
  "first_chars": "Weld looked over the bay...",
  "word_count": 1843,
  "labels": {
    "pov_joe": false,
    "joe_on_screen": false,
    "joe_mentioned_offscreen": true,
    "time_real": true,
    "time_flashback": false,
    "time_framing": false,
    "time_dilated": false,
    "counts_for_cp": false
  },
  "annotator": "deinspanjer",
  "annotated_at": "2026-05-04T15:32:11Z",
  "schema_version": 2
}
```

`first_chars` is the first ~3000 characters (matching what
`extract_chapter_sections.py` already keeps), so the file is self-sufficient
for training without re-reading the EPUB.

## BIO encoding (for layer-A and layer-B independently)

At training time, character-level spans get projected to per-token BIO tags
using `tokenizer(..., return_offsets_mapping=True)`. See `nlp/encode.py`
(to be implemented; `docs/local_nlp_training.md` specifies the conversion).

Per-layer BIO tag sets:

```
LAYER_A = ["O", "B-ROLL_HIT",  "I-ROLL_HIT",
                "B-ROLL_MISS", "I-ROLL_MISS"]

LAYER_B = ["O", "B-PERK_REFERENCE",  "I-PERK_REFERENCE",
                "B-PRESENCE_ACTION", "I-PRESENCE_ACTION",
                "B-DATE_REF",        "I-DATE_REF",
                "B-TIME_OF_DAY",     "I-TIME_OF_DAY",
                "B-DURATION",        "I-DURATION",
                "B-FLASHBACK_CUE",   "I-FLASHBACK_CUE",
                "B-DILATION_CUE",    "I-DILATION_CUE"]
```

Two heads, two BIO sets, jointly trained on a shared encoder.

## Chapter-context payload

Each span-labeling candidate is enriched with a `roll_context` dict derived
by `scripts/derive_roll_resolutions.py` and stored in
`data/derived/roll_resolutions.json`. The bootstrap script appends a formatted
"Chapter context for the predicted roll near this passage" block to the user
prompt so the LLM (and the human annotator via the TUI) sees the same
contextual evidence.

This context is for annotation candidate selection. Canonical roll ownership,
deferred narration, display coordinates, and CP accounting live in
`data/derived/roll_facts.json` and flow into `chapter_facts.json`.

Fields (omit any that are null):

| Field | Type | Description |
|---|---|---|
| `chapter_num` | string | Mechanical predicted-roll chapter identifier, e.g. `"16.1"` |
| `section_index` | int | Section index within chapter |
| `predicted_char_offset` | int | Character offset of the predicted roll position |
| `anchor_string` | string | Last ~15 words of prose immediately before the predicted roll position |
| `banked_at_roll` | int | CP banked at the predicted roll moment |
| `banked_at_roll_source` | string | `"curator"` or `"roll_trigger_cp_threshold"` |
| `curator_chapter_num` | string or null | Chapter identifier per the curator log (null when no curator entry exists, e.g. ch 76+) |
| `chapter_attribution_disagreement` | bool | `true` when the curator's `chapter_num` differs from the simulator's `chapter_num` |
| `curator_outcome` | string or null | `"HIT"`, `"MISS"`, or null (ch 76+ not yet curated) |
| `curator_perk_name` | string or null | Curator-validated perk name for HIT rows |
| `curator_constellation` | string or null | Curator-validated constellation |
| `curator_cost` | int or null | Curator-validated perk cost |
| `curator_free_associated_perks` | list or null | Free perks acquired alongside this hit |
| `chapter_acquired_perks_in_order` | list | Acquired perks listed for this chapter in `obtained_perks.json`, ordered |
| `outstanding_perks_with_cost_gt_banked` | list | Top 5 catalog perks with cost > banked CP, ascending by cost |
| `constellations_known_by_joe` | list | Constellation names Joe currently knows at this point |

For chapters 1–75 the `curator_outcome` field is validated; for ch 76+ it is
null and the labeler relies on `chapter_acquired_perks_in_order` plus
`outstanding_perks_with_cost_gt_banked` to reason about plausible outcomes.

When `chapter_attribution_disagreement` is `true`, the curator's recorded perk
name may **not** appear in `chapter_acquired_perks_in_order` (which reflects the
simulator's chapter view).  The bootstrap prompt will prepend a disclaimer so
the LLM is warned not to confabulate a span for a perk that is absent from the
passage.

The TUI displays the context block above the passage so the annotator sees the
same evidence the LLM did.

## Data versioning

- The labeled JSONL files live in `data/labeled/` and are committed. They are
  not author prose — they are character offsets into unshipped prose plus our
  spans. Treat as derivative metadata.
- Bump `schema_version` and write a migration note in this doc when any field
  changes meaning. Do not silently re-purpose fields.
- Keep `data/labeled/spans/heldout.jsonl` reserved — it is *never* used for
  training and never inspected by the LLM during proposal generation. It exists
  for blind evaluation only.

### Migration: v1 → v2

Schema v2 narrows the label set to signals that the existing parsers cannot
derive. In layer A, `ACQUISITION` → `ROLL_HIT` and `MISS` → `ROLL_MISS`;
`ROLL_ATTEMPT` and `CONSTELLATION_REVEAL` are dropped entirely. In layer B,
`PERK_NAME`, `CONSTELLATION_NAME`, `JOE_NAME`, `JOE_CAPE_NAME`, and
`OTHER_CAPE_NAME` are dropped; `PRESENCE_ACTION` is added. The six temporal
anchor labels (`DATE_REF`, `TIME_OF_DAY`, `DURATION`, `FLASHBACK_CUE`,
`DILATION_CUE`) are unchanged. Any v1 spans with a dropped label should be
migrated by the script `scripts/migrate_spans_v1_to_v2.py` (to be written):
it renames `ACQUISITION` → `ROLL_HIT` and `MISS` → `ROLL_MISS`, deletes
spans with dropped labels, and bumps `schema_version` to `2`. Do not silently
re-use v1 files against v2 code.

## Annotation guideline summary (printable)

A one-screen reference for the annotator to keep open. Generate during phase 1
from the catalog above; live as `docs/local_nlp_label_quickref.md` (created
when the schema freezes).
