# Phase 4: Inference Refinement, Confidence Gate & Routing - Pattern Map

**Mapped:** 2026-08-02
**Files analyzed:** ~9-11 (exact plan split is the planner's call; this maps the functional pieces named in CONTEXT.md)
**Analogs found:** strong analogs for 6 of 9 functional pieces; 3 are genuinely new construction (batch client, confidence gate, ledger)

## Read First: The No-Parallel-Implementations Constraint (D-03)

This phase is unusual — most of the hard work already exists. The planner's job is to correctly
**wire** these together, not re-derive them. Building a second paragraph scorer, a second
constellation extractor, or a second prose/word-offset pipeline is a phase failure per D-03 and
the project's `feedback_no_parallel_implementations` rule. Read the "Two Prose Pipelines Exist"
warning below before planning the retrieval file — it is the single sharpest risk in this phase.

## File Classification

| New/Modified File (functional piece) | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| Stage 2 retrieval (candidate-paragraph assembly per D-01) | service/transform | batch, CRUD-read | `scripts/forge_curator/evidence_scorer.py` + `scripts/forge_curator/miss_quote_matcher.py` (both imported, not modified) | exact (reuse, not new) |
| Stage 2 prompt/schema module (conventions + exemplars + output schema) | config/transform | request-response | none (new); structural precedent in `scripts/build_exemplar_index.py`'s doc-mining shape | no analog for prompt content; loader shape has an analog |
| Batch client (submit/poll/collect Anthropic Batches API) | service | batch, event-driven | **none anywhere in repo** | no analog — see "Genuinely New" below |
| Quote/structure verification bridge (Stage 2 output → `verify_roll`) | service | transform | `scripts/mechanical_verifier.py:verify_roll/verify_chapter` (imported directly, not modified) | exact (reuse) |
| Confidence gate (composite score, D-13) | service | transform | none as a unit; assembles `mechanical_verifier` + `obtained_perks_index` + model self-report | no analog — new, but built entirely from existing signals |
| Routing (corpus write vs proposals sidecar) | service | CRUD, request-response | `scripts/chapter_roll_overrides_io.py:write_chapter_roll_overrides_doc` (corpus side, reused verbatim) + new proposals writer | corpus side exact; proposals side no analog |
| Proposals sidecar writer | service | file-I/O | `scripts/measure_candidate_accuracy.py` (report+JSON sidecar shape) / `scripts/build_exemplar_index.py` (`build_index()` pure function + thin CLI) | role-match (report/sidecar shape), not schema shape |
| Agent-run ledger (CINF-04) | store/model | CRUD, event-driven | `scripts/forge_curator/persistence.py:_append_journal` (JSONL journal) | partial match (journal mechanics only; shape/purpose differ — see below) |
| Dry-run token/cost estimator (D-23) | utility | transform | none | no analog — new |
| Calibration/held-out split + per-class report (D-21/D-22) | script (measurement) | batch, transform | `scripts/measure_candidate_accuracy.py` (whole file — this is Phase 3's own analog, built for exactly this shape of "compare against corpus, per evidence class, hand-authored .md summary") | exact |

## Pattern Assignments

### 1. Candidate-paragraph retrieval (D-01/D-02/D-03)

**Reuse verbatim — do not reimplement.**

`scripts/forge_curator/evidence_scorer.py` (139 lines, read in full):

- `EVIDENCE_CANDIDATE_THRESHOLD = 4` (line 24) — **the TUI's own default. Stage 2 must NOT
  change this constant.** Per D-02, pass a different threshold as a parameter instead.
- `score_paragraph(paragraph: str) -> tuple[int, list[str]]` (lines 104-122) — pure function,
  scores one paragraph string, returns `(score, matched_terms)`. No I/O.
- `evidence_candidates(text, word_offsets, *, threshold=EVIDENCE_CANDIDATE_THRESHOLD) -> list[EvidenceCandidate]`
  (lines 77-101) — **this is Stage 2's entry point.** Call signature:
  ```python
  evidence_candidates(
      text: str,                              # full chapter prose text
      word_offsets: list[tuple[int, int]],    # (char_start, char_end) per CP-word
      threshold: int = 4,                     # Stage 2 passes 3 (D-01's measured knee) or its own tuned value
  ) -> list[EvidenceCandidate]
  ```
  `EvidenceCandidate` (lines 68-74, frozen dataclass): `paragraph_index, char_start, char_end,
  word_index, score, matched_terms`.
- **`word_offsets` is supplied by the caller** — `evidence_scorer.py` has zero I/O of its own.
  The TUI's current caller is `data_loader.py:ChapterProse.word_offsets` (see item 4 below for
  the batch-path equivalent).

`scripts/forge_curator/quote_autofill.py` (87 lines, read in full) — deterministic constellation
extraction, **exactly what D-03 says Stage 2 must never re-derive**:

- `KNOWN_CONSTELLATIONS` (lines 9-13) — the 14-item canonical list.
- `single_constellation_reference(quote: str) -> str | None` (lines 70-78) — returns the sole
  unambiguous constellation name in a string, or `None` if zero or multiple. **Feed Stage 2's
  retrieved paragraphs (and later the model's own proposed quote text) through this before ever
  asking the model to name a constellation** — if the code can already resolve it deterministically
  and unambiguously, the model should not be asked to.
- `classify_quote_autofill(quote: str) -> QuoteAutofillSuggestion | None` (lines 53-67) — stricter:
  requires both a single constellation AND unambiguous hit/miss language (`_HIT_LANGUAGE` /
  `_MISS_LANGUAGE` regexes, lines 14-44), returns `QuoteAutofillSuggestion(outcome, constellation)`.
  Useful as a pre-fill/cross-check against the model's own `outcome`+`constellation` output — if
  they disagree, that disagreement is itself a confidence signal.

`scripts/forge_curator/miss_quote_matcher.py` (387 lines; read lines 1-100 in full, remainder is
internal helper machinery for the two public entry points):

- `find_miss_quote_candidates(text, word_offsets, *, constellation, anchor_word_index, window_before=800, window_after=6500) -> list[MissQuoteCandidate]`
  (lines 56-97) — miss evidence is retrieved by "constellation named nearby + miss-language
  regex", **not** by `evidence_scorer`'s general paragraph scoring; per CURATION-CONVENTIONS §4
  this is a distinct evidence shape (no perk to anchor on). `constellation` is required — for a
  predicted miss roll with no constellation yet resolved, this can't run until one is available
  (from D-04's `quote_autofill` or the model's own proposal).
- `MissQuoteCandidate` (lines 34-41): `text, char_start, char_end, word_index, score, reason_tags, variants`.
- Internally imports `score_paragraph` from `evidence_scorer.py` (line 8) — confirms these two
  modules are already meant to compose, not duplicate.

**D-01's union set for Stage 2's retrieval file:** (1) `evidence_candidates(..., threshold=3)`
paragraphs, (2) paragraphs containing a token-subset match against `obtained_perks.json` names
for that chapter (this token-subset matcher is genuinely new — no existing module does
perk-name-variant matching against arbitrary prose; closest precedent is
`perk_name_resolver.py`'s alias ladder, but that resolves already-extracted *names*, not scans
prose for them), and (3) `roll_text_evidence.json`'s `prose_window` per predicted roll. Only (2)
lacks a direct analog; (1) and (3) are read-only reuse.

### 2. Prose text + word_offsets — TWO PIPELINES EXIST, PICK CAREFULLY

**This is the sharpest risk in the phase.** There are two independent chapter-prose/word-index
implementations in the repo, and they are not interchangeable:

- **TUI path:** `scripts/forge_curator/data_loader.py:ForgeCuratorData.chapter_prose()`
  (lines 432-509) — reads the epub via its own `_strip_html`/`_HtmlStripper` (lines 46-108),
  computes `word_offsets` via `_compute_word_offsets(text)` (line 481, defined ~line 552). Returns
  a `ChapterProse` dataclass (`text`, `word_offsets: list[tuple[int,int]]`,
  `section_break_word_indices`, `implicit_header_word_ranges`). This is what feeds
  `evidence_scorer.evidence_candidates()` and `miss_quote_matcher.find_miss_quote_candidates()`
  **inside the TUI today.** It is importable outside the TUI (it's a plain method on a class you
  can instantiate with `root: Path`), but it is coupled to the TUI's `ForgeCuratorData` object
  graph (meta/derived caches, `chapter_sections.json`, etc.) — heavier than a batch script needs.

- **Verifier/canonical path:** `scripts/cp_word_index.py` — `_chapter_word_index()`,
  `_strip_to_spaces()`, `load_chapter_html()` (also used directly by
  `scripts/mechanical_verifier.py:_build_prose_loader`, lines 466-485). This is the tokenizer
  `word_position` in `chapter_roll_overrides.json` is actually defined against — it is the
  **CP-earning word index**, the one D-10's mechanical position derivation and the verifier's
  `bisect` lookups both rely on. `mechanical_verifier.py`'s own comment block (lines 33-71)
  documents entity-decoding and paragraph-boundary edge cases this tokenizer handles that the
  TUI's `_strip_html`/`_compute_word_offsets` may not.

**Because D-10/D-11 require every Stage-2-proposed quote to pass `verify_roll()`, and
`verify_roll()`'s position tolerance is measured in `cp_word_index.py`'s word units, Stage 2's
retrieval and position-derivation should use `cp_word_index.py`'s tokenizer, not
`data_loader.py`'s, for anything that will be compared against `word_position` or fed to the
verifier.** `evidence_scorer.py`/`miss_quote_matcher.py` themselves are tokenizer-agnostic (they
just take `word_offsets` as a parameter) — so the fix is "call them with `cp_word_index`-derived
offsets in the batch path," not "rebuild the scorers." The planner must decide explicitly whether
the batch pipeline reconstructs paragraph/offset data via `cp_word_index` (recommended, matches
what the verifier already does) or reuses `data_loader.ChapterProse` (simpler, but introduces a
second offset space that must then be reconciled with the verifier's before any position check —
a reconciliation step that does not currently exist anywhere).

### 3. Mechanical verifier (D-11, D-13's hard signal)

`scripts/mechanical_verifier.py` (528 lines; read in full) — **pure module, no argparse/file I/O
in the two functions Stage 2 calls:**

```python
verify_roll(
    chapter_num: str,
    roll_index: int,
    roll: dict,
    *,
    prose_loader,          # callable: chapter_num -> (chapter_html, word_index)
    directory_index,       # perk_name_resolver.DirectoryMatchIndex
    obtained_perks_index: dict[tuple[str, str], dict],  # from build_obtained_perks_index()
) -> dict   # {chapter_num, roll_index, status: pass|fail|no_evidence, issues: [{code, severity, message}]}
```
(lines 291-378). `verify_chapter()` (lines 381-413) aggregates per-chapter. Both are already
composed by the CLI wrapper's `_build_prose_loader()` closure (lines 466-485) — **reuse that
closure shape** (lazy per-chapter cache over `cp_word_index.load_chapter_html` +
`_chapter_word_index`) rather than writing a new prose_loader.

`build_obtained_perks_index(obtained_perks_doc) -> dict[tuple[str,str], dict]` (lines 217-230) —
indexes `obtained_perks.json` rows by `(chapter_num, perk_name)`; the cost-0/cost>0 branch point
D-06(c) depends on.

The `{code, severity, message}` issue shape (e.g. `quote_not_found`, `position_out_of_tolerance`,
`perk_unresolved`, `bad_outcome_enum` — see lines 156-364 for the full enumerated set) is the
vocabulary the confidence gate should read, not re-derive. A gate that wants "every quote passed"
is literally `all(r["status"] == "pass" for r in verify_chapter(...)["rolls"])`, no new logic
needed.

### 4. Corpus write path (unchanged, reused verbatim)

`scripts/chapter_roll_overrides_io.py` (105 lines, read in full) — **the only sanctioned write
path**, already exists, already stamps schema-required `curated_by`:

```python
write_chapter_roll_overrides_doc(doc: dict, path: Path | None = None) -> None
load_chapter_roll_overrides_doc(path: Path | None = None, *, default: dict | None = None) -> dict
```
Validates against `data/derived/_schemas/chapter_roll_overrides.schema.json`, writes
`indent=2, ensure_ascii=False` + trailing newline. **Agent writes must set `curated_by: "agent"`
per chapter entry before calling this** — no code change to this module is needed or wanted; it
already enforces the enum (`["human", "agent"]`). CINF-04's "never overwrite an existing
hand-curated chapter" rule is enforced by the caller (check `curated_by` on
`load_chapter_roll_overrides_doc()`'s existing entry before writing), not by this module.

### 5. Proposals sidecar (D-15, D-17) — genuinely new, but with a shape precedent

**No existing file is "a sidecar holding roll-object-schema data that is NOT the trusted
corpus."** D-15 requires reusing the corpus's roll-object schema so Phase 5's TUI review needs no
translation. Closest structural precedents (report-artifact + JSON sidecar, not schema-identical):

- `scripts/build_exemplar_index.py` (341 lines; read lines 1-40 and tail ~60 lines) — pattern:
  pure `build_index(overrides_doc, chapter_facts_doc, transitions) -> dict` core function, thin
  argparse `main()` that loads inputs, calls the pure function, does
  `output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))`, prints a stats summary.
  **This argparse+pure-function+plain-json.dumps-write shape (not schema-validated/registered,
  explicitly a "QA/measurement instrument, not a pipeline input" per its own docstring) is what
  the proposals writer should look like structurally** — except the proposals file DOES need to
  reuse the `chapter_roll_overrides` schema per D-15, unlike this analog's report, which is
  deliberately unregistered.
- `scripts/measure_candidate_accuracy.py` (568 lines; read header + tail) — same shape, plus the
  paired `.json` + hand-authored `.md` summary convention (`candidate-accuracy-report.json` /
  `.md`) that D-18's reporting (fields-pre-filled-per-chapter, chapters-requiring-no-manual-hunt)
  should follow for Stage 2's own calibration report.

**Recommendation for the planner:** the proposals sidecar's *on-disk write mechanics* (atomic
write, `indent=2, ensure_ascii=False`, trailing newline) should mirror
`chapter_roll_overrides_io.py`'s `write_validated_json` call even though it's a different target
path/schema-registration status — don't hand-roll a third JSON writer. Whether it goes through
`_common.write_validated_json` (if a schema gets registered for it) or a bare `write_text` (if
Claude's discretion keeps it unregistered per D-15's "location and file shape are Claude's
discretion") is a planner decision; either way, copy the serialization convention, not a new one.

### 6. Agent-run ledger (CINF-04, D-19/D-20)

Partial analog only: `scripts/forge_curator/persistence.py` — `CurationPersistence._journal_path`
/ `_journal()` (lines 110-114) / `_append_journal()` (lines 116-143). Pattern: JSONL file per
session at `data/manual/.session_journals/<ISO-timestamp>.jsonl`, one line per action:
```python
entry = {
    "timestamp": ...,       # ISO8601, UTC, seconds precision, "Z" suffix
    "action_type": ...,
    "chapter_num": ...,
    "before": ..., "after": ...,
    "target_file": ...,     # relative to MANUAL.parent
}
# optionally "extra": {...}
with journal_path.open("a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```
**What transfers:** the append-only JSONL mechanics and the ISO-timestamp-per-session file
naming.
**What does NOT transfer:** this journal is per-*session* (one TUI sitting = one file, arbitrary
action count) and write-only (nothing reads it back for idempotency checks). CINF-04's ledger is
the opposite shape — it must be **keyed by chapter and by fingerprint**, and it must be **read
before every run** to decide "does this chapter need reprocessing" (D-20's no-diff-on-rerun
requirement). This is closer to a small keyed store (chapter_num → {fingerprint, model, run_id,
confidence, timestamps}) than an append-only log. **No existing file in the repo implements a
keyed, read-before-write idempotency ledger — this is new construction.** The fingerprint (D-20)
must hash: chapter prose (or its epub_href + a content hash), Stage 1's candidate object for that
chapter, the conventions/prompt version string, and the model id — all four already exist as
inputs elsewhere in the pipeline (`candidate_rolls.json`, epub, this phase's own prompt module,
the batch request's model field); the ledger only needs to combine and hash them, not derive any
of them fresh.

## Shared Patterns

### Pure-function-core + thin-argparse-CLI (applies to: retrieval module, gate module, ledger module, dry-run estimator)
**Source:** `scripts/build_exemplar_index.py`, `scripts/measure_candidate_accuracy.py`,
`scripts/mechanical_verifier.py` (all three: `parse_args()` / pure functions / `main()` split)
```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES, ...)
    return p.parse_args(argv)

def main(argv=None) -> None:
    args = parse_args(argv)
    doc = load_x(args.x)
    payload = build_y(doc)          # pure function — this is what tests import
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"wrote {args.output}")

if __name__ == "__main__":
    main()
```
Apply to every new script in this phase — tests should import the pure `build_*`/`verify_*`-style
function with synthetic fixtures, never shell out to the CLI.

### Import-fallback for dual-context modules
**Source:** `scripts/chapter_roll_overrides_io.py` lines 38-50, `scripts/build_exemplar_index.py`
lines 32-36.
```python
try:
    from chapter_roll_overrides_io import load_chapter_roll_overrides_doc
except ImportError:  # pragma: no cover
    from scripts.chapter_roll_overrides_io import load_chapter_roll_overrides_doc
```
Any new Stage 2 module imported both as a bare top-level script (`PYTHONPATH=scripts`) and as a
package-qualified import (from the forge_curator TUI, if Phase 5's review flow ever imports Stage
2 internals) needs this same fallback.

### Validated + atomic JSON write
**Source:** `scripts/chapter_roll_overrides_io.py:write_chapter_roll_overrides_doc` (delegates to
`_common.write_validated_json`).
**Apply to:** the corpus write (unchanged, reused as-is) and, if the proposals sidecar gets a
registered schema, the same `_common.write_validated_json` call rather than a bare `json.dumps`.

### `{code, severity, message}` issue/reason shape
**Source:** `scripts/mechanical_verifier.py` (all `_verify_quote`/`_verify_perk` returns) — itself
inherited from `derive_roll_facts.py`'s `_manual_override_issues` shape per the module docstring.
**Apply to:** the confidence gate's own rejection reasons, so Phase 5's TUI can render gate
failures with the same vocabulary as verifier failures instead of a second ad hoc shape.

## No Analog Found

| File/piece | Role | Data Flow | Reason |
|---|---|---|---|
| Batch client (Anthropic SDK: `messages.batches.create`, poll `processing_status`, collect by `custom_id`) | service | batch, event-driven | **Confirmed via repo-wide grep: zero existing usage of `anthropic`, `ANTHROPIC_API_KEY`, `messages.create`, or `messages.batches` anywhere in this codebase.** This is genuinely new construction. Follow `.planning/research/STACK.md`'s D-06/D-07/D-08/D-09 mechanics (Batches API + prompt caching + structured outputs + Opus-then-Sonnet tiering) directly — there is no in-repo analog to defer to, only the STACK.md research and the Anthropic SDK's own documented API shape. |
| Confidence gate (composite scorer combining verifier pass/fail + structural agreement + perk resolution + model self-report, D-13) | service | transform | No existing module combines multiple pipeline signals into one routing decision. It is new, but should be a thin composition layer over `mechanical_verifier.verify_chapter()` + `build_obtained_perks_index()` — no new verification logic belongs here, only combination/thresholding logic. |
| Dry-run token/cost estimator (D-23) | utility | transform | No existing script estimates API cost before a run — this pipeline has never spent API budget before this phase. Build from scratch using the Anthropic SDK's token-counting utilities (see STACK.md) and the retrieval module's own output size. |
| Keyed, fingerprint-based run ledger (CINF-04, D-19/D-20) | store | event-driven, CRUD | `persistence.py`'s session journal is append-only and per-session, not keyed/read-before-write; no existing file plays this role. See item 6 above for what does and doesn't transfer. |
| Perk-name-variant-in-prose scanner (D-01 signal 2: "paragraphs containing a known perk name, tolerant of variants") | utility | transform | `perk_name_resolver.py` resolves already-extracted candidate *names* against a directory; it does not scan raw prose for name occurrences. This is a small new function, but should reuse `perk_name_resolver.py`'s alias/variant data (`data/manual/perk_aliases.json`) as its variant source rather than inventing a second alias table. |

## Metadata

**Analog search scope:** `scripts/`, `scripts/forge_curator/`, `data/derived/_schemas/`, `data/manual/.session_journals/`
**Files scanned (read in full or targeted sections):** `evidence_scorer.py`, `quote_autofill.py`,
`miss_quote_matcher.py` (partial — public API + head), `mechanical_verifier.py` (full),
`chapter_roll_overrides_io.py` (full), `data_loader.py` (targeted: `chapter_prose` + class
surface), `cp_word_index.py` (signature scan), `build_exemplar_index.py` (head + tail),
`measure_candidate_accuracy.py` (head + tail), `persistence.py` (journal section)
**Repo-wide grep confirming no Anthropic SDK usage:** `grep -rn "anthropic\|ANTHROPIC_API_KEY\|messages.create\|messages.batches" --include="*.py" .` → zero matches.
**Pattern extraction date:** 2026-08-02
