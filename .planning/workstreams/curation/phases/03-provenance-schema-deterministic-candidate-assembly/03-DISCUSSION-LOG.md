# Phase 3: Provenance Schema & Deterministic Candidate Assembly - Discussion Log

> **Audit trail only.** Decisions live in CONTEXT.md.

**Date:** 2026-08-01
**Mode:** `--auto` (gray areas auto-resolved; grounded in CURATION-CONVENTIONS.md rather than generic defaults)
**Areas:** Phase scope/split, provenance rollout, Stage 1 output, expectation setting, measurement

## Phase scope — the split

| Option | Selected |
|---|---|
| Split at the Stage-1/Stage-2 seam; Stage 2 + confidence + routing + ledger → new Phase 4 | ✓ |
| Keep one phase covering 5 requirements and an unbounded calibration loop | |

Dre pre-approved the split guidance. Old Phase 4 renumbered to 5; requirement coverage and traceability updated.

## Provenance rollout

`curated_by` is required (not optional-with-default) so an agent entry cannot pass as hand-curated by omission; all 118 existing entries stamped `"human"`; chapter-entry level, matching the decided shape — per-roll granularity deferred to Phase 4 only if a chapter proves to mix sources.

## Stage 1 output

Candidates artifact under `data/derived/`, in the existing roll-object schema so Phase 4 routing and Phase 5 TUI review need no translation. Stage 1 never writes `chapter_roll_overrides.json`.

## Expectation setting

Measured evidence distribution over 718 predicted rolls: `forward_ref` 485 (68%), `direct` 132 (18%), `no_evidence` 74 (10%), `general_only` 27 (4%). Stage 1 is expected to perform on `direct` and usefully narrow the rest — explicitly NOT to be tuned toward the `forward_ref` majority, since loosening its binding rules would manufacture false candidates.

## Measurement

Per-evidence-class accuracy, not a headline number (a global figure would be dominated by `forward_ref`). Stub chapters excluded from the denominator — scoring against a generated stub measures agreement with a stub, not with Dre. Committed as a report, since Phase 4 reads it to size its own scope.

## Deferred

Stage 2 / confidence / routing / ledger → Phase 4. TUI review + batch → Phase 5. Stub-chapter curation → Dre. Per-roll provenance → only if proven necessary.
