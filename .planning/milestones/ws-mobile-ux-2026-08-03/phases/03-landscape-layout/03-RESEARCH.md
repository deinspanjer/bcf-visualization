# Phase 3: Landscape Layout - Research

**Researched:** 2026-08-01
**Domain:** Vanilla-JS mobile web layout (landscape phone), reusing an existing portrait implementation's gesture/state/surface-stack machinery
**Confidence:** HIGH — this phase is almost entirely codebase archaeology against a live, tested Phase 1/2 implementation, not new-library research. No new packages, frameworks, or external services are introduced.

## Summary

Phase 3 replaces the D-12 interim landscape fallback (`render()` still calling `renderAppShell()` for `layoutMode === "landscape"`, at `web/app.js:991`) with a real `renderMobileLandscape()` arm that mirrors the prototype's `LandscapeF`: sky at ~75% width, a right rail holding a field log (top 2/3) over a Settings/About dock (bottom 1/3), and an auto-hiding cinema-scrub pill. Everything this phase needs already exists in the codebase in portrait form — the sky region, the surface stack (Settings/About/Help with focus trap and back-gesture dismissal), the scrub math (`binRolls`/`panOffsetForPlayhead`/`mobileInnerFraction`), the gesture primitives (`attachSkyGestures`/`attachRailScrub`), and the field-log data seam (`recentRolls`). The work is disciplined reuse and generalization, not new invention.

Three places in `web/app.js` currently branch on the literal string `"portrait"` and will silently do nothing for landscape unless generalized: `render()`'s gesture-attach/focus-trap block (`app.js:1005-1015`), `cachePlaybackDomRefs()`'s mobile-ref caching (`app.js:2701`), and `updatePlaybackFrame()`'s dispatch (`app.js:2733`). All three must become "portrait or landscape" (or acquire a landscape counterpart) or the landscape surface will render once and then never receive gesture attachment, DOM-ref caching, or incremental frame updates — a subtle, easy-to-miss bug because nothing throws; the surface would just look inert.

The one genuinely novel piece is chrome auto-hide (MOBL-02): the prototype's own reference implementation resets its idle timer on `wordPos` changes, and `wordPos` changes on every `requestAnimationFrame` tick during playback — so a literal port of that effect would never actually hide anything while playing (the exact case D-28 targets). Production code must reset the timer from discrete gesture-callback events (tap/swipe/scrub), not from continuous playback state, and must NOT call `render()` to toggle it (that would tear down and reattach every gesture listener on every hide/reveal, violating D-18's single-render-tier discipline) — a `classList.toggle()` inside the existing incremental update function is correct.

**Primary recommendation:** Build `renderMobileLandscape()` as a structural sibling to `renderMobilePortrait()` that extracts the sky's common markup into one shared, layout-parameterized helper (D-35); generalize the three portrait-only branch points named above to cover landscape too; wire the cinema-scrub through `attachRailScrub` (not the prototype's bespoke pointer handler) so D-17's single-scrub-input-path rule holds; and implement the auto-hide timer as a small piece of `app`-scoped state (handle + `setTimeout`) reset from gesture callbacks and `togglePlayback`/rotation, mutated via `classList.toggle`, never via `render()`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Landscape layout structure (sky/rail split) | Browser / Client (vanilla JS render function) | CSS (`web/mobile.css`) | No server; `render()` dispatches to a pure-DOM-building function, same as every other view in this app |
| Field log content (rolls up to `wordPos`) | Browser / Client (`recentRolls()` model call) | — | Purely client-side; `app.data.story.rolls` is a pre-baked static JSON payload (`visualization_facts.json`), not fetched per-request |
| Chrome auto-hide timer | Browser / Client (`app`-scoped `setTimeout` handle) | — | Pure UI ephemeral state; never persisted, never server-driven |
| Rotation hand-off / state preservation | Browser / Client (`app.*` fields + full `render()` rebuild) | — | `app.layoutMode` is derived from `matchMedia`; all preserved fields (`wordPos`, `playing`, `speed`, `zoom`, prefs) already live on the one `app` object read by both layout renderers |
| Flyout dismissal (backdrop/focus-trap/back-gesture) | Browser / Client (`openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus`) | Browser History API (`history.pushState`/`popstate`) | Fully client-side; the History API is used only as a "current surface is open" sentinel, not for real navigation |
| Static data payload | Build-time artifact (`visualization_facts.json`) | CDN/Static hosting | Out of scope for this phase — Phase 1 already established this; landscape reads the same in-memory `app.data`, no new fetch |

No API/backend tier is involved anywhere in this phase; this is a 100%-client-side, single static-bundle app (per the project's `Web data single bundle` convention).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MOBL-01 | Landscape phone shows sky (~75% width) + right rail (field log top 2/3, settings/about dock bottom 1/3), reusing the existing field-log data path | `recentRolls()` seam (D-24) confirmed at `app.js:791`; prototype `LandscapeF`/`FieldLog` markup reference read in full; CSS split ratios confirmed in prototype `styles.css` `@media (orientation: landscape)` block |
| MOBL-02 | Chrome auto-hides after 4000ms idle; first sky tap reveals (no pause), second tap within window pauses; any sky/rail touch resets timer | `G.CHROME_AUTOHIDE = 4000` already defined in `web/mobile-gestures.js` (byte-identical, D-17); prototype's own auto-hide effect read and found to have a design flaw (resets on `wordPos`, which changes every playback frame) — documented as Pitfall 1 below with the correct fix |
| MOBL-03 | Rotation mid-playback swaps layouts without visible remount; word position/play state/speed/zoom/prefs survive | `onLayoutMaybeChanged()` (`app.js:2919-2933`) and the full `app.*` state object read; confirmed every named field is a plain `app.*` property untouched by a structural `render()` rebuild |
| MOBL-04 | Flyouts dismiss on backdrop tap, trap focus, close on mobile back gesture | Surface stack (`openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus`/`teardownMobileSurfaceFocusTrap`, `app.js:2991-3086`) is layout-agnostic already — confirmed it operates purely on `app.mobileSurface`/DOM queries, not on `app.layoutMode` — landscape reuses it wholesale per D-33 |

</phase_requirements>

## Standard Stack

No new libraries, frameworks, or npm packages for this phase. Per project `CLAUDE.md`, `web/` stays framework-free with zero build step; this phase is pure native-API reuse of what Phase 1/2 already installed conceptually (Pointer Events, `matchMedia`, `ResizeObserver`, native History API, `localStorage`).

### Core (already present, reused as-is)
| API | Source | Purpose | Why Standard |
|-----|--------|---------|--------------|
| `attachSkyGestures` / `attachRailScrub` | `web/mobile-gestures.js` (byte-identical since Phase 1, D-17) | Tap/double-tap/swipe on the sky; drag-to-scrub on a track element | Already the single gesture-input implementation; landscape reuses both functions unmodified — only the DOM element and the callback bodies passed to them change |
| `ResizeObserver` | Native browser API | Track the scrub track's live pixel width for zoom-aware bin computation | Already used by `attachMobilePortraitGestures`'s rail-width observer (`app.js:3941-3963`); the exact same coalesced-rAF pattern generalizes to the landscape cinema-scrub track |
| `history.pushState` / `popstate` | Native History API | Surface-stack (Settings/About/Help) dismissal via mobile back gesture | Already implemented, layout-agnostic (D-16); landscape reuses without changes |
| `setTimeout` / `clearTimeout` | Native | Chrome auto-hide idle timer (MOBL-02) | The only genuinely new piece of state this phase adds; no timer library needed for a single 4000ms window |

### Supporting
| API | Purpose | When to Use |
|-----|---------|-------------|
| `classList.toggle` | Auto-hide chrome visibility | Every auto-hide state change — never a structural `render()` call (see Pitfall 2) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Reusing `attachRailScrub` for the cinema-scrub | Porting the prototype's bespoke `CinemaScrub` pointer handler verbatim | The prototype's own pointer wiring inside `scrubber.jsx`'s `CinemaScrub` component duplicates `attachRailScrub`'s logic almost exactly (pointer capture, `fractionFromPointer`, `onScrub`/`onScrubEnd`). Porting it verbatim would create a second scrub-input implementation, violating D-17 and the project's no-parallel-implementations rule. Reuse `attachRailScrub` against the cinema-scrub's track element instead — explicitly sanctioned by CONTEXT.md's Claude's Discretion list. |
| `classList.toggle` for auto-hide | A CSS custom property + `render()`-driven re-render | A structural render tears down and reattaches every gesture listener (D-07 discipline) on every hide/reveal cycle — wasteful and risks the exact mid-gesture teardown race D-22 explicitly warns about for rotation. A direct DOM mutation on the cached `app.dom` ref (same pattern as `updateMobilePortraitFrame`) is correct and cheap. |

**Installation:** None. No `npm install` — nothing added to `web/`.

## Package Legitimacy Audit

**Not applicable.** This phase installs no external packages. `web/` remains dependency-free (no `package.json`, no bundler) per the frozen project constraint; verified again in Phase 2's freeze proof (`02-05-SUMMARY.md` D5: `os.walk` scan for `package.json`/`package-lock.json`/`yarn.lock`/`vite.config.js` found none — still true at the start of this phase since no `web/` dependency file exists in this worktree).

## Architecture Patterns

### System Architecture Diagram

```
Orientation change / resize
        │
        ▼
matchMedia listeners (MOBILE_MQ, PORTRAIT_MQ) ── window "orientationchange"
        │
        ▼
onLayoutMaybeChanged()  (rAF-coalesced)
        │  detectLayoutMode() → "desktop" | "portrait" | "landscape"
        ▼
   app.layoutMode = next
        │
        ▼
      render()  ◄────────────────────────────────────────────┐
        │                                                      │
        ├─ app.layoutMode === "portrait"  → renderMobilePortrait()
        ├─ app.layoutMode === "landscape" → renderMobileLandscape()  [NEW, Phase 3]
        └─ else                           → renderAppShell()  (frozen desktop)
        │
        ▼
  cachePlaybackDomRefs()   (must branch: portrait refs vs landscape refs)
        │
        ▼
  updatePlaybackFrame()
        │
        ├─ layoutMode === "portrait"  → updateMobilePortraitFrame()   (existing)
        ├─ layoutMode === "landscape" → updateMobileLandscapeFrame()  [NEW, Phase 3]
        └─ else                       → desktop incremental updates
        │
        ▼
  Gesture attach (only for portrait|landscape, NOT desktop):
        attachMobileGestureProbes()          (Phase 1 diagnostic — untouched)
        attachMobileGestures()               [renamed/generalized from
                                               attachMobilePortraitGestures, D-34]
            ├─ portrait:  sky = .mobile-sky, scrub track = .mobile-rail
            └─ landscape: sky = .mobile-sky (shared, D-35), scrub track =
                          the cinema-scrub's track element
        Surface-stack focus trap re-attach (openMobileSurface/closeMobileSurface —
            ALREADY layout-agnostic; only the render()-side gating that calls
            trapMobileSurfaceFocus needs to stop being portrait-only, see
            Pitfall 3)
        │
        ▼
  User interaction (tap / swipe / drag / Settings / rotation)
        │
        ├─ setWordPos() / togglePlayback() → app.* mutation → updatePlaybackFrame()
        │   (incremental — NO structural render, D-18)
        │
        └─ openMobileSurface()/closeMobileSurface()/onLayoutMaybeChanged()
            → app.* mutation → render()  (full rebuild — sanctioned cases only)
```

### Recommended Project Structure

No new files. Everything lands in the existing `// ── Mobile UX ──` section of `web/app.js` (grouped near the Phase 2 portrait code, per the project's own convention) and in `web/mobile.css` behind the same mobile media query block Phase 1/2 established.

```
web/
├── app.js          # renderMobileLandscape(), updateMobileLandscapeFrame(),
│                    # generalized attachMobileGestures(), auto-hide timer
│                    # helpers — appended to the existing Mobile UX section
├── mobile.css       # landscape layout rules added to the existing
│                    # @media (max-width: 900px), (orientation: portrait)...
│                    # block; body scroll-lock un-nested (D-32)
├── mobile-gestures.js  # UNCHANGED (D-17) — attachSkyGestures/attachRailScrub
│                        # reused as-is, no new exported hooks
└── style.css        # UNCHANGED — frozen desktop CSS (§0.1.5)
```

### Pattern 1: One shared sky helper, wrapped per layout (D-35, answers planner question 1)

**What:** `renderMobilePortrait()`'s sky region (`app.js:3348-3370`) is:
```js
el("div", { class: "mobile-sky mobile-sky-surface" },
  renderViewportFrame(),                                   // frozen §0.2 read-only
  el("div", { class: "mobile-sky-camera-layer" },
    frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,  // frozen §0.2
  ),
  renderMobileFocalLabel(frame),                            // mobile-only, layout-agnostic
  renderMobileSkyTapHint(),                                 // mobile-only, layout-agnostic
  app.mobileSurface === "help" ? renderMobileHelpOverlay() : null,
  renderMobileSurface(),                                    // Settings/About flyout mount point
)
```
Every piece here is **common** to both layouts: the viewport-frame corners, the camera layer, the focal label, the tap hint, and the Settings/About/Help mount points (D-33 explicitly reuses the D-19 "mount inside `.mobile-sky`" convention for landscape too). Only the **outer wrapper's flex sizing** differs — `flex: 0 1 60%` (portrait, vertical stack) vs. a horizontal `flex: 1 1 auto` sibling next to the rail at ~75% width (landscape). The top-cluster chips also differ slightly in content (portrait shows word count in the chip text; the prototype's landscape chip omits it — `CH {num}` only, no word count) but are otherwise the same component.

**Concrete seam:** extract a `renderMobileSkyRegion(frame)` function containing exactly the block above (viewport frame → camera layer → focal label → tap hint → help overlay → surface mount), called identically by both `renderMobilePortrait()` and `renderMobileLandscape()`. Each caller wraps it in its own outer container with layout-specific CSS class (`mobile-sky` class stays the constant hook both `attachMobileGestures` and CSS key off; add a second class like `mobile-sky--landscape` only if landscape-specific sizing can't be expressed as a sibling-flex rule on a shared class). The landscape-only top-chip cluster and the auto-hide cinema-scrub are NOT part of this shared helper — they are landscape-specific siblings/overlays rendered by `renderMobileLandscape()` around the shared sky call, matching how the prototype's `LandscapeF` wraps its own `<Sky>` + `.top-cluster.landscape-only` + `<CinemaScrub>` inside one relatively-positioned flex child (`layouts.jsx:56-86`).

**When to use:** Any time sky markup changes in the future (camera layer, focal label, tap hint), edit it once in the shared helper — never duplicate it a second time (this is the exact justification D-35 uses: "duplicating would mean fixing the tap hint, focal label and camera layer twice").

### Pattern 2: Generalizing `attachMobilePortraitGestures` → `attachMobileGestures` (D-34, answers planner question 2)

**What differs between portrait and landscape attachment**, confirmed by reading both `attachMobilePortraitGestures` (`app.js:3852-3964`) and the prototype's landscape scrub reference (`scrubber.jsx` `CinemaScrub`, `layouts.jsx` `LandscapeF`):

| Aspect | Portrait | Landscape |
|--------|----------|-----------|
| Sky gesture surface | `document.querySelector(".mobile-sky")` | Same selector — shared per D-35 (Pattern 1) |
| Sky `onTap` callback body | `if (!app.tapToPause) return; togglePlayback();` | Must additionally handle D-30's reveal-vs-pause branch: `if (chrome is hidden) { reveal; return; }` **before** the tap-to-pause check — reveal always happens regardless of the `tapToPause` preference |
| Scrub-drag surface | `document.querySelector(".mobile-rail")` (the bottom-dock mini-rail) | The cinema-scrub's own track element (a **different**, differently-styled and differently-positioned DOM node — floating over the sky, not in a bottom dock) — **not** the landscape `.rail` sidebar, which is the field-log+dock container and is not a scrub-drag surface at all. Do not conflate the two "rail" words — the prototype itself uses `.rail` for the sidebar and `.scrub-track`/`.cinema-scrub` for the drag surface. |
| `onScrub`/`onScrubEnd` callback bodies | Identical math (`panOffsetForPlayhead`, `mobileInnerFraction`, frozen auto-pan-capture-on-pointerdown fix) | **Identical** — same math, same `app.mobileScrubPanPct` freeze-on-drag-start pattern (the real device-found monotonicity fix from Phase 2, `ed59087`) applies equally; only the queried element differs |
| ResizeObserver target | `.mobile-rail` | The cinema-scrub's track element | Generalizes directly — same coalesced-rAF callback shape, only the observed element and the "what gets `replaceChildren`'d" target (rolls lane vs. cinema-scrub bins) differ |
| Teardown slots | `app.mobileSkyTeardown`, `app.mobileRailTeardown`, `app.mobileRailResizeObserver` | Same three slots, reused as-is — **do not** add a fourth `mobileLandscapeXTeardown` slot; that would be exactly the "parallel teardown logic" D-34 forbids. Naming can stay generic (`mobileScrubTeardown` instead of `mobileRailTeardown` if renaming for clarity, but a rename is optional — Claude's Discretion) |
| Auto-hide timer wiring | N/A (no auto-hide in portrait) | New: reset the idle timer inside `onSwipeStep`/`onSwipeEnd`/`onScrub`/`onScrubEnd` callback bodies (see Pattern 3) |

**Answer:** the ResizeObserver logic generalizes almost verbatim — same shape, different queried element and different "what to rebuild" target. The ONE hard branch point is the `onTap` callback body (reveal-vs-pause semantics only exist in landscape) and which element is queried for the scrub surface. Structure `attachMobileGestures()` as:
```js
function attachMobileGestures() {
  // teardown block: IDENTICAL for both layouts, runs unconditionally first
  // (mobileSkyTeardown / mobileRailTeardown / mobileRailResizeObserver / mobileScrubPanPct reset)
  if (app.mobileSurface) return;   // shared guard, unchanged

  const skyEl = document.querySelector(".mobile-sky");         // shared
  const scrubEl = app.layoutMode === "landscape"
    ? document.querySelector(".mobile-cinema-scrub-track")     // new landscape selector
    : document.querySelector(".mobile-rail");                  // existing portrait selector

  // attachSkyGestures(skyEl, { onTap: ..., onDoubleTap: ..., onSwipeStep: ..., onSwipeEnd: ... })
  //   onTap branches once, at the top, on app.layoutMode === "landscape" && app.chromeHidden
  // attachRailScrub(scrubEl, { onScrub: ..., onScrubEnd: ... })  — same callback bodies for both

  // ResizeObserver — same shape, observes scrubEl, rebuilds whichever
  // "rolls lane" markup the current layout renders
}
```

### Pattern 3: Field log incremental update without a second update path (D-26, answers planner question 3)

`cachePlaybackDomRefs()` (`app.js:2680-2724`) and `updatePlaybackFrame()` (`app.js:2726-2747`) both currently gate their mobile branch on the literal string `"portrait"`. There is no landscape branch today because landscape has always rendered `renderAppShell()` (desktop markup, no mobile refs needed). Once `renderMobileLandscape()` exists, both functions need a landscape counterpart — **this is not optional generalization, it's a hard requirement**, or the field log will render once at mount and then never update as `wordPos` advances.

**Concrete plan:**
1. In `cachePlaybackDomRefs()`, change `if (app.layoutMode === "portrait") { ...portrait-only refs... }` to branch a second time (or use `app.layoutMode !== "desktop"` for anything truly shared, then a nested branch for layout-specific refs). Add landscape-only refs: `app.dom.mobileFieldLogList`, `app.dom.mobileFieldLogLive`, `app.dom.mobileFieldLogHeader` (the "N of total" count), `app.dom.mobileCinemaScrubTrack`, `app.dom.mobileCinemaScrubThumb`, `app.dom.mobileCinemaScrubFab`, matching the naming convention of the existing `mobileDockMeta`/`mobileDockTitle` refs.
2. In `updatePlaybackFrame()`, add a landscape branch mirroring the portrait one exactly:
   ```js
   if (app.layoutMode === "portrait") { updateMobilePortraitFrame(); return; }
   if (app.layoutMode === "landscape") { updateMobileLandscapeFrame(); return; }
   ```
   (The early-return-before-the-desktop-playhead-gate ordering constraint documented in the existing comment at `app.js:2728-2732` — "portrait has no `#scrubber-playhead`... this early return MUST land before the `!app.dom?.playhead` gate" — applies identically to landscape, which also has no `#scrubber-playhead`.)
3. `updateMobileLandscapeFrame()` follows the **exact same memoized-key pattern** desktop's `updatePlaythroughFrame()` already uses for its field log (`app.js:2800-2810`, the `narrativeKey`/`app.frameKeys.narrative` pair) and that portrait's `updateMobilePortraitFrame()` uses for the sky camera (`skyCameraKey`/`app.frameKeys.skyCamera`): compute a cheap string key from `(recentRolls(app.wordPos, N))`'s identity-relevant fields (e.g., the live roll's `uid` plus the visible recent-rolls' `uid`s joined), compare against a new `app.frameKeys.mobileFieldLog` (or similar) field, and only call `app.dom.mobileFieldLogList.replaceChildren(...)` when the key changed. This is "the existing incremental tier" — not a literal second call into `updateMobilePortraitFrame()` (which has nothing to do with a field log) but the same *pattern*, applied to a new DOM target. D-26 says "rides the existing incremental tier (D-18) rather than adding one" — the tier is the architecture (one `updatePlaybackFrame()` dispatch → one incremental-diff function per layout, no separate rAF loop, no second render path), not a shared function body.
4. `recentRolls(wordPos, count)` (`app.js:791`, D-24's locked seam) is the only model call needed — call it directly from `updateMobileLandscapeFrame()`/the structural `renderMobileLandscape()`, exactly as prescribed. Never call `renderNarrativeReadout`/`renderRecentRolls` (§0.2 frozen, desktop-sized).

### Pattern 4: Auto-hide idle timer — where it lives and what resets it (answers planner question 4)

**Where it lives:** a new `app`-scoped field, e.g. `app.mobileChromeHideTimer` (the `setTimeout` handle) alongside the existing `app.chromeHidden` boolean (already reserved on the `app` object since Phase 1/2 — `app.js:131` — unused until now). Store the handle on `app`, not `app.dom` (which `render()` blanks on every structural rebuild) and not a module-level closure variable (which would survive a landscape→portrait→landscape round-trip incorrectly if not explicitly cleared) — this matches the exact reasoning already documented for `app.mobileSurfaceFocusTrapTeardown` ("lives on `app` (not `app.dom`, which render() resets) so it survives to be invoked defensively before the next surface mounts").

**Lifecycle (D-07 teardown discipline, generalized to a timer instead of an event listener):**
- **Start/reset:** call a `resetChromeHideTimer()` helper that does `clearTimeout(app.mobileChromeHideTimer); app.mobileChromeHideTimer = null;` then, only if `app.layoutMode === "landscape" && app.playing` (D-28), sets a new `setTimeout` that sets `app.chromeHidden = true` and applies the DOM mutation directly (`classList.add("is-hidden")` on the cached cinema-scrub ref — never `render()`).
- **Reset triggers ("any sky or rail touch resets the timer," MOBL-02):** call `resetChromeHideTimer()` from inside the gesture callback bodies already wired in `attachMobileGestures()` — `onTap` (after handling reveal), `onDoubleTap`, `onSwipeStep`, `onSwipeEnd`, `onScrub`, `onScrubEnd`. This is the only way to satisfy "any touch resets it" **without** adding a second raw pointer listener outside the existing gesture module (which would violate D-17's single-input-path spirit and `mobile-gestures.js`'s byte-identical constraint — that file cannot gain a new `onDown` hook).
- **Also reset/restarted (not from a touch) at:** `togglePlayback()` transitioning to `playing = true` (starts the window), transitioning to `playing = false` (D-28: pausing reveals chrome and stops the timer — call `clearTimeout` and force `app.chromeHidden = false`), and `onLayoutMaybeChanged()`'s landscape-entry path (D-31: "arrives with chrome visible and the idle timer started" — force `app.chromeHidden = false` then call `resetChromeHideTimer()` after the `render()` that mounts the landscape DOM, since the ref it needs isn't cached until `cachePlaybackDomRefs()` runs).
- **Teardown (prevents leaking across renders/layout changes):** `clearTimeout` at the top of `attachMobileGestures()`'s unconditional teardown block (same place `mobileSkyTeardown`/`mobileRailTeardown` are torn down) — this covers both a structural re-render within landscape (e.g., a Settings toggle) and a layout transition away from landscape (portrait/desktop never re-attach `attachMobileGestures()`'s landscape branch, so a stale timer must not survive into the new layout).
- **Do NOT** put the reset in `updateMobileLandscapeFrame()` or gate it on a `wordPos` comparison — see Pitfall 1.

### Pattern 5: Cinema-scrub reuses `attachRailScrub`, not a bespoke pointer handler

The prototype's `CinemaScrub` React component (`scrubber.jsx:200-280`) wires its own `pointerdown`/`pointermove`/`pointerup`/`pointercancel` listeners directly, duplicating `attachRailScrub`'s logic (pointer capture, `fractionFromPointer`, `onScrub`/`onScrubEnd` callback shape) almost line-for-line. This is a React-prototype artifact (it needs its own `useEffect`-scoped listener because it's a distinct component instance), not a signal to duplicate in production. Call `window.attachRailScrub(cinemaScrubTrackEl, { onScrub, onScrubEnd })` — identical function, identical callback bodies to the portrait rail's — against whichever DOM element is the cinema-scrub's track. This keeps `web/mobile-gestures.js` as the single scrub-input implementation (D-17) and is explicitly the option CONTEXT.md's Claude's Discretion list anticipates ("whether the cinema-scrub reuses the portrait mini-rail's binning/pan helpers directly or wraps them").

### Anti-Patterns to Avoid
- **A second `updateMobileLandscapeFrame`-equivalent rAF loop:** there is exactly one incremental-update dispatch point (`updatePlaybackFrame()`), called from exactly one rAF-driven playback tick. Landscape's frame updates must be a branch inside that existing dispatch, never a second `requestAnimationFrame` loop.
- **A landscape-specific `MOBILE_LAYOUT_QUERY` variant or a raw width check:** D-06/D-36 already lock `detectLayoutMode()` as the single source of truth; landscape is simply `MOBILE_MQ.matches && !PORTRAIT_MQ.matches`. Never hand-roll a second width comparison anywhere in the landscape code.
- **Calling `render()` to toggle chrome visibility:** breaks D-18 and D-22 (an in-flight drag must survive a rotation without being torn down; a full render on every auto-hide tick would make that impossible to reason about, and would fire 4000ms after every idle moment during ordinary playback, causing spurious re-attachment of every gesture listener).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Cinema-scrub drag-to-scrub | A second pointer-handling implementation (porting the prototype's `CinemaScrub` internal listeners) | `window.attachRailScrub()` (existing, `web/mobile-gestures.js`) | Same math already implemented and device-tested (the Phase 2 auto-pan-freeze fix, `ed59087`, applies here too); a second implementation would need to independently rediscover that same monotonicity bug |
| Landscape Settings/About dismiss + focus trap + back-gesture | A bespoke landscape flyout anchor scheme | The existing `openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus` stack (`app.js:2991-3086`), mounted inside `.mobile-sky` per D-33 | Already implemented, already device-hardened against exactly the failure modes a new implementation would rediscover (Phase 2's defects #2 and #3: dock buttons painting through a mis-anchored panel, and a backdrop that stopped spanning the dock) |
| Cluster-binning for the cinema-scrub's roll markers | A new binning algorithm for the landscape scrub track | `binRolls`/`finalizeBin`/`binSize` (`app.js:3226-3259`, already generic over any `pxWidth`) | Same algorithm, same live-schema field names (`word_position`/`outcome`) — just called with the cinema-scrub track's width instead of the mini-rail's |
| Landscape Settings/About/toggle-playback button wiring | New click handlers per landscape button | The existing module-level `data-action` click-delegation listener (`app.js:3970-4015`) — already handles `toggle-playback`, `mobile-open-settings`, `mobile-open-info`, `mobile-open-help`, `mobile-close-surface` | This listener is attached once at module load (`document.body.addEventListener`), not per-render, and is layout-agnostic; landscape buttons need only the matching `data-action` attribute, no new JS |
| "Is any touch happening" detection for auto-hide | A parallel raw `pointerdown` listener on the sky/rail elements | Reset calls threaded into the existing gesture callbacks (`onTap`/`onSwipeStep`/`onSwipeEnd`/`onScrub`/`onScrubEnd`) | `web/mobile-gestures.js` must stay byte-identical (D-17); it cannot gain a new `onDown` hook, so the reset must happen from the *callback* side in `app.js`, not the *listener* side |

**Key insight:** every piece of machinery this phase needs to build from scratch is the auto-hide timer and the `renderMobileLandscape()`/`updateMobileLandscapeFrame()` structural/incremental functions themselves. Everything else — gestures, scrub math, binning, the surface stack, the data seam — is Phase 1/2 code that already exists, is already tested, and in two cases (auto-pan freeze, flyout anchoring) already survived a real-device debugging cycle. The risk in this phase is re-litigating solved problems, not solving new ones.

## Common Pitfalls

### Pitfall 1: Porting the prototype's auto-hide effect verbatim breaks it entirely
**What goes wrong:** The prototype's own reference implementation (`design/mobile-ux/prototype/app.jsx:138-142`) resets its `setTimeout` on a dependency array of `[isLandscape, playing, wordPos]`. But `wordPos` is set via `setWordPos()` on **every single `requestAnimationFrame` tick** during playback (`app.jsx:109-129`, the animation-loop effect calls `setWordPos(next)` every frame). A React effect keyed on `wordPos` therefore tears down and reschedules its `setTimeout` roughly 60 times per second during ordinary playback — the 4000ms timer can never survive long enough to fire. Chrome would never actually auto-hide while playing, which is the literal opposite of D-28's stated intent ("the idle timer runs only during playback").
**Why it happens:** In the prototype this is invisible because `wordPos` is treated as a generic "something changed" signal, conflating "the playhead advanced" (happens constantly, every frame) with "the user touched something" (the actual definition of "idle" this feature needs).
**How to avoid:** Reset the timer only from discrete gesture-callback events (Pattern 3/4 above), never from a `wordPos`-changed check and never from inside the per-frame `updateMobileLandscapeFrame()` incremental update.
**Warning signs:** If a manual QA pass shows the cinema-scrub never fades out during unattended playback, this is the first thing to check.

### Pitfall 2: Three portrait-only branch points will silently no-op for landscape (answers planner question 5, and generally)
**What goes wrong:** `render()`'s gesture-attach/focus-trap block (`app.js:1005-1015`), `cachePlaybackDomRefs()` (`app.js:2701`), and `updatePlaybackFrame()`'s dispatch (`app.js:2733`) all currently test `app.layoutMode === "portrait"` literally. Landscape never took this path before (it always rendered the desktop shell), so nothing is broken today — but `renderMobileLandscape()` will mount DOM that these three functions never look at unless each is generalized. The failure mode is silent: the landscape surface renders once (via the plain `render()` call inside `onLayoutMaybeChanged`), then never receives a gesture listener, never gets its DOM refs cached, and never receives an incremental frame update — it looks static/dead, not broken, which is easy to miss in a quick visual check.
**Why it happens:** These three checks were written when landscape had no mobile DOM to look at; the literal string comparison was correct at the time it was written and has no compile-time signal that it needs revisiting.
**How to avoid:** Grep for `layoutMode === "portrait"` across `app.js` before considering this phase's core render/update wiring done, and confirm each site either becomes `layoutMode !== "desktop"` (for logic truly shared across both mobile layouts) or gains an explicit landscape branch (for logic that differs).
**Warning signs:** Landscape renders correctly on first paint but gestures do nothing, the field log never updates as playback advances, or a structural re-render (e.g. opening Settings) loses gesture responsiveness.

### Pitfall 3: `render()`'s focus-trap re-attach is currently gated the same way — a flyout opened in landscape would trap focus nowhere
**What goes wrong:** The exact same `if (app.layoutMode === "portrait")` block in `render()` (`app.js:1010-1014`) also owns the D-16 focus-trap re-attach (`trapMobileSurfaceFocus`/`teardownMobileSurfaceFocusTrap`). If only the gesture-attach call is generalized and this sibling logic is missed, landscape's Settings/About/Help flyouts would open and render correctly but never trap keyboard focus — an accessibility regression that MOBL-04 explicitly requires ("keep focus trapped while open").
**Why it happens:** Both pieces of logic live in the same `if` block; it's easy to move/generalize one call and forget the other sits right next to it.
**How to avoid:** When generalizing this block, change the whole `if (app.layoutMode === "portrait")` guard to `if (app.layoutMode !== "desktop")` in one edit, not two separate edits to the gesture-attach and focus-trap lines individually.

### Pitfall 4: The `@media (orientation: portrait)` scoping D-32 removes has no other dependents in `web/mobile.css` — but landscape's own new CSS must not accidentally re-introduce portrait-only scoping elsewhere
**What goes wrong:** Confirmed by full-file inspection: `web/mobile.css` currently has exactly one `@media (orientation: portrait)` nested block (the body scroll-lock at line 29, the one D-32 explicitly targets) and no other rule in the file is scoped to portrait specifically — all other rules (`.mobile-sky`, `.mobile-dock`, etc.) are already inside only the outer `@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px)` block, which covers both mobile orientations. `web/style.css`'s narrow-viewport rules (`@media (max-width: 1100px)`, `@media (max-width: 640px)`) are frozen desktop rules that, after this phase, become unreachable at any viewport landscape mobile can occupy (since landscape ≤900px now renders `renderMobileLandscape()`, never `renderAppShell()`) — this is expected and requires no action; those rules remain live only for genuine desktop windows narrowed between 901–1100px, which is outside the mobile breakpoint entirely.
**Why it happens:** N/A — this is a confirmed-safe finding, not an active bug. Recorded so the planner doesn't spend a task re-verifying it.
**How to avoid:** When adding new landscape-specific CSS (sky/rail split, cinema-scrub, dock), keep it inside the existing outer mobile media-query block; do not add a fresh `@media (orientation: landscape)` nested block unless a rule genuinely needs to differ between portrait and landscape (the sky/dock flex split does — see Pattern 1 — but that's a legitimate, intentional per-orientation rule, structurally identical in kind to the one D-32 removes, not a repeat of the same mistake).

### Pitfall 5: iOS Safari's swipe-back gesture has a documented history of not firing `popstate`
**What goes wrong:** WebKit bug 248303 documents a regression (iOS 16 era) where the OS-level edge-swipe-to-go-back gesture did not fire a `popstate` event, which is the sole mechanism `closeMobileSurface`/D-16 relies on for "the mobile back gesture dismisses instead of leaving the app" (MOBL-04's literal wording). Phase 2's real-device iOS Safari 18.5 pass exercised and confirmed the surface-stack's back-gesture dismissal working (per `02-05-SUMMARY.md`'s device-pass notes — no back-gesture defect was reported among the four found), so this is very likely resolved on current iOS, but it was tested against **portrait** flyouts only.
**Why it happens:** WebKit-specific `pushState`/`popstate` timing quirks around user-gesture-triggered navigation are a known historical fragile area, not fully documented as permanently fixed.
**How to avoid:** Since D-33 reuses the identical `openMobileSurface`/`closeMobileSurface` mechanism unmodified for landscape, no new code risk is introduced — but explicitly re-exercise the back-gesture dismissal during the Phase 3 real-device gate pass (D-23), not just the backdrop-tap and close-button routes, since this is the one MOBL-04 behavior that cannot be fully trusted from portrait's prior verification alone (different screen orientation, different Safari chrome layout around the content area).
**Warning signs:** A flyout that opens fine in landscape but doesn't close on an edge-swipe gesture on a real iPhone even though the same swipe correctly dismisses it in portrait.

### Pitfall 6: `attachRailScrub`'s `fractionFromPointer`-equivalent math assumes a horizontally-oriented track — confirm the cinema-scrub track element has a real measured width before first paint
**What goes wrong:** The Phase 2 device-found monotonicity bug (`ed59087`, fixed by freezing `app.mobileScrubPanPct` at drag-start) depended on the rail's `ResizeObserver`-reported width being correct. The cinema-scrub track is a narrower, floating, auto-hiding pill (per prototype CSS, positioned `absolute; left:12px; right:12px; bottom:12px` inside the sky) rather than a full-width dock element — its initial width before the first `ResizeObserver` callback fires needs a reasonable fallback default (the existing `app.mobileRailWidth: 350` default may not be appropriate for a narrower cinema-scrub track; the prototype's own `CinemaScrub` uses `useState(200)` as its fallback, half of the mini-rail's).
**How to avoid:** If reusing the shared `app.mobileRailWidth` field for both layouts (Claude's Discretion — see Architecture Patterns), consider whether the different natural widths of the two elements make the shared-field's stale-value fallback (from the previous layout, immediately after a rotation and before the new `ResizeObserver` fires) visually wrong for one frame. A cheap mitigation: reset the field to a layout-appropriate default inside `renderMobileLandscape()`'s structural build (mirroring `recomputeMobileRailBins()`'s existing call site discipline), not just relying on the stale value from the prior layout persisting harmlessly.

## Code Examples

### Verified patterns from the existing codebase (all HIGH confidence, direct inspection)

**The `recentRolls` seam (D-24) — the only field-log data call needed:**
```js
// Source: web/app.js:791-798 (frozen §0.2-stable helper, not itself a §0.2
// render function, so it is directly callable — never renderNarrativeReadout
// or renderRecentRolls, which ARE frozen render functions with desktop sizing)
function recentRolls(wordPos, count = 10) {
  const rows = [];
  for (let i = app.data.story.rolls.length - 1; i >= 0 && rows.length < count; i -= 1) {
    const roll = app.data.story.rolls[i];
    if (roll.word_position <= wordPos) rows.push(roll);
  }
  return rows;
}
```

**The incremental-diff pattern to replicate for the landscape field log:**
```js
// Source: web/app.js:2800-2810 — desktop's own field-log incremental update,
// the pattern D-26/Pattern 3 above generalizes for the landscape rail
const narrativeRollUid = frame.firing ? (frame.lastRoll?.uid || "none") : "none";
const recentRollUid = frame.lastRoll?.uid || "none";
const narrativeKey = app.fieldLogHidden
  ? "hidden"
  : `${frame.chapter.chapter_num}|${narrativeRollUid}|${recentRollUid}`;
if (app.dom.narrativeMount && app.frameKeys.narrative !== narrativeKey) {
  app.dom.narrativeMount.replaceChildren(
    ...(!app.fieldLogHidden ? [renderNarrativeReadout(frame.firing ? frame.lastRoll : null, frame.chapter)] : []),
  );
  app.frameKeys.narrative = narrativeKey;
}
```

**The auto-pan-freeze pattern the cinema-scrub's `onScrub` must reuse verbatim:**
```js
// Source: web/app.js:3908-3927 — the Phase 2 device-found fix (ed59087).
// Reuse this EXACT capture-on-first-callback / clear-on-scrub-end shape for
// the landscape cinema-scrub's onScrub/onScrubEnd — do not recompute the pan
// offset per pointermove, or the same backward-drag bug this fix resolved
// will reappear in the landscape scrub track.
onScrub: viewportFraction => {
  if (!app.data) return null;
  const total = app.data.story.total_words || 1;
  if (app.mobileScrubPanPct == null) {
    const playheadPctRaw = (app.wordPos / total) * 100;
    app.mobileScrubPanPct = panOffsetForPlayhead(playheadPctRaw, app.mobileTimelineZoom);
  }
  const innerFrac = mobileInnerFraction(viewportFraction, app.mobileTimelineZoom, app.mobileScrubPanPct);
  const target = Math.round(innerFrac * total);
  setWordPos(target);
  return lastRollAtWord(target);
},
onScrubEnd: () => {
  app.mobileScrubPanPct = null;
  persistBookmarkNow();
},
```

**The teardown-discipline shape to extend for the auto-hide timer:**
```js
// Source: web/app.js:3852-3872 (attachMobilePortraitGestures's existing
// unconditional teardown block) — add a fourth clearTimeout alongside the
// three existing teardown calls, in the same unconditional position (before
// the `if (app.mobileSurface) return;` guard) so a stale timer never
// survives a re-attach or a layout transition away from landscape.
function attachMobileGestures() {
  if (typeof app.mobileSkyTeardown === "function") { app.mobileSkyTeardown(); app.mobileSkyTeardown = null; }
  if (typeof app.mobileRailTeardown === "function") { app.mobileRailTeardown(); app.mobileRailTeardown = null; }
  app.mobileScrubPanPct = null;
  if (app.mobileRailResizeObserver) { app.mobileRailResizeObserver.disconnect(); app.mobileRailResizeObserver = null; }
  // NEW: clearTimeout(app.mobileChromeHideTimer); app.mobileChromeHideTimer = null;
  if (app.mobileSurface) return;
  // ...
}
```

## State of the Art

Not applicable in the conventional sense — there is no external library/ecosystem drift to track here. The one relevant "state of the art" note is internal: Phase 2 discovered and fixed a real production bug (`ed59087`, the auto-pan monotonicity fix) that the prototype reference code does not have (the prototype's `CinemaScrub` recomputes pan per-move exactly the way the pre-fix portrait code did). **Do not port `scrubber.jsx`'s `CinemaScrub` pointer-handling logic as a reference implementation for the fix's absence** — the freeze-on-drag-start pattern must be applied to the landscape scrub path from the start, not discovered a second time on a second real device.

**Superseded within this project:**
- The D-12 interim landscape fallback (`renderAppShell()` for landscape) — this phase's entire purpose is retiring it.
- `tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` — see Environment/Validation section below; this test's assertions are the explicit contract for what changes.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | The Phase 2 iOS Safari 18.5 device pass's confirmation of back-gesture flyout dismissal generalizes to landscape orientation without re-testing, because the underlying mechanism (`popstate`/`history.pushState`) is orientation-agnostic | Pitfall 5 | Low-moderate — if iOS Safari's edge-swipe-to-back behaves differently in landscape (e.g., due to a different on-screen safe area or Safari chrome layout), MOBL-04's back-gesture requirement could silently fail only in landscape. Mitigated by explicitly re-testing this specific behavior at the Phase 3 device gate (already planned via D-23) rather than skipping it as "already proven." |
| A2 | Reusing the single `app.mobileRailWidth`/`app.mobileRailBins` field pair for both the portrait mini-rail and the landscape cinema-scrub track (rather than introducing separate fields) is safe because only one layout is ever mounted at a time | Pattern 2, Pitfall 6 | Low — if a future phase ever needs both layouts' scrub state simultaneously (unlikely given D-36's no-tablet-tier stance), the shared field would need splitting. For Phase 3 alone this is a reasonable simplification, but it is Claude's Discretion, not a locked decision — the planner should confirm this choice explicitly rather than assume it silently. |
| A3 | `ROTATION_ANIM` (220ms, defined in `web/mobile-gestures.js`'s `G` constants) is not needed anywhere in this phase, since D-20 explicitly forbids building a cross-fade | Summary; Pattern 1 | Very low — the constant already exists (byte-identical, untouched) and is simply unused by this phase; INTEGRATION_PLAN.md §5 Phase E ("cross-fade rotation skipped [under reduced motion]") implies a cross-fade may be built in a later phase, not this one. If a future reviewer expects `ROTATION_ANIM` to already be wired, this note preempts that confusion. |

## Open Questions

1. **Exact DOM class names for the landscape-specific elements (cinema-scrub track, field-log list, control dock)**
   - What we know: CONTEXT.md explicitly leaves "exact landscape DOM structure and class names" to Claude's Discretion, with `prototype/layouts.jsx`'s `LandscapeF` and `prototype/styles.css` as the visual reference.
   - What's unclear: Whether to adopt the prototype's exact class names (`.cinema-scrub`, `.field-log`, `.control-dock`, `.rail`) prefixed `.mobile-` (matching the existing `.mobile-sky`/`.mobile-dock`/`.mobile-rail` portrait convention) or different names entirely.
   - Recommendation: Follow the portrait precedent exactly — prefix every prototype class name with `mobile-` (e.g. `.mobile-cinema-scrub`, `.mobile-field-log`, `.mobile-control-dock`), since `.mobile-rail` is already taken by the portrait mini-rail and reusing it for the landscape sidebar container would collide semantically (the sidebar in landscape is NOT a scrub-drag surface, unlike `.mobile-rail` in portrait) — pick a distinct name such as `.mobile-landscape-rail` or `.mobile-sidebar` for the field-log+dock container to avoid the exact "rail vs rail" ambiguity flagged in Pattern 2.

2. **Whether `app.mobileChromeHideTimer`'s reveal-on-tap (D-30) needs to suppress the immediately-following tap-to-pause toggle, or whether both can fire in the same tap**
   - What we know: D-30 says "the first sky tap always reveals hidden chrome... The second tap within the window pauses only when tap-to-pause is on." This describes two SEPARATE taps (first reveals, second pauses), not one tap doing both.
   - What's unclear: The prototype's own `onSky.tap` handler (`app.jsx:171-176`) does exactly this: `if (isLandscape && chromeHidden) { setChromeHidden(false); return; }` — an early `return` that makes the reveal tap a no-op for pause purposes, confirming the "one tap, one job" reading. This matches the CONTEXT.md wording precisely; not actually ambiguous, but flagged here because it's easy to accidentally implement as "reveal AND toggle pause on the same tap" if read quickly.
   - Recommendation: Implement the early-return exactly as the prototype does — a tap that reveals hidden chrome must `return` immediately, never falling through to the `togglePlayback()` call in the same handler invocation.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Chromium (Playwright) | Automated Playwright test suite (rotation, auto-hide, focus-trap regression tests) | Assumed ✓ (Phase 1/2's 33 passing tests already run against it in this environment) | — | Tests already use `pytest.importorskip("playwright.sync_api")` + `_chromium_browser_or_skip` to skip gracefully if Chromium is missing — no change needed for Phase 3 |
| Real iOS Safari device (over `ios-webkit-debug-proxy` / WebKit inspector protocol) | D-23's mandatory device-pass gate — MOBL-02/03/04's `resize`/`orientationchange` timing race explicitly cannot be verified in emulation | Confirmed available in this project's workflow — Phase 2 completed a full iOS Safari 18.5 pass via this exact tooling (Daniel's iPhone, `02-05-SUMMARY.md`) | iOS 18.5 / Safari 18.5 (as of the Phase 2 pass) | None — D-23 makes this a hard, non-optional gate; no automated substitute exists for the dynamic-toolbar/orientation-timing class of defect this project has repeatedly found only on real hardware |
| `/Users/dre/src/bcf-visualization/.venv` (main-checkout venv, since this worktree has none) | Running `pytest` | Confirmed by the orchestrator's session constraints | — | Always invoke tests as `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest ...` from within this worktree, never `pytest` bare |

**Missing dependencies with no fallback:** None identified — this phase's only hard external dependency (real iOS hardware) is already available per the project's established Phase 1/2 workflow.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + Playwright (sync API), same as Phase 1/2 |
| Config file | None dedicated — plain `pytest` invocation against `tests/` |
| Quick run command | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_plumbing.py tests/test_mobile_portrait.py -x` |
| Full suite command | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py` (33 tests as of Phase 2 close; expect a new landscape test file or additions to `test_mobile_portrait.py`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| MOBL-01 | Landscape layout shows sky ~75%/rail 25% with field log + dock | e2e (Playwright bounding-box assertions, mirroring `test_portrait_layout_proportions_and_chip_overlap`) | `pytest tests/test_mobile_landscape.py::test_landscape_layout_proportions -x` | ❌ Wave 0 — new file recommended (see below) |
| MOBL-02 | Auto-hide 4000ms idle, reveal-vs-pause tap semantics, reset on touch | e2e (Playwright, using `page.wait_for_timeout` for the 4000ms window, and `page.clock` fake-timer APIs if determinism is needed) | `pytest tests/test_mobile_landscape.py::test_chrome_autohide_and_reveal -x` | ❌ Wave 0 |
| MOBL-03 | Rotation preserves word position/play state/speed/zoom/prefs, no visible remount | e2e (Playwright `set_viewport_size` swap mid-playback + field-by-field assertion) | `pytest tests/test_mobile_landscape.py::test_rotation_preserves_state -x` | ❌ Wave 0 |
| MOBL-04 | Flyouts dismiss on backdrop tap, focus trap, back-gesture dismiss | e2e (Playwright, mirroring `test_mobile_portrait.py`'s existing surface-stack tests at `~line 934`, retargeted to `PHONE_LANDSCAPE`) | `pytest tests/test_mobile_landscape.py::test_landscape_surface_stack -x` | ❌ Wave 0 |
| — | `test_landscape_fallback_is_unchanged` must be REPLACED, not left passing | regression | `pytest tests/test_mobile_portrait.py -k landscape` | ⚠️ Existing test asserts the OLD (pre-Phase-3) contract — see below |

### Sampling Rate
- **Per task commit:** `pytest tests/test_mobile_plumbing.py tests/test_mobile_portrait.py -x` (fast subset touching mobile code)
- **Per wave merge:** Full suite (`test_desktop_smoke.py` + `test_mobile_plumbing.py` + `test_mobile_portrait.py` + any new `test_mobile_landscape.py`)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus D-23's mandatory two-pronged proof (Playwright viewport-swap test AND the real-device iOS Safari pass — neither alone suffices)

### Wave 0 Gaps
- [ ] A new `tests/test_mobile_landscape.py` (or a `PHONE_LANDSCAPE`-targeted addition to `tests/test_mobile_portrait.py`) covering MOBL-01..04 structurally, following the exact harness conventions already established (`staged_web_runtime_site`, `_page_with_console_capture`, `_chromium_browser_or_skip`, `PHONE_LANDSCAPE = {"width": 844, "height": 390}` already defined in both existing test files).
- [ ] `tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` (lines 1264-1298) **must be rewritten**, not left as-is — see "Which assertions must change" below (answers planner question 5 in full).
- [ ] No new fixtures/conftest needed — the existing `tiny-default` data package fixture already used throughout `test_mobile_portrait.py` covers this phase's needs.

### Which existing test assertions must change vs. must NOT change (full answer to planner question 5)

**`tests/test_mobile_plumbing.py` — landscape-touching tests, verified NOT requiring changes:**
Read in full. Every landscape reference in this file (`test_layout_mode_matrix_matches_css_breakpoint`, `test_layout_mode_survives_rotation`, `test_gesture_attach_survives_forced_rerenders_without_double_fire`, `test_mid_drag_rerender_is_safe_and_fresh_probe_fires_once`) asserts only `window.__bcfLayoutMode === "landscape"` and the Phase-1 diagnostic `.mobile-gesture-probe`'s attach/tap-count behavior — **never** any desktop-shell-specific markup (`.app`, `.app-header`, etc.). `attachMobileGestureProbes()` runs for `app.layoutMode !== "desktop"` unconditionally (portrait or landscape alike) and is untouched by this phase's changes to `attachMobileGestures()` (a distinct, separately-named function). **These tests should stay green with zero edits** — this is the "Phase 1 gesture-probe contract" the task brief calls out, and it is independent of what `render()` mounts for landscape.

**`tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` (lines 1264-1298) — MUST be rewritten:**
This test currently asserts, at `PHONE_LANDSCAPE`:
- `expect(page.locator(".app")).to_be_visible()` — **will become false**; `renderMobileLandscape()` replaces `renderAppShell()` for landscape, so `.app` will no longer mount there.
- `expect(page.locator(".portrait-banner")).to_be_visible()` — **will become false**; the banner only ever rendered inside `renderAppShell()`'s desktop-shell tree (`app.js:1041`), which landscape stops using.
- `document.querySelector('.mobile-gesture-probe') != null` — **stays true**, per the analysis above.
- `document.querySelector('.mobile-app')` **is None** — **will become false** (inverted): landscape will now mount a `.mobile-app` (or a landscape-specific root class, per Open Question 1) — the assertion's entire premise ("the portrait surface must never mount at a landscape viewport") needs restating as "landscape mounts ITS OWN mobile surface, structurally distinct from the portrait one, and NEVER mounts `renderAppShell()`'s `.app`/`.portrait-banner` markup." The test's own comment already anticipates this exact obsolescence: "Phase 3 replaces it with `renderMobileLandscape()`, not this plan."

Recommendation: rename this test (e.g. `test_landscape_no_longer_falls_back_to_desktop_shell`) and rewrite its assertions to the inverse of today's, keeping the `.mobile-gesture-probe` assertion unchanged and adding a positive assertion that whatever `renderMobileLandscape()`'s root class is (`.mobile-app` or otherwise) IS present. Do not simply delete the test — its regression-guard purpose (proving the fallback is gone, on purpose, not by accident) still matters for Phase 4, which needs to know landscape definitively left `renderAppShell()` behind before deleting the portrait banner globally.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | No | No auth in this app |
| V3 Session Management | No | No server session; `localStorage` prefs only |
| V4 Access Control | Marginal — UI-level only | Focus-trap containment (D-16, reused unmodified) is a UI-affordance control, not a security boundary; no privileged data is gated behind it |
| V5 Input Validation | Yes, at the UI-event layer | Gesture callback allow-lists already in place (`MOBILE_SURFACES.includes(kind)` guard in `openMobileSurface`, `ON_ROLL_BEHAVIORS.includes(value)` guard on the settings delegation) — landscape introduces no new user-text-input surfaces, only pointer gestures and pre-defined button actions, so no new validation surface is created |
| V6 Cryptography | No | N/A — no crypto in this app |
| V11 Business Logic | Marginal | `history.pushState`/`popstate` sentinel balance (D-16) prevents history-stack growth (already threat-flagged T-02-14, mitigation already implemented and reused unmodified) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Evidence-quote text (D-27's truncated field-log quote) rendered unsafely, enabling stored/reflected script injection | Tampering / Elevation of Privilege | Confirmed by direct inspection: `app.js` contains zero `innerHTML` assignments anywhere; the `el()` DOM helper only ever sets `node.textContent` via its `text` prop (`app.js:278-312`). The landscape field log must follow this exact convention (`el("div", { text: truncatedQuote })`, never string-concatenated HTML) — already the established, verified-safe pattern, not a new decision this phase needs to make. |
| `history.pushState`/`popstate` sentinel growth if a programmatic close forgets `history.back()` | Denial of Service (very low severity) | Already mitigated by `closeMobileSurface`'s `fromPopstate`-gated `history.back()` call (D-16), reused unmodified for landscape — no new code path introduced |
| A stale `setTimeout` handle (the new auto-hide timer) firing after its owning layout/render has been torn down, mutating a detached or stale DOM node | Tampering (of application state, not security-sensitive data) | Addressed directly in Pattern 4/Pitfall 2's teardown discipline — clear the timer unconditionally in `attachMobileGestures()`'s teardown block, and guard the fired callback's DOM mutation with an `app.dom.mobileCinemaScrubTrack?.classList...` optional-chain in case the ref went stale between scheduling and firing (e.g., a rotation away from landscape happened inside the 4000ms window) |

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `web/app.js` (full read of the render dispatch, portrait renderer, gesture attach, playback-frame update tier, surface stack, layout-mode detection) — the authoritative source for every generalization point identified above.
- `web/mobile.css` (full read) — confirmed the single portrait-scoped body-lock rule D-32 targets and the absence of any other portrait-dependent rule.
- `web/mobile-gestures.js` (full read) — confirmed the exact shape of `attachSkyGestures`/`attachRailScrub` and that no `onDown`/generic-touch hook exists, informing the auto-hide reset design.
- `design/mobile-ux/prototype/layouts.jsx`, `panels.jsx`, `scrubber.jsx` (`CinemaScrub`), `app.jsx` (full reads) — the visual/behavioral reference, cross-checked against production code to find both what's reusable (markup shape, math) and what's a prototype-only artifact not to copy (the bespoke pointer handler, the `wordPos`-keyed auto-hide effect).
- `design/mobile-ux/prototype/styles.css` (landscape `@media` block) — confirmed the ~75%/25% sky/rail split and the rail's 2/3 field-log / 1/3 control-dock ratio as CSS `flex` values.
- `tests/test_mobile_plumbing.py`, `tests/test_mobile_portrait.py` (full reads of landscape-touching sections) — confirmed exactly which assertions survive Phase 3 unchanged vs. require rewriting.
- `.planning/workstreams/mobile-ux/phases/02-portrait-layout/02-05-SUMMARY.md` (full read) — the four real-device-found defects, their fixes, and the explicit "carried into Phase 3" guidance (D-19 sky-scoping convention reuse, budget a real-device pass into every remaining gate).
- `design/mobile-ux/INTEGRATION_PLAN.md` §0 (freeze rules), §5 Phase C — confirmed the frozen §0.2 read-only function list includes `renderViewportFrame`/`renderSkyCamera`/`renderNarrativeReadout`/`renderRecentRolls`, validating D-13/D-24/D-35's "call, never edit or duplicate" framing.

### Secondary (MEDIUM confidence — WebSearch, cross-checked)
- WebSearch "auto-hide UI chrome idle timer reset on user interaction not on animation frame state change" — confirmed the general industry pattern (reset from discrete interaction events, not from continuous/animation-frame-driven state) matches the fix this research recommends for Pitfall 1; no single canonical source, synthesized from GeeksforGeeks/kirupa.com-tier general JS idle-detection writeups.
- WebSearch "history.pushState popstate dismiss mobile flyout back gesture focus trap accessible pattern" — surfaced WebKit bug 248303 ("REGRESSION (iOS 16): popstate events are not fired for swipe-back gesture"), the source for Pitfall 5's device-pass recommendation. [CITED: bugs.webkit.org/show_bug.cgi?id=248303] — treated as a historical risk flag, not a confirmed-current bug, since Phase 2's iOS 18.5 pass did not report this failure mode (in portrait).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; every API cited is already live and tested in this codebase.
- Architecture (generalization points, shared-helper seam): HIGH — every claim traced to a specific line range read directly in this session, not inferred.
- Pitfalls: HIGH for Pitfalls 1-4, 6 (all derived from direct code/prototype comparison); MEDIUM for Pitfall 5 (WebSearch-sourced historical WebKit bug, not independently reproduced this session).

**Research date:** 2026-08-01
**Valid until:** Effectively pinned to this phase's lifetime — this research is almost entirely a snapshot of this exact codebase state at the start of Phase 3, not time-decaying external-library research. Re-verify the three "portrait"-literal branch points (Pitfall 2) if any other agent touches `render()`/`cachePlaybackDomRefs()`/`updatePlaybackFrame()` before this phase's plan executes.
