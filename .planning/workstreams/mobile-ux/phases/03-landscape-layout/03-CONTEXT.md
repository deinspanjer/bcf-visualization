# Phase 3: Landscape Layout - Context

**Gathered:** 2026-08-01
**Status:** Ready for planning

<domain>
## Phase Boundary

A phone turned sideways gives a cinema view with the field log, and rotating between layouts never loses your place. Replaces the D-12 interim landscape fallback — `render()` at `web/app.js:991` still routes every non-portrait mobile viewport to `renderAppShell()` — with a real landscape layout: sky at ~75% width, right rail carrying the field log (top 2/3) over a settings/about dock (bottom 1/3), auto-hiding cinema-scrub chrome, and rotation hand-off that preserves playback state. Covers MOBL-01..MOBL-04, mapping to `INTEGRATION_PLAN.md` §5 Phase C. Desktop stays frozen per plan §0. Phase ends with the §5 Phase C gate review with Dre plus a passing `tests/test_desktop_smoke.py` run and a real-device pass.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phases 1–2 (D-01..D-11 in `../01-mobile-state-gesture-plumbing/01-CONTEXT.md`, D-12..D-19 in `../02-portrait-layout/02-CONTEXT.md` and `02-05-SUMMARY.md`). **All prior decisions remain binding**, in particular D-05 (no carousel on mobile), D-13 (real sky camera, never the prototype placeholder), D-17 (single scrub input path; `web/mobile-gestures.js` stays byte-identical), D-18 (single rAF update tier), and D-19 (surfaces scoped to `.mobile-sky`).

### Rotation hand-off (MOBL-03 — the phase's hard gate)

- **D-20 "No visible remount" means state preservation, not DOM preservation:** `onLayoutMaybeChanged()` keeps calling a full `render()`. Every field MOBL-03 names — word position, play state, speed, zoom, preference toggles — already lives on `app.*` and survives a rebuild, so nothing is lost; a single frame of rebuild is acceptable and keeps the phase inside D-18's single-render-tier discipline. Do NOT build a cross-fade or re-parent live DOM nodes. — **Reversibility:** reversible — a cross-fade could be layered on later without changing the state contract.
- **D-21 An open surface survives rotation:** Settings, About and Help stay open and re-render in the new layout's position. Rotation is not a dismissal gesture. This also keeps the D-16 history sentinel balanced with no extra bookkeeping.
- **D-22 Mid-gesture rotation aborts the drag and keeps the cinematic:** An in-flight rail scrub is cancelled cleanly (the existing teardown already clears the frozen pan offset at `app.js:3864`); a playing roll cinematic continues from state, since it is driven by `wordPos` rather than by the DOM. Do not defer or block the layout swap while a pointer is down — an ignored physical rotation reads as a freeze.
- **D-23 Prove the gate two ways:** A Playwright test swaps the viewport and asserts every MOBL-03 field survives (the CI regression net), AND a real-device pass at the gate covers the `resize`/`orientationchange` timing race that the roadmap notes does not reproduce in emulation. Neither alone is sufficient — Phase 2 demonstrated that a fully green suite still missed four device-only defects.

### Field log (MOBL-01)

- **D-24 Share the model, duplicate the view — the seam is `recentRolls`:** Call `recentRolls(wordPos, count)` (`app.js:791`) as the data path and hand-author the rail markup. Never call `renderNarrativeReadout` (`:2343`) or `renderRecentRolls` (`:2366`) — they are §0.2 read-only and carry desktop sizing and scroll assumptions. This resolves the apparent conflict between plan §7 ("read the same model, build separate views") and §5 Phase C ("reuse the field-log model, adapt markup to the rail"): both point the same way. Same resolution D-13 reached for the sky.
- **D-25 Content follows the prototype's `FieldLog`:** Defined in `design/mobile-ux/prototype/panels.jsx` — a highlighted live roll (roll number, outcome, CP, perk name, jump) above a list of recent entries (chapter, outcome/CP, name). Not a mirror of desktop's readout content — desktop has far more width to spend.
- **D-26 The log auto-follows the playhead; it does not scroll:** The list re-derives from the current word position so the live roll is always at top. This rides the existing incremental update tier (D-18) rather than adding one, and avoids the auto-scroll-versus-manual-scroll conflict entirely.
- **D-27 Keep the truncated evidence quote:** ~100 chars, shown on the live roll. It is the strongest tie back to the story text and the data already carries it. It MUST have a hard height clamp so a long quote cannot push the recent list out of the rail.

### Chrome auto-hide (MOBL-02)

- **D-28 The idle timer runs only during playback:** Pausing reveals chrome and keeps it revealed. Matches the prototype (which bails unless playing) and respects that a paused reader is inspecting, which is exactly when the controls are wanted.
- **D-29 Only the cinema-scrub hides:** Top chips and the right rail stay visible. Matches the prototype, where `isHidden` is passed only to `CinemaScrub`, and keeps the field log readable — the defining feature of landscape per MOBL-01. Hiding the rail would also edge into the full-bleed cinematic that D-01 deferred to v2.
- **D-30 Reveal is navigation, pause is playback control:** The first sky tap always reveals hidden chrome, regardless of the tap-to-pause preference. The second tap within the window pauses **only** when tap-to-pause is on, consistent with MOBP-02's existing "no-op when tap-to-pause off" rule. This guarantees hidden chrome is always recoverable — a user with tap-to-pause off must never be trapped.
- **D-31 Rotating into landscape arrives with chrome visible and the idle timer started:** Rotation counts as activity, so the user sees the controls they just rotated into, and the cinema view still appears for someone who then simply watches.

### Landscape shell mechanics

- **D-32 Drop the portrait-only nesting around the iOS body scroll-lock:** The `@media (orientation: portrait)` wrapper at `web/mobile.css:29` goes away. Phase 2 scoped it to portrait solely to protect the then-scrollable desktop fallback in landscape; Phase 3 removes that fallback, so the lock must apply to the whole mobile block. Leaving it portrait-only would reintroduce the exact 82px iOS scroll bug (frozen `style.css:45` sets `body { min-height: 100vh }`, the LARGE viewport on iOS) in landscape only. Update the rule's comment, which currently says "until Phase 3 replaces it."
- **D-33 Landscape Settings/About mount inside `.mobile-sky` with an app-spanning backdrop:** The exact D-19 arrangement Phase 2 arrived at after two device-found defects. Not constrained to the right rail (only ~25% of a landscape phone's width; the Settings segments and About link row would be badly cramped) and not a bespoke dock-anchored flyout (a third anchoring scheme, and bespoke anchors caused the Phase 2 overlap defect).
- **D-34 Generalize the gesture attach into a single function:** `attachMobilePortraitGestures` (`app.js:3852`) becomes `attachMobileGestures`, branching internally on `layoutMode`. One set of teardown slots, one place where the D-07 attach lifecycle and the frozen-pan reset live. Do NOT add a parallel landscape sibling — that duplicates the defensive teardown logic that D-07 and the drag-monotonicity fix both depend on.
- **D-35 One mobile-internal shared sky helper:** Wrapped differently by each layout (60% height in portrait, 75% width in landscape). Plan §7 forbids sharing with the frozen **desktop** surface only; the project's no-parallel-implementations rule actively wants a single path here. Duplicating would mean fixing the tap hint, focal label and camera layer twice.

### Device scope

- **D-36 No tablet tier; the §7 no-third-breakpoint stance holds:** Verified against the live routing (`MOBILE_LAYOUT_QUERY`, `app.js:73`): iPad-portrait (820/1024 wide) resolves to **mobile portrait**; iPad-landscape and typical Chromebooks (>900px, not portrait) resolve to **desktop**; a Chromebook window narrowed to ≤900px resolves to **mobile landscape**. Nothing prohibits touch on any of these — the mobile module accepts mouse as well as touch (`mobile-gestures.js:45,159` reject only non-primary buttons) and the frozen desktop scrubber is itself pointer-based (`app.js:1186 onPointerDown`, plus a native `type="range"` control), so touch devices routed to desktop remain fully usable; they simply do not get the mobile gesture vocabulary. Phase 3 adds no tablet-specific breakpoint, sizing or gesture tuning. See the deferred idea below for the known ergonomic gap.

### Claude's Discretion

- Exact landscape DOM structure and class names (follow `prototype/layouts.jsx` `LandscapeF` and `prototype/styles.css` as the visual reference)
- How the ~75% sky / ~25% rail split and the rail's 2/3–1/3 division are expressed in CSS
- Whether the cinema-scrub reuses the portrait mini-rail's binning/pan helpers directly or wraps them (D-17's single-input-path rule is the constraint; the helpers themselves are already shared)
- Auto-hide timer implementation details (reset sources, coalescing) provided the D-28..D-31 semantics hold
- Playwright test structure for rotation and auto-hide, following the Phase 2 harness conventions

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mobile UX plan & contract
- `design/mobile-ux/INTEGRATION_PLAN.md` — §0 freeze rules + §0.5 smoke checklist, §1 locked decisions (chrome auto-hide is landscape-only; swipe right = forward), §2 scope, §3.1–3.2 file-level changes, §5 Phase C steps + gate, §6 acceptance checklist, §7 things NOT to do (esp. no shared desktop components, no third tablet breakpoint). Its `redesign/mobile-ux/…` path prefix is stale — everything lives under `design/mobile-ux/…`.
- `design/mobile-ux/gesture-contract.html` — locked v1 constants, mirrored in `web/mobile-gestures.js` `G`: `CHROME_AUTOHIDE` 4000ms, `ROTATION_ANIM` 220ms, 250ms tap, 300ms/24px double-tap, 24px engage, 1.5× axis lock, 56px/roll.

### Prototype (visual/behavioral reference)
- `design/mobile-ux/prototype/layouts.jsx` — `LandscapeF`: sky region with top chips and the auto-hide `CinemaScrub`, plus the right rail (`FieldLog` over `control-dock` with Settings/About and a status line). The landscape DOM/UX reference.
- `design/mobile-ux/prototype/panels.jsx` — `FieldLog` (D-25 content reference, incl. the truncated evidence quote), `SettingsFlyout`, `InfoFlyout`, `HelpOverlay`, icons.
- `design/mobile-ux/prototype/scrubber.jsx` — `CinemaScrub` (landscape scrub pill, `isHidden` prop) plus the `binRolls`/`panOffsetForPlayhead`/`fractionFromPointer` helpers already ported in Phase 2.
- `design/mobile-ux/prototype/app.jsx` — landscape chrome auto-hide effect (only while playing — the D-28 precedent) and the reveal-vs-pause tap branch (D-30).
- `design/mobile-ux/prototype/styles.css` — landscape CSS to adapt into `web/mobile.css`.

### Live code (Phase 1–2 output this phase builds on)
- `web/app.js:991` — the `render()` branch that still routes landscape to `renderAppShell()`; this phase adds the landscape arm.
- `web/app.js:73-80` — `MOBILE_LAYOUT_QUERY` / `detectLayoutMode()`; the D-36 routing evidence. Never introduce a second query variant (D-06).
- `web/app.js:3852` — `attachMobilePortraitGestures`, the D-07 attach/teardown convention to generalize per D-34.
- `web/app.js:791` — `recentRolls(wordPos, count)`, the D-24 model seam. `:2343`/`:2366` are the frozen views — call neither.
- `web/app.js` `// ── Mobile UX ──` section — layout-mode rAF recompute, `window.__bcfPrefs` bridge, pref setters, surface stack (`openMobileSurface`/`closeMobileSurface`, incl. the Phase 2 toggle + single-sentinel fix), focus trap, frozen-pan scrub.
- `web/mobile.css:29` — the portrait-scoped body scroll-lock D-32 un-nests; its comment explicitly anticipates this phase.
- `web/mobile-gestures.js` — byte-identical since Phase 1 and must stay so (D-17).
- `tests/test_mobile_portrait.py`, `tests/test_mobile_plumbing.py`, `tests/test_desktop_smoke.py` — 33 passing tests; all must stay green. Run via the main checkout's venv: `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest ...`

### Planning
- `../02-portrait-layout/02-CONTEXT.md` — D-12..D-18.
- `../02-portrait-layout/02-05-SUMMARY.md` — D-19, the full gate record, the four device-found defects, and the "iOS finds what emulation cannot" lesson.
- `../02-portrait-layout/02-UI-SPEC.md` — locked design tokens and the recorded flyout-anchor deviation.
- `.planning/workstreams/mobile-ux/ROADMAP.md` / `REQUIREMENTS.md` — Phase 3 success criteria and MOBL-01..04 wording.
- `.planning/research/PITFALLS.md`, `ARCHITECTURE.md`, `STACK.md`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `renderMobilePortrait()` and its sub-renderers: the structural template for the landscape arm; the sky region becomes the D-35 shared helper.
- Surface stack (`openMobileSurface`/`closeMobileSurface`, backdrop + focus trap + history sentinel): complete and device-hardened in Phase 2 — landscape reuses it wholesale per D-33.
- Scrub helpers (`binRolls`/`finalizeBin`/`binSize`, `panOffsetForPlayhead`, `mobileInnerFraction`) plus the frozen-pan drag fix: the cinema-scrub consumes these, never a second implementation.
- `recentRolls(wordPos, count)` (`:791`), `chapterAtWord`, `lastRollAtWord`, `formatWords`: the shared model layer.
- `cachePlaybackDomRefs` / `updatePlaybackFrame` mobile branch: the incremental tier the landscape field log and scrub plug into (D-18, D-26).
- Phase 2 Playwright harness (`staged_web_runtime_site`, `PHONE_PORTRAIT`, `_page_with_console_capture`) — landscape needs a `PHONE_LANDSCAPE` viewport following the same conventions.

### Established Patterns
- Full-teardown `render()` with per-render listener attach; teardown handles on `app`, never `app.dom`.
- Desktop freeze: §0.2 read-only functions; no edits to existing CSS rules or variables; all new CSS in `web/mobile.css` behind the mobile media query.
- Device passes find what green suites miss — budget one into the Phase C gate (D-23).

### Integration Points
- `render()` landscape branch → `renderMobileLandscape()` (new, in the `// ── Mobile UX ──` section).
- `attachMobileGestures()` (generalized per D-34) → sky gestures + cinema-scrub scrub.
- `web/mobile.css` — un-nest the body scroll-lock (D-32); add landscape layout rules.
- `app.*` additive state only (e.g. a chrome-hidden flag and its idle timer handle).

</code_context>

<specifics>
## Specific Ideas

- Phase ends with the `INTEGRATION_PLAN.md` §5 Phase C gate review **with Dre**, a passing `tests/test_desktop_smoke.py`, and a real-device pass (D-23). Per the Phase 2 experience, run the device pass on **iOS Safari** specifically — it found layout defects Android and emulation both missed. See `reference_device_debugging` notes for the tooling.
- The `.mobile-gesture-probe` and the Phase 1 landscape assertions in `tests/test_mobile_plumbing.py` currently rely on landscape rendering the desktop shell. Replacing the fallback WILL interact with `test_landscape_fallback_is_unchanged` (added in Phase 2) — that test asserts the portrait surface never mounts at a landscape viewport and is expected to need rewriting for the new landscape surface. Treat it as an intended, recorded change, not a regression.
- Deleting the "Best in landscape" banner is **Phase 4**, not here (`app.js:1173` / `renderPortraitBanner`). It remains the safety net until the cutover.

</specifics>

<deferred>
## Deferred Ideas

- **Large-tablet-portrait ergonomics.** An iPad in portrait resolves to the mobile layout (D-36), but every gesture constant is absolute pixels tuned for a phone thumb — 56px per roll, 24px engage, 44px targets — as are the dock's 70px rail and control heights. Functional but untuned: swiping through 2.72M words at 56px/roll is a lot of dragging on a 12.9" screen. Scaling the constants (or adding a tablet tier) would be a §7 plan deviation and needs its own decision. Nothing in Phase 3 forecloses it — `attachMobileGestures` branches on `layoutMode` and the shared sky helper are both extensible.
- **Desktop-view escape hatch from mobile** — requested by Dre at the Phase 2 gate, conditional on not compromising the mobile design. Carried to **Phase 4** (Mobile Cutover), which already reworks the landing page and deletes the rotate banner.
- **Persistent idle sky** (something rendered between roll cinematics) — considered and not pursued at the Phase 2 gate after measurement showed the sky is populated 88% of playback.
- Plan §8 v2 backlog: pinch zoom, long-press preview, edge swipe-down peel, throw-to-scrub inertia, real constellation outlines, richer cinematic content, Screen Wake Lock.

</deferred>

---

*Phase: 3-Landscape Layout*
*Context gathered: 2026-08-01*
