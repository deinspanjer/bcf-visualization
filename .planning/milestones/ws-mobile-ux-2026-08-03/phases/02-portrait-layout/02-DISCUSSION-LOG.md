# Phase 2: Portrait Layout - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-26
**Phase:** 2-Portrait Layout
**Mode:** `--auto` (single pass; every question resolved to the recommended default without user prompts)
**Areas discussed:** Interim landscape fallback, Portrait sky source, About access in portrait, Details mode in portrait v1, Zoom-aware rail wiring, Portrait playback update tier, Flyout back-gesture & focus trap

Prior decisions honored without re-asking: D-01..D-11 (Phase 1 interview + auto-resolved), plan §1 locked decisions (tap-to-pause default ON, swipe right = forward, chrome auto-hide landscape-only, pinch/long-press deferred to v2), gesture-contract §03 constants, plan §7 prohibitions.

---

## Interim landscape fallback (D-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Landscape keeps current fallback (desktop shell + banner) until Phase 3 | Only the portrait arm lands this phase; banner remains the safety net (deleted in Phase 4) | ✓ |
| Render portrait layout in landscape too | Wrong ergonomics; duplicates work Phase 3 replaces; widens Phase 2 test surface | |

**Choice:** `[auto]` recommended default — portrait arm only.

## Portrait sky source (D-13)

| Option | Description | Selected |
|--------|-------------|----------|
| Real sky via existing sky-camera/cinematic model; call frozen renderers where sizing allows, duplicate mobile markup over the same model where not | The app's actual visualization; consistent with D-01 (cinematic same as desktop) and plan §7 (duplicate views over shared model) | ✓ |
| Port the prototype's procedural-diamond `Sky` | It was a fidelity stand-in in a standalone prototype, not a production target ("plan wins over prototype") | |

**Choice:** `[auto]` recommended default. Researcher determines which sky renderers are callable at phone sizes.

## About access in portrait (D-14)

| Option | Description | Selected |
|--------|-------------|----------|
| ⓘ button in the dock transport row next to the gear | Mirrors landscape's Settings/About dock pairing; MOBP-05 requires About in portrait; prototype `PortraitC` simply lacked an entry point | ✓ |
| About link inside the Settings flyout | Buries story credit/source links one level deeper; diverges from landscape access pattern | |
| Second icon in the top chip cluster | Crowds the top cluster and risks the MOBP-01 focal-label overlap rule | |

**Choice:** `[auto]` recommended default — dock ⓘ button.

## Details mode in portrait v1 (D-15)

| Option | Description | Selected |
|--------|-------------|----------|
| Faithful prototype port: mode segment persists shared `bcf:mode`, portrait always renders the playthrough presentation; flag at Phase B gate review | The approved design contains no mobile details view; inventing one is unapproved new UI | ✓ |
| Build a minimal mobile roll-log/details view now | New capability not in the approved prototype or plan §2 scope — deferred idea instead | |
| Drop the mode segment from portrait Settings | Deviates from plan §2's explicit Settings scope (mode is listed) | |

**Choice:** `[auto]` recommended default, with an explicit gate-review flag for Dre.

## Zoom-aware rail wiring (D-17)

| Option | Description | Selected |
|--------|-------------|----------|
| Single path: `attachRailScrub` only; zoom/pan math inside `onScrub`; return roll index so the built-in haptic roll-cross tick works | Keeps `mobile-gestures.js` byte-identical; one scrub input path; restores the haptic the prototype's override bypassed | ✓ |
| Port the prototype's parallel raw pointer-listener override alongside `attachRailScrub` | React workaround; creates a second scrub input path (violates no-parallel-implementations) and double-handles every pointer event | |

**Choice:** `[auto]` recommended default.

## Portrait playback update tier (D-18)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `cachePlaybackDomRefs`/`updatePlaybackFrame` with a portrait early-branch; bins recompute only on structural render / zoom change / resize | One rAF tier, per D-07 and no-parallel-implementations; desktop path byte-identical | ✓ |
| Separate mobile rAF/update loop | Second animation pipeline to keep in sync; direct violation of the consolidation rule | |

**Choice:** `[auto]` recommended default.

## Flyout back-gesture & focus trap (D-16)

| Option | Description | Selected |
|--------|-------------|----------|
| `history.pushState` sentinel per open surface + `popstate` closes topmost; focus trapped while open, restored on close | Standard mobile-web dismissal pattern; roadmap mandates building this alongside the flyouts in Phase 2 | ✓ |
| Defer back-gesture handling to Phase 3/4 | Contradicts the roadmap's explicit Phase 2 note | |

**Choice:** `[auto]` recommended default.

## Claude's Discretion

- Portrait DOM structure/class names within `renderMobilePortrait()` (prototype as visual reference)
- Chip/hint-row copy and dock metadata formatting
- CSS expression of the ~60% sky / dock split (svh/dvh + flex per D-08)
- Help auto-open trigger point details
- Playwright portrait test structure

## Deferred Ideas

- Mobile details view behind the mode toggle (pending Phase B gate-review outcome on D-15)
- Full-bleed mobile cinematic (v2, per D-01)
- Plan §8 v2 backlog items (pinch zoom, long-press preview, edge peel, throw inertia, real constellation outlines, richer cinematic, Wake Lock)
