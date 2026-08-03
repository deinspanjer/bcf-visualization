# Phase 4: Mobile Cutover & Accessibility - Research

**Researched:** 2026-08-02
**Domain:** Frontend accessibility (WCAG/axe-core semantics), CSS `prefers-reduced-motion`, keyboard input handling, static-HTML modal patterns, Lighthouse CLI tooling, and git-history freeze verification — all against the existing vanilla-JS `web/app.js` codebase.
**Confidence:** HIGH (every finding below is grounded in direct inspection of this repo's source, its git history, and the actual bundled `lighthouse`/`axe-core` packages fetched via `npx` — not training-data recall)

## Summary

This phase is smaller than its own CONTEXT.md implies once the codebase is actually read. Three of D-37..D-51's hardest-looking items are **already done or structurally impossible to need**: (1) the 36×36 `.mobile-icon-btn.compact` buttons already clear the 44px tap-target floor via a Phase-2 `box-sizing:content-box` + `padding` technique, and a Playwright test (`test_mobile_portrait.py:520-534`) already proves it with `getBoundingClientRect()` — only the 40×40 landscape `.mobile-cinema-scrub-fab` genuinely needs new CSS. (2) The keyboard `Space` key already toggles playback identically on every layout mode today (no `layoutMode` gate exists in the handler) — MOBX-03's "Space" equivalent needs zero new code, only a test. (3) `prefers-reduced-motion: reduce` is already enforced globally by a pre-existing, unscoped rule in frozen `web/style.css:62` (`*, *::before, *::after { animation: none !important; transition: none !important; }`) — this already silences every mobile.css transition/animation (the 220ms rail-pan, the 220ms cinema-scrub fade, the 5s hint-fade keyframe) without any Phase 4 edit. The one item that IS genuinely new JS is doubling `CHROME_AUTOHIDE` (4000→8000ms) in `resetMobileChromeHideTimer()`, and it should reuse the exact `PREFERS_REDUCED_MOTION` module-load constant desktop's own cinematic code already defines at `app.js:237` — not a second `matchMedia` query. "Throw decay" (named in MOBX-04) and the "220ms rotation crossfade" (named in `gesture-contract.html`) were never built (both are v2/aspirational); Phase 4 must document them as not-applicable, not invent them.

A second major finding: Lighthouse's Accessibility category's `target-size` audit (the only tap-target check it runs) is axe-core's `target-size` rule with a **default minimum of 24×24 CSS px** (WCAG 2.5.8 AA), not 44×44. Every element in this app already clears that bar. This means MOBX-03's literal "≥44×44" requirement is a **self-imposed UX bar the plan chose, not something the Lighthouse ≥90 gate can detect or enforce** — the planner must verify 44×44 via a direct `getBoundingClientRect()` Playwright assertion (as the codebase already does for the compact buttons), not by pointing at a passing Lighthouse score.

Third, the roll data model was inspected directly (`data/derived/visualization_facts.json`, 670 rolls: 410 miss / 260 hit, 51 with >1 paid perk in one roll, exactly 1 with `source_kind: "trigger"`). The mobile field-log/cinema-scrub UI already computes the exact `{n} of {total}` numbering the live region needs (`app.data.story.rolls.indexOf(live) + 1` / `rolls.length` — never `roll_label`, which is `null` on 669 of 670 rolls). `viz-model.js`'s existing `rollMarkerModel(roll)` already classifies every outcome shape (`isMissLike`, `paidCount`, `freeCount`, `isUntracked`) that outcome-aware announcement phrasing needs — reuse it, don't re-derive miss/multi-grab logic a second time.

**Primary recommendation:** Treat this phase as "verify three things are already true, write four small pieces of new code (FAB hit-area, `?` key + mobile arrows/Home branch, live region, landing-page chip+dialog, auto-hide doubling), and prove the whole-milestone freeze with `git diff 57d2768 HEAD -- web/style.css` (not the Phase-3 base `22bdd8c` — Phase 1 started the mobile work, so `57d2768` is the true pre-milestone commit)."

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Banner deletion (D-37/D-38) | Browser/Client (CSS+JS) | — | Pure static-asset deletion in the existing client bundle; no server involved |
| Landing page chip/credit/`?` | Browser/Client (static HTML) | — | `index.html` is a standalone static file with zero JS/build step; a native `<dialog>` is the only "server-like" concept needed and it's client-native |
| Live region / announcements | Browser/Client (DOM + ARIA) | — | Pure DOM mutation on the existing `app.js` render/update cycle; no network |
| Keyboard equivalents | Browser/Client (event listener) | — | Global `keydown` listener already exists in `app.js`; this adds a layout-gated branch |
| Tap-target sizing | Browser/Client (CSS) | — | CSS box-model change only; Lighthouse/axe-core run client-side against the rendered DOM |
| Reduced-motion | Browser/Client (CSS media query + JS `matchMedia`) | — | `prefers-reduced-motion` is a client-only signal; no server component |
| `visibilitychange` pause verification | Browser/Client (Page Visibility API) | — | Already implemented (D-02/D-51); this phase only tests it |
| Lighthouse runner | Tooling (outside `web/`, no tier) | — | A CLI invoked against a locally served `web/` build; not part of the shipped app's runtime tiers at all |

No capability in this phase touches a backend, database, or CDN tier — the entire app is static files served from GitHub Pages with a single client-side JS bundle. This matches the existing Architectural Responsibility precedent from Phases 1-3.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MOBX-01 | `renderPortraitBanner` and CSS deleted; no banner anywhere; desktop byte-identical above breakpoint | §1 below: exact deletion sites, exact line ranges, exact test-file impact, and the whole-milestone freeze-proof base commit (`57d2768`) |
| MOBX-02 | Landing page shows title chip + author credit + `?` opening the same help overlay; letter stays verbatim | §6 below: `index.html` structure inspected; native `<dialog>` recommended; STORY_LINKS/credit content identified for duplication |
| MOBX-03 | `aria-live="polite"` announcements; keyboard equivalents (Space/←/→/Home/`?`); 44×44 targets; Lighthouse A11y ≥90 | §2, §3, §7 below: exact roll-data shapes for announcement phrasing, exact keyboard-handler insertion point and reused helper functions, exact CSS sites needing the 44px fix (only one), and the real semantics of Lighthouse's `target-size` audit |
| MOBX-04 | `prefers-reduced-motion: reduce` disables transitions/throw-decay, doubles auto-hide to 8000ms | §5 below: enumerated every transition/animation source; confirmed the existing global rule already covers all of them; confirmed throw-decay and the rotation crossfade were never built; identified the one real code change (auto-hide doubling) |
| MOBX-05 | Playback pauses when page hidden | §8/D-51 below: confirmed the existing guard (`app.layoutMode !== "desktop"`) already covers landscape; this is a verify-only requirement |
</phase_requirements>

## Standard Stack

This phase adds **zero new runtime dependencies** to `web/` (per CLAUDE.md's explicit "no npm install, no build step" rule) and **zero new Python dependencies** to the test suite (Playwright is already a `pyproject.toml` dev dependency, version 1.59.0, already installed in `.venv`).

### Core (already present, reused as-is)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Playwright (Python) | 1.59.0 [VERIFIED: `pip show playwright` in `.venv`] | Existing test harness; also used to drive the Lighthouse target page | Already the project's sole browser-automation tool across Phases 1-3; adding a second one would violate no-parallel-implementations |
| `<dialog>` (native HTML element) | N/A (browser built-in) | Landing-page Help modal | Zero-dependency, has built-in `::backdrop`, `showModal()`/`close()`, and largely-correct default focus handling — eliminates hand-rolling a focus trap for a page that has no JS framework at all [CITED: MDN `<dialog>` element — training-data knowledge, not fetched this session, so tag as `[ASSUMED]` for exact browser-support specifics; the element itself is used nowhere else in this repo yet] |

### Supporting (new, tooling-only — lives outside `web/`)
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `lighthouse` (npm CLI, via `npx --yes lighthouse`) | 13.4.1 [VERIFIED: `npx --yes lighthouse --version` executed this session in this environment] | Runs the Accessibility category audit against a locally served `web/` | Invoked from a `tests/` script/pytest test, never added to any `package.json` — `npx` fetches and caches it under `~/.npm/_npx`, outside the repo entirely, satisfying D-40's "no npm dependency of the app" |
| Google Chrome (system-installed) | present at `/Applications/Google Chrome.app` [VERIFIED: `ls` this session] | Chrome instance Lighthouse's `chrome-launcher` auto-detects and drives | No `CHROME_PATH` override needed on this machine; if a target CI machine lacks system Chrome, point `CHROME_PATH` at Playwright's own bundled Chromium (`~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/`), which is already downloaded for the Playwright suite |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `npx lighthouse` CLI | Lighthouse's Node API (`import lighthouse from 'lighthouse'`) driven from a `.js` script | Requires a `package.json` + `node_modules` somewhere in the repo to `import` it reliably — `npx` needs neither, since it resolves/caches the package itself. Not worth the extra footprint for a single audit category. |
| Native `<dialog>` for the landing-page Help modal | Duplicating `web/app.js`'s manual `.mobile-help-overlay` div + hand-rolled focus trap into `index.html` | `index.html` has no JS today; hand-rolling a focus trap in a brand-new tiny inline `<script>` is exactly the kind of "deceptively complex" problem (see Don't Hand-Roll below) `<dialog>` exists to eliminate |
| `resetMobileChromeHideTimer()` reusing the existing `PREFERS_REDUCED_MOTION` constant | A second, mobile-specific `matchMedia("(prefers-reduced-motion: reduce)")` call | Two independent snapshots of the same OS preference is exactly the "second computation path" the project's no-parallel-implementations rule forbids; the existing constant is already correct (queried once at module load, same as the desktop cinematic) |

**Installation:** None. `npx --yes lighthouse <url> --only-categories=accessibility ...` requires no `npm install` step in this repo; it is already runnable in this environment (confirmed this session).

**Version verification:** `npx --yes lighthouse --version` → `13.4.1`, confirmed by direct execution in this environment on 2026-08-02. `axe-core` bundled inside that Lighthouse install is `4.12.1` (confirmed via `node_modules/axe-core/package.json` inside the npx cache).

## Package Legitimacy Audit

No new packages are added to any `requirements.txt`/`pyproject.toml`/`package.json` in this repo. `lighthouse` is invoked via `npx --yes lighthouse` (ephemeral, cached outside the repo) rather than installed as a project dependency, so the standard install-time legitimacy gate does not apply in the usual sense. For completeness:

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `lighthouse` | npm | Years (Google-maintained, part of Chrome DevTools) [ASSUMED — not run through the package-legitimacy seam this session; this is one of the most widely-known Google-published CLI tools in the ecosystem] | Very high (tens of millions/week class) [ASSUMED] | `github.com/GoogleChrome/lighthouse` [VERIFIED: license header inside the fetched package reads `Copyright 2016 Google LLC`, confirmed by direct file read this session] | OK (by inspection) | Approved — but not run through `gsd-tools query package-legitimacy check` since it is never installed as a repo dependency; if the planner wants the formal seam check anyway before scripting the `npx` invocation, run `gsd_run query package-legitimacy check --ecosystem npm lighthouse` |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────────────┐
                     │   repo-root index.html (NEW: MOBX-02) │
                     │   static HTML, own <style>, zero JS   │
                     │   today → gains: title chip, credit,  │
                     │   "?" button → <dialog> (native modal)│
                     └───────────────┬───────────────────────┘
                                     │ <a href="./web/">
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│ web/index.html  →  web/app.js (single module)                        │
│                                                                        │
│  window keydown listener (app.js:4564, EXISTING)                     │
│    ├─ Space  → togglePlayback()          [ALREADY layout-agnostic]   │
│    ├─ "?"    → openMobileSurface("help") [NEW: D-48, gated on        │
│    │                                       layoutMode !== "desktop"] │
│    └─ layoutMode !== "desktop" early branch [NEW: D-46/D-47]         │
│         ├─ ArrowRight/Left → rollStepFrom(wordPos, ±1) → setWordPos  │
│         └─ Home            → lastRollAtWord(wordPos) → setWordPos    │
│                               + togglePlayback() if not playing      │
│                                        │                              │
│                                        ▼                              │
│  render() → app.layoutMode branch (UNCHANGED dispatch point)         │
│    ├─ desktop  → renderAppShell()  [ONE edit this phase: D-37        │
│    │                                 removes the banner call]        │
│    ├─ portrait → renderMobilePortrait()                              │
│    └─ landscape→ renderMobileLandscape()                             │
│                                        │                              │
│                                        ▼                              │
│  updateMobileFieldLogFrame() / updateMobileLandscapeFrame()          │
│  (EXISTING, per-frame incremental DOM update — NOT full render)      │
│    └─ on a USER-CAUSED position change only (tap/double-tap/swipe/   │
│       rail-scrub/keyboard) → NEW: write text into one visually-      │
│       hidden aria-live="polite" region, mobile-shell-scoped only     │
│                               (never mounts on desktop)               │
│                                                                        │
│  resetMobileChromeHideTimer() (EXISTING, app.js:4336)                │
│    └─ NEW: delay = PREFERS_REDUCED_MOTION (existing const, app.js:237)│
│             ? CHROME_AUTOHIDE * 2 : CHROME_AUTOHIDE                   │
└──────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
              web/style.css (frozen; ONE sanctioned deletion: D-37)
              web/mobile.css (NEW: .mobile-cinema-scrub-fab 44px fix;
                               reduced-motion already inherited from
                               style.css's global blanket rule — no new
                               @media (prefers-reduced-motion) block needed
                               unless the planner wants belt-and-suspenders)
```

### Recommended Project Structure

No new directories. Files touched:
```
index.html              # MOBX-02: title chip, credit, "?" → <dialog>
web/app.js               # D-37 deletion, D-42..48 keyboard+live-region, D-40's timer edit
web/style.css             # D-37: delete .portrait-banner + its media block (ONLY sanctioned CSS edit)
web/mobile.css            # D-39: .mobile-cinema-scrub-fab 44px hit area
tests/test_desktop_smoke.py         # update 2 stale banner assertions/comments (see §1)
tests/test_mobile_portrait.py       # new: aria-live, keyboard, reduced-motion, visibilitychange assertions
tests/test_mobile_landscape.py      # new: same, landscape-specific + FAB size assertion
tests/test_lighthouse_accessibility.py  # NEW file: D-40's repeatable Lighthouse runner (recommended location)
```

### Pattern 1: Reuse the existing `PREFERS_REDUCED_MOTION` module constant
**What:** `app.js:237` already computes `const PREFERS_REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;` once at module load, and the desktop cinematic's `currentFocusAnimT()` already branches on it (`if (PREFERS_REDUCED_MOTION) return 1;`).
**When to use:** Any new reduced-motion-gated logic in this phase (specifically `resetMobileChromeHideTimer()`'s auto-hide doubling).
**Example:**
```javascript
// Source: web/app.js:236-239 (existing, verbatim)
const PREFERS_REDUCED_MOTION = (typeof window !== "undefined"
  && typeof window.matchMedia === "function"
  && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

// Recommended edit inside the EXISTING resetMobileChromeHideTimer() (app.js:4336):
function resetMobileChromeHideTimer() {
  clearTimeout(app.mobileChromeHideTimer);
  app.mobileChromeHideTimer = null;
  if (app.layoutMode === "landscape" && app.playing && !app.mobileSurface) {
    const base = window.GestureConstants?.CHROME_AUTOHIDE ?? 4000;
    const delay = PREFERS_REDUCED_MOTION ? base * 2 : base; // MOBX-04
    app.mobileChromeHideTimer = setTimeout(() => {
      app.chromeHidden = true;
      app.dom.mobileCinemaScrub?.classList.add("is-hidden");
    }, delay);
  }
}
```
Do NOT touch `web/mobile-gestures.js` to do this — `CHROME_AUTOHIDE` is defined there (`G.CHROME_AUTOHIDE = 4000`) but that file is byte-frozen (D-17); the doubling logic belongs entirely in `app.js`, which already reads the constant via `window.GestureConstants?.CHROME_AUTOHIDE`.

### Pattern 2: Reuse `rollMarkerModel(roll)` for outcome-aware announcement classification
**What:** `web/viz-model.js:58-82` already computes `{ paidCount, freeCount, isUntracked, isMissLike, cost }` for every roll, used today by the desktop sky-camera renderer to decide `single`/`binary`/`trinary`/`miss`/`free` marker styling.
**When to use:** Building the `aria-live` announcement string (D-43) — do not write a second miss/multi-grab classifier.
**Example:**
```javascript
// Source: web/viz-model.js:58-82 (existing, verbatim). CONFIRMED this session:
// app.js's existing `import { paidRollPerks, perkDisplayLabel, rollTotalCost,
// ... } from "./viz-model.js"` block (app.js:1-48) does NOT currently include
// rollMarkerModel — the other three are already imported and used, but this
// one needs a one-line addition to that same import block.
export function rollMarkerModel(roll) {
  const paidCount = paidRollPerks(roll).length;
  const freeCount = (roll.free_perks || []).length;
  const isUntracked = roll.evidence_kind === "untracked_acquisition";
  const isMissLike = roll.outcome !== "hit" && !isUntracked;
  const cost = isMissLike ? null : rollTotalCost(roll);
  // ... kind classification omitted; the four booleans/counts above are
  // exactly what an announcement string needs.
}
```

### Anti-Patterns to Avoid
- **A second `matchMedia("(prefers-reduced-motion...")` query:** see Pattern 1 — reuse the existing constant.
- **A throttled `aria-live` update:** D-42 explicitly forbids this (a throttle silently drops announcements, misrepresenting the roll count in the one channel whose job is to be truthful). Fire on every user-caused position change; stay silent during free playback (gate on the SAME callback sites the field-log frame update already uses to distinguish "user gesture" from "rAF playback tick").
- **A `::before` overlay technique applied to `.mobile-icon-btn.compact`:** unnecessary — that element already has a working, tested `padding`-based solution (see §3 below). Applying a second technique on top would be redundant churn.
- **Padding-based hit-area expansion on `.mobile-cinema-scrub-fab`:** would grow the visible circle+glow (border-radius:50%, box-shadow) because CSS `background`/`box-shadow` paint through the padding box by default — this is the ONE element where the `::before` overlay technique D-39 names is actually the correct (not just permitted) choice. See §3.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Landing-page modal + focus trap | A custom `.help-overlay` div + manual `keydown`-based focus wrap in a brand-new inline `<script>` on `index.html` | Native `<dialog>` + `showModal()`/`close()` | `index.html` has zero JS today; a hand-rolled focus trap is exactly the deceptively-complex problem (tab-order edge cases, Escape handling, backdrop click, restoring focus on close) that `<dialog>` already solves natively in every evergreen browser |
| Miss/multi-grab/untracked roll classification for the announcement string | A new `if (roll.outcome === "miss") ... else if (paidRollPerks(roll).length > 1) ...` chain inside the live-region code | `rollMarkerModel(roll)` from `viz-model.js` (already exists, already used by the desktop sky-camera renderer for the identical classification) | Two independent implementations of "what kind of roll is this" is exactly the no-parallel-implementations violation the project's own CLAUDE.md forbids |
| "Roll N of Total" numbering for the announcement | Deriving a new sequence number from `roll_label`/`roll_ordinal`/`predicted_ordinal` | `app.data.story.rolls.indexOf(roll) + 1` / `app.data.story.rolls.length` — the exact expression `mobileFieldLogRows()` (app.js:4022-4028) already uses for the field-log header count (`${rows.idx + 1} of ${rows.total}`) and the cinema-scrub count | `roll_label` is `null` on 669 of 670 rolls in the real dataset (only the very first roll has `"R1"`); `roll_ordinal`/`predicted_ordinal`/`source_ordinal` are three DIVERGENT numbering sequences per this project's own documented convention (predictor vs curator numbering never joins) — using any of them for a user-facing "Roll N of Total" would produce wrong or misleading numbers on 99.85% of rolls |
| A Lighthouse-driven local web server | A bespoke `http.server` invocation or a new fixture | `tests/helpers/web_runtime_site.py`'s existing `staged_web_runtime_site()` context manager, which already stages the fixture data package and serves it over a real local HTTP port via Python's `http.server` | Already battle-tested across Phases 1-3's entire Playwright suite; Lighthouse needs a real `http://` URL (not `file://`) to fetch `visualization_facts.json` correctly, and this fixture already provides exactly that |

**Key insight:** Almost every "new" piece of logic this phase seems to need already has an existing, tested equivalent somewhere in `app.js`/`viz-model.js`. The actual net-new code surface is small: one CSS rule (FAB hit-area), one `if (window.GestureConstants...)` timer edit, one keyboard-handler branch (three key cases, all calling existing functions), one new DOM node (the live region) wired into two existing update functions, and the landing-page HTML/CSS/tiny inline script.

## Common Pitfalls

### Pitfall 1: Assuming Lighthouse's `target-size` audit requires 44×44
**What goes wrong:** A task gets written as "fix X so Lighthouse's tap-target check passes," and when X already exceeds the audit's real 24×24 threshold, the task looks "already done" and gets skipped — but MOBX-03's literal 44×44 text requirement (a stricter, self-imposed bar) never gets verified.
**Why it happens:** The word "Lighthouse" and "44×44" appear together in D-39/D-40/MOBX-03's text, implying a causal link that doesn't exist in the actual tool. `axe-core`'s bundled `target-size` rule (confirmed by reading `node_modules/axe-core/axe.js` inside the fetched `lighthouse` npm package this session) defaults `minSize` to **24**, not 44 — this is WCAG 2.5.8 (AA, "Target Size Minimum"), a different, lower success criterion than WCAG 2.5.5 (AAA, "Target Size Enhanced," which is 44×44 and NOT part of Lighthouse's `wcag2a`/`wcag2aa` `runOnly` tag set that the accessibility gatherer requests).
**How to avoid:** Verify 44×44 with a direct `getBoundingClientRect()` Playwright assertion (the exact pattern `test_mobile_portrait.py:520-534` already uses for `.mobile-dock-transport button`), independent of the Lighthouse score. Treat the Lighthouse ≥90 gate and the literal "≥44×44 CSS px" requirement as two SEPARATE acceptance criteria that happen to both live under MOBX-03's text.
**Warning signs:** A plan task whose only verification step is "Lighthouse score ≥90" for a requirement whose text says "44×44."

### Pitfall 2: Re-implementing hit-area expansion for `.mobile-icon-btn.compact`
**What goes wrong:** A task is written to "add padding or a ::before overlay to `.mobile-icon-btn.compact` (mobile.css:305) to reach 44×44," duplicating work that Phase 2 (`STATE.md` decision "02-02: .mobile-icon-btn.compact uses a scoped box-sizing:content-box override") already shipped and that `test_mobile_portrait.py:520-534` already proves passes (`box["width"] >= 44` and `height >= 44`, asserted against `.mobile-dock-transport button` at a 320px viewport — the compact buttons live inside that dock transport).
**Why it happens:** D-37/D-39's own CONTEXT.md text describes both `.mobile-icon-btn.compact` (36×36) and `.mobile-cinema-scrub-fab` (40×40) together as needing the same fix, without noting that Phase 2 already closed out the first one.
**How to avoid:** Read `web/mobile.css:305-309` before writing the task — the `box-sizing: content-box; width: 36px; height: 36px; padding: 4px;` rule (content 36px + padding 8px + inherited 1px border ×2 ≈ 46px rendered/hit-tested box) already clears 44px. Scope this phase's actual CSS work to `.mobile-cinema-scrub-fab` only.
**Warning signs:** A plan task that touches `mobile.css:305` without first running the existing `test_mobile_portrait.py` size assertion to see it already passes.

### Pitfall 3: Growing the FAB's visible circle while trying to expand its hit area
**What goes wrong:** Applying the SAME `padding`-based technique used for `.mobile-icon-btn.compact` to `.mobile-cinema-scrub-fab` (`width:40px; height:40px; border-radius:50%; box-shadow: 0 0 22px ...`) would make the circle (and its glow) visibly 44-46px, not just its hit-testable box — because `background`/`box-shadow`/`border-radius` paint through the padding area by default (`background-clip`/box-shadow default to the border-box). This directly violates D-39's "without changing painted size" requirement AND the mobile.css comment's own stated intent that the FAB stay visually locked to the approved prototype reference.
**Why it happens:** Padding-based expansion works cleanly for `.mobile-icon-btn.compact` because that element's background is a subtle, mostly-invisible-anyway translucent rounded rect at low contrast against the panel behind it — a few extra pixels of that background are visually unremarkable. A glowing cyan circular FAB is the opposite case: any growth is immediately visible.
**How to avoid:** For the FAB specifically, use a transparent `::before` (or `::after`) pseudo-element, absolutely positioned with a negative inset (e.g., `inset: -2px` to go from 40px to 44px, or `-4px` to be safely over 44px), `content: ""`, no `background`/`box-shadow` — the FAB's own painted circle stays exactly 40×40, but a click/tap anywhere in the pseudo-element's larger box still targets the real `<button>` (pseudo-elements are not separate hit-test targets; a click within a positioned `::before`'s box dispatches to its host element). **Caveat, confirmed this session:** this technique improves REAL touch usability but will NOT be picked up by `getBoundingClientRect()`-based measurement (axe-core's `target-size` rule reads the host element's own layout box, which a `::before`'s absolute-position overflow does not change) — since the FAB is 40×40 and the real threshold is 24×24, this has zero effect on the Lighthouse score either way (see Pitfall 1). Write the verification for this element as a manual/visual check (does a tap 2px outside the visible circle still register?) or via `page.mouse.click()` at an offset coordinate in Playwright, not via `getBoundingClientRect()`.

### Pitfall 4: Announcement phrasing that treats "miss" as the edge case
**What goes wrong:** The plan's own locked template (`"Roll {n} of {total}. {perkName}, {cp} CP."`) renders literally as `"Roll 61 of 670. dash, dash CP."` for a miss when `perkName`/`cp` are naively substituted with placeholder dashes — and 410 of 670 rolls (61%) in the real dataset are misses [VERIFIED: `data/derived/visualization_facts.json` counted directly this session — `Counter({'miss': 410, 'hit': 260})`].
**Why it happens:** The template was written perk-first, implicitly modeling "roll = you got something," when the actual gameplay/data distribution is majority-miss.
**How to avoid:** Branch the announcement string on `rollMarkerModel(roll).isMissLike` (or `roll.outcome !== "hit"`) FIRST, before ever touching perk-name fields. See §2 below for concrete proposed phrasing for every outcome shape.
**Warning signs:** Any announcement-string code path that accesses `perkDisplayLabel(...)` or `paidRollPerks(...)[0].name` without first checking outcome.

### Pitfall 5: Do NOT bump STORAGE_VERSION just to purge the now-dead `LS_PORTRAIT_DISMISSED` key
**What goes wrong (the tempting-but-wrong fix):** Deleting `renderPortraitBanner()`/the `.portrait-banner` CSS also orphans the `LS_PORTRAIT_DISMISSED` constant (`app.js:62`), its state field (`app.portraitDismissed`, `app.js:145`), and its migration-purge entry (`app.js:428`). The instinct is to bump `STORAGE_VERSION` (currently `"3"`) to `"4"` so `migratePreviewStorage()` purges any lingering `bcf:portrait-dismissed` key one more time for users who dismissed the banner during the v3 era.
**Why that instinct is wrong here:** the actual blast radius of a version bump is much larger than it first looks. `grep -rn "preview-port-storage-version" tests/` [VERIFIED, counted this session] shows the literal string `"3"` seeded **34 times across four files** (`tests/test_desktop_smoke.py`, `tests/test_mobile_portrait.py`, `tests/test_mobile_landscape.py`, `tests/test_web_app_integration.py`) — every one of those fixtures represents "storage is already at the current version, so `migratePreviewStorage()` is a no-op and my seeded prefs survive intact." Bumping to `"4"` would require updating all 34 sites (or every test that seeds `bcf:*` prefs and expects them to survive page load would start silently failing the moment `migratePreviewStorage()` sees a version mismatch and wipes them). That is a large, purely-cosmetic churn: the orphaned `bcf:portrait-dismissed` key, left un-purged, has **zero functional impact** — nothing in the app ever reads it again once the JS constant/usages are deleted; it is inert dead data sitting in a small subset of returning users' `localStorage`.
**How to avoid:** Simply delete `LS_PORTRAIT_DISMISSED` and its three usage sites (`app.js:62,145,428,1098`). Leave `STORAGE_VERSION` at `"3"` and leave every seeded `"3"` value in the 34 existing test sites untouched. Do not add a task to bump the version for this reason alone — there is no future `bcf:*` key being ADDED this phase that would independently justify a bump (CLAUDE.md's "bump STORAGE_VERSION in the same change" rule is written for the case of adding new keys that need a clean default on upgrade, not for removing one that nothing reads anymore).
**Warning signs:** A plan task titled "bump STORAGE_VERSION to purge bcf:portrait-dismissed" — that is solving a non-problem at a cost of ~34 test-fixture edits.

## Code Examples

### The exact D-37 deletion sites (verified line numbers, this session, `HEAD` = `ef21947`)
```javascript
// web/app.js:62 — delete this line
const LS_PORTRAIT_DISMISSED = "bcf:portrait-dismissed";

// web/app.js:145 — delete this line (inside the app state object literal)
portraitDismissed: readStoredBoolean(LS_PORTRAIT_DISMISSED, false),

// web/app.js:428 — delete this line from migratePreviewStorage()'s clear-list
// (recommend replacing with a literal string per Pitfall 5, or a one-line
// comment noting the historical key name, per planner's call)
LS_PORTRAIT_DISMISSED,

// web/app.js:1098 — delete this line from renderAppShell() (the ONE
// sanctioned edit to a §0.2 read-only function this milestone)
app.portraitDismissed ? null : renderPortraitBanner(),

// web/app.js:1228-1233 — delete the whole function
function renderPortraitBanner() {
  return el("div", { class: "portrait-banner is-visible", role: "status" },
    el("span", {}, el("strong", { text: "Best in landscape." }), " The Forge timeline reaches across millions of words - rotating gives the scrubber room to breathe."),
    el("button", { type: "button", onClick: () => { app.portraitDismissed = true; store(LS_PORTRAIT_DISMISSED, true); render(); }, text: "got it" }),
  );
}
```
```css
/* web/style.css:325-361 — delete this whole block (comment through the
   closing brace of the media query), verified via `grep -n` this session:
   line 325 comment, 326-359 rule bodies, 360-362 the media query wrapper.
   Line 363 (`.app-main {`) must survive untouched immediately after. */
```

`app.js:73-93`'s `MOBILE_LAYOUT_QUERY` comment explicitly documents and anticipates this exact deletion ("`style.css:360` keeps the old query and is deliberately NOT edited... Phase 4 deletes it outright") — no other code depends on the deleted CSS surviving.

### The two `tests/test_desktop_smoke.py` sites needing an update (not a "keep byte-identical" file — Phase 2 already edited it once for F-02)
```python
# tests/test_desktop_smoke.py:119-123 and :329 currently read:
expect(page.locator(".portrait-banner")).to_be_hidden()
# Playwright's to_be_hidden() treats ZERO MATCHING ELEMENTS as "hidden," so
# this assertion will keep PASSING even after the element is deleted from
# the DOM entirely — but its accompanying comment (lines 118-122, referencing
# "web/app.js:1084" and "style.css:326/360") becomes factually wrong once
# those lines no longer exist. Recommend replacing with the same idiom the
# OTHER three test files already use for the identical fact:
assert page.evaluate("document.querySelector('.portrait-banner')") is None
# and rewriting the stale comment to describe deletion, not "hidden by CSS."
```

### The keyboard handler insertion point (D-46/D-47/D-48)
```javascript
// web/app.js:4564 — window.addEventListener("keydown", event => { ... })
// Insert a mobile-mode early branch AFTER the existing `editable` guard
// (so a focused text control still blocks all of these, matching desktop's
// own convention) and AFTER the Space case (Space already works cross-layout
// — see Pitfall discussion; no change needed there), but BEFORE the
// desktop-only 10000/2000-word ArrowLeft/Right stepping:
if (app.layoutMode !== "desktop") {
  if (event.key === "ArrowRight") {
    const next = rollStepFrom(app.wordPos, 1);       // existing helper, app.js:814
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
    // NOT word 0 (which is what desktop's own Home key does two lines
    // below this branch and must keep doing).
    const target = lastRollAtWord(app.wordPos);        // existing helper, app.js:798
    if (target) setWordPos(target.word_position);
    if (!app.playing) togglePlayback();
    event.preventDefault();
    return;
  }
  if (event.key === "?") {
    openMobileSurface("help");   // already toggles closed if already open (app.js:3097-3113)
    event.preventDefault();
    return;
  }
}
```
Note `Space` needs NO branch here — the existing unconditional `if (event.key === " ") { ...; togglePlayback(); ... }` case a few lines above already fires identically regardless of `app.layoutMode` [VERIFIED: read the full handler this session, `app.js:4564-4584` — no `layoutMode` check exists anywhere in it today].

### Live-region announcement phrasing (D-43), grounded in the real data (all counts VERIFIED against `data/derived/visualization_facts.json` this session)
| Outcome shape | Real-data example | Recommended announcement | Source fields used |
|---|---|---|---|
| Hit, single paid perk | 209 of 260 hits have `paidCount===1` [VERIFIED, recounted this session after an earlier arithmetic slip] | `"Roll 12 of 670. Workshop, 0 CP."` | `perkDisplayLabel(paidRollPerks(roll)[0])`, `rollTotalCost(roll)` |
| Hit, free-only (no paid perk) | 0 of 260 hits have `paidCount===0` [VERIFIED this session — every real "hit" in the current dataset has at least one paid perk]; the fallback chain exists in code (`mobileFieldLogPrincipalName`'s `paidRollPerks(roll)[0] ?? (roll.free_perks||[])[0]`) but has no live example today | `"Roll 12 of 670. Access Key (free)."` (code path should exist for robustness, per the existing fallback chain, but do not treat this as an observed/common case) | `perkDisplayLabel(roll.free_perks[0])` |
| Hit, multi-grab (>1 paid perk) | 51 of 670 rolls, e.g. `roll_label:"R56"`, `["Science! Mechanics","Science! Engineering"]`, `purchased_perk_cost_total: 200` [VERIFIED: dumped this exact roll this session] | `"Roll 56 of 670. Science! Mechanics and 1 more, 200 CP."` (use `paidCount - 1` for the "N more" count so it stays accurate at ≥3) | `rollMarkerModel(roll).paidCount`, `perkDisplayLabel(paidRollPerks(roll)[0])`, `rollTotalCost(roll)` |
| Miss | 410 of 670 rolls (61%) — the COMMON case, must not be an afterthought | `"Roll 61 of 670. Miss."` (deliberately terse per D-45's "negligible cost" framing — do not append `miss_cost_estimate`, which reads as confusing jargon in speech) | `rollMarkerModel(roll).isMissLike` |
| `source_kind === "trigger"` | exactly 1 roll in the real dataset, `word_position: null` [VERIFIED this session] — this is a starting-bonus roll with no real timeline position | Since `word_position` is `null`, this roll can never be the live-edge target of a user gesture in the first place (nothing can scrub/tap TO a null position) — **no special-case phrasing is needed**; if it is ever reachable, fall through to the ordinary hit/miss phrasing above, since its `outcome`/`purchased_perks` shape is identical to any other hit |
| `evidence_kind === "untracked_acquisition"` | 0 rolls in the current dataset [VERIFIED this session — `Counter` returned zero] | Not reachable today; if it ever appears, `rollMarkerModel(roll).isUntracked` is already computed and can route to a distinct phrase, but do not build dead-code branches for a case with zero live examples — flag as an Open Question instead |

The `{n}`/`{total}` numbers should be `app.data.story.rolls.indexOf(roll) + 1` and `app.data.story.rolls.length` — the identical expression `mobileFieldLogRows()` already computes (`app.js:4022-4028`) and the field-log header/cinema-scrub count already display (`app.js:4105,4185,4249,4252`). Do not use `roll.roll_label` (null on 669/670 rolls) or any `*_ordinal` field (three divergent numbering systems per this project's own established convention — see MEMORY.md "BCF roll numbering").

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| "Portrait banner suggesting rotation" as the mobile fallback | A real, purpose-built mobile portrait+landscape UI (Phases 1-3) | This milestone | The banner and its dismissal state (`bcf:portrait-dismissed`) become permanently dead code; Phase 4 is the cleanup |
| Lighthouse's PWA category's "tap-targets" audit (historical) | Lighthouse's Accessibility category's `target-size` audit (axe-core, WCAG 2.5.8, 24px default) | Lighthouse v10 removed the PWA category entirely; `target-size` has lived in Accessibility since 2023 [VERIFIED: `target-size.js`'s license header reads "Copyright 2023 Google LLC," read directly from the fetched package this session] | Any pre-2023 mental model of "Lighthouse checks 44px tap targets under a PWA audit" is stale; the current, only tap-target check that exists is the 24px axe-core rule under Accessibility |

**Deprecated/outdated:** The `.portrait-banner` CSS/JS pair itself — this whole phase's D-37/D-38 is retiring it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `<dialog>`'s default focus-trap/backdrop/Escape behavior is sufficient for the landing-page Help modal without extra JS beyond `showModal()`/`close()` | Don't Hand-Roll, Standard Stack | Low — if a gap is found (e.g., older-Safari `<dialog>` quirks), the fallback is a few more lines of the same inline `<script>`, not a different architecture. This was not verified against a live browser this session (no `<dialog>` currently exists anywhere in this repo to inspect); tag as training-data knowledge. |
| A2 | axe-core 4.12.1's `target-size` rule's spacing-exception logic (elements smaller than 24px can still pass if they have sufficient clear space around them) does not materially change any conclusion in this doc, since every element discussed already exceeds 24px on its own | Pitfall 1, Common Pitfalls | Low — this doc's core claim (24px default threshold, not 44px) was read directly from source (`minSize = (options?.minSize) || 24` in `axe.js`), which is solid; the spacing-exception detail is a refinement that doesn't change the "already passes" conclusion for 36×36/40×40 elements |
| A3 | The recommended announcement phrasing wording ("Miss.", "and N more") is Claude's proposed copy, not a wording Dre has explicitly approved | Code Examples (announcement table) | Medium — if the plan/discuss-phase treats this as final copy without a check-in, and Dre's taste differs, this is a one-line-per-branch string edit, not a structural rework. D-43 explicitly assigns "propose phrasing" to research, so this is within scope, but final copy approval is reasonable to fold into the phase's own gate review rather than treating it as pre-locked. |

## Open Questions

1. **Landing-page Help dialog content scope**
   - What we know: MOBX-02's literal text says the `?` button opens "the same help overlay"; the in-app overlay includes title/author/links (duplicable) AND a full gesture how-to (tap/double-tap/swipe — meaningless before entering the app) AND a persistence note.
   - What's unclear: whether Dre wants the full gesture how-to duplicated on the static landing page too, or just the credit block + a "full help is available once you open the visualization" pointer.
   - Recommendation: this is explicitly Claude's Discretion per `04-CONTEXT.md` ("whether the landing page's `?` reuses the in-app Help markup or duplicates it... permits either"); propose the condensed credit-only version at plan time and let the phase's own gate review (with Dre) confirm or expand it — low cost to change either way since it's static HTML.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js / `npx` | D-40 Lighthouse runner | ✓ [VERIFIED this session] | Node v26.0.0, npm 11.12.1 | — |
| `lighthouse` (via `npx --yes lighthouse`) | D-40 Lighthouse runner | ✓ [VERIFIED this session — downloaded, cached, ran `--version` and `--help` successfully] | 13.4.1 | If `npx` has no network access on a future CI runner, the package must be pre-fetched into the npx cache once with network, or `CHROME_PATH` + a vendored lighthouse tarball would be needed — not a concern on this dev machine, worth a note for the planner's CI-portability thinking |
| Google Chrome (system) | Lighthouse's Chrome launcher | ✓ [VERIFIED this session] | present at `/Applications/Google Chrome.app` | Playwright's own bundled Chromium (`~/Library/Caches/ms-playwright/chromium-1217/chrome-mac-arm64/Google Chrome for Testing.app`) is already downloaded and can be pointed to via `CHROME_PATH` if system Chrome is ever absent on a different machine |
| Playwright (Python) + Chromium browser | Existing + new Playwright tests, and serving the Lighthouse target | ✓ [VERIFIED this session] | playwright 1.59.0, chromium builds 1217/1234 cached | — |
| Real iOS Safari hardware | Phase gate device pass (per `04-CONTEXT.md`'s specifics, budgeted per Phase 3's precedent) | Not verified this session (no device attached in this environment) | — | None — this is explicitly a human-gate item (Dre's own device), not something this research session can substitute for; carried forward exactly as Phases 2/3 did |

**Missing dependencies with no fallback:** None that block automated implementation work; the real-device iOS pass remains a human-only gate as in every prior phase.

**Missing dependencies with fallback:** Network-dependent first-fetch of the `lighthouse` npm package (already resolved in this environment; flagged for CI-portability awareness only).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + `pytest-playwright`-style manual Playwright fixtures (Python), configured via `pyproject.toml`'s `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| Config file | `/Users/dre/src/bcf-visualization/pyproject.toml` |
| Quick run command | `.venv/bin/python -m pytest tests/test_mobile_portrait.py -x -q` (or the specific new test file for a given task) |
| Full suite command | `.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py -v` (the exact invocation Phase 3's closing sweep used; 53/53 passing at the end of Phase 3 per `03-04-SUMMARY.md`) |

Note: this worktree has no `.venv`; the `.venv` with `playwright`/`pytest` installed lives at the main repo checkout (`/Users/dre/src/bcf-visualization/.venv`). Confirm at plan/execute time which `.venv` the execution environment should actually use — this may already be handled by however this worktree's execution environment is provisioned, but it was NOT independently present in this worktree at research time.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOBX-01 | Banner gone; desktop byte-identical | integration + freeze-diff | `pytest tests/test_desktop_smoke.py -x -q` + `git diff --exit-code 57d2768 HEAD -- web/style.css` (expect exactly the D-37 hunk) | ✅ test file exists; freeze-diff is a shell command, not a pytest test — recommend wrapping it as a pytest test too (`test_freeze_proof.py` or an addition to an existing file) so it reruns automatically at future gates, matching D-40's "committed, repeatable" philosophy applied consistently |
| MOBX-02 | Landing chip/credit/`?` dialog | new Playwright test against `index.html` directly (not `web/`) | new: `pytest tests/test_landing_page.py -x -q` | ❌ Wave 0 gap — no test file targets repo-root `index.html` today; all existing Playwright fixtures target `/web/` |
| MOBX-03 (live region) | Announces on user gesture, silent during playback | integration | extend `tests/test_mobile_portrait.py`/`test_mobile_landscape.py` | ❌ Wave 0 gap — no `aria-live` assertions exist in any current test file (`grep -rn "aria-live" tests/` returned nothing this session) |
| MOBX-03 (keyboard) | Space/←/→/Home/`?` | integration | extend existing mobile test files | ❌ Wave 0 gap — no keyboard-event tests exist for mobile layout modes today |
| MOBX-03 (44×44) | Every tappable target | integration | extend `getBoundingClientRect()` pattern already at `test_mobile_portrait.py:520-534` to cover `.mobile-cinema-scrub-fab` specifically | Partial — the pattern and the compact-button case already exist and pass; only the FAB assertion is new |
| MOBX-03 (Lighthouse ≥90) | Automated a11y score | new integration | new: `pytest tests/test_lighthouse_accessibility.py -x -q` (shells to `npx --yes lighthouse ... --only-categories=accessibility`, parses JSON, asserts `>= 0.90`) | ❌ Wave 0 gap |
| MOBX-04 | Reduced-motion CSS + timer doubling | integration | extend existing mobile test files with a `prefers-reduced-motion` emulated context (`page.emulate_media(reduced_motion="reduce")` in Playwright) | ❌ Wave 0 gap — no test in this repo currently emulates `prefers-reduced-motion` |
| MOBX-05 | Pause on hidden | integration | new: emulate `document.visibilityState` via `page.evaluate` + `dispatchEvent(new Event("visibilitychange"))`, or Playwright's own page-visibility emulation if available in 1.59.0 | ❌ Wave 0 gap — this is a VERIFY-only requirement (D-51) but still needs its own automated test since none exists yet for either portrait or landscape |

### Sampling Rate
- **Per task commit:** the relevant single test file (`pytest tests/test_mobile_portrait.py -x -q`, etc.)
- **Per wave merge:** the full four-file command above
- **Phase gate:** full suite green + the Lighthouse score check + the freeze-diff check, before the `/gsd-verify-work`/human device-pass gate

### Wave 0 Gaps
- [ ] `tests/test_lighthouse_accessibility.py` — new file, D-40's Lighthouse runner, reusing `staged_web_runtime_site()`
- [ ] `tests/test_landing_page.py` — new file, MOBX-02, targets repo-root `index.html` (a genuinely new test surface — every existing Playwright fixture targets `/web/`, none targets the root landing page)
- [ ] `aria-live` assertions — add to `test_mobile_portrait.py`/`test_mobile_landscape.py`
- [ ] Keyboard-equivalent assertions — add to `test_mobile_portrait.py`/`test_mobile_landscape.py`
- [ ] `prefers-reduced-motion` emulation coverage — add to `test_mobile_portrait.py`/`test_mobile_landscape.py` (Playwright 1.59.0 supports `page.emulate_media(reduced_motion="reduce")` — verify this exact API name against the installed version at plan/execute time; it is a well-established Playwright feature but was not independently confirmed against 1.59.0's API surface this session)
- [ ] `visibilitychange`-pause assertions — add to both portrait and landscape test files (verifying D-51, not implementing new behavior)
- [ ] `.mobile-cinema-scrub-fab` size assertion — add to `test_mobile_landscape.py`, mirroring `test_mobile_portrait.py:520-534`'s existing pattern

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | This app has no auth of any kind (static site, no login) |
| V3 Session Management | No | No server sessions; `localStorage` prefs are not session/auth state |
| V4 Access Control | No | No access-control boundaries exist in a static, unauthenticated visualization |
| V5 Input Validation | Partial-yes | The one live user-facing text this phase introduces (the announcement string, the landing-page chip/dialog text) is entirely author-controlled static/derived data, never user input — but the EXISTING convention (`T-03-01`, confirmed in `mobileFieldLogSubChildren`'s comment: "Every text fragment flows through `el()`'s `text` prop (textContent), never string-concatenated markup") must be followed for any new DOM text this phase writes, since `evidence_quotes` text can contain literal `<`/`>` characters and must never be inserted via `innerHTML`. |
| V6 Cryptography | No | No cryptographic operations anywhere in this phase or this app |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DOM-based XSS via evidence-quote text (pre-existing risk surface, not introduced by this phase but touched by it if the live region ever echoes a perk/quote string) | Tampering/Elevation via injected markup | Continue the existing `el()`-helper convention (always `.textContent`, never string-concatenated HTML) for every new DOM write this phase makes — the live-region text node, the landing-page dialog content, and any new dock/chip text |
| `rel="noopener noreferrer"` on `target="_blank"` links (already the established convention for `STORY_LINKS`/GitHub links in `app.js`) | Tampering (reverse-tabnabbing) | Apply the identical `target="_blank" rel="noopener noreferrer"` pattern to any new external link added to `index.html`'s landing-page credit block (the existing `.secondary-link` "View source" link in `index.html` already does this correctly — mirror it) |

This is a client-only, static-hosting, no-backend, no-auth application; the security surface for this phase is narrow and almost entirely "don't regress the existing XSS-safe text-insertion convention."

## Sources

### Primary (HIGH confidence — direct codebase/tool inspection this session)
- `web/app.js` (full file grep + targeted reads: lines 1-250, 595-635, 798-870, 1080-1240, 3097-3130, 3725-3770, 4020-4110, 4310-4440, 4555-4600) — layout dispatch, keyboard handler, roll normalization, mobile surfaces, help overlay, field-log rows, chrome auto-hide timer
- `web/viz-model.js` (lines 40-139) — `paidRollPerks`, `rollTotalCost`, `rollMarkerModel`, `perkDisplayLabel`
- `web/style.css` (lines 55-70, 300-363) — the existing global `prefers-reduced-motion` blanket rule, the exact `.portrait-banner` deletion range
- `web/mobile.css` (lines 195-215, 265-310, 335-355, 675-715) — every transition/animation source, the compact-button hit-area technique, the FAB definition
- `data/derived/visualization_facts.json` — direct `python3 -c "json.load(...)"` inspection: 670 total rolls, outcome/source_kind/evidence_kind distributions, concrete hit/miss/multi-grab/trigger example rows
- `index.html` (repo root, full file) — landing-page structure, existing CSS variables, existing `prefers-reduced-motion` handling for its own decorative animation
- `tests/test_desktop_smoke.py`, `tests/test_mobile_portrait.py`, `tests/test_mobile_landscape.py`, `tests/test_mobile_plumbing.py` (targeted greps + reads) — existing assertion patterns, the already-passing 44px size test, `STORAGE_VERSION` seed values
- Git history (`git log`, `git show`, `git diff`) against this worktree's `HEAD` (`ef21947`) — resolved the pre-Phase-1 base commit `57d2768`, confirmed zero drift in `web/style.css` and `renderAppShell()`'s function body since that commit
- `lighthouse` npm package v13.4.1 fetched live via `npx --yes lighthouse` this session (`--help`, `--list-all-audits`, and direct source reads of `core/config/default-config.js`, `core/gather/gatherers/accessibility.js`, `core/audits/accessibility/target-size.js`) — confirmed `target-size` audit exists, its weight (7) and group (`a11y-best-practices`), and that the accessibility gatherer runs it with no `minSize` override
- `axe-core` v4.12.1 (bundled dependency of the above) — direct source read of `axe.js` confirming `minSize = (options?.minSize) || 24` as the `target-size` rule's actual threshold

### Secondary (MEDIUM confidence)
- `<dialog>` element's browser-support/behavior specifics (A1 in Assumptions Log) — training-data knowledge, not independently re-verified this session against current browser versions

### Tertiary (LOW confidence)
- None used as load-bearing claims in this document; every load-bearing claim above is either Primary (direct inspection) or explicitly flagged `[ASSUMED]` in the Assumptions Log.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new runtime dependency; the one new tool (`lighthouse` via `npx`) was actually run in this environment this session
- Architecture: HIGH — every insertion point (keyboard handler, timer function, render dispatch, field-log helpers) was located by direct grep/read, with exact line numbers cited against this session's `HEAD` (`ef21947`)
- Pitfalls: HIGH — three of the five pitfalls (Lighthouse's real threshold, the already-shipped compact-button fix, the miss-majority data distribution) were discovered by direct measurement/inspection, not inference
- Announcement phrasing: MEDIUM — the underlying data shapes and reusable helper functions are HIGH confidence (verified); the exact proposed wording ("Miss.", "and N more") is a recommendation, not yet Dre-approved copy (see A3)

**Research date:** 2026-08-02
**Valid until:** This is the final phase of the mobile-ux workstream and touches no fast-moving external API — validity is bounded only by whether the codebase itself changes before this phase executes (i.e., valid until the next commit lands on this branch that touches any of the cited line numbers). Re-grep line numbers at plan-write time if any other work has landed on this branch since `ef21947`.
