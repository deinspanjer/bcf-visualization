"""Deterministic same-regime exemplar retrieval (D-06).

Pure module — no argparse, no file I/O in the retrieval path. Takes an
already-loaded exemplar_index.json dict and returns a filtered/ranked
subset. No embeddings, no fuzzy similarity, no LLM: retrieve() is a plain,
deterministic filter + sort over ``index["exemplars"]``.

Phase 3 imports ``retrieve()`` directly; the thin ``__main__`` block below
is for manual debugging only.
"""

from __future__ import annotations


def _chapter_sort_key(chapter_num: str) -> tuple[int, int]:
    parts = str(chapter_num).split(".")
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _chapter_ordinal(chapter_num: str) -> float:
    """A single float ordinal for proximity distance. Chapter minors are
    small (single-digit sub-chapter markers, e.g. "95.5") so major +
    minor/100 preserves ordering and gives a well-defined distance."""
    major, minor = _chapter_sort_key(chapter_num)
    return major + minor / 100.0


def retrieve(
    target_regime: int,
    index: dict,
    *,
    k: int | None = None,
    target_chapter: str | None = None,
) -> list[dict]:
    """Return exemplars whose regime_tags intersect target_regime.

    Deterministic: filters to entries where ``target_regime`` appears in
    ``entry["regime_tags"]`` (a boundary-tagged entry with regime_tags ==
    [2, 3] is returned for BOTH target_regime=2 and target_regime=3
    queries), then sorts deterministically — by proximity to
    ``target_chapter`` when given (numeric chapter-distance ascending,
    chapter_num ascending as tie-break), otherwise by chapter_num
    ascending. Truncates to ``k`` entries if given.

    Never returns an exemplar whose regime_tags does not intersect
    target_regime.
    """
    exemplars = index.get("exemplars", [])
    candidates = [
        entry for entry in exemplars
        if target_regime in entry.get("regime_tags", [])
    ]

    if target_chapter is not None:
        target_ordinal = _chapter_ordinal(target_chapter)

        def _proximity_key(entry: dict) -> tuple[float, tuple[int, int]]:
            distance = abs(_chapter_ordinal(entry["chapter_num"]) - target_ordinal)
            return (distance, _chapter_sort_key(entry["chapter_num"]))

        candidates.sort(key=_proximity_key)
    else:
        candidates.sort(key=lambda entry: _chapter_sort_key(entry["chapter_num"]))

    if k is not None:
        return candidates[:k]
    return candidates


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent.parent
    DEFAULT_INDEX = ROOT / "data" / "derived" / "exemplar_index.json"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--regime", type=int, required=True)
    parser.add_argument("--k", type=int, default=None)
    parser.add_argument("--target-chapter", type=str, default=None)
    args = parser.parse_args()

    loaded_index = json.loads(args.index.read_text())
    results = retrieve(
        args.regime, loaded_index, k=args.k, target_chapter=args.target_chapter,
    )
    print(json.dumps(results, indent=2, ensure_ascii=False))
