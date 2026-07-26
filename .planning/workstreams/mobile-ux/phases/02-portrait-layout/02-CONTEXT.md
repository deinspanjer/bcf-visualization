# Phase 2: Portrait Layout - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

A phone held upright is a complete, usable visualization: `render()` gains a real `renderMobilePortrait()` arm (sky over an always-visible mini-rail dock), sky gestures wired per the locked contract, zoom-aware mini-rail scrub with cluster-binning, and the Settings / About / Help surfaces with first-run help auto-open. Covers MOBP-01..MOBP-05, mapping to `INTEGRATION_PLAN.md` §5 Phase B. Landscape phones keep their current fallback until Phase 3; desktop stays frozen per plan §0. Phase ends with the §5 Phase B gate review with Dre plus a passing `tests/test_desktop_smoke.py` run.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phase 1 (D-01..D-11 in `../01-mobile-state-gesture-plumbing/01-CONTEXT.md`); all Phase 1 decisions remain binding here. All decisions below were auto-resolved to the recommended default (`--auto` mode, single pass).

### Layout branching

- **D-12 Interim landscape fallback:** `[auto]` During Phase 2, `render()` branches to `renderMobilePortrait()` only when `app.layoutMode === "portrait"`. `layoutMode === "landscape"` keeps the current fallback (desktop shell + portrait banner) untouched until Phase 3 delivers `renderMobileLandscape()`. The banner stays the safety net; it is deleted only in Phase 4 (cutover).

### Portrait sky

- **D-13 Sky source:** `[auto]` The portrait sky region shows the **real** sky visualization driven by the existing playthrough/sky-camera/cinematic model — never a port of the prototype's procedural-diamond placeholder `Sky` (that was a fidelity stand-in; `prototype/sky.jsx` is reference-only for gesture-surface shape). Reuse the frozen render functions (`renderViewportFrame`, `renderSkyCamera`, `renderSpotlight`, `renderBeam`, …) by **calling** them where their sizing assumptions hold at phone dimensions; where they don't, duplicate mobile markup over the same model per plan §7 ("duplicate views over shared model") — never edit the originals. Cinematic behavior is D-01: same as desktop, text-first, within the sky area. Researcher must determine which of the sky render functions are directly callable at mobile sizes vs. need a duplicated mobile variant.

### Portrait chrome & surfaces

- **D-14 About access in portrait:** `[auto]` The prototype's `PortraitC` has no About entry point (a prototype gap — MOBP-05 requires About to work in portrait). Add an ⓘ (info) icon button to the dock transport row alongside the existing gear button, opening the same About flyout as landscape will use. Help stays the top-right `?` button; the About flyout's "Gestures & help" link opens the Help overlay (per `prototype/panels.jsx` `InfoFlyout`). All new buttons ≥ 44×44 CSS px tap targets.
- **D-15 Details mode in portrait v1:** `[auto]` Faithful prototype port: the Settings "View mode" segment reads/writes the shared `bcf:mode` key, but portrait v1 always renders the playthrough presentation — no new mobile details/roll-log view is invented (the approved design contains none; plan §2 scopes the *control*, not a mobile details layout). Toggling to "details" on a phone persists and takes effect on desktop. **Flag this at the Phase B gate review** so Dre can confirm or redirect; a real mobile details view is captured as a deferred idea. — **Reversibility:** reversible — adding a mobile details view later is additive UI in the mobile-only path.
- **D-16 Flyout back-gesture & focus trap (built here per roadmap note, not deferred to Phase 4):** `[auto]` One surface stack for Settings / About / Help. Opening a surface pushes a `history.pushState` sentinel; `popstate` closes the topmost surface (mobile back gesture dismisses instead of leaving the app); programmatic close consumes its sentinel via `history.back()` so the history stack never grows stale. Backdrop tap closes flyouts. While a surface is open, focus is trapped inside it (redirect on `focusin` / wrap at edges) and returns to the opening button on close. Mobile-only wiring — desktop dialogs untouched.

### Scrub & playback machinery

- **D-17 Zoom-aware rail wiring (single path):** `[auto]` `web/mobile-gestures.js` stays byte-identical (D-07/verbatim-port precedent). The mini-rail attaches **only** `attachRailScrub`; its `onScrub(fraction)` callback converts the viewport fraction to the inner-content fraction using the verbatim-ported `panOffsetForPlayhead` + the `fractionFromPointer` math (inner = (f + panPct/100) / zoom), then commits via the existing `setWordPos` path and returns the roll index so the module's built-in haptic-per-roll-cross fires. The prototype `MiniRail`'s parallel raw pointer-listener override (which passed `onScrub: null` and bypassed the haptic) was a React workaround — do **not** port it; porting it would create a second scrub input path (violates no-parallel-implementations).
- **D-18 Portrait playback update tier:** `[auto]` No second rAF loop. The existing `tickPlayback` → `updatePlaybackFrame` incremental tier drives portrait: `cachePlaybackDomRefs` additionally caches portrait refs (playhead, rail inner transform, chips, dock meta, active-roll marker) when `layoutMode === "portrait"`, and `updatePlaybackFrame` updates them via an early mobile branch that leaves the desktop code path byte-identical. Cluster bins (`binRolls`/`finalizeBin`/`binSize`, ported verbatim per plan §3.1) recompute only on structural render, zoom change, or rail resize (ResizeObserver, rAF-coalesced) — never per playback frame. Gesture callbacks never trigger structural `render()` mid-drag (D-07).

### Claude's Discretion

- Exact portrait DOM structure/class names inside `renderMobilePortrait()` (follow `prototype/layouts.jsx` `PortraitC` + `prototype/styles.css` as the visual reference)
- Chip copy/format details (CH chip, roll chip, hint row) and dock "now" metadata formatting
- How the ~60% sky / dock split is expressed in CSS (svh/dvh + flex per D-08; MOBP-01 overlap rule is the acceptance bar)
- Help auto-open trigger point (after data load, mobile layouts only, once per session, when `helpSeen` is false; dismiss calls `markHelpSeen()`)
- Playwright test structure for portrait behaviors (mirroring Phase 1's harness conventions)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mobile UX plan & contract
- `design/mobile-ux/INTEGRATION_PLAN.md` — Source of truth: §0 freeze rules + §0.5 smoke checklist, §1 locked decisions (tap-to-pause ON default, swipe right=forward, auto-hide landscape-only), §2 scope, §3.1–3.2 file-level changes, §4 storage keys, §5 Phase B steps + gate, §6 acceptance checklist (Layout/Gestures/Scrubber/Persistence/Help), §7 things NOT to do. NOTE: its `redesign/mobile-ux/…` prefix is stale — everything lives under `design/mobile-ux/…`. Plan deviations on record: D-03 (no `user-scalable=no`), D-02 (visibilitychange pause, already shipped in Phase 1).
- `design/mobile-ux/gesture-contract.html` — Locked v1 gesture constants (mirrored in `web/mobile-gestures.js` `G`): 250ms tap, 300ms/24px double-tap window, 24px engage, 1.5× axis lock, 56px/roll scrub step, 4000ms auto-hide.

### Prototype (visual/behavioral reference to port)
- `design/mobile-ux/prototype/layouts.jsx` — `PortraitC`: top chip cluster, sky, dock (transport row + `MiniRail` + hint row). The portrait DOM/UX reference.
- `design/mobile-ux/prototype/scrubber.jsx` — `binRolls`/`finalizeBin`/`binSize` (5px bin threshold, cluster size/count/dominant-outcome rules), `panOffsetForPlayhead`, `fractionFromPointer` — port these functions verbatim per plan §3.1; see D-17 for what NOT to port (the React-side pointer-listener override).
- `design/mobile-ux/prototype/panels.jsx` — `SettingsFlyout` (mode/on-roll/speed/zoom/comfort groups), `InfoFlyout` (title, author credit, SV/FF/AO3 links, dataset stats, help link), `HelpOverlay` (gesture list + credits + "Got it"), `Seg`, icons.
- `design/mobile-ux/prototype/app.jsx` — Transport semantics reference: onSky tap/dblTap (snap to last roll + resume)/swipeStep (±1 roll)/swipeEnd (persist bookmark), speed cycle order 0.5/1/2/4, flyout open/close exclusivity.
- `design/mobile-ux/prototype/styles.css` — Mobile CSS to adapt into `web/mobile.css` (reuse existing `--cyan`/`--green`/etc. variables; new rules only).

### Live code (Phase 1 output — the plumbing this phase builds on)
- `web/mobile-gestures.js` — Verbatim-ported `attachSkyGestures`/`attachRailScrub`/`haptic`/`GestureConstants`. Byte-identical; do not modify (D-17).
- `web/app.js` `// ── Mobile UX ──` section (~:2762–2927) — layout-mode rAF recompute, `window.__bcfPrefs` getter bridge, pref setters (`setTapToPause`/`setHaptics`/`setMobileTimelineZoom`/`markHelpSeen` via `window.__bcfMobile`), `attachMobileGestureProbes` (the D-07 attach convention Phase 2 replaces with production callbacks), D-02 visibilitychange pause.
- `web/app.js` `render()` (~:903–929) — the branch point; the probe-element block inside the `layoutMode !== "desktop"` branch is Phase 1 scaffolding that portrait rendering supersedes (landscape keeps fallback per D-12).
- `web/mobile.css` — Phase 1 foundation (touch-action surface classes, `--mobile-vh` 100svh, safe-area inset variables) — currently inert; portrait is the first consumer.
- `tests/test_desktop_smoke.py` — D-10 gate artifact; must pass at the Phase B gate. Run via the main checkout's venv: `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py`.

### Planning
- `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md` — D-01..D-11; all still binding (esp. D-01 cinematic, D-03 viewport, D-06/07/08/09/11).
- `.planning/workstreams/mobile-ux/ROADMAP.md` — Phase 2 success criteria + workstream gates.
- `.planning/workstreams/mobile-ux/REQUIREMENTS.md` — MOBP-01..MOBP-05 exact wording.
- `.planning/research/PITFALLS.md` — regression modes, phase-mapped.
- `.planning/research/ARCHITECTURE.md` — render/listener lifecycle analysis of `web/app.js`.
- `.planning/research/STACK.md` — Pointer Events / touch-action / vibrate support reality.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `render()` dispatch (`web/app.js:903`): already branches on `layoutMode !== "desktop"` for the Phase 1 probe; Phase 2 turns this into the real portrait arm (D-12).
- `window.__bcfMobile` pref setters + `window.__bcfPrefs` getter bridge: the Settings flyout calls these — do not add a second persistence path.
- Existing model functions (`setWordPos`, `setMode`, `chapterAtWord`, `recentRolls`, `cumulativeAt`, `formatWords`, `activeRoll`-style lookups) and playback engine (`tickPlayback`, `togglePlayback`, speed handling, bookmark persistence): reuse, never rewrite (plan §3.1). The prototype's `PLAY_RATE` loop is NOT ported — the app's engine already exists.
- `cachePlaybackDomRefs`/`updatePlaybackFrame`: the incremental tier portrait refs plug into (D-18).
- Module-level `data-action` click delegation + keyboard handler (`web/app.js:2858–2904`): dock buttons can ride the same delegation pattern.
- Phase 1 Playwright harness conventions in `tests/` (incl. `window.__bcfGestureStats` diagnostic pattern).

### Established Patterns
- Full-teardown `render()` + per-render listener attach (D-07); teardown handles stored on `app`, not `app.dom`.
- Desktop freeze: §0.2 read-only functions; no edits to existing CSS rules/variables; new CSS scoped in `web/mobile.css` behind the mobile media query.
- Storage: all prefs through existing `LS_*` constants + `store()`; no new keys needed this phase (D-09 already added them all).

### Integration Points
- `render()` portrait branch → `renderMobilePortrait()` (new, in the `// ── Mobile UX ──` section at end of `web/app.js`).
- Gesture attach: replace `attachMobileGestureProbes`'s diagnostic callbacks with production sky callbacks (tap → tap-to-pause honoring `app.tapToPause`; double-tap → snap to last roll ≤ current word + resume; swipeStep → ±1 roll; swipeEnd → persist bookmark) and rail attach per D-17 — same per-render lifecycle slot.
- `app.*` additive state only: `helpOpen`, `settingsOpen`, `infoOpen` exist per Phase 1 plan; portrait uses them.
- `updatePlaybackFrame` mobile early-branch for portrait incremental updates (D-18) — desktop path byte-identical.

</code_context>

<specifics>
## Specific Ideas

- Gate discipline: Phase ends with `INTEGRATION_PLAN.md` §5 Phase B gate review **with Dre** plus a passing `tests/test_desktop_smoke.py` run — both mandatory, per workstream gate 2. D-15 (no mobile details view in v1) is explicitly on the gate-review agenda.
- Real-device iOS Safari verification is expected for portrait (emulation does not reproduce toolbar/`100vh` behavior) — roadmap Phase 2 note; treat as a gate-review item Dre performs on hardware.
- MOBP-01's "top chips never overlap the sky's focal label" is the portrait layout acceptance bar; verify at small viewports (e.g. 320px width) too.

</specifics>

<deferred>
## Deferred Ideas

- Mobile details view (a real portrait roll-log/details presentation behind the mode toggle) — new capability; revisit after D-15 is reviewed at the Phase B gate.
- Full-bleed mobile cinematic — v2, per D-01.
- Mobile v2 backlog per plan §8 (pinch zoom, long-press preview, edge swipe-down peel, throw inertia, real constellation outlines, richer cinematic content, Screen Wake Lock).

</deferred>

---

*Phase: 2-Portrait Layout*
*Context gathered: 2026-07-26*
