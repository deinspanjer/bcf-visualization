# Phase 3: Landscape Layout - Pattern Map

**Mapped:** 2026-08-01
**Files analyzed:** 4 (2 modified source files, 2 test files — one new, one rewritten)
**Analogs found:** 4 / 4 — this phase's dominant analog is Phase 2 itself; every landscape construct has a portrait counterpart already built, device-tested and committed in the same two source files.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `web/app.js` — `renderMobileLandscape()` (new function) | component (render function) | request-response (pure DOM build from `app.*` state) | `renderMobilePortrait()` (`app.js:3340-3413`) | exact — same file, same section, same calling convention |
| `web/app.js` — `renderMobileSkyRegion(frame)` (new, D-35 shared helper) | component (render function) | request-response | The sky-region block inside `renderMobilePortrait()` (`app.js:3348-3370`) | exact — this is an extraction of existing code, not a new pattern |
| `web/app.js` — `attachMobileGestures()` (renamed/generalized from `attachMobilePortraitGestures`, D-34) | controller (event-attach lifecycle) | event-driven | `attachMobilePortraitGestures()` (`app.js:3852-3964`) | exact — same file being edited in place |
| `web/app.js` — `updateMobileLandscapeFrame()` (new incremental-tier function) | service (incremental DOM diff) | streaming (per-rAF-tick update) | `updateMobilePortraitFrame()` (referenced from `updatePlaybackFrame()` at `app.js:2733`) + desktop's `updatePlaythroughFrame()` narrative-key pattern (`app.js:2800-2810`) | exact — same memoized-key pattern, new DOM target |
| `web/app.js` — `render()` landscape branch, `cachePlaybackDomRefs()` landscape refs, `updatePlaybackFrame()` landscape dispatch (3 edits to existing functions) | controller / config (dispatch wiring) | request-response | The existing `"portrait"`-literal branches in the same three functions (`app.js:991`, `:1005-1015`, `:2701-2719`, `:2733-2736`) | exact — literal-string generalization of code already in the file |
| `web/app.js` — chrome auto-hide timer (`resetChromeHideTimer()`, `app.mobileChromeHideTimer`, `app.chromeHidden`) | utility (timer lifecycle) | event-driven | **No analog** — see "No Analog Found" below; closest structural precedent is the teardown-discipline pattern for `app.mobileSkyTeardown`/`app.mobileRailResizeObserver` |
| `web/mobile.css` — landscape layout rules (sky/rail split, cinema-scrub, field-log, control-dock) | config (CSS) | — | The portrait block in the same file (`.mobile-sky`, `.mobile-dock`, `.mobile-rail` rules) plus `design/mobile-ux/prototype/styles.css`'s `@media (orientation: landscape)` block | role-match — CSS conventions transfer 1:1, exact values come from the prototype per UI-SPEC |
| `web/mobile.css` — un-nest body scroll-lock (D-32) | config (CSS) | — | The existing `@media (orientation: portrait) { body {...} }` block at `mobile.css:29-36` | exact — this is a one-line scope edit to code already in the file |
| `tests/test_mobile_landscape.py` (new) | test | request-response (Playwright e2e) | `tests/test_mobile_portrait.py` — harness fixtures + surface-stack tests (`~line 934` onward) | exact — same harness, same fixtures, new viewport target |
| `tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` (rewrite) | test | request-response | Itself (pre-Phase-3 version, `test_mobile_portrait.py:1264-1298`) | exact — in-place rewrite, inverted assertions |

## Pattern Assignments

### `web/app.js` — `renderMobileLandscape()` (component, request-response)

**Analog:** `renderMobilePortrait()`, `web/app.js:3340-3413`

**Full structural pattern to mirror** (`app.js:3340-3413`):
```javascript
function renderMobilePortrait() {
  maybeAutoOpenHelp();
  const frame = playthroughFrameState();
  // Structural render is one of the exactly three call sites for bin
  // recomputation (D-18) — never inside updateMobilePortraitFrame().
  recomputeMobileRailBins();
  return el("div", { class: "mobile-app" },
    renderMobileTopCluster(),
    el("div", { class: "mobile-sky mobile-sky-surface" },
      renderViewportFrame(),
      el("div", { class: "mobile-sky-camera-layer" },
        frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,
      ),
      renderMobileFocalLabel(frame),
      renderMobileSkyTapHint(),
      app.mobileSurface === "help" ? renderMobileHelpOverlay() : null,
      renderMobileSurface(),
    ),
    el("div", { class: "mobile-dock" }, /* transport row, scrubber, hint row */),
    renderMobileSurfaceBackdrop(),
  );
}
```
`renderMobileLandscape()` follows the same shape: `maybeAutoOpenHelp()` → frame state → bin recompute → one root `el("div", { class: "mobile-app" }, ...)` (Open Question 1 recommends reusing `.mobile-app` as the shared root class, or a distinct root — Claude's Discretion, but the *shape* of "one `el()` call returning the full tree" is locked) → sky region (via the shared `renderMobileSkyRegion(frame)` helper, D-35) as a flex sibling of a new right-rail container (field log + control dock) instead of stacked above a dock → `renderMobileSurfaceBackdrop()` as the last child, unchanged.

**Key divergence from the analog:** the sky is a horizontal flex sibling of the rail (not stacked above a dock), and the top-chip cluster's content differs (`CH {num}` only, no word count — UI-SPEC Typography table) — a real, intentional content difference, not an oversight.

---

### `web/app.js` — `renderMobileSkyRegion(frame)` (D-35 shared helper)

**Analog:** the sky-region block currently inlined in `renderMobilePortrait()`, `web/app.js:3348-3370`

**Extract verbatim into a new function**, called identically by both layouts:
```javascript
function renderMobileSkyRegion(frame) {
  return [
    renderViewportFrame(),                                    // frozen §0.2
    el("div", { class: "mobile-sky-camera-layer" },
      frame.scene ? renderSkyCamera(frame.lastRoll, frame.scene, frame.focusT) : null,  // frozen §0.2
    ),
    renderMobileFocalLabel(frame),
    renderMobileSkyTapHint(),
    app.mobileSurface === "help" ? renderMobileHelpOverlay() : null,
    renderMobileSurface(),
  ];
}
```
Each caller wraps this in its own `el("div", { class: "mobile-sky mobile-sky-surface" }, ...renderMobileSkyRegion(frame))` — the `mobile-sky` class stays the constant hook `attachMobileGestures` and CSS key off. **Never duplicate this block a second time** — D-35's explicit justification is "fixing the tap hint, focal label and camera layer twice" is the failure mode this avoids. `renderViewportFrame()` and `renderSkyCamera()` are frozen §0.2 read-only functions — call, never edit.

---

### `web/app.js` — `attachMobileGestures()` (controller, event-driven) [renamed/generalized from `attachMobilePortraitGestures`, D-34]

**Analog:** `attachMobilePortraitGestures()`, `web/app.js:3852-3964`

**Teardown block** (unconditional, runs first — extend with a 4th `clearTimeout` for the auto-hide timer, `app.js:3852-3872`):
```javascript
function attachMobileGestures() {
  if (typeof app.mobileSkyTeardown === "function") {
    app.mobileSkyTeardown();
    app.mobileSkyTeardown = null;
  }
  if (typeof app.mobileRailTeardown === "function") {
    app.mobileRailTeardown();
    app.mobileRailTeardown = null;
  }
  app.mobileScrubPanPct = null;
  if (app.mobileRailResizeObserver) {
    app.mobileRailResizeObserver.disconnect();
    app.mobileRailResizeObserver = null;
  }
  // NEW (Pattern 4): clearTimeout(app.mobileChromeHideTimer); app.mobileChromeHideTimer = null;
  if (app.mobileSurface) return;
  // ... sky gestures, scrub gestures, ResizeObserver below, unchanged shape
}
```

**Sky gesture attach — the one hard branch point (`onTap`)** (`app.js:3878-3904`):
```javascript
const skyEl = document.querySelector(".mobile-sky");   // shared selector, D-35
if (skyEl && typeof window.attachSkyGestures === "function") {
  app.mobileSkyTeardown = window.attachSkyGestures(skyEl, {
    onTap: () => {
      // NEW landscape branch, evaluated FIRST (D-30 — must precede the
      // tap-to-pause check and must `return` immediately, never fall through):
      // if (app.layoutMode === "landscape" && app.chromeHidden) { reveal(); resetChromeHideTimer(); return; }
      if (!app.tapToPause) return;
      togglePlayback();
    },
    onDoubleTap: () => {
      const target = lastRollAtWord(app.wordPos);
      if (target) setWordPos(target.word_position);
      if (!app.playing) togglePlayback();
    },
    onSwipeStep: dir => {
      const next = rollStepFrom(app.wordPos, dir);
      if (next) setWordPos(next.word_position);
      // NEW: resetChromeHideTimer() call here too (any touch resets it)
    },
    onSwipeEnd: () => persistBookmarkNow(),
  });
}
```

**Scrub gesture attach — reuse verbatim, only the queried element differs** (`app.js:3906-3934`, the D-17 single-scrub-input-path + Phase 2's device-found auto-pan-freeze fix, `ed59087`):
```javascript
const railEl = document.querySelector(".mobile-rail");   // landscape: query the cinema-scrub's
                                                            // track element instead — see Pattern 2
                                                            // note below on naming collision
if (railEl && typeof window.attachRailScrub === "function") {
  app.mobileRailTeardown = window.attachRailScrub(railEl, {
    onScrub: viewportFraction => {
      if (!app.data) return null;
      const total = app.data.story.total_words || 1;
      // Freeze auto-pan offset for the whole drag — capture on first
      // callback, clear in onScrubEnd. This is the exact device-found
      // monotonicity fix (Pixel 10 Pro XL, 68k-word backward drift) — reuse
      // this shape verbatim for the cinema-scrub, do not recompute per move.
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
      // NEW: resetChromeHideTimer()
    },
  });
}
```

**IMPORTANT naming collision to avoid (from RESEARCH.md Pattern 2):** the prototype's own vocabulary distinguishes `.rail` (the landscape sidebar — field log + dock, NOT a scrub surface) from `.scrub-track`/`.cinema-scrub` (the actual drag surface). Do not query `.mobile-rail` for the landscape scrub surface — that class is portrait's mini-rail. Use a distinct selector such as `.mobile-cinema-scrub-track`, and use a distinct name for the sidebar container (e.g. `.mobile-landscape-rail` or `.mobile-sidebar`) to avoid "rail vs rail" ambiguity.

**ResizeObserver — same shape, different observed element and rebuild target** (`app.js:3941-3963`): reused verbatim as a template; only the observed element (`.mobile-cinema-scrub-track` instead of `.mobile-rail`) and what gets `replaceChildren`'d (cinema-scrub bins instead of the rolls lane) differ.

---

### `web/app.js` — three dispatch-point generalizations (Pitfall 2, hard requirement)

**Analog:** the same three functions, current portrait-literal state

**1. `render()`** (`app.js:991`, `:1005-1015`):
```javascript
// CURRENT (app.js:991):
root.append(app.layoutMode === "portrait" ? renderMobilePortrait() : renderAppShell());
// BECOMES:
root.append(
  app.layoutMode === "portrait" ? renderMobilePortrait()
  : app.layoutMode === "landscape" ? renderMobileLandscape()
  : renderAppShell()
);
```
```javascript
// CURRENT (app.js:1005-1015) — the gesture-attach + focus-trap block:
if (app.layoutMode === "portrait") {
  attachMobilePortraitGestures();
  if (app.mobileSurface) {
    trapMobileSurfaceFocus(document.querySelector(".mobile-flyout, .mobile-help-overlay"));
  } else {
    teardownMobileSurfaceFocusTrap();
  }
}
// BECOMES (Pitfall 3 — change the WHOLE guard in one edit, not two, or focus-trap
// re-attach silently stays portrait-only while gesture-attach is fixed):
if (app.layoutMode !== "desktop") {
  attachMobileGestures();
  if (app.mobileSurface) {
    trapMobileSurfaceFocus(document.querySelector(".mobile-flyout, .mobile-help-overlay"));
  } else {
    teardownMobileSurfaceFocusTrap();
  }
}
```

**2. `cachePlaybackDomRefs()`** (`app.js:2701-2719`) — add a landscape branch alongside the existing portrait one; do not collapse both into one `!== "desktop"` block, since the ref sets differ (field-log/cinema-scrub refs vs. rail/dock refs):
```javascript
if (app.layoutMode === "portrait") {
  app.dom.mobileSky = document.querySelector(".mobile-sky");
  // ...existing portrait-only refs, unchanged...
} else if (app.layoutMode === "landscape") {
  app.dom.mobileSky = document.querySelector(".mobile-sky");            // shared, D-35
  app.dom.mobileFieldLogList = document.querySelector(".mobile-field-log-list");
  app.dom.mobileFieldLogLive = document.querySelector(".mobile-field-log-live");
  app.dom.mobileFieldLogHeader = document.querySelector(".mobile-field-log-header");
  app.dom.mobileCinemaScrubTrack = document.querySelector(".mobile-cinema-scrub-track");
  app.dom.mobileCinemaScrubThumb = document.querySelector(".mobile-cinema-scrub-thumb");
  app.dom.mobileCinemaScrubFab = document.querySelector(".mobile-cinema-scrub-fab");
}
```

**3. `updatePlaybackFrame()`** (`app.js:2733-2736`) — the early-return-before-the-desktop-playhead-gate ordering constraint applies identically to landscape:
```javascript
// CURRENT:
if (app.layoutMode === "portrait") {
  updateMobilePortraitFrame();
  return;
}
if (!app.dom?.playhead) { render(); return; }
// BECOMES (add BEFORE the `!app.dom?.playhead` gate, same as portrait):
if (app.layoutMode === "portrait") { updateMobilePortraitFrame(); return; }
if (app.layoutMode === "landscape") { updateMobileLandscapeFrame(); return; }
if (!app.dom?.playhead) { render(); return; }
```

---

### `web/app.js` — `updateMobileLandscapeFrame()` (service, streaming/incremental)

**Analog:** desktop's field-log incremental-diff pattern, `app.js:2800-2810` (the memoized-key idiom to replicate)

```javascript
// Source: web/app.js:2800-2810 — desktop's own field-log incremental update,
// the pattern D-26 generalizes for the landscape rail.
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
Apply the same shape to `app.dom.mobileFieldLogList`/`app.frameKeys.mobileFieldLog`, computing the key from `recentRolls(app.wordPos, N)`'s live-relevant fields (e.g. joined `uid`s), and only calling `replaceChildren` when the key changes. **The data call is `recentRolls(wordPos, count)` (`app.js:791`, D-24's locked seam) — never `renderNarrativeReadout`/`renderRecentRolls` (frozen §0.2, desktop-sized).**

```javascript
// Source: web/app.js:791-798 — the only field-log data call needed.
function recentRolls(wordPos, count = 10) {
  const rows = [];
  for (let i = app.data.story.rolls.length - 1; i >= 0 && rows.length < count; i -= 1) {
    const roll = app.data.story.rolls[i];
    if (roll.word_position <= wordPos) rows.push(roll);
  }
  return rows;
}
```

---

### `web/app.js` — chrome auto-hide timer (utility, event-driven) — **NO ANALOG, novel piece**

See "No Analog Found" below. Closest structural precedent for the *lifecycle discipline* (state lives on `app`, not `app.dom`; unconditional teardown at the top of `attachMobileGestures()`) is the existing `app.mobileSurfaceFocusTrapTeardown` reasoning (documented inline near `trapMobileSurfaceFocus`/`teardownMobileSurfaceFocusTrap`, `app.js:3049-3086`) and the `app.mobileSkyTeardown`/`app.mobileRailResizeObserver` teardown slots shown above. Concrete shape (from RESEARCH.md Pattern 4, already vetted against Pitfall 1):
```javascript
function resetChromeHideTimer() {
  clearTimeout(app.mobileChromeHideTimer);
  app.mobileChromeHideTimer = null;
  if (app.layoutMode === "landscape" && app.playing) {
    app.mobileChromeHideTimer = setTimeout(() => {
      app.chromeHidden = true;
      app.dom.mobileCinemaScrubTrack?.closest(".mobile-cinema-scrub")?.classList.add("is-hidden");
    }, 4000);   // G.CHROME_AUTOHIDE in mobile-gestures.js
  }
}
```
**Never** reset from `wordPos` changes (Pitfall 1) or from `updateMobileLandscapeFrame()` — reset only from discrete gesture-callback bodies (`onTap` after reveal-handling, `onDoubleTap`, `onSwipeStep`, `onSwipeEnd`, `onScrub`, `onScrubEnd`) and from `togglePlayback()`/`onLayoutMaybeChanged()`'s landscape-entry path. Mutate visibility via `classList.toggle`/`classList.add`/`classList.remove` directly on the cached DOM ref — never via `render()` (would tear down and reattach every gesture listener every 4s during ordinary playback).

---

### `web/mobile.css` — landscape layout rules (config)

**Analog:** the existing portrait block in the same file, plus the prototype's `@media (orientation: landscape)` block for exact values (already locked in UI-SPEC's Spacing Scale table — reproduce those pixel values verbatim, do not re-derive).

**D-32: un-nest the body scroll-lock** (`web/mobile.css:29-36`):
```css
/* CURRENT — scoped to portrait only: */
@media (orientation: portrait) {
  body {
    min-height: 100svh;
    height: 100svh;
    overflow-y: hidden;
    overscroll-behavior-y: none;
  }
}
/* BECOMES — apply to the whole outer mobile block (both orientations),
   since landscape no longer falls back to the scrollable desktop shell.
   Update the comment too — it currently says "until Phase 3 replaces it." */
body {
  min-height: 100svh;
  height: 100svh;
  overflow-y: hidden;
  overscroll-behavior-y: none;
}
```
This edit lands inside the existing outer `@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px) { ... }` block (`mobile.css:11`), just un-nested one level — not moved to a new file or a new outer media query.

**Safe-area variables to consume** (already defined, unused until this phase — `web/mobile.css:50-56`):
```css
:root {
  --safe-top: env(safe-area-inset-top, 0px);
  --safe-bottom: env(safe-area-inset-bottom, 0px);
  --safe-left: env(safe-area-inset-left, 0px);
  --safe-right: env(safe-area-inset-right, 0px);
}
```
UI-SPEC's safe-area table applies these to `.mobile-app` landscape root (`padding-left/right: var(--safe-left/right)`), the control-dock's bottom edge (`padding-bottom: max(<locked>, var(--safe-bottom))`, same `max()` idiom as the portrait dock at `mobile.css:226`), and the top chip cluster — never raw `env()` calls outside this centralized variable block.

---

### `tests/test_mobile_landscape.py` (new) (test, request-response/e2e)

**Analog:** `tests/test_mobile_portrait.py` — harness fixtures and the surface-stack test group (`~line 934` onward)

**Harness conventions to reuse verbatim** (imports/fixtures already defined in `test_mobile_portrait.py`):
```python
PHONE_LANDSCAPE = {"width": 844, "height": 390}   # test_mobile_portrait.py:61 — already defined,
                                                     # import or duplicate the constant
```
```python
def _chromium_browser_or_skip(playwright, playwright_api):
    ...  # test_mobile_portrait.py:22 — reuse the skip-if-no-Chromium guard verbatim

def _page_with_console_capture(browser, site, viewport=None, storage=None):
    page = browser.new_page(viewport=viewport or PHONE_PORTRAIT)
    ...  # test_mobile_portrait.py:31-40 — reuse verbatim, pass viewport=PHONE_LANDSCAPE
```
Use `staged_web_runtime_site(tmp_path)` (the `tiny-default` data package fixture) exactly as every existing portrait test does — no new fixture/conftest needed per RESEARCH.md's Wave 0 gap analysis. Structure new tests as one Playwright session per behavior (rotation, auto-hide, layout proportions, surface stack), mirroring the existing `test_portrait_layout_proportions_and_chip_overlap`-style bounding-box assertions for MOBL-01's sky/rail proportions.

---

### `tests/test_mobile_portrait.py::test_landscape_fallback_is_unchanged` (rewrite)

**Analog:** itself, pre-Phase-3 (`tests/test_mobile_portrait.py:1264-1298`)

**Current (must be inverted, not deleted):**
```python
def test_landscape_fallback_is_unchanged(tmp_path):
    # 02-05 phase-close proof: ... Phase 3 replaces it with
    # renderMobileLandscape(), not this plan. ...
    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page, console_messages = _page_with_console_capture(
                browser, site, viewport=PHONE_LANDSCAPE, storage=DEFAULT_STORAGE,
            )
            assert page.evaluate("window.__bcfLayoutMode") == "landscape"
            expect(page.locator(".app")).to_be_visible()               # WILL BECOME FALSE
            expect(page.locator(".portrait-banner")).to_be_visible()   # WILL BECOME FALSE
            assert page.evaluate(
                "document.querySelector('.mobile-gesture-probe') != null") is True   # STAYS TRUE
            assert page.evaluate("document.querySelector('.mobile-app')") is None    # INVERTS
            assert console_messages == []
            browser.close()
```
**Rename** (e.g. `test_landscape_no_longer_falls_back_to_desktop_shell`) and rewrite the assertions to their inverse: `.app`/`.portrait-banner` must NOT be visible; whatever `renderMobileLandscape()`'s root class is (`.mobile-app` or a distinct landscape root, per Open Question 1) MUST be present; keep the `.mobile-gesture-probe` assertion unchanged (still `!= null` for every non-desktop layout mode) and the `console_messages == []` assertion unchanged. Do not delete the test — its regression-guard purpose (proving the fallback is gone *on purpose*) matters for Phase 4, which needs to know landscape definitively left `renderAppShell()` behind before deleting the portrait banner globally.

**No changes needed:** every landscape-touching assertion in `tests/test_mobile_plumbing.py` (`test_layout_mode_matrix_matches_css_breakpoint`, `test_layout_mode_survives_rotation`, `test_gesture_attach_survives_forced_rerenders_without_double_fire`, `test_mid_drag_rerender_is_safe_and_fresh_probe_fires_once`) asserts only `window.__bcfLayoutMode` and the `.mobile-gesture-probe` diagnostic — never desktop-shell markup — and stays green with zero edits.

## Shared Patterns

### Desktop-freeze / §0.2 read-only functions
**Source:** `design/mobile-ux/INTEGRATION_PLAN.md` §0.2; enforced throughout `web/app.js`
**Apply to:** `renderMobileLandscape()`, `renderMobileSkyRegion()`, `updateMobileLandscapeFrame()`
```javascript
// Frozen, callable-but-not-editable: renderViewportFrame(), renderSkyCamera(),
// renderNarrativeReadout(), renderRecentRolls(). The last two must NEVER be
// called by landscape code (D-24) — call recentRolls(wordPos, count) instead.
```

### Full-teardown-before-attach discipline (D-07)
**Source:** `attachMobilePortraitGestures()`, `web/app.js:3852-3876`
**Apply to:** `attachMobileGestures()` — every stateful handle (`mobileSkyTeardown`, `mobileRailTeardown`, `mobileRailResizeObserver`, and the new `mobileChromeHideTimer`) is torn down unconditionally at the top of the function, before the `if (app.mobileSurface) return;` guard, so a stale handle never survives a re-attach or a layout transition.

### `app`-scoped (not `app.dom`-scoped) ephemeral state
**Source:** the reasoning already documented for `app.mobileSurfaceFocusTrapTeardown` and `app.mobileScrubPanPct`
**Apply to:** `app.mobileChromeHideTimer`, `app.chromeHidden` (already reserved unused at `app.js:131`)
```javascript
// Lives on `app` (not `app.dom`, which render() blanks every structural
// rebuild) so it survives to be cleared/invoked defensively across renders.
```

### No `innerHTML`, `textContent` only
**Source:** the `el()` DOM helper, `web/app.js:278-312`
**Apply to:** the field-log's truncated evidence quote (D-27) and every new text node this phase adds
```javascript
el("div", { text: truncatedQuote })   // never string-concatenated HTML
```

### Module-level click delegation for buttons — no new per-render handlers
**Source:** `web/app.js:3970-4015` (module-level `data-action` delegation, attached once at load, layout-agnostic)
**Apply to:** landscape's Settings/About/toggle-playback buttons — add matching `data-action` attributes only, no new JS wiring
```javascript
el("button", { "data-action": "mobile-open-settings", "aria-label": "Settings" }, mobileGearIcon())
```

## No Analog Found

| File / Construct | Role | Data Flow | Reason |
|---|---|---|---|
| Chrome auto-hide idle timer (`resetChromeHideTimer()`, `app.mobileChromeHideTimer`, `app.chromeHidden`) | utility | event-driven | No prior idle-timer construct exists anywhere in the mobile codebase — this is the one genuinely novel piece of state Phase 3 introduces (RESEARCH.md: "the one genuinely novel piece is chrome auto-hide"). The prototype's own reference implementation (`design/mobile-ux/prototype/app.jsx:138-142`) is explicitly a broken reference (Pitfall 1 — resets on `wordPos`, which changes every rAF tick, so the timer would never fire) and must NOT be ported verbatim. Use RESEARCH.md Pattern 4's design (reset from discrete gesture callbacks + `togglePlayback`/`onLayoutMaybeChanged`, teardown alongside the existing three teardown slots, `classList.toggle` mutation only, never `render()`). |
| Cinema-scrub track's initial-width fallback (Pitfall 6) | config/constant | — | The portrait `app.mobileRailWidth: 350` default may not suit the narrower, floating cinema-scrub pill. No existing per-layout default field exists; this phase must decide (Claude's Discretion per RESEARCH.md A2) whether to share `app.mobileRailWidth` across both layouts or reset it structurally inside `renderMobileLandscape()`, mirroring `recomputeMobileRailBins()`'s existing call-site discipline as the nearest structural precedent. |

## Metadata

**Analog search scope:** `web/app.js` (full file, 4060 lines — read via targeted non-overlapping ranges at lines 973-1050, 2680-2755, 3336-3435, 3852-3966, plus grep for all `layoutMode === "portrait"` sites and `openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus` definitions), `web/mobile.css` (lines 1-60 read directly; full-file scope confirmed safe by RESEARCH.md Pitfall 4's prior full-file inspection), `tests/test_mobile_portrait.py` (1382 lines; fixture/constant grep + direct read of `test_landscape_fallback_is_unchanged` at lines 1264-1298), `design/mobile-ux/prototype/{layouts,panels,scrubber,app,styles}.{jsx,css}` (referenced via RESEARCH.md's already-complete direct reads, not re-read in this pass to avoid duplicate token cost).
**Files scanned:** 4 source/test files read directly this session; RESEARCH.md/UI-SPEC.md supplied pre-verified excerpts for the prototype files, cross-checked against the live `app.js` reads above and found consistent.
**Pattern extraction date:** 2026-08-01
