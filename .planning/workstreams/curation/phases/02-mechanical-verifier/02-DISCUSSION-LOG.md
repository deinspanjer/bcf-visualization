# Phase 2: Mechanical Verifier - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 2-Mechanical Verifier (curation workstream)
**Mode:** `--auto` (all gray areas auto-selected; recommended option chosen per question, no interactive prompts)
**Areas discussed:** Tokenizer reuse, Normalization boundary, Empty-evidence policy, Verifier scope, Output shape, Baseline enforcement

---

## Tokenizer reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Extract to shared module, rewrite consumer | Moves `_chapter_word_index`/`_split_sections`/`_strip_to_spaces` out of `find_text_backed_rolls.py`; full rewrite, no alias re-export | ✓ |
| Import the private functions cross-script | Cheaper, but couples the verifier to a script's private API | |
| Reimplement in the verifier | Violates no-parallel-implementations outright | |

**Choice:** `[auto]` Extraction. Also folds in the `data_paths` fix — `find_text_backed_rolls.py:59` hardcodes `ROOT / "data" / "raw"`, bypassing `BCF_DATA_DIR` and making the tokenizer untestable against a scratch dir.

---

## Normalization boundary (Tier 2)

| Option | Description | Selected |
|--------|-------------|----------|
| Confusables + whitespace + case, no word edits | Folds dash/quote/ellipsis variants, collapses whitespace, case-insensitive; rejects any word-level edit | ✓ |
| Byte-exact only | Would false-fail on hand-curated data — `realign_chapters.py` re-escapes `–`/`…` on every run | |
| Any fuzzy/edit-distance tier | Forbidden by REQUIREMENTS.md Out of Scope | |

**Choice:** `[auto]` Two tiers, both substring-exact after normalization. Grounded in an observed corpus fact rather than theory: the Phase 1 `ensure_ascii` churn proves both character forms exist in the file.

---

## Empty-evidence policy

| Option | Description | Selected |
|--------|-------------|----------|
| Third outcome `no_evidence` | Not a fail (WoG rolls are legitimate), not a pass (agents can't trivially qualify) | ✓ |
| Treat as pass | Lets an agent emit zero quotes to clear the gate | |
| Treat as fail | Breaks the 100% baseline on ch 121.1's WoG-backed rolls | |

**Choice:** `[auto]` Three-outcome model. This is the decision that lets Dre's WoG convention and the exact-or-reject trust bar coexist.

---

## Verifier scope

| Option | Description | Selected |
|--------|-------------|----------|
| Quotes + positions + perk names + enum sanity | Matches CINF-03's three primitives plus structural checks | ✓ |
| Also roll-scheduling/slot capacity | Would make the 100% baseline unreachable — ch 104 fails there by design | |

**Choice:** `[auto]` Scoped to prose-truthfulness. Capacity validation stays with `roll_scheduler.py`/`multi_grab.py`. Locked the anti-corruption rule: a verifier/corpus disagreement is fixed in the verifier, never by editing hand-curated data.

---

## Output shape

| Option | Description | Selected |
|--------|-------------|----------|
| Python API + CLI report, not pipeline-wired | API is Phase 3's contract; report is convenience; no DAG coupling | ✓ |
| Pipeline-wired, manifest-registered artifact | Drags verification into every data regen; it's a QA instrument, not an input | |

**Choice:** `[auto]` Standalone. Deliberately differs from Phase 1's exemplar-index decision because that artifact *is* a downstream input and this one is not.

---

## Baseline enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Corpus-wide pytest, skip if epub absent | Regressions caught by the existing suite; suite stays runnable without private source | ✓ |
| CLI-only, manual runs | No regression protection | |

**Choice:** `[auto]` pytest over all 118 chapters asserting zero `fail`; phase gate requires a run with the epub present, baseline counts recorded in the SUMMARY.

---

## Claude's Discretion

- Module/CLI names and locations
- Position-tolerance constant and rationale
- Per-roll result object shape (must carry outcome + machine-readable reason code)
- Confusable folding implementation (hand table vs `unicodedata`)
- Test structure and fixtures

## Deferred Ideas

- Slot-capacity verification → existing scheduler validation path
- Confidence scoring and routing → Phase 3
- LLM/similarity-based verification → permanently out of scope
- The 5 known-accepted test failures and ch 104's anchor → Phase 1 deferred-items
