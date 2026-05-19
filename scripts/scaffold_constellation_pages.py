"""Scaffold constellation design pages under data/constellations.

Each cluster constellation gets an ordered folder with an index.html page.
The page embeds an editable cluster SVG followed by data-derived jump and
perk tables for design notes.
"""

from __future__ import annotations

import html
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"
OUT = ROOT / "data" / "constellations"
CURRENT_FILENAME = "current.svg"
REFERENCE_FILENAME = "reference.svg"

CONST_HUES = {
    "Toolkits": 196,
    "Knowledge": 268,
    "Vehicles": 30,
    "Time": 218,
    "Crafting": 152,
    "Clothing": 320,
    "Magic": 286,
    "Quality": 48,
    "Size": 100,
    "Resources and Durability": 8,
    "Magitech": 240,
    "Alchemy": 170,
    "Capstone": 52,
    "Personal Reality": 130,
}

EDITABLE_RE = re.compile(
    r"(?P<block><!-- EDITABLE: cluster silhouette\b.*?<!-- /EDITABLE -->)",
    re.DOTALL,
)
SVG_RE = re.compile(r"(?P<svg><svg\b.*?</svg>)", re.DOTALL)


def slug(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return value or "unnamed"


def folder_slug(index: int, name: str) -> str:
    return f"{index:02d}-{slug(name)}"


def norm(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("–", "-").replace("—", "-").replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().casefold()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def cost_label(cost: int | None) -> str:
    if cost is None:
        return "?"
    if cost == 0:
        return "Free"
    return f"{cost} CP"


def bucket_for(cost: int | None) -> str:
    if cost is None:
        return "star-100"
    if cost == 0:
        return "satellite"
    if cost >= 1000:
        return "star-1000"
    if cost >= 800:
        return "star-800"
    if cost >= 600:
        return "star-600"
    if cost >= 400:
        return "star-400"
    if cost >= 300:
        return "star-300"
    if cost >= 200:
        return "star-200"
    return "star-100"


def build_jump_lookup(
    jumps: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], str],
    dict[tuple[str, str], set[str]],
    dict[str, set[tuple[str, str]]],
]:
    by_jump: dict[tuple[str, str], str] = {}
    by_perk: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_perk_global: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for jump in jumps:
        constellation = jump["constellation"]
        jump_name = jump["jump"]
        by_jump[(constellation, norm(jump_name))] = jump_name
        for star in jump.get("stars", []):
            by_perk[(constellation, norm(star.get("perk_name")))].add(jump_name)
            by_perk_global[norm(star.get("perk_name"))].add((constellation, jump_name))
    return by_jump, by_perk, by_perk_global


def resolve_roll_jump(
    constellation: str,
    raw_jump: str | None,
    paid_names: list[str],
    free_perks: list[dict[str, Any]],
    by_jump: dict[tuple[str, str], str],
    by_perk: dict[tuple[str, str], set[str]],
) -> str | None:
    raw = norm(raw_jump)
    exact = by_jump.get((constellation, raw))
    if exact:
        return exact

    if raw.endswith(" supplement"):
        stripped = by_jump.get((constellation, raw.removesuffix(" supplement").strip()))
        if stripped:
            return stripped

    if raw:
        fuzzy = [
            jump
            for (const, known), jump in by_jump.items()
            if const == constellation and (raw in known or known in raw)
        ]
        if len(fuzzy) == 1:
            return fuzzy[0]

    candidates: set[str] | None = None
    for paid_name in paid_names:
        jumps = by_perk.get((constellation, norm(paid_name)), set())
        candidates = set(jumps) if candidates is None else candidates & jumps
    if candidates and len(candidates) == 1:
        return next(iter(candidates))

    free_jump_candidates = {
        by_jump[(constellation, norm(perk.get("jump")))]
        for perk in free_perks
        if (constellation, norm(perk.get("jump"))) in by_jump
    }
    if len(free_jump_candidates) == 1:
        return next(iter(free_jump_candidates))

    return None


def resolve_paid_location(
    raw_constellation: str,
    raw_jump: str | None,
    paid_name: str,
    free_perks: list[dict[str, Any]],
    by_jump: dict[tuple[str, str], str],
    by_perk: dict[tuple[str, str], set[str]],
    by_perk_global: dict[str, set[tuple[str, str]]],
) -> tuple[str, str] | None:
    jump = resolve_roll_jump(
        constellation=raw_constellation,
        raw_jump=raw_jump,
        paid_names=[paid_name],
        free_perks=free_perks,
        by_jump=by_jump,
        by_perk=by_perk,
    )
    if jump:
        return raw_constellation, jump

    candidates = by_perk_global.get(norm(paid_name), set())
    if not candidates:
        return None

    raw = norm(raw_jump)
    if raw:
        jump_filtered = {
            (constellation, jump_name)
            for constellation, jump_name in candidates
            if raw == norm(jump_name)
            or raw in norm(jump_name)
            or norm(jump_name) in raw
        }
        if len(jump_filtered) == 1:
            return next(iter(jump_filtered))

    if len(candidates) == 1:
        return next(iter(candidates))

    free_constellations = {perk.get("constellation") for perk in free_perks if perk.get("constellation")}
    constellation_filtered = {
        (constellation, jump_name)
        for constellation, jump_name in candidates
        if constellation in free_constellations
    }
    if len(constellation_filtered) == 1:
        return next(iter(constellation_filtered))

    return None


def build_free_addons(jumps: list[dict[str, Any]], rolls: list[dict[str, Any]]) -> tuple[dict[tuple[str, str, str], list[str]], list[str]]:
    by_jump, by_perk, by_perk_global = build_jump_lookup(jumps)
    addons: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    unresolved: list[str] = []

    for roll in rolls:
        free_perks = list(roll.get("free_perks") or [])
        purchased = list(roll.get("purchased_perks") or [])
        if not free_perks or not purchased:
            continue

        constellation = roll.get("constellation") or ""
        free_names = [str(perk.get("name") or "") for perk in free_perks if perk.get("name")]
        paid_names = [str(perk.get("name") or "") for perk in purchased]
        for paid_name in paid_names:
            location = resolve_paid_location(
                raw_constellation=constellation,
                raw_jump=roll.get("purchased_perk_jump"),
                paid_name=paid_name,
                free_perks=free_perks,
                by_jump=by_jump,
                by_perk=by_perk,
                by_perk_global=by_perk_global,
            )
            if not location:
                unresolved.append(
                    f"{constellation} / {roll.get('purchased_perk_jump')}: {paid_name}"
                )
                continue
            paid_constellation, jump = location
            key = (paid_constellation, jump, paid_name)
            for free_name in free_names:
                if free_name not in addons[key]:
                    addons[key].append(free_name)

    return dict(addons), unresolved


def existing_editable_block(path: Path) -> str | None:
    if not path.exists():
        return None
    match = EDITABLE_RE.search(path.read_text())
    if not match:
        return None
    return match.group("block")


def ensure_editable_hue(editable_block: str, hue: int) -> str:
    return re.sub(
        r'color="oklch\(0\.82 0\.14 [^)]+\)"',
        f'color="oklch(0.82 0.14 {hue})"',
        editable_block,
        count=1,
    )


def write_current_svg(path: Path, editable_block: str) -> None:
    match = SVG_RE.search(editable_block)
    svg = match.group("svg") if match else editable_block
    path.write_text(svg.strip() + "\n")


def scaled_points(vertices: list[list[float]]) -> list[tuple[float, float]]:
    raw = [(float(v[0]), float(v[1])) for v in vertices]
    if not raw:
        return []
    min_x = min(x for x, _ in raw)
    max_x = max(x for x, _ in raw)
    min_y = min(y for _, y in raw)
    max_y = max(y for _, y in raw)
    span = max(max_x - min_x, max_y - min_y, 0.01)
    pad = 30.0
    scale = (320.0 - pad * 2.0) / span
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    return [
        (160.0 + (x - center_x) * scale, 160.0 - (y - center_y) * scale)
        for x, y in raw
    ]


def starfield(seed: int) -> str:
    rng = random.Random(seed)
    dots = []
    for _ in range(60):
        x = rng.uniform(0, 320)
        y = rng.uniform(0, 320)
        bright = rng.random() > 0.45
        r = 0.9 if bright else 0.5
        opacity = 0.55 if bright else 0.3
        dots.append(f'      <circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" opacity="{opacity}"/>')
    return "\n".join(dots)


def generated_editable_block(cluster: dict[str, Any], index: int) -> str:
    name = cluster["name"]
    hue = CONST_HUES.get(name, 196)
    vertices = cluster.get("marker_positions", [])
    points = scaled_points(vertices)
    point_attr = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    marker_uses = []
    for x, y in points:
        marker_uses.append(f'      <use href="#star-mark" x="{x - 15:.1f}" y="{y - 15:.1f}" width="30" height="30"/>')
    markers = "\n".join(marker_uses)
    outline = ""
    if len(points) > 1:
        outline = f"""    <polyline class="cluster-outline" points="{point_attr} {point_attr.split()[0]}"
              fill="none" stroke="currentColor" stroke-opacity="0.32"
              stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round"/>"""
    elif points:
        x, y = points[0]
        outline = f"""    <circle class="cluster-outline" cx="{x:.1f}" cy="{y:.1f}" r="24"
              fill="none" stroke="currentColor" stroke-opacity="0.32"
              stroke-width="1.1"/>"""

    return f"""<!-- EDITABLE: cluster silhouette - markers expand the silhouette template to jump_count -->
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320"
       color="oklch(0.82 0.14 {hue})"
       style="background: radial-gradient(circle at 50% 60%, #07121a 0%, #03080d 75%)">
    <title>{escape(name)}</title>
    <desc>{escape(name)} as a constellation of its {len(vertices)} jumps. One marker per jump.</desc>
    <defs>
      <linearGradient id="ray-grad" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0"    stop-color="transparent"/>
        <stop offset="0.48" stop-color="#fff" stop-opacity="0.58"/>
        <stop offset="0.50" stop-color="#fff" stop-opacity="0.92"/>
        <stop offset="0.52" stop-color="#fff" stop-opacity="0.58"/>
        <stop offset="1"    stop-color="transparent"/>
      </linearGradient>
      <symbol id="star-mark" viewBox="-50 -50 100 100" overflow="visible">
        <g filter="drop-shadow(0 0 1px #fff) drop-shadow(0 0 3px currentColor)" opacity="0.76">
          <g opacity="0.68" style="mix-blend-mode:screen">
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(-3.00)"/>
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(63.00)"/>
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(117.00)"/>
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(183.00)"/>
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(237.00)"/>
            <rect x="-32.00" y="-0.390" width="64.00" height="0.780" rx="0.390" fill="url(#ray-grad)" transform="rotate(303.00)"/>
          </g>
          <g opacity="0.32" style="mix-blend-mode:screen">
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(27.00)"/>
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(93.00)"/>
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(147.00)"/>
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(213.00)"/>
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(267.00)"/>
            <rect x="-18.00" y="-0.125" width="36.00" height="0.250" rx="0.125" fill="url(#ray-grad)" transform="rotate(333.00)"/>
          </g>
          <circle r="2.2" fill="currentColor" opacity="0.16"/>
          <circle r="1.4" fill="#fff"/>
        </g>
      </symbol>
    </defs>

    <!-- Background starfield (deterministic seed-{index} LCG, 60 dots). -->
    <g class="starfield">
{starfield(index)}
    </g>

{outline}

    <!-- One diffraction-spike marker per jump. -->
    <g class="jump-markers">
{markers}
    </g>
  </svg>
  <!-- /EDITABLE -->"""


def perk_counts_summary(stars: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for star in stars:
        cost = star.get("cost")
        key = "free" if cost == 0 else cost_label(cost)
        counts[key] += 1
    return " · ".join(f"{count} x {label}" for label, count in counts.items()) or "no perks"


def cluster_perk_bucket_summary(jumps: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for jump in jumps:
        for star in jump.get("stars", []):
            counts[bucket_for(star.get("cost"))] += 1
    if not counts:
        return "no perks"
    bucket_order = [
        "satellite",
        "star-100",
        "star-200",
        "star-300",
        "star-400",
        "star-600",
        "star-800",
        "star-1000",
    ]
    return " · ".join(
        f"{counts[bucket]} x {bucket}" for bucket in bucket_order if counts.get(bucket)
    )


def free_perk_summary(jumps: list[dict[str, Any]]) -> str:
    count = sum(
        1
        for jump in jumps
        for star in jump.get("stars", [])
        if star.get("cost") == 0
    )
    if count == 0:
        return "no free perks"
    return f"{count} free perk{'s' if count != 1 else ''}"


def jump_summary_rows(jumps: list[dict[str, Any]]) -> str:
    rows = []
    for jump in jumps:
        jump_name = jump["jump"]
        rows.append(
            "    <tr>"
            f"<td><a href=\"#{escape(slug(jump_name))}\">{escape(jump_name)}</a></td>"
            f"<td>{len(jump.get('stars', []))}</td>"
            "<td class=\"note-field\"></td>"
            "</tr>"
        )
    return "\n".join(rows)


def perk_detail_table(jump: dict[str, Any], addons: dict[tuple[str, str, str], list[str]]) -> str:
    rows = []
    for star in jump.get("stars", []):
        free_addons = addons.get((jump["constellation"], jump["jump"], star["perk_name"]), [])
        rows.append(
            "      <tr>"
            f"<td>{escape(star['perk_name'])}</td>"
            f"<td>{escape(cost_label(star.get('cost')))}</td>"
            f"<td>{escape(', '.join(free_addons))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('      <tr><td colspan="3">No perks in derived wireframe data.</td></tr>')
    return "\n".join(rows)


def jump_sections(jumps: list[dict[str, Any]], addons: dict[tuple[str, str, str], list[str]]) -> str:
    sections = []
    for jump in jumps:
        jump_name = jump["jump"]
        sections.append(
            f"""  <section class="jump-detail" id="{escape(slug(jump_name))}">
    <h3>{escape(jump_name)}</h3>
    <p class="jump-meta">{escape(perk_counts_summary(jump.get("stars", [])))}</p>
    <table>
      <thead>
        <tr><th>Perk name</th><th>Cost</th><th>Free add-ons</th></tr>
      </thead>
      <tbody>
{perk_detail_table(jump, addons)}
      </tbody>
    </table>
  </section>"""
        )
    return "\n".join(sections)


def page_html(
    cluster: dict[str, Any],
    jumps: list[dict[str, Any]],
    editable_block: str,
    addons: dict[tuple[str, str, str], list[str]],
    has_reference: bool,
) -> str:
    name = cluster["name"]
    hue = CONST_HUES.get(name, 196)
    reference_panel = (
        f'<img class="reference-image" src="{REFERENCE_FILENAME}" alt="{escape(name)} reference image"/>'
        if has_reference
        else '<div class="empty-reference">No reference.svg saved yet.</div>'
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{escape(name)} · Cluster Wireframe</title>
<style>
  :root {{
    --void:       #03080d;
    --void-soft:  #07121a;
    --ink:        #e8fdff;
    --muted:      #9ad7df;
    --dim:        #5f9ba4;
    --cyan:       #5cf4ff;
    --rose:       #ff8aa8;
    --edge-soft:  rgba(92, 244, 255, 0.22);
    --warn-bg:    rgba(255, 138, 168, 0.10);
    --warn-edge:  rgba(255, 138, 168, 0.55);
    --serif:      Georgia, "Times New Roman", serif;
    --sans:       "Avenir Next", "Segoe UI", system-ui, sans-serif;
    --mono:       ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  html, body {{ margin: 0; padding: 0; background: var(--void); color: var(--ink);
                font-family: var(--sans); }}
  body {{ padding: 28px 36px 48px; min-height: 100vh; }}
  h1 {{ font-family: var(--serif); font-size: 28px; color: var(--cyan);
        margin: 0 0 6px 0; letter-spacing: 0.03em; }}
  .back-link {{ display: inline-block; margin: 0 0 18px 0; font-family: var(--mono);
                font-size: 12px; color: var(--dim); }}
  h2 {{ font-family: var(--serif); font-size: 22px; color: var(--cyan);
        margin: 32px 0 12px 0; }}
  h3 {{ font-family: var(--serif); font-size: 18px; color: var(--ink);
        margin: 26px 0 6px 0; }}
  dl.meta {{ margin: 0 0 22px 0; font-family: var(--mono); font-size: 12px;
             display: grid; grid-template-columns: 78px 1fr; row-gap: 4px;
             column-gap: 14px; max-width: 760px; }}
  dl.meta dt {{ color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em; }}
  dl.meta dd {{ margin: 0; color: var(--ink); }}
  p.shape-concept {{ font-family: var(--serif); font-style: italic; color: var(--muted);
                     font-size: 15px; max-width: 60ch; margin: 0 0 24px 0; line-height: 1.4; }}
  p.shape-concept .label {{ display: block; font-family: var(--mono); font-style: normal;
                            color: var(--dim); text-transform: uppercase; letter-spacing: 0.08em;
                            font-size: 11px; margin-bottom: 4px; }}
  .image-comparison {{ display: grid; grid-template-columns: repeat(2, minmax(260px, 360px));
                       gap: 18px; align-items: start; margin: 0 0 30px 0; }}
  .image-panel {{ margin: 0; padding: 0; }}
  .preview-label {{ color: var(--dim); font-family: var(--mono); font-size: 11px;
                    letter-spacing: 0.08em; margin: 0 0 7px 0; text-transform: uppercase; }}
  .image-panel svg, .image-panel img, .empty-reference {{
    width: 100%; aspect-ratio: 1 / 1; display: block;
    border: 1px solid var(--edge-soft); border-radius: 4px;
    background: var(--void-soft);
  }}
  .image-panel svg {{ height: auto; }}
  .image-panel img {{ object-fit: contain; padding: 18px; box-sizing: border-box; }}
  .image-panel img.reference-image {{ background: #e8fdff; }}
  .empty-reference {{ box-sizing: border-box; color: var(--dim); display: grid; place-items: center;
                      font-family: var(--mono); font-size: 12px; padding: 18px; text-align: center; }}
  @media (max-width: 760px) {{
    .image-comparison {{ grid-template-columns: minmax(260px, 360px); }}
  }}
  table {{ border-collapse: collapse; width: min(100%, 980px); margin: 0 0 18px 0;
           font-size: 13px; }}
  th, td {{ border: 1px solid var(--edge-soft); padding: 8px 10px; vertical-align: top; }}
  th {{ color: var(--cyan); font-family: var(--mono); font-size: 11px; font-weight: 600;
        text-align: left; text-transform: uppercase; letter-spacing: 0.08em;
        background: rgba(92, 244, 255, 0.06); }}
  td {{ color: var(--ink); line-height: 1.35; }}
  td:nth-child(2) {{ width: 120px; font-family: var(--mono); color: var(--muted); }}
  .jump-summary td:nth-child(2) {{ width: 120px; text-align: right; }}
  .note-field {{ min-width: 220px; }}
  .jump-meta {{ margin: 0 0 8px 0; color: var(--dim); font-family: var(--mono); font-size: 12px; }}
  a {{ color: var(--cyan); text-decoration-color: var(--edge-soft); }}
</style>
</head>
<body>
<h1>{escape(name)}</h1>
<a class="back-link" href="../index.html">Back to constellation index</a>
<dl class="meta">
  <dt>Jumps</dt><dd>{len(jumps)}</dd>
  <dt>Hue</dt><dd>{hue}° · oklch(0.82 0.14 {hue})</dd>
  <dt>Perks</dt><dd>{escape(cluster_perk_bucket_summary(jumps))}</dd>
  <dt>Free</dt><dd>{escape(free_perk_summary(jumps))}</dd>
</dl>
<p class="shape-concept"><span class="label">Intended image</span>{escape(cluster.get("shape_concept", ""))}</p>
<section class="image-comparison">
  <figure class="image-panel">
    <div class="preview-label">Current</div>
    {editable_block}
  </figure>
  <figure class="image-panel">
    <div class="preview-label">Reference</div>
    {reference_panel}
  </figure>
</section>

<section class="jump-summary">
  <h2>Jump Summary</h2>
  <table>
    <thead>
      <tr><th>Jump name</th><th>Total perks in jump</th><th>Notes</th></tr>
    </thead>
    <tbody>
{jump_summary_rows(jumps)}
    </tbody>
  </table>
</section>

<section class="jump-details">
  <h2>Perk Details</h2>
{jump_sections(jumps, addons)}
</section>
</body>
</html>
"""


def root_index_html(
    page_records: list[dict[str, Any]],
) -> str:
    rows = []
    for record in page_records:
        cluster = record["cluster"]
        name = cluster["name"]
        jumps = record["jumps"]
        folder = record["folder"]
        reference_cell = (
            f'<img class="thumb reference-thumb" src="{escape(folder)}/{REFERENCE_FILENAME}" alt="{escape(name)} reference image"/>'
            if record["has_reference"]
            else '<span class="empty-thumb">none</span>'
        )
        rows.append(
            "    <tr>"
            f"<td class=\"num\">{record['index']:02d}</td>"
            f"<td><a href=\"{escape(folder)}/index.html\">{escape(name)}</a></td>"
            f"<td class=\"thumb-cell\"><img class=\"thumb\" src=\"{escape(folder)}/{CURRENT_FILENAME}\" alt=\"{escape(name)} current image\"/></td>"
            f"<td class=\"thumb-cell\">{reference_cell}</td>"
            f"<td class=\"num\">{len(jumps)}</td>"
            f"<td class=\"num\">{sum(len(jump.get('stars', [])) for jump in jumps)}</td>"
            f"<td>{escape(cluster.get('shape_concept', ''))}</td>"
            "</tr>"
        )
    rows_html = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Constellation Design Index</title>
<style>
  :root {{
    --void:       #03080d;
    --ink:        #e8fdff;
    --muted:      #9ad7df;
    --dim:        #5f9ba4;
    --cyan:       #5cf4ff;
    --edge-soft:  rgba(92, 244, 255, 0.22);
    --serif:      Georgia, "Times New Roman", serif;
    --sans:       "Avenir Next", "Segoe UI", system-ui, sans-serif;
    --mono:       ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  html, body {{ margin: 0; padding: 0; background: var(--void); color: var(--ink);
                font-family: var(--sans); }}
  body {{ padding: 28px 36px 48px; min-height: 100vh; }}
  h1 {{ font-family: var(--serif); font-size: 28px; color: var(--cyan);
        margin: 0 0 14px 0; letter-spacing: 0.03em; }}
  p {{ color: var(--muted); margin: 0 0 22px 0; max-width: 68ch; line-height: 1.45; }}
  table {{ border-collapse: collapse; width: min(100%, 1180px); font-size: 13px; }}
  th, td {{ border: 1px solid var(--edge-soft); padding: 8px 10px; vertical-align: top; }}
  th {{ color: var(--cyan); font-family: var(--mono); font-size: 11px; font-weight: 600;
        text-align: left; text-transform: uppercase; letter-spacing: 0.08em;
        background: rgba(92, 244, 255, 0.06); }}
  td.num {{ color: var(--dim); font-family: var(--mono); text-align: right; width: 72px; }}
  td:nth-child(2) {{ min-width: 220px; }}
  .thumb-cell {{ width: 96px; text-align: center; }}
  .thumb {{ width: 72px; height: 72px; object-fit: contain; display: inline-block;
            border: 1px solid var(--edge-soft); border-radius: 4px;
            background: #07121a; padding: 6px; box-sizing: border-box; }}
  .reference-thumb {{ background: #e8fdff; }}
  .empty-thumb {{ color: var(--dim); display: inline-grid; place-items: center;
                  width: 72px; height: 72px; font-family: var(--mono); font-size: 11px; }}
  a {{ color: var(--cyan); text-decoration-color: var(--edge-soft); }}
</style>
</head>
<body>
<h1>Constellation Design Index</h1>
<p>Cluster constellation pages in discovery order.</p>
<table>
  <thead>
    <tr><th>Order</th><th>Constellation</th><th>Current</th><th>Reference</th><th>Jumps</th><th>Perks</th><th>Intended image</th></tr>
  </thead>
  <tbody>
{rows_html}
  </tbody>
</table>
</body>
</html>
"""


def main() -> None:
    wireframes = load_json(DATA / "constellation_wireframes.json")
    rolls = load_json(DATA / "roll_facts.json")["rolls"]
    clusters = list(wireframes["cluster_constellations"])
    all_jumps = list(wireframes["jump_constellations"])
    addons, unresolved = build_free_addons(all_jumps, rolls)

    jumps_by_constellation: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for jump in all_jumps:
        jumps_by_constellation[jump["constellation"]][jump["jump"]] = jump

    OUT.mkdir(parents=True, exist_ok=True)
    page_records = []
    for index, cluster in enumerate(clusters, start=1):
        folder = OUT / folder_slug(index, cluster["name"])
        folder.mkdir(parents=True, exist_ok=True)
        page = folder / "index.html"
        editable = existing_editable_block(page) or generated_editable_block(cluster, index)
        editable = ensure_editable_hue(editable, CONST_HUES.get(cluster["name"], 196))
        write_current_svg(folder / CURRENT_FILENAME, editable)
        # Jump ordering used to follow the cluster_vertices seating chart, which
        # is gone in the hand-authored-SVG world. Sort by descending perk count
        # then name so the densest/most-defining jumps surface first on the page.
        ordered_jumps = sorted(
            jumps_by_constellation[cluster["name"]].values(),
            key=lambda j: (-len(j.get("stars", [])), j.get("jump", "")),
        )
        has_reference = (folder / REFERENCE_FILENAME).exists()
        page_records.append(
            {
                "index": index,
                "cluster": cluster,
                "folder": folder.name,
                "jumps": ordered_jumps,
                "editable": editable,
                "has_reference": has_reference,
            }
        )
        page.write_text(page_html(cluster, ordered_jumps, editable, addons, has_reference))

    (OUT / "index.html").write_text(root_index_html(page_records))

    print(f"Wrote {len(clusters)} constellation pages under {OUT.relative_to(ROOT)}")
    if unresolved:
        print(f"Unresolved free add-on roll associations: {len(unresolved)}")
        for item in unresolved:
            print(f"  - {item}")


if __name__ == "__main__":
    main()
