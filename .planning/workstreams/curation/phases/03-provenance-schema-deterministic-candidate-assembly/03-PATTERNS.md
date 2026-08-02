# Phase 3: Provenance Schema & Deterministic Candidate Assembly - Pattern Map

**Mapped:** 2026-08-01
**Files analyzed:** 8 (1 data file, 6 CINF-01 consumers/tests, 1-2 new ACUR-01 scripts + tests)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `data/manual/chapter_roll_overrides.json` (add required `curated_by` to all 118 entries) | model (manual data) | CRUD | same file's existing `_fingerprint` sibling field | exact (in-file precedent) |
| `data/derived/_schemas/*.schema.json` — **no schema currently exists for `chapter_roll_overrides.json`** (see Finding below) | config (schema) | — | `data/derived/_schemas/roll_text_evidence.schema.json` | role-match |
| `scripts/derive_roll_facts.py` (consumer rewrite) | service/transform | CRUD (read override → restructure rows) | itself — existing `curator_added` / `model_validation_resolution` read sites | exact |
| `scripts/build_chapter_facts.py` (consumer rewrite) | service/transform | CRUD (read override → merge) | itself — `_load_chapter_roll_overrides()` | exact |
| `scripts/forge_curator/data_loader.py` (consumer rewrite) | service (loader) | CRUD (read-only doc cache) | itself — `chapter_roll_overrides` property | exact |
| `scripts/forge_curator/persistence.py` (consumer + writer rewrite) | service (persistence) | CRUD (read-modify-write + journal) | itself — `_ensure_chapter_entry` / `_stamp_chapter_alignment_fingerprint` | exact |
| `scripts/forge_curator/app.py` (TUI display rewrite) | component (TUI view) | request-response (render) | itself — `_roll_override_entry` usage sites | exact |
| `tests/test_chapter_roll_overrides.py` (extend) | test | CRUD | itself | exact |
| new `scripts/build_candidate_rolls.py` (or similar; ACUR-01 Stage 1) | service/transform (build_*) | batch/transform | `scripts/find_text_backed_rolls.py` | exact (role + data flow: reads predicted rolls + evidence, emits one `data/derived/*.json` artifact) |
| new candidates artifact `data/derived/candidate_rolls.json` (name at planner's discretion) | model (derived data) | batch | `data/derived/roll_text_evidence.json` (shape/schema pattern) | exact |
| new accuracy report script/artifact (D-10) | utility (report) | batch, non-DAG | `scripts/mechanical_verifier.py`'s `main()` CLI block (lines 415-519) → `data/derived/mechanical_verification_report.json` | exact |
| new tests for candidate assembly + accuracy scoring | test | batch | `tests/test_chapter_roll_overrides.py`, `tests/test_mechanical_verifier.py` | role-match |

## IMPORTANT FINDING: no schema currently gates `chapter_roll_overrides.json`

`data/derived/_schemas/` holds schemas for every *derived* artifact (`roll_text_evidence.schema.json`, `predicted_rolls.schema.json`, etc.), validated via `scripts/_common.py:write_validated_json`. **There is no `chapter_roll_overrides.schema.json`.** It is a hand-edited manual file (`data/manual/`) with no `write_validated_json` gate — the "_purpose" header documents its shape in prose only, and shape enforcement happens ad hoc inside consumers (`derive_roll_facts.py`'s `_has_structural_roll_override`, `_manual_override_issues`, etc.) and in `tests/test_chapter_roll_overrides.py`.

**Consequence for D-01 ("required, not optional-with-default; absent value is a validation error"):** there is no existing JSON-Schema enforcement point to hook into. The planner has two real options, and must pick one explicitly rather than assume a schema file exists to edit:
1. Add a new `data/derived/_schemas/chapter_roll_overrides.schema.json` and a new call to `write_validated_json`/a bespoke loader-side validator when `chapter_roll_overrides.json` is read (all four Python consumers below currently read it with a bare `json.loads`, no schema check at all).
2. Add an explicit Python-level assertion in one canonical load function (all four consumers call through different loaders — `load_overrides` in `multi_grab.py`, `_load_chapter_roll_overrides` in `build_chapter_facts.py`, `chapter_roll_overrides` property in `data_loader.py` — so this would need consolidating to one place or replicating the check four times, which risks a shim/inconsistency; prefer consolidating).

Either way, `tests/test_chapter_roll_overrides.py::test_missing_override_file_has_no_legacy_fallback` (line 37-40) and `test_roll_entries_must_use_dict_shape` (line 21-34) are the direct precedent for "assert shape, raise ValueError with a clear message" — follow that pattern for a new `test_curated_by_is_required` case.

## Pattern Assignments

### `data/manual/chapter_roll_overrides.json` (model, CRUD) — add `curated_by`

**Analog:** the file's own `_fingerprint` field, stamped by `scripts/forge_curator/persistence.py`.

**Existing chapter-entry shape** (`data/manual/chapter_roll_overrides.json`, entry for chapter "67"):
```json
"67": {
  "_fingerprint": "sha256:49ac1f51a000d7ea",
  "rolls": [ { "perks": [], "outcome": "miss", ... } ]
}
```
`curated_by` should sit alongside `_fingerprint` at the **chapter-entry level** (confirmed by D-02 and by this file's own precedent of chapter-level metadata siblings — `_fingerprint` here, `model_validation_resolution` referenced elsewhere per-roll). All 118 top-level entries under `"chapter_roll_overrides"` get `"curated_by": "human"` added — a one-time bulk edit, not per-roll.

Note: `"association_review"` is a **second top-level key** in this file (sibling to `"chapter_roll_overrides"`, holding `baseline_fingerprint` / `reviewed_through_chapter_num`) — do not confuse it with a chapter entry when writing the bulk-stamp script; iterate only `doc["chapter_roll_overrides"].items()`.

---

### `scripts/derive_roll_facts.py` (consumer, CRUD)

**Analog:** itself — this file already has the exact-precedent pattern for reading a required/optional chapter-entry-level metadata field and gating restructuring logic on it.

**Existing read pattern** (`scripts/derive_roll_facts.py:766`):
```python
resolution = (override or {}).get("model_validation_resolution") or {}
```

**Existing curator_added consumption** (lines 1520-1530):
```python
if (
    entry.get("curator_added")
    and entry.get("source_ordinal") is None
    and entry.get("outcome") == "miss"
    and not entry.get("perks")
):
    source_idx, template = last_source_idx, {}
    curator_added = True
```

**What changes for `curated_by`:** anywhere this module reads a chapter-level override `entry` (search hits at lines 631-870 for `_is_metadata_only_roll_override`, `_has_structural_roll_override`, `_fallback_projection_override`, `_manual_override_issues`, `_restructure_curator_rows`) must treat `curated_by` as a required, always-present key on `entry` — i.e. any code path that currently does `override or {}` defaulting must not silently tolerate a missing `curated_by`; validation should catch that upstream (see schema/validator finding above) rather than this module special-casing it.

---

### `scripts/build_chapter_facts.py` (consumer, CRUD)

**Analog:** itself.

**Loader** (`scripts/build_chapter_facts.py:248-256`):
```python
def _load_chapter_roll_overrides() -> dict[str, dict]:
    data = _read_json(CHAPTER_ROLL_OVERRIDES)
    return {
        str(chapter_num): override
        for chapter_num, override
        in data.get("chapter_roll_overrides", {}).items()
        if isinstance(override, dict)
    }
```
This is the single funnel point for override entries into `build_chapter_facts.py`. If a schema/shape-validation check is added (see Finding above), this is a natural second place to assert `curated_by in override` right after load, matching the existing `isinstance(override, dict)` filter style — same defensive-loop shape, just one more required-key check.

---

### `scripts/forge_curator/data_loader.py` (consumer, read-only cache)

**Analog:** itself.

**Existing property** (`scripts/forge_curator/data_loader.py:279-285`):
```python
def chapter_roll_overrides(self) -> dict:
    if self._chapter_roll_overrides_doc is None:
        if CHAPTER_ROLL_OVERRIDES.exists():
            self._chapter_roll_overrides_doc = _read_json(CHAPTER_ROLL_OVERRIDES)
        else:
            self._chapter_roll_overrides_doc = {"chapter_roll_overrides": {}}
    return self._chapter_roll_overrides_doc
```

**Presence-check usage** (lines 409-411):
```python
cro = self.chapter_roll_overrides.get("chapter_roll_overrides") or {}
overrides_present["chapter_roll_overrides"] = cn in cro
```
No change to the loader's read mechanics is required unless the TUI needs to *surface* `curated_by` per chapter (see `app.py` below) — this file is the funnel that would need a small accessor (e.g. `curated_by_for(chapter_num)`) if the TUI displays it.

---

### `scripts/forge_curator/persistence.py` (consumer + writer, CRUD)

**Analog:** itself — `_ensure_chapter_entry` / `_stamp_chapter_alignment_fingerprint` is the exact precedent for "auto-stamp a chapter-level metadata field the first time an entry is touched."

**Entry creation** (`scripts/forge_curator/persistence.py:156-164`):
```python
def _ensure_chapter_entry(self, chapter_num: str) -> dict:
    """Get or create the chapter_roll_overrides entry for ``chapter_num``."""
    cro = self.chapter_roll_overrides.setdefault("chapter_roll_overrides", {})
    if chapter_num not in cro:
        cro[chapter_num] = {"rolls": []}
    elif "rolls" not in cro[chapter_num]:
        cro[chapter_num]["rolls"] = []
    self._stamp_chapter_alignment_fingerprint(chapter_num, cro[chapter_num])
    return cro[chapter_num]
```

**Fingerprint auto-stamp** (lines 166-177):
```python
def _stamp_chapter_alignment_fingerprint(
    self,
    chapter_num: str,
    entry: dict,
) -> None:
    if entry.get("_fingerprint"):
        return
    if not self.chapter_alignment_fingerprints_path.exists():
        return
    doc = json.loads(self.chapter_alignment_fingerprints_path.read_text())
    fingerprints = doc.get("chapter_alignment_fingerprints") or {}
    entry["_fingerprint"] = fingerprints.get(str(chapter_num), "sha256:none")
```

**What changes:** `_ensure_chapter_entry` currently creates `{"rolls": []}` with no `curated_by` — since D-01 makes the field required on every entry, this creation site must set `curated_by` to a sane default (almost certainly `"human"`, since this is the human-facing TUI creating a brand-new entry) in the same dict literal, i.e. `cro[chapter_num] = {"rolls": [], "curated_by": "human"}`. This is the one human-visible write path for the field in this phase — Phase 4's agent path is a different writer, not this one.

---

### `scripts/forge_curator/app.py` (TUI display)

**Analog:** itself — `_roll_override_entry` (line 3809) is the accessor pattern the TUI uses to pull override fields for display; `curated_by` would follow the same shape as `mention_chapter_num`/`display_position_policy` reads shown at lines 3766-3805.

**Existing read-for-display pattern** (lines 3766-3805):
```python
override = self._roll_override_entry(cn, idx)
...
override.get("mention_chapter_num")
if override and override.get("mention_chapter_num") is not None
else ...
```
If the TUI is expected to surface `curated_by` (e.g. in a status line or chapter header), it reads the **chapter-entry** dict directly (not the per-roll `_roll_override_entry`), since `curated_by` lives at chapter level per D-02 — analogous to how `_fingerprint` would be read off the chapter entry, not a roll entry.

---

### `tests/test_chapter_roll_overrides.py` (test, CRUD)

**Analog:** itself.

**Shape-assertion precedent** (lines 21-34):
```python
def test_roll_entries_must_use_dict_shape(tmp_path: Path) -> None:
    path = tmp_path / "chapter_roll_overrides.json"
    path.write_text(json.dumps({
        "chapter_roll_overrides": {"1": {"rolls": [["Old Bare List"]]}},
    }))
    with pytest.raises(ValueError, match="must be dict"):
        load_overrides(path)
```
New tests for `curated_by` required-ness should follow this exact shape: write a synthetic override doc missing `curated_by`, assert the loader/validator raises. Also add a positive test mirroring `test_missing_override_file_has_no_legacy_fallback` (lines 37-40) confirming an empty-file default still round-trips.

---

### New ACUR-01 Stage 1 script (`scripts/build_candidate_rolls.py` or similar)

**Analog:** `scripts/find_text_backed_rolls.py` (19.3K), which produces `data/derived/roll_text_evidence.json` from `predicted_rolls.json` + regex anchors — this is Stage 1's primary *input*, and its own construction is the closest precedent for "read predicted rolls + evidence, bind fields, emit one validated derived artifact."

**Module docstring/contract pattern** (`scripts/find_text_backed_rolls.py:1-40`):
```python
"""For each predicted roll, find prose evidence in the chapter text.
...
Inputs:
  - data/raw/Brocktons_Celestial_Forge.epub
  - data/derived/predicted_rolls.json (regime-simulated positions)
  - data/derived/chapters.json
  ...
Output:
  - data/derived/roll_text_evidence.json (validated)
...
"""
from __future__ import annotations
import json, re, zipfile
from pathlib import Path
from _common import write_validated_json
from cp_word_index import _chapter_word_index
from find_roll_locations import _to_plain
```

**Validated write** (line 415):
```python
write_validated_json(OUT, payload, "roll_text_evidence")
```

**What Stage 1 binds over — the exact input row shape** (from `data/derived/_schemas/roll_text_evidence.schema.json` `$defs.roll`, required keys):
```
roll_number, chapter_num, slot_index, cp_rule_regime, roll_trigger_cp_threshold,
cp_offset, epub_offset, predicted_word_in_chapter, predicted_char_offset,
anchor_string, window_char_start, window_char_end,
evidence_kind ("direct"|"general_only"|"forward_ref"|"no_evidence"),
matching_anchor_kinds (array of "roll_attempt"|"miss"|"acquisition"|"constellation_reveal"|"general"),
matching_event_count, matching_events (array of {anchor_kind, anchor_phrase, anchor_offset, kinds_present, hit_count}),
next_specific_event_offset, prose_window
```
This is the 718-row substrate D-07's percentages (`forward_ref` 485, `direct` 132, `no_evidence` 74, `general_only` 27) are computed over. A new script consuming this file should follow `find_text_backed_rolls.py`'s own `write_validated_json(OUT, payload, "<new_schema_name>")` call, and needs a matching new `data/derived/_schemas/<new_artifact>.schema.json` (see the `roll_text_evidence.schema.json` top-level shape at lines 1-60 — required `_source`/`_method`/`_framing_note`-style metadata keys plus a `rolls`/array-of-items body — as the schema-authoring template; **D-05 requires candidate objects reuse the roll-object schema fields** — `perks`/`outcome`/`constellation`/`word_position`/`mention_*`/`display_position_policy`/`evidence_quotes` — as documented in `chapter_roll_overrides.json`'s own `"_purpose"` header, plus new provenance fields for evidence_kind/matched anchors/unfilled fields per D-05/D-06).

**Second input — bundle grouping signal (§1 of CURATION-CONVENTIONS.md):** `data/derived/obtained_perks.json`, paid-perk-first ordering, consumed today via `scripts/multi_grab.py:merge_paid_units` / `load_overrides`. Reuse `multi_grab.py`'s existing grouping function rather than reimplementing bundle detection (CONTEXT.md's "no parallel implementations" rule, reinforced by the canonical-refs note to reuse `find_roll_locations.py`/`find_text_backed_rolls.py` verbatim).

---

### New accuracy-measurement artifact (D-10)

**Analog:** `scripts/mechanical_verifier.py`'s CLI block (lines 415-519) → `data/derived/mechanical_verification_report.json`, explicitly **not** DAG-wired or schema-validated (comment at lines 415-420):
```python
# ---------------------------------------------------------------------------
# CLI — QA convenience wrapper (D-09: not DAG-wired, not manifest-
# registered). Loads the real corpus, runs verify_chapter() over every
# chapter in chapter_roll_overrides.json, and writes a plain JSON report
# (a bare json.dumps write — deliberately not schema-validated/registered).
# ---------------------------------------------------------------------------
```
**Report-assembly pattern** (lines 487-519):
```python
def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    overrides_doc = json.loads(args.overrides.read_text())
    ...
    chapter_roll_overrides = overrides_doc["chapter_roll_overrides"]
    chapter_results: dict[str, dict] = {}
    totals = {"pass": 0, "fail": 0, "no_evidence": 0}
    for chapter_num, entry in chapter_roll_overrides.items():
        result = verify_chapter(chapter_num, entry, ...)
        chapter_results[chapter_num] = result
        for status, n in result["counts"].items():
            totals[status] += n
    payload = {"chapters": chapter_results, "totals": totals}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
```
This is the direct template for D-10's committed accuracy report: per-class (not global) totals dict, argparse-driven paths with sane defaults, plain non-schema-validated JSON write. **D-08 requires breaking `totals` out per `evidence_kind` class** (`direct`/`forward_ref`/`no_evidence`/`general_only`) rather than the single flat `{"pass","fail","no_evidence"}` shown here — extend the `totals` dict to be keyed by evidence class, each holding the "matched / no-curated-counterpart / partial" triad D-08 specifies.

For the **prose/markdown side** of D-10 ("a report, as in Phase 1's `corpus-analysis-report.md`"): `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` exists as a **committed hand/agent-written markdown artifact** with no generating script found in `scripts/` — i.e. that report was written directly into the phase's planning output, not code-generated. The planner should decide (per Claude's Discretion note) whether Phase 3's D-10 artifact is (a) a script-generated JSON report following `mechanical_verifier.py`'s pattern, checked by tests, with a short markdown summary appended by hand/by the phase's summary step, or (b) fully code-generated markdown. Given D-10 says "Phase 4 reads it," prefer a machine-readable JSON report (option a) as the primary artifact — Phase 4 needs to parse numbers, not prose.

**Stub-chapter exclusion (D-09):** re-derive the stub list from data rather than hardcoding. No existing script filters "stub chapters" by name; the closest signal is chapters whose `chapter_roll_overrides` entry rolls all lack `evidence_quotes` (per D-09's description "carry rolls with no evidence quotes and were not hand-curated"). Grep confirms no existing `STUB_CHAPTERS` constant anywhere in `scripts/` — this filter is new logic for this phase, derived at runtime from `chapter_roll_overrides.json` content, not copied from an analog.

---

## Shared Patterns

### `write_validated_json` — canonical write gate for new derived artifacts
**Source:** `scripts/_common.py:31-49`
**Apply to:** the new Stage 1 candidates artifact (`data/derived/*.json`) if D-04's discretion is resolved toward "pipeline-wired" — but note Phase 2 deliberately opted OUT of this for its QA report (`mechanical_verifier.py` writes with a bare `json.dumps`, not `write_validated_json`). D-04 leans standalone for the candidates artifact too; if standalone, follow `mechanical_verifier.py`'s bare-write pattern instead of `_common.py`'s validated-write pattern.
```python
def write_validated_json(out_path: Path, payload: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(json.loads(text)), key=lambda e: list(e.path))
    if errors:
        raise ValueError(...)
    out_path.write_text(text)
```

### `build_*`/`derive_*` script skeleton
**Source:** `scripts/find_text_backed_rolls.py` (module docstring → constants → pure helper functions → `main()` → CLI)
**Apply to:** the new Stage 1 candidate-assembly script and the accuracy-report script. Both should expose pure functions importable from tests without invoking `main()`, per the established `tests/test_*.py` convention of `from scripts.X import _pure_function`.

### Chapter-entry-level metadata stamping (auto-fill on first touch)
**Source:** `scripts/forge_curator/persistence.py:156-177` (`_ensure_chapter_entry` + `_stamp_chapter_alignment_fingerprint`)
**Apply to:** wherever `curated_by` needs a default value supplied by code rather than by the bulk one-time JSON edit — i.e. any future/TUI-driven creation of a *new* chapter entry (out of scope for the 118 existing entries, which get a one-time bulk script/edit instead).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `data/derived/_schemas/chapter_roll_overrides.schema.json` (if planner chooses schema-gate option) | config | — | No schema currently exists for this manual file at all (see Finding above); planner must decide whether to introduce one in this phase or keep enforcement Python-side, consolidated into one loader. |
| Stub-chapter auto-detection logic | utility | transform | No existing "is this chapter a stub" predicate exists anywhere in `scripts/`; must be derived fresh from `evidence_quotes`-emptiness per D-09, not copied. |

## Metadata

**Analog search scope:** `scripts/`, `scripts/forge_curator/`, `tests/`, `data/manual/`, `data/derived/_schemas/`
**Files scanned:** ~90 top-level scripts + 3 forge_curator modules + `chapter_roll_overrides.json` + `roll_text_evidence.schema.json` + `mechanical_verifier.py`
**Pattern extraction date:** 2026-08-01
