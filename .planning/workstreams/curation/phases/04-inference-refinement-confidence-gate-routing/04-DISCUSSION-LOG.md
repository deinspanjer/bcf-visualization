# Phase 4: Inference Refinement, Confidence Gate & Routing - Discussion Log

> **Audit trail only.** Decisions live in CONTEXT.md.

**Date:** 2026-08-02
**Mode:** `--auto` (gray areas auto-resolved, grounded in measured data + STACK.md rather than generic defaults)
**Areas:** Input shape/cost, API mechanics, model boundary, confidence gate, idempotency, calibration & spend control

## Input shape — the dominant cost decision

Measured before deciding:

| Strategy | Tokens | Verdict |
|---|---|---|
| 250-word windows only | ~434k | insufficient — misses `forward_ref` by construction |
| Windows + bounded forward span | ~1.7M | ✓ selected |
| Whole chapters | ~3,531k | 8x cost, mostly irrelevant text |

`forward_ref` is 485 rolls (68%) and is Stage 2's main job, but its evidence sits outside the window by definition. `roll_text_evidence.json` already carries `next_specific_event_offset` for all 485, so the span is bounded rather than open-ended: median 969 words, p90 3,713, pathological max ~46k. Cap at ~p90 and MARK truncation, so a truncation-caused miss is distinguishable from a model-caused one.

## API mechanics

Batches API (50% cheaper, purpose-built for N independent requests; key by `custom_id`, never positional) + prompt caching on the shared prefix (conventions + schema + exemplars) + structured outputs. Per STACK.md. Calibrate on Opus-tier; step down to Sonnet only if held-out data shows it clears the same bar.

## Model boundary

Model proposes quote text and structure. It never emits positions or ordinals — those are derived mechanically by locating the proposed quote through Phase 2's verifier. A quote that can't be located is a failed proposal, not a position to invent. Verifier is the hard gate; self-reported confidence is a tiebreaker that can never promote something the verifier rejected.

## Confidence gate

Composite and code-computed: quotes pass verifier tiers + structure agrees with the mechanical bundle + perk names resolve. Self-report breaks ties only. Regime-boundary chapters must demonstrably route low more often — verified empirically, not asserted. Explicitly: a large proposals volume is a legitimate outcome; never relax verification to raise the high-confidence count.

## Calibration & spend

108 genuinely curated chapters (10 stubs excluded) split into calibration and held-out; tune on calibration, report on held-out. Report per evidence class against Phase 3's recorded Stage 1 baseline using the same position ladder — success criterion 1 is comparative. Dry-run token estimate + explicit ceiling before any batch; pilot first. `checkpoint:decision` before the first uncurated run, since uncurated output has no ground truth.

## Inference transport reversed mid-execution (2026-08-02, Dre)

Raised at Plan 04-01's Task 1 checkpoint — before `anthropic` was installed, before any code was written, nothing committed. Dre declined to pay per-token API costs and named three alternatives: orchestrator subagent, `claude` CLI, `codex` CLI.

Assessed: the orchestrator-subagent option was rejected as the wrong seam — Stage 2 must be callable from a batch runner, resumable via the ledger, and testable against a mock, and inference living in a conversation is none of those. A CLI subprocess fits the existing `call_stage2_sync(..., client=None)` seam almost unchanged, but gives up server-enforced structured output and would have meant free-text-then-parse, which CLAUDE.md forbids.

Dre then recalled an MCP server built to let Codex drive the Forge Curator TUI. Searched `scripts/`, `docs/`, `plans/`, `TODO.md`, git history, and a repo-wide scan for `model context protocol`/`fastmcp`/`mcp.server` — **it does not exist in this repo.** New construction, not configuration.

Selected anyway, because tool-call inputs are schema-validated by the protocol, which restores the D-08 guarantee at a different layer, adds a retry signal, and amortizes against the interactive-TUI use case the server was originally wanted for. Recorded as D-25 through D-29, with the propose-only tool surface (D-26) as the load-bearing constraint: the handler decides corpus vs proposals, never the model.

Struck: Batches API (D-06), prompt caching (D-07), the `anthropic` dependency, the dollar-cost estimator and `--ceiling-usd` cap (D-23). Survived with revision: structured-output intent (D-08→D-26), model tiering (D-09→D-28), spend checkpoints re-framed as run-size approvals (D-29). Unaffected: D-24.

Phase 4 is re-planned in full against these decisions rather than deviated in place — the spend-shaped design ran through four of the five plans.

## Deferred

TUI review + 80-chapter batch → Phase 5. Per-roll provenance → only if provenance ever mixes. TUI validation-error crash → tracked follow-up. Stub curation → Dre.
