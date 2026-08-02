"""Build the regime-tagged exemplar index mined from the hand-curated corpus.

Mines ``data/manual/chapter_roll_overrides.json`` (the 118-chapter
hand-curated corpus) and tags each curated chapter with its CP regime,
sourced ONLY from the pipeline's existing regime computation:

  - Non-boundary chapters: ``data/derived/chapter_facts.json``'s
    ``point_calculation_regime`` field (D-01 — never recomputed here).
  - Boundary chapters (present in ``data/manual/regime_transitions.json``):
    both the pre-transition regime (via
    ``scripts.regime_simulator.regime_for_chapter``) and the post-transition
    regime (the transition's own ``new_regime`` field), plus an explicit
    ``is_boundary`` flag (D-02).

This script never opens the epub file or any epub prose text. Evidence
text in the output comes only from already-committed
``chapter_roll_overrides.json`` ``evidence_quotes`` (D-04).

Output: data/derived/exemplar_index.json

Usage
-----
    python scripts/build_exemplar_index.py [--overrides ...] [--chapter-facts ...]
                                            [--transitions ...] [--output ...]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

try:
    from chapter_roll_overrides_io import load_chapter_roll_overrides_doc
    from regime_simulator import regime_for_chapter
except ModuleNotFoundError:
    from scripts.chapter_roll_overrides_io import load_chapter_roll_overrides_doc
    from scripts.regime_simulator import regime_for_chapter

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OVERRIDES = ROOT / "data" / "manual" / "chapter_roll_overrides.json"
DEFAULT_CHAPTER_FACTS = ROOT / "data" / "derived" / "chapter_facts.json"
DEFAULT_TRANSITIONS = ROOT / "data" / "manual" / "regime_transitions.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "exemplar_index.json"

SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Chapter ordering helper (ordering only — NOT a regime computation; see
# scripts/multi_grab.py's identical _chapter_sort_key for the established
# pattern this mirrors).
# ---------------------------------------------------------------------------

def _chapter_sort_key(chapter_num: str) -> tuple[int, int]:
    parts = str(chapter_num).split(".")
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


# ---------------------------------------------------------------------------
# Chapter-facts lookup
# ---------------------------------------------------------------------------

def _chapter_facts_index(chapter_facts_doc: dict) -> dict[str, dict]:
    """Return {chapter_num: chapter_facts_entry} from chapter_facts.json's
    "chapters" LIST (not a dict — see plan interfaces note)."""
    chapters = chapter_facts_doc.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError(
            "chapter_facts.json must have a top-level 'chapters' list"
        )
    return {str(c["chapter_num"]): c for c in chapters}


def _transitions_index(transitions: list[dict]) -> dict[str, dict]:
    """Return {chapter_num: transition_entry}. Only a single documented
    transition per chapter exists today; if more ever appear, the first
    match wins (deterministic, matches iteration order)."""
    index: dict[str, dict] = {}
    for t in transitions:
        cn = str(t.get("chapter_num"))
        index.setdefault(cn, t)
    return index


# ---------------------------------------------------------------------------
# Regime tagging (D-01 / D-02) — never re-derives regime; only reads
# already-computed/already-curated values.
# ---------------------------------------------------------------------------

def _tag_chapter(
    chapter_num: str,
    chapter_facts_by_num: dict[str, dict],
    transitions_by_chapter: dict[str, dict],
) -> tuple[list[int], bool]:
    entry = chapter_facts_by_num.get(chapter_num)
    if entry is None:
        raise ValueError(
            f"chapter {chapter_num!r} is curated in chapter_roll_overrides.json "
            "but has no corresponding entry in chapter_facts.json"
        )

    primary_regime = entry["point_calculation_regime"]
    boundary_entry = transitions_by_chapter.get(chapter_num)

    if boundary_entry is None:
        return sorted({int(primary_regime)}), False

    # Per D-01/D-02 (and RESEARCH.md Pattern 3 / Pitfall 1): the boundary
    # case reads regime_simulator.regime_for_chapter() directly for the
    # PRE-transition regime rather than trusting chapter_facts.json's
    # single-value point_calculation_regime field, which is currently
    # buggy for ch97 (build_chapter_facts.py's own duplicate/out-of-sync
    # regime_for_chapter — see RESEARCH.md Pitfall 1, deliberately not
    # fixed in this plan). This recipe is correct regardless of that bug.
    pre_transition_regime = regime_for_chapter(chapter_num)
    post_transition_regime = int(boundary_entry["new_regime"])
    tags = sorted({pre_transition_regime, post_transition_regime})
    return tags, True


# ---------------------------------------------------------------------------
# Roll-level record (D-04 — evidence text sourced only from the override)
# ---------------------------------------------------------------------------

def _roll_cp_ledger_checkpoint(roll: dict) -> dict | None:
    """Surface a roll's cp_ledger_checkpoint if any of its evidence_quotes
    carry one (the schema nests this metadata on the quote, not the roll
    itself — see scripts/derive_roll_facts.py's _apply_cp_ledger_checkpoints
    and chapter_roll_overrides.json's own _purpose docstring). This is a
    passthrough of already-curated data, not a computation."""
    for quote in roll.get("evidence_quotes") or []:
        if not isinstance(quote, dict):
            continue
        checkpoint = quote.get("cp_ledger_checkpoint")
        if isinstance(checkpoint, dict):
            return checkpoint
    return None


def _build_roll_record(roll: dict, roll_index: int) -> dict:
    if not isinstance(roll, dict):
        raise ValueError(
            f"roll entry at index {roll_index} must be dict, got {type(roll).__name__}"
        )
    evidence_quotes = roll.get("evidence_quotes") or []
    return {
        "roll_index": roll_index,
        "perks": list(roll.get("perks") or []),
        "outcome": roll.get("outcome"),
        "constellation": roll.get("constellation"),
        "display_position_policy": roll.get("display_position_policy"),
        "evidence_quote_count": len(evidence_quotes),
        "evidence_quotes": evidence_quotes,
        "cp_ledger_checkpoint": _roll_cp_ledger_checkpoint(roll),
    }


def _build_exemplar(
    chapter_num: str,
    entry: dict,
    chapter_facts_by_num: dict[str, dict],
    transitions_by_chapter: dict[str, dict],
) -> dict:
    regime_tags, is_boundary = _tag_chapter(
        chapter_num, chapter_facts_by_num, transitions_by_chapter,
    )
    rolls = entry.get("rolls") or []
    roll_records = [
        _build_roll_record(roll, idx) for idx, roll in enumerate(rolls)
    ]
    return {
        "chapter_num": chapter_num,
        "regime_tags": regime_tags,
        "is_boundary": is_boundary,
        "rolls": roll_records,
    }


# ---------------------------------------------------------------------------
# Statistics (D-05 machine-readable half)
# ---------------------------------------------------------------------------

def _compute_statistics(exemplars: list[dict]) -> dict:
    regime_distribution: Counter[str] = Counter()
    boundary_chapters: list[str] = []
    roll_shape_distribution: Counter[str] = Counter()
    display_position_policy_distribution: Counter[str] = Counter()
    evidence_quote_counts: list[int] = []
    cp_ledger_checkpoint_usage_count = 0

    for exemplar in exemplars:
        for tag in exemplar["regime_tags"]:
            regime_distribution[str(tag)] += 1
        if exemplar["is_boundary"]:
            boundary_chapters.append(exemplar["chapter_num"])
        for roll in exemplar["rolls"]:
            roll_shape_distribution[str(len(roll["perks"]))] += 1
            policy = roll["display_position_policy"]
            display_position_policy_distribution[
                "null" if policy is None else str(policy)
            ] += 1
            evidence_quote_counts.append(roll["evidence_quote_count"])
            if roll["cp_ledger_checkpoint"] is not None:
                cp_ledger_checkpoint_usage_count += 1

    if evidence_quote_counts:
        evidence_quote_stats = {
            "min": min(evidence_quote_counts),
            "max": max(evidence_quote_counts),
            "mean": sum(evidence_quote_counts) / len(evidence_quote_counts),
            "total": sum(evidence_quote_counts),
        }
    else:
        evidence_quote_stats = {"min": 0, "max": 0, "mean": 0.0, "total": 0}

    return {
        "chapter_count": len(exemplars),
        "regime_distribution": dict(sorted(regime_distribution.items())),
        "boundary_chapters": sorted(boundary_chapters, key=_chapter_sort_key),
        "roll_shape_distribution": dict(sorted(
            roll_shape_distribution.items(), key=lambda kv: int(kv[0])
        )),
        "display_position_policy_distribution": dict(
            sorted(display_position_policy_distribution.items())
        ),
        "evidence_quote_stats": evidence_quote_stats,
        "cp_ledger_checkpoint_usage_count": cp_ledger_checkpoint_usage_count,
    }


# ---------------------------------------------------------------------------
# Pure build entry point
# ---------------------------------------------------------------------------

def build_index(
    overrides_doc: dict,
    chapter_facts_doc: dict,
    transitions: list[dict],
) -> dict:
    """Pure function: build the full exemplar_index.json payload.

    Raises ValueError loudly on malformed input rather than silently
    producing an empty/partial index (V5 input validation).
    """
    if "chapter_roll_overrides" not in overrides_doc:
        raise ValueError(
            "chapter_roll_overrides.json missing its top-level "
            "'chapter_roll_overrides' key"
        )

    chapter_roll_overrides = overrides_doc["chapter_roll_overrides"]
    chapter_facts_by_num = _chapter_facts_index(chapter_facts_doc)
    transitions_by_chapter = _transitions_index(transitions)

    chapter_nums = sorted(chapter_roll_overrides.keys(), key=_chapter_sort_key)
    exemplars = [
        _build_exemplar(
            chapter_num,
            chapter_roll_overrides[chapter_num],
            chapter_facts_by_num,
            transitions_by_chapter,
        )
        for chapter_num in chapter_nums
    ]

    statistics = _compute_statistics(exemplars)

    return {
        "schema_version": SCHEMA_VERSION,
        "exemplars": exemplars,
        "statistics": statistics,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--overrides",
        type=Path,
        default=DEFAULT_OVERRIDES,
        help="Path to chapter_roll_overrides.json (default: %(default)s)",
    )
    p.add_argument(
        "--chapter-facts",
        type=Path,
        default=DEFAULT_CHAPTER_FACTS,
        help="Path to chapter_facts.json (default: %(default)s)",
    )
    p.add_argument(
        "--transitions",
        type=Path,
        default=DEFAULT_TRANSITIONS,
        help="Path to regime_transitions.json (default: %(default)s)",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for output file (default: %(default)s)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    overrides_doc = load_chapter_roll_overrides_doc(args.overrides)
    chapter_facts_doc = json.loads(args.chapter_facts.read_text())
    transitions_doc = json.loads(args.transitions.read_text())
    transitions = list(transitions_doc.get("transitions") or [])

    payload = build_index(overrides_doc, chapter_facts_doc, transitions)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    stats = payload["statistics"]
    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"  exemplar chapter count:        {stats['chapter_count']}")
    print(f"  regime distribution:           {stats['regime_distribution']}")
    print(f"  boundary chapters:             {stats['boundary_chapters']}")
    print(f"  roll shape distribution:       {stats['roll_shape_distribution']}")
    print(
        "  evidence quote stats (per roll): "
        f"{stats['evidence_quote_stats']}"
    )
    print(
        f"  cp_ledger_checkpoint usage count: "
        f"{stats['cp_ledger_checkpoint_usage_count']}"
    )


if __name__ == "__main__":
    main()
