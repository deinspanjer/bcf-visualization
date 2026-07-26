# Phase 1: Epub Refresh & Exemplar Mining - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

The pipeline reflects the newest released chapters, and the hand-curated corpus is characterized well enough to teach an agent. Delivers: (1) epub refreshed via the existing private-source flow with chapter count and nav entries matching the newest release; (2) a full pipeline re-run green — predicted rolls extend into new chapters, all previously curated chapters still validate, `visualization_facts.json` rebuilds, and the pre-existing Track B staleness failures are cleared; (3) a regime-tagged exemplar index over the hand-curated corpus with same-regime retrieval; (4) documentation of the corpus's evidence-quote patterns, roll-shape distribution, and perk-link conventions.

HARD GATE for Phases 2–4. Pure analysis over existing data — **no LLM calls in this phase**. Must run in the main checkout (needs the gitignored epub, `data/private-source/` clone, and `.venv`).

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked — do not re-litigate)

- **From mobile-ux Phase 1 interview (Dre, 2026-07-25):** D-04 provenance shape — minimal `curated_by: "human" | "agent"` marker with a separate agent-run ledger — binds Phase 3, not this phase. The interview gate is one-time; nothing in this phase re-opens it.
- **Workstream Gate 1:** this phase is a hard gate; no verifier/schema/agent work starts until it is green.
- **Project rules:** no parallel implementations of domain quantities; only `chapter_facts.json:cp_earning_word_count` is valid for CP math; story prose stays local — no new prose in committed artifacts beyond the established evidence-quote convention; hand-curated data is authoritative.

### Regime tagging (auto-resolved 2026-07-26)

- **D-01:** A chapter's regime tag comes from the pipeline's existing computation — `chapter_facts.json:point_calculation_regime` — never recomputed by the exemplar-mining code. If the miner needs regime at finer granularity (per-roll), it reads whatever the existing simulation already emits; it must not re-derive regime from `regime_transitions.json` itself.
- **D-02:** Chapters containing a mid-chapter regime transition (e.g., ch 97 / Nano-Forge per `data/manual/regime_transitions.json`) are tagged with **both** regimes plus an explicit boundary flag. Retrieval for a target in either adjacent regime may return them, and the boundary flag is preserved in the index so Phase 3's regime-boundary sensitivity check (ACUR-02) can identify them without re-deriving.

### Exemplar index artifact (auto-resolved 2026-07-26)

- **D-03:** The index is a derived artifact (`data/derived/`) built by a new `scripts/` build script following the existing `build_*`/`derive_*` conventions, wired into `scripts/pipeline.py` and registered in the `data_release.py` manifest so staleness checking covers it — **Reversibility:** costly — un-registering a manifest-tracked artifact later touches the release/staleness machinery and any Phase 2/3 consumers keyed to it.
- **D-04:** Index entries reference source rolls by chapter + roll identity and may carry the already-committed evidence-quote text from `chapter_roll_overrides.json` (established convention). No text sourced from the epub prose itself goes into the committed index.

### Corpus characterization (auto-resolved 2026-07-26)

- **D-05:** Two outputs: machine-readable statistics inside the index artifact (roll-shape distribution incl. multi-grab frequency, evidence-quote patterns — count/length/position-policy distributions, `cp_ledger_checkpoint` usage, perk-link/naming conventions), plus a human-readable analysis report (markdown) for Phase 3 prompt design. The report may quote examples only via already-committed evidence quotes.

### Retrieval (auto-resolved 2026-07-26)

- **D-06:** Retrieval is a deterministic pure-Python function (same module family as the build script): given a target chapter, return only exemplars whose regime tags include the target's regime. No embeddings, no fuzzy similarity, no LLM. The within-regime ranking/selection heuristic (e.g., chapter proximity, roll-count similarity, quota `k`) is Claude's discretion, but it must be deterministic and covered by a test asserting the same-regime constraint (roadmap success criterion 3).

### Staleness clearance & refresh ordering (auto-resolved 2026-07-26)

- **D-07:** Order of operations: sync private source → hydrate epub → full pipeline re-run → regenerate derived artifacts and manifest → then diagnose whatever failures remain. Do not hand-patch stale sha256s or individual derived files before the regen; the refresh itself is expected to clear the `perk_directory` manifest staleness and most of the 24 data-consistency test failures documented in `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/deferred-items.md`.
- **D-08:** If any residual failure (notably the ch 95.5 multi_grab override referencing 'Minor Blessing Zeus – Lightning') traces to a hand-curated entry rather than stale derived data, the fix is **surfaced to Dre with a diagnosis, not silently applied** — hand-curated overrides are authoritative and agents/executors never edit them unprompted. Plan a human checkpoint for exactly this contingency.
- **D-09:** "Newest release" is verified mechanically: post-hydrate chapter count and nav entries compared against the private-source repo's current state, and predicted rolls demonstrably extend past the previous last chapter (~ch 96 per the deferred-items notes).

### Claude's Discretion

- Exact index schema field names and file name (within `data/derived/` + manifest conventions)
- Retrieval ranking heuristic within the same-regime constraint (deterministic, tested)
- Where the human-readable corpus report lives (phase dir vs `docs/`), and its structure
- Exact mechanism for the chapter-count/nav verification and how it is scripted
- Whether exemplar mining is one script or a build + query module pair

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workstream planning
- `.planning/workstreams/curation/ROADMAP.md` — Phase details, success criteria, Workstream Gates (epub hard gate; D-04 provenance shape already decided).
- `.planning/workstreams/curation/REQUIREMENTS.md` — EPUB-01, EPUB-02, CINF-02 definitions; out-of-scope table (no fuzzy matching, no new epub download path).
- `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md` — Interview decisions D-01..D-05; D-04 binds the curation workstream's provenance shape.
- `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/deferred-items.md` — The exact Track B staleness failures this phase must clear (stale `perk_directory` sha256; ch 95.5 multi_grab override; 24 data-consistency test failures, enumerated by test file).

### Milestone research
- `.planning/research/STACK.md` — Curation-pipeline technology decisions (two-tier quote verification, exact-or-reject bar, batch/caching guidance for later phases).
- `.planning/research/PITFALLS.md` — Regression modes, phase-mapped.
- `.planning/research/ARCHITECTURE.md` — Pipeline/render architecture analysis.

### Domain
- `plans/roll_sequence_validation.md` — Regime model and mid-chapter transition semantics (referenced by `regime_transitions.json`).
- `data/manual/regime_transitions.json` — Hand-curated mid-chapter regime transitions (currently ch 97 / Nano-Forge).
- `data/manual/chapter_roll_overrides.json` (`_purpose` header) — Authoritative roll-object schema the exemplar index mines: perks, outcome, constellation, word_position, mention_chapter_num, mention_word_position, display_position_policy, evidence_quotes (+ optional cp_ledger_checkpoint).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/sync_private_source_repo.py` → `scripts/hydrate_source_epub.py`: the ONLY sanctioned epub refresh path (REQUIREMENTS out-of-scope forbids a new download path).
- `scripts/pipeline.py`: existing DAG runner — the new exemplar-index build stage hooks in here.
- `scripts/data_release.py`: manifest/staleness machinery (`check-derived`, `manifest`) — the green/stale arbiter for EPUB-02 and the home for the new artifact's registration.
- `data/derived/chapter_facts.json`: `point_calculation_regime` per chapter (regime source of truth, D-01); `cp_earning_word_count` (only valid CP word count); `rolls` with per-chapter roll facts.
- `scripts/regime_simulator.py`, `scripts/predict_rolls.py`, `scripts/roll_scheduler.py`: existing regime-aware simulation — read-only context for what "predicted rolls extend into new chapters" means.
- `scripts/verify.py`: existing verification entry point that currently fails on the documented staleness — its going green is part of this phase's definition of done.
- `data/manual/chapter_roll_overrides.json`: the 118-chapter corpus being mined (keyed under `chapter_roll_overrides`, with `association_review` sibling key).

### Established Patterns
- Derived artifacts are produced by `build_*`/`derive_*` scripts in `scripts/`, land in `data/derived/`, and are manifest-tracked; the exemplar index follows this shape, not a one-off notebook/report.
- Curator vs. predictor `roll_number` sequences diverge — never join across them; exemplar mining keys rolls the way the overrides file does, not by predictor ordinals.
- Tests in `tests/` enforce data-consistency contracts; the 24 currently-failing Track B tests are the regression net proving EPUB-02.

### Integration Points
- `scripts/pipeline.py` DAG (new exemplar-index stage)
- `data_release.py` manifest (new artifact entry)
- Phase 2 verifier and Phase 3 agent prompts consume the index's retrieval function and characterization stats — its schema is a downstream contract.

</code_context>

<specifics>
## Specific Ideas

- The exemplar index exists to *teach an agent*: regime tagging must exist before retrieval logic is built (roadmap note), and the characterization stats should be written with Phase 3 prompt construction in mind.
- The phase is also a cleanup gate: `scripts/verify.py` and the full pytest suite going green (minus nothing) is the observable proof of EPUB-02.

</specifics>

<deferred>
## Deferred Ideas

- Confidence/error dashboard across curation runs — v2 (CUR2-01)
- Automated re-curation triggers when new epub versions revise old chapters — v2 (CUR2-02)
- Any LLM-assisted mining/summarization of the corpus — Phase 3 territory; this phase is deterministic analysis only

</deferred>

---

*Phase: 1-Epub Refresh & Exemplar Mining*
*Context gathered: 2026-07-26*
