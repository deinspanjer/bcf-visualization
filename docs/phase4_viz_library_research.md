# Phase 4 — 3D Planetarium Library Research

**Goal:** pick a JS library (or stack) for a 3D "planetarium" view of the
Celestial Forge — camera inside a sky sphere, ~14 named constellations,
500–1000 stars sized by perk cost, scrubber-driven sky drift, and
animated camera zooms when rolls fire.

**Constraints recap (from the task brief):**

- Static hosting (GitHub Pages), no server.
- Plain web preferred (the existing scrubber is vanilla JS); a build
  step is acceptable but not required.
- 60 fps with 500–1000 stars.
- Hover tooltips, raycast/highlight line, smooth camera tweens.
- WebAssembly only as a last resort.

## 1. Top-3 recommendations

### 1. Three.js (recommended)

The default-correct answer. Three.js is the most widely used WebGL
library on the web, ships as ES modules importable directly from a CDN
(no build step required via `<script type="importmap">`), and every
single capability in the brief — interior `BackSide` sphere, `Points`
or `InstancedMesh` for many stars, `Raycaster` for hover and the
roll-fire line, `PerspectiveCamera` tweening — is either built in or a
stock-recipe forum thread away. Bundle is ~155 KB gzipped for the core
module which is fine for a project site. 200,000-star starfields are
documented at 60 fps when you use `InstancedMesh` or a `Points` cloud,
so 500–1000 stars is trivially within budget. Active weekly releases,
huge example gallery, ~100k GitHub stars.

### 2. Babylon.js

Excellent alternative if you want a more "batteries-included" feel.
Babylon ships with a built-in animation system (no need for an external
tween lib), a `SolidParticleSystem` and `ThinInstance` API for many
sprites, declarative GUI, and a noticeably friendlier docs/playground
experience for newcomers. The trade-off is bundle weight (~1 MB minified
for full core, can be tree-shaken with a build step) and a smaller
ecosystem of casual snippets. CDN-loadable as UMD or ES6. Pick this if
the developer prefers "engine that does it all" over Three's "pick your
pieces" philosophy.

### 3. A-Frame (declarative wrapper around Three.js)

If you want the planetarium to feel like the existing scrubber
(declarative HTML, very little JS plumbing), A-Frame lets you write
`<a-sky>`, `<a-entity geometry="…" position="…">`, and a custom
`stars` component, and you get Three.js underneath for free. Big wins:
markup-style authoring, automatic VR/mobile support if you ever want
it, trivial integration with the existing static page. Big losses:
adds another abstraction layer over Three (debugging is one level
removed), the framework is opinionated about scene structure, and the
default build is ~1 MB. Pick this only if the *declarative* aesthetic
is a hard requirement.

## 2. Comparison table

| Library | License | Bundle (gz) | Learning curve | Sphere/inside-out | Animation primitives | Style | Last active | GH stars | GH Pages |
|---|---|---|---|---|---|---|---|---|---|
| **Three.js** | MIT | ~155 KB core | Medium | `SphereGeometry` + `BackSide` material, trivial | None built-in; pair with `tween.js` (~3 KB) or GSAP | Imperative | Monthly releases, very active | ~100k | Yes (CDN + import map) |
| **Babylon.js** | Apache-2.0 | ~400 KB–1 MB | Medium-low (great docs) | `CreateSphere` + `BackSide`, trivial | Built-in `Animation` + easing, no extra dep | Imperative (with declarative GUI option) | Monthly releases (v9.x in 2026) | ~24k | Yes (CDN UMD or ES6) |
| **A-Frame** | MIT | ~1 MB (incl. Three.js) | Low for HTML devs | `<a-sky>` primitive | Built-in `<a-animation>` / `animation` component | Declarative | Active, slower cadence | ~17k | Yes (single `<script>` tag) |
| **d3-celestial** | BSD-3 | ~80 KB + d3 | Low if you know d3 | **2D only** (Aitoff/Mollweide projections) | d3 transitions | Declarative-ish JSON config | Maintained but slow | ~720 | Yes |
| **VirtualSky** | Multi-license (LCO) | ~70 KB | Low | 2D planetarium projection (stereographic etc.) | Time-based animation built in | Imperative-config | Active (LCOGT) | ~150 | Yes |
| **Stellarium Web** | GPL | Heavy (full app) | High to embed/customize | True planetarium | Built-in | Embed-only | Active | n/a | Iframe only |
| **regl** | MIT | ~25 KB | High (hand-write GLSL) | DIY everything | DIY | Functional WebGL wrapper | Maintenance mode | ~6k | Yes |
| **deck.gl** | MIT | ~400 KB | Medium-high | `OrbitView` + cartesian, but layer-oriented and geospatial-flavored | Built-in transitions per attribute | Layer/declarative | Very active | ~13k | Yes |
| **ECharts GL** | Apache-2.0 | ~1 MB (echarts + gl) | Low | `globe`/`scatter3D` charts; not a free-form scene | Chart-style transitions | Declarative config | Active | ~63k | Yes |
| **Plotly.js 3D** | MIT | ~3 MB | Low | `scatter3d` only — not an interior sphere | Chart-style transitions | Declarative | Active | ~17k | Yes (huge bundle) |
| **Cesium** | Apache-2.0 | ~5 MB+ | High | Geocentric globe, planet-surface mindset | Built-in clock/animation | Imperative | Very active | ~13k | Yes (heavy) |

(Sizes are order-of-magnitude; star counts are May 2026 ballpark.)

### Disqualified and why

- **d3-celestial / VirtualSky** — 2D map projections of a celestial
  sphere. They look like a planetarium but they are not 3D scenes; you
  cannot fly the camera into a constellation.
- **Stellarium Web** — full-app, designed for embed-as-iframe with the
  real night sky. Customizing constellations is a sky-culture content
  pipeline, not a JS API. Wrong tool.
- **Cesium** — built for the Earth (or a planet). The "celestial body"
  framing is geographic, not free-form starry-sky.
- **deck.gl** — possible (`OrbitView` + non-geospatial cartesian works)
  but the entire mental model is "layers of geospatial data", which
  fights every interaction we want.
- **ECharts GL / Plotly 3D** — chart-shaped APIs. You declare `series`
  and `options`; you do not own the scene graph or the camera. Animated
  zoom-to-a-star is not a first-class operation.
- **regl** — beautiful, but means writing your own shaders, raycasting,
  scene management. Not justified when Three.js exists.
- **A-Frame** — viable, listed in top-3 only for the declarative angle;
  Three.js is the same engine without the abstraction cost.

## 3. Single recommendation: Three.js + tween.js + import map

**Use Three.js, loaded via a `<script type="importmap">` from
jsdelivr, with `tween.js` (or GSAP) for camera tweens. No build step.**

Reasoning:

- **Every requirement maps to a stock Three.js feature.** Interior
  sphere = `SphereGeometry` with `material.side = THREE.BackSide`.
  500–1000 stars = `Points` with a circular sprite texture and
  per-vertex `size`/`opacity` attributes (or `InstancedMesh` if you
  want each star to be a real mesh). Hover = `Raycaster` against the
  `Points` object. Roll-fire line = `Line` from camera to star. Camera
  zoom = tween `camera.position` and call `camera.lookAt(target)` in
  `onUpdate`.
- **Fits the existing site shape.** The current scrubber is
  vanilla-JS + plain HTML; an import map keeps that property. Drop one
  `<script type="module">` block in `web/planetarium.html`, ship.
- **Performance headroom is enormous.** Documented 200k-star scenes
  hit 60 fps with `InstancedMesh`; we need 500–1000.
- **Ecosystem.** Every problem you'll hit ("how do I make stars look
  fuzzy then crisp", "how do I tween lookAt") is the top result on the
  Three.js discourse forum.
- **Star→crisp transition** is a per-vertex shader uniform (gradient
  texture lookup with a `progress` attribute) — well-trodden ground,
  see the "Three.js Particles" tutorial pattern.

Cost: medium learning curve if the developer is new to WebGL. Mitigated
by the tutorial wealth.

## 4. Code sketch — render and rotate one constellation

A self-contained ~30-line snippet (drop into `web/planetarium.html`):

```html
<!doctype html>
<html><head><style>body{margin:0}canvas{display:block}</style></head>
<body>
<script type="importmap">
{ "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"
} }
</script>
<script type="module">
import * as THREE from 'three';

const scene  = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth/innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);

// Sky sphere we sit inside (BackSide flips normals so we see the inside).
const sky = new THREE.Mesh(
  new THREE.SphereGeometry(500, 64, 64),
  new THREE.MeshBasicMaterial({color: 0x05060a, side: THREE.BackSide}));
scene.add(sky);

// One constellation = N stars positioned on the inner sphere surface.
// Replace `perks` with your derived JSON; `cost` drives star size.
const perks = [{ra:0.10, dec:0.20, cost:200},{ra:0.15, dec:0.25, cost:400},
               {ra:0.22, dec:0.18, cost:100},{ra:0.30, dec:0.30, cost:800}];
const R = 480;  // just inside the sky shell
const positions = new Float32Array(perks.length * 3);
const sizes     = new Float32Array(perks.length);
perks.forEach((p,i) => {
  const x = R*Math.cos(p.dec)*Math.cos(p.ra);
  const y = R*Math.sin(p.dec);
  const z = R*Math.cos(p.dec)*Math.sin(p.ra);
  positions.set([x,y,z], i*3);
  sizes[i] = 2 + p.cost / 100;       // bigger perk = brighter star
});
const geom = new THREE.BufferGeometry();
geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
geom.setAttribute('size',     new THREE.BufferAttribute(sizes, 1));
const mat  = new THREE.PointsMaterial({color:0xffffee, size:6, sizeAttenuation:true});
const constellation = new THREE.Points(geom, mat);
scene.add(constellation);

// Animation loop: slow sky drift mapped to the scrubber elsewhere.
camera.position.set(0,0,0.01);   // sit at the centre, looking out
function tick(t){
  constellation.rotation.y = t * 0.00005;   // drift
  renderer.render(scene, camera);
  requestAnimationFrame(tick);
}
tick(0);
</script></body></html>
```

That renders the sky, one constellation of four stars sized by cost,
and a slow drift. Plug in real perk data, repeat per constellation,
add `Raycaster` for hover, add `tween.js` for roll-fire camera zoom.

### Implementation roadmap (~1 day to first usable build)

1. **Hour 1 — scaffold.** Copy the sketch above into
   `web/planetarium.html`. Confirm it renders locally.
2. **Hour 2 — load real data.** Read `data/derived/obtained_perks.json`
   + `perks_catalog.json`; group by constellation; deterministically
   place each constellation's stars on a patch of the sphere
   (hash-to-RA/Dec or hand-authored centers per the 14 constellations).
3. **Hour 3 — fuzzy → crisp.** Custom `ShaderMaterial` for the
   `Points`. Add a per-vertex `acquired` float and a uniform
   `chapterProgress`; in the fragment shader sample a soft gaussian
   when `acquired > chapterProgress` and a sharp disk when below.
4. **Hour 4 — scrubber wiring.** Reuse the existing `web/app.js`
   scrubber events; map chapter → `constellation.rotation.y` drift +
   the shader uniform.
5. **Hour 5 — hover.** `Raycaster.setFromCamera(mouse, camera)`,
   `intersectObject(constellation)`, lift first hit, draw a tooltip
   `<div>` over the canvas at the projected screen coords.
6. **Hour 6 — roll-fire zoom.** When a roll event fires, `tween.js`
   moves `camera.position` toward the jump's centroid and the
   `Line` from camera→star renders for the duration of the tween.

## 5. Risks and unknowns

- **Constellation placement strategy.** Real constellations have
  hand-curated star positions; ours don't. Decide early whether you
  hand-author 14 sphere-centres + jump-sub-centres, or compute them
  from a deterministic hash. Hand-authoring is ~1 hour and looks much
  better.
- **Fuzzy-to-crisp shader.** A `PointsMaterial` cannot do this; you
  need a `ShaderMaterial` (~30 lines of GLSL). Doable but if the
  developer has never touched GLSL there's a half-day learning bump.
  Fallback: two `Points` clouds (one fuzzy, one crisp) and crossfade
  opacity per-cluster — no GLSL needed but coarser-grained.
- **Mobile / GPU-poor browsers.** 1000 stars is fine; bloom or
  postprocessing would not be. Skip postprocessing in v1.
- **Tooltip jitter.** Raycasting `Points` requires
  `raycaster.params.Points.threshold` tuning; too low and stars
  don't register, too high and adjacent stars conflict. Plan to
  iterate.
- **Scrubber→sky-drift mapping.** Publish-date span is ~5.5 years;
  mapping linearly to a full sphere rotation will look glacial.
  Likely want chapter-index mapped to ≤180° total drift, or non-linear
  scaling per regime band.
- **Bundle/CDN risk.** jsdelivr outage = no planetarium. Mitigate by
  pinning a version and optionally vendoring `three.module.js` into
  `web/vendor/` (one file, ~600 KB unminified) for offline-safety.
- **Three.js r170+ removed some legacy paths** (e.g., older
  `examples/js/` UMD scripts). Use `examples/jsm/` ES module imports
  exclusively — a non-issue if you start fresh.

## 6. Do we need WebAssembly?

**No.** Five hundred to one thousand animated points is well below the
threshold where JS+WebGL becomes the bottleneck — the GPU does the
work, JS just submits draw calls. Documented Three.js scenes hit
hundreds of thousands of stars at 60 fps using stock `InstancedMesh`
or `Points`. WebAssembly would help if we needed CPU-side spatial
indexing of 100k+ items (e.g., a kd-tree for hover at huge scale), but
at our scale a linear `Raycaster.intersectObject` call on a single
`Points` mesh runs in microseconds. Revisit only if a future phase
balloons star count by 100×.

## TL;DR

Use **Three.js** loaded via an import map from a CDN, with `tween.js`
for camera animation. No build step. The sketch above plus six hours
of plumbing gets us from zero to a working scrubber-driven planetarium.
