# Feature Research

**Domain:** Mobile web media/playback UX (Workstream 1) + human-in-the-loop LLM curation pipeline (Workstream 2)
**Researched:** 2026-07-25
**Confidence:** MEDIUM (a11y/spec-backed items HIGH; general "best practice" web synthesis LOW — see Confidence Notes)

This is a **subsequent-milestone** feature scan, not a green-field domain survey. Workstream 1's scope is already locked by `design/mobile-ux/INTEGRATION_PLAN.md` — the job here is to flag table-stakes gaps in that locked plan, not to re-propose its scope. Workstream 2 has no existing plan to check against, so it gets a fuller table-stakes/differentiator/anti-feature breakdown.

---

## Workstream 1 — Mobile Touch Playback/Scrubbing UX

### Table Stakes Already Covered by the Locked Plan

These are correctly scoped in `INTEGRATION_PLAN.md` §1/§2/§5 — noted here only so the dependency map below is complete, not because they're new findings:

| Feature | Why Expected | Complexity | Plan Reference |
|---|---|---|---|
| Tap-to-pause / double-tap-to-live-edge | Standard mobile media gesture vocabulary (tap-anywhere-to-toggle, double-tap-to-skip) | LOW | §1, §5 Phase A/B |
| Horizontal swipe-to-scrub with haptic-per-unit feedback | Matches "swipe to seek" convention users bring from native video/photo apps | MEDIUM | §1, §5 Phase B |
| Drag-scrub on a rail with live preview | "Live scrubbing" pattern (pause + seek-as-you-drag) is the de facto standard for timeline rails | MEDIUM | §5 Phase B/C |
| Settings persistence in one namespace with a version bump | Users expect prefs (speed, zoom, on-roll behavior) to survive reload | LOW | §4 |
| First-run help overlay, skippable, re-openable from a persistent `?` | Standard onboarding pattern — short, skip-able, always re-enterable via help nav | LOW | §5 Phase B |
| `prefers-reduced-motion` respected (no throw decay, no cross-fade, longer auto-hide) | Now a hard a11y expectation, not a nice-to-have | MEDIUM | §5 Phase E |
| `aria-live="polite"` region for roll changes | WAI media-player pattern: announce status without stealing focus | LOW | §5 Phase E |
| Keyboard equivalents (Space, arrows, Home, `?`) | Media players are expected to be fully keyboard-operable (WAI media player spec) | LOW | §5 Phase E |
| Tap targets ≥ 44×44 CSS px | Exceeds WCAG 2.5.8 AA minimum (24×24); meets AAA guidance — good call already | LOW | §6 checklist |

### Table-Stakes Gaps Not Addressed by the Locked Plan

These are genuine findings — things 2026 mobile users expect from an autoplay/scrub media experience that the plan doesn't currently name. Flag these at the fresh-perspective review gate (Dre interview) before Phase A starts; most are small, cheap to add early, and expensive to retrofit after gesture code ships.

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| `touch-action` / `overscroll-behavior` CSS on gesture surfaces | Without this, the browser's native pull-to-refresh and pan/zoom gestures fight the custom swipe-to-scrub and rail-drag handlers — a near-universal first bug in hand-rolled touch gesture code | LOW | Should land in Phase A alongside `mobile-gestures.js`, not bolted on later. Missing this produces exactly the kind of subtle regression §0.3 warns about, just on the mobile side. |
| Pause on `document.visibilitychange` (tab/app backgrounded) | Standard for any autoplaying media — nobody expects "cinematic" mode to keep advancing word position while the phone is locked or the tab is backgrounded | LOW | **Already flagged as an open question in plan §9** with "strongly recommend yes" — this research confirms yes, treat as settled, not open. |
| Screen Wake Lock during active playthrough | Users expect an actively-autoplaying visualization (comparable to video) not to let the screen dim/lock mid-playback | LOW–MEDIUM | Not mentioned anywhere in the plan. `navigator.wakeLock` is well-supported; needs a request-on-play / release-on-pause pair and a silent no-op fallback where unsupported. |
| Dynamic viewport units (`dvh`/`svh`) instead of `100vh` for full-bleed sky layout | iOS Safari's address-bar show/hide resizes the visual viewport; `100vh`-based full-bleed layouts jump or clip under the bottom chrome as it appears/disappears | MEDIUM | Directly relevant to Portrait C ("sky takes ~60% of viewport") and Landscape F sizing — worth locking down in Phase A/B, not discovered as a bug in Phase E polish. |
| `env(safe-area-inset-*)` for dock/rail placement | iPhone notch/Dynamic Island and home-indicator gesture bar can obscure a bottom-docked mini-rail or a right-side landscape rail without safe-area padding | LOW–MEDIUM | Plan already sets `viewport-fit=cover` (§3.3) — that's step one; step two (actually consuming the safe-area env vars in the mini-rail/rail CSS) isn't listed. |
| Focus trap + `role="dialog"` for Settings/About/Help flyouts | A11y baseline for any overlay: focus should be trapped inside while open and restored to the trigger on close, for both keyboard and screen-reader users | MEDIUM | Plan's Phase E keyboard section covers global Space/arrow/Home/`?` shortcuts but doesn't name flyout focus management specifically — easy to miss and directly affects the Lighthouse a11y ≥ 90 gate. |
| Back-button / history handling for open overlays | Mobile browser back gesture/button is expected to close an open Settings/About/Help flyout rather than navigating away from the app | LOW–MEDIUM | Common miss in SPA-style overlay code; worth a one-line decision (intercept via `popstate` + a pushed history entry per flyout open) rather than discovering it after Phase D ships. |
| Haptics graceful no-op on iOS Safari | `bcf:haptics` (already planned) needs to silently do nothing where `navigator.vibrate` is unsupported (all iOS Safari versions), not throw or leave a broken toggle in Settings | LOW | Feature is already scoped; this is an implementation-detail flag, not new scope — call out during Phase B build so the toggle doesn't look "broken" on iPhone. |

**Accessibility tension to flag, not necessarily block:** the plan's `user-scalable=no` viewport setting (§0.4/§3.3, inherited from the prototype) disables pinch-zoom-of-the-page, which is the standard mitigation against page-zoom fighting the custom gesture surface — but it is also in tension with WCAG 1.4.4 (Resize Text), which technically expects users to be able to zoom text to 200%. This is a common, accepted trade-off in gesture-heavy apps (the Lighthouse a11y ≥ 90 gate in §5 Phase E won't fail on it), but it's worth a one-line acknowledgment at the review gate rather than an unstated assumption.

### Differentiators (Already Planned or Worth Considering)

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Scrubber cluster-binning at all zoom levels | Most mobile timeline scrubbers just smear overlapping dots at high roll density; binning with a count badge is a real usability edge for a 195-chapter, hundreds-of-rolls dataset | MEDIUM | Already planned (§2, §5 Phase B) — correctly scoped as v1, not deferred. |
| Landscape cinema-scrub auto-hide with two-stage reveal/pause tap | More polished than most mobile players' "tap anywhere" (which conflates reveal and pause) | MEDIUM | Already planned (§5 Phase C) — good v1 call. |
| Haptic feedback per roll crossed during swipe-scrub | Tactile confirmation of discrete "roll" boundaries is a nice touch beyond typical scrub-bar haptics (which are usually just edge/snap feedback) | LOW | Already planned (§1, §6). |
| Deep-link / shareable URL fragment to a specific word position or roll | Lets someone share "look at this exact roll" — natural for a story-analysis visualization, and cheap if word-position is already the state's source of truth | LOW–MEDIUM | **Not currently planned.** Worth a note for the v2 backlog (§8) rather than v1 scope — respects the plan's "ship the locked scope" discipline while flagging a genuinely low-cost, high-value follow-up. |
| PWA manifest / "Add to Home Screen" | Turns repeat mobile visits into an app-like experience with no native app cost | LOW | **Not currently planned.** Same treatment — v2 backlog candidate, not v1 scope creep. |

### Anti-Features (Respect the Plan's v2 Deferrals; Don't Reintroduce Scope)

| Feature | Why It Seems Appealing | Why Problematic Now | Alternative |
|---|---|---|---|
| Pinch-to-zoom on the scrubber | Feels more "native" than a segmented control | Plan already deferred this to v2 with a clear reason (segmented 1/2/4/8 zoom covers v1 needs, hook is already in `setPrefs({zoom})`) — reopening it mid-milestone is scope creep against a locked decision | Ship the segmented control; leave the hook per §8.1 |
| Long-press roll-dot preview tooltip | Nice discoverability aid | Explicitly deferred to v2 (§1, §8.2); adds a new interaction mode to an already-dense gesture surface before the core surface has shipped | Defer per plan |
| Throw-to-scrub inertia | Feels more "physical" | Cap is set for v1, physics/easing implementation explicitly deferred (§8.4); the velocity hook already exists so this is cheap to revisit post-ship, not now | Defer per plan; the `swipeEnd(velocity)` hook already carries what's needed |
| Real constellation outline rendering in the sky | Would look better than the procedural diamond | Explicitly out of scope — separate workstream (`phase4_sky_view_design.md`) with its own design process; pulling it into this milestone couples two unrelated efforts | Keep the procedural diamond placeholder; mobile layouts must render whatever the sky becomes, not assume its internals |
| Push notifications / re-engagement prompts | Common growth-hack pattern for media apps | No account system, no server, no user base to notify — pure complexity with no audience | None needed |
| Native app wrapper (Capacitor/Cordova) for app-store presence | "Real app" feel | This is a static personal-project visualization; app-store packaging is a maintenance burden disproportionate to the audience | PWA manifest (see Differentiators) is the right-sized version of "app-like," if ever wanted |
| Usage analytics/telemetry | Tempting to "see what mobile users actually do" | No stated need, adds a privacy/complexity surface unrelated to Core Value, and there's no team to act on the data | Rely on direct feedback from the actual (small, known) audience if tuning is ever needed |
| A third "tablet" breakpoint | Feels more precise than a binary desktop/mobile split | Plan explicitly rejects this (§7) — iPads-in-landscape are desktop, iPads-in-portrait are mobile, and the existing 1100px breakpoint already encodes it correctly | Respect the existing binary breakpoint |

---

## Workstream 2 — Human-in-the-Loop LLM Curation Pipeline

Context that shapes every call below: this is a **single-maintainer** pipeline curating a **single, non-adversarial domain** (one story's roll mechanics) against **one ground-truth curator** (Dre). There is no team, no second independent annotator population, and no continuous-integration cadence — curation happens in bursts. That context is why several "textbook HITL pipeline" features are anti-features here, not just optional.

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| Provenance marker per curated entry (human vs. agent, and which agent/prompt version) | PROJECT.md already commits to this ("high-confidence rolls written into `chapter_roll_overrides.json` with a provenance marker") — without it, the corpus can't be audited or selectively re-curated later, and the "curation authority" rule (hand-curated always beats agent) has nothing to check against | LOW–MEDIUM | Schema change under the project's no-shims policy: touches `derive_roll_facts`, the TUI, and validators in the same change — budget for that, not just the field itself. |
| Confidence score/threshold per chapter (or per roll) routing high→overrides, low→proposals | This *is* the mechanism the whole workstream is built around (PROJECT.md Active items + Key Decisions) | MEDIUM–HIGH | Rubric must be mined from the 118-chapter hand-curated corpus (evidence-quote patterns, roll structure, perk-link conventions) — this is real research/calibration work, not a fixed constant. |
| Review queue surfaced in the existing Forge Curator TUI | Low-confidence output needs somewhere a human actually looks, on the tool the human already uses daily — a separate proposals file nobody opens is dead weight | MEDIUM | Reuses the existing TUI rather than building a second review surface (respects "no parallel implementations"). |
| Validation-harness reuse (quote-verifies-against-prose, word-position alignment, perk-name resolution) | Already an Active requirement in PROJECT.md; this is the actual trust mechanism that lets high-confidence output land *directly* in the corpus without a human gate | MEDIUM | Must be the *same* validators hand-curated chapters pass — a second bespoke "agent validator" would be exactly the parallel-implementation pattern the project forbids. |
| Never-overwrite guarantee for existing hand-curated chapters | Explicit Constraint in PROJECT.md; this is the single most important trust invariant for Core Value ("agent-curated data must never silently degrade the hand-curated evidence corpus") | LOW | Cheap to enforce (check chapter presence before write) but must be enforced at the write boundary, not just assumed by convention. |
| Minimal audit trail: what was agent-curated, when, under which confidence-framework/prompt version | Needed so a future "why does chapter 142 look off" question is answerable, and so a rubric change can be traced against what it affected | LOW | Can piggyback on the provenance field + a timestamp/version — does **not** need a separate audit-log subsystem (see Anti-Features). |
| Idempotent re-runs | The epub will keep growing past 195 chapters and the pipeline will be re-run repeatedly as new chapters release; re-running on an already-curated chapter must not duplicate or corrupt entries | MEDIUM | Ties directly to the never-overwrite guarantee and to provenance (need to know "already agent-curated at rubric v1" vs. "never curated"). |

### Differentiators (Valuable, Not Required for Trust)

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| Confidence-framework versioning tagged per entry | Lets the maintainer identify "these proposals were rejected under rubric v1, worth re-running under v2" as the confidence framework is tuned over time | LOW | Cheap extension of the provenance field; high payoff for an evolving single-maintainer rubric. |
| Batch rerun with diff-against-previous-output | As the rubric improves, re-curating the low-confidence backlog can recover throughput without re-reading every chapter's proposal from scratch | MEDIUM | Most valuable after the first full pass through the 77 uncurated chapters reveals where the rubric under- or over-trusts. |
| Agent rationale/self-critique stored alongside a proposal (not in committed prose, a short note) | Maps naturally onto the existing `curator_note` field convention — lets the human curator evaluate a low-confidence proposal in the TUI without re-deriving evidence from the source text | MEDIUM | High leverage precisely because the TUI already has a place for this kind of note to live. |
| Simple per-batch calibration summary (counts: high-confidence / low-confidence / rejected-on-review) | Cheap visibility into whether the confidence threshold is well-tuned, without building formal statistics | LOW | This is the right-sized substitute for inter-annotator agreement metrics (see Anti-Features) — a maintainer can eyeball "80% of high-confidence proposals survive review unedited" and decide whether to loosen/tighten the threshold. |
| Token/cost tracking per chapter or per batch run | Solo maintainer is paying for the API calls out of pocket across ~77 remaining chapters; visibility into cost avoids surprise bills | LOW | Small, practical, easy to bolt onto the existing pipeline logging. |

### Anti-Features (Overkill for a Single-Maintainer Project)

| Feature | Why Requested | Why Problematic Here | Alternative |
|---|---|---|---|
| Formal inter-annotator agreement metrics (Cohen's κ, Krippendorff's α, Fleiss' κ) | Standard in HITL/annotation literature for measuring labeling quality | These metrics require *multiple independent annotators* to compare against each other. There is exactly one ground-truth curator (Dre) and no second parallel human-annotation stream — there's nothing to compute agreement *against* | Track simple accept/edit/reject counts as proposals move through the TUI review — a de facto precision proxy without needing a second annotator population |
| Multi-model ensemble / voting consensus (e.g., 3 LLM judges vote) | Reduces single-model error/bias in high-stakes labeling pipelines | Disproportionate cost and complexity for one story's roll mechanics reviewed by one trusted human backstop; the never-overwrite + validation-harness gate already catches most failure modes cheaply | Single well-calibrated confidence rubric mined from the 118-chapter corpus, tuned by spot-checking output, not ensemble voting |
| Adopting a dedicated annotation platform (Label Studio, Prodigy, etc.) | Mature, feature-rich, built for exactly this kind of review workflow | Would mean building a second, parallel curation surface alongside the existing Forge Curator TUI — the domain schema (evidence quotes, word positions, perk links, roll accounting) is bespoke enough that a generic tool would need heavy customization anyway, and now there are two UIs to keep in sync | Extend the existing TUI with a proposal-review mode; it already understands the domain schema |
| Continuous CI-style regression testing against a held-out "gold" chapter set with a live quality dashboard | Standard practice for production ML pipelines with ongoing drift risk | Curation happens in bursts (epub refreshes, occasional runs), not continuously; a permanent CI gate and dashboard is process overhead with no team to consume it | One-time calibration pass (spot-check a sample of high-confidence output) when the confidence framework is first built or meaningfully changed, not a permanent pipeline stage |
| Fine-grained per-field/per-token confidence scores (separate confidence for each evidence quote, each word position, etc.) | More granular signal, in theory more precise routing | Adds real complexity to the rubric and schema for a routing decision that only needs two buckets (write-direct vs. review-queue); nothing downstream consumes finer granularity | Single chapter- or roll-level confidence score, matching the actual high/low routing decision that's needed |
| Real-time collaborative review UI (multi-user cursors, comments, assignment) | Standard for team annotation tools | No team — single maintainer, sequential workflow | The existing single-user TUI is already right-sized |
| External tamper-evident audit ledger (immutable/blockchain-style logging) | Sounds rigorous for "trustworthy corpus" claims | Security theater for a personal hobby-project data pipeline; git history is already an append-only, timestamped, diffable record of every change to the overrides file | Rely on git commit history (already true for hand-curated overrides today) plus the in-schema provenance field |

---

## Feature Dependencies

```
[Workstream 1 — Mobile UX]

touch-action / overscroll-behavior CSS ──requires-before──> horizontal swipe-to-scrub, rail drag-scrub
        (gap not in plan)                                    (planned, Phase A/B)

Phase A (app.layoutMode, LS_* keys, gesture plumbing)
    └──requires──> Phase B (Portrait C) ──and──> Phase C (Landscape F)
                       └──requires──> cluster-binning (dense-dataset usability)
                       └──requires──> dvh/svh viewport units + safe-area-inset CSS
                                        (gaps not in plan; cheapest to fix here, not in Phase E)

Settings persistence (bcf: keys + STORAGE_VERSION bump)
    └──requires──> Settings/About/Help flyouts being meaningful across reloads
    └──requires──> focus-trap + role="dialog" on flyouts (gap not in plan)

Phase D (cutover: delete banner, landing page chip)
    └──requires──> Phase B + C complete (nothing left needing the old banner)

Phase E (a11y polish: aria-live, keyboard, reduced-motion, Lighthouse ≥90)
    └──enhances──> everything above; ordered last correctly, but focus-trap
                    and back-button handling for flyouts should be pulled
                    forward into B/C, not left as an E-only concern

pause-on-visibilitychange, wake-lock, haptics-no-op-on-iOS
    └──independent, low-cost additions──> slot into Phase A/B without blocking anything
```

```
[Workstream 2 — Curation Pipeline]

Confidence framework (mined from 118-chapter corpus)
    └──requires-before──> Agent curation pipeline can route high/low confidence

Provenance-marker schema change (full rewrite: derive_roll_facts, TUI, validators)
    └──requires-before──> Agent curation pipeline can write anything
    └──requires-before──> Never-overwrite guarantee can be enforced precisely
    └──requires-before──> Audit trail exists in any form

Validation-harness reuse (existing quote/word-position/perk-name checks)
    └──requires-before──> High-confidence output can land directly in overrides
                            (this is the actual trust gate — nothing else substitutes)

Review queue in Forge Curator TUI
    └──requires──> Provenance-marker schema change (needs to distinguish proposal
                    entries from confirmed overrides)
    └──requires-before──> Low-confidence output has anywhere useful to go

Idempotent re-runs
    └──requires──> Provenance-marker + never-overwrite guarantee
                    (needs to know "already curated, which version" to skip safely)

[Anti-features — explicitly NOT required by anything above]
Inter-annotator agreement metrics ──conflicts-with──> single-ground-truth-curator reality
Dedicated annotation platform ──conflicts-with──> "no parallel implementations" constraint
```

### Dependency Notes

- **The provenance-marker schema change is the true root dependency for Workstream 2.** Almost everything else (routing, review queue, never-overwrite enforcement, audit trail, idempotent reruns) needs to know which entries are agent-authored and under what confidence/version before it can function. This should be the first concrete implementation step, done as a full schema rewrite per the project's no-shims policy — not incrementally.
- **The validation-harness reuse is the actual trust mechanism, not the confidence score.** The confidence score decides *where* output goes; the validators decide whether it's *correct*. Both gates matter, but if forced to prioritize one first, the validators are non-negotiable — they're what makes "direct to overrides" safe at all.
- **On mobile, the CSS-level gaps (`touch-action`, `overscroll-behavior`, `dvh`/`svh`, `env(safe-area-inset-*)`) are cheapest to fix at Phase A/B time** and expensive to retrofit once gesture handlers and layout math are built around their absence — this is the strongest argument for surfacing them at the fresh-perspective review gate before Phase A starts, not discovering them as bugs during Phase E polish.
- **Focus-trap and back-button handling for flyouts are a11y/UX table stakes that naturally belong with the flyouts themselves (Phase B/C), not with the general keyboard-shortcut work in Phase E.** Splitting them out to Phase E risks shipping Phase B/C with flyouts that trap nothing and a back gesture that navigates away from the app.

---

## MVP Definition

Framed against the two workstreams' own already-defined scope (Active items in PROJECT.md), not a fresh MVP proposal — this section maps research findings onto that existing plan.

### Launch With (v1 — matches the locked plan + flagged gaps)

**Workstream 1:**
- [ ] Everything in `INTEGRATION_PLAN.md` §2 "In scope for v1 ship" — locked, already scoped correctly
- [ ] `touch-action` / `overscroll-behavior` CSS on gesture surfaces — cheap, prevents a near-guaranteed first bug
- [ ] Pause on `document.visibilitychange` — plan's own §9 recommends yes; treat as decided, not open
- [ ] `dvh`/`svh` viewport units for full-bleed sky sizing — prevents iOS Safari address-bar layout jumps
- [ ] `env(safe-area-inset-*)` consumed in mini-rail/rail CSS — plan already sets `viewport-fit=cover`; this is step two of that same decision
- [ ] Focus-trap + `role="dialog"` on Settings/About/Help flyouts — belongs with flyout construction, not deferred to polish
- [ ] Back-button handling for open flyouts — small, avoids an accidental app-exit bug
- [ ] Screen Wake Lock during active playthrough — matches user expectations for an autoplaying visualization

**Workstream 2:**
- [ ] Provenance-marker schema change (full rewrite of all consumers) — root dependency for everything else
- [ ] Confidence framework mined from the 118-chapter corpus
- [ ] Agent curation pipeline: high-confidence → overrides (with provenance), low-confidence → proposals file
- [ ] Reuse of existing validation harness for agent-curated chapters — non-negotiable trust gate
- [ ] Review-queue surface in the Forge Curator TUI for low-confidence proposals
- [ ] Never-overwrite enforcement for existing hand-curated chapters

### Add After Validation (v1.x)

- [ ] (WS1) Deep-link/shareable URL fragment to a specific word position — cheap once word-position is confirmed as stable state
- [ ] (WS1) PWA manifest / Add to Home Screen — once mobile usage patterns are actually observed
- [ ] (WS2) Confidence-framework versioning tagged per entry — once the rubric has been tuned at least once and there's a "v1 vs v2" to distinguish
- [ ] (WS2) Batch rerun with diff-against-previous-output — once the first full pass through remaining chapters reveals where the rubric mis-trusts
- [ ] (WS2) Per-batch calibration summary — trigger: after the first agent-curation run, to decide whether to loosen/tighten the threshold

### Future Consideration (v2+, respecting existing deferrals)

- [ ] (WS1) Pinch-to-zoom, long-press preview, edge swipe-down, throw inertia, real constellation rendering — all already deferred by the plan (§8); no new reason found to pull any forward
- [ ] (WS2) Token/cost tracking dashboard — nice, not urgent; add if API spend becomes a real concern
- [ ] (WS2) Agent rationale/self-critique notes in proposals — valuable but can wait until the review queue itself is proven out

---

## Feature Prioritization Matrix

| Feature | User/Maintainer Value | Implementation Cost | Priority |
|---|---|---|---|
| `touch-action`/`overscroll-behavior` CSS (WS1) | HIGH | LOW | P1 |
| Pause on visibilitychange (WS1) | HIGH | LOW | P1 |
| `dvh`/`svh` + safe-area-inset CSS (WS1) | HIGH | LOW–MEDIUM | P1 |
| Flyout focus-trap + back-button handling (WS1) | HIGH | MEDIUM | P1 |
| Screen Wake Lock (WS1) | MEDIUM | LOW–MEDIUM | P1 |
| Provenance-marker schema change (WS2) | HIGH | LOW–MEDIUM | P1 |
| Confidence framework from corpus (WS2) | HIGH | MEDIUM–HIGH | P1 |
| Validation-harness reuse (WS2) | HIGH | MEDIUM | P1 |
| Review queue in TUI (WS2) | HIGH | MEDIUM | P1 |
| Never-overwrite enforcement (WS2) | HIGH | LOW | P1 |
| Idempotent reruns (WS2) | MEDIUM | MEDIUM | P2 |
| Deep-link to word position (WS1) | MEDIUM | LOW–MEDIUM | P2 |
| Confidence-framework versioning (WS2) | MEDIUM | LOW | P2 |
| Batch rerun with diff (WS2) | MEDIUM | MEDIUM | P2 |
| Per-batch calibration summary (WS2) | MEDIUM | LOW | P2 |
| PWA manifest (WS1) | LOW–MEDIUM | LOW | P3 |
| Token/cost tracking (WS2) | LOW–MEDIUM | LOW | P3 |
| Agent rationale notes in proposals (WS2) | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have — either already committed scope (matches PROJECT.md Active items) or a table-stakes gap cheap enough to fold into that same v1 pass
- P2: Should have, natural v1.x follow-up once v1 is running and generates real signal to act on
- P3: Nice to have, defer until there's a concrete trigger (usage pattern, API spend, rubric maturity)

---

## Reference Patterns (in place of a Competitor Feature Analysis)

This isn't a market product with competitors, so this section substitutes the reference behaviors and specs actually consulted:

| Area | Reference Pattern | How It Informs This Project |
|---|---|---|
| Mobile scrub gestures | Native mobile video players' tap-anywhere/swipe-to-seek/drag-live-preview conventions | Confirms the plan's gesture contract (§1) matches mainstream expectations rather than inventing a novel interaction model |
| Media player a11y | W3C WAI "Media Players" pattern, WCAG 2.5.8 (target size), WCAG 1.4.4 (resize text) | Backs the plan's aria-live/keyboard/tap-target choices; surfaces the `user-scalable=no` tension as a known, accepted trade-off rather than an unstated risk |
| Onboarding overlays | Standard "short, skippable, always re-enterable" pattern from mobile onboarding UX literature | Confirms the plan's first-run-help-overlay design (auto-open once, `?` button to reopen) already matches the pattern; no changes suggested |
| HITL LLM annotation | Draft-then-selectively-review pattern (LLM proposes, human reviews only uncertain cases) cited as matching full-human quality at a fraction of review effort | Directly validates the confidence-threshold-routing design already chosen in PROJECT.md's Key Decisions — this is the right shape of pipeline for this problem |
| Solo-maintainer data curation | Lightweight, per-sample-provenance pipelines (as opposed to heavyweight MLOps annotation platforms) | Backs the anti-feature calls against adopting a dedicated annotation platform or building CI-style regression dashboards |

---

## Confidence Notes

- **HIGH confidence:** WCAG/WAI-sourced a11y specifics (tap target sizing, aria-live pattern, reduced-motion, media-player keyboard operability) — these are spec citations, not opinion.
- **MEDIUM confidence:** Mobile gesture conventions (tap/swipe/drag-live-preview), onboarding pattern guidance, HITL draft-then-review pipeline shape — cross-referenced across multiple independent web searches and consistent with well-established, longstanding practice, but individual sources are general web content rather than primary specs.
- **LOW confidence, flagged accordingly:** Any single-source claim not corroborated elsewhere was excluded rather than reported. Where a source disagreed with the plan's own stated open questions (e.g., visibilitychange pause), the plan's framing was treated as authoritative and the research used only to confirm the recommended answer.
- **Gap:** Web search did not surface strong, dedicated primary-source guidance specifically on "first-run help overlay for a media/timeline app" (as opposed to generic app onboarding) or on audit-trail tooling specifics for HITL pipelines — those sections above lean more on direct application of the project's own stated constraints (PROJECT.md) than on external sourcing.

## Sources

- `design/mobile-ux/INTEGRATION_PLAN.md` (primary source — locked plan, read in full)
- `.planning/PROJECT.md` (primary source — Workstream 2 requirements and constraints)
- W3C WAI, "Media Players" pattern — https://www.w3.org/WAI/media/av/player/
- WCAG 2.5.8 Target Size (Minimum) implementation guide — https://www.allaccessible.org/blog/wcag-258-target-size-minimum-implementation-guide
- MDN, "Mobile accessibility checklist" — https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Mobile_accessibility_checklist
- Accessible.org, "Video Player Accessibility Best Practices" — https://accessible.org/video-player-accessibility-best-practices/
- Rabbitpair, "Web Video Gesture Controls: Swipe, Hold, Double Tap Guide" — https://www.rabbitpair.com/en/blog/gestify-video-gesture-control-guide
- react-native-video-controls PR #126 (tap-anywhere-to-pause pattern) — https://github.com/itsnubix/react-native-video-controls/pull/126
- Appcues, "Onboarding UX: 10 patterns, best practices, and real examples" — https://www.appcues.com/blog/user-onboarding-ui-ux-patterns
- Appcues, "The essential guide to mobile user onboarding" — https://www.appcues.com/blog/essential-guide-mobile-user-onboarding-ui-ux
- Atlan, "Data Labeling for LLMs: Annotation Methods, Quality & Governance" — https://atlan.com/know/data-labeling-best-practices-llms/
- Keymakr, "Guide to LLM Data Annotation: Best Practices" — https://keymakr.com/blog/complete-guide-to-llm-data-annotation-best-practices-for-2025/
- arXiv 2507.15821, "Just Put a Human in the Loop? Investigating LLM-Assisted Annotation for Subjective Tasks" — https://arxiv.org/html/2507.15821v1
- CuratorKIT (arXiv 2606.21631), per-sample provenance chain pattern for LLM data curation — https://arxiv.org/pdf/2606.21631
- Medium (GovTech DSAID), "Validating Annotation Agreement between Humans and LLMs" (κ/α metrics context) — https://medium.com/dsaid-govtech/validating-annotation-agreement-between-humans-and-llms-bc334245b1d9

---
*Feature research for: BCF Visualization — Mobile UX + Autonomous Curation milestone*
*Researched: 2026-07-25*
