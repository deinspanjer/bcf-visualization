# Roadmap: BCF Visualization — Mobile UX + Autonomous Curation

## Overview

This milestone runs **two independent tracks**. Track A (Phases 1–4) ports the approved mobile UX from `design/mobile-ux/` into the live `web/` app without touching the frozen desktop experience, following the locked acceptance gates in `INTEGRATION_PLAN.md` §5 (its phases A–E, with D+E merged into Phase 4). Track B (Phases 5–8) refreshes the epub to the latest released chapters and then builds an agent-based curation pipeline that curates the remaining chapters, routing high-confidence output into the trusted overrides file with provenance and low-confidence output into a proposals sidecar for hand-curation.

The two tracks share no files and no data. **Phase 5 has no dependency on Phases 1–4** and may be executed before, after, or in parallel with Track A. Within each track, phases are strictly sequential — each stage's correctness bar depends on the previous stage's output being trustworthy.

## Track Independence

| Track | Phases | Domain | Entry point | Parallelizable |
|-------|--------|--------|-------------|----------------|
| A — Mobile UX | 1 → 2 → 3 → 4 | `web/*`, `index.html`, `design/mobile-ux/` | Phase 1 | Yes, vs. Track B |
| B — Autonomous Curation | 5 → 6 → 7 → 8 | `scripts/*`, `data/manual/*`, Forge Curator TUI | Phase 5 | Yes, vs. Track A |

## Milestone Gates

Three user-mandated gates govern this milestone:

1. **Interview gate (Phase 1 start).** Phase 1 MUST begin with `/gsd-discuss-phase` resolving, in one sitting: `INTEGRATION_PLAN.md` §9 open questions (mobile cinematic behavior vs. desktop, carousel focus pattern on mobile, `visibilitychange` pause), the `user-scalable=no` vs. Lighthouse-a11y conflict, `visibilitychange` pause confirmation, and **the provenance field shape for Track B**. The Track B question is asked here deliberately so Phase 7 needs no second interview.
2. **Track A phase gates.** Every Track A phase ends with a user review checkpoint against the corresponding `INTEGRATION_PLAN.md` §5 gate, plus a pass of the scripted desktop smoke test (MOBF-06 / plan §0.5). A phase that fails the smoke test is not done.
3. **Epub hard gate (Phase 5).** Phase 5 is a HARD GATE for Phases 6–8. No curation infrastructure, verifier work, or agent run may begin until the epub is refreshed and the full pipeline re-runs green on it. Building a verifier or confidence gate against a stale chapter set means re-tuning everything after the refresh.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

**Track A — Mobile UX**

- [ ] **Phase 1: Mobile State & Gesture Plumbing** - Interview gate, layout-mode detection, gesture attach/detach contract, storage keys, desktop smoke test
- [ ] **Phase 2: Portrait Layout** - Sky over mini-rail dock, sky gestures, zoom-aware rail scrub, cluster-binning, Settings/About/Help
- [ ] **Phase 3: Landscape Layout** - Sky plus field-log rail, cinema-scrub auto-hide, rotation state preservation, flyouts
- [ ] **Phase 4: Mobile Cutover & Accessibility** - Banner deletion, landing-page chip, aria-live, keyboard, reduced-motion, Lighthouse a11y ≥ 90

**Track B — Autonomous Curation**

- [ ] **Phase 5: Epub Refresh & Exemplar Mining** - Latest chapters hydrated, pipeline green, regime-tagged exemplar index from the 118-chapter corpus
- [ ] **Phase 6: Mechanical Verifier** - Deterministic quote/word-position/perk-name verification baselined at 100% on hand-curated chapters
- [ ] **Phase 7: Provenance Schema & Agent Curation Pipeline** - Provenance field rewrite, per-chapter curation agent, confidence gate, overrides/proposals routing
- [ ] **Phase 8: Proposal Review & Full Batch Run** - Forge Curator proposal review flow plus the full batch over remaining chapters

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
**Plans**: TBD
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
**Plans**: TBD
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
**Plans**: TBD
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

### Phase 5: Epub Refresh & Exemplar Mining
**Goal**: The pipeline reflects the newest released chapters, and the hand-curated corpus is characterized well enough to teach an agent
**Mode:** mvp
**Depends on**: Nothing (Track B entry point — independent of Phases 1–4, may run in parallel or first)
**Requirements**: EPUB-01, EPUB-02, CINF-02
**Success Criteria** (what must be TRUE):
  1. The existing private-source flow (`sync_private_source_repo.py` → `hydrate_source_epub.py`) yields an epub whose chapter count and nav entries reflect the newest release
  2. A full pipeline re-run completes green: predicted rolls extend into the new chapters, all previously curated chapters still validate, and `visualization_facts.json` rebuilds
  3. An exemplar index built from the hand-curated chapters is tagged by CP regime, and a retrieval query for a target chapter returns only same-regime exemplars
  4. The index documents the corpus's observed evidence-quote patterns, roll-shape distribution, and perk-link conventions
**Plans**: TBD
**Notes**: HARD GATE for Phases 6–8 — no verifier, schema, or agent work begins until this phase is green. Regime tagging must exist before retrieval logic is built, not be retrofitted. Exemplar mining is pure analysis over existing data; no LLM calls in this phase.

### Phase 6: Mechanical Verifier
**Goal**: Any candidate curation can be judged true or false by deterministic code, with the hand-curated corpus as its proof of correctness
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: CINF-03
**Success Criteria** (what must be TRUE):
  1. Running the verifier over every hand-curated chapter passes 100% — a failure means the verifier is wrong, not the corpus
  2. The verifier accepts only exact or whitespace-normalized quote matches and rejects paraphrase; no fuzzy matching path exists
  3. Word positions and perk names are resolved through the pipeline's existing tokenizer and `perk_name_resolver.py` ladder, with no second implementation of either
  4. The verifier reports per-roll pass/fail with reasons, in a form the Phase 7 confidence gate can consume
**Plans**: TBD
**Notes**: Built and validated with zero LLM in the loop, so agent output has a real bar to clear on its first run. This is the "never let the model compute a value that has a deterministic source of truth" rule made executable.

### Phase 7: Provenance Schema & Agent Curation Pipeline
**Goal**: Agents can curate a chapter, and their output is routed by confidence into the trusted corpus or a proposals queue — never silently degrading either
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: CINF-01, CINF-04, ACUR-01, ACUR-02, ACUR-03
**Success Criteria** (what must be TRUE):
  1. Every roll-override entry carries a provenance marker in the shape decided at the Phase 1 interview, and every in-repo consumer (`derive_roll_facts`, Forge Curator TUI, validators) is rewritten for it in the same change — no shims, aliases, or deprecation paths
  2. Running the agent on a chapter produces roll objects in the existing schema where word positions and roll ordinals are derived mechanically and never emitted by the model
  3. High-confidence curations write into `chapter_roll_overrides.json` with provenance; low-confidence curations write to a proposals sidecar in the same roll-object schema
  4. Re-running a chapter with unchanged inputs produces no diff (fingerprint-keyed idempotency), and an existing hand-curated entry is never overwritten
  5. The confidence gate is tuned against held-out hand-curated chapters, uses mechanical verification as the hard signal with model self-report only as a tiebreaker, and demonstrably routes regime-boundary-adjacent chapters to low confidence more often
**Plans**: TBD
**Notes**: Research flags this phase as needing calibration, not just implementation — the confidence rubric is derived empirically from a pilot batch against known chapters, with a checkpoint before running on uncurated ones. The provenance field shape was settled at the Phase 1 interview; no second interview needed. Curator vs. predictor roll numbering diverge — the agent must respect the existing predicted-mode mapping rather than inventing one.

### Phase 8: Proposal Review & Full Batch Run
**Goal**: The remaining chapters are curated, and everything the agent was unsure about is sitting in the TUI waiting for Dre
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: ACUR-04, ACUR-05
**Success Criteria** (what must be TRUE):
  1. The Forge Curator TUI lists agent proposals and supports reviewing, accepting, editing, and rejecting them using its existing keybind and interaction model
  2. Accepting a proposal produces a hand-curated entry that outranks agent provenance for that chapter
  3. A batch run over all remaining uncurated chapters completes and emits a per-chapter summary report of accepted / proposed / failed
  4. Pipeline validation is green after the batch, and the visualization renders agent-curated chapters correctly alongside hand-curated ones
**Plans**: TBD
**Notes**: Extends the existing ~7.5K-line TUI rather than building a second review surface. Depends on the finalized proposals-file schema from Phase 7.

## Progress

**Execution Order:**
Within Track A: 1 → 2 → 3 → 4. Within Track B: 5 → 6 → 7 → 8. Tracks are independent; either may start first or both may run in parallel.

| Phase | Track | Plans Complete | Status | Completed |
|-------|-------|----------------|--------|-----------|
| 1. Mobile State & Gesture Plumbing | A | 0/TBD | Not started | - |
| 2. Portrait Layout | A | 0/TBD | Not started | - |
| 3. Landscape Layout | A | 0/TBD | Not started | - |
| 4. Mobile Cutover & Accessibility | A | 0/TBD | Not started | - |
| 5. Epub Refresh & Exemplar Mining | B | 0/TBD | Not started | - |
| 6. Mechanical Verifier | B | 0/TBD | Not started | - |
| 7. Provenance Schema & Agent Curation Pipeline | B | 0/TBD | Not started | - |
| 8. Proposal Review & Full Batch Run | B | 0/TBD | Not started | - |

## Requirement Coverage

31 of 31 v1 requirements mapped, each to exactly one phase.

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 | MOBF-01, MOBF-02, MOBF-03, MOBF-04, MOBF-05, MOBF-06 | 6 |
| 2 | MOBP-01, MOBP-02, MOBP-03, MOBP-04, MOBP-05 | 5 |
| 3 | MOBL-01, MOBL-02, MOBL-03, MOBL-04 | 4 |
| 4 | MOBX-01, MOBX-02, MOBX-03, MOBX-04, MOBX-05 | 5 |
| 5 | EPUB-01, EPUB-02, CINF-02 | 3 |
| 6 | CINF-03 | 1 |
| 7 | CINF-01, CINF-04, ACUR-01, ACUR-02, ACUR-03 | 5 |
| 8 | ACUR-04, ACUR-05 | 2 |
| **Total** | | **31** |

---
*Roadmap created: 2026-07-25*
