# Mobile UX — Integration plan (v1)

**Source of truth.** This document tells the implementing agent/engineer
how to fold the mobile UX prototype into the live `web/` app. It
references the spec and prototype, but the *contracts* live here.

| Artifact | Path | Status |
|---|---|---|
| Gesture spec | `redesign/mobile-ux/gesture-contract.html` | Locked v1 |
| Visual mocks | `redesign/mobile-ux/index.html` | Approved |
| Working prototype | `redesign/mobile-ux/prototype.html` (+ `prototype/*`) | Approved |
| This plan | `redesign/mobile-ux/INTEGRATION_PLAN.md` | — |

When the plan and the prototype disagree, **this plan wins** — the
prototype was a fidelity tool, not a production target.

---

## 0 · Desktop is FROZEN

> **Read this section first. Do not skip it.**

The existing desktop / large-screen visualization is **working and
shipped**. The mobile UX work must not regress it in any way.

### 0.1 The hard rules

1. **No visual or behavioural change at viewport ≥ 1100px CSS pixels.**
   Pixel-for-pixel parity with `main` is the acceptance bar.
2. **Do not edit the body of any existing render function** (anything
   named `renderXyz()` in `app.js`). Treat them as a closed API. You
   may *call* them from new mobile code, you may *not* refactor them.
3. **Do not "extract a shared component"** between desktop and mobile.
   It looks tidy and will break desktop in subtle ways (sizing
   assumptions, animation hooks, layout interactions). Duplicate
   freely; mobile is a separate presentation.
4. **Branch as early as possible.** The dispatch point is
   `render()` — first thing it does is read `app.layoutMode` and
   call `renderAppShell()` (desktop), `renderMobilePortrait()`, or
   `renderMobileLandscape()`. Below that branch, **the desktop path
   must execute exactly the code it executed before this change**.
5. **No edits to existing CSS rules.** New mobile CSS goes in its own
   block, scoped behind the mobile media query. If you find yourself
   wanting to "just tweak" a desktop rule for consistency, stop —
   that's a desktop change in disguise.
6. **No edits to existing CSS variables** (`--cyan`, `--green`, type
   scales, etc.). They are part of the design system. Reuse them in
   new rules; don't redefine them.

### 0.2 Functions that are read-only for this work

You may *call* these. You may *not* modify them. If you think you
need to, your design is wrong — branch earlier or duplicate.

```
renderAppShell, renderHeader, renderPackageSelector, renderInfoPopover,
renderScrubber, renderDateTrack, renderChapterTrack, renderPovTrack,
renderRollTrack, renderAxisTrack, renderScrubberControls,
renderStatStrip, renderPlaythrough, renderViewportFrame,
renderCarousel, renderConstellationCard, renderUnresolvedCard,
renderSkyCamera, renderSpotlight, renderBeam,
renderNarrativeReadout, renderRecentRolls,
renderDetail, renderSelectedChapter, renderRecentAcquisitions,
renderConstellationBars, renderRollLog, renderRollRow
```

`setWordPos`, `setMode`, `setRollLocation`, `chapterAtWord`,
`recentRolls`, `cumulativeAt`, `formatWords`, etc. are also stable —
call them, don't modify them.

### 0.3 If you change one of these by accident…

You will produce one or more of:

- Carousel cards misaligned on first render
- Sky-camera cinematic firing at the wrong word position
- Scrubber roll dots shifting one pixel left
- Reduced-motion users getting animations
- The "Best in landscape" banner re-appearing on certain widths

These are all regressions. **The smoke test in §6 catches them — run
it before claiming done.**

### 0.4 Safe surface

You can edit anything in this list freely:

- `render()` itself (only to add the `app.layoutMode` branch)
- `migratePreviewStorage()` (only to update key list + bump version)
- `app.*` state object (only to add new fields)
- `web/style.css` (only to add new rules; not to edit existing ones)
- The `meta name="viewport"` tag in `web/index.html`
- The top-level `index.html` landing page (the Survey letter file)

You can create new files freely:
`web/mobile-gestures.js`, `web/mobile.css`, new `renderMobile*`
functions inside `app.js` (preferably grouped at the end of the file
with a `// ── Mobile UX ─────────` divider).

### 0.5 The desktop smoke test

Before claiming any phase done, run this manually on a desktop
viewport (≥ 1100px wide):

1. Open the page. The header, scrubber, carousel, and field log
   render as they did on `main`. No "Best in landscape" banner.
2. Click play. The playhead advances. A roll cinematic fires when
   one is reached.
3. Open the carousel; scrub to roll #47. The constellation card
   centers; outline animates in if enabled.
4. Toggle Details mode. The full roll log table renders.
5. Resize the window from 1920px down to 1101px — UI stays as
   desktop. At 1100px and below, mobile takes over. At 900px and
   below, the lower mobile breakpoint engages.
6. Resize back up — desktop restores cleanly with no flash of
   stale layout.

If any of those six fail, the change is a regression regardless of
what mobile is doing.

---

## 1 · Locked design decisions

These were left open in the spec; they're now fixed for v1 shipping.

| Decision | v1 default |
|---|---|
| Tap-on-sky to pause | **ON** (opt-out in Settings → Comfort) |
| Swipe direction on sky | **Right = forward in time** (left = backward) |
| Throw-to-scrub | **Capped at ±5 rolls/throw**; ease-out 600ms |
| Chrome auto-hide | **Landscape only**; portrait C keeps the dock visible |
| Long-press preview | **Deferred to v2** — do not implement now |
| Pinch zoom | **Deferred to v2** — the segmented zoom control (1×/2×/4×/8×) covers v1 |
| Reduced-motion respect | Required — see §6 |

---

## 2 · Scope

**In scope for v1 ship:**

- Replace the "rotate to landscape" banner (`renderPortraitBanner`) with
  a real mobile playthrough mode.
- Two responsive layouts driven by `@media (orientation)`:
  - **Portrait C** — sky over a mini-rail dock
  - **Landscape F** — sky + field-log rail + auto-hiding cinema scrub
- Gesture surface from the spec: tap-pause, double-tap-live-edge,
  horizontal swipe-scrub-by-roll, rail drag-scrub, rotation hand-off.
- Settings flyout (mode, on-roll, speed, **timeline zoom**, comfort).
- About flyout (story title + author + source links + dataset stats).
- Help overlay (gestures + credits; auto-shown first run).
- Scrubber cluster-binning (any zoom; collapse rolls within 5px).
- Persistence of all new prefs in the existing `bcf:` namespace with
  one new storage-version bump.

**Out of scope (v2 backlog):**

- Pinch-to-zoom on scrubber
- Long-press roll-dot preview tooltip
- Edge swipe-down from top to peel field log over the sky (portrait)
- Throw-to-scrub inertia (the cap is set; the implementation is v2)
- Real `constellation_outlines` rendering inside the sky (prototype
  uses a procedural diamond placeholder — keep it for now)

---

## 3 · File-level changes

### 3.1 `web/app.js`

| Change | Reference |
|---|---|
| **Delete** `renderPortraitBanner()` and its call in `renderAppShell()`. | `app.js:969-974` |
| **Remove** `LS_PORTRAIT_DISMISSED` from `migratePreviewStorage()` purge list (key is going away). | `app.js:60`, `app.js:79` |
| **Add** new state keys to `app.*`: `app.layoutMode` (`"desktop"` \| `"portrait"` \| `"landscape"`), `app.helpOpen`, `app.settingsOpen`, `app.infoOpen`, `app.chromeHidden`, `app.tapToPause`, `app.haptics`. | new |
| **Add** orientation detection on init + on `resize` / `orientationchange`. Logic: if `(max-width: 900px) or (orientation: portrait) and (max-width: 1100px)` use mobile path, otherwise `"desktop"`. | mirrors current banner media query |
| **Add** new `LS_*` constants matching the spec: `bcf:timeline-zoom`, `bcf:tap-to-pause`, `bcf:haptics`, `bcf:help-seen`. | §4 below |
| **Bump** `STORAGE_VERSION`. The migration purges the new keys on bump so we start clean. | `app.js:81-87` |
| **Branch** `render()` on `app.layoutMode`. Existing `renderAppShell` is desktop; add `renderMobilePortrait` + `renderMobileLandscape`. | `app.js:803-816` |
| **Reuse, don't rewrite,** the existing model code: `setWordPos`, `setMode`, `setRollLocation`, `chapterAtWord`, `recentRolls`, `cumulativeAt`, `formatWords`, etc. | `app.js:677-700`, `:622-680` |
| **Adapt** `renderNarrativeReadout` for the landscape rail (top 2/3). New file or in-place is fine; the field log model already exists. | `app.js:2098-2119` |
| **Add** `renderMobileScrubber()` and `renderMobileCinemaScrub()`. Port from `redesign/mobile-ux/prototype/scrubber.jsx` (binning + zoom + auto-pan). | new |
| **Add** gesture wiring. Port the two helpers from `redesign/mobile-ux/prototype/gestures.js` verbatim (`attachSkyGestures`, `attachRailScrub`) and call them in `render()` after the DOM is mounted. | new |

### 3.2 `web/style.css`

| Change | Reference |
|---|---|
| **Delete** `.portrait-banner` rules and the media-query block that toggles it. | `style.css:340-363` |
| **Add** mobile layout rules adapted from `redesign/mobile-ux/prototype/styles.css`. Keep the existing CSS variables (`--cyan`, `--green`, etc.) — they're already compatible. | port |
| **Wrap** new mobile rules in `@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px)` so the desktop UI is untouched. | mirror existing breakpoint |
| **Add** orientation-scoped rules inside that block, using the *same* `@media (orientation: portrait)` / `(orientation: landscape)` pattern from the prototype. | port |
| **Hide** the existing `.scrubber-stack`, `.scrubber-controls`, `.stat-strip`, `.app-header` chrome on mobile; the new layouts replace them. | new |

### 3.3 `web/index.html`

| Change |
|---|
| Tighten the viewport meta to match the prototype: `width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1, user-scalable=no`. |
| No other changes — the new layouts inject into `#root` via `render()`. |

### 3.4 `index.html` (landing page)

| Change |
|---|
| Add the small story-title chip + author credit at the top, plus the `?` help button — as designed in the Landing mockup. The Survey letter stays verbatim. |
| The `?` button opens the same help-overlay surface used in-app (extract into a shared partial or duplicate the markup; either is fine for v1). |

### 3.5 New files

| Path | Purpose |
|---|---|
| `web/mobile-gestures.js` | Port of `prototype/gestures.js`. Loaded before `web/app.js`. |
| `web/mobile.css` | (Optional split) — the mobile-only block, if `style.css` is getting unwieldy. |

---

## 4 · Storage keys

All new keys live in the existing `bcf:` namespace. **Bump
`STORAGE_VERSION`** so any stale values get cleared on first load.

| Key | Type | Default | Notes |
|---|---|---|---|
| `bcf:bookmark` | number (word pos) | 0 | already exists |
| `bcf:speed` | 0.5 \| 1 \| 2 \| 4 | 1 | already exists |
| `bcf:mode` | `"playthrough"` \| `"details"` | `"playthrough"` | already exists |
| `bcf:on-roll` | `"cinematic"` \| `"skip"` \| `"pause"` | `"cinematic"` | already exists as `LS_ON_ROLL_BEHAVIOR` |
| `bcf:timeline-zoom` | 1 \| 2 \| 4 \| 8 | 1 | **new** — desktop currently uses `LS_ZOOM` (`bcf:zoom`?); keep them separate to avoid coupling desktop's continuous zoom with mobile's quantized steps |
| `bcf:tap-to-pause` | "true" \| "false" | "true" | **new** |
| `bcf:haptics` | "true" \| "false" | "true" | **new** |
| `bcf:help-seen` | "true" \| "false" | "false" | **new** — first-run help auto-opens |
| `bcf:portrait-dismissed` | — | — | **delete** — no longer meaningful |

---

## 5 · Implementation phases

Execute in this order. Each phase has a hard acceptance gate.

### Phase A — Gesture + state plumbing

1. Port `prototype/gestures.js` → `web/mobile-gestures.js`.
2. Add new `LS_*` constants and bump `STORAGE_VERSION`.
3. Add `app.layoutMode` detection and re-render on `resize` /
   `orientationchange`. Keep desktop path identical for now.
4. Add `tapToPause` and `haptics` to the prefs read/write helpers.

**Gate:** running on desktop is unchanged. On a phone-sized viewport,
`app.layoutMode` flips to `"portrait"` or `"landscape"` correctly and
survives rotation.

### Phase B — Portrait C

1. Add `renderMobilePortrait()` mirroring the prototype's `PortraitC`.
2. Wire the sky tap/swipe handlers using `attachSkyGestures`.
3. Wire the mini-rail drag using `attachRailScrub` with the **zoom-
   aware fraction** (port `fractionFromPointer` + `panOffsetForPlayhead`
   verbatim from `prototype/scrubber.jsx`).
4. Add cluster-binning (`binRolls`, `finalizeBin`, `binSize`).
5. Add Settings, About, and Help surfaces. Help auto-opens when
   `bcf:help-seen` is false.

**Gate:** portrait phone shows sky on top, mini-rail at bottom, all
gestures from the spec work, settings persist across reload.

### Phase C — Landscape F

1. Add `renderMobileLandscape()` mirroring the prototype's `LandscapeF`.
2. Reuse the field-log model already in `app.js:2098-2119` — adapt
   markup to the rail layout (top 2/3) but keep the data path identical.
3. Implement the **cinema-scrub auto-hide**: 4000ms idle timer, reset
   on any sky/rail touch. When chrome is hidden, the first sky tap
   reveals (does *not* pause); second tap within the window pauses.
4. Settings + About **flyouts** appear from the right rail's bottom
   dock; backdrop-tap dismisses.

**Gate:** rotating mid-playthrough swaps layouts without remounting
state. Word position, playing/paused, speed, and zoom all survive.

### Phase D — Cutover

1. Delete `renderPortraitBanner` and its media query.
2. Update the landing page (top-level `index.html`) with title chip,
   author credit, and `?` help button.
3. Verify all desktop functionality untouched (resize a desktop window
   below 900px and back — should still re-render the desktop view at
   ≥900px without flicker).

**Gate:** no "rotate to landscape" banner anywhere. Desktop UI byte-
for-byte unchanged for viewports above the breakpoint.

### Phase E — Polish + a11y

1. Add `aria-live="polite"` region announcing roll changes:
   `"Roll {n} of {total}. {perkName}, {cp} CP."`
2. Add keyboard equivalents: Space (pause), ←/→ (step roll),
   Home (live edge), `?` (help).
3. Verify `prefers-reduced-motion`: throw decay disabled, cross-fade
   rotation skipped, auto-hide timer doubles to 8000ms.
4. Add `meta name="viewport"` with `viewport-fit=cover` (Phase A
   probably already did this).

**Gate:** Lighthouse Accessibility ≥ 90 on a mobile preset.

---

## 6 · Acceptance criteria (the full checklist)

Tick off all of these before calling v1 done.

### Layout

- [ ] **§0.5 desktop smoke test passes** at every phase gate, not just
      at the end. If a phase fails the smoke test, it's not done.
- [ ] Phone in portrait: sky takes ~60% of viewport, mini-rail dock
      always visible at bottom, top chips do not overlap the sky's
      focal label.
- [ ] Phone in landscape: sky takes ~75% width, right rail shows field
      log (top 2/3) + settings/about dock (bottom 1/3).
- [ ] Rotating mid-playback preserves word position, play state,
      speed, zoom, and pref toggles. No remount visible.
- [ ] Desktop (viewport ≥ 1100px) is byte-identical to pre-change.

### Gestures (per gesture-contract.html §03 constants)

- [ ] Tap sky → toggles pause/play within 250ms.
- [ ] Tap sky when `tapToPause` is off → no effect.
- [ ] Double-tap sky → snaps playhead to last roll's word position and
      resumes playing.
- [ ] Horizontal swipe (≥ 24px engage, dx > 1.5×dy) → ±1 roll per 56px
      of travel; haptic per roll crossed.
- [ ] Drag mini-rail → scrubs word position; respects current zoom +
      auto-pan offset.
- [ ] Drag cinema-scrub (landscape) → same as above.
- [ ] Landscape chrome auto-hides after 4000ms idle; first tap on sky
      reveals (does NOT pause); second tap pauses.

### Scrubber zoom + binning

- [ ] Settings → Timeline zoom segmented (1×/2×/4×/8×). Selected
      value persists.
- [ ] At 1× with the full dataset, the rail shows cluster diamonds
      (numeric count inside multi-rolls clusters), not a smear of
      overlapping dots.
- [ ] At 8×, individual rolls are visible at thumb resolution; the
      content auto-pans so the playhead stays centred.
- [ ] Active roll always renders as a separate cyan diamond on top of
      any cluster.

### Persistence

- [ ] All `bcf:*` keys listed in §4 are read on init and written on
      change.
- [ ] `STORAGE_VERSION` bumped; old keys (`bcf:portrait-dismissed`)
      cleared on first load after upgrade.

### Accessibility

- [ ] `prefers-reduced-motion: reduce`: no transitions, no throw
      decay, auto-hide extended to 8000ms.
- [ ] Keyboard: Space, ←/→, Home, `?` all work.
- [ ] Roll changes announce in the aria-live region.
- [ ] All tappable targets ≥ 44×44 CSS px.

### Help + credits surfaces

- [ ] First-run help overlay auto-opens; dismissing sets
      `bcf:help-seen` so subsequent loads don't re-open it.
- [ ] About flyout shows story title, "by LordRoustabout", SV/FF/AO3
      links, dataset stats. The flyout's "Gestures & help" link opens
      the same overlay.
- [ ] Landing page (`index.html`) shows the same `?` button top-right
      and the title-chip with author credit at the top of Survey's
      letter.

---

## 7 · Things NOT to do

- **Don't edit any of the read-only functions listed in §0.2.** Branch
  earlier; duplicate if needed. The point of §0 is that the desktop
  app is a closed surface from this workstream's perspective.
- **Don't "share components" between mobile and desktop.** Yes, the
  field log on mobile shows the same data as `renderNarrativeReadout`
  on desktop. Yes, the obvious thing is to factor a shared component.
  No. The two surfaces have different sizing, different scroll
  semantics, and different gesture targets. Read the same model,
  build separate views.
- **Don't replace the sky's procedural diamond with real constellation
  outlines** — that's a separate workstream tracked under
  `phase4_sky_view_design.md`. The mobile layouts must render whatever
  the sky becomes; they don't need to know its internals.
- **Don't fork the storage namespace.** Reuse `bcf:` keys exactly as
  named. Don't introduce a `bcf:mobile:*` parallel.
- **Don't add a third "tablet" breakpoint.** Phones get mobile;
  everything else gets desktop. iPads-in-landscape are desktop;
  iPads-in-portrait are mobile. The breakpoint at `1100px` (the
  upper bound from the existing portrait-banner media query) already
  encodes this.
- **Don't edit existing CSS variables or rules.** Add new ones. If
  a desktop CSS value needs to change for some reason you discovered,
  surface it as an open question first — do not silently edit it.
- **Don't change the viewport meta in ways that affect desktop.** The
  spec says set `viewport-fit=cover, maximum-scale=1, user-scalable=no`
  — that affects mobile rendering and pinch-zoom-of-the-page (which
  we don't want), but does not change desktop layout. Confirm both
  views still render identically before and after the meta change.
- **Don't move existing functions around in `app.js`.** Leave them
  where they are. Add new `renderMobile*` functions at the end of the
  file in a clearly-labelled section.

---

## 8 · v2 backlog (for the next round)

Once v1 ships and gets real-user feedback, these are the named
follow-ups. They've been designed and reserved; the implementing agent
should leave hooks.

1. **Pinch zoom** on the scrubber. The current zoom levels are
   `1/2/4/8`; pinch would interpolate between. Hook: the
   `setPrefs({ zoom })` call already supports any positive number;
   only the UI is quantized.
2. **Long-press roll preview tooltip.** The roll diamonds in the rail
   are already individually addressable in `data.rolls`; add a 450ms
   timer + tooltip element.
3. **Edge swipe-down to peel field log** over the sky in portrait.
   Spec'd in `gesture-contract.html`. Requires a new translucent panel.
4. **Throw-to-scrub inertia.** The `swipeEnd(velocity)` callback in
   `attachSkyGestures` already passes velocity; the consumer currently
   ignores it. Wire it to an ease-out loop capped at ±5 rolls.
5. **Real constellation rendering** in the sky viewport (separate
   workstream).
6. **Cinematic content** during on-roll-cinematic mode for mobile —
   currently text-only.

---

## 9 · Open questions for the implementing agent

If any of these come up during implementation, ping the design author
before resolving:

- Does `cinematic` on-roll behave the same on mobile as on desktop,
  or does the cinematic pull more of the sky's screen area on phones
  (e.g., temporary chrome hide + full-bleed)?
- The desktop scrubber's "carousel" focus pattern — should it surface
  on mobile in any form (e.g., when paused on a roll, swipe left/right
  to see neighbouring constellation cards)? Not in v1.
- Background autoplay behaviour — should we pause when the page is
  hidden (`document.visibilitychange`)? Strongly recommend **yes**,
  but spec doesn't say.
