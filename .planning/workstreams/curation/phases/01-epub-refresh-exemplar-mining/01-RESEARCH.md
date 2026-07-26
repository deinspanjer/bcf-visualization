# Phase 1: Epub Refresh & Exemplar Mining - Research

**Researched:** 2026-07-26
**Domain:** Deterministic Python data-pipeline refresh + derived-artifact mining over an existing ETL DAG (no LLM calls)
**Confidence:** HIGH — every claim below is grounded in direct reads of this repo's own scripts, tests, and live local data (`data/derived/`, `data/manual/`, `data/private-source/`), not general pattern recall.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Carried forward (locked — do not re-litigate):**
- D-04 (mobile-ux interview) provenance shape — `curated_by: "human" | "agent"` marker — binds Phase 3, not this phase.
- Workstream Gate 1: this phase is a hard gate; no verifier/schema/agent work starts until it is green.
- Project rules: no parallel implementations of domain quantities; only `chapter_facts.json:cp_earning_word_count` is valid for CP math; story prose stays local; hand-curated data is authoritative.

**Regime tagging (auto-resolved 2026-07-26):**
- **D-01:** A chapter's regime tag comes from the pipeline's existing computation — `chapter_facts.json:point_calculation_regime` — never recomputed by the exemplar-mining code. If the miner needs regime at finer granularity (per-roll), it reads whatever the existing simulation already emits; it must not re-derive regime from `regime_transitions.json` itself.
- **D-02:** Chapters containing a mid-chapter regime transition (e.g., ch 97 / Nano-Forge) are tagged with **both** regimes plus an explicit boundary flag. Retrieval for a target in either adjacent regime may return them, and the boundary flag is preserved in the index so Phase 3's regime-boundary sensitivity check (ACUR-02) can identify them without re-deriving.

**Exemplar index artifact (auto-resolved 2026-07-26):**
- **D-03:** The index is a derived artifact (`data/derived/`) built by a new `scripts/` build script following the existing `build_*`/`derive_*` conventions, wired into `scripts/pipeline.py` and registered in the `data_release.py` manifest — **Reversibility: costly.**
- **D-04:** Index entries reference source rolls by chapter + roll identity and may carry the already-committed evidence-quote text from `chapter_roll_overrides.json`. No text sourced from epub prose itself goes into the committed index.

**Corpus characterization (auto-resolved 2026-07-26):**
- **D-05:** Two outputs: machine-readable statistics inside the index artifact (roll-shape distribution incl. multi-grab frequency, evidence-quote patterns, `cp_ledger_checkpoint` usage, perk-link/naming conventions), plus a human-readable analysis report (markdown) for Phase 3 prompt design. The report may quote examples only via already-committed evidence quotes.

**Retrieval (auto-resolved 2026-07-26):**
- **D-06:** Retrieval is a deterministic pure-Python function: given a target chapter, return only exemplars whose regime tags include the target's regime. No embeddings, no fuzzy similarity, no LLM. Within-regime ranking heuristic is Claude's discretion but must be deterministic and tested.

**Staleness clearance & refresh ordering (auto-resolved 2026-07-26):**
- **D-07:** Order: sync private source → hydrate epub → full pipeline re-run → regenerate derived artifacts and manifest → then diagnose whatever failures remain. Do not hand-patch stale sha256s or individual derived files before the regen.
- **D-08:** If any residual failure (notably the ch 95.5 multi_grab override) traces to a hand-curated entry rather than stale derived data, the fix is **surfaced to Dre with a diagnosis, not silently applied**. Plan a human checkpoint for exactly this contingency.
- **D-09:** "Newest release" is verified mechanically: post-hydrate chapter count and nav entries compared against the private-source repo's current state, and predicted rolls demonstrably extend past the previous last chapter.

### Claude's Discretion
- Exact index schema field names and file name (within `data/derived/` + manifest conventions)
- Retrieval ranking heuristic within the same-regime constraint (deterministic, tested)
- Where the human-readable corpus report lives (phase dir vs `docs/`), and its structure
- Exact mechanism for the chapter-count/nav verification and how it is scripted
- Whether exemplar mining is one script or a build + query module pair

### Deferred Ideas (OUT OF SCOPE)
- Confidence/error dashboard across curation runs — v2 (CUR2-01)
- Automated re-curation triggers when new epub versions revise old chapters — v2 (CUR2-02)
- Any LLM-assisted mining/summarization of the corpus — Phase 3 territory; this phase is deterministic analysis only
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EPUB-01 | Latest released chapters fetched via `sync_private_source_repo.py` → `hydrate_source_epub.py`; chapter count/nav reflect newest release | See "Epub Refresh Mechanics" — exact command sequence, current local state (last synced 2026-05-16, ch120.2), and the `chapter_nav_entries`/`parse_epub_nav` verification points documented below |
| EPUB-02 | Full pipeline re-run completes green: predicted rolls extend into new chapters, curated chapters still validate, `visualization_facts.json` rebuilds | See "Staleness Mechanics" — `data_release.py check-derived`'s two independent checks (manifest sha256, live predicted-rolls re-simulation) and `chapter_alignment.py`'s fingerprint guard, both of which gate `build_chapter_facts.py` |
| CINF-02 | Exemplar corpus mined from hand-curated chapters, tagged by CP regime, retrieval constrained to same-regime | See "Exemplar Index Design" — schema mined from `chapter_roll_overrides.json`'s actual 118-chapter shape, regime-tagging mechanics via `regime_simulator.py`, and the ch97 boundary-tagging approach |
</phase_requirements>

## Summary

This phase has two independently-verifiable halves. **Half A (EPUB-01/02)** is a refresh-and-verify operation over an already-working pipeline: `sync_private_source_repo.py` (push a newer epub into the private tracking repo) → `hydrate_source_epub.py` (pull it into `data/raw/`, validate nav/chapter-number parsing, write a source sidecar) → `scripts/pipeline.py --target data --force` (regenerate every derived artifact) → `scripts/data_release.py manifest` (re-stamp sha256s) → `scripts/verify.py` (the actual green/red gate: `git diff --check`, `check-derived`, full `pytest`). The local checkout's private-source clone is currently frozen at `source-v20260516.1` (195 chapters through 120.2, published 2026-05-15) — over two months stale relative to today (2026-07-26), so this phase **will** find new chapters to pull.

**Half B (CINF-02)** is a pure-Python mining pass over the 118-chapter hand-curated corpus in `data/manual/chapter_roll_overrides.json`, following the exact `build_*` script conventions already used by `derive_outstanding_perks.py` et al. Regime tagging must read `chapter_facts.json:point_calculation_regime` per D-01 — **but this field is currently computed by a buggy, out-of-sync duplicate** of the canonical `regime_simulator.regime_for_chapter()` (see Pitfall 1 below), which matters directly for the ch97 boundary-tagging requirement (D-02).

**Primary recommendation:** Run the refresh with `pipeline.py --force` (not relying on its own staleness heuristics — see Pitfall 2, a real dependency-declaration bug that would otherwise silently skip regenerating steps that depend on `chapter_roll_overrides.json`), then let `data_release.py check-derived` and the full `pytest` suite be the sole arbiters of "green." Build the exemplar index as a single new `Step` in `pipeline.py`'s DAG, sourced from `chapter_roll_overrides.json` + `chapter_facts.json` + `regime_transitions.json` only (no epub prose reads), and use `regime_transitions.json`'s own `chapter_num` list — not a re-derivation — to identify boundary chapters for dual-tagging.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Epub sync (private repo push/pull) | Local dev tooling (`scripts/`) | — | `sync_private_source_repo.py`/`hydrate_source_epub.py` are one-shot maintainer CLIs, not part of the runtime app |
| Derived-data regeneration | Data pipeline (`scripts/pipeline.py` DAG) | — | Existing dependency-graph runner; the phase adds one new `Step`, does not build a new runner |
| Staleness/freshness verification | Data pipeline (`scripts/data_release.py`, `scripts/chapter_alignment.py`) | Test suite (`tests/`) | Two independent oracles already exist: manifest sha256 check + live re-simulation compare, plus a separate fingerprint-drift guard; the test suite reads a snapshot copy of live `data/` at session start, so it only goes green once the pipeline itself is green |
| Exemplar index build | Data pipeline (`scripts/build_*.py` → `data/derived/`) | — | Must follow the existing derived-artifact convention exactly (schema_version, manifest-eligible top-level JSON, wired into `pipeline.py`) |
| Exemplar retrieval (same-regime query) | Data pipeline / library module | Phase 3 consumer (future) | Pure function over the derived index; no service boundary in this phase — Phase 3 imports it directly |
| Regime tagging | Data pipeline (`scripts/regime_simulator.py` is canonical) | Manual data (`data/manual/regime_transitions.json`) | `regime_simulator.py` is the single source of truth per project's no-parallel-implementations rule; `regime_transitions.json` supplies the boundary-chapter list only |

## Standard Stack

### Core

No new external dependencies. This phase is pure Python 3.14 stdlib (`json`, `pathlib`, `hashlib`, `argparse`, `dataclasses`) work over the existing project scripts, matching every other `build_*`/`derive_*` script in `scripts/`. `.venv/bin/python` is Python 3.14.4, already provisioned. `[VERIFIED: local .venv inspection]`

| Tool/Module | Version | Purpose | Why Standard |
|---|---|---|---|
| Python stdlib (`json`, `hashlib`, `pathlib`) | 3.14.4 (project `.venv`) | Exemplar mining, index build | Every existing derived-artifact script in `scripts/` uses only stdlib — no JSON schema library, no dataframes; consistency with project convention |
| `gh` CLI | authenticated (`deinspanjer`, ssh protocol) | `sync_private_source_repo.py`'s `gh repo clone`/push flow | Already the sanctioned auth mechanism; confirmed logged in locally `[VERIFIED: gh auth status]` |
| `pytest` | project-pinned (see `pyproject.toml` `testpaths = ["tests"]`) | Full-suite green gate (EPUB-02) | Existing test harness; no new config needed |

### Supporting

None — no supporting libraries needed for either half of this phase.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A new `build_exemplar_index.py` + separate `query_exemplars.py` module | A single combined script (build+query) | CONTEXT.md D-06/discretion note explicitly leaves "one script or a pair" open; a pair is recommended below (see Architecture Patterns) for testability — Phase 3 needs to import the retrieval function without re-running the build |
| Reading `regime_transitions.json`'s `chapter_num` list to find boundary chapters | Calling `regime_simulator.regimes_for_chapter()` with real `perks_in_chapter`/`chapter_words` args | The full simulator call requires sourcing per-chapter ordered perk lists and word counts just to get a boundary flag — more machinery than the tagging use case needs; reading the transition table's own `chapter_num` field is a direct read of already-curated data, not a re-derivation, and is cheaper and equally correct for a boolean "is boundary" + "which two regimes" answer (see Pitfall 1 for the exact recipe) |

**Installation:** None required — no `pip install` for this phase.

**Version verification:** N/A (no new packages).

## Package Legitimacy Audit

**Not applicable.** This phase introduces zero new external packages (Python or otherwise) — pure stdlib scripting over the existing pipeline, per the orchestrator's research-focus hint and confirmed during research (no `pip install` anywhere in the relevant code paths). If the plan later discovers a need for a dependency, treat that as a plan-review flag requiring re-verification against this gate.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────┐
                          │  data/private-source/ (git clone) │
                          │  (gh-authenticated, gitignored)    │
                          └───────────────┬─────────────────┘
                                          │ sync_private_source_repo.py
                                          │  (--download via FicHub, or copy
                                          │   local data/raw/*.epub; commit+
                                          │   tag+push to private repo)
                                          ▼
                          ┌─────────────────────────────────┐
                          │  hydrate_source_epub.py           │
                          │  selects private-source epub →    │
                          │  data/raw/Brocktons_..epub         │
                          │  + parses nav.xhtml (chapter list) │
                          │  + validates manual/*.json chapter │
                          │    references against nav          │
                          │  writes data/raw/*.source.json     │
                          └───────────────┬─────────────────┘
                                          │ [EPUB-01 gate: chapter count/nav
                                          │  entries verified vs private-source]
                                          ▼
      ┌───────────────────────────────────────────────────────────────┐
      │  scripts/pipeline.py  (TopologicalSorter DAG, --force to bypass │
      │  its own imperfect staleness heuristics — see Pitfall 2)        │
      │                                                                  │
      │  parse_chapters → extract_chapter_sections → predict_rolls      │
      │       → find_text_backed_rolls, derive_roll_outcomes            │
      │       → derive_roll_facts (reads chapter_roll_overrides.json)   │
      │       → build_chapter_facts (point_calculation_regime here;     │
      │            ALSO calls chapter_alignment.fail_if_misaligned()    │
      │            at startup — see Pitfall 3)                          │
      │       → build_visualization_facts                                │
      │  [NEW] → build_exemplar_index  (reads chapter_roll_overrides.json│
      │            + chapter_facts.json + regime_transitions.json;      │
      │            writes data/derived/exemplar_index.json)             │
      └───────────────────────────────┬─────────────────────────────────┘
                                      │
                                      ▼
                    ┌───────────────────────────────────────┐
                    │  scripts/data_release.py                │
                    │   manifest   — re-stamp sha256s          │
                    │   check-derived — TWO independent checks:│
                    │     (a) manifest sha256 vs on-disk file  │
                    │     (b) LIVE re-simulation of             │
                    │         predicted_rolls.json via           │
                    │         predict_rolls._simulate() +        │
                    │         multi_grab.merge_paid_units()      │
                    │         — this is where the ch95.5          │
                    │         "no obtained perk" error surfaces  │
                    └───────────────┬─────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────────────┐
                    │  scripts/verify.py                      │
                    │   git diff --check → check-derived      │
                    │   → pytest (full suite)                 │
                    │  [EPUB-02 / green gate]                 │
                    └─────────────────────────────────────────┘

Exemplar retrieval (CINF-02), consumed later by Phase 3, not built here:
   target_chapter → query_exemplars.retrieve(regime_tags, index) → same-regime
   exemplar subset, deterministic ranking, no embeddings/LLM.
```

### Recommended Project Structure

```
scripts/
├── build_exemplar_index.py   # NEW — mines chapter_roll_overrides.json,
│                              #   tags by regime, writes derived artifact
├── query_exemplars.py         # NEW — deterministic same-regime retrieval
│                              #   function; imported by Phase 3, tested here
├── verify_epub_freshness.py   # NEW (or a function added to hydrate_source_epub.py) —
│                              #   scripted chapter-count/nav comparison for D-09
data/derived/
└── exemplar_index.json        # NEW derived artifact (name is Claude's discretion;
                                #   must carry schema_version like every sibling file)
.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/
└── corpus-analysis-report.md  # NEW human-readable report (D-05) — location is
                                #   Claude's discretion; phase dir keeps it
                                #   co-located with the phase that produced it
```

### Pattern 1: Follow the existing `build_*` script skeleton exactly

**What:** Every derived-artifact script (`derive_outstanding_perks.py` is the cleanest example) follows: `argparse` with `--output`/`--<input>` flags defaulting to the standard `data/derived`/`data/manual` paths, a pure-function core, a `SCHEMA_VERSION` constant, `payload = {"schema_version": N, ...}`, `json.dumps(..., indent=2, ensure_ascii=False)`, and a stdout summary block with sanity-check warnings printed to stderr (not raised) for soft anomalies.

**When to use:** For `build_exemplar_index.py` — this is exactly the shape D-03 calls for ("following the existing `build_*`/`derive_*` conventions").

**Example:**
```python
# Source: scripts/derive_outstanding_perks.py (this repo, read directly)
SCHEMA_VERSION = 1

def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    p.add_argument("--chapter-facts", type=Path, default=DEFAULT_CHAPTER_FACTS)
    p.add_argument("--transitions", type=Path, default=DEFAULT_TRANSITIONS)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    payload = {"schema_version": SCHEMA_VERSION, ...}
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"wrote {args.output.relative_to(ROOT)}")
```

### Pattern 2: Register the new artifact into `pipeline.py`'s DAG and `TARGET_FINAL_STEPS`

**What:** `pipeline.py` infers step ordering by matching each `Step`'s declared `inputs` to another step's `outputs` (see `_producer_by_output`). A new `Step` whose output nothing else consumes will be silently dropped from the `data` target's closure unless it is *also* added to `TARGET_FINAL_STEPS["data"]`.

**When to use:** Wiring `build_exemplar_index` in.

**Example:**
```python
# Source: scripts/pipeline.py (this repo, read directly) — pattern to follow
Step(
    name="build_exemplar_index",
    inputs=inputs(
        chapter_roll_overrides,              # data/manual/chapter_roll_overrides.json
        derived / "chapter_facts.json",       # point_calculation_regime (D-01)
        manual / "regime_transitions.json",   # boundary-chapter list only (D-01/D-02)
    ),
    outputs=(derived / "exemplar_index.json",),
    cmd=_py(root, "build_exemplar_index.py"),
),
# ...and:
TARGET_FINAL_STEPS = {
    "data": ("build_visualization_facts", "build_exemplar_index"),  # both, not just the first
    ...
}
```
Manifest registration is automatic for anything landing in `data/derived/*.json` with a `schema_version` key — `data_release.py`'s `_top_level_json_files()` globs `*.json` in `data/derived/` unconditionally (excluding only `data_package.json`/`_dev_data_package.json`), so no separate manifest-registration code is needed beyond running `scripts/data_release.py manifest` after the build.

### Pattern 3: Ch97 boundary tagging without re-deriving regime

**What:** `chapter_facts.json:point_calculation_regime` carries exactly ONE regime value per chapter (verified: ch97 → `3`). `data/manual/regime_transitions.json` lists `{"chapter_num": "97", "new_regime": 3, ...}`. Per D-01, the miner must not re-derive the regime *value* from the transition math — but reading the transition table's own `chapter_num`/`new_regime` fields to know *which* chapters are boundary chapters, and what the pre-transition regime was, is a direct read of already-curated/already-simulated data, not a re-derivation.

**Recommended recipe** (verified against actual local data):
```python
# For each chapter_num in chapter_facts.json:
#   primary_regime = chapter_facts_entry["point_calculation_regime"]
#   boundary_entry = next((t for t in regime_transitions if t["chapter_num"] == chapter_num), None)
#   if boundary_entry is None:
#       tags = {primary_regime}; is_boundary = False
#   else:
#       # regime_simulator.regime_for_chapter() is the canonical PRE-transition regime;
#       # boundary_entry["new_regime"] is the POST-transition regime (already hand-curated).
#       from regime_simulator import regime_for_chapter
#       tags = {regime_for_chapter(chapter_num), int(boundary_entry["new_regime"])}
#       is_boundary = True
```
For ch97 specifically this yields `tags = {2, 3}` — matching D-02's requirement exactly, and matching `regime_simulator.py`'s own docstring ("ch97's primary regime is 2 ... transitions flip to 3 mid-chapter"), even though `chapter_facts.json`'s single-value field currently reads `3` due to a bug (see Pitfall 1). **This recipe only needs `regime_simulator.regime_for_chapter()` (a pure, already-imported function used correctly elsewhere in the codebase) — it does not need `regimes_for_chapter()`'s word-offset machinery at all**, since the exemplar index only needs "which regimes apply", not "at what word".

### Anti-Patterns to Avoid
- **Writing a third `regime_for_chapter` implementation inside the new exemplar-mining script:** `build_chapter_facts.py` already has a rogue duplicate (Pitfall 1); do not add a fourth copy. Import `regime_for_chapter` from `scripts/regime_simulator.py` directly.
- **Trusting `pipeline.py`'s own dry-run/staleness detection to decide what needs rebuilding after this refresh:** its dependency declarations have a real bug (Pitfall 2) that under-declares inputs for two steps. Use `--force` for this one-time refresh rather than trusting incremental detection.
- **Silently running `realign_chapters.py --yes`** to clear any post-refresh fingerprint mismatches — this is exactly the "silently degrade the hand-curated evidence corpus" failure mode the project's core value forbids (see Pitfall 3 and D-08).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Regime-per-chapter computation | A new regime classifier in the exemplar miner | `scripts/regime_simulator.regime_for_chapter()` (import it) | Canonical source; `predict_rolls.py`, `derive_roll_outcomes.py`, `roll_scheduler.py` all already import from here — the ONE place that doesn't is the bug (Pitfall 1) |
| Chapter-count/nav-vs-newest-release verification | A bespoke epub-diffing script | `hydrate_source_epub.py`'s existing `parse_epub_nav()` + the private-source clone's `Brocktons_Celestial_Forge.metadata.json` (`chapters.count`, `last_chapter_friendly_number`) as the comparison baseline | Both pieces already exist; D-09 just needs a small script/assertion comparing the two, not a new parser |
| Staleness/freshness detection | A parallel "is this file stale" checker | `scripts/data_release.py check-derived` (manifest sha256 check) + `scripts/chapter_alignment.py check` (fingerprint drift) | Two independent, already-correct oracles exist; adding a third would be exactly the "parallel implementations" anti-pattern the project forbids |
| Exemplar corpus statistics (roll-shape, evidence-quote, perk-link distributions) | A statistics/analytics library dependency | Plain Python `collections.Counter`/dict aggregation over `chapter_roll_overrides.json` (118 chapters is small; no performance concern) | Matches every other derived script's dependency-free style; no library needed for counting/grouping ~700 roll objects |

**Key insight:** Every primitive this phase needs (regime computation, staleness detection, fingerprint-drift detection, manifest registration) already exists somewhere in `scripts/`. The exemplar-mining work is genuinely new (nothing currently characterizes the corpus this way), but every supporting computation it needs is a `import` away, not a rebuild.

## Common Pitfalls

### Pitfall 1: `build_chapter_facts.py` has a stale, out-of-sync duplicate of `regime_for_chapter` — a real parallel-implementation bug, currently silent
**What goes wrong:** `chapter_facts.json:point_calculation_regime` for ch97 reads `3`. The canonical `scripts/regime_simulator.regime_for_chapter("97")` returns `2` (its own docstring: "ch 97 is special. Its primary regime is 2 ... For chapters >= 98 we return 3 unconditionally"). `build_chapter_facts.py` (line ~77) has its **own local copy** of this function — commented "mirroring predict_rolls.py" — that never got the ch97 special case added: `if n <= 96: return 2` then unconditionally `return 3`, collapsing ch97 to 3.
**Why it happens:** `predict_rolls.py`, `derive_roll_outcomes.py`, and `roll_scheduler.py` all correctly `from regime_simulator import regime_for_chapter`; only `build_chapter_facts.py` forked its own copy at some point and the fork drifted when the ch97 special case was added upstream. `[VERIFIED: direct code comparison this session — grep confirms build_chapter_facts.py has no `from regime_simulator import` for this symbol]`
**How to avoid:** D-01 says the exemplar miner must trust `point_calculation_regime` as-is (do not recompute it) — so the miner's job is to work AROUND this via the Pattern 3 recipe (read the transition table directly for boundary chapters, not the buggy single-value field). Separately, flag this to the planner as a candidate one-line fix (`build_chapter_facts.py` should `from regime_simulator import regime_for_chapter` instead of defining its own) — it's a genuine "no parallel implementations" violation and currently has **zero test coverage** (`grep point_calculation_regime tests/*.py` returns nothing), so fixing it silently changes ch97's stored regime value from 3→2 with no test to catch the change. Recommend surfacing this as an explicit plan decision point (fix now vs. defer, and if fixed, whether any downstream consumer of `point_calculation_regime==3` for ch97 needs updating) rather than silently included as a drive-by fix.
**Warning signs:** Any future assertion like `chapter_facts["97"]["point_calculation_regime"] == 2` will currently fail; any exemplar-index test asserting ch97's "primary/before" tag must use `regime_simulator.regime_for_chapter`, not `chapter_facts.json`, for that specific value.

### Pitfall 2: `pipeline.py`'s declared inputs for two steps reference a file that doesn't exist — staleness detection silently misses `chapter_roll_overrides.json` edits
**What goes wrong:** `pipeline.py`'s `predict_rolls` and `find_text_backed_rolls`/`derive_roll_outcomes` steps declare `manual / "multi_grab_overrides.json"` as an input path. **No such file exists in `data/manual/`** — the actual file both scripts read at runtime is `chapter_roll_overrides.json` (via `multi_grab.load_overrides()`, whose `_OVERRIDES_PATH = MANUAL / "chapter_roll_overrides.json"`). Because `_is_stale()` only triggers on mtime/hash changes of *declared* inputs, and the declared path is permanently missing (`_path_mtime` returns `None` for it), editing `chapter_roll_overrides.json` alone will **never** mark these pipeline steps stale through `pipeline.py`'s own incremental-rebuild logic.
**Why it happens:** Naming drift — the file was presumably renamed from `multi_grab_overrides.json` to `chapter_roll_overrides.json` at some point and `pipeline.py`'s `Step` declarations weren't updated (only the `derive_roll_facts`/`build_chapter_facts` steps correctly declare `chapter_roll_overrides` as an input). `[VERIFIED: grep across scripts/ confirms the constant chapter_roll_overrides = manual / "chapter_roll_overrides.json" is used as an input only in derive_roll_facts and build_chapter_facts steps, while the identical logical dependency is mis-declared elsewhere]`
**How to avoid:** For this phase's refresh, do not rely on `pipeline.py`'s own staleness detection — run `python scripts/pipeline.py --target data --force` to force full regeneration regardless of the DAG's (buggy) incremental judgment. This is a sanctioned existing lever (`--force` flag), not a hand-patch of data, consistent with D-07. `scripts/data_release.py check-derived`'s live re-simulation check is unaffected by this bug (it doesn't use `pipeline.py`'s cache) and remains the reliable oracle regardless.
**Warning signs:** `python scripts/pipeline.py --target data --dry-run` reporting "up to date" or a small step count immediately after a `chapter_roll_overrides.json` edit, while `scripts/data_release.py check-derived` still reports predicted-rolls staleness — that divergence is this exact bug manifesting.

### Pitfall 3: `build_chapter_facts.py` fails fast on ANY hand-curated chapter whose stored `_fingerprint` no longer matches the current predicted-roll shape — and the fix tool must never be run with `--yes` blindly
**What goes wrong:** `build_chapter_facts.py`'s `main()` calls `chapter_alignment.fail_if_misaligned()` at startup, which raises `SystemExit` for any of the 118 curated chapters whose stamped `_fingerprint` (sha256 of that chapter's predicted-roll sequence at authoring time) disagrees with the freshly-recomputed one. New chapters appended at the end of the epub should not, in principle, shift earlier chapters' predicted-roll sequences — but the story source is periodically re-exported and earlier chapters occasionally get author edits (`chapter_facts.json` already tracks `last_edited_at`/`edited_lag_days` per chapter, confirming this happens), which CAN shift an earlier chapter's word-count/roll-shape and thus its fingerprint.
**Why it happens:** This is the pipeline's intentional drift-detection guard working as designed — it exists specifically to prevent silently trusting stale hand-curated data after upstream facts change.
**How to avoid:** If `chapter_alignment.py check` (or the `build_chapter_facts.py` failure) reports any mismatch post-refresh, run `scripts/realign_chapters.py` **interactively** (no `--yes`), which prints the stored-vs-current predicted-roll shape per chapter and requires an explicit `accept`/`skip`/`abort` choice per chapter. Per D-08, any mismatch should be treated as a `checkpoint:human-verify` item — the diagnosis (which chapters drifted and why) goes to Dre, not an automatic `--yes` re-stamp, since blindly accepting could paper over a real roll-structure change that invalidates that chapter's hand-curated evidence.
**Warning signs:** `build_chapter_facts.py` exiting non-zero with a message listing `ch X: stored=... current=...` — this is expected to be **rare or absent** if the refresh only appends new chapters (the common case for this workstream), but the plan must include a checkpoint task for the contingency, not assume it away.

### Pitfall 4: The ch 95.5 multi_grab failure is very likely a hand-curation data gap, not stale derived data — traced to a missing `mention_chapter_num` field
**What goes wrong:** `data_release.py check-derived`'s live re-simulation raises: `multi_grab override for ch 95.5 roll #0 references 'Minor Blessing Zeus – Lightning' but no obtained perk in the mechanical or mention chapter has that name (mechanical paid: ['arena', 'central control', 'gym', 'your robots']; mention_chapter_num: 95.5)`.
**Root-cause hypothesis (traced via direct code read, HIGH confidence in the mechanism, not yet confirmed against a fresh `obtained_perks.json`):** `chapter_roll_overrides.json`'s ch 95.5 entry has two roll objects. The first lists `perks: ["Minor Blessing Zeus – Lightning", "Unnatural Skill: Curses"]` with `mention_chapter_num: null` in the roll object itself (only its `evidence_quotes` carry `mention_chapter_num: "96"`). `load_overrides()` defaults a roll's top-level `mention_chapter_num` to the mechanical chapter (`"95.5"`) when null. `multi_grab.merge_paid_units()` then looks for "Minor Blessing Zeus – Lightning" among ch 95.5's *mechanically* obtained perks (via `_first_available(paid_global, mention_cn="95.5", ...)`) — not found, because ch 95.5's mechanical paid perks are exactly `['arena', 'central control', 'gym', 'your robots']` (which correctly matches the roll's *second* entry). The second roll's perks all resolve fine because they genuinely belong to ch 95.5 mechanically.
**Diagnosis to surface to Dre (per D-08):** the first roll's object likely needs an explicit `"mention_chapter_num": "96"` field (matching its evidence_quotes, which already say the author narrates this at ch96) so `merge_paid_units` looks in chapter 96's obtained-perk pool instead of 95.5's. **Do not add this field automatically without confirmation** — confirm against the refreshed `obtained_perks.json` first (verify "Minor Blessing Zeus – Lightning" and "Unnatural Skill: Curses" are indeed mechanically obtained in ch96, not 95.5) and get Dre's sign-off, per the phase's own D-08 checkpoint requirement.
**Warning signs:** After the refresh, if this exact error persists unchanged (same perk names, same chapter), that's strong confirmation this is a hand-curation gap unrelated to epub staleness — exactly the D-08 contingency the plan must have a checkpoint for.

### Pitfall 5: Test suite reads a point-in-time COPY of `data/`, not live edits — full pipeline regen is a hard precondition for the 24 failing tests, not a fixture fix
**What goes wrong:** `tests/conftest.py` copies `data/{raw,manual,derived}` into `tests/.tmp-data/data-<pid>/` once per test session and points `BCF_DATA_DIR` at the copy. The 24 currently-failing tests (`test_chapter_alignment_fingerprints.py`, `test_data_package_contract.py`, `test_forge_curator.py`, `test_model_validation.py`, `test_roll_ordinal_contract.py`, `test_roll_position_invariants.py`, `test_web_data_contract.py`) all read this snapshot via `scripts.data_paths.DERIVED`/`MANUAL`.
**Why it happens:** These are genuine data-consistency assertions against real local derived-data state, not flaky fixtures — they will only go green once `data/derived/*.json` in the actual working tree is regenerated fresh (confirming EPUB-02's success criterion is the literal, sole precondition).
**How to avoid:** Do not attempt to patch or special-case any of these 24 tests. Run the full refresh (Pitfall 2's `--force` regen) first; expect most/all to clear as a side effect. Re-run `pytest` (no path filter) as the actual verification step, matching what `scripts/verify.py` already does.
**Warning signs:** Any test still failing after a clean `--force` regen + `check-derived` green is a genuine new regression, not residual staleness — treat those as bugs requiring investigation.

## Code Examples

### Reading the 118-chapter corpus for mining (verified shape)
```python
# Source: data/manual/chapter_roll_overrides.json (this repo, read directly)
# Top-level keys: "_purpose", "association_review", "chapter_roll_overrides"
# chapter_roll_overrides: dict[chapter_num_str, {"rolls": [...], "_fingerprint": "sha256:..."}]
# Each roll object (verified field set from live data):
{
    "perks": ["Minor Blessing Zeus – Lightning", "Unnatural Skill: Curses"],  # [] for skipped/miss rolls
    "outcome": "hit",              # "hit" | "miss" | null
    "constellation": "Quality",
    "word_position": None,
    "mention_chapter_num": None,    # defaults to the mechanical chapter on load
    "mention_word_position": None,
    "display_position_policy": None,  # None | "mechanical" | "source_marker" | "mention" | "section_start" | "section_end"
    "skipped": False,
    "source_ordinal": None,
    "evidence_quotes": [
        {"text": "...", "mention_chapter_num": "96", "mention_word_position": 9134},
    ],
    "curator_note": None,
}
```
**Verified corpus statistics (this session, direct computation over live data — cite these or recompute fresh post-refresh):**
- 118 curated chapters (of 195 total local chapters as of this session; will grow post-refresh)
- Roll perks-per-roll shape distribution: `{0: 622, 1: 25, 2: 22, 3: 6, 4: 2, 5: 2, 7: 1, 8: 1}` (multi-grab up to 8 perks in one roll)
- `display_position_policy` explicit values: `{None: 598, "mechanical": 82, "source_marker": 1}` (None normalizes to `"mechanical"` on load per `multi_grab.load_overrides()`)
- Evidence quotes per roll: min 0, max 22, mean 1.27
- `cp_ledger_checkpoint` usage: 1 occurrence across the whole corpus (rare — document as such, don't over-index on it)

### Regime distribution over `chapter_facts.json` (verified this session)
```
regime 1: 128 chapters (ch 1 .. 91)
regime 2:  13 chapters (ch 92 .. 96.1)
regime 3:  54 chapters (ch 97 .. 120.2)   # includes the ch97 boundary chapter, tagged 3 due to Pitfall 1
```

### The manifest/staleness oracle (what actually gates green)
```python
# Source: scripts/data_release.py:check_local_derived_coherence (this repo, read directly)
# 1. Manifest sha256 check — every data/derived/data_package.json["files"][name]["sha256"]
#    must match a fresh hash of the on-disk file. ("perk_directory has stale sha256" comes
#    from here — cleared by re-running `scripts/data_release.py manifest` after the regen.)
# 2. Independent LIVE re-simulation — re-imports predict_rolls, re-runs predict_rolls._simulate()
#    with regime_simulator.load_regime_transitions(), and diffs the result against the stored
#    predicted_rolls.json byte-for-byte (via asdict() equality). ANY mismatch — including the
#    multi_grab ValueError bubbling up from merge_paid_units() — surfaces here as
#    "could not validate predicted_rolls.json freshness: <exception>".
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — this is the first exemplar-mining pass; no prior implementation exists | New `build_exemplar_index.py`/`query_exemplars.py` pair | This phase | Establishes the artifact Phase 2 (verifier) and Phase 3 (agent) will both consume as a schema contract |

**Deprecated/outdated:** None — the pipeline conventions this phase follows (`build_*` script shape, `pipeline.py` DAG, `data_release.py` manifest) are current and actively maintained; no legacy pattern to avoid here beyond the two bugs documented in Pitfalls 1–2.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The ch 95.5 multi_grab failure's root cause is a missing `mention_chapter_num: "96"` field on the first roll object (Pitfall 4) | Common Pitfalls, Pitfall 4 | If wrong, the checkpoint task investigates the wrong hypothesis first — low risk since D-08 already mandates human review before any fix, and the diagnosis is presented as a hypothesis to verify, not an applied fix |
| A2 | Fixing `build_chapter_facts.py`'s duplicate `regime_for_chapter` (Pitfall 1) is safe/desirable to do in this phase | Common Pitfalls, Pitfall 1 | Zero test coverage means the "fix" is unverified against any pinned expectation; recommend surfacing as an explicit plan decision (fix now with a new test, or defer with a documented Open Question) rather than assuming either way |
| A3 | Appending new chapters via epub refresh will not shift earlier chapters' predicted-roll fingerprints (i.e., `chapter_alignment.py check` mismatches will be rare/zero) | Common Pitfalls, Pitfall 3 | If wrong, the interactive `realign_chapters.py` review could involve more chapters than expected — plan should size the human-checkpoint task generously rather than assume zero mismatches |

**If this table is empty:** N/A — see entries above; all three are clearly flagged as hypotheses requiring live verification during execution, not locked facts.

## Open Questions (RESOLVED)

1. **Is Pitfall 1 (the `build_chapter_facts.py` regime duplicate) in-scope to fix in this phase, or a separate follow-up?**
   - What we know: It's a verified, currently-silent bug that directly affects the `point_calculation_regime` field D-01 designates as ground truth for the exemplar index's regime tags on ch97.
   - What's unclear: Whether fixing it (importing from `regime_simulator` instead of the local duplicate) has any downstream ripple (e.g., does any other consumer of `chapter_facts.json` implicitly rely on ch97 reading `3` rather than `2`?) — untested territory.
   - Recommendation: The plan should include a small, isolated investigation task (grep all consumers of `point_calculation_regime`, check test expectations) before deciding fix-now vs. defer; Pattern 3's recipe already works around the bug regardless of this decision, so the exemplar index's own correctness does not depend on this question being resolved.
   - **Resolution:** Deferred out of scope for this phase — 01-03-PLAN.md Task 1's action explicitly documents the fix as "a candidate follow-up (RESEARCH.md Open Question 1), not a requirement of CINF-02, and is deliberately not undertaken in this phase," relying instead on Pattern 3's `regime_simulator.regime_for_chapter()`-based recipe so the exemplar index's ch97 tagging is correct regardless.

2. **How many chapters, if any, will `chapter_alignment.py check` flag after the refresh?**
   - What we know: The guard only fires on genuine predicted-roll-shape drift for already-curated chapters; appending new chapters at the story's end should not, in principle, affect it.
   - What's unclear: Whether the specific two-months-newer epub re-export corrected any earlier chapter's text in a way that shifts word counts.
   - Recommendation: Treat as unknown until the refresh actually runs; the plan should have a `checkpoint:human-verify` task sized to "0 to a handful of chapters," using `scripts/realign_chapters.py` interactively (never `--yes`) as the resolution mechanism.
   - **Resolution:** Handled by 01-02-PLAN.md Task 2 — a `checkpoint:human-verify` that auto-clears on zero mismatches or, for one-or-more mismatched chapters, requires Dre's explicit interactive accept/skip/abort per chapter via `scripts/realign_chapters.py` (never `--yes`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `gh` CLI (authenticated) | `sync_private_source_repo.py`'s clone/push to the private GitHub repo | ✓ | logged in as `deinspanjer`, ssh protocol | — |
| Network access to `fichub.net` | `sync_private_source_repo.py --download` / `download_bcf_epub.py` (fetching the newest epub export) | ✓ | HTTP 200 confirmed this session | — |
| `.venv` Python | All pipeline scripts, `pytest` | ✓ | 3.14.4 | — |
| `data/private-source/` clone | Source-of-truth for the "newest release" comparison (EPUB-01/D-09) | ✓ (already cloned; last synced `source-v20260516.1`, 2026-05-15, 195 ch/120.2) | — | — |
| Local `data/raw/*.epub` | Fallback source for `hydrate_source_epub.py` if private-source is unavailable | ✓ (5.7M, present) | — | Already the sanctioned two-tier selection (`select_source_epub` prefers private-source, falls back to raw) |

**Missing dependencies with no fallback:** None identified.

**Missing dependencies with fallback:** None identified — all required tooling is present and working in this checkout.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (project-pinned via `pyproject.toml`; `.venv` provisioned) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `addopts = "-q"` |
| Quick run command | `.venv/bin/python -m pytest tests/test_chapter_roll_overrides.py tests/test_pipeline.py -q` (targeted, once the new build script + its unit tests exist) |
| Full suite command | `.venv/bin/python scripts/verify.py` (runs `git diff --check` → `check-derived` → full `pytest`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EPUB-01 | Post-hydrate chapter count/nav reflect newest release | unit/script | New test asserting `hydrate_source_epub.hydrate_source_epub()["chapter_count"]` and `last_chapter_num` exceed the pre-refresh baseline (195/"120.2") | ❌ Wave 0 — new test file or addition to `tests/test_source_epub_hydration.py` |
| EPUB-02 | Full pipeline re-run green (predicted rolls extend, curated chapters validate, `visualization_facts.json` rebuilds) | integration | `.venv/bin/python scripts/verify.py` (existing) | ✅ already exists — this phase must make it pass, not write it |
| CINF-02 | Exemplar index tagged by regime; same-regime retrieval; ch97 dual-tagged | unit | New `tests/test_build_exemplar_index.py` (or similarly named) asserting: (a) every curated chapter appears with correct regime tag(s), (b) ch97 specifically carries `{2, 3}` + boundary flag, (c) `query_exemplars.retrieve(target, index)` never returns a cross-regime exemplar | ❌ Wave 0 — new test file |

### Sampling Rate
- **Per task commit:** targeted pytest on the new/touched test files
- **Per wave merge:** `.venv/bin/python scripts/verify.py` (full suite + check-derived)
- **Phase gate:** Full `scripts/verify.py` green before `/gsd-verify-work` — this is the phase's own definition of done per CONTEXT.md's Specifics section

### Wave 0 Gaps
- [ ] `tests/test_build_exemplar_index.py` — covers CINF-02 (regime tagging, boundary dual-tag, index schema shape, statistics correctness against the known corpus counts above)
- [ ] `tests/test_query_exemplars.py` (or folded into the above) — covers the same-regime retrieval constraint (D-06's required test)
- [ ] Extension to `tests/test_source_epub_hydration.py` (or new file) — covers EPUB-01's mechanical "newest release" verification (D-09)
- [ ] Framework install: none — pytest already present and configured

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This phase has no auth surface — `gh` CLI auth is pre-existing developer tooling, out of this phase's change scope |
| V3 Session Management | No | N/A — no sessions |
| V4 Access Control | No | N/A — single-developer local tooling, no multi-user access model |
| V5 Input Validation | Yes | `hydrate_source_epub.py` already validates manual-data chapter references against parsed nav entries (`validate_manual_chapter_references`) and raises on drift; the new exemplar-index build script should validate its inputs the same way existing `build_*` scripts do (assert expected keys present, fail loudly on shape mismatch) rather than silently coercing malformed entries |
| V6 Cryptography | No | sha256 usage here is for content-addressing/staleness detection (integrity, not confidentiality) — already the established pattern (`hashlib.sha256`), not a new crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/oversized epub ingested from an external aggregator (FicHub) into local processing (`zipfile.ZipFile`, `xml.etree.ElementTree.fromstring` on `nav.xhtml`) | Tampering / DoS | Low risk given the source is a long-trusted, developer-selected, gitignored private input, not an untrusted multi-tenant upload path. `xml.etree.ElementTree` does not resolve external entities by default (no XXE by default in Python's expat-backed parser), and epub files here are small (~6MB) with no observed zip-bomb concern. No new mitigation needed beyond what already exists; worth a one-line note in the new script's docstring that inputs are developer-trusted, not adversarial |
| A hand-curated JSON file (`chapter_roll_overrides.json`) with an unexpected shape crashing the new build script ungracefully | Tampering (data integrity) | Follow the existing pattern of loud, early `raise ValueError`/`SystemExit` on unexpected shape (as `multi_grab.py`'s `_normalise_roll_entry` already does) rather than silent coercion — this is a correctness control, not a security control per se, but protects the trust guarantee (agent/tooling never silently reinterprets malformed hand-curated data) |

## Sources

### Primary (HIGH confidence — direct codebase inspection this session)
- `scripts/sync_private_source_repo.py`, `scripts/hydrate_source_epub.py` — epub refresh mechanics, current local sync state (`source-v20260516.1`)
- `scripts/pipeline.py` — DAG structure, `TARGET_FINAL_STEPS`, staleness detection logic, the `multi_grab_overrides.json` input-declaration bug
- `scripts/data_release.py` — manifest schema, `check_local_derived_coherence`, `_check_predicted_rolls_fresh` (the live re-simulation oracle)
- `scripts/chapter_alignment.py`, `scripts/realign_chapters.py` — fingerprint-drift guard and its sanctioned interactive resolution tool
- `scripts/regime_simulator.py`, `scripts/build_chapter_facts.py` — regime computation, the verified duplicate-function bug (Pitfall 1)
- `scripts/multi_grab.py` — exact code path producing the ch 95.5 error (Pitfall 4's root-cause trace)
- `scripts/derive_outstanding_perks.py` — the `build_*` script skeleton to model the new script after
- `scripts/verify.py`, `tests/conftest.py`, `pyproject.toml` — verification gate composition and test-data-isolation mechanics
- `data/manual/chapter_roll_overrides.json`, `data/manual/regime_transitions.json` — live corpus shape/statistics computed directly this session
- `data/derived/chapter_facts.json`, `data/derived/obtained_perks.json`, `data/derived/chapters.json` — live regime distribution, chapter counts (195 through ch120.2), obtained-perk data
- `data/private-source/Brocktons_Celestial_Forge.metadata.json` — confirms last sync date/version tag
- Local `gh auth status`, `.venv/bin/python --version`, `curl -I fichub.net` — environment availability checks run this session

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` (Part B, this project's milestone-level research) — corroborates the exemplar-index architecture and regime-tagging design independently arrived at here; note it suggested `data/manual/agent_curation_exemplars.json` as a possible location, which CONTEXT.md's locked D-03 supersedes (derived artifact in `data/derived/`, not manual)
- `.planning/research/PITFALLS.md` (Pitfalls 9, 10) — corroborates the regime-boundary exemplar-scarcity concern and the ch97/Nano-Forge example independently

### Tertiary (LOW confidence)
- None — no unverified WebSearch-only claims in this research; this phase's domain is entirely internal to the codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, pure verification of existing local environment
- Architecture: HIGH — directly traced through `pipeline.py`, `data_release.py`, `chapter_alignment.py` source code, cross-checked against live local data
- Pitfalls: HIGH — all five pitfalls are verified via direct code tracing and/or live-data computation this session, not inferred from general pattern knowledge

**Research date:** 2026-07-26
**Valid until:** Short shelf life for the *specific data facts* (chapter counts, sync date, corpus statistics) — these will change the moment the refresh runs; treat this document's data snapshots as "state observed pre-refresh" baselines for comparison, not as post-refresh expectations. The *code-path* findings (Pitfalls 1–5, architecture patterns) remain valid until the underlying scripts change (no fast-moving external dependency; estimate 60 days for the code-path claims, 0 days / one-time for the data snapshots).
