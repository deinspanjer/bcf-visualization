# Requirements: Mobile UX (workstream: mobile-ux)

**Defined:** 2026-07-25
**Core Value:** The frozen desktop experience must not regress while the approved mobile UX ships.

## v1 Requirements

Requirements for this workstream (MOB*). Curation requirements (EPUB/CINF/ACUR) live in `.planning/workstreams/curation/REQUIREMENTS.md` since the 2026-07-26 workstream split.

### Mobile Foundation

- [x] **MOBF-01**: Plan review interview resolves §9 open questions, the `user-scalable=no` vs Lighthouse-a11y conflict, `visibilitychange` behavior, and provenance field shape before any mobile code is written
- [x] **MOBF-02**: `app.layoutMode` (desktop/portrait/landscape) derives from `matchMedia` using the identical query string as the existing CSS breakpoint, updates on resize/orientation change, and survives rotation
- [x] **MOBF-03**: Gesture helpers ported to `web/mobile-gestures.js` with a per-render attach lifecycle that cannot double-bind or lose pointer capture to a mid-drag re-render
- [x] **MOBF-04**: New `bcf:*` storage keys (timeline-zoom, tap-to-pause, haptics, help-seen) read on init, written on change; `STORAGE_VERSION` bumped with stale-key purge (`bcf:portrait-dismissed` removed)
- [x] **MOBF-05**: Mobile CSS foundation uses `touch-action`/`overscroll-behavior` on gesture surfaces, small/dynamic viewport units, and `env(safe-area-inset-*)` in docks and rails
- [x] **MOBF-06**: A scripted desktop smoke test verifies the §0.5 checklist (desktop unchanged ≥ 1100px) and is runnable at every phase gate

### Mobile Portrait

- [x] **MOBP-01**: Portrait phone shows sky (~60% viewport) over an always-visible mini-rail dock; top chips do not overlap the sky's focal label
- [x] **MOBP-02**: Sky gestures work per gesture contract: tap toggles pause within 250ms (no-op when tap-to-pause off), double-tap snaps to last roll and resumes, horizontal swipe scrubs ±1 roll per 56px with haptic per roll crossed (haptics decorative-only; no-op on iOS)
- [x] **MOBP-03**: Mini-rail drag scrubs word position, honoring current zoom and auto-pan offset (zoom-aware fraction ported verbatim from prototype scrubber)
- [x] **MOBP-04**: Scrubber cluster-binning collapses rolls within 5px at any zoom; multi-roll clusters show numeric count; active roll always renders as a separate cyan diamond on top
- [x] **MOBP-05**: Settings flyout (mode, on-roll, speed, timeline zoom 1×/2×/4×/8×, comfort), About flyout (title, author, SV/FF/AO3 links, dataset stats), and Help overlay all work in portrait; help auto-opens when `bcf:help-seen` is false; all prefs persist across reload

### Mobile Landscape

- [ ] **MOBL-01**: Landscape phone shows sky (~75% width) plus right rail with field log (top 2/3) and settings/about dock (bottom 1/3), reusing the existing field-log data path
- [ ] **MOBL-02**: Landscape chrome auto-hides after 4000ms idle; first sky tap reveals without pausing, second tap within the window pauses; any sky/rail touch resets the timer
- [ ] **MOBL-03**: Rotating mid-playback swaps layouts without visible remount, preserving word position, play state, speed, zoom, and pref toggles
- [ ] **MOBL-04**: Flyouts dismiss on backdrop tap, trap focus while open, and handle the mobile back gesture without leaving the app

### Mobile Cutover & Accessibility

- [ ] **MOBX-01**: `renderPortraitBanner` and its CSS are deleted; no "rotate to landscape" banner anywhere; desktop UI byte-identical above the breakpoint
- [ ] **MOBX-02**: Landing page shows story-title chip with author credit and a `?` help button opening the same help overlay; Survey letter stays verbatim
- [ ] **MOBX-03**: Roll changes announce via `aria-live="polite"`; keyboard equivalents work (Space, ←/→, Home, `?`); all tappable targets ≥ 44×44 CSS px; Lighthouse Accessibility ≥ 90 on mobile preset
- [ ] **MOBX-04**: `prefers-reduced-motion: reduce` disables transitions and throw decay and doubles auto-hide to 8000ms
- [ ] **MOBX-05**: Playback pauses when the page is hidden (`document.visibilitychange`), per interview confirmation

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Mobile (per integration plan §8)

- **MOB2-01**: Pinch-to-zoom on scrubber (interpolating between quantized levels)
- **MOB2-02**: Long-press roll-dot preview tooltip
- **MOB2-03**: Edge swipe-down to peel field log over the sky in portrait
- **MOB2-04**: Throw-to-scrub inertia (velocity already captured, capped ±5 rolls)
- **MOB2-05**: Mobile cinematic content beyond text
- **MOB2-06**: Screen Wake Lock during playthrough

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Any desktop change at viewport ≥ 1100px | Desktop is frozen per integration plan §0; pixel parity is the acceptance bar |
| Shared components between desktop and mobile | Plan explicitly forbids; duplicate views over shared model |
| Real constellation outlines in the sky | Separate workstream (`phase4_sky_view_design.md`) |
| Tablet breakpoint | Phones get mobile, everything else desktop; 1100px boundary encodes this |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MOBF-01 | Phase 1 | Complete |
| MOBF-02 | Phase 1 | Complete |
| MOBF-03 | Phase 1 | Complete |
| MOBF-04 | Phase 1 | Complete |
| MOBF-05 | Phase 1 | Complete |
| MOBF-06 | Phase 1 | Complete |
| MOBP-01 | Phase 2 | Complete |
| MOBP-02 | Phase 2 | Complete |
| MOBP-03 | Phase 2 | Complete |
| MOBP-04 | Phase 2 | Complete |
| MOBP-05 | Phase 2 | Complete |
| MOBL-01 | Phase 3 | Pending |
| MOBL-02 | Phase 3 | Pending |
| MOBL-03 | Phase 3 | Pending |
| MOBL-04 | Phase 3 | Pending |
| MOBX-01 | Phase 4 | Pending |
| MOBX-02 | Phase 4 | Pending |
| MOBX-03 | Phase 4 | Pending |
| MOBX-04 | Phase 4 | Pending |
| MOBX-05 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0 ✓

**Note:** The initial combined definition recorded 31 requirements across both tracks; this file carries the 20 mobile-ux requirements since the workstream split (2026-07-26).

---
*Requirements defined: 2026-07-25*
*Last updated: 2026-07-26 after workstream split*
