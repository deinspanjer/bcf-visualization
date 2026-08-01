---
phase: 02-mechanical-verifier
verified: 2026-08-01T18:37:01Z
status: passed
score: 4/4 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 2: Mechanical Verifier Verification Report

**Phase Goal:** Any candidate curation can be judged true or false by deterministic code, with the hand-curated corpus as its proof of correctness
**Verified:** 2026-08-01T18:37:01Z
**Status:** passed
**Re-verification:** No — initial verification

All checks below were reproduced independently in this session (not taken from SUMMARY.md claims): the verifier CLI was run fresh, the corpus-baseline test was collected and run, `find_text_backed_rolls.py` was regenerated and diffed, the full pytest suite was run, and the source of `scripts/mechanical_verifier.py`/`scripts/cp_word_index.py` was read line-by-line against each locked decision (D-01..D-13).

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Verifier scores 100% over every hand-curated chapter — a failure means the verifier is wrong, not the corpus | ✓ VERIFIED | Independently ran `.venv/bin/python scripts/mechanical_verifier.py`: `pass: 591, no_evidence: 90, fail: 0` across 681 rolls / 118 chapters, reproduced byte-for-byte against the SUMMARY's claimed numbers. Independently verified all 90 `no_evidence` rolls genuinely have empty `evidence_quotes` (zero mismatches against `chapter_roll_overrides.json`), and no `pass` status silently hides a quote-less roll. `git log -- data/manual/chapter_roll_overrides.json` shows no Phase-2 commit — the corpus was never edited to force a pass (D-08 honored). |
| 2 | Verifier accepts only exact/whitespace-normalized quote matches, rejects paraphrase; no fuzzy matching path exists (structural property) | ✓ VERIFIED | `grep -rn "rapidfuzz\|difflib\|SequenceMatcher\|get_close_matches" scripts/mechanical_verifier.py scripts/cp_word_index.py scripts/find_text_backed_rolls.py` returns zero hits. Read `_verify_quote`/`_build_tier2_pattern` in full: Tier 1 is `re.escape`d exact substring search; Tier 2 is a single character-walked tolerant regex covering only whitespace runs and a fixed confusable set (dash/quote/ellipsis) — any word-level edit falls through both tiers to `quote_not_found`. Confirmed by a dedicated unit test (`test_reject_word_level_edit_fails_quote_not_found`). |
| 3 | Word positions and perk names resolved through the existing tokenizer and `perk_name_resolver.py` ladder, no second implementation of either | ✓ VERIFIED (with one noted judgment call, see below) | `scripts/find_text_backed_rolls.py:54` imports `_chapter_word_index` from the new `cp_word_index.py` and no longer defines it itself (`grep -n "def _chapter_word_index" scripts/find_text_backed_rolls.py` → no match). Regenerated `data/derived/roll_text_evidence.json` fresh in this session and diffed against the pre-verification copy: byte-identical (zero drift). `perk_name_resolver.py` and `scripts/build_perk_directory.py` are untouched since well before Phase 2 (`git log` shows last edits at `456033e`/`26fcbd8`, pre-dating this phase). Paid perks resolve via `directory_index.lookup(...)` unchanged; cost-0 free ride-alongs resolve solely via `obtained_perks_index` presence, never via the directory (spy-verified unit test `test_free_perk_resolves_without_touching_directory`). No allowlist/exception list exists anywhere (`grep -n "allowlist\|EXCLUD\|ALLOW"` → no hits); no cost-0 name was ever added to `perk_directory.json`/`perk_aliases.json` (git shows no manual edits to `perk_aliases.json` in Phase 2, and `perk_directory.json`'s builder script is untouched). |
| 4 | Verifier reports per-roll pass/fail with reasons, in a form Phase 3's confidence gate can consume | ✓ VERIFIED | `verify_roll()` returns `{chapter_num, roll_index, status: pass\|fail\|no_evidence, issues: [{code, severity, message}]}` — a plain importable dict, no file I/O, callable directly. `verify_chapter()` aggregates the same shape with `{pass, fail, no_evidence}` counts. Confirmed via direct source read and via the CLI's own JSON report output. |

**Score:** 4/4 ROADMAP success criteria verified.

### Specific Interrogation Items (from orchestrator brief)

| Item | Finding |
|---|---|
| D-05: `no_evidence` genuinely distinct from `pass`, empty/whitespace quote text is `fail` not silently skipped | VERIFIED. Code: `if not evidence_quotes and not issues: status = "no_evidence"` — this only fires when the roll has literally zero quotes. A quote with `text: "   "` hits `quote_text_empty` before any search, forcing `status = "fail"` (confirmed by `test_quote_text_empty_fails`, and independently re-derived: all 90 real `no_evidence` rolls have empty `evidence_quotes`, zero mismatches). |
| D-06(c): paid perks via ladder, cost-0 via `obtained_perks.json` only, never added to `perk_directory.json`/`perk_aliases.json`; ch92's seven-perk bundle passes; no allowlist | VERIFIED. Ch92 roll 1 (`Cybertronian Forge` + 6 cost-0 Transformers items) independently re-checked in the live report: `status: pass, issues: []`. `_verify_perk` only calls `directory_index.lookup` when the `obtained_perks_index` row is absent or has `cost > 0`; a `cost == 0` row short-circuits before any directory call. No allowlist exists in the source. |
| D-12: nothing bounds a quote's distance from the roll's `word_position`; ch92's quotes span far apart | VERIFIED. `_verify_quote`'s tolerance check compares a match's position only against that SAME quote's own `mention_word_position` (never the roll's `word_position`). Independently re-extracted ch92 roll 1's five quote positions from the real corpus: `[8241, 8286, 8497, 8871, 9858]`, a 1,617-word span — and this roll reports `status: pass`, confirming the code imposes no roll-relative bound in practice, not just in theory. |
| D-01/D-02: tokenizer moved to shared module, `find_text_backed_rolls.py` has no shim/re-export, epub path via `data_paths`, zero output drift | VERIFIED. `cp_word_index.py`'s `EPUB = RAW / "Brocktons_Celestial_Forge.epub"` is sourced via `from data_paths import RAW`. `find_text_backed_rolls.py` imports `_chapter_word_index` directly with no wrapper. Independently regenerated `roll_text_evidence.json` in this session and diffed against the prior copy: `diff -q` reported no difference. |
| Two mid-execution bug fixes in 02-03 (`_verify_quote` tag/entity handling; `_verify_perk` obtained-perks fallback) — do these weaken "no second implementation"? | (a) is not a second implementation — it is a length-preserving transform of the SAME prose text (`_strip_to_spaces` reused verbatim from `cp_word_index.py`, plus a new length-preserving entity decoder) that both quote tiers still search identically; the match/tier logic itself is unchanged. (b) is a judgment call: when `perk_name_resolver.py`'s ladder returns `None` because `perk_directory.json` catalogs a perk under a constellation different from the roll's own, `_verify_perk` falls back to checking `obtained_perks_index` presence (already-loaded data, exact `(chapter_num, name)` key lookup, no fuzzy logic) as confirmation the acquisition is real. This does not touch `perk_name_resolver.py` and does not introduce name-matching logic — it is an exact-match lookup against a different authoritative source, used only when the ladder can't disambiguate a real acquisition. I judge this a legitimate resolution-source branch consistent with D-06(c)'s existing paid/free-branch precedent, not a second implementation of the ladder itself. Flagged here for visibility since it is the one item requiring interpretive judgment rather than a bright-line check. |
| Known-accepted baseline: exactly 5 pre-existing failures, no NEW failures | VERIFIED. Independently ran the full suite (`.venv/bin/python -m pytest -q`, exit code 1). The `FAILED` lines are exactly: `test_forge_curator.py::test_stats_click_selects_actual_visible_roll_line`, `test_forge_curator.py::test_stats_click_refocuses_prose_for_motion_and_space_chords`, `test_forge_curator.py::test_stats_click_jumps_prose_to_selected_roll_location`, `test_forge_curator.py::test_click_roll_then_space_p_opens_perk_picker_for_selected_roll`, `test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction` — exactly the 5 documented known-accepted IDs, no more, no fewer. Also ran `scripts/data_release.py check-derived`: printed the known ch95 multi_grab informational line, then `local derived data ok`. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/cp_word_index.py` | Extracted tokenizer module (D-01/D-02) | ✓ VERIFIED | Exists; exports `_chapter_word_index`, `_split_sections`, `_strip_to_spaces`, `load_chapter_html`, `EPUB`. Sourced through `data_paths.RAW`. |
| `scripts/mechanical_verifier.py` | `verify_roll()`, `verify_chapter()`, `build_obtained_perks_index()`, CLI | ✓ VERIFIED | All present, read in full; CLI runs standalone and writes a report; not pipeline/manifest-wired (`grep` for `write_validated_json`/`pipeline.py`/`refresh_current_runtime_manifest` → no hits). |
| `scripts/find_text_backed_rolls.py` | Rewritten import, no shim | ✓ VERIFIED | Single `from cp_word_index import _chapter_word_index`; own definition deleted; zero output drift confirmed by fresh regeneration + diff. |
| `tests/test_cp_word_index.py` | Tokenizer regression tests | ✓ VERIFIED | 4 tests, collected and passing. |
| `tests/test_mechanical_verifier.py` | Unit + tracer + corpus-baseline tests | ✓ VERIFIED | 26 tests, collected and passing (2 real-corpus tracer, 23 synthetic unit, 1 corpus-wide D-10 baseline). |
| `.planning/.../deferred-items.md` | Three-way tokenizer-copy duplication documented | ✓ VERIFIED | Present; independently confirmed `_split_sections`/`_strip_to_spaces` exist in `find_roll_locations.py`, `extract_chapter_sections.py`, and `cp_word_index.py` (the third copy), matching the documented deferred item. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `mechanical_verifier.py` | `cp_word_index.py` | `from cp_word_index import _chapter_word_index, _strip_to_spaces, load_chapter_html` | ✓ WIRED | Confirmed by direct read of import block. |
| `mechanical_verifier.py` | `perk_name_resolver.py` | `from perk_name_resolver import build_directory_match_index, load_perk_aliases`; `directory_index.lookup(...)` | ✓ WIRED | Confirmed; ladder unchanged, still the sole paid-perk resolution mechanism. |
| `find_text_backed_rolls.py` | `cp_word_index.py` | `from cp_word_index import _chapter_word_index` | ✓ WIRED | Confirmed, zero-drift regeneration. |
| `mechanical_verifier.py` | `data/derived/obtained_perks.json` | `build_obtained_perks_index()` | ✓ WIRED | Confirmed; keys by `(chapter_num, perk_name)`, used for both the free-path and the paid-path disambiguation fallback. |
| Phase 3 (future) | `verify_roll`/`verify_chapter` | Direct Python import | ✓ WIRED (contract only) | Not yet consumed (Phase 3 not started) but the API shape is stable, pure, and documented in this plan's `<interfaces>` block for the next phase to import. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| CLI runs standalone against real repo data | `.venv/bin/python scripts/mechanical_verifier.py` | `pass: 591, no_evidence: 90, fail: 0` | ✓ PASS |
| `find_text_backed_rolls.py` output has zero drift after tokenizer extraction | `diff -q` pre/post regeneration | Identical | ✓ PASS |
| Targeted verifier test suite | `pytest tests/test_cp_word_index.py tests/test_mechanical_verifier.py -q` | 30 collected, all pass | ✓ PASS |
| Full suite regression check | `pytest -q` (exit 1) | Exactly the 5 known-accepted failures, no new ones | ✓ PASS |
| `data_release.py check-derived` | `.venv/bin/python scripts/data_release.py check-derived` | Known ch95 info line + "local derived data ok" | ✓ PASS |
| No fuzzy-matching import anywhere | `grep -rn "rapidfuzz\|difflib\|SequenceMatcher\|get_close_matches"` on touched files | Zero hits | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| CINF-03 | 02-01, 02-03 | Mechanical verifier validates agent output using existing primitives only, baselined against known-good hand-curated chapters before any LLM output touches it | ✓ SATISFIED | All four ROADMAP success criteria independently verified above; 100% baseline reproduced live (591/90/0); zero LLM code anywhere in `mechanical_verifier.py`/`cp_word_index.py` (no `anthropic` import). |

No orphaned requirements — REQUIREMENTS.md maps only CINF-03 to Phase 2, and both plans (02-01, 02-03) declare it.

### Anti-Patterns Found

None. `grep -n "TODO\|FIXME\|TBD\|XXX\|HACK\|PLACEHOLDER"` on `scripts/mechanical_verifier.py` and `scripts/cp_word_index.py` returns zero hits. No hardcoded empty returns, no allowlists, no console-log-only stubs.

### Deferred Items (pre-existing, not gaps of this phase)

- Three-way duplication of `_split_sections`/`_strip_to_spaces` across `find_roll_locations.py`, `extract_chapter_sections.py`, and the new `cp_word_index.py` — documented in this phase's own `deferred-items.md`, explicitly out of D-01's literal scope (rewrite one consumer, not consolidate the whole codebase).
- 5 known-accepted pre-existing pytest failures (4 `test_forge_curator.py`, 1 `test_roll_ordinal_contract.py`) — predate this phase, tracked in Phase 1's `deferred-items.md`, unaffected by this phase's work.

### Human Verification Required

None. This phase is pure deterministic code with no UI, no visual, and no external-service surface — every claim in scope is independently checkable by running code and reading source, and all were checked in this session.

### Gaps Summary

No gaps. Every ROADMAP success criterion, every locked D-01..D-13 decision, and every specific interrogation item from the orchestrator brief was independently reproduced or confirmed by direct source inspection in this verification session — not merely asserted by SUMMARY.md. The one item requiring interpretive (not mechanical) judgment — the `_verify_perk` obtained-perks fallback for constellation-mismatched paid perks — is judged a legitimate resolution-source branch, not a second implementation, and is flagged above for visibility rather than treated as a gap.

---

_Verified: 2026-08-01T18:37:01Z_
_Verifier: Claude (gsd-verifier)_
