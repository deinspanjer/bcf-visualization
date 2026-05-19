#!/usr/bin/env python3
"""
migrate_vertex_source.py

Two-pass atomic migration that:
  Pass 1 (dry): Resolves data-vertex-source for all 14 constellation SVGs by
    comparing <use href="#star-mark"> marker counts against jump/perk counts
    from data/derived/perk_directory.json. Halts on ANY unresolved cluster and
    reports ALL failures at once — no file is written.
  Pass 2 (write): Injects data-vertex-source="<inferred>" on the root <svg>
    element immediately after the viewBox attribute.

Also writes data/constellations/NN-<slug>/metadata.json sidecars with:
  {"schema_version": 1, "intended_image": "..."}
  where intended_image is parsed from index.html <p class="shape-concept">.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CONSTELLATIONS_DIR = REPO_ROOT / "data" / "constellations"
PERK_DIRECTORY = REPO_ROOT / "data" / "derived" / "perk_directory.json"

# Folders that are not cluster folders
_NON_CLUSTER_NAMES = {"index.html", "tracing-workbench.html"}


def iter_cluster_dirs():
    """Yield (folder_path, slug) for each of the 14 cluster directories."""
    for path in sorted(CONSTELLATIONS_DIR.iterdir()):
        if path.name in _NON_CLUSTER_NAMES:
            continue
        if path.is_dir():
            yield path, path.name


# ---------------------------------------------------------------------------
# SVG marker counting
# ---------------------------------------------------------------------------
_STAR_MARK_RE = re.compile(r'href="#star-mark"')


def count_star_marks(svg_path: Path) -> int:
    content = svg_path.read_text(encoding="utf-8")
    return len(_STAR_MARK_RE.findall(content))


def get_svg_title(svg_path: Path) -> str:
    content = svg_path.read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", content)
    if not m:
        raise ValueError(f"No <title> found in {svg_path}")
    return m.group(1)


# ---------------------------------------------------------------------------
# Perk directory counts
# ---------------------------------------------------------------------------
def build_constellation_counts(perk_directory_path: Path):
    """Return {constellation_name: {"jumps": int, "perks": int}} excluding Felyne Perks."""
    data = json.loads(perk_directory_path.read_text(encoding="utf-8"))
    perks = data["perks"]

    jump_sets = defaultdict(set)
    perk_counts = defaultdict(int)

    for p in perks:
        c = p["constellation"]
        if c == "Felyne Perks":
            continue
        jump_sets[c].add(p["jump"])
        perk_counts[c] += 1

    return {
        c: {"jumps": len(jump_sets[c]), "perks": perk_counts[c]}
        for c in jump_sets
    }


# ---------------------------------------------------------------------------
# vertex_source resolution
# ---------------------------------------------------------------------------
_DESC_RE = re.compile(r"<desc>(.*?)</desc>", re.DOTALL)


def get_svg_desc_vertex_source(svg_path: Path):
    """
    Fallback: parse <desc> text and return 'jumps' or 'perks' if unambiguous, else None.
    The desc format is: "<Name> as a constellation of its N <jumps|perks>. ..."
    """
    content = svg_path.read_text(encoding="utf-8")
    m = _DESC_RE.search(content)
    if not m:
        return None
    desc = m.group(1)
    if "jumps" in desc:
        return "jumps"
    if "perks" in desc:
        return "perks"
    return None


def resolve_vertex_source(marker_count: int, jump_count: int, perk_count: int,
                          svg_path: Path = None):
    """
    Returns "perks", "jumps", or None (unresolved).

    Resolution rules:
      perks  if marker_count == perk_count  AND marker_count != jump_count
      jumps  if marker_count == jump_count  AND marker_count != perk_count
      tie    if marker_count == jump_count == perk_count: fall back to <desc> text
      None   otherwise (truly ambiguous or no match)
    """
    if marker_count == perk_count and marker_count != jump_count:
        return "perks"
    if marker_count == jump_count and marker_count != perk_count:
        return "jumps"
    # Tie-break: all three equal (e.g. Vehicles: 1 perk per jump)
    if marker_count == jump_count == perk_count and svg_path is not None:
        return get_svg_desc_vertex_source(svg_path)
    return None


# ---------------------------------------------------------------------------
# SVG attribute injection
# ---------------------------------------------------------------------------
# Matches viewBox="..." anywhere in the <svg ...> opening tag
_VIEWBOX_RE = re.compile(r'(viewBox="[^"]*")')


def inject_vertex_source(svg_path: Path, vertex_source: str) -> None:
    """
    Write data-vertex-source="<vertex_source>" into svg_path's root <svg>
    element immediately after the viewBox attribute, byte-for-byte otherwise.
    """
    content = svg_path.read_text(encoding="utf-8")

    # Verify not already tagged
    if 'data-vertex-source=' in content:
        print(f"  [skip] {svg_path.name} already has data-vertex-source")
        return

    replacement = f'\\1 data-vertex-source="{vertex_source}"'
    new_content, n = _VIEWBOX_RE.subn(replacement, content, count=1)
    if n != 1:
        raise RuntimeError(f"Could not find viewBox attribute in {svg_path}")

    svg_path.write_text(new_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# metadata.json sidecar
# ---------------------------------------------------------------------------
_SHAPE_CONCEPT_RE = re.compile(
    r'<p[^>]*class="shape-concept"[^>]*>(.*?)</p>', re.DOTALL
)
_LABEL_SPAN_RE = re.compile(r'<span[^>]*class="label"[^>]*>.*?</span>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_intended_image(index_html_path: Path) -> str:
    content = index_html_path.read_text(encoding="utf-8")
    m = _SHAPE_CONCEPT_RE.search(content)
    if not m:
        raise ValueError(f"No <p class='shape-concept'> found in {index_html_path}")
    inner = m.group(1)
    # Strip the label span
    inner = _LABEL_SPAN_RE.sub("", inner)
    # Strip any remaining tags
    inner = _TAG_RE.sub("", inner)
    # Whitespace-collapse
    return " ".join(inner.split())


def write_metadata(cluster_dir: Path, intended_image: str) -> None:
    meta = {
        "schema_version": 1,
        "intended_image": intended_image,
    }
    out = cluster_dir / "metadata.json"
    out.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Build constellation counts from perk directory
    print("Loading perk_directory.json …")
    constellation_counts = build_constellation_counts(PERK_DIRECTORY)

    # ---------------------------------------------------------------------------
    # Pass 1: resolve without writing
    # ---------------------------------------------------------------------------
    print("\n=== Pass 1: dry resolution ===")
    resolutions = {}   # slug -> {"constellation", "marker_count", "jump_count", "perk_count", "vertex_source"}
    failures = []

    for cluster_dir, slug in iter_cluster_dirs():
        svg_path = cluster_dir / "current.svg"

        constellation_name = get_svg_title(svg_path)
        counts = constellation_counts.get(constellation_name)
        if counts is None:
            failures.append(
                f"  {slug}: constellation '{constellation_name}' not found in perk_directory"
            )
            continue

        marker_count = count_star_marks(svg_path)
        jump_count = counts["jumps"]
        perk_count = counts["perks"]
        vertex_source = resolve_vertex_source(marker_count, jump_count, perk_count, svg_path)

        row = {
            "constellation": constellation_name,
            "marker_count": marker_count,
            "jump_count": jump_count,
            "perk_count": perk_count,
            "vertex_source": vertex_source,
        }
        resolutions[slug] = row

        status = vertex_source if vertex_source else "UNRESOLVED"
        print(
            f"  {slug}: markers={marker_count}, jumps={jump_count}, "
            f"perks={perk_count} → {status}"
        )

        if vertex_source is None:
            failures.append(
                f"  {slug} ({constellation_name}): markers={marker_count}, "
                f"jumps={jump_count}, perks={perk_count} — ambiguous or no match"
            )

    if failures:
        print("\n[HALTED] The following clusters could not be resolved:")
        for f in failures:
            print(f)
        print("\nNo SVG files were modified.")
        sys.exit(1)

    print("\nAll 14 clusters resolved successfully. Proceeding to write pass.")

    # ---------------------------------------------------------------------------
    # Pass 2: write SVGs + metadata sidecars
    # ---------------------------------------------------------------------------
    print("\n=== Pass 2: writing files ===")

    # Print resolution table
    print(
        f"\n{'Cluster':<30} {'Markers':>7} {'Jumps':>6} {'Perks':>6} {'vertex_source':<12}"
    )
    print("-" * 65)

    for slug, row in resolutions.items():
        print(
            f"  {row['constellation']:<28} {row['marker_count']:>7} "
            f"{row['jump_count']:>6} {row['perk_count']:>6}  {row['vertex_source']:<12}"
        )

        cluster_dir = CONSTELLATIONS_DIR / slug
        svg_path = cluster_dir / "current.svg"

        # Inject vertex_source into SVG
        inject_vertex_source(svg_path, row["vertex_source"])
        print(f"    → wrote data-vertex-source=\"{row['vertex_source']}\" to {svg_path.name}")

        # Write metadata sidecar
        index_html = cluster_dir / "index.html"
        intended_image = parse_intended_image(index_html)
        write_metadata(cluster_dir, intended_image)
        print(f"    → wrote metadata.json (intended_image: {intended_image[:60]}…)")

    print("\nDone.")


if __name__ == "__main__":
    main()
