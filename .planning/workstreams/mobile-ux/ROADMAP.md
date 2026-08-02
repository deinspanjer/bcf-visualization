# Roadmap: Mobile UX (workstream: mobile-ux)

## Overview

This workstream ports the approved mobile UX from `design/mobile-ux/` into the live `web/` app without touching the frozen desktop experience, following the locked acceptance gates in `INTEGRATION_PLAN.md` §5 (its phases A–E, with D+E merged into Phase 4). It is fully independent of the `curation` workstream (no shared files, no shared data) and may run in parallel with it — see `.planning/workstreams/curation/ROADMAP.md`.

Phases are strictly sequential within this workstream.

> **Split note (2026-07-26):** This roadmap originally carried both tracks as Phases 1–8. Track B (Autonomous Curation, old Phases 5–8) now lives in the `curation` workstream, renumbered 1–4.

## Workstream Gates

1. **Interview gate (Phase 1 start) — SATISFIED 2026-07-25.** Phase 1 began with `/gsd-discuss-phase` resolving in one sitting: the `INTEGRATION_PLAN.md` §9 open questions, the `user-scalable=no` vs. Lighthouse-a11y conflict, `visibilitychange` pause confirmation, and the curation provenance field shape (recorded as D-01..D-05 in `phases/01-mobile-state-gesture-plumbing/01-CONTEXT.md`; D-04 handed to the curation workstream so it needs no second interview).
2. **Phase gates.** Every phase ends with a user review checkpoint against the corresponding `INTEGRATION_PLAN.md` §5 gate, plus a pass of the scripted desktop smoke test (MOBF-06 / plan §0.5). A phase that fails the smoke test is not done.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Mobile State & Gesture Plumbing** - Interview gate, layout-mode detection, gesture attach/detach contract, storage keys, desktop smoke test (completed 2026-07-26)
- [x] **Phase 2: Portrait Layout** - Sky over mini-rail dock, sky gestures, zoom-aware rail scrub, cluster-binning, Settings/About/Help (completed 2026-08-01)
- [ ] **Phase 3: Landscape Layout** - Sky plus field-log rail, cinema-scrub auto-hide, rotation state preservation, flyouts
- [ ] **Phase 4: Mobile Cutover & Accessibility** - Banner deletion, landing-page chip, aria-live, keyboard, reduced-motion, Lighthouse a11y ≥ 90

## Phase Details

### Phase 1: Mobile State & Gesture Plumbing

**Goal**: The app knows which layout it is in and can receive touch gestures safely, with zero new UI and zero desktop change
**Mode:** mvp
**Depends on**: Nothing (Track A entry point)
**Requirements**: MOBF-01, MOBF-02, MOBF-03, MOBF-04, MOBF-05, MOBF-06
**Success Criteria** (what must be TRUE):

  1. Dre's answers to the §9 open questions, the `user-scalable=no` vs. Lighthouse-a11y conflict, the `visibilitychange` pause behavior, and the Track B provenance field shape are recorded as decisions before any mobile code is written
  2. On a phone-sized viewport `app.layoutMode` reports `portrait` or `landscape` and stays correct across rotation; above the breakpoint it stays `desktop`
  3. A gesture on an attached surface fires its handler exactly once, including when a re-render lands mid-drag — no double-binding, no lost pointer capture
  4. Timeline zoom, tap-to-pause, haptics, and help-seen preferences round-trip through `bcf:*` keys across reload, and `bcf:portrait-dismissed` is purged after the `STORAGE_VERSION` bump
  5. The scripted desktop smoke test runs on demand, covers the §0.5 checklist, and passes

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Tracer: verbatim gesture port, layoutMode detection, bcf:* v3 storage schema, per-render attach lifecycle, Playwright plumbing proofs

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Mobile CSS foundation (web/mobile.css: touch-action surfaces, svh/dvh, safe-area insets) + visibilitychange pause (D-02, mobile-only)
- [x] 01-03-PLAN.md — Scripted §0.5 desktop smoke test (tests/test_desktop_smoke.py, D-10 gate artifact)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Full verification run + §5 Phase A gate review checkpoint with Dre

**Notes**: Interview gate (`/gsd-discuss-phase`) is mandatory and blocks all coding in this phase. CSS foundation decisions (`touch-action`, `overscroll-behavior`, `svh`/`dvh`, `env(safe-area-inset-*)`, viewport meta) are made here, not retrofitted. Phase ends with the §5 Phase A gate review plus a desktop smoke test pass.

### Phase 2: Portrait Layout

**Goal**: A phone held upright is a complete, usable visualization — sky, scrubbing, settings, and help
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: MOBP-01, MOBP-02, MOBP-03, MOBP-04, MOBP-05
**Success Criteria** (what must be TRUE):

  1. Portrait phone shows the sky at ~60% of the viewport over an always-visible mini-rail dock, with top chips never overlapping the sky's focal label
  2. Sky gestures behave per the contract: tap toggles pause within 250ms (no-op when tap-to-pause is off), double-tap snaps to the last roll and resumes, horizontal swipe scrubs ±1 roll per 56px with a haptic per roll crossed
  3. Dragging the mini-rail scrubs word position accurately at every zoom level, including auto-panned positions
  4. At 1× the rail shows counted cluster diamonds instead of a smear of overlapping dots, and the active roll always renders as a separate cyan diamond on top
  5. Settings, About, and Help all work in portrait; Help auto-opens on a first visit; every preference survives reload

**Plans**: 5/5 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Tracer: portrait render branch, real sky primitives, dock + mini-rail scrub, MOBP-01 layout acceptance

**Wave 2** *(blocked on Wave 1)*

- [x] 02-02-PLAN.md — Sky gesture contract (tap / double-tap / swipe-step) + dock speed cycle and tap hint

**Wave 3** *(blocked on Wave 2)*

- [x] 02-03-PLAN.md — Cluster binning with counted diamonds + zoom-aware scrub at 1×/2×/4×/8×

**Wave 4** *(blocked on Wave 3)*

- [x] 02-04-PLAN.md — Settings / About / Help surfaces with focus trap, back gesture, first-run auto-open

**Wave 5** *(blocked on Wave 4)*

- [x] 02-05-PLAN.md — Full-suite sweep, freeze proof, COVERAGE.md + §5 Phase B gate review with Dre

**UI hint**: yes
**Notes**: Flyout focus-trap and back-gesture handling are built alongside the flyouts here, not deferred to Phase 4. Real-device iOS Safari verification is expected (emulation does not reproduce toolbar/`100vh` behavior). Phase ends with the §5 Phase B gate review plus a desktop smoke test pass.

### Phase 3: Landscape Layout

**Goal**: A phone turned sideways gives a cinema view with the field log, and rotating between layouts never loses your place
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: MOBL-01, MOBL-02, MOBL-03, MOBL-04
**Success Criteria** (what must be TRUE):

  1. Landscape phone shows the sky at ~75% width plus a right rail with the field log (top 2/3) and a settings/about dock (bottom 1/3), driven by the existing field-log data path
  2. Chrome auto-hides after 4000ms idle; the first sky tap reveals without pausing, a second tap within the window pauses, and any sky or rail touch resets the timer
  3. Rotating mid-playback swaps layouts with no visible remount, preserving word position, play state, speed, zoom, and preference toggles
  4. Flyouts dismiss on backdrop tap, keep focus trapped while open, and close on the mobile back gesture instead of leaving the app

**Plans**: 2/4 plans executed

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Tracer: landscape render arm end-to-end (shared sky helper, live field log, dispatch generalization) + landscape CSS, safe areas, D-32 scroll-lock

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — One gesture-attach lifecycle for both layouts (D-34) + cinema-scrub drag + the 4000ms chrome auto-hide timer

**Wave 3** *(blocked on Wave 2)*

- [ ] 03-03-PLAN.md — Landscape surface stack (backdrop / focus trap / back gesture) + rotation hand-off and the boundary matrix

**Wave 4** *(blocked on Wave 3)*

- [ ] 03-04-PLAN.md — Full-suite sweep, whole-phase freeze proof, COVERAGE.md + §5 Phase C gate review with Dre (D-23 iOS device pass)

**UI hint**: yes
**Notes**: Reuses the Phase 2 attach/detach convention rather than reinventing it. Rotation mid-playthrough is the hard gate and must be verified on a real device — the `resize`/`orientationchange` race is invisible in emulation. Phase ends with the §5 Phase C gate review plus a desktop smoke test pass.

### Phase 4: Mobile Cutover & Accessibility

**Goal**: Mobile is the real experience — the fallback banner is gone, desktop is provably untouched, and the app is accessible
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: MOBX-01, MOBX-02, MOBX-03, MOBX-04, MOBX-05
**Success Criteria** (what must be TRUE):

  1. No "rotate to landscape" banner exists anywhere (`renderPortraitBanner` and its CSS are deleted), and the desktop UI at ≥ 1100px is byte-identical to pre-change
  2. The landing page shows a story-title chip with author credit and a `?` button that opens the same help overlay, with the Survey letter left verbatim
  3. Roll changes are announced via `aria-live="polite"`, keyboard equivalents work (Space, ←/→, Home, `?`), and every tappable target is at least 44×44 CSS px
  4. Lighthouse Accessibility scores ≥ 90 on the mobile preset
  5. With `prefers-reduced-motion: reduce`, transitions and throw decay are disabled and auto-hide doubles to 8000ms; playback pauses when the page is hidden

**Plans**: TBD
**UI hint**: yes
**Notes**: Merges `INTEGRATION_PLAN.md` §5 phases D and E. Only safe once Phases 2 and 3 have both passed their gates — the portrait banner is the safety net until then. The `user-scalable=no` decision made at the Phase 1 interview is re-verified here against the real Lighthouse run. Phase ends with the §5 Phase D+E gate review plus a desktop smoke test pass.

## Progress

**Execution Order:** 1 → 2 → 3 → 4 (strictly sequential). The `curation` workstream runs independently in parallel.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Mobile State & Gesture Plumbing | 4/4 | Complete    | 2026-07-26 |
| 2. Portrait Layout | 5/5 | Complete    | 2026-08-01 |
| 3. Landscape Layout | 2/4 | In Progress|  |
| 4. Mobile Cutover & Accessibility | 0/TBD | Not started | - |

## Requirement Coverage

20 of 20 v1 requirements mapped, each to exactly one phase.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 | MOBF-01, MOBF-02, MOBF-03, MOBF-04, MOBF-05, MOBF-06 | 6 |
| 2 | MOBP-01, MOBP-02, MOBP-03, MOBP-04, MOBP-05 | 5 |
| 3 | MOBL-01, MOBL-02, MOBL-03, MOBL-04 | 4 |
| 4 | MOBX-01, MOBX-02, MOBX-03, MOBX-04, MOBX-05 | 5 |
| **Total** | | **20** |

---
*Roadmap created: 2026-07-25; split into the mobile-ux workstream 2026-07-26*
