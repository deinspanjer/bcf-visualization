# Local NLP feasibility research for BCF acquisition extraction

_Date: 2026-05-04_

## Scope

Question: can we replace subscription LLM usage with a local model
trained or tuned on the primary BCF EPUB to extract power-acquisition
facts from prose with acceptable quality and maintenance cost?

Target facts in current pipeline terms:

- acquisition events tied to perks
- chapter/section anchoring
- approximate trigger locations
- confidence flags for downstream validators

## Current baseline constraints

- The repo already uses deterministic and cross-source joins
  (`parse_reference.py`, `predict_rolls.py`, `find_roll_locations.py`,
  `find_text_backed_rolls.py`, `validate_roll_locations.py`).
- EPUB prose is copyright-sensitive and not committed; local workflows
  can read `data/raw/Brocktons_Celestial_Forge.epub` when present.
- Existing downstream validators are strong; a model can be narrow in
  scope if it emits calibrated confidence and spans.

Implication: we do **not** need a general-purpose story-understanding
model. We need a robust mention+linking extractor that fails safely.

## Candidate technical approaches

### A) Prompted local instruct model only (no training)

- Use a 7B–14B instruct model with chunked chapter windows and strict
  JSON schema output.
- Pros: minimal setup, fastest to trial.
- Cons: unstable extraction on edge wording, expensive inference time,
  weaker calibration, drift across model versions.

Expected outcome: useful for exploratory labeling, not ideal as final
unattended pipeline.

### B) Small supervised token/span model + deterministic linking

- Fine-tune a compact encoder model for NER/span detection:
  - event cue spans ("gained", "rolled", etc.)
  - perk-name spans
  - optional local context tags (free perk, paid perk, duplicate)
- Then deterministically map spans to known perk directory entries using
  fuzzy string/linking rules and chapter constraints.
- Pros: cheaper inference, consistent behavior, easier regression tests.
- Cons: requires annotation set and light ML ops.

Expected outcome: best quality/cost tradeoff for this project.

### C) PEFT-tuned 7B extractor (LoRA/QLoRA)

- Train an instruction model to output structured extraction JSON.
- Pros: captures broader phrasing and implicit relations.
- Cons: more GPU/time, harder reproducibility, harder error analysis
  than explicit span+link stack.

Expected outcome: potentially higher recall, but likely overkill for
current requirements given strong deterministic post-processing.

## Annotation volume estimate

Recommended phased dataset:

1. **Pilot (150-250 passages)**
   - Goal: schema and guideline stabilization.
   - Output: inter-annotator agreement pass and taxonomy cleanup.
2. **MVP training set (1,000-1,500 passages)**
   - Balanced across early/mid/late chapters and phrasing variants.
   - Enough for first reliable span detector.
3. **Hard-case expansion (+400-700 passages)**
   - Focus on false positives in banter/worldbuilding and nested perk
     descriptions.

Passage unit: 1-3 paragraphs centered on likely acquisition context,
not full chapters.

## Hardware/time estimate

### Inference-only local prototype

- 7B quantized model: 16-24 GB VRAM (or slower CPU fallback).
- Throughput acceptable for offline batch extraction.

### Supervised small-model training

- Modern single GPU with 12-24 GB VRAM is sufficient for BERT-class
  fine-tuning.
- Typical cycle: hours, not days, for iterative retrains.

### LoRA 7B tuning

- Practical floor ~24 GB VRAM for comfortable iteration (with careful
  settings).
- Longer experiment and evaluation loops.

## Precision/recall expectations

Assuming approach B (span model + deterministic linking + validators):

- Early MVP target: precision 0.90+, recall 0.75-0.85 on acquisition
  event detection.
- After hard-case expansion: precision 0.92-0.95, recall 0.82-0.90.

Rationale: deterministic validators can suppress many false positives,
so precision should be prioritized over raw recall in automated mode.

## Validation design (must-have)

Every model output should pass through deterministic checks already
aligned with this repo:

- perk must map to known directory entry or flagged as unknown
- chapter/sequence consistency against derived timeline constraints
- conflict checks for impossible ordering
- provenance saved as text span + character offsets + model confidence

Recommendation: treat model results as "proposed events" until checks
pass; rejected proposals should be logged for active-learning sampling.

## Risks and mitigations

- **Copyright/data handling**: keep raw EPUB local-only; store only
  annotations/offsets/snippets as needed.
- **Label ambiguity**: maintain concise annotation guideline with
  concrete positive/negative examples.
- **Overfitting specific phrasing**: chapter-stratified splits and
  periodic blind holdout evaluation.
- **Maintenance burden**: prefer compact model and explicit post-rules
  over opaque large-model behavior.

## Recommendation

Proceed with **Approach B** as the primary path:

1. Build annotation guideline and pilot set.
2. Train compact span extractor.
3. Reuse existing deterministic validators for acceptance/rejection.
4. Benchmark against current heuristic+manual process.

Keep Approach A only as a labeling assistant, and defer Approach C until
B plateaus and clear recall gaps justify additional complexity.

## Proposed acceptance criteria for adoption

- Precision >= 0.92 on accepted events.
- Recall >= 0.85 on benchmark chapters.
- <2% invalid accepted events after deterministic validation.
- Full run wall-clock time compatible with local offline regeneration.
- Reproducible retrain and evaluation script checked into `scripts/`.
