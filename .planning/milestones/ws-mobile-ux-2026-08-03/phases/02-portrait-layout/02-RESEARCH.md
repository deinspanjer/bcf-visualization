# Phase 2: Portrait Layout - Research

**Researched:** 2026-07-26
**Domain:** Vanilla-JS mode-branched mobile rendering, real SVG sky-camera reuse at phone dimensions, zoom-aware scrub-rail math, flyout focus-trap/back-gesture wiring
**Confidence:** HIGH (all findings grounded in direct reads of `web/app.js`, `web/style.css`, `web/mobile-gestures.js`, `web/mobile.css`, the prototype source, and this workstream's own Phase 1 research/context docs — no external web research was needed; this phase is pure codebase archaeology)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Numbering continues from Phase 1 (D-01..D-11 in `../01-mobile-state-gesture-plumbing/01-CONTEXT.md`); all Phase 1 decisions remain binding here. All decisions below were auto-resolved to the recommended default (`--auto` mode, single pass).

**Layout branching**
- **D-12 Interim landscape fallback:** `[auto]` During Phase 2, `render()` branches to `renderMobilePortrait()` only when `app.layoutMode === "portrait"`. `layoutMode === "landscape"` keeps the current fallback (desktop shell + portrait banner) untouched until Phase 3 delivers `renderMobileLandscape()`. The banner stays the safety net; it is deleted only in Phase 4 (cutover).

**Portrait sky**
- **D-13 Sky source:** `[auto]` The portrait sky region shows the **real** sky visualization driven by the existing playthrough/sky-camera/cinematic model — never a port of the prototype's procedural-diamond placeholder `Sky` (that was a fidelity stand-in; `prototype/sky.jsx` is reference-only for gesture-surface shape). Reuse the frozen render functions (`renderViewportFrame`, `renderSkyCamera`, `renderSpotlight`, `renderBeam`, …) by **calling** them where their sizing assumptions hold at phone dimensions; where they don't, duplicate mobile markup over the same model per plan §7 ("duplicate views over shared model") — never edit the originals. Cinematic behavior is D-01: same as desktop, text-first, within the sky area. Researcher must determine which of the sky render functions are directly callable at mobile sizes vs. need a duplicated mobile variant.

**Portrait chrome & surfaces**
- **D-14 About access in portrait:** `[auto]` The prototype's `PortraitC` has no About entry point (a prototype gap — MOBP-05 requires About to work in portrait). Add an ⓘ (info) icon button to the dock transport row alongside the existing gear button, opening the same About flyout as landscape will use. Help stays the top-right `?` button; the About flyout's "Gestures & help" link opens the Help overlay (per `prototype/panels.jsx` `InfoFlyout`). All new buttons ≥ 44×44 CSS px tap targets.
- **D-15 Details mode in portrait v1:** `[auto]` Faithful prototype port: the Settings "View mode" segment reads/writes the shared `bcf:mode` key, but portrait v1 always renders the playthrough presentation — no new mobile details/roll-log view is invented (the approved design contains none; plan §2 scopes the *control*, not a mobile details layout). Toggling to "details" on a phone persists and takes effect on desktop. **Flag this at the Phase B gate review** so Dre can confirm or redirect; a real mobile details view is captured as a deferred idea. — **Reversibility:** reversible — adding a mobile details view later is additive UI in the mobile-only path.
- **D-16 Flyout back-gesture & focus trap (built here per roadmap note, not deferred to Phase 4):** `[auto]` One surface stack for Settings / About / Help. Opening a surface pushes a `history.pushState` sentinel; `popstate` closes the topmost surface (mobile back gesture dismisses instead of leaving the app); programmatic close consumes its sentinel via `history.back()` so the history stack never grows stale. Backdrop tap closes flyouts. While a surface is open, focus is trapped inside it (redirect on `focusin` / wrap at edges) and returns to the opening button on close. Mobile-only wiring — desktop dialogs untouched.

**Scrub & playback machinery**
- **D-17 Zoom-aware rail wiring (single path):** `[auto]` `web/mobile-gestures.js` stays byte-identical (D-07/verbatim-port precedent). The mini-rail attaches **only** `attachRailScrub`; its `onScrub(fraction)` callback converts the viewport fraction to the inner-content fraction using the verbatim-ported `panOffsetForPlayhead` + the `fractionFromPointer` math (inner = (f + panPct/100) / zoom), then commits via the existing `setWordPos` path and returns the roll index so the module's built-in haptic-per-roll-cross fires. The prototype `MiniRail`'s parallel raw pointer-listener override (which passed `onScrub: null` and bypassed the haptic) was a React workaround — do **not** port it; porting it would create a second scrub input path (violates no-parallel-implementations).
- **D-18 Portrait playback update tier:** `[auto]` No second rAF loop. The existing `tickPlayback` → `updatePlaybackFrame` incremental tier drives portrait: `cachePlaybackDomRefs` additionally caches portrait refs (playhead, rail inner transform, chips, dock meta, active-roll marker) when `layoutMode === "portrait"`, and `updatePlaybackFrame` updates them via an early mobile branch that leaves the desktop code path byte-identical. Cluster bins (`binRolls`/`finalizeBin`/`binSize`, ported verbatim per plan §3.1) recompute only on structural render, zoom change, or rail resize (ResizeObserver, rAF-coalesced) — never per playback frame. Gesture callbacks never trigger structural `render()` mid-drag (D-07).

### Claude's Discretion

- Exact portrait DOM structure/class names inside `renderMobilePortrait()` (follow `prototype/layouts.jsx` `PortraitC` + `prototype/styles.css` as the visual reference)
- Chip copy/format details (CH chip, roll chip, hint row) and dock "now" metadata formatting
- How the ~60% sky / dock split is expressed in CSS (svh/dvh + flex per D-08; MOBP-01 overlap rule is the acceptance bar)
- Help auto-open trigger point (after data load, mobile layouts only, once per session, when `helpSeen` is false; dismiss calls `markHelpSeen()`)
- Playwright test structure for portrait behaviors (mirroring Phase 1's harness conventions)

### Deferred Ideas (OUT OF SCOPE)

- Mobile details view (a real portrait roll-log/details presentation behind the mode toggle) — new capability; revisit after D-15 is reviewed at the Phase B gate.
- Full-bleed mobile cinematic — v2, per D-01.
- Mobile v2 backlog per plan §8 (pinch zoom, long-press preview, edge swipe-down peel, throw inertia, real constellation outlines, richer cinematic content, Screen Wake Lock).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MOBP-01 | Portrait phone shows sky (~60% viewport) over an always-visible mini-rail dock; top chips do not overlap the sky's focal label | §"Architecture Patterns" (portrait DOM/CSS split via `flex: 1 1 60%` + `svh`), §"Common Pitfalls" #1 (`.app` class collision with `100vh`), real-device check called out in Environment Availability |
| MOBP-02 | Sky gestures work per gesture contract: tap toggles pause within 250ms (no-op when tap-to-pause off), double-tap snaps to last roll and resumes, horizontal swipe scrubs ±1 roll per 56px with haptic per roll crossed | §"Architecture Patterns" (production gesture callback wiring, replacing `attachMobileGestureProbes`), §"Common Pitfalls" #4 (prototype's dbl-tap semantics differ from what MOBP-02 actually requires — must use `lastRollAtWord`, not "last roll in the whole story") |
| MOBP-03 | Mini-rail drag scrubs word position, honoring current zoom and auto-pan offset (zoom-aware fraction ported verbatim from prototype scrubber) | §"Code Examples" (D-17 exact `attachRailScrub` adapter), §"Don't Hand-Roll" |
| MOBP-04 | Scrubber cluster-binning collapses rolls within 5px at any zoom; multi-roll clusters show numeric count; active roll always renders as a separate cyan diamond on top | §"Code Examples" (`binRolls`/`finalizeBin`/`binSize` verbatim port), §"Architecture Patterns" (recompute triggers per D-18) |
| MOBP-05 | Settings flyout (mode, on-roll, speed, timeline zoom 1×/2×/4×/8×, comfort), About flyout, and Help overlay all work in portrait; help auto-opens when `bcf:help-seen` is false; all prefs persist across reload | §"Common Pitfalls" #3 (`bcf:mode` value mismatch — `"detail"` not `"details"`), §"Architecture Patterns" (D-16 focus-trap/back-gesture surface stack), §"Code Examples" (Settings mode-segment fix) |
</phase_requirements>

## Summary

Phase 2 turns Phase 1's inert plumbing into the first real mobile surface. The single most important fact this research surfaces — not stated anywhere in the plan, prototype, or Phase 1 context — is that **`render()` today unconditionally calls `renderAppShell()` for every layout mode** (`web/app.js:918`), and **`updatePlaybackFrame()` unconditionally gates on the desktop `#scrubber-playhead` DOM node** (`web/app.js:2591`, `if (!app.dom?.playhead) { render(); return; }`). Phase 2 must add both branches (D-12 for the first, D-18 for the second) in the same change, in that order, or portrait mode will recurse into `render()` on every single incremental playback tick the instant a portrait DOM tree exists without a `#scrubber-playhead` node — a synchronous infinite-recursion stack overflow on page load, not a subtle bug that surfaces later.

The sky-camera reuse question (D-13's open research question) resolves cleanly: `renderViewportFrame()` (fixed 24×24px decorative corners, `position:absolute; inset:0`) and `renderSkyCamera()` (a `viewBox`-scaled SVG with `preserveAspectRatio="xMidYMid meet"`, world-coordinate math against a fixed 1600×1000 "world stage") are **both directly callable at any container size**, including phone dimensions — call them, do not duplicate them. `renderSpotlight`/`renderBeam` never need to be called directly; they're internal helpers `renderSkyCamera` already composes. The one thing that must **not** be reused is `renderCarousel()` / `renderPlaythrough()` — both hard-code 320–348px fixed-pixel card geometry and absolute positioning tied to `.viewport`'s desktop dimensions, and per D-05 (Phase 1) there is no mobile carousel surface anyway. The mobile sky container must be a **new** element/class (not `.viewport`, not `.app`) so it inherits neither `.viewport`'s `min-height: 460px` nor `.app`'s `min-height: 100vh` — both are frozen desktop rules that would reintroduce the exact `100vh`-toolbar pitfall Phase 1's research already flagged.

Two further non-obvious findings change what "port from the prototype" safely means here: (1) the prototype's Settings `Seg` control for View mode uses the value `"details"` (with an "s"), but the live app's `LS_MODE`/`readStoredChoice` allow-list is `["playthrough", "detail"]` (no "s") — porting the prototype's literal string breaks reload-persistence (MOBP-05's explicit requirement) silently, because `readStoredChoice` falls back to `"playthrough"` for any value not in its allow-list. (2) the prototype's double-tap handler snaps to `data.rolls[data.rolls.length - 1]` — the *last roll in the entire story* — but the gesture contract's stated intent ("recovers from accidental scrubbing… returns to wherever the cinematic was last firing") and this Phase's own CONTEXT.md code_context both point at `lastRollAtWord(app.wordPos)` (the most recent roll at-or-before the *current* position), which is the function that already exists in `web/app.js:716`. Porting the prototype's literal implementation would jump the user to the end of the story on every double-tap.

**Primary recommendation:** Build `renderMobilePortrait()` as a wholly new function calling the frozen sky primitives (`renderViewportFrame`, `renderSkyCamera`) inside a fresh `.mobile-sky` container; wire `attachSkyGestures`/`attachRailScrub` from the existing byte-identical `web/mobile-gestures.js` with production callbacks that route through the existing shared setters (`setWordPos`, `togglePlayback`, `setMode`); fix `render()` and `updatePlaybackFrame()`'s mode branches in the same commit as the first structural-render work, before anything else, and verify with a Playwright test that plays back for several seconds in portrait with zero recursive/structural re-renders.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Portrait DOM structure (`renderMobilePortrait`) | Browser / Client (structural render) | — | New render function, mirrors `renderAppShell`'s role for the portrait branch |
| Sky cinematic rendering (viewBox SVG) | Browser / Client (structural + incremental render) | — | `renderSkyCamera` is pure client-side SVG generation from already-loaded `app.data`; no new data fetch |
| Gesture interpretation (tap/dbl-tap/swipe/drag) | Browser / Client (event layer) | — | `web/mobile-gestures.js` is a pure Pointer-Events interpreter with no app-state knowledge; callbacks write into the shared model layer |
| Word-position / mode / roll-lookup model | Browser / Client (shared model layer) | — | `setWordPos`, `setMode`, `lastRollAtWord`, `chapterAtWord` etc. already exist and are read by both desktop and mobile; this is the *only* intentional sharing surface (per plan §7) |
| Settings/About/Help flyout stack + focus trap + back-gesture | Browser / Client (overlay/dialog layer) | — | Pure DOM/history-API wiring, mobile-only; no server, no new client-side framework |
| Preference persistence (`bcf:*` keys) | Browser / Client (localStorage) | — | Existing `store()`/`readStored*` helpers; no new persistence tier |
| Data (`visualization_facts.json`) | — | — | Already fetched by Phase 0/pre-existing pipeline; this phase adds no new data dependency |

There is no server/API tier in this phase — the entire surface is client-side rendering and interaction over data already loaded into `app.data`.

## Standard Stack

No new libraries. This phase is 100% additive vanilla-JS/CSS inside the existing no-build-step `web/` app, consistent with `.planning/research/STACK.md` (already produced for this milestone) and the project's CLAUDE.md constraint ("Nothing new for web/ — native browser APIs only, no npm install, no build step").

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pointer Events (native) | n/a (browser built-in) | Sky tap/dbl-tap/swipe + rail drag | Already implemented byte-identically in `web/mobile-gestures.js` (Phase 1 output); Phase 2 only wires production callbacks, does not touch the gesture module |
| `history.pushState`/`popstate` (native) | n/a | D-16 flyout back-gesture dismissal | Native History API; no router library needed for a single-level surface stack |
| SVG `viewBox`/`preserveAspectRatio` (native) | n/a | Sky-camera scaling to phone dimensions | Already the mechanism `renderSkyCamera` uses (`preserveAspectRatio="xMidYMid meet"`, `web/app.js:1955-1958`) — confirmed by direct read, not assumed |
| `ResizeObserver` (native) | n/a | Mini-rail pixel-width tracking for cluster-binning at current zoom | Already the mechanism the prototype's `MiniRail` uses (`design/mobile-ux/prototype/scrubber.jsx:78-84`); no polyfill needed on any currently-shipping engine |

### Supporting

No supporting/new packages. All "supporting" functionality (haptics, `matchMedia`, storage versioning) already shipped in Phase 1 per `.planning/research/STACK.md`.

### Alternatives Considered

Not applicable — no new technology choices this phase; all decisions were locked in CONTEXT.md D-12..D-18 or in Phase 1's STACK.md research.

**Installation:** None. No `npm install`, no new `<script>` tags beyond what Phase 1 already added (`web/mobile-gestures.js`, loaded before `web/app.js` per `web/index.html:14`).

## Package Legitimacy Audit

**Not applicable this phase.** No external packages are installed, added, or upgraded. `web/` remains a zero-dependency, no-build-step static site; the only new files are new functions inside `web/app.js`, new CSS in `web/mobile.css`, and new Playwright test files under `tests/` (Playwright itself was already a project dependency established in Phase 1 — see `tests/test_desktop_smoke.py`, `tests/test_mobile_plumbing.py`).

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                    matchMedia change / orientationchange / initial load
                                        │
                                        ▼
                       onLayoutMaybeChanged() (rAF-coalesced, app.js:2773)
                                        │
                                        ▼
                     app.layoutMode = "desktop" | "portrait" | "landscape"
                                        │
                                        ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │  render()  (app.js:903)                                                  │
 │    clear(root); recordStructuralRender(); reset app.dom/frameKeys        │
 │                                                                          │
 │    ── NEW Phase 2 branch (D-12) ──                                      │
 │    if layoutMode === "portrait"                                         │
 │         → root.append(renderMobilePortrait())         [NEW function]    │
 │    else  (desktop OR landscape-fallback)                                │
 │         → root.append(renderAppShell())               [FROZEN, as-is]  │
 │                                                                          │
 │    cachePlaybackDomRefs()   ── extended for portrait refs (D-18)        │
 │    updatePlaybackFrame()    ── NEW early portrait branch (D-18)         │
 │                                                                          │
 │    ── gesture attach, per-render, mirrors Phase 1 slot ──               │
 │    if layoutMode === "landscape"                                        │
 │         → mount .mobile-gesture-probe + attachMobileGestureProbes()     │
 │           (UNCHANGED — Phase 3 replaces this, not Phase 2)              │
 │    if layoutMode === "portrait"                                         │
 │         → attachMobilePortraitGestures()               [NEW function]   │
 │             attachSkyGestures(skyEl, {onTap, onDoubleTap,               │
 │                                       onSwipeStep, onSwipeEnd})         │
 │             attachRailScrub(railEl, {onScrub, onScrubEnd})              │
 └──────────────────────────────────────────────────────────────────────────┘
                                        │
                    user gesture (tap / dbl-tap / swipe / rail drag)
                                        │
                                        ▼
                  mobile-gestures.js callback (pure interpretation,
                  no app-state knowledge; returns roll-index for haptic)
                                        │
                                        ▼
        shared setters: setWordPos() / togglePlayback() / setMode()
           (same functions desktop keyboard/click handlers call)
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                            ▼
              updatePlaybackFrame()          persistBookmarkSoon()/Now()
              (incremental DOM mutation;          → localStorage (bcf:*)
               early portrait branch updates
               playhead/rail/chips/dock;
               desktop branch untouched)
                          │
                          ▼
        portrait sky mutation reuses renderSkyCamera(frame.lastRoll,
        frame.scene, frame.focusT) — SAME function desktop's
        updatePlaythroughFrame() already calls, just against a
        different cached DOM ref (mobile sky-camera-layer wrapper)
```

### Recommended Project Structure

No new top-level structure — additive within existing files, per plan §0.4/§3.5 and Phase 1 precedent:

```
web/
├── app.js            # + renderMobilePortrait(), attachMobilePortraitGestures(),
│                      #   flyout-stack helpers (D-16), Settings/About/Help render
│                      #   functions, all appended at end of "── Mobile UX ──" section
│                      # + cachePlaybackDomRefs() extended (portrait refs)
│                      # + updatePlaybackFrame() extended (early portrait branch)
│                      # + render() extended (D-12 branch)
├── mobile-gestures.js # UNCHANGED — byte-identical (D-17)
├── mobile.css         # + portrait-specific rules (sky/dock split, mini-rail,
│                      #   flyouts, chips) — Phase 1's touch-action/safe-area/
│                      #   svh foundation classes get applied to real elements here
└── style.css          # UNCHANGED (frozen)
tests/
└── test_mobile_portrait.py   # new — Playwright, mirrors test_mobile_plumbing.py
                                #   / test_desktop_smoke.py conventions
```

### Pattern 1: Reuse frozen sky primitives by calling, not porting

**What:** `renderViewportFrame()` and `renderSkyCamera(roll, scene, t)` are called directly from `renderMobilePortrait()`'s structural render and from the portrait branch of `updatePlaythroughFrame`'s incremental update, exactly as desktop's `renderPlaythrough()` (`app.js:1440-1454`) and `updatePlaythroughFrame()` (`app.js:2641-2665`) already do.

**Why these two are safe to call as-is (verified by direct read):**
- `renderViewportFrame()` (`app.js:1456-1463`) returns 4 decorative corner `<span>`s absolutely positioned at fixed 12px/24×24px offsets (`web/style.css:1186-1201`) inside a `position:absolute; inset:0` wrapper. No dependency on container aspect ratio or a specific ancestor class — only needs `position:relative` on its parent.
- `renderSkyCamera(roll, scene, t)` (`app.js:1621-1966`) builds an SVG with `viewBox` computed by `focusCameraViewRect(t, scene)` (from `web/viz-model.js`) against a fixed 1600×1000 "world stage" (`WORLD_STAGE_WIDTH`/`WORLD_STAGE_HEIGHT`, `viz-model.js:332-333`), and sets `preserveAspectRatio="xMidYMid meet"` (`app.js:1957`) plus CSS `width:100%; height:100%` on the `<svg>` (`web/style.css:1180-1184`). This means it scales into *any* container box, including a narrow-tall phone sky region — it will letterbox (empty bars top/bottom) if the container is taller-and-narrower than the fixed 1.6:1 world-stage aspect, since `xMidYMid meet` fits-and-centers rather than stretches. This is a visual-quality consideration for the Phase B gate real-device check, not a functional blocker.
- `renderSpotlight()`/`renderBeam()` (`app.js:1972-2036` / `2036-2130`+) are **never called from outside `renderSkyCamera`** (confirmed: the only call sites are `app.js:1903` and `1910`, both inside `renderSkyCamera`'s own body). Nothing in mobile code needs to call them directly — they arrive for free.

**What must NOT be called:** `renderPlaythrough()` (composes carousel + narrative-mount, both desktop-only) and `renderCarousel()`/`createCarouselSlot()`/`renderConstellationCard()` (hard-coded `cardWidth = 348`, `size = 320` fixed-pixel geometry at `app.js:1474, 1556`, and `.carousel-strip`'s `top: 60px; bottom: 60px` absolute positioning at `web/style.css:1208-1215` — all sized against desktop's `.viewport` `min-height: 460px`). Per D-05 (Phase 1) there is no mobile carousel surface, so this exclusion is already decided, not a new judgment call.

**Container requirement:** The new mobile sky container must be `position:relative; overflow:hidden` (mirroring what `.viewport` already provides for desktop) but must be a **new CSS class** (e.g. `.mobile-sky`), not a reuse of `.viewport` or `.app` — see Pitfall 1 below for why.

### Pattern 2: Per-render gesture attach, mirroring Phase 1's exact convention

**What:** `attachSkyGestures`/`attachRailScrub` are called inside `renderMobilePortrait()`'s call site in `render()`, after the DOM is mounted, in the same lifecycle slot Phase 1 already established for `attachMobileGestureProbes()` (`app.js:2838-2852`). Teardown is stored on `app` (not `app.dom`, which `render()` resets every call) and invoked defensively before re-attach — same pattern, just with production callbacks instead of diagnostic counters.

**Critical nuance not visible from the plan alone:** Phase 1's landscape-mode probe wiring must be **preserved untouched** in this phase. `render()`'s existing `if (app.layoutMode !== "desktop")` block (`app.js:921-928`) currently fires for *both* portrait and landscape. D-12 only replaces the portrait side with real rendering; landscape must keep exactly what Phase 1 shipped (desktop shell + banner + gesture probe) until Phase 3. Concretely, `render()`'s post-shell block should become:

```js
// after: cachePlaybackDomRefs(); updatePlaybackFrame();
if (app.layoutMode === "landscape") {
  // UNCHANGED from Phase 1 — Phase 3's job, not this phase's.
  root.append(el("div", { class: "mobile-gesture-probe", "aria-hidden": "true",
    style: "position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0;" }));
  attachMobileGestureProbes();
} else if (app.layoutMode === "portrait") {
  attachMobilePortraitGestures(); // NEW — production callbacks
}
```

This preserves every Phase 1 Playwright assertion in `tests/test_mobile_plumbing.py` that runs at `PHONE_LANDSCAPE` viewport (several do — `test_gesture_attach_survives_forced_rerenders_without_double_fire`, `test_mid_drag_rerender_is_safe_and_fresh_probe_fires_once`) without needing to touch or re-verify that test file's landscape assertions.

### Pattern 3: Zoom-aware rail scrub (D-17) — exact math to port

**What:** Verbatim-port `panOffsetForPlayhead(playheadPctRaw, zoom)` and `fractionFromPointer(el, e, zoom, panPct)` from `design/mobile-ux/prototype/scrubber.jsx:51-67` as plain functions in `app.js`'s mobile section. Wire them as the `onScrub` callback passed to `web/mobile-gestures.js`'s `attachRailScrub(el, opts)` — **not** the prototype's `MiniRail`'s second `useEffect` that attaches raw `pointerdown`/`pointermove` listeners directly and passes `onScrub: null` to `attachRailScrub` (`scrubber.jsx:87-114`). That second effect was a React-only workaround to get zoom-aware fraction math past `attachRailScrub`'s built-in (viewport-fraction-only) `fractionFromEvent` — in this port, the *callback itself* does the zoom-aware conversion, so `attachRailScrub`'s own pointer capture, drag lifecycle, and haptic-per-roll-cross logic (`web/mobile-gestures.js:149-193`) all keep working unmodified:

```js
// New in web/app.js mobile section — verbatim math from prototype/scrubber.jsx
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

function attachMobilePortraitGestures() {
  if (typeof app.mobileGestureTeardown === "function") { app.mobileGestureTeardown(); app.mobileGestureTeardown = null; }
  if (typeof app.mobileRailTeardown === "function") { app.mobileRailTeardown(); app.mobileRailTeardown = null; }

  const skyEl = document.querySelector(".mobile-sky");
  if (skyEl && typeof window.attachSkyGestures === "function") {
    app.mobileGestureTeardown = window.attachSkyGestures(skyEl, {
      onTap: () => { if (app.tapToPause) togglePlayback(); },
      onDoubleTap: () => {
        const last = lastRollAtWord(app.wordPos);   // NOT data.rolls.at(-1) — see Pitfall 4
        if (last) setWordPos(last.word_position);
        if (!app.playing) togglePlayback();
      },
      onSwipeStep: (dir) => {
        // step ±1 roll relative to current playhead — reuse lastRollAtWord-adjacent
        // roll-index lookup; no new tokenizer/positional math needed.
      },
      onSwipeEnd: () => persistBookmarkNow(),
    });
  }

  const railEl = document.querySelector(".mobile-rail");
  if (railEl && typeof window.attachRailScrub === "function") {
    app.mobileRailTeardown = window.attachRailScrub(railEl, {
      onScrub: (viewportFraction) => {
        // attachRailScrub passes a viewport-relative fraction; re-derive from
        // the raw event isn't available here, so instead expose the zoom-aware
        // math via a wrapper that reads pointer position off railEl directly —
        // OR (simpler, and what D-17 actually specifies): compute panPct from
        // current app.wordPos/zoom, then treat the incoming fraction as the
        // viewport fraction and apply the same (f + panPct/100) / zoom transform
        // attachRailScrub's own onScrub contract already delivers `f` as
        // 0..1-across-rail-width — apply pan/zoom before converting to word pos.
        const total = app.data.story.total_words;
        const playheadPctRaw = total ? (app.wordPos / total) * 100 : 0;
        const panPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
        const innerFrac = Math.max(0, Math.min(1, (viewportFraction + panPct / 100) / app.mobileTimelineZoom));
        const target = Math.round(innerFrac * total);
        setWordPos(target);
        return rollIndexAtOrBeforeWord(target); // new small helper — see Don't Hand-Roll
      },
      onScrubEnd: () => persistBookmarkNow(),
    });
  }
}
```

*(This is illustrative, not a literal patch — the planner should verify `attachRailScrub`'s `onScrub(fraction)` contract at `web/mobile-gestures.js:149-193` against whatever exact wiring is chosen; the key correctness property is that the pan/zoom transform happens inside the callback, not via a second pointer-listener bypass.)*

### Pattern 4: Incremental update tier — the mandatory early branch (D-18)

**What:** `cachePlaybackDomRefs()` and `updatePlaybackFrame()` both need a portrait-aware early branch. This is not optional polish — without it, the very first `render()` call in portrait mode will recurse.

```js
function cachePlaybackDomRefs() {
  app.dom = {
    // ...existing desktop refs, UNCHANGED...
  };
  if (app.layoutMode === "portrait") {
    app.dom.mobilePlayhead = document.querySelector(".mobile-rail .playhead");
    app.dom.mobileRailInner = document.querySelector(".mobile-rail-inner");
    app.dom.mobileChips = document.querySelector(".mobile-top-cluster");
    app.dom.mobileDockMeta = document.querySelector(".mobile-dock-meta");
    app.dom.mobileActiveMarker = document.querySelector(".mobile-roll-dot.active");
    app.dom.mobileSkyCameraLayer = document.querySelector(".mobile-sky-camera-layer");
  }
  app.carousel.visibleSlots = new Map(/* unchanged */);
}

function updatePlaybackFrame() {
  if (!app.data) return;
  if (app.layoutMode === "portrait") {
    updateMobilePortraitFrame();   // NEW — mirrors updatePlaythroughFrame's shape
    return;
  }
  if (!app.dom?.playhead) { render(); return; }   // desktop/landscape path, BYTE-IDENTICAL
  updateScrubberFrame();
  updateStatStripFrame();
  updatePlaybackControlsFrame();
  if (app.mode === "playthrough") updatePlaythroughFrame();
  else if (app.mode === "detail") updateDetailFrame();
  centerScrubber();
}
```

`updateMobilePortraitFrame()` mirrors `updatePlaythroughFrame`'s key-diffing pattern (`app.js:2641-2665`) — replace `.mobile-sky-camera-layer`'s children with `renderSkyCamera(...)` only when the scene/roll key changed, update chip text nodes directly, move the rail playhead/inner-transform via `style.transform`, and recompute cluster bins **only** on structural render / zoom change / rail resize (never per-frame) per D-18's explicit instruction.

### Pattern 5: Flyout surface stack with focus trap + back-gesture (D-16)

**What:** One shared stack (Settings, About, Help are mutually exclusive per the prototype's `openSettings`/`openInfo` toggle pattern in `prototype/app.jsx:230-243`). Each open pushes a history sentinel; `popstate` closes the topmost; backdrop tap closes; focus is trapped via `focusin` redirect + Tab-wrap, restored to the opening button on close.

```js
function openMobileSurface(kind, triggerEl) {
  closeMobileSurface(); // ensure exclusivity — mirrors prototype's toggle pattern
  app.mobileSurface = kind;       // "settings" | "info" | "help"
  app.mobileSurfaceOpener = triggerEl;
  history.pushState({ bcfMobileSurface: kind }, "");
  render();
  // focus-trap wiring happens inside the render pass, on the mounted surface node
}
function closeMobileSurface({ fromPopstate = false } = {}) {
  if (!app.mobileSurface) return;
  app.mobileSurface = null;
  if (!fromPopstate) history.back(); // consumes the sentinel we pushed
  const opener = app.mobileSurfaceOpener;
  app.mobileSurfaceOpener = null;
  render();
  opener?.focus?.();
}
window.addEventListener("popstate", (e) => {
  if (app.mobileSurface) closeMobileSurface({ fromPopstate: true });
});
```

This is genuinely new code — nothing in the prototype implements focus-trap or back-gesture handling (the prototype is a React demo with no keyboard/a11y concerns wired in), so there is no verbatim source to port here; only the *visual* flyout markup (`prototype/panels.jsx` `SettingsFlyout`/`InfoFlyout`/`HelpOverlay`) is reference material.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sky cinematic rendering at phone size | A mobile-specific SVG camera/scene renderer | `renderViewportFrame()` + `renderSkyCamera()`, called as-is | Both already handle arbitrary container sizing via `viewBox`/`preserveAspectRatio`; a duplicate would have to re-derive all of `viz-model.js`'s scene/animation math (motion blur, spotlight, beam, multi-grab merge) — hundreds of lines of physics-adjacent interpolation |
| "Most recent roll" / "roll at word position" lookups | A new mobile roll-index binary search | `lastRollAtWord(wordPos)` (`app.js:716`), extend with a small `rollIndexAtOrBeforeWord(wordPos)` helper only if an index (not object) is needed for haptic-per-roll-cross bookkeeping | `lastRollAtWord` already exists and is the exact semantic the gesture contract wants for double-tap; don't reintroduce the prototype's `activeRollAtWord`/`rollIndexAtOrBeforeWord` prototype-only names as a second implementation — wrap the existing linear scan if an index is needed, don't write a second lookup with different semantics |
| Cluster-binning at a given pixel density | A new mobile-specific bin-merge algorithm | `binRolls`/`finalizeBin`/`binSize` ported verbatim from `prototype/scrubber.jsx:17-48` | Already implements exactly MOBP-04's 5px-threshold / dominant-outcome / count-badge contract; it's ~30 lines with no app-state coupling, trivially portable |
| Word-position → mode/CP/chapter derivations | Any new "mobile" formatWords/chapterAtWord variant | `formatWords`, `chapterAtWord`, `cumulativeAt` (existing, `app.js:359, 706, 734`) | These are the shared model layer both desktop and mobile must read identically per the architecture's core invariant (§A.3 of `.planning/research/ARCHITECTURE.md`) |
| Preference read/write | A parallel `bcf:mobile:*` namespace or ad-hoc localStorage calls | Existing `store()`, `readStoredBoolean`, `readStoredChoice`, and the `window.__bcfMobile` setter bridge (`setTapToPause`, `setHaptics`, `setMobileTimelineZoom`, `markHelpSeen`, all already shipped in Phase 1, `app.js:2803-2820`) | Already versioned, already tested (`tests/test_mobile_plumbing.py::test_mobile_pref_setters_round_trip_across_reload`); a parallel path would violate the plan's explicit "don't fork the storage namespace" rule (§7) |
| Focus trap / dialog a11y | A hand-rolled `<dialog>` polyfill or third-party a11y library | Plain `focusin` redirect + Tab-key wrap inside the surface's own render pass (see Pattern 5) | No new dependency is warranted for a single-level, three-surface stack; native `<dialog>` isn't used elsewhere in this codebase and introducing it now would be an unrelated architectural change mid-phase |

**Key insight:** every one of this phase's "hard" problems (sky rendering, roll lookup, cluster binning, preference persistence) already has an existing, tested, or directly-portable implementation somewhere in this codebase or its prototype. The actual net-new code in this phase is thin: the portrait DOM shell, the gesture-callback wiring glue, the flyout focus-trap/back-gesture mechanics (which have no prior art here), and the two mandatory `render()`/`updatePlaybackFrame()` branch additions.

## Common Pitfalls

### Pitfall 1: Reusing `.app` or `.viewport` class names silently reintroduces the `100vh`/`min-height` bug this workstream already fixed once

**What goes wrong:** `.app` (`web/style.css:67-71`) sets `min-height: 100vh` and `.viewport` (`web/style.css:1134-1152`) sets `min-height: 460px`. Both are frozen desktop rules (§0.1.5/§0.1.6 — no edits). If `renderMobilePortrait()`'s root element or sky container reuses either class name for convenience (e.g. because the desktop markup already has the right `display:flex`/`position:relative` shape), the mobile DOM tree silently inherits these rules via CSS cascade — `100vh` on iOS Safari is exactly Pitfall 4 from `.planning/research/PITFALLS.md` (dynamic toolbar), and it would resurface here even though Phase 1's `mobile.css` already defines the correct `--mobile-vh: 100svh` primitive for this exact purpose.

**Why it happens:** class names are cheap to reuse and the desktop rule's *behavior* (fill available height, relative positioning for absolute children) is exactly what mobile also wants — but the specific unit choice (`vh` vs `svh`) is not shared, and CSS class reuse silently pulls in both.

**How to avoid:** give the portrait root and sky container **new** class names (e.g. `.mobile-app`, `.mobile-sky`) defined fresh in `web/mobile.css` using `var(--mobile-vh)` (already defined, inert, from Phase 1) instead of `100vh`. Never let a mobile element carry a desktop structural class name, even one that "happens to look right."

**Warning signs:** portrait layout looks correct in Chrome DevTools device emulation (which doesn't simulate the dynamic toolbar) but the dock is clipped or the sky overflows on a real iPhone with the address bar expanded.

### Pitfall 2: `updatePlaybackFrame()`'s desktop DOM-ref gate causes infinite recursion in portrait if the D-18 branch is missed

**What goes wrong:** `updatePlaybackFrame()` (`app.js:2589-2601`) starts with `if (!app.dom?.playhead) { render(); return; }`. `app.dom.playhead` is populated by `cachePlaybackDomRefs()` querying `#scrubber-playhead` — a desktop-only element ID that will never exist in `renderMobilePortrait()`'s DOM tree. `render()` itself calls `cachePlaybackDomRefs(); updatePlaybackFrame();` unconditionally right after mounting the shell (`app.js:919-920`). Without D-18's early portrait branch landing in `updatePlaybackFrame()` **before** this desktop-ref check, the very first portrait `render()` call will: mount the portrait DOM → call `updatePlaybackFrame()` → find no `#scrubber-playhead` → call `render()` again → mount again → call `updatePlaybackFrame()` again → … a synchronous, unbounded recursive loop that overflows the call stack immediately, before the user sees anything.

**Why it happens:** the existing gate was written when only one DOM shape (`renderAppShell`) ever existed; it silently assumes "no playhead found" means "DOM not mounted yet, try a full render" — a reasonable assumption until a second, permanently-playhead-less DOM shape (portrait) is introduced.

**How to avoid:** land the `updatePlaybackFrame()` early-return branch (`if (app.layoutMode === "portrait") { updateMobilePortraitFrame(); return; }`) in the *same commit* as the first `render()` D-12 branch — never land D-12 alone even for a quick visual check, since it will crash on the first playback tick (and `render()` itself calls `updatePlaybackFrame()` once even with playback stopped, so it crashes on load, not just during playback).

**Warning signs:** blank white screen / browser "page unresponsive" dialog / `RangeError: Maximum call stack size exceeded` in the console the instant the portrait branch is enabled, even before any gesture is attempted.

### Pitfall 3: `bcf:mode` value mismatch between the prototype's Settings segment and the live app's allow-list silently breaks reload-persistence

**What goes wrong:** `prototype/panels.jsx`'s `SettingsFlyout` View-mode segment uses options `[["playthrough","Playthrough"],["details","Details"]]` — value `"details"` (plural). The live `web/app.js` app object initializes `mode: readStoredChoice(LS_MODE, ["playthrough", "detail"], "playthrough")` (`app.js:110`) — singular `"detail"`, and `setMode(mode)` (`app.js:784-788`) does **not** validate against this allow-list (unlike `setRollLocation`, which does). If the ported Settings UI calls `setMode("details")` verbatim from the prototype's `Seg` value, the app renders correctly *this session* (the `app.mode === "playthrough" ? [...] : [...]` branch at `app.js:955` just falls to the else-branch for any non-"playthrough" string), but on the next reload `readStoredChoice` rejects `"details"` (not in `["playthrough","detail"]`) and silently resets to `"playthrough"` — the user's chosen mode does not survive reload, directly violating MOBP-05's "every preference survives reload" requirement, and it will not be obvious from a quick manual test (only surfaces after a real reload with mode set to "detail/details").

**Why it happens:** the prototype was written independently of the live app's existing `LS_MODE` allow-list and never reconciled; "details" reads naturally as an English word, so it's an easy value to port literally without checking the consuming allow-list.

**How to avoid:** the ported Settings segment's mode option must use value `"detail"` (matching the existing live allow-list exactly), with only the *label* text ("Details") taken from the prototype. Add an explicit assertion in the new Playwright test that sets mode via the Settings UI, reloads, and confirms the mode string read back from `localStorage.getItem("bcf:mode")` is exactly `"detail"`.

**Warning signs:** a reload-persistence test that only checks "does the UI still show detail mode selected" (re-derived from in-memory `app.mode` state that a fresh page load never had) rather than reading the actual stored string — that kind of test would pass even with this bug present, because a full page reload wasn't exercised.

### Pitfall 4: Porting the prototype's double-tap "snap to live edge" literally jumps to the end of the entire story, not to where the cinematic was last firing

**What goes wrong:** `prototype/app.jsx`'s `onSky.dblTap` (`app.jsx:177-183`) does `const lastRoll = data.rolls[data.rolls.length - 1]; scrubTo(lastRoll.wordPosition);` — literally the final roll of the whole 195-chapter dataset. The gesture contract's stated intent (`gesture-contract.html` §01: "Recovers from accidental scrubbing — returns to wherever the cinematic was last firing") and this Phase's own CONTEXT.md code_context ("double-tap → snap to last roll ≤ current word + resume") both describe a *local* recovery action relative to the current playhead, using the roll at-or-before `app.wordPos` — which is exactly what `lastRollAtWord(app.wordPos)` (`app.js:716`) already computes. Porting the prototype's literal implementation would make every double-tap teleport the reader to the very end of the story regardless of where they currently are — a jarring, clearly-wrong behavior that would likely be caught in manual testing, but is worth flagging explicitly since "port verbatim from the prototype" is this phase's general instruction and this is the one behavioral spot where verbatim-porting is actively wrong.

**Why it happens:** the prototype's demo dataset is small/short and its own "state" model has no distinct desktop precedent to check against; `data.rolls.at(-1)` reads as a reasonable stand-in for "the newest thing" in an isolated prototype but is semantically wrong once there's an existing `lastRollAtWord` function whose contract already means "live edge relative to current position."

**How to avoid:** implement double-tap as `setWordPos(lastRollAtWord(app.wordPos)?.word_position ?? app.wordPos)` followed by ensuring playback resumes (`if (!app.playing) togglePlayback()`), not by reading `data.rolls.at(-1)`.

**Warning signs:** any code review or test where double-tap in the middle of chapter 50 lands the reader at chapter 195.

### Pitfall 5: Reusing the desktop `sky-camera-layer` class name for the mobile wrapper works by accident, not by design — decide explicitly

**What goes wrong:** `updatePlaythroughFrame()` (`app.js:2641-2665`) looks up its sky-camera mount point via `app.dom.skyCameraLayer`, cached in `cachePlaybackDomRefs()` via `document.querySelector(".sky-camera-layer")` (`app.js:2575`). Since only one layout mode's DOM tree exists in `#root` at a time, if the mobile sky wrapper *also* used the literal class `sky-camera-layer`, the desktop-path `updatePlaythroughFrame()` would "accidentally" find and update it too — but D-18 explicitly specifies a *separate* portrait update path (`updateMobilePortraitFrame()`, not `updatePlaythroughFrame()`), so this accidental compatibility must not be relied upon or it creates exactly the kind of implicit coupling between mobile and desktop code the plan's §7 anti-pattern warning is about ("don't extract/share a component between mobile and desktop").

**How to avoid:** give the mobile sky-camera mount a distinct class (e.g. `.mobile-sky-camera-layer`), queried only by the new `cachePlaybackDomRefs()` portrait branch and updated only by `updateMobilePortraitFrame()`. Never let the desktop-path function (`updatePlaythroughFrame`) and the mobile-path function (`updateMobilePortraitFrame`) resolve to the same DOM node via a shared class name, even if it would "just work" today.

**Warning signs:** code review finds `updatePlaythroughFrame` or `updateMobilePortraitFrame` querying an ambiguous shared selector rather than a mode-specific one.

### Pitfall 6: Phase 1's `attachMobileGestureProbes` landscape wiring must survive this phase's changes untouched

See Pattern 2 above — this is restated here as a pitfall because it's easy to "clean up" `render()`'s mobile block while adding the portrait branch and inadvertently also touch/replace the landscape probe path, which Phase 3 (not Phase 2) owns. Verify `tests/test_mobile_plumbing.py`'s landscape-viewport assertions still pass unmodified after this phase's changes — that test file is a regression gate for work this phase must not touch.

## Code Examples

### `render()` — the D-12 branch (illustrative, exact code left to the planner/implementer)

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

  if (app.layoutMode === "portrait") {
    root.append(renderMobilePortrait());
  } else {
    root.append(renderAppShell()); // desktop AND landscape-fallback, UNCHANGED
  }

  cachePlaybackDomRefs();
  updatePlaybackFrame();

  if (app.layoutMode === "landscape") {
    root.append(el("div", { class: "mobile-gesture-probe", "aria-hidden": "true",
      style: "position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0;" }));
    attachMobileGestureProbes(); // UNCHANGED from Phase 1
  } else if (app.layoutMode === "portrait") {
    attachMobilePortraitGestures(); // NEW
  }
}
```

### `renderMobilePortrait()` — sky reuse skeleton

```js
function renderMobilePortrait() {
  const frame = playthroughFrameState();
  return el("div", { class: "mobile-app" },
    el("div", { class: "mobile-top-cluster" }, /* chips per Claude's Discretion */),
    el("div", { class: "mobile-sky" },
      renderViewportFrame(),                                   // FROZEN, called as-is
      el("div", { class: "mobile-sky-camera-layer" },
        frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,
      ),
    ),
    el("div", { class: "mobile-dock" },
      /* transport row: play/pause FAB, now-meta, speed cycle, gear (settings), info (D-14) */
      el("div", { class: "mobile-rail" }, /* MiniRail port, bins per binRolls() */),
      /* hint row */
    ),
  );
}
```

### Cluster-binning helpers (verbatim port, MOBP-04)

```js
// Verbatim from design/mobile-ux/prototype/scrubber.jsx:14-48
const MIN_DOT_SPACING_PX = 5;
function binRolls(rolls, totalWords, pxWidth, minPx = MIN_DOT_SPACING_PX) { /* ... */ }
function finalizeBin(bin) { /* ... */ }
function binSize(bin) { /* ... */ }
```

## State of the Art

No "old vs. current approach" delta applies here — this phase implements a net-new mobile surface, not a migration of an existing one. The one relevant "state of the art" note carried over from Phase 1's STACK.md research: Pointer Events (not Touch Events) and `matchMedia` (not `screen.orientation`) are the current, correct browser-platform choices, and this phase's gesture/orientation code inherits those choices from Phase 1 without needing to re-decide them.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `renderSkyCamera`'s `preserveAspectRatio="xMidYMid meet"` will look visually acceptable (if letterboxed) at real phone portrait aspect ratios, rather than needing a mobile-specific tighter crop/viewBox | Architecture Patterns, Pattern 1 | If letterboxing reads as "broken" rather than "intentional cinematic framing" on a real device, the Phase B gate reviewer (Dre) may require a mobile-specific `focusCameraViewRect` variant — this is exactly the kind of visual judgment call the real-device verification step exists to catch; flagged, not resolved, by this research |
| A2 | The exact `attachRailScrub`/`onScrub(fraction)` wiring shown in Pattern 3's code example correctly reconciles with `web/mobile-gestures.js`'s actual `fractionFromEvent` contract (`web/mobile-gestures.js:153-156`) | Architecture Patterns, Pattern 3 | If the planner's actual implementation diverges from this illustrative sketch, the zoom-aware transform must still happen inside the callback (not via a second raw-listener bypass) — the illustrative code is not meant to be copy-pasted verbatim, only to demonstrate the correct division of responsibility |

No other claims in this research are marked `[ASSUMED]` — all other findings are sourced from direct reads of this repository's own code (`web/app.js`, `web/style.css`, `web/mobile-gestures.js`, `web/mobile.css`, the prototype source) or from CONTEXT.md/PITFALLS.md/ARCHITECTURE.md/STACK.md, which are this project's own prior research artifacts, not external/unverified sources.

## Open Questions

1. **Does `renderSkyCamera`'s letterboxing at portrait phone aspect ratios need a mobile-specific viewBox adjustment, or is it acceptable as-is?**
   - What we know: the mechanism (`viewBox` + `preserveAspectRatio="xMidYMid meet"`) technically scales to any container; the visual result at a tall-narrow aspect will show empty space above/below the 1.6:1-aspect cinematic content.
   - What's unclear: whether this reads as acceptable "letterboxed cinematic" framing or as a bug, on a real device.
   - Recommendation: build the straightforward call-through first (Pattern 1); treat this explicitly as a Phase B gate review item alongside the mandatory real-iOS-Safari verification already required by the phase notes — do not pre-optimize a mobile-specific viewBox before seeing it on a real device.

2. **Should the mobile double-tap / swipe-step "roll lookup" reuse `lastRollAtWord` directly, or does it need a companion "roll index" helper for the haptic-per-roll-cross bookkeeping `attachSkyGestures`/`attachRailScrub` expect?**
   - What we know: `lastRollAtWord(wordPos)` returns a roll object, not an index; `attachRailScrub`'s `onScrub` contract expects the callback to return an index (or any value) so it can detect "did the roll change since the last move event" for haptic firing (`web/mobile-gestures.js:163,169-172`).
   - What's unclear: whether a numeric roll index needs to be exposed as a new small helper, or whether returning the roll object itself (and having the gesture module compare by reference/uid) is sufficient — `web/mobile-gestures.js`'s `attachRailScrub` code only checks `idx !== lastRollIdx`, so any comparable value (object reference is fine as long as it's stable across renders) would work without a new helper.
   - Recommendation: try returning the roll object directly from `lastRollAtWord`-style lookups first; only add a dedicated index helper if reference-stability across renders proves unreliable in testing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Playwright (Chromium) | Automated portrait Playwright tests, desktop smoke test | ✓ (already used in Phase 1 tests, `tests/test_desktop_smoke.py`, `tests/test_mobile_plumbing.py`) | project-pinned, unchanged this phase | — |
| Python venv (`/Users/dre/src/bcf-visualization/.venv`) | Running `pytest` — this worktree has no local `.venv` | ✓ (main checkout's venv, per phase notes) | unchanged | Run via `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest` from this worktree, not a local venv |
| Real iOS Safari device | MOBP-01's viewport-percentage acceptance criteria (dynamic toolbar behavior), rotation timing — emulation does not reproduce these (Pitfalls 3/4 in `.planning/research/PITFALLS.md`) | ✗ — flagged in STATE.md as "not confirmed" | — | None functional — this is a hard gate-review item Dre performs manually; Chrome DevTools device emulation is acceptable for iteration but explicitly insufficient for phase sign-off per the phase notes and PITFALLS.md's own "Looks Done But Isn't" checklist |

**Missing dependencies with no fallback:**
- Real iOS Safari device access for the Phase B gate review — already flagged as a project-level blocker in `.planning/workstreams/mobile-ux/STATE.md` ("Real iOS Safari device access has not been confirmed"). This phase's plan must include the real-device verification as an explicit gate step, not assume emulation suffices.

**Missing dependencies with fallback:**
- None beyond the above.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Playwright (Python), via `pytest` |
| Config file | none — plain pytest fixtures in `tests/conftest.py` + `tests/helpers/web_runtime_site.py` (Phase 1 pattern) |
| Quick run command | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_portrait.py -x` (new file, Phase 2) |
| Full suite command | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOBP-01 | Sky ~60% viewport, chips never overlap focal label, dock always visible | integration (Playwright, bounding-box assertions at PHONE_PORTRAIT and a 320px-width viewport) | `pytest tests/test_mobile_portrait.py::test_portrait_layout_proportions_and_chip_overlap -x` | ❌ Wave 0 |
| MOBP-02 | Tap/dbl-tap/swipe gesture contract, including tap-to-pause off no-op | integration (Playwright, simulated pointer events + `window.__bcfGestureStats`-style counters) | `pytest tests/test_mobile_portrait.py::test_sky_gesture_contract -x` | ❌ Wave 0 |
| MOBP-03 | Rail drag scrubs word position correctly at every zoom level incl. auto-pan | integration (Playwright, drag simulation at zoom 1/2/4/8) | `pytest tests/test_mobile_portrait.py::test_rail_scrub_zoom_aware -x` | ❌ Wave 0 |
| MOBP-04 | Cluster-binning at 1×, active roll separate diamond on top | unit (pure JS logic — could also be a small Node-less browser-context Playwright eval of `binRolls`) | `pytest tests/test_mobile_portrait.py::test_cluster_binning_at_1x -x` | ❌ Wave 0 |
| MOBP-05 | Settings/About/Help work, help auto-opens once, prefs persist across reload | integration (Playwright, reload + `localStorage` read-back — see Pitfall 3) | `pytest tests/test_mobile_portrait.py::test_settings_about_help_persist_across_reload -x` | ❌ Wave 0 |
| (regression) | Zero structural re-renders / no recursion during portrait playback | integration (Playwright, `window.__bcfRenderStats.structuralRenders` counter over N seconds of playback — mirrors Phase 1's `test_gestures_fire_exactly_once_without_structural_renders`) | `pytest tests/test_mobile_portrait.py::test_portrait_playback_has_no_recursive_renders -x` | ❌ Wave 0 |
| (regression) | Landscape probe wiring unaffected | integration (existing) | `pytest tests/test_mobile_plumbing.py -x` (must still pass unmodified) | ✅ exists |
| (gate) | Desktop byte-identical | integration (existing) | `pytest tests/test_desktop_smoke.py -x` | ✅ exists |

### Sampling Rate

- **Per task commit:** `pytest tests/test_mobile_portrait.py -x` (fast subset relevant to the task)
- **Per wave merge:** `pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py`
- **Phase gate:** Full suite green, plus the mandatory real-iOS-Safari manual verification (Environment Availability) and the §5 Phase B gate review with Dre, before `/gsd-verify-work`.

### Wave 0 Gaps

- [ ] `tests/test_mobile_portrait.py` — new file covering MOBP-01..05 and the two regression checks above
- [ ] Confirm `tests/helpers/web_runtime_site.py`'s existing `PHONE_PORTRAIT` viewport fixture (already used in `test_mobile_plumbing.py`) is reused rather than redefined
- [ ] No framework install needed — Playwright is already present from Phase 1

## Security Domain

`security_enforcement` is enabled (`.planning/config.json`: `security_asvs_level: 1`). This phase has no server/API/auth surface — it's entirely client-side rendering and interaction over already-loaded public story data, so most ASVS categories are not applicable. The one category worth an explicit check is input validation at the DOM/localStorage boundary, given the mode-value pitfall found above.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface in this app |
| V3 Session Management | no | No session/cookie surface |
| V4 Access Control | no | Single-user, no roles |
| V5 Input Validation | yes (narrow) | `readStoredChoice`'s existing allow-list pattern for any `localStorage`-sourced value (already the mechanism protecting `app.mode`/`app.onRollBehavior`/`app.rollLocation`); Pitfall 3 above is functionally an input-validation-boundary bug (an unvalidated write path, `setMode`, feeding a validated read path) — the fix is either validating `setMode`'s input against the allow-list (matching `setRollLocation`'s existing pattern) or ensuring the UI only ever passes allow-listed values. Recommend the former as defense-in-depth even though the immediate fix (Pitfall 3) is UI-side. |
| V6 Cryptography | no | No crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed/unexpected `localStorage` values from a prior app version or manual tampering silently corrupting `app.mode`/`app.onRollBehavior`/etc. | Tampering (low severity — client-only state, no server trust boundary) | Already mitigated by `readStoredChoice`'s allow-list pattern on read; extend the same discipline to `setMode` on write (see V5 above) for full defense-in-depth, though this is a low-severity, purely-cosmetic risk given there's no server to protect |
| `history.pushState`/`popstate` sentinel stack (D-16) growing stale if a programmatic close forgets to call `history.back()` | Denial of Service (very low severity — worst case is extra back-button presses needed to leave the page) | D-16's own design already specifies "programmatic close consumes its sentinel via `history.back()` so the history stack never grows stale" — implement exactly as specified; add a Playwright assertion that closing a flyout via each of {backdrop tap, back button, explicit close button} leaves `history.length` unchanged relative to before opening |

## Sources

### Primary (HIGH confidence — direct codebase reads this session)
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/web/app.js` (full render/update/model/mobile-section read) — source for every code-level finding, line numbers cited inline above
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/web/style.css` (`.app`, `.viewport`, `.viewport-frame`, `.sky-camera`, `.carousel-strip`, `.const-card`) — source for the sizing-assumption analysis in Pattern 1 and Pitfall 1
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/web/mobile-gestures.js` — source for the exact `attachSkyGestures`/`attachRailScrub` contracts referenced in Patterns 2/3
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/web/mobile.css` — source for the already-shipped, inert touch-action/safe-area/svh foundation classes
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/design/mobile-ux/prototype/{layouts,scrubber,panels,app}.jsx` — source for the DOM/behavior reference and the two divergences flagged in Pitfalls 3/4
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/web/viz-model.js` (`focusCameraViewRect`, `WORLD_STAGE_WIDTH/HEIGHT`) — source for the world-coordinate/viewBox mechanism in Pattern 1
- `/Users/dre/src/bcf-visualization/.claude/worktrees/bcf-mobile-ux-phase-2-d08bbc/tests/test_mobile_plumbing.py`, `tests/test_desktop_smoke.py` — source for existing Playwright conventions and the landscape-mode regression risk in Pitfall 6
- `.planning/workstreams/mobile-ux/phases/02-portrait-layout/02-CONTEXT.md`, `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md`, `.planning/workstreams/mobile-ux/REQUIREMENTS.md`, `.planning/workstreams/mobile-ux/STATE.md`, `design/mobile-ux/INTEGRATION_PLAN.md`, `design/mobile-ux/gesture-contract.html`, `.planning/research/{PITFALLS,ARCHITECTURE,STACK}.md` — this milestone's own prior research/decision artifacts, treated as authoritative project context, not external sources

### Secondary / Tertiary
None — this phase's research required no external web search; every question was resolvable by direct codebase inspection and this workstream's existing decision/research documents.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new stack decisions, verified against existing STACK.md and CLAUDE.md constraints
- Architecture: HIGH — every architectural claim (render() branching, updatePlaybackFrame gate, sky-camera viewBox mechanism, mode-value mismatch, double-tap semantics) is grounded in direct line-numbered reads of this repository's own code, not inference
- Pitfalls: HIGH — all six pitfalls are either directly observed code-level facts (1, 2, 3, 4, 5, 6) rather than speculative risk framing

**Research date:** 2026-07-26
**Valid until:** Until `web/app.js`'s render/update-frame structure or the prototype source changes materially — this is a brownfield-analysis research artifact tied to specific line numbers in a specific commit, not a time-decaying external-API research artifact. Re-verify line numbers if Phase 1 lands further changes before Phase 2 planning begins.
