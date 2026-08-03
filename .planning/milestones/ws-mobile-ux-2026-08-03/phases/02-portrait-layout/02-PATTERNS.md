# Phase 2: Portrait Layout - Pattern Map

**Mapped:** 2026-07-26
**Files analyzed:** 3 (2 modified, 1 new; `web/app.js` is one file receiving many new functions/branches)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `web/app.js` → `render()` D-12 branch | controller (structural render dispatch) | request-response (state → DOM) | `web/app.js:903-928` `render()` existing branch | exact (editing in place) |
| `web/app.js` → `renderMobilePortrait()` (new) | component (structural render) | transform (model → DOM) | `web/app.js` `renderAppShell()` + `renderPlaythrough()` (~:1440-1463) | role-match |
| `web/app.js` → `renderMobileScrubber()`/mini-rail markup (new) | component | transform | `design/mobile-ux/prototype/scrubber.jsx` `MiniRail` (React) + desktop scrubber markup in `renderAppShell()` | role-match (cross-language port) |
| `web/app.js` → `cachePlaybackDomRefs()` extension | utility (DOM ref cache) | CRUD (populate refs) | `web/app.js:2565-2586` existing `cachePlaybackDomRefs` | exact |
| `web/app.js` → `updatePlaybackFrame()` early branch + `updateMobilePortraitFrame()` (new) | controller (incremental update) | event-driven (rAF tick → DOM patch) | `web/app.js:2589-2665` `updatePlaybackFrame`/`updatePlaythroughFrame` | exact |
| `web/app.js` → `attachMobilePortraitGestures()` (new) | event-handler/middleware | event-driven | `web/app.js:2838-2852` `attachMobileGestureProbes()` | exact |
| `web/app.js` → `panOffsetForPlayhead`/`fractionFromPointer`/`binRolls`/`finalizeBin`/`binSize` (new, verbatim port) | utility (pure transform) | transform | `design/mobile-ux/prototype/scrubber.jsx:14-67` | exact (verbatim port target) |
| `web/app.js` → flyout stack (`openMobileSurface`/`closeMobileSurface`, Settings/About/Help render fns, new) | component + event-handler | event-driven (history/focus) | `design/mobile-ux/prototype/panels.jsx` `SettingsFlyout`/`InfoFlyout`/`HelpOverlay`/`Seg` (visual ref only — no focus-trap/back-gesture prior art) | partial (visual reference only; new mechanics) |
| `web/mobile.css` (portrait rules addition) | config/style | — | `web/mobile.css:1-80` (Phase 1 foundation classes) + `design/mobile-ux/prototype/styles.css` | exact (extend existing file) |
| `tests/test_mobile_portrait.py` (new) | test | request-response (browser assertions) | `tests/test_mobile_plumbing.py` (full file, esp. `_page_with_console_capture`, `PHONE_PORTRAIT`/`PHONE_LANDSCAPE`, `GESTURE_STATS_INIT`) + `tests/test_desktop_smoke.py` | exact |

## Pattern Assignments

### `web/app.js` — `render()` D-12 branch (controller, request-response)

**Analog:** `web/app.js` current `render()` (lines ~903-928, read directly this session)

**Current code (to be edited, not replaced wholesale):**
```js
function render() {
  const root = document.getElementById("root");
  clear(root);
  recordStructuralRender();
  app.dom = {};
  app.frameKeys = { narrative: null, skyCamera: null, detail: {} };
  app.carousel.visibleSlots = new Map();
  if (app.error) { root.append(renderLoadError(app.error)); return; }
  if (!app.data) { root.append(renderLoading()); return; }
  root.append(renderAppShell());
  cachePlaybackDomRefs();
  updatePlaybackFrame();
  if (app.layoutMode !== "desktop") {
    root.append(el("div", {
      class: "mobile-gesture-probe", "aria-hidden": "true",
      style: "position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0;",
    }));
    attachMobileGestureProbes();
  }
}
```

**Target shape (from RESEARCH.md Pattern 2 / Code Examples, confirmed against live line numbers):**
```js
if (app.layoutMode === "portrait") {
  root.append(renderMobilePortrait());
} else {
  root.append(renderAppShell()); // desktop AND landscape-fallback, UNCHANGED
}

cachePlaybackDomRefs();
updatePlaybackFrame();

if (app.layoutMode === "landscape") {
  // UNCHANGED from Phase 1 — Phase 3's job.
  root.append(el("div", { class: "mobile-gesture-probe", "aria-hidden": "true",
    style: "position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0;" }));
  attachMobileGestureProbes();
} else if (app.layoutMode === "portrait") {
  attachMobilePortraitGestures();
}
```
**Critical ordering note (Pitfall 2):** the `updatePlaybackFrame()` portrait early-branch (below) MUST land in the same change as this branch, or the very first render loops infinitely (`updatePlaybackFrame`'s desktop gate `if (!app.dom?.playhead) { render(); return; }` recurses forever since portrait DOM never has `#scrubber-playhead`).

---

### `web/app.js` — `renderMobilePortrait()` (component, transform)

**Analog:** `renderAppShell()` (structural composition) + `renderPlaythrough()`/`renderViewportFrame()`/`renderSkyCamera()` (sky primitives), all in `web/app.js` (`renderSkyCamera` read in full at ~1621-1966; `renderViewportFrame` ~1456-1463).

**Core pattern — call frozen sky primitives directly, do not port them:**
```js
// renderSkyCamera(roll, scene, t) — confirmed signature, viewBox-based scaling:
return el("div", { class: "sky-camera", style: { opacity: cameraOpacity.toFixed(3) } },
  svgEl("svg", { viewBox, preserveAspectRatio: "xMidYMid meet" },
    defs, blurGroup, interiorGroup, beam?.group ?? null, spotlight?.group ?? null),
);
```
`renderSkyCamera`/`renderViewportFrame` scale into any container box via `viewBox`/`preserveAspectRatio="xMidYMid meet"` + CSS `width:100%;height:100%` — call them as-is inside a **new** `.mobile-sky` container (`position:relative; overflow:hidden`), never reuse `.viewport`/`.app` class names (Pitfall 1: those carry frozen `min-height: 460px` / `min-height: 100vh` rules).

**Skeleton (illustrative, from RESEARCH.md Code Examples, verified against real function names):**
```js
function renderMobilePortrait() {
  const frame = playthroughFrameState();
  return el("div", { class: "mobile-app" },
    el("div", { class: "mobile-top-cluster" }, /* chips */),
    el("div", { class: "mobile-sky" },
      renderViewportFrame(),                                   // FROZEN, called as-is
      el("div", { class: "mobile-sky-camera-layer" },          // NEW class — see Pitfall 5
        frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,
      ),
    ),
    el("div", { class: "mobile-dock" },
      /* transport row: play/pause FAB, now-meta, speed cycle, gear (settings), info ⓘ (D-14) */
      el("div", { class: "mobile-rail" }, /* mini-rail, see below */),
      /* hint row */
    ),
  );
}
```
**Do NOT call:** `renderPlaythrough()` (composes carousel + narrative-mount, desktop-only fixed geometry) or `renderCarousel()`/`createCarouselSlot()`/`renderConstellationCard()` (hard-coded 320-348px card widths, `.carousel-strip`'s `top:60px;bottom:60px` absolute positioning against `.viewport`'s desktop `min-height`).

**DOM structure reference (visual only):** `design/mobile-ux/prototype/layouts.jsx` `PortraitC` — top chip cluster, sky, dock (transport row + `MiniRail` + hint row).

---

### `web/app.js` — mini-rail scrub wiring (event-handler, event-driven)

**Analog:** `web/mobile-gestures.js:141-198` `attachRailScrub` (byte-identical, do not modify) + `design/mobile-ux/prototype/scrubber.jsx:51-67` (`panOffsetForPlayhead`, `fractionFromPointer` — verbatim port targets).

**`attachRailScrub` exact contract (from `web/mobile-gestures.js`, read in full):**
```js
function attachRailScrub(el, opts) {
  let down = null, lastRollIdx = null;
  function fractionFromEvent(e) {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  }
  function onDown(e) { /* ... */ const f = fractionFromEvent(e); lastRollIdx = opts.onScrub?.(f) ?? null; }
  function onMove(e) {
    /* ... */ const f = fractionFromEvent(e); const idx = opts.onScrub?.(f);
    if (idx != null && lastRollIdx != null && idx !== lastRollIdx) haptic();
    if (idx != null) lastRollIdx = idx;
  }
  function onUp(e) { /* ... */ opts.onScrubEnd?.(); }
  // pointerdown/move/up/cancel listeners; returns teardown fn.
}
```
**Key contract fact:** `onScrub(fraction)` receives a **viewport-relative** fraction (0..1 across rail width); the callback must return a value (roll index, or the roll object itself — reference-stable is fine, module only checks `idx !== lastRollIdx`) so haptic-per-roll-cross fires. The pan/zoom transform must happen **inside** this callback — never via a second raw pointerdown/pointermove listener (that was the prototype's React-only `MiniRail` workaround; porting it creates a second scrub input path, forbidden by no-parallel-implementations and D-17).

**Verbatim port from `design/mobile-ux/prototype/scrubber.jsx:14-67`:**
```js
const MIN_DOT_SPACING_PX = 5;
function binRolls(rolls, totalWords, pxWidth, minPx = MIN_DOT_SPACING_PX) {
  if (!rolls.length || pxWidth <= 0) return [];
  const minWords = (minPx / pxWidth) * totalWords;
  const bins = [];
  let cur = null;
  for (const r of rolls) {
    if (!cur || r.wordPosition - cur.firstWord > minWords) {
      if (cur) bins.push(finalizeBin(cur));
      cur = { firstWord: r.wordPosition, rolls: [r], outcomes: {} };
      cur.outcomes[r.outcome] = 1;
    } else {
      cur.rolls.push(r);
      cur.outcomes[r.outcome] = (cur.outcomes[r.outcome] || 0) + 1;
    }
  }
  if (cur) bins.push(finalizeBin(cur));
  return bins;
}
function finalizeBin(bin) {
  const last = bin.rolls[bin.rolls.length - 1];
  bin.midWord = (bin.firstWord + last.wordPosition) / 2;
  const e = bin.outcomes;
  if ((e.hit || 0) >= (e.miss || 0) && (e.hit || 0) >= (e.unknown || 0)) bin.dominant = "hit";
  else if ((e.miss || 0) >= (e.unknown || 0)) bin.dominant = "miss";
  else bin.dominant = "unknown";
  return bin;
}
function binSize(bin) {
  if (bin.rolls.length === 1) return 6;
  return Math.min(14, 5 + Math.round(Math.sqrt(bin.rolls.length) * 1.6));
}
function panOffsetForPlayhead(playheadPctRaw, zoom) {
  if (zoom <= 1) return 0;
  const wantedPct = playheadPctRaw * zoom - 50;
  const maxPct = (zoom - 1) * 100;
  return Math.max(0, Math.min(maxPct, wantedPct));
}
function fractionFromPointer(el, e, zoom, panPct) {
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0) return 0;
  const xFracView = (e.clientX - rect.left) / rect.width;
  const innerFrac = (xFracView + panPct / 100) / zoom;
  return Math.max(0, Math.min(1, innerFrac));
}
```
Bin recompute triggers: structural render, zoom change, rail ResizeObserver (rAF-coalesced) — never per playback frame (D-18).

---

### `web/app.js` — `cachePlaybackDomRefs()` extension + `updatePlaybackFrame()` early branch (controller, event-driven)

**Analog:** `web/app.js:2565-2665` (existing `cachePlaybackDomRefs`, `updatePlaybackFrame`, `updateScrubberFrame`, `updatePlaythroughFrame` — all read in full this session).

**Existing `cachePlaybackDomRefs` (confirmed live code):**
```js
function cachePlaybackDomRefs() {
  app.dom = {
    playhead: document.querySelector("#scrubber-playhead"),
    // ...statStrip, playPause, playthrough, viewport, carouselStrip,
    // skyCameraLayer, narrativeMount, detail, panels...
  };
  app.carousel.visibleSlots = new Map(
    [...document.querySelectorAll(".carousel-slot[data-roll-uid]")]
      .map(slot => [slot.dataset.rollUid, slot]),
  );
}
```
Extend (do not replace) with a portrait branch appending `app.dom.mobilePlayhead`, `mobileRailInner`, `mobileChips`, `mobileDockMeta`, `mobileActiveMarker`, `mobileSkyCameraLayer` — queried only when `app.layoutMode === "portrait"`.

**Existing `updatePlaybackFrame` (confirmed live code — the mandatory early-return insertion point, Pitfall 2):**
```js
function updatePlaybackFrame() {
  if (!app.data) return;
  if (!app.dom?.playhead) {
    render();
    return;
  }
  updateScrubberFrame();
  updateStatStripFrame();
  updatePlaybackControlsFrame();
  if (app.mode === "playthrough") updatePlaythroughFrame();
  else if (app.mode === "detail") updateDetailFrame();
  centerScrubber();
}
```
New shape: insert `if (app.layoutMode === "portrait") { updateMobilePortraitFrame(); return; }` as the very first check (before the `!app.dom?.playhead` gate), so portrait never falls through to the desktop-only gate. Desktop/landscape path stays byte-identical below it.

**`updatePlaythroughFrame` — the incremental key-diff pattern `updateMobilePortraitFrame` should mirror:**
```js
function updatePlaythroughFrame() {
  const frame = playthroughFrameState();
  const skyCameraKey = frame.scene ? `scene:${frame.lastRoll?.uid || ""}` : "none";
  if (app.dom.skyCameraLayer && (frame.scene || app.frameKeys.skyCamera !== skyCameraKey)) {
    app.dom.skyCameraLayer.replaceChildren(
      ...(frame.scene ? [renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT)] : []),
    );
    app.frameKeys.skyCamera = skyCameraKey;
  }
  // ...narrative-mount key-diff, same replaceChildren-on-key-change pattern...
}
```
**Pitfall 5:** the mobile sky-camera mount must use a distinct class (`.mobile-sky-camera-layer`), never the literal `.sky-camera-layer` desktop class — otherwise `updatePlaythroughFrame` (desktop path) would accidentally also match it via `document.querySelector(".sky-camera-layer")` in `cachePlaybackDomRefs`.

---

### `web/app.js` — `attachMobilePortraitGestures()` (event-handler, event-driven)

**Analog:** `web/app.js:2838-2852` `attachMobileGestureProbes()` (existing, confirmed live code — the exact per-render attach/teardown convention to mirror):
```js
function attachMobileGestureProbes() {
  if (typeof app.mobileGestureTeardown === "function") {
    app.mobileGestureTeardown();
    app.mobileGestureTeardown = null;
  }
  const probe = document.querySelector(".mobile-gesture-probe");
  if (!probe || typeof window.attachSkyGestures !== "function") return;
  app.mobileGestureTeardown = window.attachSkyGestures(probe, {
    onTap: () => recordGestureEvent("taps"),
    onDoubleTap: () => recordGestureEvent("doubleTaps"),
    onSwipeStep: () => recordGestureEvent("swipeSteps"),
    onSwipeEnd: () => recordGestureEvent("swipeEnds"),
  });
  recordGestureEvent("attaches");
}
```
**Teardown lives on `app` (not `app.dom`, which `render()` resets every call).** New function follows the same shape but with production callbacks routed through existing model setters:
```js
function attachMobilePortraitGestures() {
  if (typeof app.mobileGestureTeardown === "function") { app.mobileGestureTeardown(); app.mobileGestureTeardown = null; }
  if (typeof app.mobileRailTeardown === "function") { app.mobileRailTeardown(); app.mobileRailTeardown = null; }
  const skyEl = document.querySelector(".mobile-sky");
  if (skyEl && typeof window.attachSkyGestures === "function") {
    app.mobileGestureTeardown = window.attachSkyGestures(skyEl, {
      onTap: () => { if (app.tapToPause) togglePlayback(); },
      onDoubleTap: () => {
        const last = lastRollAtWord(app.wordPos);   // NOT data.rolls.at(-1) — Pitfall 4
        if (last) setWordPos(last.word_position);
        if (!app.playing) togglePlayback();
      },
      onSwipeStep: (dir) => { /* step ±1 roll relative to current playhead */ },
      onSwipeEnd: () => persistBookmarkNow(),
    });
  }
  const railEl = document.querySelector(".mobile-rail");
  if (railEl && typeof window.attachRailScrub === "function") {
    app.mobileRailTeardown = window.attachRailScrub(railEl, {
      onScrub: (viewportFraction) => {
        const total = app.data.story.total_words;
        const playheadPctRaw = total ? (app.wordPos / total) * 100 : 0;
        const panPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
        const innerFrac = Math.max(0, Math.min(1, (viewportFraction + panPct / 100) / app.mobileTimelineZoom));
        const target = Math.round(innerFrac * total);
        setWordPos(target);
        return lastRollAtWord(target); // reference-stable roll object, no new index helper needed
      },
      onScrubEnd: () => persistBookmarkNow(),
    });
  }
}
```
**Reuse, never rewrite:** `setWordPos`, `togglePlayback`, `setMode`, `lastRollAtWord` (`web/app.js:716`), `chapterAtWord`, `formatWords`, `persistBookmarkNow`/`persistBookmarkSoon` — same functions desktop's keyboard/click handlers already call.

**Pitfall 4 (double-tap semantics):** implement as `setWordPos(lastRollAtWord(app.wordPos)?.word_position ?? app.wordPos)` — NOT `data.rolls[data.rolls.length - 1]` (the prototype's `app.jsx:177-183` literal, which jumps to the end of the whole story).

---

### `web/app.js` — flyout surface stack (D-16) (component + event-handler, event-driven)

**Analog:** No direct prior-art in this codebase for focus-trap/back-gesture (genuinely new code). Visual/DOM reference only: `design/mobile-ux/prototype/panels.jsx` `SettingsFlyout` (line 39), `InfoFlyout` (line 94), `HelpOverlay` (line 132), `Seg` (line 216) — port markup/labels, not mechanics. Toggle-exclusivity precedent: `prototype/app.jsx:230-243` `openSettings`/`openInfo`.

**Existing pref bridge these flyouts must call (do not add a second persistence path) — confirmed live code, `web/app.js` `// ── Mobile UX ──` section:**
```js
function setTapToPause(value) { app.tapToPause = Boolean(value); store(LS_TAP_TO_PAUSE, app.tapToPause); }
function setHaptics(value) { app.haptics = Boolean(value); store(LS_HAPTICS, app.haptics); }
function setMobileTimelineZoom(value) {
  if (![1, 2, 4, 8].includes(value)) return; // allow-list; ignore anything else
  app.mobileTimelineZoom = value;
  store(LS_MOBILE_TIMELINE_ZOOM, value);
}
function markHelpSeen() { app.helpSeen = true; store(LS_HELP_SEEN, true); }
window.__bcfMobile = { setTapToPause, setHaptics, setMobileTimelineZoom, markHelpSeen };
```
**Pitfall 3 (critical):** the prototype's Settings mode segment uses value `"details"` (plural); the live app's `app.mode` allow-list is `["playthrough", "detail"]` (singular, no validation on write via `setMode`). Port only the **label** ("Details") from the prototype; the value must be `"detail"`. Recommend adding write-side validation to `setMode` mirroring `setRollLocation`'s existing allow-list-on-write pattern (V5 input validation, defense-in-depth).

**New mechanics (from RESEARCH.md Pattern 5, no prior art to port from, only to follow as spec):**
```js
function openMobileSurface(kind, triggerEl) {
  closeMobileSurface();
  app.mobileSurface = kind; // "settings" | "info" | "help"
  app.mobileSurfaceOpener = triggerEl;
  history.pushState({ bcfMobileSurface: kind }, "");
  render();
}
function closeMobileSurface({ fromPopstate = false } = {}) {
  if (!app.mobileSurface) return;
  app.mobileSurface = null;
  if (!fromPopstate) history.back();
  const opener = app.mobileSurfaceOpener;
  app.mobileSurfaceOpener = null;
  render();
  opener?.focus?.();
}
window.addEventListener("popstate", (e) => {
  if (app.mobileSurface) closeMobileSurface({ fromPopstate: true });
});
```

---

### `web/mobile.css` (config/style)

**Analog:** `web/mobile.css:1-80` (Phase 1 foundation, read directly — `.mobile-sky-surface`/`.mobile-rail-surface` touch-action classes, `--safe-top/bottom/left/right`, `--mobile-vh`) + `design/mobile-ux/prototype/styles.css` (visual reference to adapt).

**Existing foundation to build on (confirmed live code):**
```css
@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px) {
  .mobile-sky-surface { touch-action: pan-y; overscroll-behavior: contain; }
  .mobile-rail-surface { touch-action: none; overscroll-behavior: contain; }
  :root {
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-left: env(safe-area-inset-left, 0px);
    --safe-right: env(safe-area-inset-right, 0px);
    /* --mobile-vh uses svh, never vh — Pitfall 1 */
  }
}
```
**Rule:** new portrait rules append into this same media-query block / file; reuse `--cyan`/`--green`/etc. desktop CSS variables (read-only reference, never redefine); never edit `web/style.css`. New root/sky container classes must be entirely new names (`.mobile-app`, `.mobile-sky`, `.mobile-dock`, `.mobile-rail`) — never `.app`/`.viewport` (Pitfall 1).

---

### `tests/test_mobile_portrait.py` (test, request-response)

**Analog:** `tests/test_mobile_plumbing.py` (full file read) + `tests/test_desktop_smoke.py` (gate artifact).

**Harness helpers to reuse verbatim (confirmed live code, `tests/test_mobile_plumbing.py`):**
```python
from tests.helpers.web_runtime_site import staged_web_runtime_site

PHONE_PORTRAIT = {"width": 390, "height": 844}
PHONE_LANDSCAPE = {"width": 844, "height": 390}

def _chromium_browser_or_skip(playwright, playwright_api):
    try:
        return playwright.chromium.launch()
    except playwright_api.Error as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        raise

def _page_with_console_capture(browser, site, path="/web/?dataPackage=tiny-default", *,
                                viewport=None, storage=None, init_script=None):
    page = browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
    if init_script: page.add_init_script(init_script)
    if storage:
        page.add_init_script("const entries = " + json.dumps(storage) +
            "; for (const [key, value] of Object.entries(entries)) localStorage.setItem(key, value);")
    messages = []
    page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text}") if msg.type in {"error", "pageerror"} else None)
    page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
    page.goto(site.url_for(path), wait_until="networkidle")
    return page, messages
```
**Diagnostic init-script pattern** (`GESTURE_STATS_INIT`, `window.__bcfGestureStats`) and the structural-render counter pattern (`window.__bcfRenderStats = { structuralRenders: 0 }`, asserted via `page.evaluate("window.__bcfRenderStats.structuralRenders") == 0`) both carry forward unchanged — new portrait tests inject the same init scripts and assert the same zero-structural-render invariant during simulated playback (`test_gestures_fire_exactly_once_without_structural_renders` is the direct structural analog for the new `test_portrait_playback_has_no_recursive_renders`).

**Required new test cases (per RESEARCH.md's Phase Requirements → Test Map, using `PHONE_PORTRAIT` fixture and a 320px-width viewport for the chip-overlap check):**
- `test_portrait_layout_proportions_and_chip_overlap` (MOBP-01)
- `test_sky_gesture_contract` (MOBP-02)
- `test_rail_scrub_zoom_aware` (MOBP-03)
- `test_cluster_binning_at_1x` (MOBP-04)
- `test_settings_about_help_persist_across_reload` (MOBP-05) — must assert `localStorage.getItem("bcf:mode")` reads back exactly `"detail"` after a real reload (Pitfall 3), not just in-memory `app.mode`.
- `test_portrait_playback_has_no_recursive_renders` (regression, Pitfall 2)

**Do not modify:** `tests/test_mobile_plumbing.py`'s landscape-viewport assertions must keep passing unmodified (Pitfall 6) — run it alongside the new file, never edit its landscape-mode tests.

## Shared Patterns

### Per-render gesture attach/teardown lifecycle (D-07 convention)
**Source:** `web/app.js:2838-2852` (`attachMobileGestureProbes`)
**Apply to:** `attachMobilePortraitGestures`, mini-rail scrub attach — teardown stored on `app` (survives `render()`'s `app.dom = {}` reset), called defensively before re-attach, attach happens only inside the `render()` pass, never from the `matchMedia`/layout-change handler.

### Preference persistence via existing `LS_*`/`store()`/allow-list readers
**Source:** `web/app.js` `// ── Mobile UX ──` section — `setTapToPause`/`setHaptics`/`setMobileTimelineZoom`/`markHelpSeen`, `window.__bcfMobile` bridge, `readStoredChoice`'s allow-list pattern.
**Apply to:** all Settings/About/Help flyout controls — no new `bcf:mobile:*` namespace, no ad-hoc `localStorage` calls. Watch the `"detail"` vs `"details"` allow-list mismatch (Pitfall 3) when porting the mode `Seg` control.

### Incremental key-diff DOM update pattern
**Source:** `updatePlaythroughFrame()` (`web/app.js` ~2641-2665) — `replaceChildren` only when a computed key (`scene:${uid}`) changes, cached on `app.frameKeys`.
**Apply to:** `updateMobilePortraitFrame()`'s sky-camera layer, chip text nodes, rail playhead transform, cluster-bin recompute gating (never per-frame, per D-18).

### Mode-branched render dispatch (`layoutMode` switch)
**Source:** `render()`'s existing `app.layoutMode !== "desktop"` block (being extended in place per D-12).
**Apply to:** every call site that needs to distinguish desktop/landscape (unchanged this phase) from portrait (new this phase) — `render()`, `cachePlaybackDomRefs()`, `updatePlaybackFrame()`.

## No Analog Found

| File/Feature | Role | Data Flow | Reason |
|---------------|------|-----------|--------|
| Flyout focus-trap + `history.pushState`/`popstate` back-gesture dismissal (D-16) | component/event-handler | event-driven | No prior dialog/overlay a11y code exists in this codebase; the prototype is a React demo with no keyboard/focus-trap concerns wired in. Planner must implement fresh from RESEARCH.md Pattern 5's specification — no verbatim source to port, only the prototype's flyout *markup* is reusable. |

## Metadata

**Analog search scope:** `web/app.js` (full render/update/mobile-section reads), `web/mobile-gestures.js` (full file, 198 lines), `web/mobile.css` (foundation section), `design/mobile-ux/prototype/{scrubber,panels,layouts,app}.jsx`, `tests/test_mobile_plumbing.py` (full file), `tests/helpers/web_runtime_site.py`
**Files scanned:** 8 direct reads + targeted greps (no directory-wide Glob needed — CONTEXT.md/RESEARCH.md named all relevant files explicitly)
**Pattern extraction date:** 2026-07-26
</content>
