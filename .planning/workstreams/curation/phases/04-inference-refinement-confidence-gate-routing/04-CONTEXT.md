# Phase 4: Inference Refinement, Confidence Gate & Routing - Context

**Gathered:** 2026-08-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Stage 2: an inference pass that consumes Stage 1's candidates, recovers what deterministic heuristics cannot, grades the result, and routes by confidence into the trusted corpus or a proposals sidecar. Plus CINF-04's agent-run ledger for idempotency.

**This is the first phase that spends real API budget.** Phase 3's measurement is the input that sizes it: Stage 1 is confirmed on 4 of 663 rolls, so inference carries essentially all the semantic load.

**In scope:** ACUR-01 Stage 2, ACUR-02 (confidence gate), ACUR-03 (routing), CINF-04 (ledger idempotency).
**Not in scope (Phase 5):** the Forge Curator proposal-review flow (ACUR-04) and the full batch over the 80 uncurated chapters (ACUR-05). Phase 4 calibrates and proves on curated chapters; Phase 5 runs at scale.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked — do not re-litigate)

- **`CURATION-CONVENTIONS.md` is the domain contract.** Read in full. Stage 2's prompts must teach the four-beat evidence shape, bundle-vs-multi-grab grouping, roll placement, miss handling, and §5's partial-evidence rule.
- **Phase 2 D-13 posture:** the mechanical verifier is exact-or-reject with no fuzzy path. Stage 2 may propose; the verifier judges. Never loosen the verifier to accommodate model output.
- **Phase 2 D-06(c):** paid perks resolve via the `perk_name_resolver` ladder, cost-0 ride-alongs via `obtained_perks.json`. Never add ride-alongs to the rollable directory.
- **Phase 2 D-12:** nothing bounds a quote's distance from its roll's `word_position` (measured max 7,392 words).
- **Phase 3 D-01/D-02:** `curated_by` is required and chapter-level. Agent-written chapters stamp `"agent"`.
- **Curation authority:** an existing hand-curated chapter entry is never overwritten (CINF-04). Since agents never touch curated chapters, no chapter mixes provenance — D-02's per-roll deferral holds.
- **Writes go through `chapter_roll_overrides_io.write_chapter_roll_overrides_doc`** (validated + atomic). No new write path.

### Input shape — the dominant cost decision (auto-resolved 2026-08-02)

Measured token volumes:

| Input strategy | Volume | Adequacy |
|---|---|---|
| 250-word prose windows only | ~434k tokens | insufficient — misses `forward_ref` evidence by construction |
| Windows + bounded forward span | ~1.7M tokens | targeted |
| Whole chapters | ~3,531k tokens | 8× the window cost, mostly irrelevant text |

- **D-01:** Stage 2 receives, per candidate: the Stage 1 candidate object, its `prose_window`, its `matching_events`/`matching_anchor_kinds`, and its `evidence_kind`. **Never the whole chapter.**
- **D-02 (the `forward_ref` answer):** for `forward_ref` candidates — 485 rolls, 68% and Stage 2's principal job — additionally supply the prose span from the roll position to `next_specific_event_offset`, which `roll_text_evidence.json` already carries for **all 485**. Measured span: median 969 words, p90 3,713, with a pathological max of ~46k words. **Cap the span** (p90 is a defensible starting point) and mark any candidate whose span was truncated, so a miss caused by truncation is distinguishable from a miss caused by the model. Do not silently send an unbounded tail.
- **D-03:** exemplars come from `query_exemplars.retrieve()` (same-regime, deterministic), bounded to a small k. The full `exemplar_index.json` is 419 KB and must never be sent whole. Exemplars belong in the cached shared prefix (D-05), not per-request.

### API mechanics (auto-resolved 2026-08-02, per `.planning/research/STACK.md`)

- **D-04:** Message Batches API for any multi-chapter run — purpose-built for N independent non-latency-sensitive requests at 50% lower cost. Key results by `custom_id`; **results arrive in arbitrary order, never assume positional correspondence.**
- **D-05:** Prompt caching with a `cache_control` breakpoint on the shared system prefix (conventions + schema + retrieved exemplars). That prefix is identical across requests in a run, so each subsequent request pays ~0.1× for it. Batching and caching compose — use both.
- **D-06:** Structured outputs (`output_config.format` JSON Schema with `additionalProperties: false`, or `client.messages.parse()` with a Pydantic model). **No free-text-then-parse.** The output schema is the roll-object schema plus a self-reported confidence field and a one-line reasoning string.
- **D-07 (model tiering):** calibrate on `claude-opus-5`. Only step the bulk pass down to `claude-sonnet-5` once calibration shows it clears the same verifier + confidence bar — and make that a data-driven decision against held-out chapters, not an assumption. Never Haiku: exact-quote fidelity matters more than latency here.

### What the model may and may not produce (auto-resolved 2026-08-02)

- **D-08:** The model proposes *quote text* and *structure* (grouping, constellation, outcome). It never emits word positions or roll ordinals. Positions are derived mechanically by locating the proposed quote via Phase 2's `cp_word_index` + verifier, exactly as a human curation is verified. A quote that cannot be located is a failed proposal, not a position to invent.
- **D-09:** Every proposed quote passes Phase 2's `verify_roll()` before it can contribute to a high-confidence routing decision. The verifier is the hard gate (ACUR-02); the model's self-reported confidence is a **tiebreaker only** and can never promote a candidate the verifier rejected.
- **D-10:** §5 of the conventions still governs: partial output is correct output. Stage 2 marking a field evidence-not-found is a success, not a failure, and should route to proposals rather than being dropped or guessed.

### Confidence gate & routing (auto-resolved 2026-08-02)

- **D-11:** Confidence is composite and code-computed: (a) every evidence quote passes verifier Tier 1/Tier 2; (b) the roll's structure agrees with the mechanical bundle from `obtained_perks.json`; (c) perk names resolve per D-06(c); (d) model self-report as tiebreaker only. High confidence requires (a)+(b)+(c). Anything else routes to proposals.
- **D-12:** Regime-boundary sensitivity (ACUR-02): chapters carrying the `is_boundary` flag from Phase 1's exemplar index must route to low confidence more often — verify this empirically rather than asserting it.
- **D-13:** Proposals sidecar uses the **same roll-object schema** as the corpus (Phase 3 D-05 precedent), so Phase 5's TUI review needs no translation layer. Location and file shape are Claude's discretion; a `data/derived/` artifact or a `data/manual/`-adjacent proposals file both defensible — but it is NOT the trusted corpus and must never be loaded as such.
- **D-14 (do not lower the bar to raise the count):** per STACK.md, a large proposals volume is a legitimate outcome. If high-confidence yield is low, that is a finding for Dre's review queue — never a reason to relax verification.

### Idempotency & the ledger (auto-resolved 2026-08-02)

- **D-15:** Agent-run ledger is a separate file keyed by chapter (Workstream Gate 2), holding run bookkeeping: model, run_id, corpus fingerprint, confidence, timestamps. It is NOT part of the overrides schema.
- **D-16:** Re-running a chapter with unchanged inputs produces **no diff**. The fingerprint must cover everything that could change the output — at minimum the chapter's prose, its Stage 1 candidates, the conventions/prompt version, and the model id. A prompt or model change must invalidate the fingerprint, or "no diff" silently becomes "stale output preserved."

### Calibration & cost control (auto-resolved 2026-08-02)

Measured pool: **108 genuinely curated chapters** (10 stubs excluded), **80 uncurated** targets for Phase 5.

- **D-17:** Split the 108 curated chapters into a calibration set and a **held-out** set. Tune the rubric on calibration only; report final numbers on held-out. Tuning against the set you report on produces a number that cannot be trusted — and Phase 3 just demonstrated how easily a measurement can mislead.
- **D-18:** Report Stage 2's improvement **per evidence class against Phase 3's recorded Stage 1 baseline** (`candidate-accuracy-report.md`), using the same three-tier position ladder so the comparison is like-for-like. Success criterion 1 is comparative; a standalone Stage 2 number does not satisfy it.
- **D-19 (spend discipline):** before any batch, emit a **dry-run token estimate** (request count, cached-prefix size, per-request input, projected cost) and gate the run on an explicit ceiling. Start with a small pilot batch, verify the whole pipeline end-to-end, then scale. This phase must not be able to spend unbounded budget by accident.
- **D-20:** A `checkpoint:decision` before the first run against **uncurated** chapters (roadmap note). Calibration on curated chapters is self-checking because ground truth exists; uncurated output has none, so Dre sees the calibration numbers before that boundary is crossed.

### Claude's Discretion

- Prompt composition and the exact cached-prefix contents (must include the conventions and the output schema)
- The forward-span cap value and truncation-marking mechanism (D-02)
- Exemplar count `k` (D-03)
- Calibration/held-out split ratio and selection method — must be deterministic and recorded
- Ledger file location and serialization
- Proposals sidecar location/format within D-13's constraints

### Known-accepted baseline (do NOT chase)

5 pre-existing failures: 4 `tests/test_forge_curator.py`, 1 `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`. `scripts/verify.py` exits 1 for that reason. Judge by "no NEW failures".

### Note for the planner: AI-SPEC applies here

Phases 1–3 skipped the `ai-integration` capability with rationale — they were deterministic. **Phase 4 genuinely builds an AI system**, so `/gsd-ai-integration-phase` should fire and produce an AI-SPEC.md (framework choice, evaluation strategy, guardrails, monitoring). Do not skip it here on the precedent of the earlier phases.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain contract (read first)
- `.planning/workstreams/curation/CURATION-CONVENTIONS.md` — the practice Stage 2 must reproduce; §5 partial evidence and §6 search posture are load-bearing for the confidence gate.
- `.planning/workstreams/curation/WOG-NOTES.md` — quote-less rolls are legitimate (ch 121.1).

### Measured inputs
- `.../phases/03-.../candidate-accuracy-report.md` and `.json` — Stage 1's baseline, per evidence class, with the three-tier position ladder. Success criterion 1 measures against this.
- `.../phases/01-.../corpus-analysis-report.md` — corpus shape: 57.6% of hit rolls multi-grab, evidence-quote patterns.
- `.planning/research/STACK.md` — Batches API, prompt caching, structured outputs, model tiering, and the "never trust bare model confidence" rationale behind D-11.

### Prior locked decisions
- `.../phases/02-mechanical-verifier/02-CONTEXT.md` — D-03 quote tiers, D-04 position tolerance, D-05 three outcomes, D-06(c) paid/free resolution, D-12 evidence spread, D-13 search posture.
- `.../phases/03-.../03-CONTEXT.md` — D-01/D-02 provenance, D-04/D-05 candidate artifact and schema reuse, D-06 partial evidence, D-07 class expectations.
- `.planning/workstreams/curation/ROADMAP.md` Workstream Gate 2 — provenance shape and the separate ledger.

### Code (primary sources)
- `scripts/build_candidate_rolls.py` + `data/derived/candidate_rolls.json` — Stage 2's input (718 candidates, 712 with `unfilled_fields`).
- `data/derived/roll_text_evidence.json` — `prose_window` (250-word setting, ~500 words actual), `matching_events`, `evidence_kind`, and `next_specific_event_offset` (present for all 485 `forward_ref` rolls — the D-02 mechanism).
- `scripts/mechanical_verifier.py` — `verify_roll()` / `verify_chapter()`; the hard confidence signal.
- `scripts/cp_word_index.py` — tokenizer + prose loader for mechanical position derivation.
- `scripts/query_exemplars.py` + `data/derived/exemplar_index.json` (419 KB) — same-regime retrieval; `is_boundary` drives D-12.
- `scripts/chapter_roll_overrides_io.py` — the validated, atomic loader/writer. The only sanctioned corpus write path.
- `scripts/perk_name_resolver.py`, `data/derived/obtained_perks.json` — perk resolution per D-06(c).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2's verifier is the confidence gate's hard signal — already exact-or-reject, already 100% on the corpus.
- Phase 1's exemplar retrieval is deterministic and same-regime constrained; `is_boundary` chapters are pre-tagged.
- `roll_text_evidence.json` already carries the forward-reference offsets that make D-02's bounded expansion possible without new scanning.
- Phase 3's `chapter_roll_overrides_io` gives validated + atomic writes — agent writes inherit crash-safety and schema enforcement for free.

### Established Patterns
- `build_*`/`derive_*` scripts: argparse + pure-function core + `SCHEMA_VERSION`; tests import pure functions with synthetic fixtures.
- Derived artifacts carry registered schemas under `data/derived/_schemas/`.
- Every phase so far has kept LLM out of the loop; this is the first that does not, so the boundary between "model proposes" and "code decides" must be explicit in the code structure, not just in prose.

### Integration Points
- Phase 5's TUI review reads the proposals sidecar — D-13's schema reuse is what keeps that free.
- The ledger anchors CINF-04 and is read by Phase 5's batch run for resumability.

</code_context>

<specifics>
## Specific Ideas

- The honest framing from Phase 3: Stage 1 enumerates and marks; Stage 2 does the reasoning. Plan for that rather than for Stage 2 polishing a mostly-correct input.
- `forward_ref` at 68% is the phase. If Stage 2 does not move that class, it has not earned its budget — and D-02's bounded span is the mechanism that makes attempting it affordable.
- Dre is budget-conscious and has said so explicitly. D-19's dry-run estimate and ceiling are not ceremony; they are the difference between a calibration run and a surprise bill.

</specifics>

<deferred>
## Deferred Ideas

- Forge Curator proposal-review flow (ACUR-04) and the full 80-chapter batch (ACUR-05) — Phase 5.
- Per-roll `curated_by` granularity — only if a chapter ever legitimately mixes provenance (Phase 3 D-02).
- TUI dies on a validation error mid-session — tracked as a follow-up task; pre-existing, not this phase's.
- Confidence/error dashboard (CUR2-01) and automated re-curation on epub revision (CUR2-02) — v2.
- The 10 stub chapters' real curation — Dre's, excluded from calibration pools.

</deferred>

---

*Phase: 4-Inference Refinement, Confidence Gate & Routing*
*Context gathered: 2026-08-02*
