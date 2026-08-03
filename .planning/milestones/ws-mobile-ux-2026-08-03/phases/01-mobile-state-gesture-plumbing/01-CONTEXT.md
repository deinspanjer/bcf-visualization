# Phase 1: Mobile State & Gesture Plumbing - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

The app knows which layout it is in (`app.layoutMode`: desktop/portrait/landscape) and can receive touch gestures safely, with zero new UI and zero desktop change. Delivers: `web/mobile-gestures.js` port, new `bcf:*` storage keys + `STORAGE_VERSION` bump, layout-mode detection, mobile CSS foundation decisions, and a scripted desktop smoke test. This phase also hosts the milestone's one-time interview gate — its decisions (recorded below) bind the whole milestone, including Track B's provenance shape.

</domain>

<decisions>
## Implementation Decisions

### Interview gate — user-answered (Dre, 2026-07-25)

- **D-01 Mobile cinematic (plan §9):** Same as desktop — the roll cinematic plays within the sky area using the same model/behavior as desktop, text-first for v1. No full-bleed chrome-hide interaction. Full-bleed is a v2 idea.
- **D-02 Hidden-tab behavior (plan §9):** Pause playback on `document.visibilitychange` (hidden → pause, state intact on return). Applies to mobile layouts only; the desktop path stays untouched per the freeze. Add this to the phase-gate acceptance checklist so it can't silently drop (it was missing from plan §6).
- **D-03 Page zoom vs a11y (plan §3.3 conflict):** Allow page zoom — do NOT ship `user-scalable=no` / `maximum-scale=1`. The viewport meta gets `width=device-width, initial-scale=1, viewport-fit=cover` only. Unwanted double-tap/pinch page zoom on gesture surfaces is suppressed via `touch-action` CSS on those surfaces instead. This supersedes the plan's §3.3 meta spec — record as a plan deviation. Keeps the Lighthouse Accessibility ≥ 90 gate intact.
- **D-04 Track B provenance shape (binds Phase 7):** Minimal marker — a single `curated_by: "human" | "agent"` string on each roll-override entry, following the existing `curator_added` precedent. Run bookkeeping (model, run_id, corpus_fingerprint, confidence) lives in a separate agent-run ledger file keyed by chapter — that ledger is where CINF-04's idempotency fingerprint keying points. All in-repo consumers of the overrides schema are rewritten for the new field in the same change (no shims). — **Reversibility:** costly — widening to a rich per-roll object later means another full consumer rewrite across derive_roll_facts, the TUI, and validators.
- **D-05 Carousel on mobile (plan §9):** Decided by the plan itself — not in v1. No mobile surface for the desktop carousel focus pattern this milestone.

### Auto-resolved (recommended defaults, logged for audit)

- **D-06 Layout-mode detection:** `[auto]` Derive `app.layoutMode` from `window.matchMedia` using the exact query string already in `web/style.css:360` (`(max-width: 900px), (orientation: portrait) and (max-width: 1100px)` family), defined once as a shared constant — never a hand-rolled `innerWidth` check, never a second query variant. Listen via `matchMedia` change events plus `orientationchange`, debounced.
- **D-07 Gesture lifecycle:** `[auto]` Gesture helpers attach inside the mobile render functions per render pass (mirroring the existing `cachePlaybackDomRefs` convention). Never call full `render()` from a gesture callback while a drag is active — pointer capture on a torn-down node loses the drag. Incremental updates go through the existing rAF tier.
- **D-08 Viewport units:** `[auto]` Mobile layout heights use small/dynamic viewport units (`svh`/`dvh`), never `vh`, to survive iOS Safari's dynamic toolbar. Safe-area insets via `env(safe-area-inset-*)` on docks and rails.
- **D-09 Storage:** `[auto]` Bump `STORAGE_VERSION` (currently `"2"` at `web/app.js:64`) to `"3"`; extend the existing `migratePreviewStorage()` purge pattern — clear the new keys on bump and drop `bcf:portrait-dismissed` from existence. New keys: `bcf:timeline-zoom`, `bcf:tap-to-pause`, `bcf:haptics`, `bcf:help-seen`.
- **D-10 Desktop smoke test:** `[auto]` Scripted with Playwright (already available in this environment) covering the plan §0.5 six-step checklist at ≥ 1100px, runnable on demand at every Track A phase gate. Lives under `tests/`.
- **D-11 Haptics:** `[auto]` `navigator.vibrate()` is decorative-only and feature-detected — it is a no-op on all iOS Safari; nothing may depend on it.

### Claude's Discretion

- Exact debounce timing for orientation/resize handling
- Whether mobile CSS goes in `web/style.css` (new scoped block) or a split `web/mobile.css` — plan allows either
- Playwright smoke-test structure and selectors

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Mobile UX (Track A)
- `design/mobile-ux/INTEGRATION_PLAN.md` — Source of truth for scope, freeze rules (§0), locked decisions (§1), file-level changes (§3), storage keys (§4), phases + gates (§5), acceptance (§6). NOTE: its `redesign/mobile-ux/…` path prefix is stale — everything lives under `design/mobile-ux/…`. Deviations recorded here: D-03 supersedes §3.3's `user-scalable=no`; D-02 adds visibilitychange-pause to acceptance.
- `design/mobile-ux/gesture-contract.html` — Locked v1 gesture constants (§03: engage thresholds, 56px/roll, 250ms tap, 4000ms auto-hide).
- `design/mobile-ux/prototype/gestures.js` — `attachSkyGestures` / `attachRailScrub` to port verbatim into `web/mobile-gestures.js`.
- `design/mobile-ux/prototype/scrubber.jsx` — `fractionFromPointer`, `panOffsetForPlayhead`, binning (`binRolls`/`finalizeBin`/`binSize`) to port in later phases; Phase 1 only needs awareness.
- `design/mobile-ux/prototype/styles.css` — Mobile CSS to adapt (later phases).

### Project planning
- `.planning/ROADMAP.md` — Phase gates (Milestone Gates section) and success criteria.
- `.planning/research/PITFALLS.md` — Regression modes and prevention, phase-mapped.
- `.planning/research/ARCHITECTURE.md` — Render/listener lifecycle analysis of `web/app.js`, mode-branch design.
- `.planning/research/STACK.md` — Pointer Events / touch-action / vibrate support reality.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `web/app.js` `render()` dispatch (~:803-816): the single branch point — add `app.layoutMode` branch here; desktop path below it must be untouched.
- `renderPortraitBanner()` (`web/app.js:1045`) and `.portrait-banner` CSS (`web/style.css:340-363`): deleted only in Phase 4 (cutover); Phase 1 leaves them as the safety net.
- `migratePreviewStorage()` + `STORAGE_VERSION` (`web/app.js:60-87`): the storage-versioning pattern to extend, not replace.
- `cachePlaybackDomRefs` convention: the per-render DOM-ref caching pattern gesture attachment mirrors.
- Existing rAF incremental-update tier: never triggers full `render()`; gesture-driven playhead updates ride this tier.

### Established Patterns
- Full-teardown `render()`: every structural render rebuilds DOM, so per-render listener attachment self-cleans via GC — no manual removeEventListener bookkeeping, but also no listener may be attached outside the render pass.
- Frozen desktop surface: read-only functions in plan §0.2; no edits to existing CSS rules/variables.

### Integration Points
- `render()` branch on `app.layoutMode` (only sanctioned edit to existing render code)
- `app.*` state object (additive fields only: `layoutMode`, `helpOpen`, `settingsOpen`, `infoOpen`, `chromeHidden`, `tapToPause`, `haptics`)
- `web/index.html` viewport meta (per D-03: no `user-scalable=no`)

</code_context>

<specifics>
## Specific Ideas

- The interview gate is one-time: Phase 7 must consume D-04 without re-interviewing.
- Every Track A phase ends with the plan §5 gate review with Dre plus a passing run of the D-10 smoke test.

</specifics>

<deferred>
## Deferred Ideas

- Full-bleed mobile cinematic (chrome-hide during roll cinematics) — v2, per D-01
- Mobile v2 backlog per plan §8 (pinch zoom, long-press preview, edge swipe-down peel, throw inertia, real constellation outlines, richer cinematic content, Screen Wake Lock)

</deferred>

---

*Phase: 1-Mobile State & Gesture Plumbing*
*Context gathered: 2026-07-25*
