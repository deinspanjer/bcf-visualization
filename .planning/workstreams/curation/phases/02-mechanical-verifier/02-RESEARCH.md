# Phase 2: Mechanical Verifier - Research

**Researched:** 2026-07-26
**Domain:** Deterministic validation of hand-curated/agent-curated roll data against source prose and existing pipeline primitives (pure Python, no LLM, no external services)
**Confidence:** HIGH (all load-bearing numbers below were measured directly against the real, locally-present epub and the real `data/manual/chapter_roll_overrides.json` in this session — not assumed)

## Summary

This phase has almost no external-library research surface — it is 100% internal-codebase archaeology plus empirical measurement against the actual 118-chapter corpus and the actual (gitignored, but locally present) epub. All ten locked decisions (D-01..D-10) name specific functions/files to reuse; the job of this research was to (a) verify those functions' true dependency graph before the planner assumes a small blast radius, and (b) empirically test whether the 100%-baseline success criterion is actually reachable given the exact-or-reject quote rule and the perk-name-resolver ladder, rather than assuming it.

Two findings materially change the plan's risk profile. First, `_split_sections`/`_strip_to_spaces` are **not** private to `find_text_backed_rolls.py` as CONTEXT.md's line reference implies — they are imported from `scripts/find_roll_locations.py`, whose own docstring admits it duplicates `scripts/extract_chapter_sections.py`'s implementation verbatim. This is a pre-existing, undocumented parallel-implementation (predates this phase) that D-01's extraction will touch whether or not the planner intends to fully resolve it. Second, the quote/position half of the verifier (D-03/D-04) empirically clears the 100% bar with wide margin — but the perk-name-resolution half (D-06c) does **not**: without a `jump` value, only 80.8% of curated perk-name strings resolve through the ladder; even after cross-referencing the one available jump source, 11.7% remain permanently unresolved due to real gaps in `perk_directory.json`/`perk_aliases.json`. This is the single highest-risk item for planning and is very likely to require a documented exception (mirroring the ch104 precedent) rather than code work, or a scope clarification of what D-06(c) means by "resolves."

**Primary recommendation:** Build the quote/position verifier exactly as D-03/D-04 specify (it works, is well within tolerance everywhere in the corpus); before writing a single line of the perk-name check, run the measurement in this document's `## Perk Resolution Reality Check` section as a Wave-0 spike, and get an explicit decision from the planner/Dre on how the 14 unresolvable perks are handled — do not let this surface for the first time during phase-gate execution.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CP-earning word tokenization (epub HTML -> char-offset word index) | Data/Pipeline (offline Python) | — | Pure derivation over local files; no runtime service involved |
| Evidence-quote text verification (Tier 1/2 substring match) | Data/Pipeline (offline Python) | — | New deterministic code, consumes prose + overrides, no I/O beyond local files |
| Perk-name resolution (ladder) | Data/Pipeline (offline Python) | — | Already-existing shared module (`perk_name_resolver.py`); verifier is a new consumer, not a new tier |
| Per-roll structural sanity (enums) | Data/Pipeline (offline Python) | — | Pure validation against the override schema's own documented enum sets |
| Verifier report (JSON + Python API) | Data/Pipeline (offline Python) | — | Explicitly NOT pipeline-wired (D-09) — a QA instrument invoked out-of-band, never a `web/` or server-side concern |

There is no browser/frontend/API tier involvement anywhere in this phase — it is a pure offline Python validation layer, consistent with D-09's explicit exclusion from `scripts/pipeline.py` and the runtime manifest.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CINF-03 | Mechanical verifier validates agent output using existing primitives only (exact/whitespace-normalized quote match, pipeline tokenizer word positions, perk-name resolver ladder) and is baselined against known-good hand-curated chapters before any LLM output touches it | Tokenizer dependency graph mapped (`## Tokenizer Extraction Blast Radius`); quote-match empirically verified reachable at 100% (`## Quote Verification Reality Check`); perk-ladder resolution empirically measured and found to fall short of 100% without a scope decision (`## Perk Resolution Reality Check`) — flagged as the phase's central planning risk |
</phase_requirements>

## Standard Stack

This phase introduces **zero new external packages**. Everything needed is already a project dependency or Python stdlib.

### Core (all already present in this repo)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `re`, `zipfile`, `unicodedata`, `bisect` | 3.14 (repo's `.venv`) | HTML tag stripping, epub reading, confusable folding, nearest-occurrence position search | No dependency needed for any of D-03/D-04's requirements — confirmed by prototyping the full Tier-1/Tier-2/position-tolerance check with stdlib only in this research session |
| `jsonschema` (Draft202012Validator) | already vendored via `scripts/_common.py` | Optional schema validation of the verifier's JSON report, if the planner chooses to register one | Already a hard dependency of every `build_*`/`derive_*` script in this repo — no new install |
| `pytest` | already the test runner (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) | D-10's corpus-wide baseline test | Existing convention; no new runner |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scripts/perk_name_resolver.py` (existing, in-repo) | n/a | Perk-name ladder: `load_perk_aliases`, `build_alias_lookup`, `resolve_canonical`, `DirectoryMatchIndex`, `build_directory_match_index` | Always — D-06(c) forbids a second implementation |
| `scripts/data_paths.py` (existing, in-repo) | n/a | `RAW`/`DATA`/`DERIVED`/`MANUAL` with `BCF_DATA_DIR` override | The extracted tokenizer module's epub/JSON reads (D-02) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Exact/two-tier substring match | `difflib.SequenceMatcher`, `rapidfuzz` | Forbidden outright by REQUIREMENTS.md Out of Scope and D-03 — not evaluated further |
| Hand-written confusable table | `unicodedata.normalize("NFKD", ...)` | `unicodedata` NFKD does **not** fold en-dash/em-dash to hyphen or curly quotes to straight quotes (these are compatibility-unrelated distinct code points) — a hand-written table (as prototyped in this research) is required either way; `unicodedata` only helps for combining-character equivalences the corpus doesn't exhibit. Recommend the hand-written table. |

**Installation:** None required — no `pip install` line needed for this phase.

**Version verification:** N/A — no new packages.

## Package Legitimacy Audit

**Not applicable.** This phase installs zero external packages (see Standard Stack above — everything is stdlib or an existing in-repo module/dependency). No `npm view` / `pip index versions` / legitimacy-check invocation was needed or performed.

## Tokenizer Extraction Blast Radius (D-01/D-02) — the finding that changes scope

**This is the most important correction to CONTEXT.md's stated assumption.** CONTEXT.md says the functions to move are "`_chapter_word_index`, `_split_sections`, and `_strip_to_spaces` (`scripts/find_text_backed_rolls.py:80` and neighbours)" and that `find_text_backed_rolls.py` is "the only current consumer." Direct inspection shows this is only half true:

- `_chapter_word_index` **is** genuinely defined and private to `find_text_backed_rolls.py:80` — this part of the CONTEXT statement is accurate.
- `_split_sections` and `_strip_to_spaces` are **not** defined in `find_text_backed_rolls.py` at all. They are imported at `find_text_backed_rolls.py:54-56`:
  ```python
  from find_roll_locations import (
      _split_sections, _strip_to_spaces, _to_plain,
  )
  ```
- `scripts/find_roll_locations.py` defines its own `_split_sections` (:305) and `_strip_to_spaces` (:81). Its docstring for `_split_sections` says, verbatim: *"identical to `extract_chapter_sections._split_sections`."*
- `scripts/extract_chapter_sections.py` defines **its own, separately-maintained copy** of `_split_sections` (:461) with byte-for-byte identical logic (verified by direct diff of both function bodies in this session).

So there are already **two** independent, hand-synchronized copies of `_split_sections` in the repo (`find_roll_locations.py` and `extract_chapter_sections.py`) predating this phase entirely — a pre-existing parallel-implementation violation the project's own no-parallel-implementations rule would flag if discovered fresh today. Full consumer map (`grep -rn` across `scripts/` and `tests/`):

| Symbol | Defined in | Imported/duplicated by |
|--------|-----------|------------------------|
| `_split_sections` | `extract_chapter_sections.py:461` (own copy) | `tests/test_an_detector.py` (imports from `extract_chapter_sections`), `tests/test_extract_classify_predict_scenarios.py` (imports from `extract_chapter_sections`) |
| `_split_sections` | `find_roll_locations.py:305` (duplicate copy, docstring admits it) | `build_chapter_facts.py:51` (imports from `find_roll_locations`), `find_text_backed_rolls.py:55` (imports from `find_roll_locations`) |
| `_strip_to_spaces` | `find_roll_locations.py:81` | `find_text_backed_rolls.py:55` (imports from `find_roll_locations`) |
| `_chapter_word_index` | `find_text_backed_rolls.py:80` (genuinely private, single copy) | none currently — new consumer will be the verifier |
| `EPUB = ROOT / "data" / "raw" / ...` hardcoded path | `find_text_backed_rolls.py:59`, `find_roll_locations.py:62`, `extract_chapter_sections.py` (own `EPUB` constant) | All three scripts independently hardcode the same path, bypassing `data_paths.py` — D-02 only fixes this in the newly-extracted module, not in the two source files it doesn't touch |

**What this means for planning, without re-opening D-01/D-02:**
- D-01 literally says "rewrite `scripts/find_text_backed_rolls.py` to consume it" — the plan should honor that literal scope (only `find_text_backed_rolls.py` gets rewritten to import from the new shared module) rather than silently expanding to touch `find_roll_locations.py`/`extract_chapter_sections.py`/`build_chapter_facts.py`, which is a materially larger, riskier change with two other pipeline scripts and two more test files in its blast radius.
- However, the plan **must not** claim the extraction "consolidates the tokenizer" in its verification language — it consolidates the codepath `find_text_backed_rolls.py` was using, not the pre-existing `find_roll_locations.py`/`extract_chapter_sections.py` duplication, which remains exactly as duplicated as it was before this phase. This is worth one explicit sentence in the plan's scope statement so it isn't later mistaken for "already fixed."
- Recommend filing the `find_roll_locations.py` vs. `extract_chapter_sections.py` duplication as a **deferred item** (same pattern as Phase 1's `ensure_ascii` and DAG-ordering deferrals) rather than silently expanding this phase's scope or silently ignoring it.
- The verifier's own tokenizer needs (D-06b: "`word_position` resolves through the shared tokenizer") should import the **new** extracted module (whatever the planner names it, e.g. `scripts/cp_word_index.py`), not reach into `find_roll_locations.py` or `extract_chapter_sections.py` directly — this keeps the verifier's dependency graph confined to the one module D-01 creates.

## Architecture Patterns

### System Architecture Diagram

```
data/manual/chapter_roll_overrides.json ─┐
                                          │
data/derived/chapters.json (epub_href) ──┼──► [verify_chapter(chapter_num, override_entry)]
                                          │              │
data/raw/Brocktons_Celestial_Forge.epub ─┘              │
      (via zipfile, BCF_DATA_DIR-aware)                 │
                                                          ├─► Tier-1/Tier-2 quote match ──► per-quote {pass|fail}
data/manual/section_classifications.json ─► [cp_word_index module] (D-01/D-02, shared, imported not duplicated)
                                                          │
                                                          ├─► word_position range check ──► per-roll {pass|fail}
data/derived/perk_directory.json ─┐
data/manual/perk_aliases.json ────┼─► [perk_name_resolver ladder] ─► per-perk {resolved|unresolved}
                                   │        (existing, unmodified)
                                   └────────────────────────┘
                                                          │
                                                          ├─► enum/structural sanity (outcome, display_position_policy)
                                                          │
                                                          ▼
                                          per-roll result: {pass | fail | no_evidence, reason_codes[]}
                                                          │
                                        ┌─────────────────┴─────────────────┐
                                        ▼                                   ▼
                          Python API (importable;                CLI (`python -m ...` or
                          Phase 3 confidence gate                 script entrypoint) writes
                          imports this directly)                  JSON report to disk (D-09)
                                                          │
                                             pytest corpus-wide test (D-10):
                                             loop over all 118 hand-curated
                                             chapters, assert zero `fail`
                                             (skip whole module if EPUB absent)
```

### Recommended Project Structure
```
scripts/
├── cp_word_index.py          # NEW (D-01/D-02): extracted _chapter_word_index,
│                              # _split_sections, _strip_to_spaces (renamed/moved
│                              # from find_text_backed_rolls.py's private trio +
│                              # find_roll_locations.py's copies it imported),
│                              # epub-loading via data_paths.RAW/BCF_DATA_DIR
├── find_text_backed_rolls.py  # REWRITTEN to import from cp_word_index.py
├── mechanical_verifier.py     # NEW: pure verify_chapter()/verify_roll() functions
│                              # + thin __main__ CLI block (mirrors query_exemplars.py
│                              # pattern: "pure module... thin __main__ for manual
│                              # debugging only")
tests/
├── test_cp_word_index.py      # NEW: unit tests for the extracted tokenizer
├── test_mechanical_verifier.py # NEW: unit tests for quote/position/perk/enum checks
│                              # + the D-10 corpus-wide baseline test, skipped
│                              # when EPUB absent
```

### Pattern 1: Pure-function API + thin CLI wrapper (established precedent)
**What:** A module with zero argparse/file-I/O in its core function(s); a separate, small `__main__` block does file I/O and prints a summary.
**When to use:** Exactly this phase's D-09 requirement (importable API + CLI report).
**Example (existing precedent, `scripts/query_exemplars.py`):**
```python
"""Deterministic same-regime exemplar retrieval (D-06).

Pure module — no argparse, no file I/O in the retrieval path. Takes an
already-loaded exemplar_index.json dict and returns a filtered/ranked
subset. No embeddings, no fuzzy similarity, no LLM: retrieve() is a plain,
deterministic filter + sort over ``index["exemplars"]``.

Phase 3 imports ``retrieve()`` directly; the thin ``__main__`` block below
is for manual debugging only.
"""
def retrieve(target_regime: int, index: dict, *, k: int | None = None,
             target_chapter: str | None = None) -> list[dict]:
    ...
```
The verifier should follow this exact shape: `verify_chapter(chapter_num: str, override_entry: dict, *, prose_source, tokenizer, directory_index) -> ChapterVerification` as the pure core, with a CLI wrapper doing the epub/JSON loading and JSON-report writing.

### Pattern 2: Structured issue-record shape (established precedent)
**What:** `{"code": str, "severity": "error"|"warning", "message": str}` — the shape `derive_roll_facts.py::_manual_override_issues` already emits for model-validation problems.
**When to use:** For per-roll/per-quote reason codes (success criterion 4's "machine-readable reasons").
**Example (existing precedent, `scripts/derive_roll_facts.py:834-838`):**
```python
issues.append({
    "code": "curated_hit_missing_perks",
    "severity": "error",
    "message": f"Curated hit roll #{idx} does not name any perk.",
})
```
Recommend the verifier reuse this `{code, severity, message}` triple shape for its reason codes (e.g. `quote_not_found`, `position_out_of_tolerance`, `perk_unresolved`, `bad_outcome_enum`) rather than inventing a new shape — this is the one existing precedent for "structured reason for a roll-level problem" in this codebase.

### Anti-Patterns to Avoid
- **First-match substring search for quote position verification:** `text in chapter_prose` tells you the quote exists, but `.find()`/`in` returns the *first* occurrence — this research measured **36 of 833 exact-match quotes have the identical text appearing 2+ times in the same chapter** (short boilerplate miss-phrases like "The Time constellation passed by", which recur once per miss event using identical author phrasing). Verifying position against the first occurrence produces false "position mismatch" failures on 7 of those 36 (distances up to 30,453 words) that vanish entirely once the verifier picks the occurrence *nearest the claimed `mention_word_position`* instead. This is not an edge case to defer — it will misfire on real, currently-passing hand-curated chapters (39, 41, 46, 50, 52, 61, 66 in the current corpus) if implemented naively.
- **Treating `roll.word_position` and `evidence_quotes[].mention_word_position` as the same field:** They are not. `roll.word_position` is 0/681 populated in the current corpus (it is a pipeline-computed override field, not hand-curated) — the field the verifier actually checks quotes against is each quote's own `mention_word_position` (864/864 populated when the quote itself is populated). See `## Position Semantics (D-04) — measured` below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CP-earning word tokenization | A new HTML/word-splitter | The extracted `cp_word_index` module (D-01) — literally the same `_chapter_word_index`/`_split_sections`/`_strip_to_spaces` logic already proven against the corpus | Any independent reimplementation risks disagreeing with `predict_rolls.py`'s own word-counting (this exact bug class — computed-vs-manual `counts_for_cp` divergence — is called out in `find_text_backed_rolls.py`'s own "BUG FIX" comment at line 200) |
| Perk-name canonicalization | A second alias/matching table | `scripts/perk_name_resolver.py`'s `DirectoryMatchIndex`/`resolve_canonical` | D-06(c) is explicit; also, this research found the ladder already has known gaps (see below) — a second, looser implementation would silently paper over exactly the signal Phase 3's confidence gate needs to see |
| Quote fuzzy-matching | `difflib`/`rapidfuzz`/edit-distance | Nothing — exact substring, two normalization tiers, full stop | Forbidden outright (REQUIREMENTS.md, D-03); empirically unnecessary too — the measured corpus needs zero fuzzy tolerance (100% pass at Tier1+Tier2) |

**Key insight:** every "don't hand-roll" item in this phase already has a working, in-repo implementation — the actual risk is not "will someone reinvent this," it's "will the extraction silently widen beyond the two files D-01 names, or will the perk-ladder's real, measured gaps be discovered mid-execution instead of during planning."

## Common Pitfalls

### Pitfall 1: Assuming the perk-name ladder needs no `jump` context
**What goes wrong:** Calling `DirectoryMatchIndex.lookup(name, jump=None, constellation=...)` silently skips Steps 1-3 of the ladder (exact/alias-exact/normalized-(name,jump) matching all iterate over `jumps_to_try`, which stays an **empty list** when `jump` is falsy) and falls through to Step 4 (name-only, constellation-scoped fallback) only.
**Why it happens:** The override schema (`chapter_roll_overrides.json`) does not carry a `jump` field on roll objects at all — only `perks` (plain strings) and `constellation`. An implementer reading the schema alone has no obvious `jump` value to pass.
**How to avoid:** See `## Perk Resolution Reality Check` below — measure this explicitly before assuming either "it just works" or "it needs a jump lookup," because both the no-jump and with-jump numbers were empirically measured in this research and neither reaches 100%.
**Warning signs:** A verifier perk-check that "always passes" in a smoke test but was never run over the full 118-chapter corpus — the failure concentrates in specific chapters (79, 81, 82, 91, 92, 93, 95, 36 in this corpus) that a small smoke sample would likely miss.

### Pitfall 2: Position-tolerance checked via first-match rather than nearest-match
**What goes wrong:** See Anti-Pattern above — 7/833 quotes would false-fail with naive first-match search, at distances up to ~30,000 words, which would look like a catastrophic tolerance-constant miscalibration rather than the actual, narrow "pick the nearest occurrence" bug it is.
**Why it happens:** `str.find()`/`in` is the obvious first implementation; the corpus's genuine duplicate-phrase pattern (generic miss narration reused verbatim per event) is not visible without testing against the real corpus.
**How to avoid:** Implement nearest-occurrence-to-claimed-position search from the start (this research's `position_check2.py` approach: enumerate all occurrences via `re.finditer(re.escape(text), ...)`, map each to a word index via the tokenizer's char-offset list, take the minimum absolute distance to `mention_word_position`).
**Warning signs:** Any single quote failing with a distance in the thousands — that is a multi-occurrence-disambiguation bug, not evidence the corpus needs a bigger tolerance constant.

### Pitfall 3: Treating `realign_chapters.py`'s `ensure_ascii=True` output as a normalization signal
**What goes wrong:** Phase 1's deferred-items.md documents that `realign_chapters.py::_restamp()` writes with `ensure_ascii=True`, escaping en-dash/ellipsis into `\uXXXX` sequences on unrelated lines whenever it runs. If the verifier's confusable-folding table is built by reading a `\uXXXX`-escaped copy of the overrides file (e.g. from a stale git blob or an old commit), the escaped forms won't match the folding table's literal Unicode characters.
**Why it happens:** This is exactly what D-03's rationale section already documents as the reason the confusable set exists — restated here as a pitfall so the verifier's test fixtures don't accidentally load an ascii-escaped snapshot and think Tier 2 doesn't work.
**How to avoid:** Always load `chapter_roll_overrides.json` fresh via `json.loads()` (which un-escapes `\uXXXX` automatically) rather than treating any serialized-JSON-as-text form as the source of truth for what characters "really" appear.
**Warning signs:** A confusable-folding unit test that passes on a hand-written fixture but the corpus-wide baseline test still needs Tier 2 for 31 real quotes — that gap is expected and correct, not a bug (see below).

## Quote Verification Reality Check (D-03) — measured, not assumed

Ran the exact Tier-1/Tier-2/reject algorithm D-03 specifies against **all 864 evidence quotes currently in `data/manual/chapter_roll_overrides.json`**, resolving each quote's `mention_chapter_num` to its epub HTML via `chapters.json:epub_href` and a direct `zipfile` read of the (locally present) epub:

| Tier | Count | % of 864 |
|------|-------|----------|
| Tier 1 (byte-exact substring) | 833 | 96.4% |
| Tier 2 (confusable-folded + whitespace-collapsed + case-insensitive substring) | 31 | 3.6% |
| Fail (neither tier matches) | **0** | **0.0%** |

**Conclusion: success criterion 1's 100% baseline is empirically reachable for the quote-verification half of the check right now, with zero corpus edits.** None of the 31 Tier-2 quotes required a word-level edit to match — they needed only whitespace/paragraph-break collapsing (confirmed: exactly 31 of the corpus's evidence quotes contain an internal `\n\n`/paragraph break, and this count matches the Tier-2 count 1:1) or dash/quote/ellipsis folding. No corpus quote anywhere required rejection.

`html_tag_intrusion` and `entity_intrusion` checks (regex for `<[^>]*>` or `&\w+;`/`&#\d+;` literally inside a quote's `text` field) both returned **zero** across all 864 quotes — hand-curated quotes are always already-clean prose text, never raw HTML fragments. The verifier does not need to defend against HTML-tag-contaminated `evidence_quotes[].text` values from the existing corpus (though an agent-authored future quote could still introduce this — worth a structural sanity check even though it costs nothing today).

## Position Semantics (D-04) — measured

Two different fields carry position information in the override schema, and they are **not interchangeable**:

- `roll.word_position` (roll-level): **0 of 681 rolls** in the current corpus have this populated. It is a pipeline-computed field (`_explicit_extra_slot_position` in `derive_roll_facts.py` reads it first, before falling back to `mention_word_position`), not something hand-curation sets today.
- `roll.mention_word_position` (roll-level, distinct from the per-quote field of the same name): **43 of 681 rolls** have this populated — used together with `display_position_policy` to pick the roll's *display* anchor position (per `_explicit_extra_slot_position`'s logic: only consulted when `display_position_policy` is `"mention"` or `"source_marker"`).
- `evidence_quotes[].mention_word_position` (quote-level): **833 of 864 populated quotes** carry this — this is the field the verifier actually checks each quote's claimed position against.

Measured distance (in CP-earning words, via the extracted tokenizer) between each Tier-1 quote's **claimed** `mention_word_position` and the **nearest actual occurrence** of that quote's text in the claimed chapter's prose (n=833, using nearest-occurrence disambiguation per the pitfall above — 36 of these 833 quotes have their exact text appearing 2+ times in the same chapter, so nearest-occurrence selection is required, not optional):

| Percentile/stat | Distance (CP-earning words) |
|---|---|
| Exact match (distance 0) | 179 (21.5%) |
| ≤5 words | 640 (76.8%) |
| ≤20 words | 825 (99.0%) |
| ≤50 words | 833 (100.0%) |
| Median | 4 |
| P90 | 6 |
| P99 | 16 |
| Max | 41 |

Tier-2 quotes (n=30 of 31 measured via a flexible-whitespace regex probe; the 31st resolved in the primary Tier-1/2 pass above via full-text normalization but this research's supplementary position-probe script had an unrelated normalization-mapping limitation on that single case — not a corpus problem) show the same pattern: max distance 15, well inside the Tier-1 envelope.

**Recommendation for the D-04 tolerance constant:** a named constant of **50 CP-earning words** (e.g. `POSITION_TOLERANCE_WORDS = 50`) covers 100% of the current corpus with clear margin (max observed: 41), while still being tight enough to catch a genuinely wrong `mention_chapter_num`/`mention_word_position` pairing (which the corpus never exhibits — 0 cross-chapter false matches were found; see below). Document the rationale inline as: "measured against the full 118-chapter hand-curated corpus (2026-07-26): max real distance 41 words after nearest-occurrence disambiguation; 50 gives ~20% headroom."

**Cross-chapter check (part of D-04's "always fail if found in a different chapter" rule):** in this measurement, zero quotes were found to match only in a chapter other than their claimed `mention_chapter_num` — the corpus never exhibits this failure mode today, so the "always fail" rule cannot be validated against a real corpus example. Recommend a synthetic unit-test fixture for this rule rather than relying on corpus coverage.

## Perk Resolution Reality Check (D-06c) — the phase's central planning risk

> ## ⚠ SUPERSEDED 2026-08-01 — THIS SECTION'S CONCLUSION IS WRONG. DO NOT PLAN AGAINST IT.
>
> This section reports ~80.8% resolution and "14 permanently-unresolved perk names" framed as
> `perk_directory.json` / `perk_aliases.json` coverage gaps. **That framing is incorrect.** All 14
> are `cost: 0` **free ride-alongs** — granted alongside a paid acquisition and absent from the
> rollable roster *by design*, because they are not rollable. The measurement demanded they resolve
> through a ladder built for rollable perks, which they never can.
>
> Re-measured against the real corpus: **paid perk mentions resolve 99/99 (100%)** through the
> existing ladder, and **cost-0 ride-alongs resolve 15/15 (100%)** when checked against
> `obtained_perks.json`. One name (`ARM SLAVE M6 Bushnell`) needs only chapter-adjacent tolerance
> (roll in ch 81, grant recorded at ch 82). **There is no data gap and no data fix is required.**
>
> The corrected rule is `02-CONTEXT.md` → "D-06(c) CORRECTION — paid vs. free perk resolution".
> The remedies proposed below (exception allowlist / prerequisite data fix / scope narrowing) are
> all answers to a non-existent problem; `02-02-PLAN.md`, which implemented the data fix, has been
> removed. The rest of this file — tokenizer blast radius, quote verification, position tolerance —
> was independently re-verified and remains sound.

Ran `perk_name_resolver.build_directory_match_index()` (real `data/derived/perk_directory.json` + real `data/manual/perk_aliases.json`, unmodified) against **all 120 perk-name strings** appearing in `chapter_roll_overrides.json`'s `rolls[].perks[]` arrays across the corpus, calling `.lookup(name, jump=?, constellation=roll.constellation)` — the same call shape `derive_roll_facts.py::lookup_perk` uses.

**Critical mechanism finding:** `DirectoryMatchIndex.lookup()`'s Steps 1-3 (exact match, alias-exact match, normalized-(name,jump) match) all iterate over a `jumps_to_try` list that is **only populated `if jump:`** — passing `jump=None` (the only value available directly from an override roll object, which has no `jump` field) causes Steps 1-3 to execute as no-ops, leaving only Step 4 (name-only, constellation-scoped fallback) active.

| Scenario | Resolved | % |
|---|---|---|
| `jump=None` (only info an override roll object itself provides) | 97 / 120 | 80.8% |
| `jump=` cross-referenced from `data/derived/obtained_perks.json` by `(chapter_num, normalized perk_name)` | 106 / 120 | 88.3% |
| Still unresolved after jump cross-reference | 14 / 120 | 11.7% |

**Why the jump cross-reference only gets partway there — and why it may not be available at all for Phase 3's actual targets:** `data/derived/obtained_perks.json` is generated from a hand-tracked reference spreadsheet ("the Unabridged List") whose own `_note`/`_coverage` field states it covers *"full story EPUB sequences 1-192, story chapters 1 - 119.5"* — it has **not been updated past chapter 119.5**, and Phase 1's epub refresh already extended the story to chapter 198 (`120.2` → `121.1` and beyond). This means the jump-cross-reference trick that recovers 9 of the 23 no-jump failures **will not exist at all** for the ~80 chapters Phase 3's agent curation actually targets (chapters past 119.5) — those chapters have zero `obtained_perks.json` coverage to cross-reference against. For that future population, **80.8% (not 88.3%) is the realistic ceiling** for what "resolves through the ladder with the information an agent-curated entry can actually supply" means.

The 14 permanently-unresolved perk names (even with full jump context) cluster heavily in one chapter:

```
('36', 'Weapon & Item Storage Chest', None, jump='Monster Hunter')
('79', 'Core Ability - Amp Core', 'Knowledge', jump='Titanfall')
('79', 'Oi!', 'Knowledge', jump='Titanfall')
('81', 'ARM SLAVE M6 Bushnell', 'Knowledge', jump=None)
('82', 'Farming tool', 'Quality', jump='Viking Saga')
('91', 'Primo Victoria', 'Toolkits', jump='Sabaton')
('92', 'Altmode', 'Size', jump='Transformers')          ┐
('92', 'Decepticon Terrorize!', 'Size', jump='Transformers') │ 6 of 14 are
('92', 'Energon', 'Size', jump='Transformers')           ├─ chapter 92's
('92', 'Energon Battle Pistol', 'Size', jump='Transformers') │ Transformers
('92', 'Energon Melee Weapon', 'Size', jump='Transformers') │ sub-instances
('92', 'ROBOTS IN DISGUISE! - Medium Chassis', 'Size', jump='Transformers') ┘
('93', 'The Village', 'Personal Reality', jump='Personal Reality')
('95', 'Gladius-class Heavy Corvette', 'Knowledge', jump='Halo')
```

These are genuine `perk_directory.json`/`perk_aliases.json` coverage gaps (perks that legitimately exist in the story but were never added to the Unabridged List catalog the directory is built from), not a resolver-logic bug — this is data-completeness debt in a Phase-1-owned artifact, structurally identical in kind to the ch104 stale-anchor precedent (D-08's "the corpus/reference data needs a human, the verifier is not wrong").

**This is a direct threat to success criterion 1 as literally worded ("100%... a failure means the verifier is wrong, not the corpus").** Recommend the planner treat this exactly like ch104: NOT a verifier bug, NOT something to code around with a looser match, but an explicit, named exception path. Concretely, one of:
1. **Exception list:** the verifier ships with a small, explicit, version-controlled allowlist of `(chapter_num, perk_name)` pairs that are known-unresolvable pending a `perk_directory.json`/`perk_aliases.json` fix, and the D-10 corpus-wide baseline test treats an allowlisted miss as non-fatal (logged, not a `fail`) — mirroring how ch104's stale anchor is a documented, named exception rather than a silently-passing test.
2. **Prerequisite data fix:** file the 14 gaps as `perk_aliases.json`/`perk_directory.json` additions (a data-curation task, likely small) as a Wave-0 or pre-phase-gate step, closing the gap before the baseline test runs. This is the cleaner outcome if the additions are genuinely simple (most of the 14 look like missing alias entries or missing directory rows for legitimate one-off narrative perks).
3. **Scope narrowing:** interpret D-06(c)'s "resolves through the ladder" as "the ladder is invoked and its result (resolved-or-not) is recorded," with `perk_unresolved` becoming a `no_evidence`-style third outcome rather than a hard `fail` — but this weakens success criterion 1 more than option 1 or 2 and should only be chosen with an explicit sign-off, since it changes what "100%" means.

Do not let this surface for the first time during phase-gate execution — it is fully knowable now, and the numbers above are exact and reproducible against the current corpus.

## Chapter Prose Addressing — how position gets from `mention_chapter_num` to characters

1. `data/derived/chapters.json`'s `chapters[]` array maps `chapter_num` (string) → `epub_href` (e.g. `"chap_1.xhtml"`).
2. The epub is opened via `zipfile.ZipFile(EPUB)`; each chapter's HTML is read via `zf.read(f"EPUB/{href}").decode("utf-8")` — this exact path prefix (`"EPUB/"` + href) is used identically in `find_text_backed_rolls.py`, `find_roll_locations.py`, and `extract_chapter_sections.py`; the extracted module should preserve it.
3. `_split_sections(html)` returns `(header, html_start, html_end)` tuples demarcated by `<p><strong>X</strong></p>`-style markers.
4. Sections are filtered to only those where `section_classifications.json`'s `f"{chapter_num}@{section_index}"` entry has `counts_for_cp: true` (default `True` when absent, matching `predict_rolls.py`'s own convention per the "BUG FIX" comment in `find_text_backed_rolls.py:200-212` — this comment documents a real historical bug where using the wrong classification source caused predicted positions to land in the XML preamble).
5. Within each counted section, `_strip_to_spaces` replaces every HTML tag/entity with equal-length whitespace (preserving character offsets 1:1 against the original HTML), then `re.finditer(r"\S+", spaced)` walks CP-earning "words," recording each word's **character offset in the original chapter HTML** (not a word count, not a byte offset into stripped-plain-text — this distinction matters for the verifier's own quote-to-position mapping, which must use the same char-offset-list-then-`bisect`-search approach this research prototyped).
6. A char offset is converted to a within-chapter CP-earning word index via `bisect.bisect_right(word_index_list, char_offset) - 1` — this is the operation the verifier needs for D-04's position-tolerance check (find which CP-earning word index a matched quote's char offset falls into, then compare to the claimed `mention_word_position`).
7. `<body[^>]*>` clamping: any section starting before the epub's `<body>` tag is clamped forward, preventing the XML/DOCTYPE/`<title>` preamble from being counted as CP-earning prose.

## Test/Fixture Strategy (D-10) — no existing precedent, this is genuinely new infrastructure

Surveyed every test file in `tests/` that references `epub`/`EPUB` (19 files). **None of them read the real epub.** The pattern is uniformly:
- `test_an_detector.py`, `test_extract_classify_predict_scenarios.py`: construct small synthetic HTML strings inline and call `_split_sections`/`_classify_section` directly against them — no epub file touched.
- `test_realign_chapters.py`, `test_chapter_alignment*.py`: `monkeypatch.setattr(module, "OVERRIDES_PATH", tmp_path/...)` style — isolate via `tmp_path` + monkeypatched module-level path constants, operating on synthetic fixture JSON, never the real epub.
- `test_roll_position_invariants.py`: the closest existing precedent to a "loop over the whole corpus" test — it iterates all of `data/derived/chapters.json`/`roll_facts.json` and asserts invariants, but its inputs are already-generated derived JSON, never the raw epub.

**No file in this codebase currently contains a `pytest.mark.skipif`/epub-existence check of any kind.** D-10's requirement ("the test must skip with an explicit reason when the gitignored epub is absent") is genuinely new test infrastructure for this project, not an established pattern to imitate. Recommended shape (standard pytest, no project precedent to contradict):
```python
EPUB_AVAILABLE = (RAW / "Brocktons_Celestial_Forge.epub").exists()

@pytest.mark.skipif(not EPUB_AVAILABLE, reason="epub is gitignored; corpus baseline needs local source")
def test_verifier_passes_full_hand_curated_corpus():
    ...
```
No `conftest.py` exists anywhere in `tests/` today — if the planner wants a shared `EPUB_AVAILABLE` fixture/constant reused across `test_cp_word_index.py` and `test_mechanical_verifier.py`, this phase would be the first to introduce one. A simple module-level constant duplicated in both test files is lower-risk and consistent with this codebase's existing style (every test file computes its own `ROOT`/`sys.path.insert` block independently rather than sharing a `conftest.py`).

## Runtime State Inventory

> Included because D-01/D-02 constitute a rename/extraction/refactor of existing code (moving `_chapter_word_index`/`_split_sections`/`_strip_to_spaces` out of their current homes and fixing a hardcoded path). All five categories below resolve to "none" because this is a pure intra-repo Python source change with no external runtime service, but each is stated explicitly per the mandatory-read protocol rather than left blank.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no database/datastore keys on these function names; the extraction moves Python symbols, not data | none |
| Live service config | None — no external service (n8n, Datadog, etc.) references these functions | none |
| OS-registered state | None — no OS-level task/process registration involved | none |
| Secrets/env vars | `BCF_DATA_DIR` already exists (`scripts/data_paths.py`) and is unchanged by this phase — D-02 makes the new module *read* it (fixing the current hardcoded-path bug), it does not introduce a new env var or rename an existing one | none — this is a code fix (import path), not a secret/env-var migration |
| Build artifacts / installed packages | None — pure Python source, no compiled/packaged artifact references the old private-function locations | none |

## Code Examples

### Nearest-occurrence position check (this research's validated prototype)
```python
# Source: prototyped and validated against the full 118-chapter corpus in this
# research session (833/833 Tier-1 quotes measured; max distance 41 words).
import bisect, re

def nearest_occurrence_distance(quote_text: str, chapter_html: str,
                                  word_index: list[int], claimed_word_pos: int) -> int | None:
    """Return the minimum CP-earning-word distance between `claimed_word_pos`
    and any occurrence of `quote_text` in `chapter_html`. None if no occurrence.
    """
    offsets = [m.start() for m in re.finditer(re.escape(quote_text), chapter_html)]
    if not offsets:
        return None
    best = None
    for off in offsets:
        word_idx = bisect.bisect_right(word_index, off) - 1
        dist = abs(word_idx - claimed_word_pos)
        if best is None or dist < best:
            best = dist
    return best
```

### Confusable-folding table (D-03 Tier 2, hand-written per the D-03 boundary — validated)
```python
# Source: this research's prototype, matched exactly against D-03's named
# confusable set (dashes, quotes, ellipsis) plus whitespace collapse + casefold.
def fold_confusables(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-")      # en-dash, em-dash
    s = s.replace("‘", "'").replace("’", "'")        # curly single quotes
    s = s.replace("“", '"').replace("”", '"')        # curly double quotes
    s = s.replace("…", "...")                              # ellipsis
    return s

def normalize_tier2(s: str) -> str:
    s = fold_confusables(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()
```
Validated: this exact function, applied to both the quote text and the full chapter prose before an exact substring check, resolves all 31 quotes in the corpus that fail Tier 1 — 0 residual failures.

### Perk-ladder call shape (existing precedent, `derive_roll_facts.py:92-100`)
```python
# Source: scripts/derive_roll_facts.py (existing, unmodified — reuse exactly)
def lookup_perk(match_idx, name, jump=None, constellation=None):
    if not name:
        return None
    return match_idx.lookup(name, jump=jump, constellation=constellation)
```
The verifier must decide (per the Perk Resolution Reality Check above) what `jump` value it passes — this is the single open design decision blocking a correct D-06(c) implementation.

## State of the Art

Not applicable in the usual sense — this phase touches no rapidly-evolving external ecosystem. The one relevant "old approach / current approach" pair is internal:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `_split_sections`/`_strip_to_spaces` hand-duplicated across `extract_chapter_sections.py` and `find_roll_locations.py` | D-01 extracts one shared copy for `find_text_backed_rolls.py`'s consumption (does not touch the other two files' copies) | This phase (partial fix) | Reduces the duplication surface for this phase's own new consumer (the verifier) without fully resolving the pre-existing two-copy duplication — see blast-radius section above |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The recommended `POSITION_TOLERANCE_WORDS = 50` constant is a reasonable default; the *exact* value is Claude's Discretion per CONTEXT.md, and this research's empirical max (41) is a measurement, not a policy — a different value could be chosen and still be defensible | Position Semantics (D-04) | Low — any value ≥45 is empirically safe against the current corpus; a value chosen below 41 would break real, currently-passing hand-curated quotes and should be caught immediately by the D-10 baseline test |
| A2 | The 14 permanently-unresolved perk names are genuine `perk_directory.json`/`perk_aliases.json` data gaps rather than a resolver-logic bug this research's test harness introduced | Perk Resolution Reality Check | Medium — if a resolver-logic bug is the real cause (not tested exhaustively — e.g. whether `_normalized_word_prefixes` should have matched "Energon Battle Pistol" to a base "Energon" row and didn't for a reason not yet root-caused), the fix would be a ladder bug-fix instead of a data-gap exception, changing which of the three recommended resolutions applies |
| A3 | `data/derived/obtained_perks.json`'s coverage genuinely stops at chapter 119.5 and will not be extended to cover future chapters as part of this or an adjacent phase | Perk Resolution Reality Check | Medium — if a future phase (out of this one's scope) extends obtained_perks.json's source spreadsheet to track the newly-released chapters, the "80.8% is the realistic ceiling for Phase 3's targets" conclusion would need revisiting |

## Open Questions

1. **How should the D-10 corpus-wide baseline test treat the 14 unresolvable perk names?**
   - What we know: they are real, measured, reproducible gaps (exact list given above); ch104 is the established precedent for "document and skip, don't force green."
   - What's unclear: which of the three recommended resolutions (allowlist exception / prerequisite data fix / scope narrowing of what "resolves" means) the planner and Dre prefer.
   - Recommendation: raise this explicitly as a plan-time decision point (likely a `checkpoint:decision` task early in the plan), not something the executing agent should decide unilaterally mid-implementation.

2. **Should the extraction (D-01) also touch `find_roll_locations.py`/`extract_chapter_sections.py`'s pre-existing duplicate `_split_sections`?**
   - What we know: D-01's literal text says only `find_text_backed_rolls.py` gets rewritten; the duplication predates this phase and D-01 doesn't ask to fix it.
   - What's unclear: whether the planner considers this pre-existing duplication in-scope-by-spirit (no-parallel-implementations) or explicitly out-of-scope-by-letter (D-01's stated file).
   - Recommendation: treat as out of scope per the literal decision text, and file a `deferred-items.md` entry (matching this phase's established pattern) rather than silently expanding scope or silently ignoring the finding.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `data/raw/Brocktons_Celestial_Forge.epub` (gitignored) | D-10's corpus-wide baseline test; all quote/position verification | ✓ (present locally in this session, confirmed via `ls`) | n/a (binary epub) | D-10's `pytest.mark.skipif` — test suite must stay green without it, but the phase gate requires a run with it present |
| `jsonschema` (Python package) | Optional: registering a schema for the verifier's JSON report | ✓ (already a project dependency via `scripts/_common.py`) | already pinned by project | N/A — already present |
| `.venv` (project virtualenv, Python 3.14) | Running any of the scripts/tests referenced in this research | ✓ | 3.14 | N/A |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** the epub itself — CI/other machines without the private source will skip the corpus-wide test per D-10, exactly as designed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo-standard; `pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest tests/test_cp_word_index.py tests/test_mechanical_verifier.py -x` |
| Full suite command | `.venv/bin/python -m pytest` (per `scripts/verify.py`'s existing convention — expect the 5 pre-existing, known-accepted failures documented in Phase 1's deferred-items.md; judge by "no NEW failures," per CONTEXT.md's explicit instruction) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CINF-03 | Tier-1/Tier-2 quote verification accepts exact/normalized matches, rejects word-level drift | unit | `pytest tests/test_mechanical_verifier.py -k quote -x` | ❌ Wave 0 |
| CINF-03 | Position tolerance uses nearest-occurrence disambiguation within the named constant | unit | `pytest tests/test_mechanical_verifier.py -k position -x` | ❌ Wave 0 |
| CINF-03 | Perk names resolve through `perk_name_resolver.py`'s ladder with no second implementation | unit | `pytest tests/test_mechanical_verifier.py -k perk -x` | ❌ Wave 0 |
| CINF-03 | Enum/structural sanity (`outcome`, `display_position_policy`) | unit | `pytest tests/test_mechanical_verifier.py -k structural -x` | ❌ Wave 0 |
| CINF-03 (success criterion 1) | Verifier passes 100% (fail=0; `no_evidence` permitted) over all 118 hand-curated chapters | integration/corpus | `pytest tests/test_mechanical_verifier.py -k corpus_baseline -x` (skipped when epub absent) | ❌ Wave 0 |
| D-01/D-02 | Extracted tokenizer matches the prior `find_text_backed_rolls.py` behavior exactly (no silent drift) | unit | `pytest tests/test_cp_word_index.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/test_cp_word_index.py tests/test_mechanical_verifier.py -x`
- **Per wave merge:** full suite (`.venv/bin/python -m pytest`)
- **Phase gate:** full suite run with the epub present; recorded pass/no_evidence/fail counts go in the SUMMARY per D-10

### Wave 0 Gaps
- [ ] `tests/test_cp_word_index.py` — covers D-01/D-02's extracted tokenizer
- [ ] `tests/test_mechanical_verifier.py` — covers CINF-03's four checks plus the D-10 corpus-wide baseline
- [ ] Framework install: none — pytest already present, no new install needed
- [ ] Wave 0 spike (not a test file, but should run before implementation starts): re-run this research's perk-resolution measurement against the live repo state to confirm the 14-unresolved-perk list hasn't changed since this research, and get the Open Question 1 decision from Dre before writing the perk-check's `fail` logic

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Offline local CLI/library, no auth surface |
| V3 Session Management | No | No sessions |
| V4 Access Control | No | Single-user local repo tooling |
| V5 Input Validation | Yes (narrow) | The verifier reads only trusted, already-committed local JSON/epub files it does not accept untrusted network input; its own output (the JSON report) should still go through `write_validated_json`-style structural validation if a schema is registered, consistent with every other `build_*`/`derive_*` script's convention |
| V6 Cryptography | No | No crypto operations anywhere in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ReDoS via `re.escape(quote_text)` fed unbounded, attacker-controlled quote text into a regex engine | Denial of Service | Not a realistic concern here — `evidence_quotes[].text` values are either hand-curated (trusted) today or, in Phase 3, will be model-generated but locally processed (no network-facing regex evaluation); `re.escape()` neutralizes any regex metacharacters in the literal quote text before matching, which is already the correct mitigation and should be kept in the implementation exactly as prototyped in this research (never build the position-search regex from raw, un-escaped quote text) |

## Sources

### Primary (HIGH confidence — direct codebase inspection and empirical measurement in this session)
- `scripts/find_text_backed_rolls.py` — full read; confirmed `_chapter_word_index` (:80) is genuinely private, confirmed `_split_sections`/`_strip_to_spaces` are imported (not defined) at :54-56
- `scripts/find_roll_locations.py` — full read of relevant sections; confirmed `_split_sections` (:305) docstring self-reports duplication of `extract_chapter_sections.py`
- `scripts/extract_chapter_sections.py` — read `_split_sections` (:461) and diffed against `find_roll_locations.py`'s copy
- `scripts/perk_name_resolver.py` — full read of the resolution ladder (`load_perk_aliases`, `build_alias_lookup`, `resolve_canonical`, `DirectoryMatchIndex`, `build_directory_match_index`)
- `scripts/derive_roll_facts.py` — read the quote-extraction (`_evidence_quotes`, :685-715), position-resolution (`_explicit_extra_slot_position`, :842-856), and perk-lookup (`perk_meta`/`lookup_perk`, :92-100, :247-290, :2680-2753) logic
- `scripts/_common.py` — full read (`write_validated_json` schema-validation convention)
- `scripts/query_exemplars.py` — full read (pure-module/thin-CLI precedent for D-09)
- `data/manual/chapter_roll_overrides.json` — read `_purpose` header; empirically measured all 864 evidence quotes and 120 perk names against the real epub and real perk directory in this session
- `data/derived/perk_directory.json`, `data/derived/obtained_perks.json`, `data/derived/chapters.json`, `data/manual/section_classifications.json` — read/queried directly for the perk-resolution and tokenizer-position measurements
- `tests/*.py` (grep across all 19 epub-referencing test files) — confirmed no existing test reads the real epub or uses a `pytest.mark.skipif`-style guard
- Empirical scripts run in this session (`.venv/bin/python`, real repo data, real locally-present epub): Tier-1/Tier-2/fail corpus scan (864 quotes), nearest-occurrence position-distance measurement (833 quotes), perk-name resolution measurement with and without jump cross-reference (120 perk mentions)

### Secondary (MEDIUM confidence)
- None — this phase required no external web research; all findings are direct-inspection or direct-measurement against this specific repository

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, pure stdlib, confirmed by direct prototyping
- Architecture: HIGH — directly read every file in the dependency graph; consumer map built via `grep -rn`, not assumed
- Pitfalls: HIGH — both major pitfalls (nearest-occurrence, jump-context) were discovered by running the actual algorithm against the actual corpus, not by inspection alone
- Perk resolution risk: HIGH confidence in the *numbers*; MEDIUM confidence in the *root cause* of the 14 residual gaps (Assumption A2) — recommend the Wave-0 spike re-confirm before committing to a resolution path

**Research date:** 2026-07-26
**Valid until:** Effectively indefinite for the archaeological findings (tokenizer duplication, ladder mechanics) since they describe existing, committed code. The empirical corpus numbers (864 quotes, 120 perks, 118 chapters) will drift the moment new chapters are hand-curated or `perk_directory.json`/`perk_aliases.json` are edited — treat the exact percentages as a 2026-07-26 snapshot and re-run the measurement scripts described above if more than a few weeks pass before this phase executes.
