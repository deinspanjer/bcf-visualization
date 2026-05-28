# Web App JS Modularization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce `web/app.js` from a mixed-responsibility 2,787-line module into focused vanilla JavaScript modules without changing runtime behavior.

**Architecture:** Keep the existing dependency-light browser module runtime. Extract stable responsibilities behind explicit function interfaces, with `web/app.js` remaining the orchestration entrypoint for loading, state transitions, mode switching, and wiring. No extracted module may import from `web/app.js`; extracted modules may import pure helpers from `web/viz-model.js` and DOM helpers from `web/dom-helpers.js`.

**Tech Stack:** Vanilla ES modules, existing `web/index.html`, existing `web/style.css`, pytest, Playwright-backed web integration tests, `node --check`.

---

## Context

`web/app.js` is already large enough that future feature work should not add more major responsibilities to it casually. Current responsibility clusters include:

- DOM helpers and storage helpers: `web/app.js:200-280`
- Story/data adaptation and chapter/roll lookup: `web/app.js:421-728`
- Playback state setters and lifecycle: `web/app.js:734-867`
- Structural shell and controls rendering: `web/app.js:869-1396`
- Playthrough, carousel, sky-camera, beam, and narrative rendering: `web/app.js:1397-2245`
- Detail rendering: `web/app.js:2247-2382`
- SVG marker helpers and background/star helpers: `web/app.js:2362-2503`
- Incremental frame update path: `web/app.js:2519-2709`

This plan is a ratchet, not a rewrite. Extract one cohesive area at a time, verify behavior, then continue. Do not introduce React, a bundler, TypeScript, or a new state framework as part of this refactor.

## Acceptance Matrix

| ID | Requirement | Status | Verification |
| --- | --- | --- | --- |
| A1 | `web/app.js` remains the public entrypoint loaded by `web/index.html`. | Not started | `web/index.html` still imports `web/app.js`; app loads in existing web integration harness. |
| A2 | Extracted modules do not import `web/app.js` or mutate hidden global app state. | Not started | `rg -n "from \"./app.js\"|from './app.js'|window\\.app|globalThis\\.app" web/*.js` finds no new coupling. |
| A3 | Story model logic is testable without a browser DOM. | Not started | Unit tests cover story building, roll-location selection, chapter lookup, cumulative stats, and recent rolls using stable fixtures. |
| A4 | Playthrough and Detail mode behavior remains unchanged. | Not started | Existing targeted tests in `tests/test_web_app_integration.py` pass. |
| A5 | Playback frame updates still avoid full structural render during normal RAF playback. | Not started | Existing `__bcfRenderStats` invariant test remains passing. |
| A6 | UI tests assert semantic behavior and performance invariants, not incidental implementation shape. | Not started | Self-review all added or materially changed tests against `DEVELOPERS.md` Testing Design Pattern. |
| A7 | Final repository gate passes. | Not started | `.venv/bin/python scripts/verify.py` passes. |

## File Structure

Create or modify these files:

- Create: `web/dom-helpers.js`
  - Owns `el`, `svgEl`, `setProps`, `append`, and `clear`.
  - Pure DOM construction utilities only. No app state.

- Create: `web/story-model.js`
  - Owns `buildStory`, `resolveRollWordPosition`, `buildConstellations`, `chapterAtWord`, `chapterIndex`, `lastRollAtWord`, `recentRolls`, `cumulativeAt`, `buildSyntheticCpTicks`, `cpEarningAt`, `rawWordAtCpEarning`, `sectionStyle`, `povColor`, and format-free story lookup helpers.
  - Accepts explicit inputs such as `story`, `rollLocation`, and `wordPos`; does not read `app`.

- Create: `web/playthrough-view.js`
  - Owns `renderPlaythrough`, `renderViewportFrame`, carousel rendering, card rendering, and narrative readout rendering.
  - Receives a view context object with `app` data it needs, plus callbacks such as `setFieldLogHidden`.
  - Does not own playback lifecycle.

- Create: `web/sky-camera-view.js`
  - Owns `renderSkyCamera`, `renderSpotlight`, `renderBeam`, `getCameraSymbolDefs`, `buildCameraSymbolDefs`, and `placeCameraStar`.
  - Imports visual math from `web/viz-model.js` and DOM helpers from `web/dom-helpers.js`.
  - Does not know about `app.mode`, storage, package loading, or structural render.

- Create: `web/detail-view.js`
  - Owns `renderDetail`, selected chapter panel, recent acquisitions panel, constellation bars, roll log, row rendering, and detail key helpers where possible.
  - Receives explicit state and callbacks for filter/sort/location changes.

- Modify: `web/app.js`
  - Keep orchestration: load package data, maintain app state, call render modules, route frame updates, wire events, and own structural fallback render.
  - Remove extracted implementations after imports are wired.

- Modify: `tests/test_web_viz_model.py` or create `tests/test_web_story_model.py`
  - Add semantic tests for extracted pure story model behavior.

- Modify: `tests/test_web_app_integration.py`
  - Keep existing user-visible and performance invariant tests passing.
  - Add tests only if extraction creates a real behavior risk not currently covered.

## Implementation Todo

### Task 1: Baseline Inventory And Guardrails

**Files:**
- Inspect: `web/app.js`
- Inspect: `web/viz-model.js`
- Inspect: `tests/test_web_app_integration.py`
- Inspect: `tests/test_web_viz_model.py`
- Inspect: `DEVELOPERS.md`

- [ ] **Step 1: Confirm clean working context**

Run:

```bash
git status --short --branch
```

Expected: identify unrelated local changes before editing. Do not revert user changes.

- [ ] **Step 2: Record current app size and function inventory**

Run:

```bash
wc -l web/app.js web/viz-model.js web/data-contract.js
rg -n "^function |^async function |^class |^const [A-Za-z0-9_]+ = \\(" web/app.js
```

Expected: confirms the starting point and extraction candidates.

- [ ] **Step 3: Run current focused web checks**

Run:

```bash
node --check web/app.js
.venv/bin/pytest tests/test_web_viz_model.py tests/test_web_app_integration.py -q
```

Expected: PASS before refactoring. If this fails, stop and diagnose before moving code.

- [ ] **Step 4: Commit nothing**

This task is inventory only.

### Task 2: Extract DOM Helpers

**Files:**
- Create: `web/dom-helpers.js`
- Modify: `web/app.js:200-247`

- [ ] **Step 1: Create `web/dom-helpers.js` with the current helper implementations**

Move these functions exactly first:

```js
export function el(tag, props, ...children) {
  const node = document.createElement(tag);
  setProps(node, props);
  append(node, children);
  return node;
}

export function svgEl(tag, props, ...children) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  setProps(node, props, true);
  append(node, children);
  return node;
}

export function setProps(node, props, svg = false) {
  if (!props) return;
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (key === "class") node.setAttribute("class", value);
    else if (key === "text") node.textContent = String(value);
    else if (key === "style" && typeof value === "object") {
      for (const [name, styleValue] of Object.entries(value)) {
        if (styleValue == null) continue;
        if (name.startsWith("--")) node.style.setProperty(name, styleValue);
        else node.style[name] = styleValue;
      }
    } else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (svg || key.includes("-") || key === "role" || key === "for") {
      node.setAttribute(key, String(value));
    } else {
      node[key] = value;
    }
  }
}

export function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.appendChild(typeof child === "string" || typeof child === "number"
      ? document.createTextNode(String(child))
      : child);
  }
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}
```

- [ ] **Step 2: Import helpers in `web/app.js`**

Add near the top of `web/app.js`:

```js
import { clear, el, svgEl } from "./dom-helpers.js";
```

Remove the local helper definitions. Do not export anything from `app.js`.

- [ ] **Step 3: Verify syntax**

Run:

```bash
node --check web/dom-helpers.js
node --check web/app.js
```

Expected: PASS.

- [ ] **Step 4: Verify browser behavior**

Run:

```bash
.venv/bin/pytest tests/test_web_app_integration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add web/app.js web/dom-helpers.js
git commit -m "refactor: extract web DOM helpers"
```

### Task 3: Extract Story Model

**Files:**
- Create: `web/story-model.js`
- Modify: `web/app.js:421-728`
- Create or modify: `tests/test_web_story_model.py`

- [ ] **Step 1: Write failing story-model tests**

Create stable fixture tests that do not read current generated story data:

```python
def test_build_story_selects_predicted_or_curated_roll_positions(web_module):
    # Minimal chapter_facts fixture with one chapter and one roll.
    # Assert predicted location uses epub_word_offset_predicted.
    # Assert curated location uses epub_word_offset_curated.
```

Also cover:

- fallback local roll word positions clamp inside the chapter span
- `recentRolls(story, wordPos, count)` returns only rolls at or before `wordPos`
- `cumulativeAt(story, wordPos)` counts hits, misses, paid perks, and free perks
- `chapterAtWord(story, wordPos)` returns the last chapter at story end

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
.venv/bin/pytest tests/test_web_story_model.py -q
```

Expected: FAIL because `web/story-model.js` does not exist or exports are missing.

- [ ] **Step 3: Move pure story functions into `web/story-model.js`**

Use explicit arguments instead of reading `app`. Target interface:

```js
export function buildStory(chapterFacts, { rollLocation = "predicted" } = {}) {}
export function buildConstellations(wireframes) {}
export function chapterAtWord(story, wordPos) {}
export function chapterIndex(story, chapterNum) {}
export function lastRollAtWord(story, wordPos) {}
export function recentRolls(story, wordPos, count = 10) {}
export function cumulativeAt(story, wordPos) {}
export function buildSyntheticCpTicks(story) {}
```

Keep format-only helpers in `app.js` unless the test or another module actually needs them.

- [ ] **Step 4: Update `web/app.js` call sites**

Replace app-bound calls:

```js
app.data.story = buildStory(chapterFacts, { rollLocation: app.rollLocation });
const chapter = chapterAtWord(app.data.story, app.wordPos);
const recent = recentRolls(app.data.story, wordPos, 8);
const cumulative = cumulativeAt(app.data.story, app.wordPos);
```

Do not allow `web/story-model.js` to import from `web/app.js`.

- [ ] **Step 5: Verify syntax and unit tests**

Run:

```bash
node --check web/story-model.js
node --check web/app.js
.venv/bin/pytest tests/test_web_story_model.py -q
```

Expected: PASS.

- [ ] **Step 6: Verify web integration**

Run:

```bash
.venv/bin/pytest tests/test_web_app_integration.py -q
```

Expected: PASS, including mode switching and playback invariants.

- [ ] **Step 7: Commit**

Run:

```bash
git add web/app.js web/story-model.js tests/test_web_story_model.py
git commit -m "refactor: extract web story model"
```

### Task 4: Extract Sky Camera Renderer

**Files:**
- Create: `web/sky-camera-view.js`
- Modify: `web/app.js:1578-2210`
- Modify only if needed: `tests/test_web_app_integration.py`

- [ ] **Step 1: Identify required imports**

`web/sky-camera-view.js` should import DOM helpers and visual math directly:

```js
import { el, svgEl } from "./dom-helpers.js";
import {
  beamOpacity,
  beamReach,
  clusterLocalToWorld,
  easeInOutCubic,
  focalClusterOpacity,
  focalScaleFactor,
  focalWorldFromScene,
  focusCameraViewRect,
  haloAuraProgress,
  HALO_BINARY_OFFSET,
  JUMP_RADIUS_WORLD,
  lerp,
  motionBlurStdDeviation,
  multiGrabFlashOpacity,
  multiGrabMergeProgress,
  nonFocalClusterOpacity,
  nonFocalInteriorOpacity,
  phase,
  silhouetteOpacity,
  splitProgress,
  spotlightProgress,
  starWorldFromScene,
  vertexPinOpacity,
} from "./viz-model.js";
```

- [ ] **Step 2: Move renderer with explicit context**

Target interface:

```js
export function renderSkyCamera({ roll, scene, t, conByName }) {}
```

Inside the renderer, replace `app.data.conByName` with `conByName`.

- [ ] **Step 3: Update `web/app.js` call sites**

Replace:

```js
renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT)
```

with:

```js
renderSkyCamera({
  roll: frame.lastRoll,
  scene: frame.scene,
  t: frame.focusT,
  conByName: app.data.conByName,
})
```

- [ ] **Step 4: Verify the performance-sensitive integration behavior**

Run:

```bash
node --check web/sky-camera-view.js
node --check web/app.js
.venv/bin/pytest tests/test_web_app_integration.py -q
```

Expected: PASS. Existing tests should still show shared diffraction defs, no blur-heavy beam regression, and no structural render during RAF playback.

- [ ] **Step 5: Commit**

Run:

```bash
git add web/app.js web/sky-camera-view.js tests/test_web_app_integration.py
git commit -m "refactor: extract sky camera renderer"
```

### Task 5: Extract Playthrough View

**Files:**
- Create: `web/playthrough-view.js`
- Modify: `web/app.js:1397-1577`
- Modify: `web/app.js:2212-2245`
- Modify only if needed: `tests/test_web_app_integration.py`

- [ ] **Step 1: Move carousel and narrative rendering behind a context object**

Target interface:

```js
export function renderPlaythroughView(context) {}
export function carouselFrameModel(context, focusT = null, firingCinematic = false) {}
export function createCarouselSlot(context, slot) {}
export function applyCarouselSlotState(node, slot) {}
```

The context should contain only what rendering needs:

```js
{
  story,
  conByName,
  wordPos,
  fieldLogHidden,
  carouselKnowledgeIndex,
  renderSkyCamera,
  setFieldLogHidden,
}
```

- [ ] **Step 2: Keep playback lifecycle in `web/app.js`**

Do not move `tickPlayback`, `startPlayback`, `stopPlayback`, `setWordPos`, or `updatePlaybackFrame` in this task. This task is rendering extraction only.

- [ ] **Step 3: Update app call sites**

`web/app.js` should call:

```js
renderPlaythroughView(makePlaythroughContext())
```

where `makePlaythroughContext()` is a small local adapter in `app.js`.

- [ ] **Step 4: Verify playthrough behavior**

Run:

```bash
node --check web/playthrough-view.js
node --check web/app.js
.venv/bin/pytest tests/test_web_app_integration.py -q
```

Expected: PASS for playthrough layout, field log collapse, playback frame updates, cinematic/quick/pause behavior, and carousel card state.

- [ ] **Step 5: Commit**

Run:

```bash
git add web/app.js web/playthrough-view.js tests/test_web_app_integration.py
git commit -m "refactor: extract playthrough view"
```

### Task 6: Extract Detail View

**Files:**
- Create: `web/detail-view.js`
- Modify: `web/app.js:2247-2382`
- Modify: `web/app.js:2624-2678`
- Modify only if needed: `tests/test_web_app_integration.py`

- [ ] **Step 1: Move detail panel renderers**

Target interface:

```js
export function renderDetailView(context) {}
export function renderSelectedChapter(context) {}
export function renderRecentAcquisitions(context) {}
export function renderConstellationBars(context) {}
export function renderRollLog(context) {}
export function detailFrameKeys(context) {}
```

The context should include `story`, `wordPos`, `rollFilter`, `rollSort`, `rollLocation`, and callbacks for row clicks/filter changes.

- [ ] **Step 2: Keep incremental panel replacement in `web/app.js` unless extraction is clean**

`updateDetailFrame()` can stay in `web/app.js` as orchestration. Move `detailFrameKeys()` only if the context object makes the dependency boundaries clear.

- [ ] **Step 3: Verify Detail mode semantics**

Run:

```bash
node --check web/detail-view.js
node --check web/app.js
.venv/bin/pytest tests/test_web_app_integration.py -q
```

Expected: PASS, especially tests that detail panels stay stable when semantic keys do not change and refresh when keyed state changes.

- [ ] **Step 4: Commit**

Run:

```bash
git add web/app.js web/detail-view.js tests/test_web_app_integration.py
git commit -m "refactor: extract detail view"
```

### Task 7: Final Coupling Audit And Documentation

**Files:**
- Modify if useful: `DEVELOPERS.md`
- Modify if useful: `TODO.md`
- Inspect: `web/*.js`

- [ ] **Step 1: Audit module coupling**

Run:

```bash
rg -n "from \"./app.js\"|from './app.js'|window\\.app|globalThis\\.app" web/*.js
```

Expected: no new coupling. If any reference remains, remove it or document why it is a real external contract.

- [ ] **Step 2: Audit obsolete local definitions**

Run:

```bash
rg -n "^function (buildStory|renderSkyCamera|renderPlaythrough|renderDetail|el|svgEl)\\b" web/app.js
```

Expected: extracted functions no longer remain in `web/app.js`.

- [ ] **Step 3: Check file sizes**

Run:

```bash
wc -l web/app.js web/dom-helpers.js web/story-model.js web/playthrough-view.js web/sky-camera-view.js web/detail-view.js web/viz-model.js
```

Expected: `web/app.js` is materially smaller and each extracted file has a single clear responsibility. Do not chase an arbitrary line target if responsibility boundaries are already clean.

- [ ] **Step 4: Run full verification gate**

Run:

```bash
.venv/bin/python scripts/verify.py
```

Expected: PASS.

- [ ] **Step 5: Self-review tests**

Confirm any added or materially changed tests protect behavior or invariants:

- pure story model contracts
- playthrough/detail user-visible behavior
- playback structural-render avoidance
- roll-location selection semantics

Remove or rewrite tests that pin incidental module structure.

- [ ] **Step 6: Final commit**

If documentation or cleanup changed after the previous commits:

```bash
git add DEVELOPERS.md TODO.md web/*.js tests/test_web_story_model.py tests/test_web_app_integration.py
git commit -m "docs: record web app modularization boundaries"
```

## Ratchet Rule For Future Web Changes

After this plan lands, use this rule for future web UI work:

- If a change touches only orchestration, keep it in `web/app.js`.
- If a change adds story adaptation, put it in `web/story-model.js`.
- If a change adds cinematic SVG rendering, put it in `web/sky-camera-view.js`.
- If a change adds playthrough-only rendering, put it in `web/playthrough-view.js`.
- If a change adds detail-only rendering, put it in `web/detail-view.js`.
- If a change needs edits across three or more distant areas of `web/app.js`, first extract the smallest cohesive module that makes the change local.

## Final Handoff Checklist

- [ ] `web/app.js` still loads from `web/index.html`.
- [ ] No extracted module imports `web/app.js`.
- [ ] Tests added or changed are semantic and fixture-stable.
- [ ] Existing Playthrough and Detail integration tests pass.
- [ ] Playback RAF path still avoids structural render.
- [ ] `.venv/bin/python scripts/verify.py` passes.
- [ ] Final response states which behavior or invariant any new tests protect.
