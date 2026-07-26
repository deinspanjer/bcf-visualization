# Phase 1: Epub Refresh & Exemplar Mining - Pattern Map

**Mapped:** 2026-07-26
**Files analyzed:** 6 (new/modified)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `scripts/build_exemplar_index.py` | utility (build script) | transform (batch, JSON-in/JSON-out) | `scripts/derive_outstanding_perks.py` | exact |
| `scripts/query_exemplars.py` | utility (pure query module) | transform (in-memory filter/rank, no I/O) | `scripts/multi_grab.py` (pure functions over loaded overrides) + `scripts/regime_simulator.py` (pure lookup fn) | role-match |
| `scripts/pipeline.py` (modified — add `Step`) | config/DAG registration | batch (dependency-graph declaration) | existing `build_visualization_facts` `Step` block (same file) | exact |
| `scripts/data_release.py` (no code change expected) | config (manifest) | batch | `_top_level_json_files()` (auto-discovery, no per-file registration needed) | exact (verified: no change needed) |
| `tests/test_build_exemplar_index.py` | test | CRUD-ish (assert derived JSON shape) | `tests/test_chapter_roll_overrides.py` (loads overrides via `multi_grab.load_overrides`, asserts shape/behavior) | exact |
| `tests/test_query_exemplars.py` | test | transform | `tests/test_build_visualization_facts.py` (imports `build()` directly, asserts on in-memory dict) | role-match |
| `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` | doc | — | none (new artifact type) | no analog |
| `scripts/verify_epub_freshness.py` (or addition to `tests/test_source_epub_hydration.py`) | utility/test | request-response (compare two data sources) | `scripts/hydrate_source_epub.py`'s `parse_epub_nav()`/`validate_manual_chapter_references()` | role-match |

## Pattern Assignments

### `scripts/build_exemplar_index.py` (utility, transform/batch)

**Analog:** `scripts/derive_outstanding_perks.py` (full file read; 342 lines)

**Imports pattern** (lines 25-37):
```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_CATALOG = ROOT / "data" / "derived" / "perk_directory.json"
DEFAULT_ACQUIRED = ROOT / "data" / "derived" / "obtained_perks.json"
DEFAULT_CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "outstanding_perks_by_chapter.json"

SCHEMA_VERSION = 1
```
For the new script, mirror this exactly but with:
```python
DEFAULT_OVERRIDES = ROOT / "data" / "manual" / "chapter_roll_overrides.json"
DEFAULT_CHAPTER_FACTS = ROOT / "data" / "derived" / "chapter_facts.json"
DEFAULT_TRANSITIONS = ROOT / "data" / "manual" / "regime_transitions.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "exemplar_index.json"
SCHEMA_VERSION = 1
```
Import the canonical regime function rather than re-deriving (per RESEARCH Pattern 3 / Pitfall 1):
```python
try:
    from regime_simulator import regime_for_chapter
except ModuleNotFoundError:
    from scripts.regime_simulator import regime_for_chapter
```

**CLI/argparse pattern** (lines 141-167):
```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG,
                    help="Path to perk_directory.json (default: %(default)s)")
    ...
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                    help="Path for output file (default: %(default)s)")
    return p.parse_args(argv)
```
Adapt flags to `--overrides`, `--chapter-facts`, `--transitions`, `--output` per RESEARCH's `parse_args` example (RESEARCH.md lines 208-214).

**Core pattern — pure inner function + orchestrating `main()`** (lines 66-108, 170-232):
- Keep transform logic in small pure functions (`_build_snapshot`, `_chapter_index`, `_find_unmatched` are the analog's shape) that take plain data in and return plain dicts — this is directly testable without file I/O, matching what `test_build_visualization_facts.py` does for `build()`.
- `main()` only: parses args, reads JSON via `json.loads(path.read_text())`, calls the pure functions, assembles `payload`, writes output, prints stdout summary.
- Soft anomalies (e.g., a chapter missing from `chapter_facts.json`, a corpus roll with an unexpected shape) are printed to **stderr as WARNING**, not raised — see lines 219-231 and 326-337 (unmatched-name warnings, final-count-mismatch warning). Hard shape violations (e.g., `chapter_roll_overrides.json` missing its top-level key) should `raise ValueError`/`SystemExit` loudly per RESEARCH's V5 input-validation note (matches `multi_grab.py`'s `_normalise_roll_entry` loud-fail convention).

**Payload/write pattern** (lines 307-313):
```python
payload = {
    "schema_version": SCHEMA_VERSION,
    "chapters": out_chapters,
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
```
Use `schema_version` as the top-level key (required for `data_release.py`'s auto-discovery to record `schema_version` in the manifest — see Shared Patterns below). Field-name/schema shape beyond this is Claude's discretion per CONTEXT.md.

**stdout summary pattern** (lines 318-337):
```python
print(f"wrote {args.output.relative_to(ROOT)}")
print(f"  chapter count:                 {len(out_chapters)}")
...
if final_outstanding != expected_final:
    print(f"  WARNING: ...", file=sys.stderr)
```
Emit a similar human-readable summary block (counts of exemplars, regime distribution, boundary-chapter count) after writing — this is the established convention, not optional flourish; several existing build scripts are diagnosed via this stdout output in CI logs.

**Entry point** (lines 340-342):
```python
if __name__ == "__main__":
    main()
```

**Ch97 boundary-tagging recipe** — copy verbatim from RESEARCH.md's Pattern 3 (already-verified recipe, do not re-derive):
```python
# For each chapter_num in chapter_facts.json:
primary_regime = chapter_facts_entry["point_calculation_regime"]
boundary_entry = next((t for t in regime_transitions if t["chapter_num"] == chapter_num), None)
if boundary_entry is None:
    tags = {primary_regime}
    is_boundary = False
else:
    tags = {regime_for_chapter(chapter_num), int(boundary_entry["new_regime"])}
    is_boundary = True
```

---

### `scripts/query_exemplars.py` (utility, pure transform — no I/O)

**Analog:** `scripts/regime_simulator.py`'s `regime_for_chapter()` shape (pure function, no file I/O in the query path) combined with `scripts/multi_grab.py`'s "load once, then pure functions over the loaded structure" separation.

**Pattern:** Keep this a *pure* module — it takes an already-loaded index (dict) and a target chapter/regime, and returns a filtered/ranked list. No `argparse`, no file writes. Something like:
```python
from __future__ import annotations


def retrieve(target_regimes: set[int], index: dict, k: int | None = None) -> list[dict]:
    """Return exemplars whose regime tags intersect target_regimes.

    Deterministic: same-regime filter, then a stable, documented ranking
    (e.g., chapter proximity or roll-count similarity — Claude's discretion,
    per CONTEXT.md D-06), never embeddings/fuzzy matching.
    """
    candidates = [
        entry for entry in index["exemplars"]
        if target_regimes & set(entry["regime_tags"])
    ]
    candidates.sort(key=lambda e: ...)  # deterministic tiebreak
    return candidates[:k] if k is not None else candidates
```
A thin `if __name__ == "__main__":` CLI wrapper (loads `exemplar_index.json`, calls `retrieve`, prints JSON) may be added for manual debugging, following the `--output`-style argparse convention above, but the importable function must not require CLI invocation — Phase 3 imports `retrieve()` directly (RESEARCH.md: "Phase 3 imports it directly").

---

### `scripts/pipeline.py` (modify — register new `Step`)

**Analog:** the existing `build_visualization_facts` `Step` block, same file, lines 320-331 (already read above).

**Exact insertion pattern** (RESEARCH.md lines 230-247, verified against this file's live `Step`/`_py`/`inputs` helpers):
```python
Step(
    name="build_exemplar_index",
    inputs=inputs(
        chapter_roll_overrides,               # data/manual/chapter_roll_overrides.json
        derived / "chapter_facts.json",        # point_calculation_regime (D-01)
        manual / "regime_transitions.json",    # boundary-chapter list only (D-01/D-02)
    ),
    outputs=(derived / "exemplar_index.json",),
    cmd=_py(root, "build_exemplar_index.py"),
),
```
**Critical:** also add `"build_exemplar_index"` to `TARGET_FINAL_STEPS["data"]` (currently `("build_visualization_facts",)` at line 367) — a `Step` whose output nothing else consumes is silently dropped from the `data` target's closure otherwise:
```python
TARGET_FINAL_STEPS = {
    "data": ("build_visualization_facts", "build_exemplar_index"),
    ...
}
```
Confirm `chapter_roll_overrides` is already a named path constant used elsewhere in this file (it is — used by `derive_roll_facts`/`build_chapter_facts` steps per RESEARCH Pitfall 2) and reuse that same constant; do not redeclare a second path literal for it (avoids repeating the exact `multi_grab_overrides.json` naming-drift bug documented in Pitfall 2).

---

### `scripts/data_release.py` (no code change expected)

**Analog / verified mechanism:** `_top_level_json_files()` (lines 122-126, read directly):
```python
def _top_level_json_files(source_dir: Path) -> list[Path]:
    return sorted(
        path for path in source_dir.glob("*.json")
        if path.name not in {"data_package.json", DEV_BUNDLE_MANIFEST_NAME}
    )
```
This globs `*.json` in `data/derived/` unconditionally and reads `schema_version` from each (`_file_meta`, lines 128-134-ish). **No manual registration code is needed** — as long as `build_exemplar_index.py` writes `data/derived/exemplar_index.json` with a `schema_version` key, running `python scripts/data_release.py manifest` after the pipeline picks it up automatically. Do not add a bespoke registration block; that would be a parallel-implementation anti-pattern.

---

### `tests/test_build_exemplar_index.py` (test)

**Analog:** `tests/test_chapter_roll_overrides.py` (imports pattern, lines 1-20 read):
```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts.multi_grab import load_overrides, merge_paid_units  # noqa: E402
from scripts.derive_roll_facts import (  # noqa: E402
    ...
)
```
Follow this import style (`from scripts.<module> import <fn>`) and use `tmp_path`-based fixtures for building small synthetic `chapter_roll_overrides.json`/`chapter_facts.json`/`regime_transitions.json` inputs, then call the new script's pure inner functions directly (not via subprocess) — matching `test_chapter_roll_overrides.py`'s per-function unit-test style (`test_roll_entries_must_use_dict_shape`, `test_quote_only_override_preserves_existing_roll_shape`, etc., one behavior per test function).

**Required assertions (from RESEARCH's Phase Requirements → Test Map, CINF-02 row):**
1. Every curated chapter appears with the correct regime tag(s).
2. Ch97 specifically carries `{2, 3}` tags plus a boundary flag (`is_boundary: True`).
3. `query_exemplars.retrieve(target, index)` never returns a cross-regime exemplar.

---

### `tests/test_query_exemplars.py` (test)

**Analog:** `tests/test_build_visualization_facts.py` (lines 1-6, 90-112 read) — imports the pure `build()` function directly and asserts on the returned in-memory dict, no subprocess/file round-trip needed for the core logic tests:
```python
from scripts.build_visualization_facts import build
```
Mirror as `from scripts.query_exemplars import retrieve`, construct a small synthetic in-memory `index` dict fixture (2-3 regimes, including a boundary-tagged entry), and assert the same-regime constraint plus deterministic ordering (call twice, assert identical output — no randomness).

---

### `scripts/verify_epub_freshness.py` (or addition to `tests/test_source_epub_hydration.py`) — EPUB-01 verification

**Analog:** `scripts/hydrate_source_epub.py`'s existing `parse_epub_nav()` + `validate_manual_chapter_references()` (per RESEARCH's Don't-Hand-Roll table and Architecture Diagram) — reuse these directly rather than writing a new epub parser. The verification is a comparison of two already-computed values:
- Post-hydrate `chapter_count`/`last_chapter_num` from `hydrate_source_epub.hydrate_source_epub()`'s return value.
- The private-source clone's own `Brocktons_Celestial_Forge.metadata.json` (`chapters.count`, `last_chapter_friendly_number`) as the comparison baseline.

Per D-10, this phase's plans start at **verification**, not sync/hydrate — the new code only asserts the two already-hydrated values agree/exceed the pre-refresh baseline; it does not re-implement epub parsing.

---

## Shared Patterns

### Derived-artifact build script skeleton
**Source:** `scripts/derive_outstanding_perks.py` (whole file)
**Apply to:** `scripts/build_exemplar_index.py`
- `argparse` with `--<input>`/`--output` flags defaulting to standard `data/derived`/`data/manual` paths
- Pure-function core, `SCHEMA_VERSION` constant, `payload = {"schema_version": N, ...}`
- `json.dumps(..., indent=2, ensure_ascii=False)`
- stdout summary + stderr warnings for soft anomalies, `raise`/`SystemExit` for hard shape violations

### Pipeline DAG registration
**Source:** `scripts/pipeline.py` lines 320-331, 366-368 (this file)
**Apply to:** the new `build_exemplar_index` `Step` — must be added to **both** the `Step` list **and** `TARGET_FINAL_STEPS["data"]`, or it will be silently excluded from the `data` target's closure.

### Manifest auto-discovery — no registration code needed
**Source:** `scripts/data_release.py` lines 122-126 (`_top_level_json_files`)
**Apply to:** any new file under `data/derived/*.json` with a `schema_version` key — automatically picked up by `manifest`/`check-derived`; do not write bespoke registration logic.

### Canonical regime source — never re-derive
**Source:** `scripts/regime_simulator.py::regime_for_chapter`
**Apply to:** `build_exemplar_index.py` — import this function directly; never write a second regime classifier (RESEARCH Pitfall 1 documents the existing `build_chapter_facts.py` duplicate-function bug as the anti-pattern to avoid repeating).

### Loud-fail on malformed hand-curated input
**Source:** `scripts/multi_grab.py::_normalise_roll_entry` (referenced in RESEARCH's V5 Input Validation row)
**Apply to:** `build_exemplar_index.py`'s loader for `chapter_roll_overrides.json` — raise loudly on unexpected shape rather than silently coercing, consistent with the project's trust guarantee for hand-curated data.

### Test import/fixture convention
**Source:** `tests/test_chapter_roll_overrides.py` (imports), `tests/test_build_visualization_facts.py` (direct-function-call style), `tests/conftest.py` (`BCF_DATA_DIR` snapshot isolation — read but not modified by this phase's new tests)
**Apply to:** `tests/test_build_exemplar_index.py`, `tests/test_query_exemplars.py` — import pure functions directly (`from scripts.<module> import <fn>`), avoid subprocess invocation for logic tests, use `tmp_path` for any file-based fixtures.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` | doc | — | First human-readable corpus-characterization report in this project; no prior markdown-report convention to copy. Follow RESEARCH.md's D-05 content spec (roll-shape distribution, evidence-quote pattern stats, perk-link/naming conventions) and quote only via already-committed evidence quotes; no code pattern applies — this is prose, not a script. |

## Metadata

**Analog search scope:** `scripts/` (all `build_*.py`/`derive_*.py`), `tests/` (test files for existing derived scripts), `scripts/pipeline.py`, `scripts/data_release.py`, `scripts/data_paths.py`, `scripts/regime_simulator.py`, `scripts/multi_grab.py`
**Files scanned:** ~15 (directory listing + 6 read in full/targeted)
**Pattern extraction date:** 2026-07-26
