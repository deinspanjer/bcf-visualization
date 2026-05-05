# Local NLP build plan

_Companion to `docs/local_nlp_research.md`. This is the implementation
plan; the research doc is the rationale._

## Goal

Replace the brittle prose-extraction layer of the pipeline (regex
catalogs in `find_roll_locations.py`, rule-based POV classification in
`build_section_classifications.py`) with locally-hosted models that:

1. Find acquisition / miss / roll-attempt events and perk-name spans in
   chapter prose.
2. Find date, time-of-day, duration, flashback, and time-dilation
   spans, plus Joe-name and cape-name mentions.
3. Classify each chapter section's POV mode, time mode, and
   counts-for-CP status.

All model outputs feed the existing deterministic validators
(`validate_roll_locations.py`, `build_perk_directory.py` linking,
`spot_check.py`) — the model proposes, the rules dispose.

## Non-goals

- Training a generator/LLM from scratch on the EPUB.
- Replacing the curator's xlsx workflow; we still consume the
  Reference and Curator spreadsheets as canonical inputs for what they
  cover.
- A general-purpose story-understanding model. Scope is the extractions
  named above.
- Cloud or subscription LLM dependence. Everything runs on-prem.

## Architecture

Two boxes, three "lanes" (HTTP endpoints) on the GPU box:

```
                  ┌──────────────────────────────────────────┐
                  │  Windows GPU box (CUDA 13.1 + cuBLAS)    │
                  │                                          │
   iMac           │   :11434  llama.cpp                      │
   (project,     ─┼─→         Qwen3-32B  / Qwen3-30B-A3B     │
    git, scripts) │           "labeling assistant" lane      │
                  │                                          │
                  │   :8000   FastAPI + transformers         │
                  │           - POST /extract       (spans)  │
                  │           - POST /classify      (section)│
                  │           - GET  /version, /health       │
                  │                                          │
                  │   :8002   TEI (optional, embeddings)     │
                  │                                          │
                  │   training runs locally via uv, not HTTP │
                  └──────────────────────────────────────────┘
```

The iMac stays a dev / orchestration box: editor, git, existing parser
scripts. New code on the iMac is just a thin client that calls the two
lanes. All model weights and training jobs live on the Windows box.

## Model inventory

| # | Role | Architecture | Backbone | Trained? | Where |
|---|------|--------------|----------|----------|-------|
| 1 | Labeling assistant + hard-case reasoner | Decoder LLM (GGUF) | `Qwen3-30B-A3B-Instruct-2507` (batch); `Qwen3-32B` (hard cases) | No (already on disk) | llama.cpp `:11434` |
| 2 | Span extractor | Encoder + token-classification head | `answerdotai/ModernBERT-base` (primary); `microsoft/deberta-v3-base` (fallback) | **Yes** — fine-tuned on BCF labeled spans | FastAPI `:8000/extract` |
| 3 | Section classifier | Encoder + multi-label sequence-classification head | Same backbone as #2 | **Yes** — fine-tuned on BCF labeled sections | FastAPI `:8000/classify` |
| 4 | Embeddings (optional) | Encoder | `BAAI/bge-base-en-v1.5` | No | TEI `:8002` or llama.cpp `--embedding` |

Two distinct trained models, both ~150–180M params, both built from the
same off-the-shelf backbone. They share an inference process but use
different fine-tuning runs and different label heads.

ModernBERT-base is preferred over DeBERTa-v3-base because:
- 8K native context fits whole sections without windowing.
- Faster inference (newer architecture, FlashAttention-friendly).
- License is permissive (Apache-2.0).

DeBERTa-v3-base remains the documented fallback if a ModernBERT-specific
issue blocks training.

## Phased rollout

The phases mirror the research doc's pilot/MVP/expansion plan, extended
to cover all label classes.

### Phase 0 — environment & scaffolding

- Install `uv`, Python 3.11, CUDA-matched `torch`, `transformers`,
  `fastapi`, `uvicorn`, `textual`, `seqeval`, `datasets`, `evaluate`.
- Create `nlp/` package layout in the repo (see `docs/local_nlp_setup.md`).
- Stand up a no-op FastAPI server with stub `/health` and `/version`
  endpoints, callable from the iMac.
- Smoke-test llama.cpp endpoint from the iMac.

Exit: iMac can reach all expected URLs on the Windows box.

### Phase 1 — pilot annotation (~250 passages)

- Implement the labeling-assistant prompt for llama.cpp (see
  `docs/local_nlp_annotation_playbook.md`).
- Implement the review TUI (Textual) and JSONL persistence.
- Bootstrap proposals for ~250 candidate passages drawn from chapters
  spanning all three regimes.
- Hand-review every proposal. Lock down the label schema (see
  `docs/local_nlp_label_schema.md`); revise as edge cases surface.
- Inter-annotator review: re-review the first 50 passages a second
  time after the schema settles. Discard the first-pass labels if drift
  is significant.

Exit: 250 passages with frozen schema, internal IAA estimate ≥ 0.9.

### Phase 2 — MVP training (~1500 passages)

- Bootstrap-and-review the rest of the MVP set (~1250 more passages),
  stratified by chapter, regime, and event type.
- Train the span model on 1200 / eval on 300 (chapter-stratified).
- Train the section classifier on the same passage pool's parent
  sections (~400 sections labeled).
- Wire the FastAPI server up to the trained checkpoints.
- Wire iMac client into a new pipeline script that reads
  `chapter_sections.json`, calls `/extract` on each section, and writes
  `data/derived/extracted_events.json`.
- Run the existing deterministic validators against the new outputs.

Exit: span model F1 ≥ 0.85 micro, section classifier F1 ≥ 0.90 macro,
end-to-end pipeline replays existing `roll_text_evidence.json` outputs
within ±5% on chapters 1–75.

### Phase 3 — hard-case expansion (+400–700 passages)

- Use active learning: sample passages where the MVP model has low
  confidence, then label them.
- Add the time/date and flashback/dilation labels in earnest (some
  appear in MVP but get a pilot-grade pass).
- Retrain. Acceptance criteria from the research doc apply (see below).

Exit: meets acceptance criteria below; pipeline integration is the
default path; regex pass survives only as a fallback.

### Phase 4 — integration and decommission

- Replace `find_roll_locations.py` consumers with span-model output;
  keep regex script as a sanity-check fallback.
- Add `extract_chapter_dates.py` script that consumes span output to
  produce per-chapter in-world dates (resolves a long-standing TODO
  item).
- Add a "Joe on screen" track to the section classifier output and
  feed it into the scrubber's POV display.
- Decide whether to retire any deterministic logic; default is to
  keep the rules as guards.

## Acceptance criteria

Lifted and refined from `docs/local_nlp_research.md`:

| Metric | Target | How measured |
|---|---|---|
| Span model precision (micro) | ≥ 0.92 on accepted events | seqeval over heldout passages |
| Span model recall (micro) | ≥ 0.85 on benchmark chapters | seqeval over heldout passages |
| Section classifier macro-F1 | ≥ 0.90 | per-label F1 averaged |
| Validator-rejection rate | < 2% of accepted events | run deterministic validators over span output |
| End-to-end replay vs `obtained_perks.json` | ≥ 95% match on chapters 1–75 | per-chapter paid-acquisition count |
| Full-pipeline wall clock | < 30 min on Windows GPU box | from raw EPUB to `chapter_facts.json` |
| Reproducibility | one-command retrain, deterministic given seed + dataset | `uv run nlp/train_span.py --version vN` |

## Doc map

| Doc | Audience | Purpose |
|---|---|---|
| `docs/local_nlp_research.md` | Anyone | Why we're doing this, options considered |
| `docs/local_nlp_plan.md` (this) | Anyone | What we're building, in what order |
| `docs/local_nlp_label_schema.md` | Annotators, model trainer | Label catalog, JSONL schemas, edge cases |
| `docs/local_nlp_setup.md` | Operator (Windows + iMac) | Install steps, env, smoke tests |
| `docs/local_nlp_annotation_playbook.md` | Annotator | Workflow + TUI spec |
| `docs/local_nlp_training.md` | Model trainer | Train scripts, eval harness, iteration |
| `docs/local_nlp_serving.md` | Operator + integrator | Endpoint specs, client integration |

## Open decisions

These are recorded as decisions to make, not blockers — defaults are
listed and can be flipped later.

1. **Backbone**: ModernBERT-base (default) vs DeBERTa-v3-base. Locked
   to ModernBERT until a training-time issue forces fallback.
2. **Single-process vs separate-process serving**: one FastAPI process
   hosting both heads (default) vs two. Single is simpler; switch only
   if VRAM contention bites.
3. **Annotation tool**: custom Textual TUI (default) vs Argilla. Custom
   is simpler for solo annotation; switch if multiple annotators.
4. **Embedding model usage**: skip until needed (default). Add when
   either model needs candidate-narrowing or clustering for active
   learning.
5. **Multi-label section head**: independent sigmoids per label
   (default) vs softmax over a flattened label set. Sigmoids handle
   "Joe on screen + flashback" cleanly.
6. **Multi-layer span overlap** (e.g. PERK_NAME inside ACQUISITION):
   two parallel heads trained jointly (default) vs flattened single
   label set with overlap-detection rules. Two heads is cleaner; cost
   is one extra forward pass at training time.

## What success looks like

After phase 3, the pipeline can be regenerated from scratch on a
machine with no internet (after the one-time model + EPUB downloads):

```sh
# on Windows box
uv run nlp/serve.py &              # span + section model on :8000
.\run-llama-server.bat &           # llama.cpp on :11434

# on iMac (existing flow + new step)
python3 scripts/extract_chapter_sections.py
python3 scripts/build_section_classifications.py   # uses /classify
python3 scripts/extract_chapter_events.py          # NEW, uses /extract
python3 scripts/extract_chapter_dates.py           # NEW, uses /extract
python3 scripts/build_chapter_facts.py             # consumes new derived
python3 scripts/spot_check.py
```

The visualization picks up new tracks (in-world dates, Joe-on-screen
indicator) by reading the new `chapter_facts.json` fields.
