# Phase 1: Epub Refresh & Exemplar Mining - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 1-Epub Refresh & Exemplar Mining
**Mode:** `--auto` (all gray areas auto-selected; recommended option chosen for every question, no interactive prompts)
**Areas discussed:** Regime tagging, Exemplar index artifact, Corpus characterization, Retrieval, Staleness clearance & refresh ordering

---

## Regime tagging

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `chapter_facts.json:point_calculation_regime` | Existing pipeline computation is the single regime source | ✓ |
| Re-derive from `regime_transitions.json` in the miner | Second implementation of regime logic | |

**Choice:** `[auto]` Reuse the existing pipeline value (no-parallel-implementations rule).

| Option | Description | Selected |
|--------|-------------|----------|
| Boundary chapters tagged with both regimes + flag | Ch 97-style mid-chapter transitions retrievable from either regime; flag feeds Phase 3 sensitivity check | ✓ |
| Single dominant regime per chapter | Simpler, but loses the boundary signal ACUR-02 needs | |

**Choice:** `[auto]` Both regimes + explicit boundary flag.

---

## Exemplar index artifact

| Option | Description | Selected |
|--------|-------------|----------|
| `data/derived/` artifact, pipeline stage, manifest-registered | Follows existing `build_*`/`derive_*` + `data_release.py` conventions; staleness-checked | ✓ |
| Standalone one-off analysis script/report | Faster, but outside staleness machinery and unversionable as a Phase 2/3 input | |

**Choice:** `[auto]` Pipeline-integrated derived artifact. Quotes in the index limited to already-committed evidence-quote text; no epub prose.

---

## Corpus characterization

| Option | Description | Selected |
|--------|-------------|----------|
| Stats in index + human-readable report | Machine stats for retrieval/gating; markdown report for Phase 3 prompt design | ✓ |
| Stats only | Satisfies retrieval but under-serves prompt construction | |

**Choice:** `[auto]` Both outputs.

---

## Retrieval

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic pure-Python same-regime filter | No embeddings/LLM; tested same-regime constraint | ✓ |
| Embedding/similarity-based retrieval | Violates "no LLM calls this phase"; nondeterministic | |

**Choice:** `[auto]` Deterministic filter; ranking heuristic left to Claude's discretion.

---

## Staleness clearance & refresh ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Refresh → full regen → then diagnose residuals | Refresh expected to clear manifest staleness + most of 24 test failures | ✓ |
| Patch failures first, refresh after | Hand-patching stale derived data wastes effort and masks root cause | |

**Choice:** `[auto]` Refresh first. Residual failures tracing to hand-curated entries (ch 95.5 multi_grab) are surfaced to Dre with diagnosis — never silently edited (curation authority). Human checkpoint planned for that contingency.

---

## Claude's Discretion

- Index schema field names and artifact file name
- Retrieval ranking heuristic (deterministic, same-regime, tested)
- Location/structure of the corpus report
- Chapter-count/nav verification mechanism
- One script vs. build + query module pair

## Deferred Ideas

- CUR2-01 confidence/error dashboard (v2)
- CUR2-02 automated re-curation on epub revisions (v2)
- LLM-assisted corpus mining — Phase 3 territory
