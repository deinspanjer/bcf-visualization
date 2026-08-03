---
phase: 01-mobile-state-gesture-plumbing
reviewed: 2026-07-26T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - web/mobile-gestures.js
  - web/app.js
  - web/mobile.css
  - web/index.html
  - tests/helpers/web_runtime_site.py
  - tests/test_mobile_plumbing.py
  - tests/test_desktop_smoke.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 1 mobile plumbing additions: the byte-identical `web/mobile-gestures.js` port (confirmed identical to `design/mobile-ux/prototype/gestures.js` via `diff`), the new `bcf:*` state/storage plumbing and layout-mode/gesture-attach lifecycle appended to `web/app.js`, the new `web/mobile.css` foundation, the two-line `web/index.html` wiring, and the new/extended test suite (`tests/test_mobile_plumbing.py`, `tests/test_desktop_smoke.py`, `tests/helpers/web_runtime_site.py`).

I did not find any Critical/BLOCKER-grade defects — no evidence of desktop CSS/render functions being touched, the `MOBILE_LAYOUT_QUERY` JS constant is character-identical to the new `mobile.css` `@media` query, `migratePreviewStorage()` correctly extends the purge list and bumps `STORAGE_VERSION` to `"3"`, and every new/extended `localStorage` access path is wrapped in the existing `try {} catch {}` convention. The rAF-coalesced layout-mode detector (`onLayoutMaybeChanged`) correctly re-reads `detectLayoutMode()` at fire time rather than trusting stale event data, and coalesces the three separate listeners (`MOBILE_MQ`, `PORTRAIT_MQ`, `orientationchange`) into a single scheduled frame, so I did not find a race there either.

I did find a genuine gesture-listener lifecycle gap (mobile→desktop transitions never invoke `mobileGestureTeardown`), a type-mismatch footgun in a setter explicitly documented as the future Settings-UI contract point, some inherited-but-real dead code in the gesture module, and a couple of lower-priority quality/consistency items (cache-busting convention, unused state fields, duplicated test helpers).

## Warnings

### WR-01: Gesture listeners are never torn down when leaving mobile layout mode

**File:** `web/app.js:921-928`, `web/app.js:2838-2852`
**Issue:** `attachMobileGestureProbes()` — which is the *only* call site that ever invokes `app.mobileGestureTeardown()` — is called exclusively from inside the `if (app.layoutMode !== "desktop")` branch of `render()`:

```js
if (app.layoutMode !== "desktop") {
  root.append(el("div", { class: "mobile-gesture-probe", ... }));
  attachMobileGestureProbes();
}
```

When a layout transition goes mobile → desktop, `render()` takes the `else` path implicitly (the whole block is skipped), so `app.mobileGestureTeardown` — still holding the closure/listeners bound to the just-removed (now DOM-detached) probe element from the previous mobile render — is never called. It sits on `app` (a long-lived global) until the *next* mobile-mode render, at which point `attachMobileGestureProbes()` finally calls the stale teardown before attaching fresh listeners. In practice this is currently non-functional (a detached node cannot receive dispatched pointer events, so there is no double-fire risk), but it directly contradicts the function's own doc-comment intent ("Teardown lives on `app`... so it survives to be invoked defensively before re-attach") and leaves a real 4-listener leak + retained detached DOM node for the entire duration of any desktop session that follows a mobile session, which will only grow if Phase 2/3 attach gestures to more than one probe element.
**Fix:** Tear down unconditionally when leaving mobile mode, not just defensively before re-attaching:
```js
if (app.layoutMode !== "desktop") {
  root.append(el("div", { class: "mobile-gesture-probe", ... }));
  attachMobileGestureProbes();
} else if (typeof app.mobileGestureTeardown === "function") {
  app.mobileGestureTeardown();
  app.mobileGestureTeardown = null;
}
```

### WR-02: `setMobileTimelineZoom` uses a type-strict allow-list that will silently reject the string values a real `<select>`/input control produces

**File:** `web/app.js:2811-2815`
**Issue:** The function is explicitly documented as "the MOBF-04 written-on-change contract Phase 2's Settings UI calls":
```js
function setMobileTimelineZoom(value) {
  if (![1, 2, 4, 8].includes(value)) return; // allow-list; ignore anything else
  app.mobileTimelineZoom = value;
  store(LS_MOBILE_TIMELINE_ZOOM, value);
}
```
`.includes()` uses strict equality, and the array contains numbers. A native `<select>` or radio input's `.value` is always a string (`"4"`, not `4`). The first real Phase 2 wiring that does the obvious thing (`setMobileTimelineZoom(event.target.value)` or `setMobileTimelineZoom(select.value)`) will silently no-op on every legitimate value with no console warning or thrown error — the preference will appear to do nothing, and this will be non-obvious to debug because the guard is silent by design.
**Fix:** Coerce before validating:
```js
function setMobileTimelineZoom(value) {
  const n = Number(value);
  if (![1, 2, 4, 8].includes(n)) return;
  app.mobileTimelineZoom = n;
  store(LS_MOBILE_TIMELINE_ZOOM, n);
}
```

### WR-03: New mobile assets bypass the project's cache-busting convention

**File:** `web/index.html:10,14`
**Issue:** `style.css` and `app.js` are both loaded with an explicit `?v=phase9-info-link` cache-busting query parameter:
```html
<link rel="stylesheet" href="style.css?v=phase9-info-link" />
...
<script type="module" src="app.js?v=phase9-info-link"></script>
```
The two files added this phase do not follow that convention:
```html
<link rel="stylesheet" href="mobile.css" />
...
<script src="mobile-gestures.js"></script>
```
This phase itself is fine (the reference is brand-new in `index.html`, so it can't be stale). But going forward, any future edit to `mobile.css` or `mobile-gestures.js` content that isn't paired with an `index.html` edit will not bust caches for clients whose CDN/browser cache is keyed on URL — exactly the class of bug the existing `?v=` convention exists to prevent for the other two files.
**Fix:** Add the same `?v=...` query convention to both new asset references, and bump it alongside `app.js`'s version string on future edits.

### WR-04: `_chromium_browser_or_skip` / `_page_with_console_capture` are duplicated verbatim (mod. default viewport) across test files

**File:** `tests/test_mobile_plumbing.py:23-57`, `tests/test_desktop_smoke.py:35-73`
**Issue:** Both new/extended test modules define byte-for-byte identical `_chromium_browser_or_skip` helpers, and near-identical `_page_with_console_capture` helpers (differing only in default viewport and doc comment). This is exactly the kind of duplication that drifts silently — e.g. if the Playwright skip-detection string (`"Executable doesn't exist"` / `"playwright install"`) ever needs to change, it now has to change in (at least) two places, and nothing enforces that.
**Fix:** Extract both helpers into `tests/helpers/web_runtime_site.py` (or a new `tests/helpers/playwright_site.py`) parameterized by default viewport, and import from both test modules.

## Info

### IN-01: Dead `pendingTapTimer` variable in the ported gesture module

**File:** `web/mobile-gestures.js:39,69,108,123,138`
**Issue:** `pendingTapTimer` is declared (`let pendingTapTimer = null;`) and defensively cleared in four separate places (`onMove`'s swipe-engage branch, `onUp`'s double-tap branch, `onCancel`, and the teardown closure), but it is never assigned the return value of a `setTimeout(...)` call anywhere in the file. All four `if (pendingTapTimer)` checks are permanently unreachable dead code — a leftover from an earlier design (delayed single-tap firing to disambiguate from double-tap) superseded by the current "fire single-tap immediately" approach documented at line 114-116. Functionally harmless (the checks are no-ops), but it misleads readers into thinking a debounce exists where none does.
**Note:** Per the review brief, `web/mobile-gestures.js` must stay byte-identical to `design/mobile-ux/prototype/gestures.js` (confirmed identical via `diff`) — any fix belongs in the prototype source file, not a standalone edit to the production copy, otherwise the two will diverge.
**Fix:** In the prototype source, either wire up the timer for real (if delayed-tap disambiguation is still wanted for some case) or remove `pendingTapTimer` and its four dead checks entirely.

### IN-02: Unused `app` state fields added this phase

**File:** `web/app.js:120-122`
**Issue:** `helpOpen: false`, `settingsOpen: false`, and `chromeHidden: false` are added to the `app` state object but are not read or written anywhere else in the file (confirmed via full-file search). They appear to be forward-provisioned for Phase 2's Settings/Help UI. Not a bug, but currently untested dead state with no consumer.
**Fix:** No action required if intentionally pre-provisioned per the phase plan; consider a one-line comment noting they're Phase 2 placeholders (similar to the existing "Phase 1 plumbing" comment style already used elsewhere in this section) so a future reader doesn't mistake them for orphaned/incomplete work.

### IN-03: `window.__bcfPrefs` accessor is non-configurable and getter-only

**File:** `web/app.js:2792-2799`
**Issue:**
```js
Object.defineProperty(window, "__bcfPrefs", {
  get: () => ({ haptics: app.haptics, ... }),
});
```
`Object.defineProperty` defaults unspecified descriptor flags to `false`, so this property is both non-writable-via-assignment (any `window.__bcfPrefs = ...` elsewhere will throw a `TypeError` in strict mode — and ES module top-level code is always strict) and non-configurable (it can never be redefined or deleted later, e.g. by a future test harness needing to stub it). No current code attempts either, so this is not an active bug, but it's a landmine for anyone who later tries to monkey-patch or reset this property (including from a test).
**Fix:** If this is intentionally read-only-forever, a brief comment saying so would save a future debugging session; otherwise consider `configurable: true` to leave the door open for tests to redefine it.

---

_Reviewed: 2026-07-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
