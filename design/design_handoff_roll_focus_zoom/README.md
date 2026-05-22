# Handoff: Sky View Roll Focus & Zoom

## Overview

This handoff replaces the **roll info popup** (`renderJumpFocus` in `web/app.js`) with a **cinematic zoom into the sky view** when the scrubber locks onto a roll. Instead of overlaying a tooltip card with roll details, the sky view's camera pans and scales onto the focal constellation, the rolled jump's perk-vertex splits into its actual perk motes, a forge reach beam rises from below the viewport, a shrinking halo focuses on the rolled perk(s), and the perk diffraction star flares for a hit (or dims for a miss).

This is the foundation for a later enhancement that will visualize the Forge's "grab" process step-by-step inside that focused view.

## About the Design Files

The files in this bundle are **design references created in HTML/CSS/SVG** — a working interactive prototype that demonstrates the intended look and behavior. They are **not** drop-in code for the existing repo. The task is to recreate this behavior inside `web/app.js` (and adjacent files), reusing the existing diffraction-marker recipe, color tokens, constellation wireframe data, and roll model. The existing codebase is a vanilla-JS imperative renderer with no framework — keep that style.

## Fidelity

**High-fidelity prototype.** The animation prototype (`sky-zoom-animation.html` + `animation.js`) is the source of truth for timing, easing, layering, and visual treatment. The static frame-by-frame storyboard (`sky-zoom-storyboard.html`) is a secondary artifact useful for studying individual frames in isolation. Where the prototype and the storyboard disagree, **prefer the prototype** — it received more iteration.

## Context: Where This Fits in the Existing App

- The current sky view lives in `renderPlaythrough()` → `renderJumpFocus()` in `web/app.js`.
- `renderJumpFocus()` currently composes a small overlay panel with a mini constellation, perk name, jump label, and hit/miss summary. **That overlay goes away entirely.** The HUD-style indicator labels inside the stage frame (top-left, top-right) **also go away** — the inside of the sky view should be purely spacey, no techy chrome.
- A planned (in-flight) layout change moves the sky view **above** the scrubber. The forge reach beam rises from **below** the viewport so it visually emerges from the scrubber's direction.
- The existing diffraction-marker recipe (`diffractionMarker` + `starSvg` + `recipeFor` in `web/app.js`) defines mote appearance by cost. The new design reuses that recipe exactly — match the ray counts, lengths, widths, and jitter values.
- Constellation shapes and per-jump perk positions come from `data/derived/constellation_wireframes.json`. The cluster-level `silhouette` and `marker_positions` and the per-jump `stars` arrays drive everything.

## Animation Timeline

A roll-focus animation runs for a fixed ~2.8 seconds of wall-clock time. During firing the scrubber's word position locks to the roll's word position so the cinematic plays at full pace regardless of the configured words/second. All effects are parameterized by `t` ∈ [0, 1] across that duration. Times below are normalized `t` values; convert to milliseconds using the configured animation duration. `onRollBehavior` is `cinematic` (default — auto-resume on completion), `pause` (hold final frame until the user presses play), or `quick` (skip the cinematic entirely).

| t        | Phase            | What happens                                                                                             |
|----------|------------------|----------------------------------------------------------------------------------------------------------|
| 0.00–0.10 | drift            | Sky at rest. No camera movement. Scrubber hasn't yet committed to a roll.                                |
| 0.10–0.20 | lock             | Scrubber lands on a roll. Camera begins easing toward the target jump anchor.                            |
| 0.10–0.65 | approach (camera) | Camera pans + scales from wide (1280×800 viewBox) toward the jump's reveal target (320×200 viewBox).    |
| 0.22–0.50 | motion blur rises | SVG `feGaussianBlur` `stdDeviation` on the cluster group ramps 0 → 8.                                    |
| 0.40–0.58 | split            | The single rolled-jump vertex resolves into the jump's actual perk stars (1–N motes in wireframe positions). Fades in concurrently with the silhouette fading out. |
| 0.50–0.62 | motion blur falls | `stdDeviation` ramps 8 → 0. Smear clears, revealing the perk cluster.                                   |
| 0.50–0.60 | silhouette + cluster-marker fade | Constellation outline, vertex pins, and non-focal jump markers fade from full opacity to 0 — entirely under cover of the motion blur peak/fall, so nothing pops in when the blur clears. |
| 0.48–0.84 | spotlight tightens | Radial darkness overlay tightens from radius 220 to 64 world units around the focal point. Opacity 0 → 0.74. |
| 0.55–0.86 | beam reach       | Beam apex eases from base of viewport up to the focal point (or short of it, for miss).                  |
| 0.62–0.88 | multi-grab merge | (multi-grab only) Focal perks slide from their wireframe positions to their binary positions next to each other. |
| 0.62–0.86 | halo (hit only)  | Shared shrinking halo ring closes in around the focal perk(s). Skipped entirely for miss.                |
| 0.65–0.86 | camera (reveal → hit) | Camera continues zooming into a tighter 192×120 viewBox tightly centered on the focal perk.         |
| 0.66+    | focal scale-up   | Single-focal hit: focal star scales up to 1.5× its base diffraction size by the flare beat. Multi-grab focals stay at 1.0× (their proximity does the visual work). |
| 0.82–0.92 | multi-grab flash | (multi-grab only) Brief white burst at the merge centerpoint. Two radial circles, peak opacity ~0.32.   |
| 0.82–0.90 | hit flare        | Single-focal hit: focal scales from 1.28× → 1.50× as the beam apex locks on.                            |
| 0.86–1.00 | hold             | Final state holds. Camera locked. Halo and aura at full. Beam at full reach (or stalled short for miss).|

### Easing

- Camera position/scale: `easeInOutCubic`
- Beam reach: `easeOutCubic` (decelerates as it approaches the apex)
- Halo shrink (multi-grab): driven by the merge progress curve (`easeInOutCubic`)
- Halo shrink (single-focal): `easeInOutCubic` of its own phase
- Split progress: `easeInOutCubic`
- Multi-grab merge: `easeInOutCubic`
- Spotlight progress: `easeInOutCubic`

### Reduced motion

When `prefers-reduced-motion: reduce` is set, all phases should resolve to their end state immediately. No camera movement, no blur, no particle motion, no halo shrink. The focal mote is rendered at its final position with the apex bloom and the halo at final radius, but no transitions.

## Outcome Branching

The scenario produces one of three visual shapes:

### 1. Hit on a multi-perk jump (most common)

- Split reveals all perks in the rolled jump at their wireframe positions
- Non-focal perks dim to 0.28 opacity by the hit beat
- Focal perk scales up to 1.5× to dominate visually
- Halo shrinks from `JUMP_RADIUS * 0.85 ≈ 60` world units down to `focalVisualSize * 0.40` (tight around the focal star)
- Beam fully reaches the focal, apex bloom paints over the tip
- Aura ring color: cluster accent color

### 2. Multi-grab hit

- Split reveals all perks in the rolled jump
- Two (or more) focal perks slide from their wireframe positions toward their *binary positions* (offsets `(-5, +1)` and `(+5, -1)` world units from the merge center — same ratio the scrubber uses for paired-cost diffraction markers). Their rays heavily overlap, reading as fused.
- Shared halo shrinks from `halfDist + 16` world units (covers both wireframe positions) down to `14` world units (hugs the binary pair)
- Brief white flash at the merge centerpoint at the moment of fusion (t = 0.82 → 0.92)
- Focal scale stays at 1.0× (the proximity + ray overlap is the visual)

### 3. Miss

- Split reveals the inferred candidate perk (or the rolled jump's perks, dimmed)
- **No halo** — explicit visual distinction from hits
- Beam reach caps at 0.78 (apex stops short of the focal)
- Apex bloom is small and dim (`bloomR` 4 → 9 world units, opacity factor 0.25)
- No focal scale-up (focal stays at 0.95×)
- Candidate perk does not flare — pulses dimmer

## Camera Math

World space is a 1600 × 1000 conceptual stage. The cluster constellation lives in a 620 × 620 region centered at world `(800, 500)`. Mapping from cluster-local `[0,1]` coords to world is:

```js
world_x = 490 + clusterX * 620
world_y = 190 + clusterY * 620
```

Jump-interior perks (`[-1, 1]` x/y from `jump_constellations.stars`) map around the jump's cluster-marker anchor using `JUMP_RADIUS = 70` world units:

```js
world_x = anchor_x + star.x * 70
world_y = anchor_y - star.y * 70   // flip y because constellation_wireframes uses up-positive
```

Camera positions (use `viewBox` in SVG, or canvas transform in canvas):

| Phase   | Center                                         | Size              |
|---------|------------------------------------------------|-------------------|
| wide    | `(800, 500)`                                   | `1280 × 800`     |
| reveal  | jump anchor in world (or focal if jump has 1 perk) | `320 × 200`      |
| hit     | focal perk in world                            | `192 × 120`      |

Interpolation between phases uses `easeInOutCubic`. Wide → reveal spans t=0.10→0.65; reveal → hit spans t=0.65→0.86; t≥0.86 holds at hit.

## Visual Layers (Z-order, back to front)

1. **Background starfield** — fixed in *screen* coordinate space, not camera-relative. Rendered as its own absolutely positioned SVG layer behind the camera SVG with `preserveAspectRatio="xMidYMid slice"`. ~220 small dots, opacity 0.18–0.60. **Critical:** never let the camera zoom scale these — they're supposed to be "infinitely distant" and should remain ambient noise.
2. **Constellation silhouette polylines** — at full opacity during drift (0.62), faded to 0 by t=0.60. Use `vector-effect="non-scaling-stroke"` so the stroke stays a clean hairline at any camera zoom. Render under the motion blur filter group during the approach.
3. **Vertex pins** — small 3px-radius circles at each cluster marker position, same color as silhouette, opacity 0.85 → 0 on the same window as silhouette.
4. **Cluster-marker stars** (the other jumps' anchor stars in the focal constellation) — diffraction markers at cost = 100, drawn under the motion blur filter group. Outer markers fade from 0.65 → 0 across t=0.50→0.60. Focal vertex marker fades 0.85 → 0 as the split progresses.
5. **Interior perk stars** — diffraction markers at each perk's real cost, drawn at jump-local positions. Fade in 0 → 1 across t=0.40 → 0.58. Focal perk(s) at 1.0× opacity; non-focal at 0.72 → 0.28 by hit beat.
6. **Halo ring** — single shared ring at the halo center. Stroke 1.4 with `vector-effect="non-scaling-stroke"`. See "Halo" below for radius and timing per outcome.
7. **Forge reach beam** — 4-layer mystical light. See "Beam" below.
8. **Spotlight overlay** — full-viewport rect with a radial-gradient mask. Radius shrinks from 220 → 64 world units, dark opacity 0 → 0.74, plus a faint colored glow gradient at the center. Combined with the gradients these darken everything outside the focal area.

## The Beam (4 layers)

The beam rises from off-screen below to the focal mote. Replaced a flat polygon/centerline pair with a layered mystical light:

```
outer cone (gaussian-blurred wide accent-color cone)
  ↓ over
inner core (narrower brighter less-saturated cone, lighter blur)
  ↓ over
particle motes (white circles flowing base → apex on a sin-curve brightness)
  ↓ over
apex bloom (radial gradient at the apex)
```

**Geometry:**
- Outer cone: trapezoid with `apexW = lerp(4, 0, reach)` at the top, `baseW = 72` at the bottom. **Apex tapers to a true point** (width 0 at full reach) so the gaussian blur dissolves the tip into the void on misses (no flat edge artifact).
- Inner core: trapezoid with `coreApexW = lerp(2, 0, reach)`, `coreBaseW = 22`.
- Beam apex Y: `lerp(viewportBottom + 30, focal.y, reach)`. Base Y: `viewportBottom + 30`.

**Gradients:**
- Outer cone vertical gradient: accent color, stops at 0.52·op / 0.20·op / 0 (opacity factors × beam opacity). Filter: `feGaussianBlur stdDeviation=6`.
- Inner core vertical gradient: brighter accent color (oklch lightness 0.95, lower chroma 0.06), stops at 0.78·op / 0.30·op / 0. Filter: `feGaussianBlur stdDeviation=2.4`.

**Particles:**
- 14 particles, each with a fixed seeded x-jitter and phase offset
- Each particle's phase: `((t * 2.6) + phaseOffset) % 1` — so they cycle continuously base → apex
- Y position: `bottomY - phase * beamLen`
- Brightness: `sin(phase * π) * 0.55 * op` — peaks mid-rise, fades at base and apex
- Size: `0.7 + (seed % 7) / 7 * 1.0`

**Apex bloom:**
- Radial gradient centered at the apex
- For hit: radius `lerp(8, 26, reach)`, opacity `0.7 * reach * op`
- For miss: radius `lerp(4, 9, reach)`, opacity `0.25 * reach * op` (tight and dim, no successful lock)

**Beam reach (apex Y interpolation):**
- For hit/multi-grab: `easeOutCubic((t - 0.55) / 0.27)`, fully reaches 1.0 at t=0.82
- For miss: same curve but multiplied by 0.78 — beam visibly stalls short of the focal

## The Halo

Single shared ring around the focal point(s), drawn for hits only.

| Scenario | Center | Initial radius | Final radius | Shrink driver |
|----------|--------|----------------|--------------|---------------|
| Single-focal hit | Focal perk world coords | `JUMP_RADIUS * 0.85 ≈ 60` | `focalVisualSize * 0.40` | `easeInOutCubic` of `phase(t, 0.62, 0.86)` |
| Multi-grab | Merge centerpoint | `halfDist + 16` (covers both wireframe positions) | `14` (tight around binary pair) | `mergeT` (the perks' merge progress) |
| Miss | — | — | — | Halo not drawn |

Opacity ramps from 0.18 → 0.58 across t=0.62 → 0.86. Stroke `1.4` with `vector-effect="non-scaling-stroke"`. Color: cluster accent.

## Motion Blur

Applied to the silhouette + cluster-marker group only (not to interior perks, beam, halo, or spotlight). Uses an SVG `feGaussianBlur` filter, `stdDeviation` driven by `t`:

```
t < 0.22:                                     0
0.22 ≤ t < 0.50:    ((t - 0.22) / 0.28) * 8   (rising)
0.50 ≤ t < 0.62:    8 - ((t - 0.50) / 0.12) * 8   (falling)
t ≥ 0.62:                                     0
```

The 0.50 → 0.60 silhouette opacity fade is intentionally synchronized with the 0.50 → 0.62 blur clear so the opacity transition is masked by the smear — silhouette finishes fading before the picture sharpens. The 0.40 → 0.58 split fade-in is also masked.

## Diffraction Markers (Mote Visual)

Reuse the existing `recipeFor` and `starSvg` from `web/app.js`:

```js
function recipeFor(cost) {
  if (cost >= 800) return { major: 12, minor: 12, length: 46, width: 1.05, minorLength: 32, minorWidth: 0.32, jitter: 8 };
  if (cost >= 400) return { major: 8,  minor: 8,  length: 39, width: 0.92, minorLength: 24, minorWidth: 0.28, jitter: 5 };
  if (cost >= 200) return { major: 6,  minor: 6,  length: 32, width: 0.78, minorLength: 18, minorWidth: 0.25, jitter: 3 };
  return                  { major: 4,  minor: 4,  length: 27, width: 0.7,  minorLength: 12, minorWidth: 0.22, jitter: 1 };
}

function sizeFor(cost) {
  if (cost >= 800) return 96;
  if (cost >= 400) return 78;
  if (cost >= 200) return 64;
  return 54;
}
```

`sizeFor` is the rendered diameter in world units at scale 1.0. Apply `focalScaleFactor(t)` to the focal perk's visualSize during the hit beat.

**SVG `<symbol>` + `<use>` gotcha**: if you use `<symbol viewBox="-50 -50 100 100">` with `<use href="#sym"/>`, the use defaults to the outer SVG's viewport for sizing, which makes the symbol stretch wildly. **Always set explicit `x="-50" y="-50" width="100" height="100"` on the `<use>` element** so it renders at the symbol's intrinsic dimensions. This was the source of a major alignment bug — see comment in `animation.js · placeStar()`.

## Color System

Cluster accent colors come from `HUES` in `web/app.js`:

```js
{
  "Toolkits": 196, "Knowledge": 268, "Vehicles": 30, "Time": 218,
  "Crafting": 152, "Clothing": 320, "Magic": 286, "Quality": 48,
  "Size": 100, "Resources and Durability": 8, "Magitech": 240,
  "Alchemy": 170, "Capstone": 52, "Personal Reality": 130
}
```

All beam, halo, silhouette, and spotlight colors derive from the focal constellation's hue:

- Beam outer + halo + silhouette: `oklch(0.82 0.14 ${hue})`
- Beam inner core: `oklch(0.95 0.06 ${hue})` — brighter, less saturated
- Spotlight glow: same as accent at low opacity
- Apex bloom inner stop: white at full opacity, fades through accent color to transparent

## Data Sources

The animation needs to know, given a roll:
- Which cluster (`roll.constellation`) → which silhouette + markers + hue
- Which jump (`roll.purchased_perk_jump`) → which anchor in `cluster.marker_positions` and which `jump_constellations` entry
- Which perks were rolled (`roll.purchased_perks` filtered to `!free`) → focal indices into the jump's `stars` array
- Outcome (`roll.outcome`) → which branch (hit / multi-grab / miss)
- Miss target inference (`roll.miss_cost_estimate` + `roll.available_cp`) → candidate perk for miss scenarios

The current `web/app.js` already builds `app.data.conByName` and `app.data.jumpWireframeByKey` — the new design uses the same lookups.

**Open data question (deferred from this conversation):** the wireframe data has jump-interior perks in `[-1, 1]` x/y coords, but for some jumps (e.g. Star Trek: TNG with 12 perks in a perfect circle) those positions create a too-regular ring that reads as "a constellation in its own right" rather than an organic cluster. The prototype's TNG_PERKS data uses scattered organic positions for storyboard clarity. **Real implementation should use the wireframe data as-is** but flag this as a design question worth revisiting later — it's a constellation_wireframes content concern, not a renderer concern.

## Performance

- Rebuilding the full SVG content via `innerHTML` at 60fps is acceptable at this scene complexity (a few dozen polylines + circles + polygons + ~14 particles). Diffraction stars share a single `<symbol>` per cost tier and instance via `<use>` so per-frame cost is minimal.
- The background starfield is generated once per scenario and cached. It only updates when the focal constellation changes.
- The motion blur filter is applied to a `<g>` containing the silhouette + cluster-marker group only; not to interior perks, beam, or halo.

## What's Out of Scope

- **The Forge "grab process" animation** that will eventually play during the hit beat (visualizing exactly how the Forge selects + acquires the perk) is a future enhancement. The current design lays the groundwork (camera locks, halo focuses, beam lands) and leaves the post-lock beat as a hold.
- **Free-perk satellite motes** — the current scrubber draws small satellite dots around a marker for free bonus perks. Those should appear attached to the focal perk in the locked state. The prototype scenarios don't include free perks, so this is not animated in the handoff — match the existing satellite treatment from `web/app.js` (`diffractionMarker` → `.star-satellite` spans).
- **HUD chrome inside the sky view** — there is none. The "sky lock" / "forge active" / phase indicator labels from the earlier storyboard are removed. The scrubber and outer chrome stay holographic/techy; the sky interior is purely spacey.
- **Tooltips** on stars at rest are unchanged from the existing app's behavior.

## Files in This Bundle

| File | What it is |
|------|------------|
| `sky-zoom-animation.html` + `animation.js` + `animation.css` | **Primary reference.** Interactive prototype with play/pause, scrubber, 3 looping scenarios (hit / multi-grab / miss), and speed control. Open this and study the transitions — this is the source of truth for timing and visual layering. |
| `sky-zoom-storyboard.html` + `storyboard-render.js` + `storyboard.css` | Static frame-by-frame storyboard. Each scenario shown as 5 keyframes side-by-side with per-frame captions. Useful for studying individual states in isolation but less complete than the animation. |
| `storyboard-data.js` | Scene data + constellation shape data (silhouettes, markers, perks). Used by both prototypes. |

The animation prototype's `animation.js` is the most thoroughly iterated artifact — its comments document the rationale for each effect and timing choice. The storyboard renderer is older and may have minor drift from the animation's final treatment.

## Recommended Implementation Order

1. **Layout swap first** (already in-flight per a separate task): move the sky view above the scrubber.
2. **Remove `renderJumpFocus()`** entirely. Remove the HUD indicator labels inside the stage frame.
3. **Add the background starscape layer** as a separate SVG behind the main stage SVG, fixed in screen space.
4. **Wire up the timing state machine**: when the scrubber lands on a roll that's within the firing window, lock wordPos to the roll's word_position and kick off a `t` interpolation across the configured animation duration. Drive all effects from `t`. Respect `onRollBehavior` (cinematic / pause / quick) — `cinematic` auto-resumes word advance when `t >= 1`; `pause` holds the final frame until the user presses play; `quick` skips the cinematic entirely.
5. **Implement camera/viewBox interpolation** between the wide/reveal/hit states using `easeInOutCubic`.
6. **Add the motion blur filter group** wrapping the silhouette + cluster-marker rendering.
7. **Implement the split** — switch from rendering the focal jump's cluster marker to rendering the jump's interior perks, fading in over t=0.40 → 0.58.
8. **Add the beam** — 4 layers, all the gradient + filter machinery, particle stream.
9. **Add the spotlight + halo + flash** in that order.
10. **Test miss treatment** — make sure the beam stalls and no halo draws.
11. **Reduced-motion path** — collapse all animations to their end state.
