# Phase 1: Mobile State & Gesture Plumbing - Research

**Researched:** 2026-07-25
**Domain:** Vanilla-JS (no build step) mode-branched web app — layout-mode detection, pointer-event gesture plumbing, localStorage prefs migration, Playwright-based desktop regression smoke test
**Confidence:** HIGH — every claim below is grounded in a direct read of this repo's own `web/app.js`, `web/style.css`, `web/index.html`, `design/mobile-ux/*`, `tests/*`, `pyproject.toml`, `DEVELOPERS.md`, `AGENTS.md`, plus the three existing project-level research documents (`STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`), which are themselves HIGH-confidence for this codebase. No new external library research was needed — Phase 1 introduces zero new dependencies.

## Summary

This phase has almost no "go learn a new technology" risk — `.planning/research/{STACK,ARCHITECTURE,PITFALLS}.md` already did that work at the milestone level and it fully covers Phase 1's domain (Pointer Events, `matchMedia`, `touch-action`, `svh`/`dvh`, `localStorage` versioning). What Phase 1 actually needs is precise, line-level knowledge of the *current* `web/app.js`/`web/style.css` state so the plan can say exactly where each edit lands, plus a concrete design for two things CONTEXT.md left to auto-resolved defaults: the `attachSkyGestures`/`attachRailScrub` per-render attach lifecycle (D-07) and the Playwright desktop smoke test (D-10).

Both of those already have a load-bearing precedent in the codebase: `cachePlaybackDomRefs()` is called immediately after `root.append(renderAppShell())` inside `render()` (app.js:888-890) — mobile gesture attachment must follow the exact same call-after-mount shape, inside `renderMobilePortrait`/`renderMobileLandscape`, never in the `resize`/`matchMedia` handler that sets `app.layoutMode`. And a full Playwright + pytest + local-HTTP-server harness already exists (`tests/helpers/web_runtime_site.py` → `staged_web_runtime_site()`, consumed by `tests/test_web_app_integration.py`) — the D-10 smoke test is a new test module in that exact pattern, not a new tool or a new way of serving the app.

One concrete discrepancy surfaced during research and must be resolved in the plan, not left ambiguous: `INTEGRATION_PLAN.md` §3.1 says to "**Remove** `LS_PORTRAIT_DISMISSED` from `migratePreviewStorage()` purge list" — but the *actual current code* (app.js:315-323) does **not** contain `LS_PORTRAIT_DISMISSED` in that purge list today. CONTEXT.md D-09 and the phase's own success criterion #4 ("`bcf:portrait-dismissed` purged after STORAGE_VERSION bump") require the opposite of the plan's literal wording: `LS_PORTRAIT_DISMISSED` must be **added** to the purge list so the stale value is cleared on the v2→v3 bump. Follow D-09 and the success criterion, not the plan's stale literal instruction — record this as a plan deviation.

**Primary recommendation:** Implement `app.layoutMode` detection as a single `matchMedia`-driven module-scope listener (mirroring the existing `PREFERS_REDUCED_MOTION` pattern at app.js:130-132), computed once before the first `render()` call; attach/detach gesture listeners strictly inside the two new `renderMobile*` functions after DOM mount (mirroring `cachePlaybackDomRefs`); extend `migratePreviewStorage()`'s purge array and bump `STORAGE_VERSION` to `"3"`; and add a new `tests/test_desktop_mobile_smoke.py` (or similar) built on the existing `staged_web_runtime_site()` fixture, asserting the §0.5 checklist via DOM/computed-style probes plus the existing `window.__bcfRenderStats.structuralRenders` counter to catch spurious re-renders across a resize round-trip.

## Architectural Responsibility Map

This is a single-tier static web app with no backend for this phase — every capability lives in the Browser/Client tier. The table below maps capability to sub-layer *within* that tier, since that's the meaningful boundary here.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `app.layoutMode` detection (`matchMedia`) | Browser/Client — module-scope listener layer | — | Runs once at script load + on breakpoint crossing; must agree with CSS, not with any server |
| `render()` dispatch branch | Browser/Client — render/dispatch layer | — | Existing single branch point (app.js:873); this phase only adds the `layoutMode` read, doesn't touch the frozen desktop branch |
| Gesture interpretation (`mobile-gestures.js`) | Browser/Client — new standalone module, no app-state knowledge | — | Pure pointer-event → semantic-callback translation; called by, not merged into, render functions |
| Gesture attach/detach lifecycle | Browser/Client — inside `renderMobilePortrait`/`renderMobileLandscape` | — | Must run post-mount, same render pass, same convention as `cachePlaybackDomRefs` |
| `bcf:*` preference persistence | Browser/Client — `localStorage` | — | No server-side storage exists or is being added; `STORAGE_VERSION`-gated purge is the only "migration" mechanism |
| Mobile CSS foundation (`touch-action`, `svh`/`dvh`, safe-area insets) | Browser/Client — CSS layer | — | Static stylesheet, no build step; new rules must out-cascade (not edit) three existing responsive `@media` blocks |
| Desktop freeze surface (`renderAppShell` + `render*` set) | Browser/Client — existing render layer, read-only | — | Explicitly frozen per plan §0.2; Phase 1 must not touch these bodies |
| Desktop smoke test | Test/CI tooling (Python) | Browser/Client (drives it) | Playwright drives the same Browser/Client app under a local HTTP server; no new runtime dependency |

## Standard Stack

No new libraries. This phase is 100% native browser APIs plus the project's existing Python/pytest/Playwright test stack, all already installed.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pointer Events (native) | N/A (browser API) | Gesture input | Already the exclusive input model in `design/mobile-ux/prototype/gestures.js`; no polyfill needed on any current engine `[CITED: .planning/research/STACK.md]` |
| `window.matchMedia` (native) | N/A | Layout-mode + reduced-motion detection | Already used once in this file for `prefers-reduced-motion` (app.js:130-132); extending the same pattern to the mobile breakpoint keeps JS and CSS provably in sync `[VERIFIED: web/app.js:130-132, direct read]` |
| `localStorage` (native) | N/A | Preference persistence | Existing `LS_*`/`STORAGE_VERSION`/`migratePreviewStorage()` pattern (app.js:55-64, 315-323) — extend, don't replace `[VERIFIED: web/app.js, direct read]` |
| `playwright` (Python) | already in `pyproject.toml` `[project.optional-dependencies].dev` | Desktop smoke test | Already installed in `.venv`; `playwright.sync_api` Chromium launch verified working in this environment during research (`chromium launch ok`) `[VERIFIED: .venv/bin/python chromium launch test, this session]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `pytest-asyncio` | already in `pyproject.toml` dev extras | Test runner | Already the only test runner in the project; new smoke test is a plain pytest module under `tests/` |
| `http.server` / `socketserver` (Python stdlib) | N/A | Local static-site serving for Playwright | Already implemented as `_serve()` inside `tests/helpers/web_runtime_site.py` — reuse `staged_web_runtime_site()`, do not write a second server helper |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `matchMedia` layout detection | `screen.orientation` API | Rejected — patchy historical Safari support; project's own STACK.md and INTEGRATION_PLAN.md already settled on `matchMedia` `[CITED: .planning/research/STACK.md]` |
| Playwright via existing pytest harness | A new/separate Node-based Playwright Test project | Rejected — would introduce a `package.json`/Node toolchain the project explicitly doesn't have for `web/`; the Python pytest+Playwright pattern is already proven in `tests/test_web_app_integration.py` |

**Installation:**
```bash
# Nothing new to install — verify the existing environment instead:
.venv/bin/python -c "from playwright.sync_api import sync_playwright; \
  p = sync_playwright().start(); b = p.chromium.launch(); b.close(); p.stop()"
node --check web/app.js   # existing JS syntax gate (DEVELOPERS.md "Web app checks")
```

**Version verification:** No new packages recommended, so no new-package version check is required. Confirmed in-session that `.venv/bin/python` exists, the `playwright` module imports, and `chromium.launch()` succeeds — the D-10 smoke test has no environment blocker.

## Package Legitimacy Audit

**Not applicable — this phase installs zero new packages.** All work uses native browser APIs already vetted at the milestone level (`.planning/research/STACK.md`) plus `playwright`/`pytest`, both already present in `pyproject.toml`'s `dev` extras and already installed in `.venv`. No `npm view` / `pip index versions` check is needed because nothing new is being added to either manifest.

## Architecture Patterns

### System Architecture Diagram

```
                         module load (script start)
                                   │
                    ┌──────────────┴───────────────┐
                    ▼                               ▼
      MOBILE_MQ = matchMedia(…)          PREFERS_REDUCED_MOTION = matchMedia(…).matches
      PORTRAIT_MQ = matchMedia(…)                 (existing pattern, app.js:130-132)
                    │
                    ▼
      detectLayoutMode() → app.layoutMode = "desktop"|"portrait"|"landscape"
                    │
     MOBILE_MQ.addEventListener("change", onLayoutChange)   ┐
     PORTRAIT_MQ.addEventListener("change", onLayoutChange) ┤  rAF-debounced (Pitfall 3)
     window.addEventListener("orientationchange", onLayoutChange) ┘
                    │
                    ▼
              render()  ──────────────────────────────────────────────┐
                    │                                                  │
     app.layoutMode === "desktop"        app.layoutMode === "portrait"/"landscape"
                    │                                                  │
                    ▼                                                  ▼
        renderAppShell()  (FROZEN,               renderMobilePortrait() /
         byte-identical to pre-change)             renderMobileLandscape()  (NEW)
                    │                                                  │
        cachePlaybackDomRefs()                       (mirror pattern: attach gesture
        (existing, app.js:2524)                       listeners to sky/rail node
                                                        immediately after mount, in
                                                        the SAME render pass)
                                                                        │
                                                        attachSkyGestures(node, {...})
                                                        attachRailScrub(node, {...})
                                                        (web/mobile-gestures.js, ported
                                                         verbatim from prototype/gestures.js)
                                                                        │
                                              user gesture (tap/swipe/drag)
                                                                        │
                                              semantic callback (onTap/onSwipeStep/onScrub)
                                                                        │
                                              SAME shared setters desktop uses:
                                              setWordPos() / setMode() / setRollLocation()
                                                                        │
                                              incremental update path (mobile equivalent
                                              of updatePlaybackFrame()) — NEVER render()
                                              while a drag/tap sequence is mid-flight
```

### Recommended Project Structure
```
web/
├── app.js               # existing single file; add app.layoutMode, LS_* consts,
│                         #   MOBILE_MQ/PORTRAIT_MQ, render() branch, renderMobile* stubs
├── mobile-gestures.js    # NEW — port of design/mobile-ux/prototype/gestures.js,
│                         #   loaded via <script> BEFORE app.js in index.html
├── style.css             # add new mobile-scoped block (or split — Claude's discretion)
├── index.html             # add <script src="mobile-gestures.js"> before app.js;
│                          #   tighten viewport meta per D-03 (no user-scalable=no)
tests/
├── helpers/
│   └── web_runtime_site.py   # WEB_FILES tuple MUST gain "mobile-gestures.js" or the
│                               #   Playwright fixture serves a site missing gesture code
└── test_desktop_mobile_smoke.py   # NEW — D-10 smoke test, built on staged_web_runtime_site()
```

### Pattern 1: Module-scope, query-once-then-listen layout detection
**What:** Compute `app.layoutMode` synchronously at module load (before the first `render()` call at app.js:2784), then keep it live via `matchMedia("change")` + a debounced `orientationchange`/`resize` fallback.
**When to use:** This is the *only* place `app.layoutMode` is written. Never let a `render*` function or a gesture callback write to it.
**Example:**
```js
// Source: pattern mirrors existing app.js:130-132 (PREFERS_REDUCED_MOTION), adapted
// per .planning/research/ARCHITECTURE.md §A.4 and CONTEXT.md D-06.
const MOBILE_MQ = window.matchMedia(
  "(max-width: 900px), (orientation: portrait) and (max-width: 1100px)"
); // IDENTICAL string to web/style.css:360 — do not hand-roll a second copy
const PORTRAIT_MQ = window.matchMedia("(orientation: portrait)");

function detectLayoutMode() {
  if (!MOBILE_MQ.matches) return "desktop";
  return PORTRAIT_MQ.matches ? "portrait" : "landscape";
}

let layoutRaf = null;
function onLayoutMaybeChanged() {
  if (layoutRaf) return;
  layoutRaf = requestAnimationFrame(() => {
    layoutRaf = null;
    const next = detectLayoutMode();
    if (next !== app.layoutMode) {
      app.layoutMode = next;
      render(); // discrete transition — full structural render is correct here
    }
  });
}

app.layoutMode = detectLayoutMode(); // set BEFORE the first render() call (app.js:2784)
MOBILE_MQ.addEventListener("change", onLayoutMaybeChanged);
PORTRAIT_MQ.addEventListener("change", onLayoutMaybeChanged);
window.addEventListener("orientationchange", onLayoutMaybeChanged);
```

### Pattern 2: Post-mount gesture attach/detach, mirroring `cachePlaybackDomRefs`
**What:** `attachSkyGestures`/`attachRailScrub` return a teardown closure. Call the attach function immediately after the target element is appended in `renderMobilePortrait`/`renderMobileLandscape`, store the teardown on `app.dom`, and — because `render()` already does full-teardown DOM replacement (app.js:874-875 `clear(root)`) — GC handles cleanup, but call the stored teardown explicitly before it's overwritten as defensive belt-and-suspenders (per `.planning/research/ARCHITECTURE.md` §A.2).
**When to use:** Every structural render that produces a sky/rail node. Never at module scope, never inside the `resize`/`matchMedia` handler.
**Example:**
```js
// Source: web/app.js:889 cachePlaybackDomRefs() call-after-mount convention,
// combined with design/mobile-ux/prototype/gestures.js's attach/teardown contract.
function renderMobilePortrait() {
  const shell = el("div", { class: "mobile-portrait" }, /* ...sky + rail nodes... */);
  return shell;
}

// in render():
root.append(app.layoutMode === "portrait" ? renderMobilePortrait() : renderMobileLandscape());
if (app.layoutMode !== "desktop") {
  const skyEl = document.querySelector(".mobile-sky");
  if (app.dom.skyGestureTeardown) app.dom.skyGestureTeardown();
  app.dom.skyGestureTeardown = window.attachSkyGestures(skyEl, {
    onTap: () => { if (app.tapToPause) togglePlayback(); },
    onDoubleTap: () => { setWordPos(/* last roll word pos */); startPlayback(); },
    onSwipeStep: dir => setWordPos(app.wordPos + dir * ROLL_STEP_WORDS), // incremental, no render()
    onSwipeEnd: () => persistBookmarkSoon(),
  });
}
```

### Pattern 3: `window.__bcfPrefs` bridge for the ported `haptic()` helper
**What:** `design/mobile-ux/prototype/gestures.js`'s `haptic()` reads `window.__bcfPrefs?.haptics` (a global the React prototype set up itself). **`window.__bcfPrefs` does not exist anywhere in `web/app.js` today** `[VERIFIED: grep of web/app.js for "__bcfPrefs" returns no matches, direct read this session]`. Porting `gestures.js` "verbatim" per CONTEXT.md's canonical-refs note still requires wiring this one global, or the haptic no-op path silently never fires (harmless functionally — haptics are decorative-only per D-11 — but worth deciding explicitly rather than discovering it during Phase 2 QA).
**When to use:** Set once near the other module-scope setup, kept in sync with `app.haptics`:
```js
// Minimal bridge — keeps mobile-gestures.js unmodified per "port verbatim."
Object.defineProperty(window, "__bcfPrefs", { get: () => ({ haptics: app.haptics }) });
```
**Recommendation:** Decide in the plan whether to add this bridge (keeps `gestures.js` truly verbatim) or adapt `haptic()`'s call sites to accept a `haptics` flag as a parameter (a small, intentional deviation from "verbatim"). Either is acceptable; leaving it undecided is not — CONTEXT.md's "port verbatim" instruction and the actual absence of `window.__bcfPrefs` are in tension and the plan must pick one resolution.

### Anti-Patterns to Avoid
- **A second `innerWidth`/`innerHeight` check as a fallback "just in case."** `.planning/research/ARCHITECTURE.md` §A.4 flags this explicitly — it drifts from the CSS breakpoint over time. Use only the `matchMedia` object built from the identical query string at `style.css:360`.
- **Attaching gesture listeners at module scope "to avoid re-attaching every render."** This is the single largest risk this phase carries — see Common Pitfalls below.
- **Calling `render()` from inside a `pointermove`/`onSwipeStep` callback.** Kills pointer capture mid-drag (Pitfall 2/ARCHITECTURE §A.2). Gesture callbacks write to `app.wordPos`/etc. and call an incremental update path, never `render()`.
- **Writing a second, mobile-only tokenizer/breakpoint constant pair.** The breakpoint numbers (900/1100) already live in exactly one CSS string; JS must read that same string via `matchMedia`, never redefine `900`/`1100` as separate JS literals.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gesture recognition (tap/double-tap/swipe/drag) | A new pointer-event state machine | `design/mobile-ux/prototype/gestures.js`'s `attachSkyGestures`/`attachRailScrub`, ported verbatim into `web/mobile-gestures.js` | Already implements the full locked gesture-contract constants (`TAP_MAX_DURATION`, `SCRUB_STEP_PX`, etc.) `[VERIFIED: design/mobile-ux/prototype/gestures.js, direct read]`; CONTEXT.md explicitly mandates verbatim port |
| Local dev server for Playwright | A new `http.server` invocation script | `tests/helpers/web_runtime_site.py`'s `_serve()`/`staged_web_runtime_site()` | Already implements a `ThreadingTCPServer` on an ephemeral port serving a staged copy of `web/` + synthetic fixture data `[VERIFIED: tests/helpers/web_runtime_site.py, direct read]` |
| localStorage schema versioning/migration | A new versioning scheme for the mobile keys | Existing `LS_STORAGE_VERSION`/`STORAGE_VERSION`/`migratePreviewStorage()` pattern (app.js:315-323) | Already the sole persistence-migration mechanism in this app; project convention is invalidate-and-default, not incremental migration `[VERIFIED: web/app.js, direct read; CITED: .planning/research/STACK.md]` |
| Preference read/write helpers | New ad hoc `localStorage.getItem`/`setItem` calls for the 4 new keys | `readStoredChoice`/`readStoredNumber`/`readStoredBoolean`/`store` (app.js:252-283) | Already handle the try/catch-for-private-browsing and allow-list validation this phase's Security Domain requires |
| Chromium-launch-or-skip guard for Playwright tests | New boilerplate per test file | `_chromium_browser_or_skip()` (`tests/test_web_app_integration.py:11-17`) | Already handles the "Playwright installed but browser binaries missing" case gracefully via `pytest.skip` |

**Key insight:** Every piece of infrastructure this phase needs — gesture state machine, local test server, storage versioning, preference validation, browser-launch guarding — already exists in this repository in a form built for exactly this purpose. The work is wiring, not invention. The single genuinely new piece of logic is the `matchMedia`-driven `app.layoutMode` state machine itself (Pattern 1 above), which is small and has a direct precedent (`PREFERS_REDUCED_MOTION`) to mirror.

## Common Pitfalls

### Pitfall 1: `LS_PORTRAIT_DISMISSED` purge-list discrepancy between the plan document and the actual code
**What goes wrong:** `INTEGRATION_PLAN.md` §3.1 instructs "**Remove** `LS_PORTRAIT_DISMISSED` from `migratePreviewStorage()` purge list" — but the current purge array (app.js:318) is `[LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR, LS_ROLL_LOCATION, LS_FIELD_LOG_HIDDEN]` and **does not contain `LS_PORTRAIT_DISMISSED` today**. Following the plan's literal instruction ("remove it") is a no-op that leaves the key un-purged, which directly fails the phase's own success criterion #4 ("`bcf:portrait-dismissed` purged after `STORAGE_VERSION` bump") and CONTEXT.md D-09 ("drop `bcf:portrait-dismissed` from existence").
**Why it happens:** The plan document was written against an earlier or hypothetical state of `app.js`; the live code diverged.
**How to avoid:** **Add** `LS_PORTRAIT_DISMISSED` to the purge array (alongside the existing 7 keys), not remove it. The `LS_PORTRAIT_DISMISSED` *constant* and the `app.portraitDismissed` field/`renderPortraitBanner()` call stay functionally intact in Phase 1 (banner deletion is Phase 4 per plan §5D) — only its *persisted value* is cleared on this version bump, so returning users see the banner again once, which is expected/acceptable.
**Warning signs:** A test asserting `localStorage.getItem("bcf:portrait-dismissed")` is `null` after a version-3 load, from a page that had it set under version 2, failing.

### Pitfall 2: Colliding the new `bcf:timeline-zoom` key with the existing `bcf:timeline:zoom` (desktop) key
**What goes wrong:** Desktop's continuous zoom already persists under `LS_ZOOM = "bcf:timeline:zoom"` (colon-separated, app.js:57). The new mobile quantized zoom key per D-09/plan §4 is `bcf:timeline-zoom` (hyphen-separated) — a **different string**, by design (plan §4 explicitly calls out keeping them separate to avoid coupling continuous desktop zoom with quantized mobile 1×/2×/4×/8× steps). A typo collapsing the hyphen to a colon (or vice versa) silently merges two semantically different preferences.
**Why it happens:** The two keys differ by exactly one punctuation character and share a name stem — an easy typo, and nothing in the type system catches it (`localStorage` keys are just strings).
**How to avoid:** Define the new constant explicitly, e.g. `const LS_MOBILE_TIMELINE_ZOOM = "bcf:timeline-zoom";`, distinct from the existing `LS_ZOOM`. Add a code comment at both definitions cross-referencing the other, since nothing else enforces the distinction.
**Warning signs:** Changing zoom on mobile visibly changes the desktop scrubber's zoom (or vice versa) after a reload.

### Pitfall 3: `bcf:timeline-zoom` needs allow-list validation, not `readStoredNumber`
**What goes wrong:** Mobile timeline zoom is quantized to exactly `{1, 2, 4, 8}` (plan §4, phase success criteria MOBP-05). `readStoredNumber(key, fallback)` (app.js:261-270) accepts *any* finite number — it doesn't restrict to the quantized set. A tampered or corrupted stored value (e.g. `"3"` or `"1.5"`) would silently pass through and produce an off-contract zoom level.
**Why it happens:** `readStoredNumber` was built for desktop's continuous zoom (`clamp(readStoredNumber(LS_ZOOM, DEFAULT_ZOOM), 0.5, 6)` at app.js:98), where any number in range is valid. Reusing it unmodified for a quantized-set preference silently drops the quantization guarantee.
**How to avoid:** Validate `bcf:timeline-zoom` with `readStoredChoice(key, ["1", "2", "4", "8"], "1")` (string comparison, matching the existing helper's contract) then `Number(...)` the result, or write a small `readStoredNumberChoice` helper if the plan prefers numeric storage. Either way, the allow-list must be explicit — this is also the Security Domain's V5 Input Validation control for this key (see below).
**Warning signs:** A Lighthouse/manual test setting `localStorage.setItem("bcf:timeline-zoom", "3")` via devtools and reloading shows a zoom level the UI never offers as a control.

### Pitfall 4: `window.__bcfPrefs` doesn't exist — the ported `haptic()` helper is a silent no-op without it
**What goes wrong:** See Architecture Pattern 3 above. If the plan ports `gestures.js` byte-for-byte without adding the `window.__bcfPrefs` bridge, `haptic()`'s `if (!window.__bcfPrefs?.haptics) return;` guard is always true (since `window.__bcfPrefs` is `undefined`), so haptic feedback never fires even when `app.haptics` is `true`. Functionally harmless per D-11 (haptics are decorative-only, no-op on iOS anyway), but it means the `bcf:haptics` toggle silently does nothing on Android Chrome too, which is a real (if minor) regression from the prototype's behavior.
**Why it happens:** The prototype set `window.__bcfPrefs` itself somewhere outside the pasted `gestures.js` file; that setup code isn't part of the "port verbatim" scope, and it's easy to port the file and miss the implicit global dependency.
**How to avoid:** Add the one-line bridge shown in Pattern 3, or explicitly decide (and document in the plan) to adapt `haptic()`'s call sites instead. Either is fine; the plan must not leave this unaddressed.
**Warning signs:** Manual test on an Android Chrome device/emulator: haptics toggle ON, swipe crosses a roll boundary, no vibration — silent failure, no console error.

### Pitfall 5: Existing `@media (max-width: 1100px)` and `@media (max-width: 640px)` blocks already style `.app-header`/`.scrubber`/`.playthrough`/`.detail`/`.stat-strip` down to narrow widths
**What goes wrong:** `web/style.css:1564` and `:1607` are **pre-existing, already-shipped** responsive rules that compact the *desktop* shell at ≤1100px and ≤640px respectively `[VERIFIED: web/style.css:1560-1614, direct read]`. These ranges overlap the new mobile breakpoint (`max-width: 900px`, or portrait ≤1100px). This isn't a Phase 1 blocker — Phase 1 adds zero new UI — but the plan's later phases (B/C, hiding `.app-header`/`.scrubber-stack`/etc. behind the mobile media query) must out-cascade these existing rules by *appending* new selectors later in the file (or with matching/higher specificity), never by editing rules at `:1564`/`:1607` directly (that would violate the CSS freeze in plan §0.1.5).
**Why it happens:** Two independently-written responsive systems (an older desktop-narrow-viewport compaction pass, and the new mobile takeover) target overlapping width ranges without either being aware of the other.
**How to avoid:** Phase 1 should record the CSS file-organization decision (new block in `style.css` vs. split `web/mobile.css`, per CONTEXT.md's "Claude's Discretion") with this overlap in mind — whichever choice is made, the new mobile block must be positioned (or scoped) so it always wins the cascade against `:1564`/`:1607` for the elements it hides. Not an action item for Phase 1's own deliverables, but should be flagged in the plan as a note for Phase 2/3.
**Warning signs:** Deferred to Phase 2/3 QA: mobile layout shows fragments of the desktop-compacted header/scrubber underneath the new mobile chrome.

### Pitfall 6: Forgetting to add `mobile-gestures.js` to the Playwright fixture's `WEB_FILES` tuple
**What goes wrong:** `tests/helpers/web_runtime_site.py`'s `WEB_FILES = ("index.html", "app.js", "data-contract.js", "viz-model.js", "style.css")` (line 14-20) is the exact list of files `staged_web_runtime_site()` copies into the served test site `[VERIFIED: tests/helpers/web_runtime_site.py, direct read]`. It does not currently include `mobile-gestures.js`. If Phase 1 adds `web/mobile-gestures.js` and `web/index.html` references it via `<script>`, but `WEB_FILES` isn't updated, every Playwright integration test (existing ones and the new D-10 smoke test) serves a site with a 404'd script — likely surfacing as a console error the existing tests already assert `console_messages == []` against (see `test_web_app_integration.py:84`), so this would fail loudly, but only once someone runs the suite, not from a visual check.
**Why it happens:** The fixture list is a hand-maintained tuple with no automatic sync to the real `web/` directory contents.
**How to avoid:** Add `"mobile-gestures.js"` to `WEB_FILES` in the same change that adds the file and the `<script>` tag in `index.html`.
**Warning signs:** `.venv/bin/python -m pytest tests/test_web_app_integration.py` failing with a `pageerror`/404-related console message assertion after this phase's changes land.

## Code Examples

### Existing preference-read pattern to extend (verbatim reuse, not reinvention)
```js
// Source: web/app.js:252-283, direct read — use unmodified for the 4 new bcf:* keys
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

### Existing storage-version migration to extend
```js
// Source: web/app.js:315-323, direct read
function migratePreviewStorage() {
  try {
    if (localStorage.getItem(LS_STORAGE_VERSION) === STORAGE_VERSION) return;
    for (const key of [
      LS_BOOKMARK, LS_SPEED, LS_ZOOM, LS_MODE, LS_ON_ROLL_BEHAVIOR,
      LS_ROLL_LOCATION, LS_FIELD_LOG_HIDDEN,
      // Phase 1 additions — see Pitfall 1:
      LS_PORTRAIT_DISMISSED,       // ADD — currently absent; must be purged per D-09
      LS_MOBILE_TIMELINE_ZOOM,     // new
      LS_TAP_TO_PAUSE,             // new
      LS_HAPTICS,                  // new
      LS_HELP_SEEN,                // new
    ]) {
      localStorage.removeItem(key);
    }
    localStorage.setItem(LS_STORAGE_VERSION, STORAGE_VERSION); // STORAGE_VERSION = "3"
  } catch {}
}
```

### Existing Playwright test harness pattern (to follow for D-10)
```python
# Source: tests/test_web_app_integration.py:1-86 + tests/helpers/web_runtime_site.py, direct read
from tests.helpers.web_runtime_site import staged_web_runtime_site

def test_desktop_smoke_resize_round_trip(tmp_path):
    playwright_api = pytest.importorskip("playwright.sync_api")
    with staged_web_runtime_site(tmp_path) as site:
        with playwright_api.sync_playwright() as p:
            browser = _chromium_browser_or_skip(p, playwright_api)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.add_init_script(
                "window.__bcfRenderStats = { structuralRenders: 0 };"
            )
            page.goto(site.url_for(), wait_until="networkidle")
            page.evaluate("window.__bcfRenderStats.structuralRenders = 0")
            # §0.5 step 5: resize 1920 -> 1101 (desktop) -> 900 (mobile) -> back to 1920
            page.set_viewport_size({"width": 1101, "height": 900})
            page.set_viewport_size({"width": 899, "height": 900})
            page.set_viewport_size({"width": 1920, "height": 1080})
            expect = playwright_api.expect
            expect(page.locator(".app-header")).to_be_visible()
            expect(page.locator(".portrait-banner.is-visible")).to_have_count(0)
            browser.close()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| No layout-mode detection exists in `app.js` at all today | `matchMedia`-driven `app.layoutMode` module-scope listener | This phase | First introduction of the desktop/portrait/landscape state machine; no prior art to migrate away from inside this codebase |
| `renderPortraitBanner()` as the sole "mobile-aware" behavior | Full mode-branched render tree (later phases) with Phase 1 laying only the detection/gesture/storage groundwork | Phase 1 → Phase 4 cutover | Banner remains the safety net through Phase 1-3; Phase 1 does not remove it |

**Deprecated/outdated:** None yet — `renderPortraitBanner`/`.portrait-banner`/`LS_PORTRAIT_DISMISSED` are explicitly kept alive through this phase (deletion is Phase 4 per plan §5D), only the *value* is purged this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | The plan's suggested resolution for the `LS_PORTRAIT_DISMISSED` purge-list wording conflict (add, don't "remove") is the correct read of CONTEXT.md D-09's intent | Common Pitfalls #1 | Low — the phase's own success criterion #4 is unambiguous ("purged after STORAGE_VERSION bump"), so this is a directly-checkable fact, not really an assumption, but flagging it since it contradicts the plan document's literal words |
| A2 | Adding a `window.__bcfPrefs` getter bridge (rather than adapting `haptic()`'s call sites) is an acceptable way to satisfy "port `gestures.js` verbatim" | Architecture Pattern 3 / Pitfall 4 | Low — either resolution is functionally fine since haptics are decorative-only per D-11; only affects code-review "is this really verbatim" framing, not behavior |

**All other claims in this research were verified via direct file reads in this session or cited from the existing project-level research documents** (`STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`), themselves HIGH confidence for this codebase.

## Open Questions

> **Naming note (post-planning):** this document's `tests/test_desktop_mobile_smoke.py` became two files in the final plans: `tests/test_mobile_plumbing.py` (layout-mode/gesture/storage proofs — plans 01-01, 01-02) and `tests/test_desktop_smoke.py` (§0.5 desktop smoke test — plan 01-03). The plans and 01-VALIDATION.md are authoritative.

1. **(RESOLVED — plan 01-01 Task 1 step 6(e))** **Where does `ROLL_STEP_WORDS` (the word-position delta per swipe-step) come from for Phase 1's `onSwipeStep` wiring?** Resolution: minimal diagnostic-probe attach point in Phase 1 proves single-fire/no-double-bind; production wiring to `setWordPos` deferred to Phase 2, exactly per the recommendation below.
   - What we know: `attachSkyGestures`'s `onSwipeStep(dir)` fires once per `SCRUB_STEP_PX` (56px) of horizontal travel; the *word-position* delta per roll-step is a Phase 2 (Portrait C) concern per plan §5B ("wire the sky tap/swipe handlers using `attachSkyGestures`" is listed under Phase B, not Phase A).
   - What's unclear: Phase 1's own gate only requires that gesture *helpers* exist and `app.layoutMode` flips correctly — not that gestures are fully wired to `setWordPos`. It's a planning-scope call whether Phase 1's `web/mobile-gestures.js` port includes a stub call site (verifying the module loads and callbacks fire) or defers all wiring to Phase 2.
   - Recommendation: Given the phase's own success criterion #3 ("gestures fire exactly once, surviving mid-drag re-renders") requires *something* to be attached and observably counted, plan for a minimal attach point in Phase 1 (e.g., attached to a placeholder/no-op sky element or an existing hidden test target) sufficient to prove the no-double-binding property, with full production wiring explicitly deferred to Phase 2. Confirm this scope boundary in the plan rather than leaving it implicit.

2. **(RESOLVED — plan 01-01 uses plain rAF-coalescing per the recommendation; iOS ~100ms re-settle check withheld until a real device shows the flap)** **Exact debounce timing for orientation/resize (explicitly Claude's Discretion per CONTEXT.md).**
   - What we know: `.planning/research/PITFALLS.md` Pitfall 3 recommends `requestAnimationFrame`-scheduling plus a ~100ms re-check for iOS Safari's late-settling dimensions.
   - What's unclear: No hard number is locked; CONTEXT.md explicitly leaves this to implementation discretion.
   - Recommendation: Use rAF-scheduling for the primary debounce (shown in Pattern 1 above); add the ~100ms iOS late-settle re-check only if/when real-device testing (flagged as unconfirmed in STATE.md) surfaces the flap. Don't over-engineer the re-check in Phase 1 without a device to validate against.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| `.venv/bin/python` | All Python tooling (pytest, verify.py) | ✓ | Python 3.14 (via `.venv/bin/python -> python3.14`) | — |
| `playwright` (Python package) | D-10 smoke test | ✓ | Installed in `.venv`, import succeeds | — |
| Playwright Chromium binary | D-10 smoke test browser automation | ✓ | `chromium.launch()` verified successful in this session | `_chromium_browser_or_skip()` pattern already handles missing-binary via `pytest.skip` if this ever regresses |
| `node` (for `node --check` syntax gate) | DEVELOPERS.md "Web app checks" | ✓ | v26.0.0 | — |
| Real iOS Safari device | `svh`/`dvh` toolbar behavior, `orientationchange` timing verification (Phases 2-3, not Phase 1) | ✗ (unconfirmed per STATE.md Blockers) | — | Not a Phase 1 blocker — Phase 1 ships no mobile UI to test on-device; flagged for Phase 2/3 planning |

**Missing dependencies with no fallback:** None blocking Phase 1.

**Missing dependencies with fallback:** Real iOS Safari device access — not needed until Phase 2/3 gates; already tracked as a project-level blocker in `STATE.md`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + Playwright (`playwright.sync_api`), already configured via `pyproject.toml` `[project.optional-dependencies].dev` and `[tool.pytest.ini_options]` |
| Config file | `pyproject.toml` (`testpaths = ["tests"]`, `addopts = "-q"`) |
| Quick run command | `.venv/bin/python -m pytest tests/test_desktop_mobile_smoke.py -q` (new file this phase adds) plus `node --check web/app.js web/mobile-gestures.js` |
| Full suite command | `.venv/bin/python scripts/verify.py` (runs `git diff --check`, `data_release.py check-derived`, then full `pytest`) `[VERIFIED: scripts/verify.py, direct read]` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| MOBF-01 | Interview gate resolves §9 opens, `user-scalable` conflict, `visibilitychange`, provenance shape | N/A — process gate, not code | Verified by presence/content of `01-CONTEXT.md` (already done) | N/A |
| MOBF-02 | `app.layoutMode` derives from `matchMedia`, updates on resize/rotation, survives rotation | integration (Playwright) | `pytest tests/test_desktop_mobile_smoke.py::test_layout_mode_flips_at_breakpoints -x` | ❌ Wave 0 — new test file |
| MOBF-03 | Gesture helpers, per-render attach, no double-bind, no lost pointer capture | unit (module load) + integration (Playwright, swipe-after-time) | `pytest tests/test_desktop_mobile_smoke.py::test_gesture_attach_survives_rerender -x`; `node --check web/mobile-gestures.js` | ❌ Wave 0 — new test file; mirrors PITFALLS.md Pitfall 2's "swipe after 2 minutes of playthrough" recommendation, scaled to a fast forced-re-render loop instead of a real 2-minute wait |
| MOBF-04 | New `bcf:*` keys round-trip; `STORAGE_VERSION` bump purges stale keys incl. `bcf:portrait-dismissed` | unit + integration | `pytest tests/test_web_app_integration.py -k storage_migration -x` (extend existing file, follows its `init_script`/`storage=` fixture pattern already used at lines 26-37) | Partial — file exists, new test cases needed |
| MOBF-05 | Mobile CSS foundation: `touch-action`, `overscroll-behavior`, `svh`/`dvh`, `env(safe-area-inset-*)` | integration (Playwright computed-style probe) | `pytest tests/test_desktop_mobile_smoke.py::test_mobile_css_foundation_values -x` (assert `getComputedStyle` on gesture-surface elements once Phase 1 CSS lands) | ❌ Wave 0 — new test file |
| MOBF-06 | Scripted desktop smoke test covers §0.5 six-step checklist, passes | integration (Playwright) | `pytest tests/test_desktop_mobile_smoke.py -x` (the file itself IS this requirement) | ❌ Wave 0 — new test file |

### Sampling Rate
- **Per task commit:** `node --check web/app.js web/mobile-gestures.js` + targeted `pytest tests/test_desktop_mobile_smoke.py -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/test_web_app_integration.py tests/test_desktop_mobile_smoke.py -q`
- **Phase gate:** `.venv/bin/python scripts/verify.py` green before `/gsd-verify-work`, per `AGENTS.md`'s standing verification requirement

### Wave 0 Gaps
- [ ] `tests/test_desktop_mobile_smoke.py` — new file; covers MOBF-02, MOBF-03 (attach-survives-rerender case), MOBF-05, MOBF-06
- [ ] `tests/helpers/web_runtime_site.py` — `WEB_FILES` tuple needs `"mobile-gestures.js"` added (see Pitfall 6); not a new file, but a required edit before any Phase 1 Playwright test can pass
- [ ] New test cases in `tests/test_web_app_integration.py` (or a new file) for MOBF-04's storage round-trip + purge behavior, following the existing `init_script`/`storage=` kwarg pattern in `_page_with_console_capture` (`scripts/smoke_pages_site.py:20-45`, mirrored in the app-integration test file)
- [ ] No framework install needed — `pytest`/`playwright` already present

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | No | No auth surface in this phase or app |
| V3 Session Management | No | No server sessions; app is a static site |
| V4 Access Control | No | No access-controlled resources touched |
| V5 Input Validation | Yes | All 4 new `bcf:*` localStorage reads must go through an allow-list validator (`readStoredChoice`/`readStoredBoolean`, not raw `localStorage.getItem`), exactly as the 7 existing keys already do (app.js:252-283) |
| V6 Cryptography | No | No crypto surface introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Devtools/console tampering with `localStorage` values (e.g., setting `bcf:timeline-zoom` to an out-of-set value, or `bcf:haptics` to a non-boolean string) | Tampering | Allow-list decode on every read (`readStoredChoice`/`readStoredBoolean`), silently falling back to the documented default — already the existing pattern for all 7 current keys; extend identically to the 4 new keys (see Pitfall 3) |
| Rapid `resize`/`orientationchange` event storms causing excessive structural `render()` calls (resource exhaustion, not classically "security" but a reliability/DoS-adjacent concern for a client this app runs unattended for long playthrough sessions) | Denial of Service (client-side) | `requestAnimationFrame`-debounce the layout-mode recompute (Pattern 1); the existing `window.__bcfRenderStats.structuralRenders` counter (app.js:285-290) gives a directly testable signal for "did this resize storm cause N renders instead of 1" |
| A malicious/misbehaving third-party `web/mobile-gestures.js` script tag ordering (loaded after `app.js` instead of before) silently breaking gesture wiring | Tampering (build-time, not runtime, since there's no build step — this is really a load-order correctness risk, not an attacker-controlled surface) | `index.html`'s `<script>` tag order is static and reviewed; no dynamic script injection exists in this app, so this is a correctness check (verify load order in the smoke test), not an exploitable surface |

## Sources

### Primary (HIGH confidence — direct reads this session)
- `/Users/dre/src/bcf-visualization/web/app.js` — `LS_*`/`STORAGE_VERSION`/`migratePreviewStorage` (lines 55-64, 85-125, 252-323), `render()`/`renderAppShell()`/`renderPortraitBanner()` dispatch (lines 803-1050), `cachePlaybackDomRefs`/`updatePlaybackFrame`/rAF tier (lines 842-891, 2524-2563), module-scope listeners incl. existing `visibilitychange` (lines 2754-2782), `el()`/`setProps()` event-binding convention (lines 203-233)
- `/Users/dre/src/bcf-visualization/web/style.css` — `.portrait-banner` + `:360` media query (lines 330-363), pre-existing overlapping `@media (max-width: 1100px)`/`(max-width: 640px)` desktop-compaction blocks (lines 1564-1614)
- `/Users/dre/src/bcf-visualization/web/index.html` — current viewport meta and script load order
- `/Users/dre/src/bcf-visualization/design/mobile-ux/INTEGRATION_PLAN.md` — full read; §0 freeze rules, §3 file-level changes, §4 storage keys, §5 phases, §9 open questions
- `/Users/dre/src/bcf-visualization/design/mobile-ux/prototype/gestures.js` — full read; `attachSkyGestures`/`attachRailScrub`/`haptic()` implementation and the `window.__bcfPrefs` dependency
- `/Users/dre/src/bcf-visualization/tests/helpers/web_runtime_site.py`, `tests/test_web_app_integration.py`, `tests/test_pages_smoke.py`, `scripts/smoke_pages_site.py` — existing Playwright + pytest + local-HTTP-server test harness
- `/Users/dre/src/bcf-visualization/pyproject.toml`, `/Users/dre/src/bcf-visualization/AGENTS.md`, `/Users/dre/src/bcf-visualization/DEVELOPERS.md` — project conventions, verification gate, testing design pattern
- `/Users/dre/src/bcf-visualization/.planning/phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md` — locked decisions D-01..D-11
- In-session environment check: `.venv/bin/python` + `playwright` import + `chromium.launch()` succeeded; `node --version` → v26.0.0

### Secondary (MEDIUM confidence, already project-level research)
- `/Users/dre/src/bcf-visualization/.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md` — milestone-level research already covering Pointer Events, `matchMedia`, `touch-action`, `svh`/`dvh`, haptics support reality, and all 11 pitfalls relevant to this workstream; not re-derived here, only applied to this phase's specific scope

### Tertiary (LOW confidence)
- None — no new WebSearch was required for this phase; all claims trace to direct codebase reads or the existing HIGH/MEDIUM-confidence project research documents.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, all native APIs already vetted at milestone level
- Architecture: HIGH — grounded in direct reads of the exact `render()`/`cachePlaybackDomRefs`/rAF-tier code this phase must integrate with
- Pitfalls: HIGH — 4 of 6 pitfalls above are concrete code-level discrepancies found by direct comparison of the plan document against current `app.js`/`style.css`/test-fixture state, not generic domain knowledge

**Research date:** 2026-07-25
**Valid until:** No external expiry driver (no new dependency versions to go stale) — re-verify only if `web/app.js`, `web/style.css`, or `tests/helpers/web_runtime_site.py` are edited by another workstream before this phase executes.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|--------------|----------------------|
| MOBF-01 | Interview gate resolves §9 opens, `user-scalable` conflict, `visibilitychange`, provenance shape before any mobile code | Already satisfied — `01-CONTEXT.md` D-01..D-11 records all resolutions. Research confirms no additional open items were missed: the existing `document.addEventListener("visibilitychange", ...)` at app.js:2780 currently only persists the bookmark, not pauses playback — D-02's pause-on-hidden behavior is new logic to add there, mobile-only. |
| MOBF-02 | `app.layoutMode` derives from identical `matchMedia` query to CSS breakpoint, updates on resize/rotation, survives rotation | Architecture Pattern 1 gives the exact implementation, mirroring the existing `PREFERS_REDUCED_MOTION` precedent (app.js:130-132) and reusing the identical query string already at `style.css:360` |
| MOBF-03 | Gesture helpers ported with per-render attach lifecycle, no double-bind, no lost pointer capture | Architecture Pattern 2 + Pitfalls (Common Pitfalls in `.planning/research/PITFALLS.md` #2) give the exact attach-after-mount convention to mirror (`cachePlaybackDomRefs`); Pattern 3/Pitfall 4 flag the `window.__bcfPrefs` gap in the verbatim port |
| MOBF-04 | New `bcf:*` keys read on init/written on change; `STORAGE_VERSION` bump purges stale keys incl. `bcf:portrait-dismissed` | Code Examples section gives the exact `migratePreviewStorage()` extension; Pitfall 1 resolves a direct contradiction between the plan document and the current code re: the purge list; Pitfall 2/3 flag key-naming-collision and allow-list-validation risks specific to `bcf:timeline-zoom` |
| MOBF-05 | Mobile CSS: `touch-action`/`overscroll-behavior`, `svh`/`dvh`, `env(safe-area-inset-*)` | Covered at the technique level by `.planning/research/STACK.md`/`PITFALLS.md` (Pitfall 4 there); Pitfall 5 in this document flags the pre-existing overlapping `@media` blocks the new mobile CSS must out-cascade without editing |
| MOBF-06 | Scripted desktop smoke test verifies §0.5 checklist, runnable at every phase gate | Full existing Playwright+pytest harness identified (`staged_web_runtime_site`, `_chromium_browser_or_skip`, `window.__bcfRenderStats`); Code Examples gives a working test skeleton; Validation Architecture section maps it to `tests/test_desktop_mobile_smoke.py` |

</phase_requirements>

---
*Research for: BCF Visualization — Phase 1: Mobile State & Gesture Plumbing*
*Researched: 2026-07-25*
