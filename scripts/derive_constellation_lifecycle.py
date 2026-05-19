"""Derive per-constellation lifecycle milestones.

For each of the 14 cluster-constellations, compute:
  - revealed_at_chapter   : first chapter where the constellation appears in
                             `revealed_in_chapter` (from constellation_knowledge_by_chapter)
  - completed_at_chapter  : first chapter where the constellation was non-empty
                             in before_chapter.by_constellation AND absent/empty
                             in after_chapter.by_constellation (from outstanding_perks_by_chapter)
  - entered_pool_at_chapter: same as revealed_at_chapter for slots 1–12;
                             hardcoded "62" for slots 13 (Capstone) and 14 (Personal Reality)

Constellation names are extracted from the <title> element of each cluster's
`data/constellations/NN-<slug>/current.svg`.  The slug folder prefix encodes
the slot position.

Reads:
  data/derived/constellation_knowledge_by_chapter.json
  data/derived/outstanding_perks_by_chapter.json
  data/constellations/NN-<slug>/current.svg  (for each of the 14 cluster folders)

Writes:
  data/derived/constellation_lifecycle.json
  data/derived/_schemas/constellation_lifecycle.schema.json  (pre-exists; not re-written here)

Usage
-----
    python3 scripts/derive_constellation_lifecycle.py [--knowledge ...] [--outstanding ...] [--output ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_KNOWLEDGE    = ROOT / "data" / "derived" / "constellation_knowledge_by_chapter.json"
DEFAULT_OUTSTANDING  = ROOT / "data" / "derived" / "outstanding_perks_by_chapter.json"
DEFAULT_CONSTELLATIONS_DIR = ROOT / "data" / "constellations"
DEFAULT_OUTPUT       = ROOT / "data" / "derived" / "constellation_lifecycle.json"

SCHEMA_VERSION = 1
POOL_OVERRIDE_CHAPTER = "62"
POOL_OVERRIDE_SLOTS = {13, 14}

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)


def _extract_svg_title(svg_path: Path) -> str:
    text = svg_path.read_text(encoding="utf-8")
    m = _TITLE_RE.search(text)
    if not m:
        raise ValueError(f"No <title> element found in {svg_path}")
    return m.group(1).strip()


def _collect_slugs(constellations_dir: Path) -> list[str]:
    """Return the 14 cluster slug folder names sorted by slot_position."""
    slugs = []
    for entry in constellations_dir.iterdir():
        if not entry.is_dir():
            continue
        parts = entry.name.split("-", 1)
        if len(parts) == 2 and parts[0].isdigit():
            slugs.append(entry.name)
    return sorted(slugs, key=lambda s: int(s.split("-", 1)[0]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive per-constellation lifecycle milestones.",
    )
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=DEFAULT_KNOWLEDGE,
        metavar="PATH",
        help="Path to constellation_knowledge_by_chapter.json (default: %(default)s)",
    )
    parser.add_argument(
        "--outstanding",
        type=Path,
        default=DEFAULT_OUTSTANDING,
        metavar="PATH",
        help="Path to outstanding_perks_by_chapter.json (default: %(default)s)",
    )
    parser.add_argument(
        "--constellations-dir",
        type=Path,
        default=DEFAULT_CONSTELLATIONS_DIR,
        metavar="PATH",
        help="Path to the data/constellations/ directory (default: %(default)s)",
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
    # 1. Collect the 14 cluster slug folders and extract names from SVG.
    # ------------------------------------------------------------------
    slugs = _collect_slugs(args.constellations_dir)

    failures: list[str] = []

    if len(slugs) != 14:
        failures.append(
            f"Expected exactly 14 cluster folders, found {len(slugs)}: {slugs}"
        )

    # Map slug → name (via SVG <title>), and build slot_position list.
    slug_to_name: dict[str, str] = {}
    slug_to_slot: dict[str, int] = {}
    for slug in slugs:
        slot = int(slug.split("-", 1)[0])
        slug_to_slot[slug] = slot
        svg_path = args.constellations_dir / slug / "current.svg"
        if not svg_path.exists():
            failures.append(f"Missing current.svg for slug '{slug}' at {svg_path}")
            continue
        try:
            slug_to_name[slug] = _extract_svg_title(svg_path)
        except ValueError as exc:
            failures.append(str(exc))

    # Validate slot positions are 1..14 with no gaps or duplicates.
    observed_slots = sorted(slug_to_slot.values())
    if observed_slots != list(range(1, 15)):
        failures.append(
            f"Slot positions are not exactly 1..14; got {observed_slots}"
        )

    if failures:
        print("VALIDATION FAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 2. Build reverse map: name → slug.
    # ------------------------------------------------------------------
    name_to_slug: dict[str, str] = {v: k for k, v in slug_to_name.items()}

    # ------------------------------------------------------------------
    # 3. Derive revealed_at_chapter from constellation_knowledge_by_chapter.
    # ------------------------------------------------------------------
    knowledge_data = json.loads(args.knowledge.read_text(encoding="utf-8"))
    revealed_at: dict[str, str] = {}  # name → chapter_num string

    for chapter in knowledge_data["chapters"]:
        chapter_num = chapter["chapter_num"]
        for name in chapter.get("revealed_in_chapter", []):
            if name not in revealed_at:
                revealed_at[name] = chapter_num

    # ------------------------------------------------------------------
    # 4. Derive completed_at_chapter from outstanding_perks_by_chapter.
    # ------------------------------------------------------------------
    outstanding_data = json.loads(args.outstanding.read_text(encoding="utf-8"))
    completed_at: dict[str, str] = {}  # name → chapter_num string

    for chapter in outstanding_data["chapters"]:
        chapter_num = chapter["chapter_num"]
        before_by_const = chapter["before_chapter"]["by_constellation"]
        after_by_const  = chapter["after_chapter"]["by_constellation"]

        for name, perks_before in before_by_const.items():
            if not perks_before:
                # was already empty before; not a completion event
                continue
            perks_after = after_by_const.get(name, [])
            if not perks_after:
                # non-empty before → empty/absent after → first completion
                if name not in completed_at:
                    completed_at[name] = chapter_num

    # ------------------------------------------------------------------
    # 5. Validate that every constellation has a revealed_at_chapter.
    # ------------------------------------------------------------------
    all_names = list(slug_to_name.values())
    missing_revealed = [n for n in all_names if n not in revealed_at]
    if missing_revealed:
        failures.append(
            f"The following constellations have no revealed_at_chapter: {missing_revealed}"
        )

    if failures:
        print("VALIDATION FAILURES:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    # ------------------------------------------------------------------
    # 6. Assemble output payload ordered by slot_position.
    # ------------------------------------------------------------------
    records = []
    for slug in slugs:  # already sorted by slot_position
        name = slug_to_name[slug]
        slot = slug_to_slot[slug]
        revealed = revealed_at[name]
        completed = completed_at.get(name, None)
        entered_pool = POOL_OVERRIDE_CHAPTER if slot in POOL_OVERRIDE_SLOTS else revealed

        records.append(
            {
                "name": name,
                "slug": slug,
                "slot_position": slot,
                "revealed_at_chapter": revealed,
                "completed_at_chapter": completed,
                "entered_pool_at_chapter": entered_pool,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "_source": (
            "derived from constellation_knowledge_by_chapter"
            " + outstanding_perks_by_chapter"
            " + data/constellations/ folder names"
        ),
        "constellations": records,
    }

    # ------------------------------------------------------------------
    # 7. Validate and write.
    # ------------------------------------------------------------------
    # Use the project's shared helper (validates against the schema before writing).
    sys.path.insert(0, str(ROOT / "scripts"))
    from _common import write_validated_json  # noqa: E402

    write_validated_json(args.output, payload, "constellation_lifecycle")
    print(f"Wrote {len(records)} constellation lifecycle records to {args.output}")


if __name__ == "__main__":
    main()
