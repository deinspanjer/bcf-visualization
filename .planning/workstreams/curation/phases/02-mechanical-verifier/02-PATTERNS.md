# Phase 2: Mechanical Verifier - Pattern Map

**Mapped:** 2026-07-26
**Files analyzed:** 8 (2 rewritten/extracted, 2 new modules, 3 new test files, 1 data file addition)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/cp_word_index.py` (new, D-01/D-02) | utility/service (pure transform) | transform (HTML → char-offset word index) | `scripts/query_exemplars.py` (pure-module + thin `__main__`) | role-match, exact shape |
| `scripts/find_text_backed_rolls.py` (rewritten consumer) | service (batch derivation script) | batch / transform | itself (pre-extraction version) + `scripts/find_roll_locations.py` (sibling consumer of the same trio) | exact (self, minus extracted trio) |
| `scripts/mechanical_verifier.py` (new, D-06/D-09) | service (pure verification API) + CLI | request-response (per-roll check) + batch (corpus report) | `scripts/query_exemplars.py` (pure API + thin CLI) for the API half; `scripts/build_exemplar_index.py` (argparse + `write_validated_json` + stdout summary) for the CLI half | role-match, exact shape |
| `tests/test_cp_word_index.py` (new) | test | transform | `tests/test_build_exemplar_index.py` | exact |
| `tests/test_mechanical_verifier.py` (new) | test (unit + corpus-baseline) | transform / batch | `tests/test_build_exemplar_index.py` (unit shape) — no direct analog for the `pytest.mark.skipif`-on-epub-absence baseline test; this is genuinely new infrastructure | role-match (unit half), no analog (skip-guard half) |
| `data/manual/perk_aliases.json` (additive rows, D-11) | config/data (hand-curated) | CRUD (manual additive edit) | itself (existing file) — `scripts/perk_name_resolver.py::load_perk_aliases` is the sole reader | exact |

## Pattern Assignments

### `scripts/cp_word_index.py` (utility, transform)

**Analog:** `scripts/find_text_backed_rolls.py` (current, pre-extraction) `_chapter_word_index` (lines 80-101) + `scripts/find_roll_locations.py`'s `_strip_to_spaces` (:81) and `_split_sections` (:305), plus `scripts/data_paths.py` for path resolution.

**Module docstring / pure-module convention** (model after `scripts/query_exemplars.py:1-10`):
```python
"""Deterministic same-regime exemplar retrieval (D-06).

Pure module — no argparse, no file I/O in the retrieval path. ...

Phase 3 imports ``retrieve()`` directly; the thin ``__main__`` block below
is for manual debugging only.
"""
```
Apply verbatim shape: `cp_word_index.py` should open with a docstring stating it is the shared tokenizer extracted per D-01, that `find_text_backed_rolls.py` is its consumer, and that no other script should reimplement it.

**Core transform pattern to move as-is** (`scripts/find_text_backed_rolls.py:80-101`, current file):
```python
def _chapter_word_index(
    chapter_html: str,
    section_classifications: dict[str, dict],
    chapter_num: str,
) -> list[int]:
    body_m = re.search(r"<body[^>]*>", chapter_html)
    body_content_start = body_m.end() if body_m else 0

    out: list[int] = []
    for section_index, (_header, s_start, s_end) in enumerate(_split_sections(chapter_html)):
        cls = section_classifications.get(f"{chapter_num}@{section_index}")
        if not cls or not cls.get("counts_for_cp"):
            continue
        effective_start = max(s_start, body_content_start)
        if effective_start >= s_end:
            continue
        spaced = _strip_to_spaces(chapter_html[effective_start:s_end])
        for m in re.finditer(r"\S+", spaced):
            out.append(effective_start + m.start())
    return out
```
`_split_sections` and `_strip_to_spaces` must be copied (not imported) from `scripts/find_roll_locations.py:305` and `:81` into the new module — per RESEARCH.md's blast-radius finding, do NOT import them from `find_roll_locations.py` (that would leave the verifier depending on a script outside D-01's stated scope, and does not resolve the pre-existing `find_roll_locations.py`/`extract_chapter_sections.py` duplication, which stays a deferred item).

**Path resolution — the fix D-02 requires** (replace `scripts/find_text_backed_rolls.py:59`'s `EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"` with the `data_paths.py` convention, `scripts/data_paths.py:1-15`):
```python
from data_paths import RAW

EPUB = RAW / "Brocktons_Celestial_Forge.epub"
```
This is the exact pattern `perk_name_resolver.py:38` already uses (`from data_paths import MANUAL` / `PERK_ALIASES_JSON = MANUAL / "perk_aliases.json"`) — mirror it precisely.

**Chapter-HTML read path (preserve exactly, per RESEARCH.md "Chapter Prose Addressing"):**
```python
with zipfile.ZipFile(EPUB) as zf:
    html = zf.read(f"EPUB/{href}").decode("utf-8")
```
This exact `"EPUB/" + href` prefix is used identically today in `find_text_backed_rolls.py`, `find_roll_locations.py`, and `extract_chapter_sections.py` — the extracted module must preserve it byte-for-byte, not "clean it up."

---

### `scripts/find_text_backed_rolls.py` (rewritten consumer, no shim)

**Analog:** itself, before extraction (already read in full above, lines 1-101 shown).

**Import-block change** (was `scripts/find_text_backed_rolls.py:54-56`):
```python
from find_roll_locations import (
    _split_sections, _strip_to_spaces, _to_plain,
)
```
becomes:
```python
from cp_word_index import _chapter_word_index
from find_roll_locations import _to_plain  # unrelated to D-01; still needed here
```
Per D-01, this is a full rewrite of this one consumer — no re-export shim, no alias module. `_to_plain` stays imported from `find_roll_locations.py` since it is out of scope for the tokenizer extraction (only the tokenizer trio moves).

**No behavior-diff requirement:** the rewrite must produce byte-identical `_chapter_word_index` output to the pre-extraction version — this is exactly what `tests/test_cp_word_index.py` (see below) exists to pin down before/after the extraction.

---

### `scripts/mechanical_verifier.py` (new: pure API + CLI)

**Analog (API half):** `scripts/query_exemplars.py` full file (pure `retrieve()` core, thin `if __name__ == "__main__":` block at the bottom doing argparse + file I/O + `print(json.dumps(...))`).

**Analog (CLI/report half):** `scripts/build_exemplar_index.py` (`parse_args` :280, `main` :309, stdout summary lines :323-332).

**Docstring convention to copy** (from `query_exemplars.py:1-10`, adapted):
```python
"""Deterministic mechanical verification of curated roll data against
source prose and existing pipeline primitives (D-01..D-11).

Pure module — no argparse, no file I/O in verify_chapter()/verify_roll().
Zero fuzzy matching anywhere (REQUIREMENTS.md Out of Scope): quote
verification is exact-substring, two normalization tiers, full stop.

Phase 3's confidence gate imports verify_chapter()/verify_roll() directly.
The thin __main__ block below is a CLI convenience that loads the real
corpus (epub + chapter_roll_overrides.json + perk_directory.json +
perk_aliases.json) and writes a JSON report. NOT wired into
scripts/pipeline.py and NOT manifest-registered (D-09) — this is a QA
instrument, not a pipeline input.
"""
```

**Structured reason-code shape — reuse verbatim** (`scripts/derive_roll_facts.py:834-838`, `_manual_override_issues`):
```python
issues.append({
    "code": "curated_hit_missing_perks",
    "severity": "error",
    "message": f"Curated hit roll #{idx} does not name any perk.",
})
```
Apply this `{code, severity, message}` triple to every per-roll/per-quote reason the verifier emits, e.g.:
```python
{"code": "quote_not_found", "severity": "error", "message": "..."}
{"code": "position_out_of_tolerance", "severity": "error", "message": "..."}
{"code": "perk_unresolved", "severity": "error", "message": "..."}
{"code": "bad_outcome_enum", "severity": "error", "message": "..."}
```
This is the one existing precedent in the codebase for "structured reason for a roll-level problem" — do not invent a new shape.

**Perk-ladder call — reuse exactly, do not reimplement** (`scripts/derive_roll_facts.py:92-100`):
```python
def lookup_perk(match_idx, name, jump=None, constellation=None):
    if not name:
        return None
    return match_idx.lookup(name, jump=jump, constellation=constellation)
```
And the ladder construction (`scripts/perk_name_resolver.py`):
```python
from perk_name_resolver import (
    load_perk_aliases, build_alias_lookup, resolve_canonical,
    build_directory_match_index,
)
aliases = load_perk_aliases()
directory_index = build_directory_match_index(directory_rows, aliases)
```

**CLI argparse + stdout-summary convention** (`scripts/build_exemplar_index.py:280-332`, structure to mirror):
```python
def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(...)
    return p.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    ...
    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"  pass:        {stats['pass']}")
    print(f"  no_evidence: {stats['no_evidence']}")
    print(f"  fail:        {stats['fail']}")

if __name__ == "__main__":
    main()
```
Since D-09 says the report is a convenience (not a pipeline artifact), a registered JSON schema via `_common.write_validated_json` is optional — but if one is added, follow `scripts/_common.py:29-46`'s exact validate-then-write shape (serialize with `ensure_ascii=False`, validate the serialized form, then write).

**Nearest-occurrence position check — copy this prototype verbatim** (RESEARCH.md, validated against full corpus):
```python
import bisect, re

def nearest_occurrence_distance(quote_text, chapter_html, word_index, claimed_word_pos):
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
Never use first-match `str.find()`/`in` for position verification — 7/833 real corpus quotes false-fail with distances up to ~30,000 words if first-match is used instead of nearest-occurrence.

**Confusable-folding (Tier 2) — copy this prototype verbatim:**
```python
def fold_confusables(s: str) -> str:
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("‘", "'").replace("’", "'")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("…", "...")
    return s

def normalize_tier2(s: str) -> str:
    s = fold_confusables(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()
```
Named tolerance constant to declare inline (per D-04, Claude's discretion but documented):
```python
# Measured against the full 118-chapter hand-curated corpus (2026-07-26):
# max real distance 41 words after nearest-occurrence disambiguation;
# 50 gives ~20% headroom.
POSITION_TOLERANCE_WORDS = 50
```

---

### `tests/test_cp_word_index.py` (new)

**Analog:** `tests/test_build_exemplar_index.py` (full file structure: `sys.path.insert` boilerplate at top, fixture-builder helper functions, imports the pure function directly, never shells out).

**Import + path boilerplate to copy** (`tests/test_build_exemplar_index.py:1-14`):
```python
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scripts.cp_word_index import _chapter_word_index  # noqa: E402
```
**Fixture convention:** small synthetic HTML strings built inline via helper functions (mirroring `_overrides_doc`/`_chapter_facts_doc`/`_cf_entry`/`_roll` in `test_build_exemplar_index.py`), never live repo data, never the real epub for unit-level tests. Confirm before/after-extraction behavior parity by asserting identical output against the same synthetic fixture the pre-extraction function would have produced.

---

### `tests/test_mechanical_verifier.py` (new — unit tests + D-10 corpus baseline)

**Analog (unit half):** `tests/test_build_exemplar_index.py` (same fixture-builder + direct-import convention as above).

**Analog (skip-guard half): none exists in this codebase today.** RESEARCH.md confirms: surveyed all 19 epub-referencing test files, zero use `pytest.mark.skipif` or any epub-existence guard. This is genuinely new infrastructure — recommended shape (standard pytest, no project precedent to contradict, matches `scripts/data_paths.py`'s `RAW` convention):
```python
from data_paths import RAW

EPUB_AVAILABLE = (RAW / "Brocktons_Celestial_Forge.epub").exists()

@pytest.mark.skipif(not EPUB_AVAILABLE, reason="epub is gitignored; corpus baseline needs local source")
def test_verifier_passes_full_hand_curated_corpus():
    ...
```
No `conftest.py` exists anywhere in `tests/` — follow the established (if not ideal) codebase convention of a module-level constant duplicated in this file, rather than introducing a shared fixture file as this phase's first `conftest.py`.

**Closest structural precedent for "loop over the whole corpus" pattern:** `tests/test_roll_position_invariants.py` (iterates all of `data/derived/chapters.json`/`roll_facts.json` and asserts invariants) — use its loop-and-assert shape, but note it consumes already-generated derived JSON, never the raw epub, so it is not a `skipif` precedent, only a corpus-loop-shape precedent.

---

### `data/manual/perk_aliases.json` (additive rows, D-11)

**Exact existing shape** (confirmed via direct read):
```json
{
  "Accelerator Equipment": [
    "Accelerator Equipment (Zoids: Legacy) (3 Customization Points)"
  ],
  "Additional Space": [
    "Additional Space - Starting Area",
    "Additional Space – Lofty Loft"
  ]
}
```
Structure: flat `{canonical: [alias, ...]}` dict, no metadata wrapper, no `_purpose` header (unlike `chapter_roll_overrides.json`). Any of the 14 D-11 additions must match this exact shape — canonical key as the directory's true name, alias list containing the raw curated string(s) that fail to resolve. Read via `scripts/perk_name_resolver.py::load_perk_aliases` (`json.loads(Path(src).read_text())`, then validated to ensure every value is a list — `perk_name_resolver.py:163-172`). This is a hand-curated file: additions are a `checkpoint:decision` task per D-11, never an autonomous executor edit.

## Shared Patterns

### Pure-module + thin-CLI split
**Source:** `scripts/query_exemplars.py` (whole file)
**Apply to:** `scripts/cp_word_index.py` and `scripts/mechanical_verifier.py`
No argparse or file I/O inside the pure functions (`_chapter_word_index`, `verify_chapter`, `verify_roll`); all file/epub/JSON loading happens only in each module's own `if __name__ == "__main__":` block.

### Structured issue/reason-code triple
**Source:** `scripts/derive_roll_facts.py:834-838` (`_manual_override_issues`)
**Apply to:** every per-roll/per-quote failure the verifier reports
`{"code": str, "severity": "error"|"warning", "message": str}` — reuse this shape rather than inventing a new one; it is the one existing precedent for structured validation-problem reporting in this codebase.

### `data_paths.py` env-override convention
**Source:** `scripts/data_paths.py` (`RAW`/`DATA`/`DERIVED`/`MANUAL`, `BCF_DATA_DIR` override) and `scripts/perk_name_resolver.py:38` (`from data_paths import MANUAL`)
**Apply to:** `cp_word_index.py`'s epub path (fixes the D-02 hardcoded-path bug) and any other new module needing repo data paths — never hardcode `ROOT / "data" / "raw"` again.

### Direct-import test convention (no shelling out)
**Source:** `tests/test_build_exemplar_index.py`
**Apply to:** `tests/test_cp_word_index.py`, `tests/test_mechanical_verifier.py`
`sys.path.insert(0, str(SCRIPTS))` boilerplate + `from scripts.<module> import <fn>` + inline synthetic-fixture builder functions; never invoke the script as a subprocess.

## No Analog Found

| File/Concern | Role | Data Flow | Reason |
|---|---|---|---|
| `pytest.mark.skipif`-on-epub-absence guard (D-10) | test | conditional/batch | RESEARCH.md confirms zero existing tests in this codebase use any epub-existence guard; this is genuinely new test infrastructure. Recommended shape given inline above (standard pytest idiom, no project-specific deviation needed). |

## Metadata

**Analog search scope:** `scripts/` (all `.py`, especially `find_text_backed_rolls.py`, `find_roll_locations.py`, `extract_chapter_sections.py`, `perk_name_resolver.py`, `data_paths.py`, `_common.py`, `derive_roll_facts.py`, `query_exemplars.py`, `build_exemplar_index.py`, `chapter_alignment.py`, `verify.py`); `tests/` (19 epub-referencing files surveyed per RESEARCH.md, plus direct read of `test_build_exemplar_index.py`); `data/manual/perk_aliases.json`.
**Files scanned:** ~15 direct reads/greps in this session, cross-referenced against RESEARCH.md's own (already-exhaustive) codebase archaeology to avoid duplicate reads.
**Pattern extraction date:** 2026-07-26
</content>
