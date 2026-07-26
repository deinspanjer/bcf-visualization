# BCF Visualization — Mobile UX + Autonomous Curation

## What This Is

An interactive web visualization of the Celestial Forge roll mechanics in *Brockton's Celestial Forge* (by LordRoustabout), backed by a Python data pipeline that derives roll facts from the story epub and a hand-curated evidence corpus. This milestone delivers two independent workstreams: (1) shipping the approved mobile UX (portrait + landscape layouts, gestures, settings) into the live `web/` app, and (2) building an agent-based curation pipeline that autonomously curates remaining story chapters using the 118-chapter hand-curated corpus as exemplars.

## Core Value

The visualization stays correct and trustworthy: the frozen desktop experience must not regress, and agent-curated data must never silently degrade the hand-curated evidence corpus.

## Requirements

### Validated

- ✓ Desktop visualization (scrubber, carousel, sky camera, roll log, playthrough mode) — shipped, working on `main`
- ✓ Data pipeline DAG (`scripts/pipeline.py`): epub → chapters → sections → predicted rolls → roll facts → `visualization_facts.json` — existing
- ✓ Forge Curator TUI for hand-curating roll evidence into `data/manual/chapter_roll_overrides.json` — existing, 118/195 chapters curated
- ✓ Predicted-roll simulation across 3 CP regimes with cross-validation against logged rolls — existing
- ✓ Perk name resolution ladder + perk directory build — existing
- ✓ Private-source epub management (`sync_private_source_repo.py`, `hydrate_source_epub.py`) — existing

### Active

**Workstream 1 — Mobile UX (per `design/mobile-ux/INTEGRATION_PLAN.md`):**

- [ ] Fresh-perspective review of the integration plan, resolving its §9 open questions and any questionable decisions via interview with Dre (gate before any code)
- [ ] Phase A: gesture + state plumbing (`web/mobile-gestures.js`, `LS_*` keys, `STORAGE_VERSION` bump, `app.layoutMode` detection)
- [ ] Phase B: Portrait C layout (sky + mini-rail dock, gestures, cluster-binning, Settings/About/Help surfaces)
- [ ] Phase C: Landscape F layout (sky + field-log rail, cinema-scrub auto-hide, flyouts)
- [ ] Phase D: cutover (delete portrait banner, landing-page title chip + help button, desktop byte-identical above breakpoint)
- [ ] Phase E: polish + a11y (aria-live, keyboard, reduced-motion, Lighthouse a11y ≥ 90)
- [ ] Review checkpoint with Dre at each phase gate

**Workstream 2 — Autonomous chapter curation:**

- [ ] Hard gate: refresh the epub to the latest released chapters (sync private-source repo, hydrate, re-run pipeline; verify chapter count and predicted-roll integrity)
- [ ] Confidence framework: define what makes an agent curation "high confidence" by mining the 118-chapter hand-curated corpus (evidence-quote patterns, roll structure, perk-link conventions)
- [ ] Agent curation pipeline: agents curate remaining chapters; high-confidence rolls written into `chapter_roll_overrides.json` with a provenance marker; low-confidence output to a separate proposals file
- [ ] Forge Curator TUI surfaces agent proposals for hand-curation of the low-confidence remainder
- [ ] Validation: agent-curated chapters pass the same pipeline validation as hand-curated ones (quote text verifies against prose, word positions align, perk names resolve)

### Out of Scope

- Mobile v2 backlog items (pinch zoom, long-press preview, edge swipe-down, throw inertia, real constellation outlines in sky) — deferred by the integration plan
- Any change to desktop behavior/appearance at viewport ≥ 1100px — desktop is frozen per plan §0
- Shared components between desktop and mobile views — plan explicitly forbids; duplicate freely
- Automated curation of ambiguous/low-confidence chapters — Dre hand-curates those by design
- Real constellation rendering in the sky viewport — separate workstream (`phase4_sky_view_design.md`)

## Context

- Repo: brownfield, working data pipeline (Python) + static web app (vanilla JS, no framework). Web layer fetches a single `visualization_facts.json` bundle plus manifest; new viz inputs go through the bundler, not new fetches.
- The mobile prototype is React/JSX (`design/mobile-ux/prototype/`); production port is vanilla JS into `web/app.js` / new files. The integration plan references `redesign/mobile-ux/…` paths — actual location is `design/mobile-ux/…` (stale prefix; all artifacts exist).
- Integration plan §9 open questions (need Dre's answers at the interview gate): mobile cinematic behavior vs desktop, carousel focus pattern on mobile, pause on `document.visibilitychange`.
- Curation corpus: `data/manual/chapter_roll_overrides.json` (118 of 195 chapters). Roll schema: perks, outcome, constellation, word_position, display_position_policy, evidence_quotes (text + mention chapter/word position), curator_note. No numeric confidence field exists today.
- Several chapters have been released since the epub was last refreshed; chapter count will grow past 195 after the sync.
- Epub is copyrighted prose: gitignored locally, managed via a private source repo. Agent curation must read prose locally and never commit/redistribute it.
- Curator vs predictor roll numbering diverge; predicted-mode maps curator rolls to non-skipped predictor slots — curation agents must respect this accounting.

## Constraints

- **Desktop frozen**: No visual/behavioral change ≥ 1100px; read-only render functions listed in plan §0.2; no edits to existing CSS rules or variables; branch at `render()` on `app.layoutMode`.
- **Schema policy**: Schema changes are full rewrites of all in-repo consumers — no shims, aliases, or deprecation paths. Adding provenance/confidence fields to the overrides schema means updating every consumer (derive_roll_facts, TUI, validators) in the same change.
- **No parallel implementations**: If agent curation needs a domain quantity the pipeline already computes, reuse it; never add a second computation path.
- **Word-count discipline**: Only `chapter_facts.json:cp_earning_word_count` is valid for CP math.
- **Copyright**: Story prose stays local; no prose in committed artifacts beyond the established evidence-quote convention.
- **Curation authority**: Hand-curated overrides (and Dre's narrative-evidence overrides) always beat agent output; agents never overwrite an existing hand-curated chapter entry.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Agent curation split by confidence: high-confidence direct to overrides with provenance marker, low-confidence to proposals file | Preserves corpus trust while capturing autonomous throughput; TUI surfaces the remainder | — Pending |
| Mobile UX gates: one upfront interview (plan review + §9 questions), then review checkpoint at each phase gate A–E | Resolves design ambiguity once; keeps Dre in the loop at natural acceptance boundaries | — Pending |
| Follow INTEGRATION_PLAN.md as source of truth for mobile scope (with fresh-perspective review first) | Plan is locked v1 with explicit desktop-freeze rules; review catches staleness (e.g., path prefix) | — Pending |
| Epub refresh uses existing `sync_private_source_repo.py` → `hydrate_source_epub.py` → `pipeline.py` flow | Flow already exists and maintains private-repo provenance; no new download path | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-25 after initialization*
