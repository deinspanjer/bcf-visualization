# Phase 4: Mobile Cutover & Accessibility - Pattern Map

**Mapped:** 2026-08-02
**Files analyzed:** 9 (2 deletions-only, 3 modified, 1 new static-HTML surface, 3 new/extended test files)
**Analogs found:** 5 / 9 (2 have partial/contrasting analogs, 2 have explicitly NO analog — called out below)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `web/app.js` (deletion: `renderPortraitBanner` + call site + `LS_PORTRAIT_DISMISSED`) | component (render fn) | CRUD (delete) | **none — first deletion this milestone** | no-analog (see below) |
| `web/app.js` (live region DOM node + update helper) | component + service (DOM mutation) | event-driven | `updatePlaybackFrame()` incremental-update shape; structurally, `resetMobileChromeHideTimer()`'s per-render-attached DOM node | no-analog for the ARIA mechanism, role-match for the "incremental DOM write off an existing update function" shape |
| `web/app.js` (keyboard early-branch, D-47) | controller (event handler) | request-response (keydown → state mutation) | `updatePlaybackFrame()`'s mobile early-return; the *existing* body of the same `keydown` listener (`app.js:4564-4584`) | exact — same file, same function, same "layoutMode gate then return" shape |
| `web/app.js` (`resetMobileChromeHideTimer` 8000ms doubling) | service (timer/util) | event-driven | `currentFocusAnimT()`'s existing `PREFERS_REDUCED_MOTION` branch (`app.js:237`) | exact |
| `web/style.css` (delete `.portrait-banner` + stale media block) | config/style | CRUD (delete) | **none — the one sanctioned frozen-CSS deletion** | no-analog |
| `web/mobile.css` (`.mobile-cinema-scrub-fab::before` hit-area) | style | transform (CSS box model) | `.mobile-icon-btn.compact` (`mobile.css:305-310`) | contrasting case — same *goal*, opposite *technique*, excerpt both |
| `web/mobile.css` (`.mobile-live-region` hiding rule) | style | — | none in this codebase (`aria-live`/sr-only pattern appears zero times) | no-analog — use the UI-SPEC's locked property table verbatim |
| `index.html` (title chip, author credit, `?` button + `<dialog>`) | component (static HTML) | request-response (dialog open/close) | `web/app.js`'s `renderMobileHelpOverlay()` (content source, not importable) + `index.html`'s own existing `.actions`/`.secondary-link` markup | role-match (content), no-analog (dialog markup/JS — no `<dialog>` anywhere in repo) |
| `tests/test_lighthouse_accessibility.py` | test | batch (CLI shell-out + JSON parse) | none — new test *shape* (shells to `npx`, not Playwright-only) | no-analog |
| `tests/test_landing_page.py` | test | request-response | `tests/test_mobile_portrait.py`'s `_page_with_console_capture` harness — but targeting `index.html` not `staged_web_runtime_site()`'s `/web/` fixture | partial — harness pattern reusable, fixture target is new |
| `tests/test_freeze_proof.py` | test | batch (git diff wrapper) | none — new test shape (shells to `git diff`, not a browser test) | no-analog |
| `tests/test_mobile_portrait.py` / `test_mobile_landscape.py` (aria-live, keyboard, reduced-motion, visibilitychange, FAB-offset-click additions) | test | request-response | `test_mobile_portrait.py:520-534` (`getBoundingClientRect()` tap-target pattern) | exact for structure, **explicit anti-pattern** for the FAB case (see below) |

---

## Pattern Assignments

### `web/app.js` — Banner deletion (D-37/D-38)

**Analog:** none. Every prior phase in this milestone ADDED code; this is the first deletion. Treat as a pure subtraction task, not a "write new code following pattern X" task.

**Exact deletion sites** (verified against `HEAD=ef21947` by RESEARCH; re-grep at execute time if the branch has moved):
```javascript
// app.js:62 — delete
const LS_PORTRAIT_DISMISSED = "bcf:portrait-dismissed";

// app.js:145 — delete (inside the `app` state object literal)
portraitDismissed: readStoredBoolean(LS_PORTRAIT_DISMISSED, false),

// app.js:428 — delete from migratePreviewStorage()'s clear-list
LS_PORTRAIT_DISMISSED,

// app.js:1098 — delete from renderAppShell() (the ONE sanctioned §0.2 edit)
app.portraitDismissed ? null : renderPortraitBanner(),

// app.js:1228-1233 — delete the whole function
function renderPortraitBanner() { ... }
```
**Do NOT** bump `STORAGE_VERSION` for this (Pitfall 5 — 34 test-fixture sites across 4 files seed the literal `"3"`; the orphaned `bcf:portrait-dismissed` key has zero functional impact once nothing reads it).

---

### `web/style.css` — the one sanctioned frozen-CSS deletion (D-37/D-38)

**Analog:** none — §0.4 otherwise permits only *adding* rules. This is a scoped, surgical deletion, not a pattern to imitate elsewhere.

```css
/* web/style.css:325-362 — delete this whole block verbatim:
   - line 325: comment
   - lines 326-359: .portrait-banner + its .is-visible/strong/button/
     button:hover/svg child-selector rules
   - lines 360-362: the stale `@media (max-width: 900px), …` wrapper
   Line 363 (`.app-main {`) must survive untouched immediately after. */
```
**Verification is the pattern here, not code:** `git diff --exit-code 57d2768 HEAD -- web/style.css` must show *exactly* this hunk and nothing else — this is the freeze-proof test's whole job (see `tests/test_freeze_proof.py` below).

---

### `web/app.js` — Live region DOM node + update helper (D-42..D-45)

**Analog:** no direct precedent (`aria-live` appears zero times in the codebase, confirmed by grep). Two partial structural analogs to combine:

1. **DOM node placement** — follow the per-render-attached-node pattern any `renderMobilePortrait`/`renderMobileLandscape` child uses (mount once per full render, keep a reference on `app.dom.*` for later reads/writes), the same convention `app.dom.mobileCinemaScrub` already uses (referenced in `resetMobileChromeHideTimer()`, `app.js:4407` area).
2. **Incremental text update** — model the update helper on `updatePlaybackFrame()`'s "compute → write into an existing node's text" shape, but the live region is written from **user-gesture callback sites**, not the rAF tick.

**Exact trigger sites to hook (UI-SPEC's locked trigger table, all pre-existing calls to `setWordPos`):**
```javascript
// app.js:4419-4424 — onDoubleTap
onDoubleTap: () => {
  const target = lastRollAtWord(app.wordPos);
  if (target) setWordPos(target.word_position);   // ← announce here, after setWordPos
  if (!app.playing) togglePlayback();
  resetMobileChromeHideTimer();
},
// app.js:4428-4432 — onSwipeStep
onSwipeStep: dir => {
  const next = rollStepFrom(app.wordPos, dir);
  if (next) setWordPos(next.word_position);        // ← announce here
  resetMobileChromeHideTimer();
},
// app.js:4467 area — onScrubEnd (NOT the per-move onScrub callback at :4443-4466 —
// that fires on every pointermove and must stay silent per D-42)
onScrubEnd: () => {
  app.mobileScrubPanPct = null;
  persistBookmarkNow();
  // ← announce the settled position here, using the LAST target from onScrub
},
```
Plus the new keyboard branch (below) calls the same announce helper.

**Numbering expression — reuse verbatim, do not re-derive:**
```javascript
// app.js:4022-4028, mobileFieldLogRows() — the exact {n}/{total} expression
const total = app.data.story.rolls.length;
const idx = app.data.story.rolls.indexOf(roll);   // 0-based; announcement uses idx+1
```
Never `roll.roll_label` (null on 669/670) or any `*_ordinal` field.

**Outcome classification — reuse `rollMarkerModel(roll)` from `web/viz-model.js:58-82`,** add it to `app.js`'s existing viz-model import block (it imports `paidRollPerks`, `perkDisplayLabel`, `rollTotalCost` already but not `rollMarkerModel`). Do not write a second miss/multi-grab classifier.

**Hiding technique (UI-SPEC locked, `web/mobile.css`, no analog in codebase):**
```css
.mobile-live-region {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  margin: -1px;
  border: 0;
  padding: 0;
}
```
Prohibited: `display: none`, `visibility: hidden`, `hidden` attribute, `aria-hidden="true"`, `content-visibility: hidden`, zero width/height — every one silences the announcement while leaving the node present (this is the single most failure-prone value in the phase per UI-SPEC).

**Update mechanism (load-bearing correctness detail):**
```javascript
// Two synchronous writes in the same tick, so a repeat-landing on the same
// roll still re-announces (screen readers only fire on a text MUTATION):
liveRegionEl.textContent = "";
liveRegionEl.textContent = message;
```

---

### `web/app.js` — Keyboard early-branch (D-46/D-47/D-48)

**Analog:** exact — `updatePlaybackFrame()`'s mobile early-return is the named precedent, and the insertion is literally inside the SAME existing function this phase's other work already reads.

**Existing handler in full (`app.js:4564-4584`), insertion point marked:**
```javascript
window.addEventListener("keydown", event => {
  if (!app.data) return;
  const active = document.activeElement;
  const tag = active?.tagName;
  const editable = active?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  if (event.key === " ") {
    if (editable) return;
    if (tag === "BUTTON") active.blur();
    togglePlayback();
    event.preventDefault();
    return;
  }
  if (editable) return;
  // ↓↓↓ INSERT the D-47 mobile early-branch HERE, before desktop word-stepping ↓↓↓
  if (app.layoutMode !== "desktop") {
    if (event.key === "ArrowRight") {
      const next = rollStepFrom(app.wordPos, 1);     // existing helper, app.js:814
      if (next) setWordPos(next.word_position);
      event.preventDefault();
      return;
    }
    if (event.key === "ArrowLeft") {
      const next = rollStepFrom(app.wordPos, -1);
      if (next) setWordPos(next.word_position);
      event.preventDefault();
      return;
    }
    if (event.key === "Home") {
      // Mirrors onDoubleTap's exact body (app.js:4419-4424) — "live edge,"
      // NOT word 0, which is what desktop's own Home does two lines below.
      const target = lastRollAtWord(app.wordPos);     // existing helper, app.js:798
      if (target) setWordPos(target.word_position);
      if (!app.playing) togglePlayback();
      event.preventDefault();
      return;
    }
    if (event.key === "?") {
      openMobileSurface("help");   // already toggles closed if already open
      event.preventDefault();
      return;
    }
  }
  const step = event.shiftKey ? 2000 : 10000;
  if (event.key === "ArrowRight") setWordPos(app.wordPos + step);
  else if (event.key === "ArrowLeft") setWordPos(app.wordPos - step);
  else if (event.key === "PageDown") setWordPos(app.wordPos + 100000);
  else if (event.key === "PageUp") setWordPos(app.wordPos - 100000);
  else if (event.key === "Home") setWordPos(0);
  else if (event.key === "End") setWordPos(app.data.story.total_words);
});
```
**Do NOT add a second `window.addEventListener("keydown", ...)`** — D-07's single-attach discipline forbids competing listeners on the same key. `Space` needs zero changes; it is already layout-agnostic.

---

### `web/app.js` — Auto-hide 8000ms doubling under reduced motion (MOBX-04)

**Analog:** exact — reuse the existing module-level `PREFERS_REDUCED_MOTION` constant already used by desktop's `currentFocusAnimT()`.

```javascript
// Source: app.js:236-239 (existing, verbatim, DO NOT re-query matchMedia)
const PREFERS_REDUCED_MOTION = (typeof window !== "undefined"
  && typeof window.matchMedia === "function"
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

// Edit inside the EXISTING resetMobileChromeHideTimer() (app.js:4336 area):
function resetMobileChromeHideTimer() {
  clearTimeout(app.mobileChromeHideTimer);
  app.mobileChromeHideTimer = null;
  if (app.layoutMode === "landscape" && app.playing && !app.mobileSurface) {
    const base = window.GestureConstants?.CHROME_AUTOHIDE ?? 4000;
    const delay = PREFERS_REDUCED_MOTION ? base * 2 : base;   // MOBX-04, new
    app.mobileChromeHideTimer = setTimeout(() => {
      app.chromeHidden = true;
      app.dom.mobileCinemaScrub?.classList.add("is-hidden");
    }, delay);
  }
}
```
Do NOT touch `web/mobile-gestures.js` (byte-frozen, D-17) and do NOT add a second `matchMedia` query.

---

### `web/mobile.css` — `.mobile-cinema-scrub-fab` hit-area (D-39) — CONTRASTING pair, excerpt both

**Analog A (what NOT to copy for the FAB, but IS correct elsewhere):** `.mobile-icon-btn.compact`, `mobile.css:305-310`:
```css
.mobile-icon-btn.compact {
  box-sizing: content-box;
  width: 36px;
  height: 36px;
  padding: 4px;
}
```
This works because padding grows the element's *own* hit-tested box — verifiable directly by `getBoundingClientRect()` (proven at `tests/test_mobile_portrait.py:520-534`). It works cleanly here because the background is a subtle, near-invisible panel fill — a few extra px of it is unremarkable.

**Analog B / actual technique for the FAB — locked by UI-SPEC, no prior instance in the codebase:**
```css
/* Existing rule, mobile.css:695-713 — gains ONE new declaration: */
.mobile-cinema-scrub-fab {
  position: relative;   /* NEW — required so ::before resolves against the button */
  width: 40px;           /* UNCHANGED — painted size stays locked */
  height: 40px;
  border-radius: 50%;
  background: var(--cyan);
  box-shadow: 0 0 22px rgba(92, 244, 255, 0.55), 0 6px 22px rgba(0, 0, 0, 0.5);
  /* ...rest unchanged */
}

/* NEW rule */
.mobile-cinema-scrub-fab::before {
  content: "";
  position: absolute;
  inset: -4px;          /* → 48x48 hit-testable box */
  /* no background, no box-shadow, no border-radius — a transparent
     pseudo-element's box still dispatches clicks to its host, but does
     not paint anything, so the circle+glow stay pixel-identical */
}
```
**Why NOT padding here (Pitfall 3):** `.mobile-cinema-scrub-fab`'s `background`/`box-shadow`/`border-radius` paint through the padding box by default — padding-based expansion would visibly grow the glowing circle, directly violating D-39. This is the ONE element in the phase where `::before` is the *correct*, not just *permitted*, choice.

**Verification consequence (do not get this wrong in the test file):** `getBoundingClientRect()` on `.mobile-cinema-scrub-fab` will always report 40×40 — a `::before`'s absolute-position overflow never changes its host's own layout box. **Never write a `getBoundingClientRect() >= 44` assertion for this element** — it will always fail (or be quietly, wrongly relaxed to 40). Verify via `page.mouse.click()` at an offset 2-4px outside the visible circle and assert the FAB's handler fired.

---

### `index.html` — Landing-page chip, credit, `?` dialog (MOBX-02)

**Analog:** No dialog/help markup exists anywhere in `index.html` today (read in full above — 359 lines, zero JS, zero `<dialog>`). Content source is `renderMobileHelpOverlay()` in `web/app.js` (NOT imported — `index.html` shares no JS module with `web/`). Structural/CSS analog is `index.html`'s own existing `.actions`/`.secondary-link`/`.message-panel` local idiom.

**Existing external-link convention to mirror exactly (already-correct precedent in the same file, `index.html:353`):**
```html
<a class="secondary-link" href="https://github.com/deinspanjer/bcf-visualization" target="_blank" rel="noopener noreferrer">View source</a>
```
Apply the identical `target="_blank" rel="noopener noreferrer"` pattern to the new SV/FF/AO3 links inside the help dialog (their hrefs come from `web/app.js`'s `STORY_LINKS` constant, lines 116-119 — copy the literal URLs; flagged by UI-SPEC as an accepted duplication risk, not a shared module).

**Locked insertion point (UI-SPEC):** first child of `.message-panel`, immediately before `.constellation`, i.e. before `<p class="subject">` at `index.html:341`.

**New markup shape (per UI-SPEC's locked values — 44×44 built at-size, no hit-area trick needed since this is new markup, not a retrofit):**
```html
<div class="landing-meta-row">
  <span class="landing-title-chip">Brockton's Celestial Forge</span>
  <span class="landing-author-credit">by LordRoustabout</span>
  <button type="button" class="landing-help-btn" aria-label="Help" title="About & help"
          onclick="this.nextElementSibling.showModal && this.nextElementSibling.showModal()">?</button>
  <dialog id="landing-help-dialog" aria-label="About & help">
    <!-- title/byline/source-links/pointer-line/CTA per UI-SPEC Copywriting Contract -->
  </dialog>
</div>
<noscript><style>.landing-help-btn{display:none}</style></noscript>
```
Plus one inline `<script>` (UI-SPEC-mandated, since `<dialog>` does not restore focus on close in all browsers):
```javascript
document.getElementById('landing-help-dialog')
  .addEventListener('close', () => document.querySelector('.landing-help-btn').focus());
```
This is genuinely new territory — `index.html` has zero JS today; this dozen-line inline script is the first.

---

### `tests/test_lighthouse_accessibility.py` — no analog

**Analog:** none — this is a new test *shape* in the suite (shells to `npx --yes lighthouse`, parses JSON, asserts a score threshold, not a Playwright-DOM-assertion test). Reuse `staged_web_runtime_site()` from `tests/helpers/web_runtime_site.py` (already used by every Phase 1-3 test) to get a real `http://` URL for Lighthouse to fetch against — Lighthouse needs `http://`, not `file://`, to load `visualization_facts.json` correctly. This is the "Don't Hand-Roll" call from RESEARCH — do not write a bespoke `http.server` invocation.

---

### `tests/test_landing_page.py` — partial analog

**Analog:** `tests/test_mobile_portrait.py`'s `_page_with_console_capture(browser, site, storage=..., viewport=...)` harness pattern is reusable for browser setup/console-capture, but **`site` must point at repo-root `index.html`, not `staged_web_runtime_site()`'s `/web/` target** — no existing fixture serves the repo root today; this is a genuinely new fixture surface.

---

### `tests/test_freeze_proof.py` — no analog

**Analog:** none — wraps `git diff --exit-code 57d2768 HEAD -- web/style.css` (and optionally the `renderAppShell()`/`renderPortraitBanner()` deletion sites in `web/app.js`) as a pytest assertion instead of a one-off shell command. `57d2768` is the pre-Phase-1 base commit, NOT Phase 3's `22bdd8c` — use the milestone-wide base per D-37's "verify against the pre-milestone base, not just the working tree."

---

### `tests/test_mobile_portrait.py` / `test_mobile_landscape.py` additions

**Analog — the 44px tap-target pattern to extend for every case EXCEPT the FAB:**
```python
# test_mobile_portrait.py:520-534, existing, verbatim pattern
boxes = page.eval_on_selector_all(
    ".mobile-dock-transport button",
    "els => els.map(el => { const r = el.getBoundingClientRect(); "
    "return { width: r.width, height: r.height }; })",
)
for box in boxes:
    assert box["width"] >= 44
    assert box["height"] >= 44
```
**Anti-pattern warning (VALIDATION.md finding #3, repeated here so it isn't missed):** do NOT reuse this exact pattern for `.mobile-cinema-scrub-fab` — its host box is permanently 40×40 by design; a `getBoundingClientRect() >= 44` assertion on it will always fail. Use an offset `page.mouse.click()` assertion instead (see the FAB section above).

**New assertion categories with NO existing analog anywhere in the suite** (grep confirmed zero hits): `aria-live` presence/content assertions, keyboard-event assertions for mobile layout modes, `page.emulate_media(reduced_motion="reduce")` usage (verify this exact Playwright 1.59.0 API name before relying on it — not independently confirmed this session), `visibilitychange` dispatch assertions. Model these structurally on the existing `_page_with_console_capture(browser, site, storage=..., viewport=...)` fixture shape used throughout both files, since the harness pattern itself IS reusable even though the specific assertions are new.

---

## Shared Patterns

### Single global `keydown` listener (D-07/D-18 discipline)
**Source:** `web/app.js:4564` (the one and only `window.addEventListener("keydown", ...)`)
**Apply to:** the D-47 mobile branch — inserted inside this function, never as a second listener.

### `PREFERS_REDUCED_MOTION` single computation
**Source:** `web/app.js:236-239`
**Apply to:** the auto-hide timer doubling. Never add a second `matchMedia` call anywhere this phase touches.

### `rollMarkerModel(roll)` for outcome classification
**Source:** `web/viz-model.js:58-82`
**Apply to:** the live-region announcement's miss/multi-grab/hit branching. Never write a second `if (roll.outcome === "miss")` chain.

### `{n}`/`{total}` numbering expression
**Source:** `web/app.js:4022-4028` (`mobileFieldLogRows()`)
**Apply to:** the live-region announcement's roll count. Never `roll_label` or any `*_ordinal` field (three divergent numbering systems per project convention — see MEMORY.md "BCF roll numbering").

### `el()`-helper textContent-only DOM writes (XSS convention)
**Source:** established convention referenced throughout `app.js` (e.g. `mobileFieldLogSubChildren`'s comment: "every text fragment flows through `el()`'s `text` prop, never string-concatenated markup")
**Apply to:** the new live-region text node and any new landing-page dialog text — never `innerHTML`.

### `target="_blank" rel="noopener noreferrer"` on external links
**Source:** `index.html:353` (existing `.secondary-link`)
**Apply to:** the new SV/FF/AO3 links inside the landing-page help dialog.

---

## No Analog Found

| File / Change | Role | Data Flow | Reason |
|---|---|---|---|
| `web/app.js` banner deletion | component (deletion) | CRUD-delete | First deletion this milestone — every prior phase added code; there is no "how we deleted things" precedent to follow, only the surgical line-range list above |
| `web/style.css` `.portrait-banner` deletion | style (deletion) | CRUD-delete | The one sanctioned frozen-CSS edit; §0.4 otherwise permits only additions |
| `.mobile-live-region` ARIA hiding technique | style | — | `aria-live` appears zero times in the codebase; use UI-SPEC's locked property table verbatim, do not improvise a variant (`display:none`/`visibility:hidden`/0×0 all silently break it) |
| `index.html`'s `<dialog>` + inline `<script>` | component (static HTML + vanilla JS) | request-response | No `<dialog>` element and no inline `<script>` exists anywhere in `index.html` today — this is genuinely first-of-its-kind for this file |
| `tests/test_lighthouse_accessibility.py` | test | batch (CLI shell-out) | No prior test in the suite shells to an external CLI and parses its JSON output; every existing test is Playwright-DOM-only |
| `tests/test_freeze_proof.py` | test | batch (git diff) | No prior test wraps a `git diff` assertion |
| `tests/test_landing_page.py`'s target fixture | test | request-response | Every existing Playwright fixture (`staged_web_runtime_site`) targets `/web/`; none serves repo-root `index.html` |

## Metadata

**Analog search scope:** `web/app.js`, `web/mobile.css`, `web/style.css`, `web/viz-model.js`, `index.html`, `tests/test_mobile_portrait.py`, `tests/test_mobile_landscape.py`, `tests/test_desktop_smoke.py`
**Files scanned:** 8 (all read in full or via targeted non-overlapping ranges; no file exceeded 2,000 lines requiring Grep-first triage)
**Pattern extraction date:** 2026-08-02
