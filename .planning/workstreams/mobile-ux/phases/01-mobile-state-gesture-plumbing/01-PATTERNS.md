# Phase 1: Mobile State & Gesture Plumbing - Pattern Map

**Mapped:** 2026-07-25
**Files analyzed:** 6 (new: 2, modified: 4)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `web/mobile-gestures.js` (new) | utility (pure pointer-event → callback module) | event-driven | `design/mobile-ux/prototype/gestures.js` | exact — verbatim port source |
| `web/app.js` — `app.layoutMode` detection + `MOBILE_MQ`/`PORTRAIT_MQ` | config/state (module-scope listener) | event-driven | `web/app.js:130-132` `PREFERS_REDUCED_MOTION` | exact |
| `web/app.js` — `LS_*` new constants + `migratePreviewStorage()` extension + `STORAGE_VERSION` bump | model/utility (storage schema) | CRUD (localStorage) | `web/app.js:55-64` (`LS_*` consts) + `web/app.js:315-323` (`migratePreviewStorage`) | exact |
| `web/app.js` — `readStoredNumberChoice`/reuse of `readStoredChoice`/`readStoredBoolean` for the 4 new keys | utility | CRUD (localStorage) | `web/app.js:252-283` | exact |
| `web/app.js` — gesture attach/teardown inside new `renderMobilePortrait`/`renderMobileLandscape` | controller/component (render function) | event-driven | `web/app.js:2524-2549` `cachePlaybackDomRefs()` (post-mount DOM-ref caching convention) called from `render()` at `web/app.js:889` | role-match (attach convention, not identical purpose) |
| `web/app.js` — `visibilitychange` pause-on-hidden (D-02) | event handler | event-driven | `web/app.js:2780-2782` existing `visibilitychange` listener (currently persists bookmark only) | exact — same listener to extend, not duplicate |
| `web/index.html` — `<script>` load order + viewport meta | config | request-response (static asset) | `web/index.html:5,13` (current viewport meta + module script tag) | exact |
| `web/style.css` — new mobile-scoped block | config/style | n/a | `web/style.css:360-362` (`@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px)` — the exact breakpoint string to reuse in JS `matchMedia`) plus `web/style.css:1564`/`1607` (pre-existing overlapping desktop-narrow `@media` blocks to out-cascade, never edit) | exact (breakpoint string), caution (cascade ordering) |
| `tests/test_desktop_smoke.py` (new) | test | request-response (Playwright integration) | `tests/test_web_app_integration.py:1-86` (harness pattern: `staged_web_runtime_site`, `_chromium_browser_or_skip`, `_page_with_console_capture`) | exact |
| `tests/helpers/web_runtime_site.py` — `WEB_FILES` tuple | config (test fixture) | file-I/O | `tests/helpers/web_runtime_site.py:14-20` (existing tuple; must gain `"mobile-gestures.js"`) | exact — same file, additive edit |

## Pattern Assignments

### `web/mobile-gestures.js` (new file — utility, event-driven)

**Analog:** `design/mobile-ux/prototype/gestures.js` (full file, 198 lines) — port verbatim per CONTEXT.md canonical refs, with the `window.__bcfPrefs` bridge decision resolved in the plan (see Shared Patterns below).

**Constants block to port unmodified** (`design/mobile-ux/prototype/gestures.js:6-19`):
```js
const G = {
  TAP_MAX_DURATION: 250,
  TAP_MAX_MOVE: 8,
  DOUBLE_TAP_INTERVAL: 300,
  DOUBLE_TAP_RADIUS: 24,
  SWIPE_ENGAGE: 24,
  SWIPE_AXIS_LOCK: 1.5,
  SCRUB_STEP_PX: 56,
  THROW_DECAY: 600,
  LONG_PRESS: 450,
  CHROME_AUTOHIDE: 4000,
  ROTATION_ANIM: 220,
  HAPTIC_TICK: 8,
};
```

**Haptic no-op guard** (`design/mobile-ux/prototype/gestures.js:21-24`) — depends on `window.__bcfPrefs.haptics`, which does not exist in `web/app.js` today. Bridge required (see Shared Patterns).

**Attach/teardown contract to preserve exactly** (`design/mobile-ux/prototype/gestures.js:35-140` `attachSkyGestures`, `:149-193` `attachRailScrub`): both functions attach 4 pointer listeners and return a teardown closure that removes them — this closure-return-for-teardown shape is what `web/app.js`'s new post-mount attach call sites must store and invoke (see next pattern).

**Export convention** (`design/mobile-ux/prototype/gestures.js:195-198`):
```js
window.GestureConstants = G;
window.attachSkyGestures = attachSkyGestures;
window.attachRailScrub = attachRailScrub;
window.haptic = haptic;
```
Loaded as a plain (non-module) `<script>` before `app.js` in `index.html`, consistent with `app.js` currently being `type="module"` and referencing globals like `window.__bcfRenderStats` (see `web/app.js:286`). Keep `mobile-gestures.js` a plain script (not a module) so `window.attachSkyGestures` etc. are visible to `app.js`.

---

### `web/app.js` — `app.layoutMode` detection (state/config, event-driven)

**Analog:** `web/app.js:130-132` (`PREFERS_REDUCED_MOTION`), extended per RESEARCH.md Pattern 1.

**Existing precedent to mirror** (`web/app.js:127-132`):
```js
// Reduced-motion preference is queried once at module load. Per the design
// README, if the user has prefers-reduced-motion: reduce, the focus animation
// resolves to its end state immediately (no camera pan, no transitions).
const PREFERS_REDUCED_MOTION = (typeof window !== "undefined"
  && typeof window.matchMedia === "function"
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
```

**New pattern to add** (module-scope, computed before first `render()` at `web/app.js:2784`):
```js
const MOBILE_MQ = window.matchMedia(
  "(max-width: 900px), (orientation: portrait) and (max-width: 1100px)"
); // IDENTICAL string to web/style.css:360 — do not hand-roll a second copy
const PORTRAIT_MQ = window.matchMedia("(orientation: portrait)");

function detectLayoutMode() {
  if (!MOBILE_MQ.matches) return "desktop";
  return PORTRAIT_MQ.matches ? "portrait" : "landscape";
}
```
`app.layoutMode` is written in exactly one place (this detection), never inside a `render*` function or gesture callback — same discipline `PREFERS_REDUCED_MOTION` already follows (it's `const`, computed once, read everywhere).

---

### `web/app.js` — `LS_*` constants and `migratePreviewStorage()` extension (model, CRUD)

**Analog:** `web/app.js:55-64` (constants) + `web/app.js:315-323` (`migratePreviewStorage`)

**Existing constants block** (`web/app.js:55-64`):
```js
const LS_BOOKMARK = "bcf:bookmark:word_position";
const LS_SPEED = "bcf:playback:speed:v2";
const LS_ZOOM = "bcf:timeline:zoom";
const LS_MODE = "bcf:mode";
const LS_ON_ROLL_BEHAVIOR = "bcf:on-roll-behavior";
const LS_ROLL_LOCATION = "bcf:roll-location";
const LS_FIELD_LOG_HIDDEN = "bcf:field-log:hidden";
const LS_PORTRAIT_DISMISSED = "bcf:portrait-dismissed";
const LS_STORAGE_VERSION = "bcf:preview-port-storage-version";
const STORAGE_VERSION = "2";
```
New constants follow the same naming convention, hyphen-separated (per Pitfall 2, deliberately distinct from `LS_ZOOM`'s colon-separated `bcf:timeline:zoom`):
```js
const LS_MOBILE_TIMELINE_ZOOM = "bcf:timeline-zoom"; // distinct from LS_ZOOM ("bcf:timeline:zoom") — do not merge
const LS_TAP_TO_PAUSE = "bcf:tap-to-pause";
const LS_HAPTICS = "bcf:haptics";
const LS_HELP_SEEN = "bcf:help-seen";
// STORAGE_VERSION bumps "2" -> "3"
```

**Existing migration function** (`web/app.js:315-323`):
```js
function migratePreviewStorage() {
  try {
    if (localStorage.getItem(LS_STORAGE_VERSION) === STORAGE_VERSION) return;
    for (const key of [LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR, LS_ROLL_LOCATION, LS_FIELD_LOG_HIDDEN]) {
      localStorage.removeItem(key);
    }
    localStorage.setItem(LS_STORAGE_VERSION, STORAGE_VERSION);
  } catch {}
}
```
Extend the purge array to add `LS_PORTRAIT_DISMISSED` (currently absent — must be ADDED per D-09/Pitfall 1, not "removed" as the stale INTEGRATION_PLAN.md wording says) plus the 4 new keys. Same try/catch-swallow shape (private-browsing safety), same `localStorage.setItem(LS_STORAGE_VERSION, STORAGE_VERSION)` tail call — do not restructure.

---

### `web/app.js` — read helpers for the 4 new keys (utility, CRUD)

**Analog:** `web/app.js:252-283` — use `readStoredChoice`/`readStoredBoolean` unmodified; do NOT use `readStoredNumber` for `bcf:timeline-zoom` (Pitfall 3 — needs an allow-list of `{1,2,4,8}`, not "any finite number").

```js
// Source: web/app.js:252-283, direct read — reuse unmodified
function readStoredChoice(key, allowed, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return allowed.includes(raw) ? raw : fallback;
  } catch {
    return fallback;
  }
}
function readStoredBoolean(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (raw === "true") return true;
    if (raw === "false") return false;
  } catch {}
  return fallback;
}
function store(key, value) {
  try { localStorage.setItem(key, String(value)); } catch {}
}
```
Application: `bcf:tap-to-pause` and `bcf:haptics` → `readStoredBoolean`; `bcf:help-seen` → `readStoredBoolean`; `bcf:timeline-zoom` → `readStoredChoice(LS_MOBILE_TIMELINE_ZOOM, ["1","2","4","8"], "1")` then `Number(...)`, matching the existing string-comparison contract of `readStoredChoice` (mirrors `app.mode`/`app.onRollBehavior`/`app.rollLocation` initialization at `web/app.js:94,99,100`).

---

### `web/app.js` — gesture attach lifecycle inside mobile render functions (controller, event-driven)

**Analog:** `cachePlaybackDomRefs()` call-after-mount convention (`web/app.js:2524-2549`, invoked at `web/app.js:889` immediately after `root.append(renderAppShell())`).

**Existing pattern** (`web/app.js:873-891`):
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
}
```
New mobile branch mirrors this exactly: after `root.append(renderMobilePortrait()/renderMobileLandscape())`, query the mounted sky/rail node and call `window.attachSkyGestures`/`window.attachRailScrub`, storing the returned teardown closure on `app.dom` (which is already reset to `{}` at the top of `render()`, so the previous teardown must be invoked defensively before being overwritten — belt-and-suspenders since full DOM teardown already GCs the old listeners). Never attach inside the `MOBILE_MQ`/`PORTRAIT_MQ` `"change"` handler — only inside the render pass, same discipline as `cachePlaybackDomRefs` which only ever runs from inside `render()`.

---

### `web/app.js` — `visibilitychange` pause-on-hidden (D-02) (event handler, event-driven)

**Analog:** existing listener at `web/app.js:2780-2782`, to be extended (not duplicated):
```js
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "hidden" && app.data) persistBookmarkNow();
});
```
D-02 requires adding a mobile-only pause branch inside this same handler (`if (app.layoutMode !== "desktop" && document.visibilityState === "hidden" && app.playing) togglePlayback()/pausePlayback()`), keeping the desktop bookmark-persist behavior untouched — a second, separate `addEventListener("visibilitychange", ...)` call is not the pattern; extend the one handler.

---

### `web/index.html` — script load order + viewport meta (config)

**Analog:** current file in full (`web/index.html:1-15`).

Current viewport meta (`web/index.html:5`):
```html
<meta name="viewport" content="width=device-width, initial-scale=1" />
```
D-03 requires: `width=device-width, initial-scale=1, viewport-fit=cover` — additive, no `user-scalable=no`/`maximum-scale=1`.

Current script tag (`web/index.html:13`):
```html
<script type="module" src="app.js?v=phase9-info-link"></script>
```
New `<script src="mobile-gestures.js"></script>` must be added BEFORE this line (plain script, not `type="module"`, so its `window.*` exports are visible synchronously to `app.js`'s module-scope code, which itself runs after module scripts are deferred — non-module scripts execute in document order before deferred modules).

---

### `web/style.css` — mobile-scoped block (config/style)

**Analog:** `web/style.css:360-362` for the exact breakpoint string; `web/style.css:1564`/`1607` (pre-existing overlapping `@media` blocks) as the cascade-ordering hazard to avoid.

```css
@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px) {
  .portrait-banner.is-visible { display: flex; }
}
```
This exact media-query string is the single source of truth the new `MOBILE_MQ`/`PORTRAIT_MQ` JS constants must match character-for-character (RESEARCH.md D-06/Pattern 1). Phase 1 adds zero new visible UI, but any CSS scaffolding (touch-action, svh/dvh, safe-area vars) must be positioned so it can out-cascade `web/style.css:1564` and `:1607` later without editing those rules directly (CSS freeze, plan §0.1.5) — append new rules later in the file or in a new `web/mobile.css` loaded after `style.css`.

---

### `tests/test_desktop_smoke.py` (new — test, request-response/integration)

**Analog:** `tests/test_web_app_integration.py:1-86` (harness setup + first test).

**Imports and harness reuse** (`tests/test_web_app_integration.py:1-17`):
```python
from __future__ import annotations
import json
import re
import pytest
from tests.helpers.web_runtime_site import staged_web_runtime_site

def _chromium_browser_or_skip(playwright, playwright_api):
    try:
        return playwright.chromium.launch()
    except playwright_api.Error as exc:
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip(f"Playwright Chromium is not installed: {exc}")
        raise
```

**Page-with-console-capture helper to reuse or adapt** (`tests/test_web_app_integration.py:20-45`):
```python
def _page_with_console_capture(
    browser, site, path="/web/?dataPackage=tiny-default", *,
    viewport=None, storage=None, init_script=None,
):
    page = browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
    if init_script:
        page.add_init_script(init_script)
    if storage:
        page.add_init_script(
            "const entries = " + json.dumps(storage)
            + "; for (const [key, value] of Object.entries(entries)) localStorage.setItem(key, value);"
        )
    messages = []
    page.on("console", lambda msg: messages.append(f"{msg.type}: {msg.text}") if msg.type in {"error", "pageerror"} else None)
    page.on("pageerror", lambda exc: messages.append(f"pageerror: {exc}"))
    page.goto(site.url_for(path), wait_until="networkidle")
    return page, messages
```

**Test skeleton pattern** (structural — assert `.app-header` visible, no `.portrait-banner.is-visible`, use `window.__bcfRenderStats.structuralRenders`):
```python
def test_desktop_smoke_resize_round_trip(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.add_init_script("window.__bcfRenderStats = { structuralRenders: 0 };")
            page.goto(site.url_for(), wait_until="networkidle")
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            page.set_viewport_size({"width": 1101, "height": 900})
            page.set_viewport_size({"width": 899, "height": 900})
            page.set_viewport_size({"width": 1920, "height": 1080})
            expect = playwright_api.expect
            expect(page.locator(".app-header")).to_be_visible()
            expect(page.locator(".portrait-banner.is-visible")).to_have_count(0)
            browser.close()
```
This is a peer file to `tests/test_web_app_integration.py`, not a merge into it — separate module per RESEARCH.md's Validation Architecture section, since it's the dedicated D-10 phase-gate artifact re-run at every Track A phase gate.

---

### `tests/helpers/web_runtime_site.py` — `WEB_FILES` tuple (config, file-I/O)

**Analog:** same file, existing tuple (`tests/helpers/web_runtime_site.py:14-20`):
```python
WEB_FILES = (
    "index.html",
    "app.js",
    "data-contract.js",
    "viz-model.js",
    "style.css",
)
```
Add `"mobile-gestures.js"` to this tuple in the same change that adds `web/mobile-gestures.js` and the `<script>` tag in `index.html` — otherwise every Playwright test (existing and new) serves a site with a 404'd script, which the existing `console_messages == []` assertions (e.g. `tests/test_web_app_integration.py:84`) will catch loudly. If mobile CSS is split into `web/mobile.css`, add that filename here too.

---

## Shared Patterns

### try/catch-swallow localStorage access
**Source:** `web/app.js:252-283` (`readStoredChoice`, `readStoredNumber`, `readStoredBoolean`, `store`)
**Apply to:** All 4 new `bcf:*` key reads/writes — never call `localStorage.getItem`/`setItem` directly; always route through these helpers (or a `readStoredChoice`-based numeric variant for `bcf:timeline-zoom`) so private-browsing `SecurityError` throws are swallowed identically to the existing 7 keys.

### `matchMedia`-driven module-scope constant, computed once before first `render()`
**Source:** `web/app.js:127-132` (`PREFERS_REDUCED_MOTION`)
**Apply to:** `app.layoutMode` detection (`MOBILE_MQ`/`PORTRAIT_MQ`) — same "compute once at module load, never write from inside a render function" discipline.

### Post-mount DOM-ref caching, called only from inside `render()`
**Source:** `web/app.js:2524-2549` (`cachePlaybackDomRefs`), called at `web/app.js:889`
**Apply to:** Gesture attach/teardown inside `renderMobilePortrait`/`renderMobileLandscape` — same "only ever called from the render pass, never from an event listener" rule that prevents the pointer-capture-loss failure mode (RESEARCH.md Pitfall/Anti-Pattern: "Calling `render()` from inside a `pointermove`/`onSwipeStep` callback").

### Single extend-in-place `migratePreviewStorage()` version-bump purge
**Source:** `web/app.js:315-323`
**Apply to:** All storage-schema changes this phase — extend the one purge array and bump `STORAGE_VERSION`; never add a second migration function or a second version constant.

### `window.__bcfPrefs` bridge for the ported `haptic()` helper (open decision, must be resolved in the plan)
**Source:** `design/mobile-ux/prototype/gestures.js:21-24` reads `window.__bcfPrefs?.haptics`; this global does not exist anywhere in `web/app.js` today (verified: no match).
**Apply to:** `web/mobile-gestures.js` port. Two resolutions, either acceptable (RESEARCH.md Architecture Pattern 3):
```js
// Option A — minimal bridge, keeps mobile-gestures.js byte-for-byte verbatim:
Object.defineProperty(window, "__bcfPrefs", { get: () => ({ haptics: app.haptics }) });
```
Option B: adapt `haptic()`'s call sites in the ported file to accept a `haptics` flag parameter instead (a small, intentional deviation from "verbatim"). The plan must pick one — leaving it unresolved silently no-ops the `bcf:haptics` toggle on Android Chrome (D-11 already makes this harmless on iOS, since `navigator.vibrate` is unsupported there regardless).

### Single canonical breakpoint string — no second copy
**Source:** `web/style.css:360` (`@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px)`)
**Apply to:** `MOBILE_MQ`/`PORTRAIT_MQ` construction in `web/app.js` — the JS `matchMedia` argument must be character-identical to this CSS string (D-06). Never hand-roll a second `innerWidth`/`innerHeight` check as a "just in case" fallback.

## No Analog Found

None — every file this phase touches or creates has a direct, concrete analog already in the repository (existing code, the mobile-ux prototype, or the existing test harness). This is consistent with RESEARCH.md's "Don't Hand-Roll" table: every piece of infrastructure Phase 1 needs already exists in some form built for exactly this purpose.

## Metadata

**Analog search scope:** `web/`, `tests/`, `design/mobile-ux/` (per orchestrator instruction — `data/` excluded and not needed for this phase)
**Files scanned:** `web/app.js` (2792 lines, targeted reads: 50-190, 252-326, 870-925, 2524-2563, 2770-2792), `web/index.html` (15 lines, full), `web/style.css` (targeted read: 335-369), `design/mobile-ux/prototype/gestures.js` (198 lines, full), `tests/helpers/web_runtime_site.py` (targeted read: 1-80), `tests/test_web_app_integration.py` (targeted read: 1-90)
**Pattern extraction date:** 2026-07-25
```
