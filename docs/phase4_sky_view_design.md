# Phase 4 — Celestial Sky View: UX & Architecture Design

**Status:** design proposal, pre-implementation
**Scope:** the 3D "planetarium" view layered on top of the existing
Phase 3 scrubber UI.
**Out of scope:** picking a 3D library (parallel task), parser changes,
final art polish, sound.

This document describes *what* the experience should look and feel
like and the data/render plumbing it implies. It deliberately leaves
implementation detail (which library, which shader, which easing
curve) to the implementor.

---

## 1. Overall composition and camera setup

The user sits at the center of a unit celestial sphere — a true
inside-out 3D view, not a 2D pan/zoom of a starfield texture. There
is exactly one camera, anchored at the origin, with FOV around
60–70°. The horizon, ground, etc. do not exist; this is pure sky.

At rest (page load, scrubber un-touched on whatever the default
chapter is), the camera looks at the **Toolkits** cluster
constellation centered slightly above eye-line. Toolkits is the
"first" constellation narratively (chapter 1's Workshop is a
Toolkits/Personal Reality acquisition) and it's also the largest
constellation by perk count, so it makes a visually-rich opening
shot.

Default screen layout:

```
+----------------------------------------------------+
| header: Brockton's Celestial Forge — Sky View      |
+----------------------------------------------------+
| scrubber (sticky, same component as Phase 3)       |
| readout: ch N · title · date                       |
+----------------------------------------------------+
|                                                    |
|              [   3D sky canvas   ]                 |
|                                                    |
|        (fills remaining viewport height)           |
|                                                    |
+----------------------------------------------------+
| inspector strip (collapses on hover/empty)         |
+----------------------------------------------------+
```

The 3D canvas is the dominant element. Hover/click info renders into
a small **inspector strip** (or floating tooltip) below the canvas
rather than over it, to keep the sky uncluttered.

The sphere has:
- A dark, near-black background (the void of "untold story").
- A very faint nebula-like noise gradient so the void isn't flat
  black — gives subtle parallax cues during rotation.
- No grid, no axes, no compass. The only orientation cue is the
  constellations themselves.

---

## 2. Constellation positioning system (14 clusters on a sphere)

**Recommendation: Fibonacci sphere distribution with manual
narrative-grouping nudges.**

A pure equator-ring of 14 fails because:
- It collapses the experience to 2D-ish (everything around the waist).
- It doesn't feel like a "sky" — there's nothing overhead, nothing
  underfoot.
- 14 around an equator gives ~26° between centers, which is too
  cramped once each cluster expands to its themed shape.

A pure Fibonacci/spiral sphere (golden-angle distribution) gives 14
points roughly evenly spaced (~50° great-circle separation between
nearest neighbors), which leaves room for each cluster's shape plus
the connecting filaments without crowding.

But pure Fibonacci is *too* uniform — narratively related
constellations end up scattered. So we apply **manual nudges** after
the auto-layout to:

- Keep **Capstone** and **Personal Reality** roughly opposite the
  default-camera direction (Toolkits) — they're the late-game
  constellations and feel right "behind" the user at start.
- Cluster **Magic / Magitech / Alchemy** in the same hemisphere
  (they're thematically linked: arcane, semi-arcane, transmutational).
- Keep **Crafting / Clothing / Quality / Size** loosely in another
  hemisphere (these are the "make a thing better" cluster).
- Keep **Knowledge / Time / Vehicles / Resources and Durability**
  roughly equatorial as "infrastructure" constellations.

The implementor should hand-tune positions after the Fibonacci seed,
verify no two cluster *bounding circles* overlap on the sphere, and
commit the final 14 unit-sphere positions as a small JSON config
(e.g. `web/sky/cluster_positions.json`) so it's easy to iterate
without code changes.

**Why this approach**: it gets the visual benefits of even
distribution (no obvious clumps, every part of the sky is
"interesting" once revealed) while still letting narrative association
inform the layout.

### Cluster shapes

Each of the 14 cluster constellations has a **silhouette inspired by
its theme**:

| Cluster | Suggested shape (vertices = jump positions) |
|---|---|
| Toolkits | wrench / spanner outline |
| Knowledge | open book |
| Vehicles | stylized car or rocket profile |
| Time | hourglass |
| Crafting | hammer-and-anvil |
| Clothing | coat / dress silhouette |
| Magic | five-pointed star with a circle |
| Quality | gem / faceted diamond |
| Size | nested squares (small → large) |
| Resources and Durability | shield |
| Magitech | gear with a wand through it |
| Alchemy | flask |
| Capstone | crown |
| Personal Reality | doorway / portal arch |

These are *star-pattern abstractions*, not literal icons. The shape
gives the silhouette; the actual rendered nodes are the jump
positions and the connecting lines are subtle. Think real-world
constellations: "Orion is a hunter" but you mostly see seven dots and
some implied lines.

Concretely, each cluster's outline polyline visits its jump-position
vertices in a fixed order. The implementor draws faint lines along
that polyline (see §7).

---

## 3. Coordinate system: mapping wireframes to the sphere

A parallel task is producing `data/derived/constellation_wireframes.json`.
Expected schema (subject to that task's output, but design assumes):

```json
{
  "clusters": {
    "Toolkits": {
      "shape_outline_2d": [[x,y], [x,y], ...],   // unit-bbox normalized
      "jumps": {
        "Personal Reality": {
          "anchor_2d": [x, y],                    // where this jump sits
                                                  // *within* the cluster shape
          "perks": [
            { "name": "Workshop: Metalworking",
              "cost": 100,
              "star_offset_2d": [x, y] },          // per-perk position
                                                  // *within* the jump's mini-constellation
            ...
          ]
        }
      }
    }
  }
}
```

All 2D coordinates are in unit-bbox space (`[-1, 1]` or `[0, 1]`,
implementor's call once the parallel task lands).

**Two-stage mapping (cluster → sphere, perk → cluster-local sphere
patch):**

1. **Cluster placement.** Each cluster has a unit-sphere center
   `C ∈ R³, |C|=1` (from the Fibonacci+nudge step) and a local
   tangent frame `(U, V)` orthonormal to `C`. Define an *angular
   radius* `α_cluster ≈ 18°` — how big the cluster appears in the
   sky. (Tunable per-cluster if a constellation has many jumps and
   needs more room.)

2. **Jump anchor placement.** For a 2D anchor `(x, y)` in the
   cluster's wireframe, the 3D direction is

   ```
   d = normalize( C + tan(α_cluster) * (x*U + y*V) )
   ```

   This is the gnomonic projection of the wireframe onto the
   tangent plane at `C`, then re-projected to the sphere. For
   `α_cluster ≈ 18°`, distortion is invisible. Each jump's anchor
   becomes a 3D point on the unit sphere.

3. **Perk-star placement within a jump.** Each jump has its own
   smaller angular radius `α_jump ≈ 3–5°` and a local tangent frame
   at the jump's anchor. Same gnomonic mapping for each perk's
   `star_offset_2d`. Perks become 3D points clustered tightly
   around the jump anchor.

This gives a clean hierarchy: the sky is divided into 14 ~36°
patches; each patch is divided into N jumps (~6–10° each); each jump
is a ~6–10° mini-constellation of 1–20 perk stars.

**Why gnomonic projection:** it's the standard "flat patch on a
sphere" map, it's invertible (great for picking — see §5), and
straight lines in the wireframe map to great-circle arcs on the
sphere, which look right when drawing connecting lines.

**Open issue:** if a jump has many perks (e.g. Personal Reality has
several), `α_jump` may need to scale with perk count. The wireframes
producer can either bake this in (output already-scaled offsets) or
the renderer can scale per-jump from a perk count it computes from
`obtained_perks.json` + `perks_catalog.json`. Defer to the
implementor.

---

## 4. Animation pipeline

Five animation systems run concurrently. Each is described here as
a small state machine or timeline. They share a single per-frame
"current state" object derived from `(scrubber_chapter_idx,
last_scrubber_chapter_idx, time_since_scrub_change, mode)` where
`mode ∈ { idle, scrubbing, roll_focus }`.

### 4.1 Sphere rotation (driven by scrubber)

Continuous mapping: `sphere_yaw = base_yaw + chapter_idx * Δ`
where `Δ ≈ 1.0–1.5°` per chapter. Across 194 chapters that's a full
~290° rotation — almost a full revolution from chapter 1 to current.

Implementation: rotate the *world* around a fixed Y-axis (the
sphere's "polar" axis), not the camera. Camera stays at origin
looking at its current focal point; the world spins underneath it.

A small `pitch` component (~30° total over the full story) tilts the
view slightly so that constellations near the poles are
occasionally seen from below — gives a sense of 3D depth as the
scrubber moves.

Rotation is *eased toward* the target yaw, never snapped. When the
user drags the scrubber rapidly, the yaw catches up over ~300ms.
This gives the "the sky is settling" feel rather than "the sky is
glued to the cursor."

### 4.2 Camera focus (where the camera looks)

Default focal point: cluster center of whichever cluster the user
last interacted with, or Toolkits at startup.

When the scrubber crosses a chapter where Joe acquires a perk in
cluster X, the focal point eases over ~600ms toward cluster X. If
the user is actively dragging the scrubber, the focal point follows
the *most recent acquired-perk cluster* and re-eases as the
acquisition cluster changes. This produces a natural "the camera
follows the action" feel without violating user agency (the user
can always grab and drag the camera to re-aim it manually — see
§5).

### 4.3 Fog clearing (per-cluster, per-jump reveal)

Each cluster and each jump has a `revealed_at_chapter_idx` (computed
once at load time from `obtained_perks.json`: the lowest chapter idx
where any perk in that cluster/jump was acquired).

Render state per cluster/jump:

```
state ∈ { hidden, revealing, revealed }
```

- `hidden`: scrubber is before reveal idx. Fuzzy, low-saturation,
  low-opacity. Stars are blurred (or rendered as dim glow blobs
  rather than crisp points). Connecting lines invisible.
- `revealing`: scrubber within ±1 chapter of reveal idx. Lerp
  opacity 0.2→1.0, blur radius high→0, saturation low→full. ~800ms
  envelope. Small subtle "shimmer" pulse at the moment of reveal.
- `revealed`: full crispness. Stays revealed even if the user
  scrubs back (showing fog of unknown only when scrubbing forward
  through unseen sky for the first time). Optional: if user holds
  the scrubber at an early chapter for >2s, re-fog the not-yet-
  revealed clusters. Defer this decision — see §8.

### 4.4 Star pulse (acquired perks)

Each star has an `acquired ∈ { not, paid, free }` flag derived from
`obtained_perks.json` filtered by `acquired_chapter ≤
current_chapter`.

- `not`: small fixed dot, dim color (think "background star").
- `paid`: gentle pulse, period ~3s, brightness oscillating ±15%.
  Color: a warm white/gold halo around a saturated core matching
  the cluster's accent color.
- `free`: same pulse cadence but color-shifted to a cool teal/blue
  halo. This makes the paid-vs-free distinction immediately
  legible in a wide shot without needing to read names.

Star size encodes cost (per spec):
- 100 CP → small (~1.5px at 1× zoom)
- 200–400 CP → medium (~2.5px)
- 600 CP → large (~4px)
- 800 CP → extra large (~5px) with a faint diffraction-spike effect
  to mark it as a capstone-tier perk

These pixel sizes are baseline at default camera zoom; real values
scale with zoom level and pixel ratio.

### 4.5 Roll firing animation

Driven by `predicted_rolls.json`. Each entry has
`(chapter_num, word_position, roll_number)`.

When the user scrubs into a chapter that contains a predicted roll
(or several), the roll animation queue plays. State machine per roll:

```
queued → camera_zoom_in → reach_extends → resolve(hit|miss) → camera_zoom_out → done
```

- **camera_zoom_in** (~400ms, eased): camera focal point eases to
  the rolled jump's 3D position. FOV narrows from ~65° to ~30° to
  give a "zoom" feel without changing camera position.
- **reach_extends** (~250ms): a placeholder thin gold raycast or
  glow filament extends from the camera origin toward the rolled
  jump's center (or toward the specific perk for a hit). This is
  the "Joe's reach extends" beat.
- **resolve**:
  - *Hit* (acquisition matched in `obtained_perks.json` for this
    chapter and jump): the matched perk star flares, transitions
    to its `paid` or `free` pulsing state. Optional small text
    overlay: perk name. Reach line collapses into the star.
  - *Miss* (no `obtained_perks` entry matches at this jump for
    this chapter, or `predicted_rolls` indicates we couldn't
    align): camera pans across the jump without highlighting any
    specific star. Reach line fades out without landing.
- **camera_zoom_out** (~400ms): FOV widens back to default;
  focal point may stay or revert to cluster center.

If multiple rolls fire in the same chapter, they queue and play in
sequence at 1.2× speed each, capped at total ~3s of animation per
chapter so rapid-scrubbing isn't blocked.

When the user drags the scrubber **fast** (e.g. multiple chapters
per second), the roll animation is suppressed entirely — only the
sphere rotation and fog reveal play. The roll animation only fires
when the scrubber has been stationary for >300ms on a chapter that
contains rolls. This avoids the animation queue from chasing a
user who's clearly skimming.

**Hooks for polish (deferred):**
- `onRollStart(roll, jump, cluster)` — placeholder no-op; sound
  designer can wire up a chime here.
- `onRollResolve(roll, hitPerk?)` — placeholder no-op; particle FX
  can hook in.
- The reach-line geometry should be a separate render pass so
  shader polish can drop in later without touching star/cluster
  rendering.

---

## 5. Interaction model

| Input | Effect |
|---|---|
| Drag scrubber (mouse, touch, keyboard — same as Phase 3) | Drives `current_chapter_idx`. Sphere rotates, camera focus follows acquisitions, fog clears, stars pulse. |
| Hover a star (desktop) | Tooltip with: perk name, jump, cluster, cost, acquired chapter (or "not acquired"). |
| Tap a star (touch) | Same tooltip; second tap dismisses. |
| Click a cluster outline / cluster center | Camera eases focal point to that cluster center over ~500ms. Sphere rotation paused for ~1s after to "let the user look." |
| Click an empty area of sky | Returns focal point to whatever cluster is closest to the current scrubber's most recent acquisition. |
| Drag the canvas (mouse middle/right, or two-finger touch) | Manual camera aim — overrides the scrubber-driven focus until next scrubber move or 5s of inactivity. Yaw and pitch only; no roll. |
| Scroll wheel / pinch | Zoom (FOV narrow/wide), clamped to 25°–80°. |
| Keyboard `[` and `]` | Cycle camera focus between cluster centers (alphabetical or `CONSTELLATION_ORDER` from `web/app.js`). |
| Keyboard `0` | Reset camera to default cluster + default zoom. |

**Picking (hover/click resolution):** since stars are small and
clustered, screen-space picking with a generous radius (~10px)
beats true ray-into-sphere picking. On hover, take the cursor's
current screen position, transform every visible star's 3D position
to screen space (cheap), find the nearest one within the radius
threshold, prefer the one with smallest screen distance. This also
handles touch correctly without finicky tap-targets.

---

## 6. Performance plan

Headline numbers for capacity:
- 504 acquired perks (current obtained_perks.json count)
- ~651 perks total in catalog (perks_catalog.json) — full sky once
  reconciliation lands ~700 stars
- 14 cluster outlines
- ~80–120 jump mini-constellations (rough estimate; once
  wireframes lands this can be exact)
- ~700 connecting line segments

Even on the high end this is small for any modern 3D library. The
real performance risks are:

1. **Per-frame DOM/text updates** for tooltips. Solution: only
   re-render tooltip on *change*, not every frame. Throttle the
   hover-pick routine to ~30Hz.

2. **Per-star animation cost.** Solution: instance all stars in a
   single instanced-mesh draw call. Per-instance attributes:
   `position`, `size`, `color`, `phase` (for pulse offset),
   `state` (acquired / not). Pulse animation done in the vertex
   shader from `phase + time` so the CPU never touches per-star
   data per frame.

3. **Fog/blur per cluster.** Avoid per-pixel post-processing if
   possible. Implement "fog" as a per-cluster opacity + saturation
   uniform, applied in the fragment shader for that cluster's
   draw call. Cluster shapes can be one draw call each (14 total),
   which is cheap.

4. **Connecting lines.** Use line-segment instancing or one big
   `LineSegments` mesh per cluster. ~700 line segments total is
   trivial.

**LOD:** probably not needed at this scale, but a simple LOD hook
makes sense in case future expansion (more perks, more detail per
star) makes it useful. Hook: cluster bounding cone vs view frustum
— if a cluster is fully behind the camera, skip its update.

**Frustum culling:** rely on the 3D library's built-in frustum
culling per draw call. Since each cluster is a tight bounding
sphere, culling is effective: typically 5–8 of 14 clusters are
visible at any moment.

**Target:** stable 60fps on a 2020-era laptop integrated GPU; no
specific mobile target (per the spec, mobile is nice-to-have).

**Memory:** all data fits in <2MB JSON. No streaming, no LOD
asset loading. Load everything at startup.

---

## 7. Connection lines

Two layers:

### 7.1 Within-jump lines (perk-to-perk)

For each jump, draw faint lines connecting its perk stars in the
order specified by the wireframe (or, if the wireframe doesn't
specify, a minimum spanning tree of perk positions in the jump's
local 2D space, then drawn as great-circle arcs on the sphere).

Color: low-opacity (~0.3) version of the cluster's accent color.
Width: 1px.

These appear when the jump is `revealed`. They fade in along with
the jump's stars.

### 7.2 Cluster outline lines (jump-to-jump)

For each cluster, the cluster's outline polyline (from the
wireframe's `shape_outline_2d`) is drawn as great-circle arcs
between the jump anchors that form the cluster's themed silhouette
(wrench, book, etc.).

Color: even fainter (~0.15) version of the accent color, so the
*shape* is implied more than drawn. The viewer reads it the way
you read Orion — pattern recognition, not explicit lines.

Width: 1px.

These appear when the cluster has any revealed jump (lower bar
than fully-revealed) — so the silhouette starts emerging as Joe
explores the cluster.

---

## 8. Accessibility notes

### Color choice

Cluster accent colors must be distinguishable from each other for
the dominant forms of color-vision deficiency. Use a 14-color
palette built off ColorBrewer or Wong's 8-color CVD-safe palette
(extended), and verify with a deuteranopia/protanopia simulator
before committing.

Critically, the **paid vs free** distinction must NOT rely on color
alone. The spec already calls for different visual treatments
(halo color); add a structural difference too: free-bonus stars
have a subtle ring, paid stars a solid disk. The pulse cadence
could also differ (paid: smooth sine; free: sharper attack-decay).

Star *size* already encodes cost — that's a structural channel,
good.

### Motion preferences

Honor `prefers-reduced-motion: reduce`:
- Disable continuous rotation (sphere rotates only when scrubber
  moves, with no easing — snap to target).
- Disable star pulse (acquired stars are slightly brighter than
  unacquired, no animation).
- Disable roll firing animation (just flash the perk star once).
- Fog clearing snaps instead of fading.

### Keyboard navigation

Beyond the per-cluster `[` / `]` cycling and `0` reset (§5):

- Tab focus enters the canvas — when focused, arrow keys nudge the
  camera aim by ~5° each.
- `Enter` or `Space` on a focused cluster triggers the same effect
  as clicking it.
- `Esc` exits canvas focus, returns to scrubber.
- Tooltip content for a hovered/focused star should also be
  exposed via an aria-live region so a screen reader announces it.

This won't make the 3D visualization *fully* accessible to a
screen-reader user — that's a fundamental constraint of the
medium — but it ensures the *data underneath* is reachable. The
existing Phase 3 scrubber view should remain the primary
accessible path to the same information.

### Contrast

Background near-black + cluster colors at full saturation gives
good contrast. Tooltips render on a high-contrast translucent dark
panel with a 1px light border (matching the existing Phase 3 panel
aesthetic but inverted for the dark canvas).

---

## 9. Open questions / decisions deferred to implementation

1. **Re-fog on backwards scrub?** §4.3 leaves this open. Two
   reasonable behaviors: (a) once revealed, always revealed
   (simple, less surprising); (b) re-fog when scrubber goes back
   so the "fog of unknown" is faithful to the moment in the story
   (more evocative, more startling). Recommend (a) for v1; (b) is
   a future polish toggle.

2. **Cluster outline visibility before reveal.** Should the
   silhouette of each cluster be visible from the start (so the
   user sees a wrench-shape from chapter 1, even before any jump
   in it is revealed) or only emerge as jumps are revealed? Spec
   implies the latter ("constellations that haven't been revealed
   render fuzzy"). But seeing the silhouette of the unknown sky
   may be more inviting than seeing a black void. Defer; suggest
   showing a *very* faint outline (0.05 opacity) before reveal,
   then sharpening as jumps appear.

3. **Per-jump α_jump scaling.** §3 — does the renderer compute
   it, or does the wireframe producer bake it in? Coordinate
   with the wireframes-producing task.

4. **Roll animation behavior at chapter boundary.** If the user
   scrubs from chapter 50 to chapter 52, do the rolls in chapter
   51 fire? (Probably no — only the rolls in the *currently
   selected* chapter fire when you arrive.) Confirm with user.

5. **Non-reconciled perks.** The 31 catalog gaps + 56 cosmetic
   variants from spot-check mean ~5–10% of acquired perks may not
   have a wireframe star to attach to. Render them as a generic
   "loose stars" cluster floating near the cluster they belong
   to? Or omit and surface in the inspector strip? Defer; suggest
   a small "unreconciled" star group that floats just outside the
   cluster's outline.

6. **Default chapter on load.** Currently Phase 3 loads at the
   *latest* chapter. For the sky view, loading at the latest
   chapter means the sky is fully revealed — which loses the
   discovery experience. Suggest loading at chapter 1 (or
   the user's last position via `localStorage`). Confirm.

7. **Predicted roll vs actual acquisition matching.**
   `predicted_rolls.json` gives ~665 predicted rolls;
   `obtained_perks.json` gives 504 acquisitions. Need a clear
   join rule: for each predicted roll in a chapter, is there an
   acquisition? If yes → hit, animate to that perk. If no → miss,
   pan past. Some chapters have more acquisitions than predicted
   rolls (free bonuses); decide whether free bonuses fire their
   own roll animation or appear silently.

8. **Sound.** Out of scope for v1 per design constraints, but the
   roll animation hooks (§4.5) leave space for it.

---

## 10. Wireframe sketches

### State A — at rest (first load, scrubber at chapter 1)

```
+------------------------------------------------------------+
| Brockton's Celestial Forge — Sky View                      |
+------------------------------------------------------------+
| [=|---------------------------------------------]  ch 1    |
| ch 1 · Introduction · 2020-07-19                           |
+------------------------------------------------------------+
|                                                            |
|        .  .                                                |
|         .                          (faint, blurred         |
|       . * .                         silhouettes —          |
|        ` `                          unrevealed clusters)   |
|         .                                                  |
|                                                            |
|              ~~Toolkits~~ (sharp, in focus)                |
|              .--*--*-.                                     |
|             /         \      ← wrench-shaped outline       |
|            *     *     *        with jump anchors          |
|             \   / \   /         as star nodes              |
|              `*'   `*'                                     |
|                                                            |
|       . .                          . .                     |
|        .         (other clusters fuzzy)         .          |
|                                                            |
+------------------------------------------------------------+
| hover a star for detail                                    |
+------------------------------------------------------------+
```

### State B — mid-scrub (user dragging scrubber to chapter 75)

```
+------------------------------------------------------------+
| Brockton's Celestial Forge — Sky View                      |
+------------------------------------------------------------+
| [============|=================================] ch 75    |
| ch 75 · The Toolkit · 2022-09-04                           |
+------------------------------------------------------------+
|                                                            |
|         (sphere has rotated ~75 * 1.5° = ~112° from start) |
|                                                            |
|   .--*--.       .--*--*--.       *  *  *                   |
|   |  *  |        \   *   /        \ * /                    |
|   *--*--*         *-----*           V       (most clusters |
|   Crafting        Knowledge       Magic      revealed,     |
|   (revealed)      (revealed)     (revealed)   sharp)       |
|                                                            |
|             . .         (Capstone, Personal Reality        |
|              .          still partially fogged — Joe       |
|           . . .         hasn't reached them yet)           |
|                                                            |
|   * * stars pulse softly where Joe has acquired perks      |
|       gold halo = paid; teal ring = free bonus             |
+------------------------------------------------------------+
| 504 perks visible · hover for detail                       |
+------------------------------------------------------------+
```

### State C — mid-roll (camera zoomed in on a jump, reach extending)

```
+------------------------------------------------------------+
| Brockton's Celestial Forge — Sky View                      |
+------------------------------------------------------------+
| [================|==============================] ch 91    |
| ch 91 · The Toolkit · 2023-01-15                           |
+------------------------------------------------------------+
|                                                            |
|                                                            |
|                                                            |
|                                                            |
|                  *                                         |
|                  |  ← reach-line filament extending        |
|                  |                                         |
|                  |             [zoomed view of Sabaton     |
|         *--------*-------*       jump within Toolkits      |
|        / \      |       / \      cluster]                  |
|       /   \     |      /   \                               |
|      *     *    |     *     *                              |
|             \   |   /                                      |
|              \  *  /  ← rolled perk: "The Toolkit"         |
|               \ | /     (about to flare and pulse)         |
|                \|/                                         |
|                 *                                          |
|                                                            |
|       (FOV narrowed; rest of sky dimmed)                   |
|                                                            |
+------------------------------------------------------------+
| Roll #312 · The Toolkit (Sabaton) · 100 CP · acquired     |
+------------------------------------------------------------+
```

The transition between B and C lasts ~400ms in; the resolve and
zoom-out lasts another ~600ms. If the user scrubs again during the
animation, the animation aborts cleanly and the new scrubber
position takes over.
