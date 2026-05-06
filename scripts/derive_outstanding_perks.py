"""Derive per-chapter outstanding perk snapshots.

"Outstanding" perks at a given chapter boundary are those in the full
perk catalog that have NOT yet been acquired by Joe — i.e., the perks
that COULD be the target of the next author-side roll.

For each chapter we emit two snapshots:

  before_chapter  — full catalog minus perks acquired in chapters
                    STRICTLY BEFORE this one (acquisition order uses the
                    chapter ordering from chapters.json, not lexicographic
                    sort).

  after_chapter   — full catalog minus perks acquired in chapters BEFORE
                    OR EQUAL TO this one.

Output: data/derived/outstanding_perks_by_chapter.json

Usage
-----
    python scripts/derive_outstanding_perks.py [--catalog ...] [--acquired ...]
                                                [--chapters ...] [--output ...]
"""

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


# ---------------------------------------------------------------------------
# Normalisation helper
# ---------------------------------------------------------------------------

def _norm(s: str | None) -> str:
    """Case-insensitive, whitespace-stripped normalisation for name matching."""
    if not s:
        return ""
    return s.strip().lower()


# ---------------------------------------------------------------------------
# Chapter ordering helper
# ---------------------------------------------------------------------------

def _chapter_index(chapter_order: list[str]) -> dict[str, int]:
    """Return {chapter_num: position} for the given ordered list."""
    return {ch: i for i, ch in enumerate(chapter_order)}


# ---------------------------------------------------------------------------
# Build outstanding snapshot
# ---------------------------------------------------------------------------

def _build_snapshot(catalog: list[dict], acquired_at_or_before: set[str]) -> dict:
    """Return a snapshot dict with total_count and by_constellation.

    catalog        — list of {name, cost, constellation, acquired_chapter_num}
    acquired_at_or_before — set of perk names (normalised) that have been
                    acquired at or before the relevant boundary.

    A perk is outstanding if its acquired_chapter_num is NOT in the set of
    chapters at or before the boundary.  Equivalently, perks with no
    acquired_chapter_num are always outstanding; perks whose
    acquired_chapter_num maps to a chapter AFTER the boundary are still
    outstanding.

    In practice we pass the set of chapter_nums that count as "acquired"
    for this boundary — perks whose acquired_chapter_num is in that set
    are NOT outstanding.

    We group by constellation, sort within each constellation by cost
    ascending then name ascending, and omit constellations with no
    outstanding perks.
    """
    by_constellation: dict[str, list[dict]] = {}
    for perk in catalog:
        if perk["acquired_chapter_num"] in acquired_at_or_before:
            # This perk has been acquired at or before this boundary — skip.
            continue
        constellation = perk["constellation"]
        entry = {"name": perk["name"], "cost": perk["cost"]}
        by_constellation.setdefault(constellation, []).append(entry)

    # Sort within each constellation: cost asc, then name asc.
    # None costs sort last (treat as infinity).
    for entries in by_constellation.values():
        entries.sort(key=lambda e: (
            e["cost"] if e["cost"] is not None else float("inf"),
            e["name"],
        ))

    total = sum(len(v) for v in by_constellation.values())
    return {
        "total_count": total,
        "by_constellation": by_constellation,
    }


# ---------------------------------------------------------------------------
# Unmatched obtained-perk reporter
# ---------------------------------------------------------------------------

def _find_unmatched(
    obtained_perks: list[dict],
    catalog_names_norm: set[str],
) -> list[str]:
    """Return a deduplicated list of obtained perk names that do not
    case-insensitively match any catalog entry name.

    Free perks frequently have unusual/variant names and are expected to
    be missing from the rollable catalog; we report them regardless so
    the caller can decide what to log.
    """
    unmatched: list[str] = []
    seen: set[str] = set()
    for op in obtained_perks:
        name = op.get("perk_name", "")
        nn = _norm(name)
        if nn not in catalog_names_norm and nn not in seen:
            unmatched.append(name)
            seen.add(nn)
    return unmatched


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Path to perk_directory.json (default: %(default)s)",
    )
    p.add_argument(
        "--acquired",
        type=Path,
        default=DEFAULT_ACQUIRED,
        help="Path to obtained_perks.json (default: %(default)s)",
    )
    p.add_argument(
        "--chapters",
        type=Path,
        default=DEFAULT_CHAPTERS,
        help="Path to chapters.json (default: %(default)s)",
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

    # ------------------------------------------------------------------
    # Load inputs
    # ------------------------------------------------------------------
    raw_catalog = json.loads(args.catalog.read_text())
    raw_acquired = json.loads(args.acquired.read_text())
    raw_chapters = json.loads(args.chapters.read_text())

    # perk_directory.json uses the key "perks"
    all_perks_raw: list[dict] = raw_catalog["perks"]

    # Extract the fields we care about from the catalog.  perk_directory
    # already carries acquired_chapter_num (set by the sophisticated
    # build_perk_directory pipeline); we use that for accurate per-chapter
    # attribution rather than re-doing name matching here.
    catalog: list[dict] = [
        {
            "name": p["name"],
            "cost": p.get("cost"),
            "constellation": p["constellation"],
            # None when not yet acquired; a chapter_num string when acquired.
            "acquired_chapter_num": p.get("acquired_chapter_num"),
        }
        for p in all_perks_raw
    ]

    catalog_size = len(catalog)

    # Build a set of normalised catalog names for the unmatched check.
    catalog_names_norm: set[str] = {_norm(p["name"]) for p in catalog}

    # obtained_perks sorted by epub_sequence (already narrative order, but
    # sort defensively in case the file ever drifts).
    obtained_perks: list[dict] = sorted(
        raw_acquired["perks"],
        key=lambda op: op.get("epub_sequence", 0),
    )

    # ------------------------------------------------------------------
    # Chapter ordering — use chapters.json order (NOT lexicographic sort)
    # ------------------------------------------------------------------
    chapter_order: list[str] = [
        c["chapter_num"] for c in raw_chapters["chapters"]
    ]
    chapter_pos = _chapter_index(chapter_order)

    # ------------------------------------------------------------------
    # Unmatched obtained-perk check (log to stderr, do not abort)
    # ------------------------------------------------------------------
    unmatched_names = _find_unmatched(obtained_perks, catalog_names_norm)
    if unmatched_names:
        print(
            f"WARNING: {len(unmatched_names)} obtained perk name(s) do not match "
            "any catalog entry by case-insensitive name — they will not be "
            "subtracted from the outstanding set (this is expected for "
            "free/variant perks):",
            file=sys.stderr,
        )
        for name in unmatched_names:
            print(f"  - {name!r}", file=sys.stderr)

    # ------------------------------------------------------------------
    # Build per-chapter snapshots
    # ------------------------------------------------------------------
    # We precompute for each chapter: the set of acquired_chapter_nums that
    # are "at or before" it (for after_chapter) and "strictly before" it
    # (for before_chapter).
    #
    # A catalog perk's acquired_chapter_num tells us exactly which chapter
    # it was acquired in (authoritative from perk_directory matching).
    # A perk is OUTSTANDING at a given boundary iff its acquired_chapter_num
    # is NOT in the set of chapters at/before that boundary.
    #
    # Rather than recomputing a position lookup for every perk on every chapter,
    # we build the snapshot incrementally: start with all perks outstanding,
    # and as we step through chapters in order we remove perks acquired in
    # each chapter.

    # Group catalog perks by acquired_chapter_num (None = never acquired).
    from collections import defaultdict

    acquired_by_chapter: dict[str | None, list[dict]] = defaultdict(list)
    for perk in catalog:
        acquired_by_chapter[perk["acquired_chapter_num"]].append(perk)

    # The "acquired_so_far" set grows as we step through chapters.
    # We represent the outstanding set as: catalog perks whose
    # acquired_chapter_num is NOT in acquired_chapters_so_far.
    #
    # For efficiency we track acquired_chapters_so_far as a set of
    # chapter_num strings, then use it directly in _build_snapshot.
    acquired_chapters_so_far: set[str] = set()

    out_chapters: list[dict] = []

    for chapter_num in chapter_order:
        # BEFORE snapshot: outstanding = catalog minus perks acquired in
        # chapters strictly before this one. At this point
        # acquired_chapters_so_far contains exactly those prior chapters.
        before_snapshot = _build_snapshot(
            catalog,
            acquired_chapters_so_far,
        )

        # Add this chapter's acquisitions to the "so far" set.
        acquired_chapters_so_far.add(chapter_num)

        # AFTER snapshot: outstanding = catalog minus perks acquired in
        # chapters at or before this one (now including this chapter).
        after_snapshot = _build_snapshot(
            catalog,
            acquired_chapters_so_far,
        )

        out_chapters.append({
            "chapter_num": chapter_num,
            "before_chapter": before_snapshot,
            "after_chapter": after_snapshot,
        })

    # ------------------------------------------------------------------
    # Verification tallies (for stdout summary)
    # ------------------------------------------------------------------
    # total_obtained_matched: catalog perks whose acquired_chapter_num is
    # a recognised chapter (i.e., perk_directory matched them to an
    # obtained acquisition).
    total_obtained_matched = sum(
        1 for p in catalog if p["acquired_chapter_num"] is not None
    )
    final_outstanding = out_chapters[-1]["after_chapter"]["total_count"]
    expected_final = catalog_size - total_obtained_matched

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    payload = {
        "schema_version": SCHEMA_VERSION,
        "chapters": out_chapters,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # stdout summary
    # ------------------------------------------------------------------
    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"  chapter count:                 {len(out_chapters)}")
    print(f"  catalog size:                  {catalog_size}")
    print(f"  catalog perks matched/acquired:{total_obtained_matched}")
    print(
        f"  final chapter after outstanding: {final_outstanding} "
        f"(expected {expected_final})"
    )
    if final_outstanding != expected_final:
        print(
            f"  WARNING: final outstanding {final_outstanding} != "
            f"expected {expected_final}",
            file=sys.stderr,
        )

    if unmatched_names:
        print(f"  unmatched obtained perk names: {len(unmatched_names)}")
        print("  (see stderr for the full list)")
    else:
        print("  unmatched obtained perk names: 0")


if __name__ == "__main__":
    main()
