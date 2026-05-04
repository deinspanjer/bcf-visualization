# Training playbook

_How to fine-tune the span model and section classifier, evaluate
them, and iterate. Pair with `docs/local_nlp_label_schema.md` for
the label catalog and `docs/local_nlp_setup.md` for the environment._

## Overview

Two trainings, one shared backbone:

| Model | Entry point | Head | Train data | Approx time on a single modern GPU |
|---|---|---|---|---|
| Span | `nlp/train_span.py` | Two parallel token-classification heads (layer A + layer B) | `data/labeled/spans/train.jsonl` | 30–90 min for ~1500 passages |
| Section | `nlp/train_section.py` | Multi-label sequence-classification head (sigmoids) | `data/labeled/sections/train.jsonl` | 10–30 min for ~400 sections |

Both fine-tune from `answerdotai/ModernBERT-base` (default) and write
checkpoints under `checkpoints/<task>/v<N>/`.

## Backbone choice

Default: **ModernBERT-base** (~149M params, 8K context, Apache-2.0).

- Native long-context handling fits whole sections without windowing.
- FlashAttention-aware; faster on the existing CUDA stack.

Documented fallback: `microsoft/deberta-v3-base` (~180M params, 512
context, MIT-derived). Switch only if a ModernBERT-specific issue
blocks training.

Environment variable `BCF_BACKBONE` overrides:

```sh
BCF_BACKBONE=microsoft/deberta-v3-base uv run python nlp/train_span.py
```

## `nlp/encode.py` — span → BIO conversion

Single utility consumed by both trainings. Pure function, easy to
unit-test.

Responsibilities:

1. Load JSONL passages and validate against the schema in
   `nlp/schema.py`.
2. Tokenize each passage with `return_offsets_mapping=True`.
3. For each layer (A and B independently), project each labeled
   `(start, end, label)` to per-token BIO tags using the offset map.
4. For passages longer than the model's max length, window with
   stride and emit one example per window. Spans are kept in any
   window that fully contains them; spans that straddle a window
   boundary are dropped from that window only (logged to a metrics
   file so we can see how often it happens).
5. Return a `datasets.Dataset` with columns:
   `input_ids`, `attention_mask`, `labels_layer_a`, `labels_layer_b`.

Test cases (in `tests/test_encode.py`):

- Span exactly on a word boundary.
- Span starting mid-token (must round to enclosing token).
- Two spans of the same layer in one passage.
- Layer-A and layer-B overlap.
- Span longer than the entire window (raises).
- Long passage forcing windowing.

## `nlp/train_span.py` — span model training

CLI shape:

```
uv run python nlp/train_span.py \
  --train data/labeled/spans/train.jsonl \
  --eval  data/labeled/spans/eval.jsonl \
  --version v1 \
  [--backbone answerdotai/ModernBERT-base] \
  [--epochs 4] [--lr 2e-5] [--batch-size 8] \
  [--seed 1337] [--bf16]
```

Required behaviors:

- Reads schema from `nlp/schema.py`. Asserts `schema_version` of the
  data matches.
- Builds two label-id maps (one per layer).
- Custom model wrapper that exposes both heads:

  ```python
  class TwoHeadTokenClassifier(PreTrainedModel):
      def __init__(self, backbone_name, num_labels_a, num_labels_b):
          ...
          self.backbone = AutoModel.from_pretrained(backbone_name)
          self.head_a = nn.Linear(d, num_labels_a)
          self.head_b = nn.Linear(d, num_labels_b)
      def forward(self, input_ids, attention_mask, labels_layer_a=None, labels_layer_b=None):
          h = self.backbone(input_ids, attention_mask=attention_mask).last_hidden_state
          logits_a = self.head_a(h)
          logits_b = self.head_b(h)
          loss = None
          if labels_layer_a is not None and labels_layer_b is not None:
              loss = (
                  cross_entropy(logits_a.view(-1, num_a), labels_layer_a.view(-1), ignore_index=-100) +
                  cross_entropy(logits_b.view(-1, num_b), labels_layer_b.view(-1), ignore_index=-100)
              )
          return TokenClassifierOutput(loss=loss, logits=(logits_a, logits_b))
  ```

- `Trainer` with `compute_metrics` that returns:
  - `f1_a_micro`, `precision_a_micro`, `recall_a_micro` (and macro)
  - `f1_b_micro`, `precision_b_micro`, `recall_b_micro` (and macro)
  - `f1_overall` (mean of the two micros, used as `metric_for_best_model`)
- Per-label metrics in `compute_metrics` output for diagnostics; not
  used for selection.
- Checkpointing: write to `checkpoints/span/<version>/epoch<N>` every
  epoch; copy best to `.../best`.

### Default hyperparameters (starting points)

| Hyperparameter | Default | Notes |
|---|---|---|
| `learning_rate` | `2e-5` | Standard for encoder fine-tuning |
| `per_device_train_batch_size` | `8` | At 8K context this is high; reduce to `4` if OOM |
| `per_device_eval_batch_size` | `16` |  |
| `num_train_epochs` | `4` | Increase to `6` if eval F1 still climbing |
| `weight_decay` | `0.01` |  |
| `warmup_ratio` | `0.1` |  |
| `max_grad_norm` | `1.0` |  |
| `lr_scheduler_type` | `cosine` |  |
| `bf16` | `True` | Falls back to `fp16` if GPU doesn't support bf16 |
| `seed` | `1337` | Pinned for reproducibility |
| `gradient_checkpointing` | `False` | Enable only if OOM at batch 4 |

### Output artifacts

Per training run, under `checkpoints/span/<version>/`:

- `best/` — model weights, tokenizer, `id2label_a.json`,
  `id2label_b.json`, `train_args.json`.
- `epoch*.json` — per-epoch eval metrics.
- `metrics_final.json` — flat key/value summary.
- `dataset_manifest.json` — file paths, sha256 of train/eval JSONL.
- `git_state.json` — current commit hash, dirty flag, branch.
- `env.json` — Python, torch, transformers, CUDA versions.

Together: enough to reproduce or audit any past run.

## `nlp/train_section.py` — section classifier training

CLI shape mirrors the span trainer:

```
uv run python nlp/train_section.py \
  --train data/labeled/sections/train.jsonl \
  --eval  data/labeled/sections/eval.jsonl \
  --version v1 \
  [--backbone answerdotai/ModernBERT-base] \
  [--epochs 4] [--lr 2e-5] [--batch-size 8] \
  [--seed 1337] [--bf16]
```

Multi-label sigmoid head:

```python
model = AutoModelForSequenceClassification.from_pretrained(
    backbone,
    num_labels=len(SECTION_LABELS),
    problem_type="multi_label_classification",
    id2label=id2label,
    label2id=label2id,
)
```

Loss is BCE-with-logits (handled by HF when `problem_type` is
`multi_label_classification`).

Compute metrics: per-label P/R/F1 + macro and micro F1. Best model by
macro-F1.

Section text input strategy:

- Prefer the first 4096 tokens of the section.
- If using DeBERTa-v3-base (512 context), use the first 512 tokens
  (matches the existing rule's first-3000-chars heuristic).

## `nlp/evaluate.py` — offline eval harness

A standalone script consumed by the trainers (and runnable on its
own):

```
uv run python nlp/evaluate.py \
  --span-checkpoint checkpoints/span/v1/best \
  --section-checkpoint checkpoints/section/v1/best \
  --span-eval data/labeled/spans/eval.jsonl \
  --span-heldout data/labeled/spans/heldout.jsonl \
  --section-eval data/labeled/sections/eval.jsonl \
  --report-out checkpoints/eval_v1_report.md
```

The report contains:

1. Per-label P/R/F1 tables (span model, two layers).
2. Macro / micro / per-label F1 (section model).
3. Confusion-style breakdown of layer-A label confusions
   (which kinds of events are mislabeled as which).
4. Top-20 false-positive and false-negative examples per layer.
5. **End-to-end pipeline replay**: feed every chapter section's text
   through the span model, run the existing deterministic linker
   against the resulting `PERK_NAME` spans, and compare the resulting
   per-chapter paid-acquisition counts against
   `data/derived/obtained_perks.json` for chapters 1–75. Surface a
   per-chapter table of agreement.
6. **Validator-rejection rate**: how many proposed spans get rejected
   by `validate_roll_locations.py`-style rules.
7. Acceptance-criteria scoreboard (red/yellow/green vs the targets in
   `docs/local_nlp_plan.md`).

The end-to-end replay is the single most important number. A model
that scores 0.95 F1 on spans but only 70% per-chapter agreement is
not a working extractor. A model that scores 0.85 F1 but 95%
per-chapter agreement is.

## Train/eval split strategy

**Chapter-stratified, not random.**

- Decide on a fixed eval set of chapters early (e.g., chapters
  spanning all three regimes: 12, 41, 56, 73, 91, 104, 130, 168).
- Every passage from those chapters goes to `eval.jsonl`. Every
  passage from any other chapter goes to `train.jsonl`.
- `heldout.jsonl` chapters are an additional set never opened in
  training or by the LLM during proposal generation. Reserve, e.g.,
  chapters 23, 67, 121, 155.
- The chapter list is recorded in `data/labeled/spans/_split.json`
  and is immutable across training runs (so eval comparisons are
  apples-to-apples).

The same chapter list governs section dataset splits.

## Reproducibility

For any training run:

```sh
git rev-parse HEAD                                  # record commit
uv run python nlp/train_span.py --version v1 ...    # respects --seed
```

`train_args.json` and `git_state.json` written to the checkpoint dir
make a run replayable by the next operator. Re-running with the same
`--version` clobbers the prior run; bump the version for any new
config.

Version numbering convention:

- `v0` — pilot scaffolding model trained on the 250-passage pilot
  set. Throwaway; used to verify the pipeline runs.
- `v1` — first MVP model, trained on the ~1500-passage train set.
- `v2`, `v3` — hard-case-expanded models. Each version's training
  data is a *strict superset* of the previous.

## Iteration playbook

Starting from `v1` after MVP labeling:

1. Run `nlp/evaluate.py` against `v1`. Read the per-label F1 table
   and the end-to-end replay.
2. Identify the worst-performing label class. For each one, ask:
   - Is it because there are too few labeled examples? (Check the
     count in `train.jsonl`.) → Add more.
   - Is it because the LLM proposals were systematically wrong on
     that label and you accepted them? → Re-review old labels.
   - Is it because the schema is genuinely ambiguous? → Update
     `local_nlp_label_schema.md` and re-label affected passages.
3. Add the new labels to `train.jsonl` (append-only; no rewrites).
4. Run `nlp/evaluate.py` again to confirm the bottom-up effect.
5. If overall passes acceptance, train `v2` and update the FastAPI
   server's pinned checkpoint.

Don't retrain on every label addition. Save retraining for batches of
≥ 100 new examples or schema-affecting fixes; otherwise iteration
cost dominates.

## Common failure modes

- **Loss diverges at first epoch.** Almost always: tokenization
  alignment is wrong and `-100` mask is missing on special tokens.
  Print the first batch's `labels_layer_a` and confirm the `[CLS]` /
  `[SEP]` positions are `-100`.
- **All metrics ~0 on a label.** Either zero examples in eval, or
  a schema/label-id mismatch between encoder run and metric run. The
  trainer should log per-label counts on startup.
- **Training works, end-to-end replay is bad.** Likely cause: the
  model learned to predict `PERK_NAME` spans that don't fuzzy-match
  the perk directory. Check `build_perk_directory.py` linking; raise
  the fuzz threshold or expand alias list.
- **OOM on Windows GPU.** Drop `per_device_train_batch_size` to 4
  and turn on `gradient_checkpointing`. ModernBERT-base + bf16 +
  batch 4 fits easily in 12 GB; if it doesn't, you're on the wrong
  torch wheel (CPU build).
- **bf16 unsupported error.** Drop to `fp16` (set `--bf16=False
  --fp16=True`).

## Acceptance bar before serving

A model checkpoint is only allowed to be promoted to the FastAPI
server if its `eval_v<N>_report.md` shows:

- Span model micro-F1 ≥ 0.85.
- Section classifier macro-F1 ≥ 0.90.
- End-to-end replay ≥ 95% chapter-level agreement on chapters 1–75.
- No per-label F1 < 0.50 with ≥ 30 examples in train.

If a candidate fails, leave the prior best in place and either label
more or fix the schema before retraining.

## What's not covered here

- **LoRA / QLoRA fine-tuning.** Not used; the base encoders are small
  enough to full-fine-tune. Revisit only if we move to a 7B+ extractor.
- **Multi-GPU.** Single GPU is the design point.
- **Continual training across schema versions.** Each schema bump
  forces a fresh training run from the backbone; the labeled data is
  reusable but the prior checkpoint is not.
