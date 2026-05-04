# Label schema for BCF span and section models

_Annotation guideline. Treat this doc as authoritative for what
counts as a span and what doesn't. Update via PR; never silently._

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
entity spans frequently overlap.

### Layer A — events

What kind of mechanic-relevant thing is happening, and where?

| Label | Definition | Positive examples | Negative examples |
|---|---|---|---|
| `ACQUISITION` | Narration that the protagonist gains a perk this moment. Includes paid and free acquisitions. | `"gained Perfect Pitch"`, `"the wheel landed on Iron Lung"`, `"received [Workshop] as a bonus"` | `"could have rolled for Iron Lung"` (didn't happen); `"the Iron Lung perk had been useful last week"` (recall, not gain) |
| `MISS` | Narration of a roll that produced no perk. | `"the wheel slowed and stopped on nothing"`, `"a familiar sense of failure"`, `"missed again"` | `"would have missed if not for"` (counterfactual) |
| `ROLL_ATTEMPT` | A roll happens but its outcome is not yet narrated in the same span (i.e. the cue without the result). Use sparingly; if both attempt and outcome are present, label only the outcome (`ACQUISITION`/`MISS`). | `"the dice began to spin"` followed in a later sentence by the result | `"rolled and gained X"` — that's `ACQUISITION` only |
| `CONSTELLATION_REVEAL` | A new constellation comes online for the first time. | `"the Toolkit constellation unfolded"` | Mention of an existing constellation in passing |

Free perks (cluster bonuses, free pulls) are still `ACQUISITION`. The
distinction "free vs paid" is a downstream linker concern, derivable
from chapter facts and the perk directory.

### Layer B — entities & references

What named or referenceable thing is being talked about?

| Label | Definition | Positive examples | Negative examples |
|---|---|---|---|
| `PERK_NAME` | The literal name of a perk as it appears in prose. | `"Perfect Pitch"`, `"Master Craftsman"`, `"[Workshop]"` (include brackets) | `"his pitch perception"` (descriptive, not the named perk) |
| `CONSTELLATION_NAME` | Name of a Celestial Forge constellation. | `"Toolkit"`, `"Personal Reality"` | "the constellation he'd just unlocked" |
| `JOE_NAME` | Reference to the protagonist by personal name. | `"Joe"`, `"Joe Murphy"`, `"Mr. Murphy"` | Pronouns; nicknames not used as names |
| `JOE_CAPE_NAME` | Reference to the protagonist by cape persona. | `"Celestial Forge"`, `"the Forge"`, `"Tinker"` *only* when used as his cape epithet | "celestial forge" lowercase descriptive use; "Tinker" referring to the role generically |
| `OTHER_CAPE_NAME` | Cape names of other characters, used to ground "who is on screen." | `"Bakuda"`, `"Garment"`, `"Parian"`, `"Dragon"` | Civilian names of those same characters when used in a non-cape context |
| `DATE_REF` | Explicit calendar reference, full or partial. | `"April 14th"`, `"that Friday the 8th"`, `"2011"`, `"the morning of the 17th"` | "the next day" (use `DURATION`); "Friday" alone in dialogue with no anchor |
| `TIME_OF_DAY` | Diurnal reference. | `"that morning"`, `"after sunset"`, `"around noon"` | "morning person" (descriptive); "the morning of the 17th" — overlap with `DATE_REF` is fine, label both |
| `DURATION` | A passage of time. | `"two hours later"`, `"the next day"`, `"after a week"`, `"by the end of the afternoon"` | Distance/length metaphors |
| `FLASHBACK_CUE` | A textual marker that the narrative has shifted into a recollection or earlier scene. | `"he remembered"`, `"two years earlier"`, `"back when he was at Brockton U"` | A flashback that is signaled only by chapter framing and a line break — those are section-level, not span-level |
| `DILATION_CUE` | A textual marker that in-story time is running differently than wall time due to a power, location, or device. | `"the dilation field engaged"`, `"a heartbeat that lasted minutes"` | Mundane "it felt like forever" (use `DURATION` if anything) |

### Span boundary conventions

- **Events** (`ACQUISITION`, `MISS`, `ROLL_ATTEMPT`, `CONSTELLATION_REVEAL`):
  span the smallest natural clause that carries the event meaning,
  including the perk reference if it's adjacent. Do not span entire
  paragraphs.
  - ✅ `"gained Perfect Pitch"`
  - ❌ `"He took a breath, focused, and then gained Perfect Pitch as the wheel clicked into place."`

- **Entities** (`PERK_NAME`, etc.): span exactly the named substring.
  Do not include articles, surrounding punctuation, or trailing
  characters.
  - ✅ `"Perfect Pitch"`, `"[Workshop]"` (brackets are part of the
    in-text marker; include them)
  - ❌ `"the Perfect Pitch perk"`

- **Capitalization**: span as the prose appears. Do not normalize.

- **Overlap is allowed across layers**, not within. Layer-A spans can
  contain layer-B spans (`ACQUISITION` containing a `PERK_NAME`).
  Layer-A and layer-A may not overlap; same for layer-B / layer-B.

### Edge cases (review before labeling)

- **Retrospective references.** "Earlier that day Joe had gained Iron
  Lung" — label as `ACQUISITION` if the *grant* is the topic of this
  sentence and there is no in-scene narration of it earlier. Otherwise,
  label only `PERK_NAME`. The `find_text_backed_rolls.py` evidence-kind
  `forward_ref` distinction is what this label class is meant to catch.
- **Negated acquisitions.** "He could have rolled for X but didn't" —
  no `ACQUISITION` span; label `PERK_NAME` on X if you want it
  searchable.
- **Multiple acquisitions in one sentence.** Label each event span
  separately. Do not merge.
- **Bracketed perks.** `"[Workshop]"` and `"Workshop"` are both valid
  `PERK_NAME` spans; include the brackets when present.
- **Cape names that are also common words.** "Tinker" is only
  `JOE_CAPE_NAME` when it's clearly the protagonist's epithet, not the
  generic role. When in doubt, leave unlabeled.
- **In-dialogue dates.** "It's April 14th, isn't it?" — yes, label
  `DATE_REF` on the substring `"April 14th"`. Section-level time-mode
  is a separate decision (see below).
- **Power-induced time skips.** "Joe spent what felt like an hour in
  the field, but only seconds passed" — `DILATION_CUE` over the whole
  clause; `DURATION` on `"an hour"` and `"seconds"` if you want the
  detail.

## Section labels

Section = one entry of `data/derived/chapter_sections.json`. Already
keyed by `(chapter_num, section_index)`.

Multi-label, independent sigmoids:

| Label | Definition | True when |
|---|---|---|
| `pov_joe` | Section is narrated from Joe's POV (first-person or close third) | Existing `count_for_cp` true cases will mostly map here, but recheck |
| `joe_on_screen` | Joe is physically/causally present in the scene, regardless of POV | Joe is acting, speaking, or being described as present in the same scene; *not* mere mention or recall |
| `joe_mentioned_offscreen` | Joe is named or referenced but is not present in the scene | Other-cape POV section talking about Joe |
| `time_real` | Scene happens in current real-time narrative present | Default for most MC sections |
| `time_flashback` | Scene is a recollection of an earlier event | Marked by `FLASHBACK_CUE` spans or by chapter framing |
| `time_framing` | Scene is a framing/exposition device (PHO posts, news articles, meeting reports, in-world documents) | The existing `pho`, `news`, `meeting_report` markers usually imply this |
| `time_dilated` | Scene includes meaningful in-power time dilation that affects the chapter timeline | Marked by `DILATION_CUE`; usually short |
| `counts_for_cp` | Inherits the existing rule: Joe-POV scenes that the author counts for word-budget purposes | Same as the current rule output, kept for regression checks |

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
  "schema_version": 1
}
```

The flags are not all mutually exclusive — that's the point of using
sigmoids. But the four `time_*` labels should sum to 1 for any
non-mixed section; mixed sections (e.g. flashback inside real-time)
can set both. If a section is genuinely split, prefer to split the
section in `extract_chapter_sections.py` rather than train the model
to disambiguate within one chunk.

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
    {"layer": "A", "start": 95,  "end": 119, "label": "ACQUISITION"},
    {"layer": "B", "start": 102, "end": 114, "label": "PERK_NAME"}
  ],
  "source": "llm_proposal_reviewed",
  "model_proposal_score": 0.81,
  "annotator": "deinspanjer",
  "annotated_at": "2026-05-04T15:32:11Z",
  "schema_version": 1
}
```

Field rules:

- `passage_id` — stable identifier; convention is
  `ch<chapter>_p<index>` where `index` is 0-based within the chapter
  pre-section split.
- `epub_char_start` / `epub_char_end` — offset back into the source
  EPUB. Lets us re-extract the passage if needed.
- `text` — verbatim passage text, exactly as it appears in the EPUB
  (including whitespace).
- `spans[].start` / `spans[].end` — character offsets *into `text`*,
  not into the EPUB. End is exclusive (Python slice semantics).
- `spans[].layer` — `"A"` for events, `"B"` for entities. Keeps the
  two-head training trivial.
- `source` — one of `llm_proposal_reviewed`, `manual`, `corrected`,
  `imported`. Drives active-learning sampling.
- `model_proposal_score` — only present when `source` starts with
  `llm_`. The LLM's stated confidence (0.0–1.0).
- `schema_version` — start at `1`. Bump on any breaking change.

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
  "schema_version": 1
}
```

`first_chars` is the first ~3000 characters (matching what
`extract_chapter_sections.py` already keeps), so the file is
self-sufficient for training without re-reading the EPUB.

## BIO encoding (for layer-A and layer-B independently)

At training time, character-level spans get projected to per-token
BIO tags using `tokenizer(..., return_offsets_mapping=True)`. See
`nlp/encode.py` (to be implemented; `docs/local_nlp_training.md`
specifies the conversion).

Per-layer BIO tag sets:

```
LAYER_A = ["O", "B-ACQUISITION", "I-ACQUISITION",
           "B-MISS",        "I-MISS",
           "B-ROLL_ATTEMPT","I-ROLL_ATTEMPT",
           "B-CONSTELLATION_REVEAL", "I-CONSTELLATION_REVEAL"]

LAYER_B = ["O", "B-PERK_NAME",          "I-PERK_NAME",
           "B-CONSTELLATION_NAME",      "I-CONSTELLATION_NAME",
           "B-JOE_NAME",                "I-JOE_NAME",
           "B-JOE_CAPE_NAME",           "I-JOE_CAPE_NAME",
           "B-OTHER_CAPE_NAME",         "I-OTHER_CAPE_NAME",
           "B-DATE_REF",                "I-DATE_REF",
           "B-TIME_OF_DAY",             "I-TIME_OF_DAY",
           "B-DURATION",                "I-DURATION",
           "B-FLASHBACK_CUE",           "I-FLASHBACK_CUE",
           "B-DILATION_CUE",            "I-DILATION_CUE"]
```

Two heads, two BIO sets, jointly trained on a shared encoder.

## Data versioning

- The labeled JSONL files live in `data/labeled/` and are committed.
  They are not author prose — they are character offsets into
  unshipped prose plus our spans. Treat as derivative metadata.
- Bump `schema_version` and write a migration note in this doc when
  any field changes meaning. Do not silently re-purpose fields.
- Keep `data/labeled/spans/heldout.jsonl` reserved — it is *never*
  used for training and never inspected by the LLM during proposal
  generation. It exists for blind evaluation only.

## Annotation guideline summary (printable)

A one-screen reference for the annotator to keep open. Generate
during phase 1 from the catalog above; live as
`docs/local_nlp_label_quickref.md` (created when the schema freezes).
