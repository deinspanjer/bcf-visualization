"""Derive per-chapter constellation-knowledge snapshots.

For each chapter, compute which constellation names Joe knows *before* that
chapter begins, which were *revealed* in that chapter (i.e. their first-ever
perk acquisition), and which he knows *after* the chapter ends.

Reads:
  - data/derived/obtained_perks.json   (504 perks in epub_sequence order)
  - data/derived/chapters.json         (canonical chapter ordering via sort_key)

Writes:
  - data/derived/constellation_knowledge_by_chapter.json

The output supports roll/context displays that need to know which
constellation names Joe knows at a given chapter boundary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OBTAINED = ROOT / "data" / "derived" / "obtained_perks.json"
DEFAULT_CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
DEFAULT_OUTPUT   = ROOT / "data" / "derived" / "constellation_knowledge_by_chapter.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive per-chapter constellation-knowledge snapshots.",
    )
    parser.add_argument(
        "--obtained",
        type=Path,
        default=DEFAULT_OBTAINED,
        metavar="PATH",
        help="Path to obtained_perks.json (default: %(default)s)",
    )
    parser.add_argument(
        "--chapters",
        type=Path,
        default=DEFAULT_CHAPTERS,
        metavar="PATH",
        help="Path to chapters.json (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help="Path to write output JSON (default: %(default)s)",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # 1. Load and sort perks by epub_sequence (ascending).
    # ------------------------------------------------------------------
    obtained_data = json.loads(args.obtained.read_text())
    perks = obtained_data["perks"]
    perks.sort(key=lambda p: p["epub_sequence"])

    # ------------------------------------------------------------------
    # 2. Build a map: constellation → chapter_num of first acquisition.
    #    We skip perks where constellation is null/missing.
    # ------------------------------------------------------------------
    first_seen: dict[str, str] = {}   # constellation → chapter_num
    for perk in perks:
        constellation = perk.get("constellation")
        if not constellation:
            continue
        if constellation not in first_seen:
            first_seen[constellation] = perk["chapter_num"]

    # ------------------------------------------------------------------
    # 3. Load chapters in canonical order (sort_key is [major, minor]).
    # ------------------------------------------------------------------
    chapters_data = json.loads(args.chapters.read_text())
    chapters = sorted(
        chapters_data["chapters"],
        key=lambda c: tuple(c["sort_key"]),
    )

    # ------------------------------------------------------------------
    # 4. Build per-chapter reveal sets.
    #    revealed_in[chapter_num] = sorted list of constellations whose
    #    first hit is in that chapter.
    # ------------------------------------------------------------------
    revealed_in: dict[str, list[str]] = {}
    for constellation, chap_num in first_seen.items():
        revealed_in.setdefault(chap_num, []).append(constellation)
    # Sort each list for determinism.
    for chap_num in revealed_in:
        revealed_in[chap_num].sort()

    # ------------------------------------------------------------------
    # 5. Walk chapters in order, maintaining a running "known" set.
    # ------------------------------------------------------------------
    out_chapters: list[dict] = []
    known: set[str] = set()

    for c in chapters:
        cn = c["chapter_num"]
        before = sorted(known)
        newly = revealed_in.get(cn, [])
        known.update(newly)
        after = sorted(known)

        out_chapters.append({
            "chapter_num": cn,
            "before_chapter_known": before,
            "revealed_in_chapter": newly,
            "after_chapter_known": after,
        })

    # ------------------------------------------------------------------
    # 6. Build and write the output payload.
    # ------------------------------------------------------------------
    payload = {
        "schema_version": 1,
        "chapters": out_chapters,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )

    # ------------------------------------------------------------------
    # 7. Print a brief summary.
    # ------------------------------------------------------------------
    total_chapters = len(out_chapters)
    total_constellations = len(first_seen)

    # Collect the first 10 reveal events in chapter order.
    first_10_reveals: list[tuple[str, str]] = []
    for c in out_chapters:
        for constellation in c["revealed_in_chapter"]:
            first_10_reveals.append((c["chapter_num"], constellation))
            if len(first_10_reveals) >= 10:
                break
        if len(first_10_reveals) >= 10:
            break

    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"  chapters: {total_chapters}")
    print(f"  unique constellations revealed total: {total_constellations}")
    print("  first 10 reveal events (chapter_num, constellation):")
    for chap_num, constellation in first_10_reveals:
        print(f"    ch {chap_num:>6s}: {constellation}")


if __name__ == "__main__":
    main()
