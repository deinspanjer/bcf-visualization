# Phase 2: Mechanical Verifier - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Any candidate curation can be judged true or false by deterministic code, with the hand-curated corpus as its proof of correctness. Delivers: a verifier that (1) accepts only exact or whitespace/punctuation-normalized evidence-quote matches and rejects paraphrase with no fuzzy path in existence, (2) resolves word positions and perk names through the pipeline's existing tokenizer and `perk_name_resolver.py` ladder with no second implementation, (3) reports per-roll pass/fail with machine-readable reasons in a shape Phase 3's confidence gate consumes, and (4) scores 100% over every hand-curated chapter — where a failure means the verifier is wrong, never that the corpus should change.

**Zero LLM in the loop.** This phase is built and validated before any model output exists, so agent output has a real bar to clear on its first run.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked — do not re-litigate)

- **Phase 1 D-01 / project rule:** domain quantities come from the existing pipeline computation; never a second implementation. This phase's success criterion 3 restates it as a hard requirement.
- **Exact-or-reject:** fuzzy/similarity-scored quote acceptance (`difflib`, `rapidfuzz`, edit-distance thresholds) is forbidden outright — not merely unused. Per REQUIREMENTS.md's Out of Scope table and STACK.md.
- **Curation authority:** hand-curated data is authoritative. See D-06 below for the consequence when the verifier disagrees with the corpus.
- **Word-count discipline:** only `chapter_facts.json:cp_earning_word_count` is valid for CP math; the tokenizer this phase reuses is the CP-earning-word tokenizer, not a generic word splitter.
- **WoG convention (Dre, 2026-07-26, `WOG-NOTES.md`):** author word-of-god can back a roll with **no `evidence_quotes` at all**. Ch 121.1's two missed rolls (Capstone 200, Knowledge 400) are the first instance. This directly drives D-03.

### Tokenizer & prose access (auto-resolved 2026-07-26)

- **D-01:** Extract the CP-earning-word tokenizer into a shared, importable module and rewrite `scripts/find_text_backed_rolls.py` to consume it — do NOT import its private functions from another script, and do NOT reimplement. The functions to move are `_chapter_word_index`, `_split_sections`, and `_strip_to_spaces` (`scripts/find_text_backed_rolls.py:80` and neighbours), plus the epub/chapter-HTML loading path. Per the project's no-shims policy this is a full rewrite of every consumer in the same change, not an aliased re-export — **Reversibility:** costly — undoing means re-inlining the tokenizer into every consumer that came to depend on the shared module.
- **D-02:** The extracted module reads the epub through `scripts/data_paths.py` (`RAW`/`DATA`, honoring `BCF_DATA_DIR`), NOT the hardcoded `ROOT / "data" / "raw"` currently in `find_text_backed_rolls.py:59`. That hardcoding is a latent bug — it makes the tokenizer untestable against a scratch data dir, and Phase 1 proved `BCF_DATA_DIR` redirection is how this codebase does isolated verification. Fixing it is in scope because the extraction touches that line anyway.

### Quote verification (auto-resolved 2026-07-26)

- **D-03 (normalization boundary):** Two tiers, both substring-exact after normalization; there is no third tier.
  - **Tier 1:** byte-exact substring of the chapter's prose.
  - **Tier 2:** normalize BOTH the quote and the prose, then exact substring. Normalization is limited to: Unicode confusable folding for dashes (`–` `—` vs `-`), quotes (curly vs straight), and ellipsis (`…` vs `...`); collapsing internal whitespace runs to a single space; stripping leading/trailing whitespace; case-insensitive comparison.
  - **Rejected outright:** anything requiring a word to be added, removed, substituted, or reordered. A candidate that only matches after word-level edits is a `fail`, never a "close enough".
  - Rationale for the confusable set specifically: the corpus demonstrably contains both forms — `scripts/realign_chapters.py` re-escapes `–`/`…` on every run (Phase 1 deferred item), so a byte-exact-only verifier would produce false failures on hand-curated data.
- **D-04 (position semantics):** A quote's claimed position (`mention_chapter_num` + `mention_word_position`) is verified as *consistent with* where the normalized match actually occurs, within a tolerance window rather than as an exact index. Exact-index equality is the wrong bar — positions in the corpus point at the roll's display anchor, not necessarily the quote's first word. The tolerance value is Claude's discretion, but it must be a named constant with a documented rationale, and a match found in a *different chapter* than claimed is always a `fail`.

### Empty evidence (auto-resolved 2026-07-26)

- **D-05:** A roll with zero `evidence_quotes` is **not a failure**, but it is **not a pass either** — it reports as a distinct third outcome (e.g. `no_evidence`). This resolves the tension the WoG convention creates: hand-curated quote-less rolls (ch 121.1) must not break the 100% corpus baseline, while an agent must never be able to trivially pass by emitting no quotes. Phase 3's confidence gate treats `no_evidence` as never-high-confidence for agent output; for hand-curated entries it is simply informational. The verifier reports counts of each outcome so the distinction is visible, never collapsed into a boolean.

### Verifier scope (auto-resolved 2026-07-26)

- **D-06:** Per roll, the verifier checks exactly: (a) every evidence quote against prose per D-03/D-04; (b) `word_position` resolves through the shared tokenizer and falls within the chapter's CP-earning word range; (c) every perk name resolves through the `perk_name_resolver.py` ladder (`load_perk_aliases` → `build_alias_lookup` → `resolve_canonical`, with `DirectoryMatchIndex` for directory matching); (d) enum/structural sanity — `outcome` in `hit|miss`, `display_position_policy` in the documented set (`mention`, `mechanical`, `section_start`, `source_marker`, `section_end`).
- **D-07 (explicitly OUT of scope):** roll-scheduling and slot-capacity validation. That is `roll_scheduler.py` / `multi_grab.py` territory and is exactly where chapter 104 currently fails (2 curated hits vs 1 predicted slot, Phase 1 deferred item). Including it would make the 100% baseline unreachable for reasons that have nothing to do with quote/position/name verification. The verifier answers "is this curation internally truthful about the prose?", not "does it fit the roll schedule?".
- **D-08 (the anti-corruption rule):** If the verifier fails a hand-curated chapter, the response is to fix the verifier — **never** to edit `data/manual/chapter_roll_overrides.json` to make it pass. ROADMAP success criterion 1 states this outright ("a failure means the verifier is wrong, not the corpus"). Any hand-curated chapter that appears genuinely wrong is a checkpoint for Dre, not an autonomous edit.

### Output & baseline (auto-resolved 2026-07-26)

- **D-09:** Ship both an importable Python API (the structured per-roll result Phase 3 imports directly) and a CLI that writes a human/CI-readable JSON report. The API is the contract; the report is a convenience. **Not** wired into `scripts/pipeline.py` and **not** manifest-registered — this is a QA instrument, not a pipeline input, and coupling it to the DAG would drag verification into every data regen. This deliberately differs from Phase 1's exemplar-index decision (D-03 there), because that artifact *is* a downstream input and this one is not.
- **D-10:** The 100% baseline is enforced by a pytest test that runs the verifier over the entire hand-curated corpus and asserts zero `fail` outcomes (`no_evidence` permitted per D-05). The test must skip with an explicit reason when the gitignored epub is absent, so the suite stays runnable without private source — but the phase gate requires a run with the epub present, and the recorded baseline numbers (pass / no_evidence / fail counts) go in the SUMMARY.

### Perk-name gap resolution (Dre, 2026-07-26, post-research)

- **D-11:** Research measured that only ~80.8% of the corpus's 120 perk-name mentions resolve through the ladder from a roll object alone (88.3% when `jump` is cross-referenced via `obtained_perks.json`, which stops at ch 119.5 and so will not cover Phase 3's target chapters). **14 names never resolve** — genuine gaps in `data/manual/perk_aliases.json` / the perk directory, concentrated in chapter 92's Transformers sub-instances.

  **Dre's decision: fix the data first.** The missing perks/aliases are added BEFORE the verifier's baseline is established, so success criterion 1's "100%" is literally true rather than allowlisted around. Consequences the planner must honor:
  - This is a **hand-curated data edit** (`data/manual/perk_aliases.json` is hand-curated) — therefore **curation authority applies**: Dre approves the additions, an executor never writes them autonomously. Structure this as a `checkpoint:decision` task (or a small batch of them) presenting each unresolved name with its evidence, ahead of any verifier-baseline task.
  - The data fix is a **prerequisite wave**, not a cleanup afterthought — the verifier's corpus baseline test (D-10) is meaningless until it lands.
  - If, after the fix, any name still fails to resolve, that is a checkpoint for Dre — **not** grounds to weaken the check or to edit `chapter_roll_overrides.json` (D-08 still governs).
  - Derived artifacts affected by an alias change (e.g. the perk directory) are regenerated through the existing pipeline, never hand-edited.
  — **Reversibility:** reversible — alias additions are additive data rows, removable without touching consumers.

### Claude's Discretion

- Name and location of the extracted tokenizer module, and of the verifier module/CLI
- The D-04 position-tolerance constant and its rationale
- Exact shape of the per-roll result object (as long as it carries pass/fail/no_evidence plus a machine-readable reason code, per success criterion 4)
- Whether the confusable-folding table is hand-written or `unicodedata`-based, provided the D-03 boundary is preserved exactly
- Test structure and fixture strategy

### Known-accepted baseline (do NOT chase)

Full pytest currently has 5 pre-existing failures — 4 in `tests/test_forge_curator.py`, 1 in `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction` — and `scripts/verify.py` exits 1 for that reason. These predate Phase 1 and are documented in the Phase 1 `deferred-items.md`. Judge this phase's work by "no NEW failures", not absolute green.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Workstream planning
- `.planning/workstreams/curation/ROADMAP.md` — Phase 2 goal, the four success criteria, and the note that this is built with zero LLM in the loop.
- `.planning/workstreams/curation/REQUIREMENTS.md` — CINF-03; the Out of Scope table forbidding fuzzy/similarity-scored quote acceptance.
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/01-CONTEXT.md` — Phase 1 locked decisions D-01..D-10 (regime sourcing, no-parallel-implementations precedent, exact-or-reject).
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/deferred-items.md` — ch 104's stale anchor (why D-07 excludes capacity checks), the 5 known-accepted test failures, the `realign_chapters.py` `ensure_ascii` churn (why D-03 needs confusable folding).
- `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` — what a well-formed hand-curated chapter looks like: roll-shape distribution (57.6% of hits are multi-grab), evidence-quote patterns, `display_position_policy` distribution, perk-link conventions. The verifier's expectations must match this observed reality.
- `.planning/workstreams/curation/WOG-NOTES.md` — the quote-less-roll convention that drives D-05.

### Milestone research
- `.planning/research/STACK.md` — the two-tier quote-verification pattern and the exact-or-reject rationale; the "What NOT to Use" table naming fuzzy matching as disqualifying.
- `.planning/research/PITFALLS.md` — regression modes, phase-mapped.

### Code (primary sources — read before designing)
- `scripts/find_text_backed_rolls.py` — `_chapter_word_index` (:80), `_split_sections`, `_strip_to_spaces`, and the hardcoded `EPUB` path (:59). Source of the tokenizer being extracted per D-01/D-02.
- `scripts/perk_name_resolver.py` — the resolution ladder: `load_perk_aliases` (:163), `build_alias_lookup` (:177), `resolve_canonical` (:192), `DirectoryMatchIndex` (:200), `build_directory_match_index` (:379).
- `scripts/data_paths.py` — `DATA`/`RAW`/`DERIVED`/`MANUAL` with `BCF_DATA_DIR` override (the isolation mechanism Phase 1 used for read-only experiments).
- `scripts/_common.py` — `write_validated_json` + the `data/derived/_schemas/*.schema.json` convention, if any verifier output gets a registered schema.
- `data/manual/chapter_roll_overrides.json` (`_purpose` header) — authoritative roll-object schema being verified, including that `cp_ledger_checkpoint` nests inside `evidence_quotes` (Phase 1 finding, not a roll-level field).
- `scripts/derive_roll_facts.py:690` — the current extent of quote validation (non-empty check only), confirming Tier-1/Tier-2 matching is new code rather than a duplicated path.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/perk_name_resolver.py`: clean public ladder — reuse directly, no wrapper, no reimplementation (success criterion 3).
- `scripts/find_text_backed_rolls.py` tokenizer trio: the CP-earning-word index, currently private and script-bound; extraction target per D-01.
- `scripts/data_paths.py`: `BCF_DATA_DIR` redirection — the sanctioned way to run against isolated data, proven in Phase 1's read-only drift experiment.
- `scripts/_common.py:write_validated_json`: schema-validated JSON writing, if the report artifact warrants a registered schema.
- `data/derived/exemplar_index.json` + `scripts/query_exemplars.py` (Phase 1): the corpus statistics the verifier's expectations should agree with; also the precedent for a pure-Python deterministic module with tests.

### Established Patterns
- `build_*`/`derive_*` scripts: argparse + pure-function core + `SCHEMA_VERSION` + stdout summary / stderr warnings; hard `raise` on shape violations. The verifier CLI should read like these even though it is not pipeline-wired.
- Tests import pure functions directly (`from scripts.<module> import <fn>`) rather than shelling out — see `tests/test_build_exemplar_index.py`, `tests/test_chapter_roll_overrides.py`.
- Gitignored inputs (epub, `data/derived/*`) mean corpus-wide tests must degrade gracefully when private source is absent (D-10).

### Integration Points
- Phase 3's confidence gate imports the verifier's Python API — the per-roll result shape is a downstream contract, so name reason codes deliberately.
- `find_text_backed_rolls.py` is rewritten (not shimmed) to consume the extracted tokenizer; it is the only current consumer, which keeps D-01's blast radius small.

</code_context>

<specifics>
## Specific Ideas

- The verifier is the phase that makes Phase 3 safe: it exists so agent output has a real bar to clear on its first run, before any model output is trusted anywhere.
- Success criterion 1 inverts the usual failure logic — the corpus is the fixture and the verifier is the code under test. D-08 encodes that inversion as a prohibition so it cannot erode under pressure to "get to green".
- D-05's three-outcome model (`pass` / `fail` / `no_evidence`) is the load-bearing design choice: it is what lets the WoG convention and the exact-or-reject trust bar coexist.

</specifics>

<deferred>
## Deferred Ideas

- Roll-scheduling / slot-capacity verification (ch 104's failure mode) — belongs to the existing `roll_scheduler.py`/`multi_grab.py` validation path, not this verifier (D-07).
- Confidence scoring and the routing of high/low-confidence output — Phase 3 (ACUR-02, ACUR-03); this phase only supplies the mechanical signal it consumes.
- Any LLM-assisted or similarity-based verification — permanently out of scope, not merely deferred (REQUIREMENTS.md Out of Scope).
- Fixing the 5 known-accepted pre-existing test failures and ch 104's anchor — tracked in Phase 1's `deferred-items.md`.

</deferred>

---

*Phase: 2-Mechanical Verifier*
*Context gathered: 2026-07-26*
