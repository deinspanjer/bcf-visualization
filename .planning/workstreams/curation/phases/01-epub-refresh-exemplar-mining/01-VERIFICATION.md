---
phase: 01-epub-refresh-exemplar-mining
verified: 2026-07-27T00:00:00Z
status: passed
score: 6/8 must-haves verified (2 accepted via override)
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "All previously curated chapters still validate / scripts/verify.py exits 0"
    reason: "Chapter 104 requires a manual curator-TUI edit (2 curated hits vs 1 predicted slot) before it can be safely re-stamped; the 5 remaining pytest failures are pre-existing Track B debt (chapter 79 TUI fixtures, chapter 55.1/56/57 roll-ordinal contract) unrelated to this phase's epub-refresh/exemplar-mining scope and reduced from 24 to 5 by this phase's work."
    accepted_by: "Dre"
    accepted_at: "2026-07-27T00:00:00Z"
    accepted_context: "Answered the seal-or-hold gate during /gsd-execute-phase 1 --auto; chose 'Seal with documented gaps', unblocking the Phase 2-4 hard gate. Both gaps remain tracked in deferred-items.md."
gaps:
  - truth: "All previously curated chapters still validate after the full pipeline force-regen (ROADMAP Phase 1 Success Criterion 2)"
    status: failed
    reason: "scripts/chapter_alignment.py check reports exactly 1 mismatch: chapter 104's stored _fingerprint disagrees with the freshly-regenerated predicted-roll shape (independently re-run this session, output confirmed: 'ch 104: stored=sha256:161e5abc1b8f878c current=sha256:5a2fe49d8482f0ea', exit 1). This is a deliberate, human-reviewed carve-out — Dre explicitly chose to skip re-stamping ch104 at an interactive checkpoint:human-verify in Plan 01-02 Task 2, because its 2 curated hit rolls exceed the model's 1 predicted slot (a real capacity mismatch, not just a stale hash) and a plain re-stamp would silently paper over it. It is documented in deferred-items.md and 01-02-SUMMARY.md, not hidden — but it means the literal truth 'all previously curated chapters still validate' is not met."
    artifacts:
      - path: "data/manual/chapter_roll_overrides.json"
        issue: "Chapter 104's _fingerprint is deliberately stale pending a curator-TUI edit to reconcile its rolls array (2 curated hits vs. 1 predicted slot)"
    missing:
      - "Dre's manual curator-TUI review and edit of chapter 104's rolls array, followed by a fingerprint re-stamp via scripts/realign_chapters.py (interactive, never --yes)"
  - truth: "Full pipeline re-run completes green (scripts/verify.py exits 0) — ROADMAP Phase 1 Success Criterion 2 / EPUB-02 / plan 01-02 and 01-04 must_haves"
    status: failed
    reason: "Independently re-ran scripts/verify.py this session: git diff --check passes, data_release.py check-derived passes ('local derived data ok'), but the full unfiltered pytest run reports 5 failed, 587 passed (exit 1 overall). Confirmed the exact same 5 failures documented across 01-02/01-03/01-04-SUMMARY.md: test_forge_curator.py::test_stats_click_selects_actual_visible_roll_line, test_forge_curator.py::test_stats_click_refocuses_prose_for_motion_and_space_chords, test_forge_curator.py::test_stats_click_jumps_prose_to_selected_roll_location, test_forge_curator.py::test_click_roll_then_space_p_opens_perk_picker_for_selected_roll, and test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction. Cross-referenced against the mobile-ux workstream's pre-existing 24-failure baseline (test_chapter_alignment_fingerprints.py 1, test_data_package_contract.py 1, test_forge_curator.py 4, test_model_validation.py 5, test_roll_ordinal_contract.py 9, test_roll_position_invariants.py 2, test_web_data_contract.py 1 — documented BEFORE this phase began, in .planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/deferred-items.md): independently confirmed zero failures now occur in test_chapter_alignment_fingerprints.py, test_data_package_contract.py, test_model_validation.py, test_roll_position_invariants.py, or test_web_data_contract.py (all 5 of those files are fully green in my own run). The 5 remaining failures are an exact subset of the pre-existing 13 in the two files that still have failures (test_forge_curator.py: unchanged at 4; test_roll_ordinal_contract.py: down from 9 to 1). No new failure signatures were introduced. This is a genuine, substantial improvement (24→5) documented honestly by the phase's own SUMMARYs rather than silently forced green, but the literal must-have ('scripts/verify.py exits 0') is not met."
    artifacts:
      - path: "tests/test_forge_curator.py"
        issue: "4 chapter-79 TUI stats-panel fixture tests fail (StopIteration looking for '# 2 (R520/P548)') — pre-existing, unrelated to this phase's epub-refresh/exemplar-mining work"
      - path: "tests/test_roll_ordinal_contract.py"
        issue: "1 test (chapter 55.1/56/57 roll-ordinal contract) fails — pre-existing curation-data staleness in a part of the corpus this phase did not touch"
    missing:
      - "Root-cause fix for the chapter-79 TUI fixture staleness and the chapter 55.1/56/57 roll-ordinal mismatch — both pre-date this phase and are explicitly out of its scope per deferred-items.md, but scripts/verify.py will not exit 0 until they are resolved"
---

# Phase 1: Epub Refresh & Exemplar Mining Verification Report

**Phase Goal:** The pipeline reflects the newest released chapters, and the hand-curated corpus is characterized well enough to teach an agent
**Verified:** 2026-07-27
**Status:** gaps_found
**Re-verification:** No — initial verification

**Note on ROADMAP mode:** This phase's ROADMAP.md entry carries `Mode: mvp`, but its Goal text ("The pipeline reflects the newest released chapters, and the hand-curated corpus is characterized well enough to teach an agent") is not phrased as a `As a ..., I want ..., so that ....` user story — it is a technical/infrastructure goal with 4 enumerated, testable success criteria. This verification therefore applies the standard goal-backward methodology against those 4 success criteria (and each plan's own `must_haves`) rather than the MVP user-flow-coverage format, since there is no user-outcome clause to narrow to.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | (SC1/EPUB-01) Private-source flow yields an epub whose chapter count/nav entries reflect the newest release | ✓ VERIFIED | Independently ran `.venv/bin/python scripts/verify_epub_freshness.py` — exit 0, `fresh: hydrated source EPUB matches private-source clone (chapter_count=198, last_chapter_num=121.1)`. Confirmed `data/private-source/Brocktons_Celestial_Forge.metadata.json` independently: `count: 198`, `last_chapter_friendly_number: "121.1"`, `version_tag: source-v20260726.1`. |
| 2 | (Backstop, plan 01-01) The hydrated epub is byte-identical (sha256) to the private-source clone's epub | ✓ VERIFIED | `sha256sum` on both files, run directly this session: `data/raw/Brocktons_Celestial_Forge.epub` and `data/private-source/Brocktons_Celestial_Forge.epub` both hash to `d5f73c536f10a97535d3240e075692aa8b72696f235d4737a1062b261dd0ffc2`. |
| 3 | (SC2, part A) Predicted rolls extend into the new chapters and `visualization_facts.json` rebuilds | ✓ VERIFIED | Independently re-ran `.venv/bin/python scripts/pipeline.py --target data --force` end-to-end this session: exit 0, log shows `RUN build_visualization_facts` and `RUN build_exemplar_index` completing; `data/derived/chapters.json` re-checked: 198 chapters, last `chapter_num: "121.1"` (exceeds the pre-refresh baseline of 195/`120.2`). |
| 4 | (SC2, part B) All previously curated chapters still validate | ✗ FAILED | `.venv/bin/python scripts/chapter_alignment.py check` (re-run this session) reports exactly 1 mismatch: chapter 104. This is a deliberate, Dre-reviewed carve-out (see Gaps below), not an oversight, but the truth as literally stated is not met. |
| 5 | (SC2, part C / EPUB-02) `scripts/verify.py` exits 0 (full pipeline "completes green") | ✗ FAILED | Independently re-ran `.venv/bin/python scripts/verify.py` this session: `git diff --check` passes, `check-derived` passes ("local derived data ok"), full pytest reports **5 failed, 587 passed**, overall exit 1. See Gaps below for full analysis of whether these are regressions (they are not). |
| 6 | (SC3/CINF-02) Exemplar index tagged by CP regime; retrieval returns only same-regime exemplars | ✓ VERIFIED | Live-inspected `data/derived/exemplar_index.json`: 118/118 curated chapters present (exact set match against `chapter_roll_overrides.json`'s keys), ch97 `regime_tags: [2, 3]`, `is_boundary: true`. Ran `scripts.query_exemplars.retrieve()` live against the real index for regimes 1/2/3: zero cross-regime leaks in any of the 101+9+9 = 119 returned entries (ch97 counted twice, once per regime); ch97 confirmed returned for both regime=2 and regime=3 queries. `tests/test_build_exemplar_index.py` + `tests/test_query_exemplars.py` (14 tests) pass. |
| 7 | (SC4/CINF-02) Index documents corpus's evidence-quote patterns, roll-shape distribution, perk-link conventions | ✓ VERIFIED | `corpus-analysis-report.md` (204 lines) exists with all 6 required sections (Overview, Roll-Shape Distribution, Evidence-Quote Patterns, cp_ledger_checkpoint Usage, Perk-Link/Naming Conventions, Regime-Boundary Handling). All numeric tables cross-checked against a live rebuild of `exemplar_index.json`'s `statistics` block (identical). The one illustrative quote ("the Magitech constellation passed by") verified verbatim in `data/manual/chapter_roll_overrides.json` (4 matches via grep). No epub read in the report-authoring script or report text. |
| 8 | (Prohibitions, all 4 plans) No unapproved hand-curated data edits, no new epub download path, no LLM/Anthropic calls, no second regime-computation implementation, no epub prose leakage | ✓ VERIFIED | See detailed prohibition-by-prohibition evidence below. |

**Score:** 6/8 truths verified (2 present-but-not-fully-met, both documented deliberate/pre-existing gaps, not silent regressions)

### EPUB-02 Explicit Assessment (per verification brief)

**"A full pipeline re-run completes green: predicted rolls extend into the new chapters, all previously curated chapters still validate, and `visualization_facts.json` rebuilds"** — **PARTIALLY MET.**

- Predicted rolls extend into new chapters: **MET** (198 chapters through 121.1, independently reproduced this session).
- `visualization_facts.json` rebuilds: **MET** (confirmed in the live pipeline run).
- All previously curated chapters still validate: **NOT MET** — chapter 104 is a known, single exception, deliberately left stale by Dre's own interactive decision (not an executor shortcut). No other chapter is affected; 100/109/112/114 (which showed the same drift class) were reviewed and re-stamped.
- `scripts/verify.py` exits 0: **NOT MET** — 5 pytest failures remain. Independently confirmed these are a strict subset of the ~23-24 failures documented as pre-existing *before this phase began* (in the mobile-ux workstream's Phase 1 `deferred-items.md`), and that 5 of the 7 previously-failing test files are now fully green. No evidence this phase's own changes introduced any new failure — every remaining failure traces to either (a) chapter 79 TUI fixture data untouched by this phase's commits, or (b) chapter 55.1/56/57 roll-ordinal data untouched by this phase's commits. **I did not find any indication the phase's own work caused these 5 failures**; they pre-date it.

Both remaining gaps are honestly documented in the phase's own artifacts (`deferred-items.md`, `01-02-SUMMARY.md`, `REQUIREMENTS.md` itself already annotates EPUB-02 as "Complete (with documented gap)"). This is a materially different situation from a silently-swept failure — but per this verifier's job to check the literal ROADMAP success criterion against the codebase, not to accept narrative claims, the criterion as literally worded is not fully satisfied today.

**This looks intentional and already human-reviewed.** If Dre accepts chapter 104's stale anchor and the 5 pre-existing Track B failures as out of this phase's scope (consistent with REQUIREMENTS.md's own "Complete (with documented gap)" annotation), add to this VERIFICATION.md's frontmatter:

```yaml
overrides:
  - must_have: "All previously curated chapters still validate / scripts/verify.py exits 0"
    reason: "Chapter 104 requires a manual curator-TUI edit (2 curated hits vs 1 predicted slot) before it can be safely re-stamped; the 5 remaining pytest failures are pre-existing Track B debt (chapter 79 TUI fixtures, chapter 55.1/56/57 roll-ordinal contract) unrelated to this phase's epub-refresh/exemplar-mining scope and reduced from 24 to 5 by this phase's work."
    accepted_by: "Dre"
    accepted_at: "<ISO timestamp>"
```

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/verify_epub_freshness.py` | Mechanical D-09 freshness check, pure function + CLI | ✓ VERIFIED | Exists, substantive (91 lines), wired (imported by its own tests, invoked directly this session with exit 0), data flows from real `source.json`/`metadata.json` files. |
| `tests/test_source_epub_hydration.py` | Regression tests for freshness/staleness | ✓ VERIFIED | 10 tests pass (`.venv/bin/python -m pytest tests/test_source_epub_hydration.py -q`, re-run this session). |
| `data/derived/chapters.json` | 198 chapters through 121.1 after force-regen | ✓ VERIFIED | Re-generated live this session; count=198, last=`121.1`. |
| `scripts/build_exemplar_index.py` | `build_index()` + `main()`, regime-tagging + statistics | ✓ VERIFIED | Exists (339 lines), substantive, imports `regime_for_chapter` from `scripts.regime_simulator` only (no local re-definition — confirmed via grep), never opens the epub (confirmed via grep), wired into `scripts/pipeline.py`'s DAG (confirmed via live run: `RUN build_exemplar_index` executes and writes the file). |
| `scripts/query_exemplars.py` | `retrieve()` deterministic same-regime filter | ✓ VERIFIED | Exists (101 lines), substantive, pure function with no file I/O in the retrieval path, live-tested against the real index this session — zero cross-regime returns. |
| `data/derived/exemplar_index.json` | Regime-tagged corpus + statistics, `schema_version` | ✓ VERIFIED | Exists, `schema_version: 1`, 118 exemplars (exact match to curated chapter set), statistics block present and matches the report. |
| `.../corpus-analysis-report.md` | Human-readable corpus characterization, ≥40 lines | ✓ VERIFIED | 204 lines, all 6 required sections present, sourced from the index's statistics block (spot-checked several numbers against a live rebuild — identical), no epub prose. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scripts/verify_epub_freshness.py` | `data/raw/*.source.json` + `data/private-source/*.metadata.json` | Field comparison | ✓ WIRED | Confirmed by direct code read and live invocation. |
| `scripts/pipeline.py --target data --force` | `scripts/predict_rolls.py` → `scripts/multi_grab.merge_paid_units` | Subprocess DAG | ✓ WIRED | Confirmed: full regen completes with only the expected informational `multi_grab: ch 95 override drops...` warning, no exception. |
| `scripts/build_exemplar_index.py` | `scripts/regime_simulator.regime_for_chapter` | Import | ✓ WIRED | Confirmed via `grep`: `from regime_simulator import regime_for_chapter` (with fallback `from scripts.regime_simulator import ...`). No second definition anywhere in the new file. Note: a pre-existing, out-of-scope duplicate `regime_for_chapter` already exists in `scripts/build_chapter_facts.py` (documented in RESEARCH.md Pitfall 1, not introduced by this phase, not touched by it either) — this phase did not add a THIRD implementation. |
| `scripts/pipeline.py` | `scripts/build_exemplar_index.py` | New `Step` + `TARGET_FINAL_STEPS["data"]` | ✓ WIRED | Confirmed: `Step(name="build_exemplar_index", ...)` present, `TARGET_FINAL_STEPS["data"] == ("build_visualization_facts", "build_exemplar_index")`; live pipeline run executes it; `tests/test_pipeline.py`'s 14-step `DATA_STEP_NAMES` list and "14 step(s)" dry-run string both pass. |
| `scripts.query_exemplars.retrieve` | `data/derived/exemplar_index.json` | Reads loaded dict's `regime_tags` | ✓ WIRED | Confirmed via live invocation against the real on-disk index. |
| `data/derived/exemplar_index.json` | Dev-derived bundle manifest (D-03 registration) | `data_release.build_manifest(bundle_class="dev-derived")` | ✓ WIRED | Directly invoked `build_manifest(...)` this session (correct kwargs, not the stale on-disk `_dev_data_package.json` which predates this phase and is unrelated — it's a separate GitHub-release-download artifact): `files['exemplar_index'] == {'path': 'exemplar_index.json', 'schema': 'exemplar_index', 'schema_version': 1, ...}`. Confirmed the phase's own architectural decision (exemplar_index.json deliberately excluded from the `pages-runtime` `data_package.json` to avoid shipping a curation artifact into the production webapp bundle) is real and intentional, not a workaround for a broken check. |

### Prohibitions (must_haves.prohibitions across all 4 plans)

| Prohibition | Status | Evidence |
|---|---|---|
| MUST NOT silently edit `chapter_roll_overrides.json` without an explicit Dre-approved checkpoint (01-01) | ✓ NOT VIOLATED | `git show 1a2c9da` — single field edit (`mention_chapter_num: null → "95"`), commit message cites the checkpoint decision. |
| MUST NOT fetch/hydrate the epub via any path other than the sanctioned sync→hydrate flow (01-01) | ✓ NOT VIOLATED | None of this phase's 12 commits touch `scripts/sync_private_source_repo.py` or `scripts/hydrate_source_epub.py` (checked via `git show --stat` on every phase commit). Pre-existing FicHub-download code in those files predates this phase and was not exercised or modified by it. |
| MUST NOT make any LLM/Anthropic API call anywhere in this phase's scripts (01-01) | ✓ NOT VIOLATED | `grep -rn "anthropic\|Anthropic\|messages.create"` across all new scripts returns nothing. |
| MUST NOT run `realign_chapters.py --yes` (01-02) | ✓ NOT VIOLATED | 01-02-SUMMARY documents the interactive session; the resulting commit (`cc84f84`) shows exactly 4 fingerprint-line changes (100/109/112/114), consistent with a per-chapter interactive accept, not a bulk `--yes` run. |
| MUST NOT force a "green" verify.py by skipping/deleting/xfail-ing tests (01-02) | ✓ NOT VIOLATED | No test files were modified to skip/xfail anything (checked `git show --stat` for all 12 phase commits — no `tests/` file appears in any commit touching `data/manual/` or pipeline code). The 5 remaining failures were left failing and documented, not silenced. |
| MUST NOT hand-patch `data/derived/*.json` directly (01-02) | ✓ NOT VIOLATED | All derived-data changes came from live pipeline/manifest script runs (independently reproduced this session), not hand edits — `data/derived/` is gitignored and not part of any commit diff. |
| MUST NOT read the epub or epub prose from any new script/test in plan 01-03 | ✓ NOT VIOLATED | `grep -n "epub" scripts/build_exemplar_index.py scripts/query_exemplars.py` returns only a docstring line stating the script *never* opens the epub. |
| MUST NOT define a second `regime_for_chapter` (01-03) | ✓ NOT VIOLATED | Exactly 2 definitions exist repo-wide: `scripts/regime_simulator.py` (canonical, imported by the new code) and `scripts/build_chapter_facts.py` (pre-existing, documented, unfixed bug, not touched this phase). No third. |
| MUST NOT use any word-count field other than `cp_earning_word_count` if computed (01-03) | ✓ NOT VIOLATED | `build_exemplar_index.py` computes no word-count figure at all. |
| MUST NOT quote/paraphrase epub prose in `corpus-analysis-report.md` beyond existing `evidence_quotes[].text` (01-04) | ✓ NOT VIOLATED | The report's one illustrative quote verified verbatim (4 exact matches via grep) in `chapter_roll_overrides.json`. |
| MUST NOT report the phase green without pasting `scripts/verify.py`'s actual output (01-04) | ✓ NOT VIOLATED | Every SUMMARY pastes the real 5-failure/587-pass output; none claim exit 0. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| EPUB-01 | 01-01 | Epub reflects newest release (chapter count/nav) | ✓ SATISFIED | Truth #1/#2 above. |
| EPUB-02 | 01-02 | Full pipeline re-run completes green | ⚠️ PARTIALLY SATISFIED | See EPUB-02 Explicit Assessment above — 2 of 4 sub-criteria not literally met, both documented, pre-existing/deliberate, non-regressive. |
| CINF-02 | 01-03, 01-04 | Regime-tagged exemplar corpus + same-regime retrieval + characterization | ✓ SATISFIED | Truths #6/#7 above. |

No orphaned requirements: the phase's declared requirement IDs (EPUB-01, EPUB-02, CINF-02 across the 4 plans) exactly match the 3 requirement IDs assigned to Phase 1 in `REQUIREMENTS.md`.

### Anti-Patterns Found

None. Scanned all new/modified files in this phase (`scripts/verify_epub_freshness.py`, `scripts/build_exemplar_index.py`, `scripts/query_exemplars.py`, `scripts/pipeline.py`, `tests/test_source_epub_hydration.py`, `tests/test_build_exemplar_index.py`, `tests/test_query_exemplars.py`, `tests/test_pipeline.py`, `corpus-analysis-report.md`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER`/"not yet implemented" — zero matches.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Epub freshness check | `.venv/bin/python scripts/verify_epub_freshness.py` | `fresh: ... (chapter_count=198, last_chapter_num=121.1)`, exit 0 | ✓ PASS |
| Full pipeline force-regen | `.venv/bin/python scripts/pipeline.py --target data --force` | Completes end-to-end, exit 0, writes `exemplar_index.json` last | ✓ PASS |
| Chapter alignment check | `.venv/bin/python scripts/chapter_alignment.py check` | 1 mismatch (ch 104), exit 1 | ✓ PASS (matches documented, expected state) |
| Full verification gate | `.venv/bin/python scripts/verify.py` | git diff --check pass, check-derived pass, pytest 5 failed/587 passed, exit 1 | ✓ PASS (matches documented, expected state — not a surprise) |
| Same-regime retrieval invariant | Direct `retrieve()` calls for regimes 1/2/3 against the live index | Zero cross-regime leaks; ch97 returned for both regime 2 and 3 | ✓ PASS |
| Exemplar index coverage | Direct Python set-comparison of index chapters vs. overrides chapters | Exact match, 118/118 | ✓ PASS |
| Byte-identical epub | `sha256sum` on both epub files | Identical hash | ✓ PASS |
| Verbatim evidence quote | `grep` for the report's illustrative quote in `chapter_roll_overrides.json` | 4 matches found | ✓ PASS |

### Human Verification Required

None triggered by the standard decision tree (no truth is UNCERTAIN or behavior-unverified) — the two failing truths are FAILED with clear, reproducible evidence, not ambiguous. However, a **human decision** is appropriate on one point that this verifier cannot resolve unilaterally:

1. **Is the documented EPUB-02 gap (chapter 104 + 5 pre-existing Track B pytest failures) acceptable as this phase's final state, unblocking the Phase 2–4 hard gate?**
   - What to review: `deferred-items.md`'s two entries dated 2026-07-26 (ch104 skip rationale; 5-failure triage), plus this report's "EPUB-02 Explicit Assessment" section.
   - Why human: This is a project-authority decision (curation-authority rule: only Dre approves deviations from hand-curated data / acceptance of known test debt), not a mechanically-verifiable fact — the mechanical facts (5 failures, 1 alignment mismatch, both pre-existing and non-regressive) are already conclusively established above.
   - If accepted: add the override block shown in the EPUB-02 Explicit Assessment section above and re-run verification; status would become `passed`.

### Gaps Summary

Of the phase's 3 requirements (EPUB-01, EPUB-02, CINF-02), 2 are fully, mechanically satisfied (EPUB-01, CINF-02) and independently reproduced this session with fresh command output — not merely trusted from SUMMARY.md prose. EPUB-02 is **partially met**: the pipeline demonstrably reflects the epub refresh (198 chapters, `visualization_facts.json` rebuilds), but the literal "all previously curated chapters still validate" and "`scripts/verify.py` exits 0" clauses are not true today. Both gaps are the result of deliberate, already-documented, human-reviewed decisions during Plan 01-02 (not executor shortcuts, and not something this phase's own commits caused) — chapter 104 needs a manual curator-TUI edit before its fingerprint can be safely re-stamped, and 5 pre-existing Track B pytest failures (unrelated to epub refresh or exemplar mining, tracing to chapter-79 TUI fixtures and chapter 55.1/56/57 data) remain out of this phase's stated scope. This phase's own work reduced the Track B failure count from ~23-24 (documented before this phase started) to 5 — a genuine, verified improvement, not a regression — but did not eliminate it entirely, and the ROADMAP's literal wording ("all previously curated chapters still validate") is not satisfied while chapter 104 remains unresolved.

Recommendation: either (a) Dre completes the chapter 104 curator-TUI edit and the Track B debt is separately tracked/fixed before treating Phase 1 as fully closed, or (b) Dre explicitly accepts this as the phase's final state via the override suggested above, in which case Phase 1 can be considered `passed` and the Phase 2–4 hard gate unblocked with this residual debt tracked forward (as `REQUIREMENTS.md` already frames it: "Complete (with documented gap)").

---

*Verified: 2026-07-27*
*Verifier: Claude (gsd-verifier)*
