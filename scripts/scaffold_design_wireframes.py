"""Scaffold the data/constellations/ wireframe workspace.

Generates an editable SVG-based design surface for the 14 cluster
constellations ("major arcana") and their 214 jumps ("minor arcana").

Read-once script: re-run safely to regenerate. Hand-edits to per-jump
SVGs/MDs are NOT preserved — the user iterates inside the design tree,
then a future sync script extracts edits back into the JSON layer.

Folder tree produced:

    data/constellations/
      README.md
      _tokens.css
      _star-defs.svg
      _preview.html
      01-toolkits/
        _cluster.svg
        _cluster.md
        gunnm.svg
        gunnm.md
        ...
      02-knowledge/
      ...
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "derived"
OUT = ROOT / "data" / "constellations"

# Hue per constellation, lifted from redesign/data.js HUES.
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


def bucket_for(cost):
    """Cost → bucket id used by _star-defs.svg symbols."""
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


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "unnamed"


def folder_slug(idx: int, name: str) -> str:
    return f"{idx:02d}-{slug(name)}"


# ---------------------------------------------------------------------------
# Shared assets
# ---------------------------------------------------------------------------

def write_tokens_css(path: Path) -> None:
    """Design tokens lifted from redesign/style.css for standalone preview."""
    path.write_text(
"""/* Design tokens for constellation wireframe authoring.
   Mirror of plans/design_handoff_bcf_visualization/redesign/style.css :root.
   Keep in sync if the redesign tokens shift. */
:root {
  --void:         #03080d;
  --void-deep:    #02060a;
  --void-soft:    #07121a;
  --ink:          #e8fdff;
  --muted:        #9ad7df;
  --dim:          #5f9ba4;
  --cyan:         #5cf4ff;
  --green:        #7bffbd;
  --amber:        #f5d27b;
  --rose:         #ff8aa8;
  --edge:         rgba(92, 244, 255, 0.56);
  --edge-soft:    rgba(92, 244, 255, 0.22);
  --edge-faint:   rgba(92, 244, 255, 0.08);
  --glow:         rgba(92, 244, 255, 0.28);
  --panel:        rgba(5, 29, 38, 0.50);
  --panel-strong: rgba(5, 29, 38, 0.78);

  --serif: Georgia, "Times New Roman", serif;
  --sans:  "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --mono:  ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* Color recipe: each per-jump SVG sets `color: oklch(0.78 0.13 <hue>)`
   on its root <svg>. The shared <symbol>s draw with currentColor so the
   hue propagates to rays automatically. */
""")


def write_star_defs(path: Path) -> None:
    """Shared <defs> file. Each cost bucket is a <symbol> at viewBox -50..50.
    Drawn with currentColor so per-jump SVGs only set color and position.

    Recipe ported from plans/design_handoff_bcf_visualization/redesign/
    star.jsx — same major/minor ray counts, lengths, widths, and jitter per
    cost bucket, sun theme (the only theme used in the redesign). When the
    user retunes the recipe in star.jsx, mirror the change here.
    """
    THEME_PRIMARY = 0.68
    THEME_SECONDARY = 0.32

    # cost → (major, minor, length, width, minorLength, minorWidth, jitter, lum)
    # Each base tuple lifted from recipeFor(); sun-theme deltas applied.
    RECIPES = {
        "star-1000": (12 + 2, 12 + 2, 47 * 1.06, 1.1, 32 * 1.18, 0.34, 10, 1.32),
        "star-800":  (10 + 2, 10 + 2, 44 * 1.06, 1.05, 29 * 1.18, 0.32, 8, 1.20),
        "star-600":  (8 + 2,  8 + 2,  40 * 1.06, 0.98, 25 * 1.18, 0.30, 6, 1.05),
        "star-400":  (6 + 2,  6 + 2,  36 * 1.06, 0.90, 21 * 1.18, 0.28, 4, 0.86),
        "star-300":  (5 + 2,  5 + 2,  32 * 1.06, 0.82, 18 * 1.18, 0.26, 3, 0.76),
        "star-200":  (4 + 2,  4 + 2,  29 * 1.06, 0.75, 14 * 1.18, 0.24, 2, 0.64),
        "star-100":  (3 + 2,  3 + 2,  26 * 1.06, 0.68, 11 * 1.18, 0.22, 0, 0.52),
    }

    def rays(count: int, length: float, width: float, jitter: float, offset: float = 0.0) -> str:
        parts = []
        for i in range(count):
            angle = (360.0 / count) * i + offset + (jitter if i % 2 else -jitter)
            final_length = length * (1.10 if i % 3 == 0 else 1.0)
            parts.append(
                f'<rect x="{-final_length:.2f}" y="{-width/2:.3f}" '
                f'width="{final_length*2:.2f}" height="{width:.3f}" '
                f'rx="{width/2:.3f}" fill="url(#ray-grad)" '
                f'transform="rotate({angle:.2f})"/>'
            )
        return "\n      ".join(parts)

    symbols = []
    for sym_id, (major, minor, length, width, mlen, mwid, jit, lum) in RECIPES.items():
        primary = rays(major, length, width, jit)
        secondary = rays(minor, mlen, mwid, jit, offset=360.0 / (major * 2))
        core_r = 2.6 + lum * 1.8
        bright_r = 1.2 + lum * 0.62
        white_glow = lum * 0.8
        color_glow = lum * 2.4
        symbols.append(
f"""    <symbol id="{sym_id}" viewBox="-50 -50 100 100" overflow="visible">
      <g filter="drop-shadow(0 0 {white_glow:.2f}px #fff) drop-shadow(0 0 {color_glow:.2f}px currentColor)" opacity="0.76">
        <g opacity="{THEME_PRIMARY}" style="mix-blend-mode: screen">
          {primary}
        </g>
        <g opacity="{THEME_SECONDARY}" style="mix-blend-mode: screen">
          {secondary}
        </g>
        <circle r="{core_r:.2f}" fill="currentColor" opacity="0.12"/>
        <circle r="{bright_r:.2f}" fill="#fff" filter="drop-shadow(0 0 1.2px #fff)"/>
      </g>
    </symbol>"""
        )

    satellite = """    <!-- Free perks render as small white dots with a colored bloom.
         Use for cost==0 perks and as visual annotations on rolls. -->
    <symbol id="satellite" viewBox="-10 -10 20 20" overflow="visible">
      <circle r="3.2" fill="#fff" opacity="0.88"
              filter="drop-shadow(0 0 2px #fff) drop-shadow(0 0 4px currentColor)"/>
    </symbol>"""

    gradient = """    <linearGradient id="ray-grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0"    stop-color="transparent"/>
      <stop offset="0.34" stop-color="currentColor" stop-opacity="0.075"/>
      <stop offset="0.48" stop-color="#fff" stop-opacity="0.58"/>
      <stop offset="0.50" stop-color="#fff" stop-opacity="0.92"/>
      <stop offset="0.52" stop-color="#fff" stop-opacity="0.58"/>
      <stop offset="0.66" stop-color="currentColor" stop-opacity="0.075"/>
      <stop offset="1"    stop-color="transparent"/>
    </linearGradient>"""

    body_symbols = "\n".join(symbols)
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  Shared diffraction-spike star symbols.

  Each <use href="_star-defs.svg#star-NNN"> reference draws one
  rays-plus-glow star at viewBox -50..50, colored by `currentColor`.
  Bucket boundaries match plans/design_handoff_bcf_visualization/
  redesign/star.jsx → recipeFor(): 100 / 200 / 300 / 400 / 600 / 800 / 1000+.

  To reference: <use href="../_star-defs.svg#star-300" x="0.4" y="-0.3"/>
-->
<svg xmlns="http://www.w3.org/2000/svg" width="0" height="0"
     style="position: absolute; width: 0; height: 0">
  <defs>
{gradient}
{body_symbols}
{satellite}
  </defs>
</svg>
"""
    path.write_text(content)


def write_preview_html(path: Path) -> None:
    """Single-file previewer. Open `_preview.html?file=01-toolkits/gunnm.svg`
    in a browser to render any wireframe SVG against the project's holographic
    panel chrome.

    SVG injection uses DOMParser + adoptNode for safety; the previewer is
    designed for trusted local files in this tree but follows the rule of
    parsing rather than splicing markup.
    """
    path.write_text("""<!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8"/>
          <title>BCF Wireframe Preview</title>
          <link rel="stylesheet" href="_tokens.css"/>
          <style>
            html, body { margin: 0; background: var(--void); color: var(--ink);
                         font-family: var(--sans); min-height: 100vh; }
            header { padding: 12px 18px; border-bottom: 1px solid var(--edge-soft);
                     display: flex; gap: 16px; align-items: baseline; }
            header h1 { font-size: 13px; margin: 0; color: var(--muted);
                        font-weight: 500; letter-spacing: 0.08em; text-transform: uppercase; }
            header .file { font-family: var(--mono); font-size: 12px; color: var(--cyan); }
            main { padding: 24px; display: grid; grid-template-columns: 1fr 360px; gap: 24px; }
            .panel { background: var(--panel-strong); border: 1px solid var(--edge);
                     border-radius: 4px; padding: 18px; box-shadow: 0 0 24px var(--glow) inset; }
            .stage { aspect-ratio: 1 / 1; display: grid; place-items: center; }
            .stage svg { width: 100%; height: 100%; max-width: 600px; }
            .meta h2 { font-size: 12px; margin: 0 0 4px 0; color: var(--muted);
                       text-transform: uppercase; letter-spacing: 0.06em; }
            .meta pre { font-family: var(--mono); font-size: 11px; color: var(--ink);
                        background: var(--void-soft); padding: 12px; border-radius: 3px;
                        overflow: auto; max-height: 80vh; }
            .empty { color: var(--dim); font-style: italic; }
            input[type=text] { background: var(--void-soft); color: var(--ink);
                               border: 1px solid var(--edge-soft); border-radius: 3px;
                               padding: 4px 8px; font-family: var(--mono); width: 320px; }
          </style>
        </head>
        <body>
          <header>
            <h1>Constellation wireframe preview</h1>
            <input type="text" id="picker" placeholder="01-toolkits/gunnm.svg"/>
            <span class="file" id="filename"></span>
          </header>
          <main>
            <div class="panel stage" id="stage">
              <span class="empty">Pass <code>?file=PATH</code> in URL or pick above.</span>
            </div>
            <div class="panel meta">
              <h2>Source</h2>
              <pre id="source">—</pre>
            </div>
          </main>
          <script>
            const params = new URLSearchParams(location.search);
            const stage = document.getElementById('stage');
            const source = document.getElementById('source');
            const picker = document.getElementById('picker');
            const fname = document.getElementById('filename');

            function showEmpty(msg) {
              while (stage.firstChild) stage.removeChild(stage.firstChild);
              const span = document.createElement('span');
              span.className = 'empty';
              span.textContent = msg;
              stage.appendChild(span);
            }

            async function load(rel) {
              if (!rel) return;
              fname.textContent = rel;
              picker.value = rel;
              try {
                const r = await fetch(rel);
                if (!r.ok) throw new Error('HTTP ' + r.status);
                const text = await r.text();
                source.textContent = text;
                const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
                const err = doc.querySelector('parsererror');
                if (err) {
                  showEmpty('Parse error: ' + err.textContent);
                  return;
                }
                const svg = doc.documentElement;
                while (stage.firstChild) stage.removeChild(stage.firstChild);
                stage.appendChild(document.adoptNode(svg));
              } catch (e) {
                showEmpty('Failed to load: ' + e.message);
              }
            }

            picker.addEventListener('change', () => {
              const u = new URL(location.href);
              u.searchParams.set('file', picker.value.trim());
              location.href = u.toString();
            });

            load(params.get('file'));
          </script>
        </body>
        </html>
""")


def write_readme(path: Path, jumps_by_const: dict) -> None:
    rows = []
    for idx, name in enumerate(CONST_HUES.keys(), 1):
        count = len(jumps_by_const.get(name, []))
        rows.append(f"| `{folder_slug(idx, name)}/` | {name} | {CONST_HUES[name]}° | {count} |")
    table = "\n".join(rows)
    total_jumps = sum(len(v) for v in jumps_by_const.values())
    path.write_text(f"""# Constellation Wireframe Workspace

Editable design tree for the 14 cluster constellations ("major
arcana") and their {total_jumps} jump mini-constellations ("minor
arcana"). Generated from `data/derived/constellation_wireframes.json`
by `scripts/scaffold_design_wireframes.py`.

## Folder Layout

```
data/constellations/
  README.md              ← you are here
  _tokens.css            ← design tokens (mirror of redesign/style.css :root)
  _star-defs.svg         ← shared <symbol>s for diffraction-spike stars
  _preview.html          ← in-browser previewer: open with ?file=PATH
  NN-<constellation>/
    _cluster.svg         ← major arcana: cluster silhouette + jump anchors
    _cluster.md          ← shape concept + per-jump index
    <jump-slug>.svg      ← minor arcana: jump mini-constellation
    <jump-slug>.md       ← prose summary + perk table
```

| Folder | Constellation | Hue | Jumps |
|---|---|---|---|
{table}

## Format Conventions

### Coordinate space
All SVGs use a `viewBox` centered on the origin, with positions in
the same `[-1, 1]` normalized range used by `constellation_wireframes.json`.
Cluster SVGs: `viewBox="-1.1 -1.1 2.2 2.2"`. Jump SVGs:
`viewBox="-1.2 -1.2 2.4 2.4"` (a hair larger to give rays headroom).

### Stars
Per-jump SVGs reference shared symbols from `_star-defs.svg`:

```svg
<use href="../_star-defs.svg#star-300" x="0.40" y="-0.30"
     data-perk-name="Mixing Mixtures" data-cost="300"
     data-status="Obtained"/>
```

Cost buckets (mapping in `scripts/scaffold_design_wireframes.py:bucket_for`):
`<=199 → star-100`, `<=299 → star-200`, `<=399 → star-300`,
`<=599 → star-400`, `<=799 → star-600`, `<=999 → star-800`,
`>=1000 → star-1000`. Cost `0` perks use `#satellite`.

Each `<use>` carries `data-perk-name`, `data-cost`, `data-status`
for round-trip tooling. The `x`/`y` attributes are authoritative.

### Color
Each per-jump SVG declares `color="oklch(0.78 0.13 <hue>)"` on the
root `<svg>`. The shared `<symbol>`s draw rays in `currentColor`,
so the constellation hue propagates without per-star color values.

### Cluster silhouettes
`_cluster.svg` ships with a placeholder convex-hull polyline derived
from `marker_positions`. The `shape_concept` (e.g. "open-end wrench")
is the artistic target — Design replaces the polyline with a
hand-authored shape that matches the metaphor.

## Round-trip to Project

| Source of truth in JSON | Lives in SVG as |
|---|---|
| `cluster_constellations[].marker_positions[]` | anchor `<g>` `transform="translate(x y)"` in `_cluster.svg` |
| `jump_constellations[].stars[].{{x,y}}` | `<use>` `x` / `y` attributes in `<jump-slug>.svg` |
| `jump_constellations[].stars[].cost` | implicit in `data-cost` and choice of bucket symbol |
| `jump_constellations[].shape_concept` | `<desc>` element in jump SVG + paragraph in `.md` |

A future `scripts/sync_wireframes_from_design.py` (not yet written)
will read SVGs, extract `<use data-perk-name x y>` triples, and patch
the JSON. For now the SVG layer is *downstream* of JSON; if you change
canonical positions in JSON, re-run the scaffolder.

## Iterating

1. `python -m http.server` in this directory.
2. Open `_preview.html?file=01-toolkits/_cluster.svg` (or any jump SVG)
   in a browser.
3. Edit the SVG in any text editor; reload to see changes.
4. To retune the diffraction recipe itself, edit `_star-defs.svg` —
   every star in the tree reflects the change.

## Open Design Questions

- Cluster silhouette: convex hull is a placeholder. Hand-authored
  polylines per `shape_concept` are the design target.
- Free perks (`cost == 0`, 7 in total) currently render as
  `#satellite` dots at their own `(x, y)`. Alternative: attach them
  as visual children of the nearest paid star.
- "Unknown cost" perks (21 in total, `cost == null`) currently fall
  through to the `star-100` bucket. Design call needed on whether
  these warrant a distinct treatment.
""")


# ---------------------------------------------------------------------------
# Per-constellation generation
# ---------------------------------------------------------------------------

def color_for(hue: int) -> str:
    return f"oklch(0.78 0.13 {hue})"


def write_cluster_svg(path: Path, const_name: str, hue: int, jumps: list, marker_positions: list) -> None:
    """Major-arcana wireframe.

    Pre-populated with: a placeholder convex-hull polyline derived from
    marker_positions, plus a small dot at each anchor. Anchors are no
    longer 1:1 with jumps (marker count is hand-authored per the
    constellation's silhouette); jump labels are dropped, leaving the
    raw anchor lattice for Design to compose against.
    """
    pts = [(float(v[0]), float(v[1])) for v in marker_positions]
    hull_pts = _convex_hull(pts) if len(pts) >= 3 else pts
    hull_d = " ".join(f"{x:.3f},{y:.3f}" for x, y in hull_pts)

    anchors = []
    for idx, (x, y) in enumerate(pts):
        anchors.append(
f"""    <g class="anchor" transform="translate({x:.3f} {y:.3f})"
       data-anchor-index="{idx}">
      <circle r="0.018" fill="currentColor" opacity="0.65"/>
      <text x="0.028" y="0.012" font-family="ui-monospace, Menlo, monospace"
            font-size="0.038" fill="currentColor" opacity="0.55">anchor {idx}</text>
    </g>"""
        )

    body = "\n".join(anchors)
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  Major arcana: {const_name}
  Hue: {hue}°
  Jumps in cluster: {len(jumps)}

  Design target: replace the placeholder convex hull with a polyline
  silhouette that evokes the shape concept above. Jump anchors are
  authoritative positions sourced from constellation_wireframes.json —
  move them only if intentionally retuning the cluster layout.
-->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1.1 -1.1 2.2 2.2"
     color="{color_for(hue)}"
     style="background: #03080d">
  <title>{_xml_text(const_name)}</title>
  <desc>Cluster silhouette for the {_xml_text(const_name)} constellation. Shape concept TBD.</desc>

  <!-- PLACEHOLDER: convex hull of jump anchor positions. -->
  <polygon class="cluster-hull" points="{hull_d}"
           fill="currentColor" fill-opacity="0.06"
           stroke="currentColor" stroke-opacity="0.35" stroke-width="0.006"/>

  <!-- Jump anchors. Each one is the seed position for one jump's
       mini-constellation. -->
  <g class="jump-anchors">
{body}
  </g>
</svg>
"""
    path.write_text(svg)


def write_cluster_md(path: Path, const_name: str, hue: int, shape_concept: str, jumps: list) -> None:
    rows = []
    for j in sorted(jumps, key=lambda j: j["jump"].lower()):
        jname = j["jump"]
        sl = slug(jname)
        nperks = len(j.get("stars", []))
        sc = j.get("shape_concept", "").split(":", 1)[0]
        rows.append(f"| [`{sl}`](./{sl}.svg) | {jname} | {nperks} | {sc} |")

    body = "\n".join(rows)
    path.write_text(f"""# {const_name}

- **Hue:** `oklch(0.78 0.13 {hue})` ({hue}°)
- **Shape concept:** {shape_concept}
- **Jumps in cluster:** {len(jumps)}

## Major Arcana Wireframe

See [`_cluster.svg`](./_cluster.svg). The current rendering uses a
convex-hull placeholder for the silhouette; the design pass should
replace it with a polyline that matches the shape concept above.

## Minor Arcana — Jumps

| Slug | Jump | Perks | Shape Concept |
|---|---|---|---|
{body}
""")


def write_jump_svg(path: Path, const_name: str, hue: int, jump: dict) -> None:
    uses = []
    for s in jump.get("stars", []):
        x = s.get("x") if s.get("x") is not None else 0.0
        y = s.get("y") if s.get("y") is not None else 0.0
        cost = s.get("cost")
        sym = bucket_for(cost)
        uses.append(
f"""    <use href="../_star-defs.svg#{sym}" x="{x:.3f}" y="{y:.3f}"
         width="0.30" height="0.30" transform="translate(-0.15 -0.15)"
         data-perk-name="{_xml_attr(s.get("perk_name",""))}"
         data-cost="{cost if cost is not None else ""}"
         data-status="{_xml_attr(s.get("status",""))}"/>"""
        )

    nstars = len(jump.get("stars", []))
    paid = sum(1 for s in jump.get("stars", []) if (s.get("cost") or 0) > 0)
    free = nstars - paid
    body = "\n".join(uses)

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  Minor arcana: {jump['constellation']} · {jump['jump']}
  Stars: {nstars} ({paid} paid, {free} free/satellite)
  Shape concept: {jump.get('shape_concept', '')}

  Star positions are authoritative — sourced from
  constellation_wireframes.json. Edit positions here, then run the
  (future) sync script to push back into the JSON layer.
-->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1.2 -1.2 2.4 2.4"
     color="{color_for(hue)}"
     style="background: #03080d">
  <title>{_xml_text(jump['jump'])} ({_xml_text(const_name)})</title>
  <desc>{_xml_text(jump.get('shape_concept', ''))}</desc>

  <!-- Per-jump silhouette polyline lives here. The shape concept
       above is the design target. Today: blank — author the line. -->
  <g class="jump-silhouette"></g>

  <!-- Stars: each one renders a diffraction-spike marker via the
       shared symbol set in ../_star-defs.svg. -->
  <g class="jump-stars">
{body}
  </g>
</svg>
"""
    path.write_text(svg)


def write_jump_md(path: Path, const_name: str, hue: int, jump: dict) -> None:
    """Per-jump summary + perk table. Summary is structural (data-derived);
    Design fleshes out narrative voice as needed."""
    stars = jump.get("stars", [])
    free = [s for s in stars if (s.get("cost") or 0) == 0]
    obtained = sum(1 for s in stars if s.get("status") == "Obtained")
    total = len(stars)

    summary = (
        f"The **{jump['jump']}** jump in the {const_name} constellation has "
        f"{total} perk{'s' if total != 1 else ''} ({obtained} obtained, "
        f"{total - obtained} still available). "
        f"Wireframe shape concept: *{jump.get('shape_concept', 'unspecified')}.* "
    )
    if free:
        summary += (
            f"Includes {len(free)} free perk{'s' if len(free) != 1 else ''} "
            "rendered as satellite dots. "
        )

    perk_rows = []
    for s in sorted(stars, key=lambda s: -(s.get("cost") or 0)):
        cost = s.get("cost")
        sym = bucket_for(cost)
        cost_label = "free" if cost == 0 else (str(cost) if cost is not None else "?")
        treatment = "satellite dot" if sym == "satellite" else f"`{sym}` diffraction spike"
        perk_rows.append(
            f"| {s.get('perk_name','')} | {cost_label} | {treatment} | {s.get('status','')} |"
        )

    perk_body = "\n".join(perk_rows) if perk_rows else "| _no perks defined in wireframe_ | | | |"
    sl = slug(jump['jump'])
    path.write_text(f"""# {jump['constellation']} · {jump['jump']}

{summary}

- **Hue:** `oklch(0.78 0.13 {hue})` ({hue}°)
- **Wireframe:** [`{sl}.svg`](./{sl}.svg)
- **Shape concept:** {jump.get('shape_concept', '')}

## Perks

| Perk | Cost (CP) | Star Treatment | Status |
|---|---|---|---|
{perk_body}

## Design Notes

- Star positions in the SVG are the source of truth for visual
  layout; the canonical positions live in
  `data/derived/constellation_wireframes.json` and are mirrored on
  each `<use>` element's `x` / `y` attributes.
- Free perks (cost = 0) use the shared `#satellite` symbol. If the
  design wants them visually attached to a paid star instead of
  standing alone, move the `<use>` into the same group as the parent
  star and adjust position.
- The jump silhouette polyline (group `jump-silhouette` in the SVG)
  is unset — author a line that evokes the shape concept.
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _xml_attr(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _xml_text(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _convex_hull(pts):
    """Andrew's monotone chain. Returns hull in CCW order."""
    pts = sorted(set(pts))
    if len(pts) <= 1:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    data = json.loads((DATA / "constellation_wireframes.json").read_text())
    clusters = data["cluster_constellations"]
    jumps = data["jump_constellations"]

    jumps_by_const = {}
    for j in jumps:
        jumps_by_const.setdefault(j["constellation"], []).append(j)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    write_tokens_css(OUT / "_tokens.css")
    write_star_defs(OUT / "_star-defs.svg")
    write_preview_html(OUT / "_preview.html")
    write_readme(OUT / "README.md", jumps_by_const)

    cluster_by_name = {c["name"]: c for c in clusters}
    for idx, name in enumerate(CONST_HUES.keys(), 1):
        hue = CONST_HUES[name]
        cluster = cluster_by_name.get(name, {})
        const_jumps = jumps_by_const.get(name, [])
        folder = OUT / folder_slug(idx, name)
        folder.mkdir()

        write_cluster_svg(
            folder / "_cluster.svg",
            const_name=name, hue=hue,
            jumps=const_jumps,
            marker_positions=cluster.get("marker_positions", []),
        )
        write_cluster_md(
            folder / "_cluster.md",
            const_name=name, hue=hue,
            shape_concept=cluster.get("shape_concept", ""),
            jumps=const_jumps,
        )
        for j in const_jumps:
            sl = slug(j["jump"])
            write_jump_svg(folder / f"{sl}.svg", const_name=name, hue=hue, jump=j)
            write_jump_md(folder / f"{sl}.md", const_name=name, hue=hue, jump=j)

    print(f"Wrote scaffold to {OUT.relative_to(ROOT)}")
    for idx, name in enumerate(CONST_HUES.keys(), 1):
        n = len(jumps_by_const.get(name, []))
        print(f"  {folder_slug(idx, name):<32} {n:>3} jumps")


if __name__ == "__main__":
    main()
