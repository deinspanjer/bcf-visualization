"""Extract structured data from constellation SVG files.

Usage:
    python3 scripts/extract_constellation_svgs.py
    # or import and call extract(constellations_dir)

The extract() function returns a dict keyed by constellation name, sorted by
slug-prefix integer (i.e., folder order). Phase 5 imports and calls it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Regex patterns – SVGs are machine-emitted so regex is safe and avoids the
# whitespace-normalization side-effects of an XML library round-trip.
# ---------------------------------------------------------------------------

_RE_VERTEX_SOURCE = re.compile(r'data-vertex-source=["\']([^"\']+)["\']')
_RE_TITLE = re.compile(r'<title>([^<]*)</title>')
_RE_USE = re.compile(
    r'<use\b[^>]*href=["\']#star-mark["\'][^>]*/?>',
    re.DOTALL,
)
_RE_ATTR_X = re.compile(r'\bx=["\']([^"\']+)["\']')
_RE_ATTR_Y = re.compile(r'\by=["\']([^"\']+)["\']')
_RE_ATTR_WIDTH = re.compile(r'\bwidth=["\']([^"\']+)["\']')
_RE_ATTR_HEIGHT = re.compile(r'\bheight=["\']([^"\']+)["\']')
_RE_CLUSTER_OUTLINE = re.compile(
    r'<(\w+)\b[^>]*class=["\']cluster-outline["\'][^>]*/?>',
    re.DOTALL,
)
_RE_POLYLINE_POINTS = re.compile(
    r'<polyline\b[^>]*class=["\']cluster-outline["\'][^>]*points=["\']([^"\']*)["\'][^>]*/?>',
    re.DOTALL,
)
# Also handle: points="..." appearing after class= with other attrs in between.
# A second pass: extract points attr from any tag matched above.
_RE_POINTS_ATTR = re.compile(r'\bpoints=["\']([^"\']*)["\']')

# SVG points value: sequences of numbers separated by commas and/or whitespace.
_RE_NUMBERS = re.compile(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?')


def _parse_points(points_str: str) -> list[list[float]]:
    """Parse an SVG points attribute into a list of [x, y] pairs."""
    numbers = [float(n) for n in _RE_NUMBERS.findall(points_str)]
    if len(numbers) % 2 != 0:
        raise ValueError(
            f"Points string has odd number of values: {points_str!r}"
        )
    return [[numbers[i] / 320.0, numbers[i + 1] / 320.0]
            for i in range(0, len(numbers), 2)]


def _slug_order(slug: str) -> int:
    """Extract leading integer from slug for sort order."""
    m = re.match(r'^(\d+)', slug)
    return int(m.group(1)) if m else 0


def extract(constellations_dir: Path) -> dict[str, dict]:
    """Parse all cluster folders under constellations_dir.

    Returns a dict keyed by constellation name, sorted by slug-prefix integer.
    Halts with sys.exit(1) on any error condition.
    """
    results: dict[str, dict] = {}

    # Collect cluster folders: directories whose names start with a digit.
    folders = sorted(
        [
            d for d in constellations_dir.iterdir()
            if d.is_dir() and re.match(r'^\d', d.name)
        ],
        key=lambda d: _slug_order(d.name),
    )

    for folder in folders:
        slug = folder.name

        # ------------------------------------------------------------------
        # 1. Parse current.svg
        # ------------------------------------------------------------------
        svg_path = folder / "current.svg"
        if not svg_path.exists():
            print(
                f"ERROR: {slug}: missing current.svg",
                file=sys.stderr,
            )
            sys.exit(1)

        svg_text = svg_path.read_text(encoding="utf-8")

        # data-vertex-source
        m = _RE_VERTEX_SOURCE.search(svg_text)
        if not m:
            print(
                f"ERROR: {slug}: <svg> root is missing data-vertex-source attribute",
                file=sys.stderr,
            )
            sys.exit(1)
        vertex_source = m.group(1)

        # constellation name from <title>
        m = _RE_TITLE.search(svg_text)
        if not m:
            print(
                f"ERROR: {slug}: <title> element not found",
                file=sys.stderr,
            )
            sys.exit(1)
        name = m.group(1).strip()

        # marker positions from <use href="#star-mark" ...>
        marker_positions: list[list[float]] = []
        for use_tag in _RE_USE.finditer(svg_text):
            tag = use_tag.group(0)
            mx = _RE_ATTR_X.search(tag)
            my = _RE_ATTR_Y.search(tag)
            mw = _RE_ATTR_WIDTH.search(tag)
            mh = _RE_ATTR_HEIGHT.search(tag)
            if not (mx and my and mw and mh):
                print(
                    f"ERROR: {slug}: <use> element missing x/y/width/height: {tag!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            x = float(mx.group(1))
            y = float(my.group(1))
            w = float(mw.group(1))
            h = float(mh.group(1))
            cx = (x + w / 2.0) / 320.0
            cy = (y + h / 2.0) / 320.0
            marker_positions.append([cx, cy])

        if not marker_positions:
            print(
                f"ERROR: {slug}: zero markers found (href=\"#star-mark\" not present)",
                file=sys.stderr,
            )
            sys.exit(1)

        # cluster-outline elements — must all be <polyline>
        silhouette: list[list[list[float]]] = []
        for outline_m in _RE_CLUSTER_OUTLINE.finditer(svg_text):
            tag_name = outline_m.group(1)
            if tag_name != "polyline":
                print(
                    f"ERROR: {slug}: cluster-outline element is <{tag_name}>, "
                    f"expected <polyline>",
                    file=sys.stderr,
                )
                sys.exit(1)
            # Extract points from the full matched tag
            full_tag = outline_m.group(0)
            pm = _RE_POINTS_ATTR.search(full_tag)
            if not pm:
                print(
                    f"ERROR: {slug}: <polyline class=\"cluster-outline\"> "
                    f"missing points attribute: {full_tag!r}",
                    file=sys.stderr,
                )
                sys.exit(1)
            pts = _parse_points(pm.group(1))
            if len(pts) < 2:
                print(
                    f"ERROR: {slug}: cluster-outline polyline has fewer than 2 points",
                    file=sys.stderr,
                )
                sys.exit(1)
            silhouette.append(pts)

        # ------------------------------------------------------------------
        # 2. Parse metadata.json
        # ------------------------------------------------------------------
        meta_path = folder / "metadata.json"
        if not meta_path.exists():
            print(
                f"ERROR: {slug}: metadata.json is missing",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(
                f"ERROR: {slug}: metadata.json is not valid JSON: {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        if meta.get("schema_version") != 1:
            print(
                f"ERROR: {slug}: metadata.json schema_version is "
                f"{meta.get('schema_version')!r}, expected 1",
                file=sys.stderr,
            )
            sys.exit(1)

        intended_image = meta.get("intended_image", "")

        # ------------------------------------------------------------------
        # 3. Build entry
        # ------------------------------------------------------------------
        results[name] = {
            "slug": slug,
            "vertex_source": vertex_source,
            "intended_image": intended_image,
            "marker_positions": marker_positions,
            "silhouette": silhouette,
        }

    return results


def _print_summary(data: dict[str, dict]) -> None:
    """Print a human-readable summary table."""
    col_name = max(len(name) for name in data) if data else 10
    col_slug = max(len(v["slug"]) for v in data.values()) if data else 8

    header = (
        f"{'Name':<{col_name}}  "
        f"{'Slug':<{col_slug}}  "
        f"{'Markers':>7}  "
        f"{'Polylines':>9}  "
        f"{'vertex_source':<13}  "
        f"intended_image (first 60 chars)"
    )
    print(header)
    print("-" * len(header))

    for name, entry in data.items():
        preview = entry["intended_image"][:60]
        print(
            f"{name:<{col_name}}  "
            f"{entry['slug']:<{col_slug}}  "
            f"{len(entry['marker_positions']):>7}  "
            f"{len(entry['silhouette']):>9}  "
            f"{entry['vertex_source']:<13}  "
            f"{preview}"
        )

    print()
    print(f"Total constellations: {len(data)}")


if __name__ == "__main__":
    _constellations_dir = Path(__file__).parent.parent / "data" / "constellations"
    _data = extract(_constellations_dir)
    _print_summary(_data)
