# Roadmap: Autonomous Curation (workstream: curation)

## Overview

This workstream refreshes the epub to the latest released chapters and then builds an agent-based curation pipeline that curates the remaining chapters, routing high-confidence output into the trusted overrides file with provenance and low-confidence output into a proposals sidecar for hand-curation. It is fully independent of the `mobile-ux` workstream (no shared files, no shared data) and may run in parallel with it.

Within this workstream, phases are strictly sequential — each stage's correctness bar depends on the previous stage's output being trustworthy.

> **Renumbering note:** These phases were Phases 5–8 of the original combined roadmap (before the workstream split on 2026-07-26). Old→new: 5→1, 6→2, 7→3, 8→4. Phase 3 was then split at the Stage-1/Stage-2 seam on 2026-08-01, making the old Phase 4 into Phase 5.

## Workstream Gates

1. **Epub hard gate (Phase 1).** Phase 1 is a HARD GATE for Phases 2–5. No curation infrastructure, verifier work, or agent run may begin until the epub is refreshed and the full pipeline re-runs green on it. Building a verifier or confidence gate against a stale chapter set means re-tuning everything after the refresh.
2. **Provenance shape is already decided — no interview needed.** Decided by Dre at the mobile-ux Phase 1 interview (2026-07-25, recorded as D-04 in `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md`): **minimal marker** — a single `curated_by: "human" | "agent"` string on each roll-override entry, following the existing `curator_added` precedent. Run bookkeeping (model, run_id, corpus_fingerprint, confidence) lives in a **separate agent-run ledger file keyed by chapter**; that ledger anchors CINF-04's idempotency fingerprint keying. All in-repo consumers of the overrides schema are rewritten for the new field in the same change (no shims). Reversibility: costly — widening to a rich per-roll object later means another full consumer rewrite.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 1: Epub Refresh & Exemplar Mining** - Latest chapters hydrated, pipeline green, regime-tagged exemplar index from the 118-chapter corpus (completed 2026-07-26)
- [x] **Phase 2: Mechanical Verifier** - Deterministic quote/word-position/perk-name verification baselined at 100% on hand-curated chapters (completed 2026-08-01)
- [ ] **Phase 3: Provenance Schema & Deterministic Candidate Assembly** - `curated_by` field rewrite, plus Stage 1: deterministic roll-candidate assembly from existing anchor/prose-window machinery, baselined against the hand-curated corpus. Zero LLM.
- [ ] **Phase 4: Inference Refinement, Confidence Gate & Routing** - Stage 2: inference pass that grades Stage 1 candidates and recovers what heuristics cannot; confidence gate, overrides/proposals routing, agent-run ledger idempotency
- [ ] **Phase 5: Proposal Review & Full Batch Run** - Forge Curator proposal review flow plus the full batch over remaining chapters

## Phase Details

### Phase 1: Epub Refresh & Exemplar Mining

**Goal**: The pipeline reflects the newest released chapters, and the hand-curated corpus is characterized well enough to teach an agent
**Mode:** mvp
**Depends on**: Nothing (workstream entry point)
**Requirements**: EPUB-01, EPUB-02, CINF-02
**Success Criteria** (what must be TRUE):

  1. The existing private-source flow (`sync_private_source_repo.py` → `hydrate_source_epub.py`) yields an epub whose chapter count and nav entries reflect the newest release
  2. A full pipeline re-run completes green: predicted rolls extend into the new chapters, all previously curated chapters still validate, and `visualization_facts.json` rebuilds
  3. An exemplar index built from the hand-curated chapters is tagged by CP regime, and a retrieval query for a target chapter returns only same-regime exemplars
  4. The index documents the corpus's observed evidence-quote patterns, roll-shape distribution, and perk-link conventions

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Verify epub freshness (D-09), resolve the ch 95.5 hand-curated data gap via a Dre-approved checkpoint, force-regenerate the full pipeline (EPUB-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Refresh the manifest, resolve any chapter-alignment drift, run the full `scripts/verify.py` green gate (EPUB-02)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Build the regime-tagged exemplar index + deterministic same-regime retrieval, wire into the pipeline/manifest (CINF-02)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — Author the human-readable corpus-analysis report, final phase-closing verification (CINF-02)

**Notes**: HARD GATE for Phases 2–5 — no verifier, schema, or agent work begins until this phase is green. Regime tagging must exist before retrieval logic is built, not be retrofitted. Exemplar mining is pure analysis over existing data; no LLM calls in this phase. This phase also clears the pre-existing Track B staleness failures documented in `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/deferred-items.md` (stale `perk_directory` sha256; ch 95.5 multi_grab override referencing an unobtained perk; 24 data-consistency test failures). This workstream MUST run in the main checkout — it needs the gitignored epub, `data/private-source/` clone, and `.venv`.

### Phase 2: Mechanical Verifier

**Goal**: Any candidate curation can be judged true or false by deterministic code, with the hand-curated corpus as its proof of correctness
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CINF-03
**Success Criteria** (what must be TRUE):

  1. Running the verifier over every hand-curated chapter passes 100% — a failure means the verifier is wrong, not the corpus
  2. The verifier accepts only exact or whitespace-normalized quote matches and rejects paraphrase; no fuzzy matching path exists
  3. Word positions and perk names are resolved through the pipeline's existing tokenizer and `perk_name_resolver.py` ladder, with no second implementation of either
  4. The verifier reports per-roll pass/fail with reasons, in a form the Phase 3 confidence gate can consume

**Plans**: 2/2 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Extract the CP-earning-word tokenizer (D-01/D-02) and build `verify_roll()`'s core (quote/position/perk/enum checks), tracer-proven against two real hand-curated rolls including paid/free perk resolution (D-06c, CINF-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-03-PLAN.md — `verify_chapter()` + CLI report writer, and the D-10 corpus-wide 100% baseline test (CINF-03)

**Notes**: Built and validated with zero LLM in the loop, so agent output has a real bar to clear on its first run. This is the "never let the model compute a value that has a deterministic source of truth" rule made executable.

### Phase 3: Provenance Schema & Deterministic Candidate Assembly

**Goal**: Every override entry declares who curated it, and a deterministic pass proposes candidate curations from prose the pipeline already indexes — measured against the hand-curated corpus before any inference is bought
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: CINF-01, ACUR-01

> ACUR-01 is delivered across two phases: its Stage 1 (deterministic assembly) half here, its Stage 2 (inference) half in Phase 4.

> **Split applied 2026-08-01 (Dre pre-approved the split guidance).** This was one phase covering both stages plus confidence/routing/idempotency — five requirements and an unbounded calibration loop. Stage 2 and everything that depends on it now live in Phase 4. The stage boundary is the natural seam: Stage 1 is independently valuable, independently verifiable with zero LLM cost, and its measured accuracy is the evidence that decides how much inference is worth buying.

**Two-pass architecture (Dre, 2026-08-01).** Curation is two sequenced stages, not one LLM extraction step. Stage 1 (this phase) is deterministic and reuses machinery that already exists; Stage 2 (Phase 4) applies inference *on top of* Stage 1's output rather than starting from raw prose.

- **Stage 1 — deterministic candidate assembly (zero LLM).** Consumes `data/derived/roll_text_evidence.json` (per predicted roll: prose window, matched regex anchors, and an evidence grade of `direct`/`general_only`/`forward_ref`/`no_evidence`) produced by the existing `find_roll_locations.py` → `find_text_backed_rolls.py` Stage-1 chain, plus the `obtained_perks.json` bundle structure (paid perk first, then its cost-0 ride-alongs). Assembles candidate roll objects: bind the constellation named at the head of a connection passage, bind the paid perk that follows, group the bundle, and search the chapter forward for each free perk's name or substring — attaching the first mention as an additional quote, per the observed curation convention (see Phase 2 `02-CONTEXT.md` D-12).
**Search posture** (`02-CONTEXT.md` D-13): Stage 1 is deliberately liberal — over-produce candidates, tolerate false positives, match name variants and substrings. Phase 2's verifier is the opposite tier — exact-or-reject with no fuzzy path in existence. Never conflate the two tunings.

**Success Criteria** (what must be TRUE):

  1. Every roll-override entry carries the `curated_by` provenance marker per the decided shape (Workstream Gate 2), and every in-repo consumer (`derive_roll_facts`, Forge Curator TUI, validators) is rewritten for it in the same change — no shims, aliases, or deprecation paths
  2. Stage 1 produces candidate roll objects from `roll_text_evidence.json` + `obtained_perks.json` with **no LLM in the loop**, and reuses the existing anchor/prose-window machinery rather than reimplementing prose scanning — a second regex-anchor or prose-window implementation is a phase failure
  3. Stage 1's accuracy against the hand-curated corpus is measured and recorded per evidence class (`direct` / `forward_ref` / `general_only` / `no_evidence`) — that measurement is the gate that sizes Phase 4's inference spend
  4. Word positions and roll ordinals are derived mechanically; Stage 1 emits candidates only and never writes to `chapter_roll_overrides.json`
  5. A candidate Stage 1 cannot support with evidence is emitted as evidence-not-found rather than guessed (`CURATION-CONVENTIONS.md` §5) — partial evidence is a correct outcome, not a failure

**Plans**: 3 plans

Plans:
**Wave 1**

- [ ] 03-01-PLAN.md — Consolidate the four independent overrides loaders into one schema-validating loader; stamp all 118 entries `curated_by: "human"` (CINF-01, D-11)
- [ ] 03-02-PLAN.md — Stage 1 deterministic candidate assembler: bind constellation/paid perk/bundle/free-perk evidence from `roll_text_evidence.json` + `obtained_perks.json` (ACUR-01 Stage 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 03-03-PLAN.md — Measure Stage 1 candidate accuracy against the hand-curated corpus, per evidence class; commit the report (ACUR-01 Stage 1 measurement)

**Notes**: The provenance field shape is already settled (Workstream Gate 2); no interview needed. Curator vs. predictor roll numbering diverge — respect the existing predicted-mode mapping rather than inventing one. Measured 2026-08-01 over 718 predicted rolls: `forward_ref` 485 (68%), `direct` 132 (18%), `no_evidence` 74 (10%), `general_only` 27 (4%) — so Stage 1 should be expected to do well on a minority of rolls, and that distribution is exactly why the Phase 4 split exists.

### Phase 4: Inference Refinement, Confidence Gate & Routing

**Goal**: An inference pass grades Stage 1's candidates and recovers what heuristics cannot, and output is routed by confidence into the trusted corpus or a proposals queue — never silently degrading either
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: CINF-04, ACUR-01, ACUR-02, ACUR-03

> ACUR-01's Stage 2 (inference) half lands here; its Stage 1 half was delivered in Phase 3.

**Stage 2 — inference refinement and grading.** Grades Stage 1's candidates into a confidence signal and teases out what deterministic heuristics cannot reach — principally the `forward_ref` (68% of rolls) and `no_evidence` classes, retrospective phrasing, and misses whose constellation is named only obliquely. Operates on Stage 1 output, never on raw prose from scratch.

**Success Criteria** (what must be TRUE):

  1. Stage 2 consumes Stage 1 candidates and improves on them measurably against held-out hand-curated chapters, versus the Stage 3-recorded Stage 1 baseline
  2. Word positions and roll ordinals stay mechanically derived; Stage 2 may adjust structure and confidence but never invents a position
  3. High-confidence curations write into `chapter_roll_overrides.json` with provenance; low-confidence curations write to a proposals sidecar in the same roll-object schema
  4. Re-running a chapter with unchanged inputs produces no diff (fingerprint-keyed idempotency via the agent-run ledger), and an existing hand-curated entry is never overwritten
  5. The confidence gate uses Phase 2's mechanical verification as the hard signal with model self-report only as a tiebreaker, and demonstrably routes regime-boundary-adjacent chapters to low confidence more often

**Plans**: TBD
**Notes**: Research flags this phase as needing calibration, not just implementation — the confidence rubric is derived empirically from a pilot batch against known chapters, with a checkpoint before running on uncurated ones. This is the phase that first spends real API budget; Phase 3's measured baseline should inform how much.

### Phase 5: Proposal Review & Full Batch Run

**Goal**: The remaining chapters are curated, and everything the agent was unsure about is sitting in the TUI waiting for Dre
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: ACUR-04, ACUR-05
**Success Criteria** (what must be TRUE):

  1. The Forge Curator TUI lists agent proposals and supports reviewing, accepting, editing, and rejecting them using its existing keybind and interaction model
  2. Accepting a proposal produces a hand-curated entry that outranks agent provenance for that chapter
  3. A batch run over all remaining uncurated chapters completes and emits a per-chapter summary report of accepted / proposed / failed
  4. Pipeline validation is green after the batch, and the visualization renders agent-curated chapters correctly alongside hand-curated ones

**Plans**: TBD
**Notes**: Extends the existing ~7.5K-line TUI rather than building a second review surface. Depends on the finalized proposals-file schema from Phase 3.

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 (strictly sequential; Phase 1 is a hard gate).

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Epub Refresh & Exemplar Mining | 4/4 | Complete    | 2026-07-26 |
| 2. Mechanical Verifier | 2/2 | Complete    | 2026-08-01 |
| 3. Provenance Schema & Deterministic Candidate Assembly | 0/3 | Not started | - |
| 4. Inference Refinement, Confidence Gate & Routing | 0/TBD | Not started | - |
| 5. Proposal Review & Full Batch Run | 0/TBD | Not started | - |

## Requirement Coverage

11 of 11 v1 requirements mapped, each to exactly one phase.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 | EPUB-01, EPUB-02, CINF-02 | 3 |
| 2 | CINF-03 | 1 |
| 3 | CINF-01, ACUR-01 (Stage 1) | 2 |
| 4 | CINF-04, ACUR-01 (Stage 2), ACUR-02, ACUR-03 | 4 |
| 5 | ACUR-04, ACUR-05 | 2 |
| **Total** | | **11** |

---
*Roadmap created: 2026-07-25 (as Phases 5–8 of the combined roadmap); split into the curation workstream 2026-07-26*
