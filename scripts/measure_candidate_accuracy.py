"""Measure Stage 1's candidate-assembly accuracy against the hand-curated
corpus, broken out per evidence class (ACUR-01, ROADMAP success criterion
3; Phase 3's D-08/D-09/D-10 decisions).

This is the load-bearing measurement of Phase 3: Phase 4 reads the
committed report to size its inference spend instead of guessing. A single
headline number would be dominated by the 68% ``forward_ref`` share and
would hide that Stage 1 works well on the ``direct`` class, which is what
D-08 exists to prevent — every number in this module's output is reported
per evidence class, never collapsed.

Inputs:
  - data/derived/candidate_rolls.json (Plan 03-02's Stage 1 output)
  - data/manual/chapter_roll_overrides.json, read exclusively through
    scripts/multi_grab.py:load_overrides() (which itself goes through
    Plan 03-01's schema-validated, curated_by-stamped consolidated loader)

Output:
  - .planning/workstreams/curation/phases/
    03-provenance-schema-deterministic-candidate-assembly/
    candidate-accuracy-report.json (a bare json.dumps write — deliberately
    NOT schema-validated/manifest-registered, same QA-instrument posture
    as mechanical_verifier.py's report; D-04's discretion note leans
    standalone for exactly this reason)
  - .../candidate-accuracy-report.md (hand-authored prose summary, sourced
    only from the JSON's own numbers, mirroring Phase 1's
    corpus-analysis-report.md)

This module is NOT wired into the data-regen DAG and NOT registered in the
runtime data manifest (D-09 in Phase 2's precedent) — it is a QA/
measurement instrument, not a pipeline input. No LLM or external API call
anywhere in this module.

Stub-chapter exclusion (D-09)
------------------------------
``derive_stub_chapters()`` re-derives, from the live corpus on every call,
the set of chapters where every curated roll carries an empty
``evidence_quotes`` list — i.e. chapters that were never actually hand
-curated with narrative evidence, only stamped with mechanically-derived
placeholder rolls. These chapters are excluded from the accuracy
denominator entirely: scoring Stage 1 against a generated stub measures
agreement with the stub, not with Dre's judgement. This is NEVER a
hardcoded literal chapter list — a chapter that gains real curation (e.g.
chapter 104, curated 2026-08-01) drops out of the stub set the next time
this function runs, with no special-casing of "104" anywhere in this
module.

Candidate-to-curated matching methodology (_method)
-----------------------------------------------------
``match_candidates_to_curated()`` pairs each curated roll in a chapter to
at most one candidate and vice versa. It NEVER compares ``roll_number`` or
``source_ordinal`` — those sequences are assigned independently by the
predictor and curator and diverge by construction (project convention);
using them as a join key would silently pair unrelated rolls whenever the
two sequences happen to agree on a number by coincidence.

The algorithm, in full:

1. For each curated roll, compute its chapter-local position: its own
   ``word_position`` when that value is non-null (the DIRECT comparison
   mode — nearly always absent in the real corpus, only 2 of 681 curated
   rolls carry one), otherwise its 0-based ORDINAL rank within that
   chapter's curated ``rolls[]`` list (the documented fallback — the
   curator's own list order is already narrative reading order).
2. For each candidate being compared against a curated roll, compute its
   position on the SAME scale the curated roll used: when the curated
   roll's real ``word_position`` was used, compare against the
   candidate's own real ``word_position`` (candidates always carry one,
   copied from ``predicted_word_in_chapter``); when the curated roll fell
   back to its ordinal rank, compare against the candidate's own 0-based
   ordinal rank within that chapter's candidate list (candidates are
   sorted by ``slot_index`` ascending first — already narrative order per
   ``build_candidate_rolls.py``). This keeps every comparison on
   compatible units — an ordinal rank (0, 1, 2, ...) is never diffed
   directly against a raw word-count position (which can run into the
   thousands).
3. For every (curated roll, candidate) pair in the chapter, compute
   ``distance`` = the absolute difference of the two positions from steps
   1-2, and ``perk_overlap`` = the number of case-insensitively normalized
   perk names present in both rolls' ``perks`` lists.
4. Sort every pair in the chapter by ``(distance ascending, perk_overlap
   descending, curated_index ascending, candidate_index ascending)`` and
   greedily walk the sorted list, claiming a pair only when neither its
   curated roll nor its candidate has already been claimed. Position
   proximity is the PRIMARY signal; perk-name overlap is a TIEBREAKER
   only, consulted when two pairs are equidistant. This produces a unique
   1:1 assignment, fully deterministic for a given chapter's inputs.
5. A curated roll left unclaimed after step 4 (candidates in the chapter
   ran out, or a closer candidate was claimed by a different curated
   roll first) is reported ``missed``. For per-evidence-class BUCKETING
   only (never for the matched/partial/missed status itself), a missed
   curated roll is attributed to the ``evidence_kind`` of its single
   nearest candidate by the same (distance, perk_overlap) ordering,
   computed ignoring the claim constraint — "which class would this roll
   have landed under, had capacity allowed."
6. A candidate left unclaimed after step 4 is reported
   ``unmatched_candidates``, bucketed under its own ``_derivation.
   evidence_kind`` (a candidate always carries one, regardless of hit or
   miss — that field comes from ``roll_text_evidence.json``, computed
   upstream of any binding decision).
7. A claimed pair where the candidate's ``_derivation.unfilled_fields``
   is non-empty is reported ``partial`` rather than ``matched`` (D-06:
   partial evidence is a first-class, honestly-reported outcome, never
   silently upgraded to a full match).

Every chapter/roll/candidate loop in this module iterates over an
explicitly ``sorted(...)`` sequence — never raw dict/set order — so
re-running this script against unchanged inputs produces a byte-identical
report (the ordering backstop must-have).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_paths import DERIVED, MANUAL
from multi_grab import load_overrides

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = (
    ROOT / ".planning" / "workstreams" / "curation" / "phases"
    / "03-provenance-schema-deterministic-candidate-assembly"
)
DEFAULT_CANDIDATES = DERIVED / "candidate_rolls.json"
DEFAULT_OVERRIDES = MANUAL / "chapter_roll_overrides.json"
DEFAULT_OUTPUT = REPORT_DIR / "candidate-accuracy-report.json"

EVIDENCE_CLASSES = ("direct", "general_only", "forward_ref", "no_evidence")

_METHOD = (
    "Per chapter present in both the non-stub curated corpus and "
    "candidate_rolls.json (the candidate/curated intersection): each "
    "curated roll gets a chapter-local position (its own word_position "
    "when non-null, else its 0-based ordinal rank in the curator's own "
    "rolls[] list) and is compared against every candidate in the "
    "chapter on the SAME scale (the candidate's real word_position when "
    "the curated side used a real word_position, else the candidate's "
    "own ordinal rank within its slot_index-sorted list). Pairs are "
    "scored by (position distance ascending, perk-name-overlap "
    "descending) -- position proximity is the PRIMARY signal, perk "
    "overlap only a tiebreaker -- and greedily assigned 1:1, most-certain "
    "pair first. This never compares roll_number/source_ordinal -- those "
    "predictor/curator sequences diverge by construction and are never "
    "used as a join key. A claimed pair whose candidate carries any "
    "_derivation.unfilled_fields is 'partial', not 'matched'. A curated "
    "roll left unclaimed is 'missed' (bucketed, for reporting only, "
    "under its single nearest candidate's evidence_kind, ignoring the "
    "claim constraint). A candidate left unclaimed is "
    "'unmatched_candidates', bucketed under its own evidence_kind."
)


# ---------------------------------------------------------------------------
# Stub-chapter derivation (D-09) — re-derived from data, never hardcoded.
# ---------------------------------------------------------------------------

def derive_stub_chapters(overrides_doc: dict) -> set[str]:
    """Chapters where every curated roll has an empty ``evidence_quotes``
    list -- generated placeholders, never hand-curated with narrative
    evidence. Excluded from the accuracy denominator (D-09). Re-derived
    live on every call; a chapter that gains real curation drops out
    automatically, with no chapter number special-cased anywhere here.
    """
    cro = overrides_doc.get("chapter_roll_overrides") or {}
    stubs: set[str] = set()
    for chapter_num, entry in cro.items():
        rolls = entry.get("rolls") or []
        # Vacuously true for a chapter with zero rolls (e.g. 55.1, whose
        # entry is {"rolls": []} with only model_validation_resolution
        # metadata) -- no rolls means no rolls carry evidence_quotes,
        # which is exactly D-09's predicate, not a special case of it.
        if all(not roll.get("evidence_quotes") for roll in rolls):
            stubs.add(str(chapter_num))
    return stubs


# ---------------------------------------------------------------------------
# Deterministic candidate-to-curated matching (Claude's Discretion, per
# 03-CONTEXT.md: "must be deterministic and documented"). Full algorithm
# is documented in this module's docstring above (_method); see that for
# the prose a future reader should use to re-derive this without reading
# the code.
# ---------------------------------------------------------------------------

def _normalized_perk_set(perks) -> set[str]:
    return {str(p).strip().lower() for p in (perks or []) if p}


def _curated_position(curated_rolls: list[dict], index: int) -> tuple[str, float]:
    word_position = curated_rolls[index].get("word_position")
    if word_position is not None:
        return ("word_position", float(word_position))
    return ("ordinal", float(index))


def _candidate_position(candidates: list[dict], index: int, mode: str) -> float:
    if mode == "word_position":
        word_position = candidates[index].get("word_position")
        return float(word_position) if word_position is not None else float(index)
    return float(index)


def match_candidates_to_curated(
    chapter_num: str, curated_rolls: list[dict], candidates: list[dict],
) -> dict:
    """Pair each curated roll in ``chapter_num`` to at most one candidate
    and vice versa. See the module docstring's ``_method`` prose for the
    full algorithm.

    Returns::

        {
          "curated_results": [
            {"index": i, "status": "matched"|"partial"|"missed",
             "evidence_kind_class": "direct"|"general_only"|
                                     "forward_ref"|"no_evidence"|None,
             "matched_candidate_index": int|None},
            ...  # one entry per curated_rolls[i], same order
          ],
          "unmatched_candidate_indices": [...],  # indices into
                                                  # "candidates_sorted"
          "candidates_sorted": [...],  # candidates, sorted by slot_index
        }
    """
    candidates = sorted(candidates, key=lambda c: c["slot_index"])
    n_curated = len(curated_rolls)
    n_candidates = len(candidates)

    def distance(i: int, j: int) -> float:
        mode, curated_pos = _curated_position(curated_rolls, i)
        candidate_pos = _candidate_position(candidates, j, mode)
        return abs(curated_pos - candidate_pos)

    def overlap(i: int, j: int) -> int:
        return len(
            _normalized_perk_set(curated_rolls[i].get("perks"))
            & _normalized_perk_set(candidates[j].get("perks"))
        )

    pairs = sorted(
        (distance(i, j), -overlap(i, j), i, j)
        for i in range(n_curated)
        for j in range(n_candidates)
    )

    claimed_curated: set[int] = set()
    claimed_candidate: set[int] = set()
    assignment: dict[int, int] = {}
    for _distance, _neg_overlap, i, j in pairs:
        if i in claimed_curated or j in claimed_candidate:
            continue
        claimed_curated.add(i)
        claimed_candidate.add(j)
        assignment[i] = j

    curated_results = []
    for i in range(n_curated):
        if i in assignment:
            j = assignment[i]
            derivation = candidates[j]["_derivation"]
            status = "partial" if derivation["unfilled_fields"] else "matched"
            curated_results.append({
                "index": i,
                "status": status,
                "evidence_kind_class": derivation["evidence_kind"],
                "matched_candidate_index": j,
            })
            continue

        # Missed: classify by the single nearest candidate, ignoring the
        # 1:1 claim constraint -- this is bucketing only, not a match.
        best_key = None
        best_j = None
        for j in range(n_candidates):
            key = (distance(i, j), -overlap(i, j), j)
            if best_key is None or key < best_key:
                best_key = key
                best_j = j
        evidence_kind_class = (
            candidates[best_j]["_derivation"]["evidence_kind"]
            if best_j is not None else None
        )
        curated_results.append({
            "index": i,
            "status": "missed",
            "evidence_kind_class": evidence_kind_class,
            "matched_candidate_index": None,
        })

    unmatched_candidate_indices = sorted(
        j for j in range(n_candidates) if j not in claimed_candidate
    )

    return {
        "curated_results": curated_results,
        "unmatched_candidate_indices": unmatched_candidate_indices,
        "candidates_sorted": candidates,
    }


# ---------------------------------------------------------------------------
# Per-evidence-class accuracy totals (D-08).
# ---------------------------------------------------------------------------

def _chapter_sort_key(chapter_num: str) -> float:
    try:
        return float(chapter_num)
    except ValueError:
        return 0.0


def compute_accuracy(overrides_doc: dict, candidates_doc: dict) -> dict:
    """Per-evidence-class totals: ``{"direct": {"curated_rolls": N,
    "matched": N, "partial": N, "missed": N, "unmatched_candidates": N},
    "general_only": {...}, "forward_ref": {...}, "no_evidence": {...}}``.

    Stub chapters (``derive_stub_chapters``) are excluded from the
    denominator entirely (D-09). Only chapters present in BOTH the
    non-stub curated corpus and ``candidates_doc`` are measured (the
    candidate/curated intersection). All iteration is over ``sorted(...)``
    sequences, never raw dict/set order, so re-running against unchanged
    inputs is byte-identical.
    """
    cro = overrides_doc.get("chapter_roll_overrides") or {}
    stub_chapters = derive_stub_chapters(overrides_doc)
    curated_chapters = {cn for cn in cro if cn not in stub_chapters}

    candidates_by_chapter: dict[str, list[dict]] = {}
    for candidate in candidates_doc.get("candidates") or []:
        candidates_by_chapter.setdefault(candidate["chapter_num"], []).append(candidate)

    totals = {
        evidence_class: {
            "curated_rolls": 0, "matched": 0, "partial": 0,
            "missed": 0, "unmatched_candidates": 0,
        }
        for evidence_class in EVIDENCE_CLASSES
    }

    intersection_chapters = sorted(
        (cn for cn in curated_chapters if cn in candidates_by_chapter),
        key=_chapter_sort_key,
    )

    for chapter_num in intersection_chapters:
        curated_rolls = cro[chapter_num].get("rolls") or []
        candidates = sorted(
            candidates_by_chapter[chapter_num], key=lambda c: c["slot_index"],
        )
        result = match_candidates_to_curated(chapter_num, curated_rolls, candidates)

        for entry in result["curated_results"]:
            evidence_class = entry["evidence_kind_class"]
            if evidence_class is None:
                continue
            totals[evidence_class]["curated_rolls"] += 1
            if entry["status"] == "matched":
                totals[evidence_class]["matched"] += 1
            elif entry["status"] == "partial":
                totals[evidence_class]["partial"] += 1
            else:
                totals[evidence_class]["missed"] += 1

        sorted_candidates = result["candidates_sorted"]
        for j in result["unmatched_candidate_indices"]:
            evidence_class = sorted_candidates[j]["_derivation"]["evidence_kind"]
            totals[evidence_class]["unmatched_candidates"] += 1

    return totals


# ---------------------------------------------------------------------------
# CLI — QA convenience wrapper, not DAG-wired (see module docstring).
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidates", type=Path, default=DEFAULT_CANDIDATES,
        help="Path to candidate_rolls.json (default: %(default)s)",
    )
    parser.add_argument(
        "--overrides", type=Path, default=DEFAULT_OVERRIDES,
        help="Path to chapter_roll_overrides.json (default: %(default)s)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Path for the JSON report (default: %(default)s)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    candidates_doc = json.loads(args.candidates.read_text())
    overrides_doc = load_overrides(args.overrides)

    by_evidence_class = compute_accuracy(overrides_doc, candidates_doc)
    stub_chapters = sorted(derive_stub_chapters(overrides_doc), key=_chapter_sort_key)

    chapter_roll_overrides = overrides_doc.get("chapter_roll_overrides") or {}
    total_curated_chapters = len(chapter_roll_overrides)
    total_curated_rolls = sum(
        len(entry.get("rolls") or []) for entry in chapter_roll_overrides.values()
    )
    total_candidates = len(candidates_doc.get("candidates") or [])

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    payload = {
        "_source": (
            "Stage 1 candidate-assembly accuracy measured against the "
            "hand-curated corpus (ACUR-01), per evidence class (D-08). "
            "Compares data/derived/candidate_rolls.json (Plan 03-02) "
            "against data/manual/chapter_roll_overrides.json (Plan "
            "03-01's schema-validated loader), excluding stub chapters "
            "(D-09)."
        ),
        "_method": _METHOD,
        "_stub_chapters_excluded": stub_chapters,
        "by_evidence_class": by_evidence_class,
        "_generated_from": {
            "candidates_path": _rel(args.candidates),
            "overrides_path": _rel(args.overrides),
            "total_candidates": total_candidates,
            "total_curated_chapters": total_curated_chapters,
            "total_curated_rolls": total_curated_rolls,
            "stub_chapters_excluded_count": len(stub_chapters),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    print(f"wrote {_rel(args.output)}")
    print(f"  stub chapters excluded: {len(stub_chapters)} -> {stub_chapters}")
    for evidence_class in EVIDENCE_CLASSES:
        counters = by_evidence_class[evidence_class]
        print(
            f"  {evidence_class}: curated_rolls={counters['curated_rolls']} "
            f"matched={counters['matched']} partial={counters['partial']} "
            f"missed={counters['missed']} "
            f"unmatched_candidates={counters['unmatched_candidates']}"
        )


if __name__ == "__main__":
    main()
