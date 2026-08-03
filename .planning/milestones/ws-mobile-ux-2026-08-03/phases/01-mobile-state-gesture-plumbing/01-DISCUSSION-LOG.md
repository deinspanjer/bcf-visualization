# Phase 1: Mobile State & Gesture Plumbing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-25
**Phase:** 1-Mobile State & Gesture Plumbing
**Areas discussed:** Mobile cinematic behavior, Hidden-tab pause, Page zoom vs a11y, Track B provenance shape (interview gate); layout detection, gesture lifecycle, viewport units, storage, smoke test, haptics (auto-resolved)

---

## Mobile cinematic behavior (plan §9)

| Option | Description | Selected |
|--------|-------------|----------|
| Same as desktop (Recommended) | Cinematic plays within the sky area as the desktop model does; text-first for v1; full-bleed deferred to v2 | ✓ |
| Full-bleed on mobile | Chrome-hide + full-viewport cinematic on phones; adds v1 state interactions with landscape auto-hide | |

**User's choice:** Same as desktop

---

## Hidden-tab pause (plan §9)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, pause (Recommended) | Pause autoplay on visibilitychange, state intact on return; mobile layouts only | ✓ |
| No, keep playing | Playhead advances in background | |

**User's choice:** Yes, pause
**Notes:** Added to the phase-gate acceptance checklist since plan §6 omitted it.

---

## Page zoom vs Lighthouse a11y (plan §3.3 conflict)

| Option | Description | Selected |
|--------|-------------|----------|
| Allow zoom (Recommended) | Drop user-scalable=no/maximum-scale; suppress double-tap/pinch page zoom via touch-action on gesture surfaces | ✓ |
| Keep no-zoom, waive audit item | Ship plan meta verbatim, accept Lighthouse penalty with documented waiver | |

**User's choice:** Allow zoom — recorded as a deviation from plan §3.3.

---

## Track B provenance shape

| Option | Description | Selected |
|--------|-------------|----------|
| Rich object (Recommended) | provenance: {source, model, run_id, corpus_fingerprint, confidence} per roll | |
| Minimal marker | Single curated_by: "human"\|"agent" string per curator_added precedent; run bookkeeping in a separate ledger | ✓ |
| Hybrid | Minimal curated_by per roll + separate agent-run ledger with full details | |

**User's choice:** Minimal marker
**Notes:** User declined the recommended rich object. Roll objects stay lean; the separate agent-run ledger carries model/run_id/corpus_fingerprint/confidence and anchors CINF-04 idempotency keying. Binds Phase 7 — no second interview.

---

## Auto-resolved (--auto recommended defaults)

- [auto] Layout detection — Q: "How to detect layoutMode?" → Selected: matchMedia with the exact `web/style.css:360` query string as a shared constant (recommended default)
- [auto] Gesture lifecycle — Q: "How do gesture listeners survive re-renders?" → Selected: per-render attach inside renderMobile* passes; no full render() during active drag (recommended default)
- [auto] Viewport units — Q: "vh vs svh/dvh?" → Selected: svh/dvh + env(safe-area-inset-*) (recommended default)
- [auto] Storage — Q: "Version bump semantics?" → Selected: STORAGE_VERSION "2"→"3", extend migratePreviewStorage purge pattern (recommended default)
- [auto] Smoke test — Q: "Tooling for scripted §0.5 desktop smoke test?" → Selected: Playwright under tests/ (recommended default)
- [auto] Haptics — Q: "vibrate() reliance?" → Selected: decorative-only, feature-detected, no-op on iOS (recommended default)

## Claude's Discretion

- Orientation/resize debounce timing
- Mobile CSS location (style.css scoped block vs web/mobile.css)
- Playwright smoke-test structure and selectors

## Deferred Ideas

- Full-bleed mobile cinematic (v2)
- Plan §8 v2 backlog (pinch zoom, long-press preview, edge peel, throw inertia, real constellation outlines, richer cinematic, Wake Lock)
