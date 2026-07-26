# Project Research Summary

**Project:** BCF Visualization — Mobile UX Port + Autonomous LLM Chapter Curation
**Domain:** Brownfield, two-track milestone: (1) mobile touch/gesture UX port onto a frozen vanilla-JS desktop web app, (2) exemplar-driven LLM structured-extraction/curation pipeline bolted onto an existing Python ETL DAG
**Researched:** 2026-07-25
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a subsequent-milestone, additive research pass against an already-working system, not a green-field domain survey — both workstreams have real prior art to build on. Workstream 1 (mobile UX) already has a locked plan (`design/mobile-ux/INTEGRATION_PLAN.md`) and a working React prototype (`design/mobile-ux/prototype/gestures.js`); the job is porting native Pointer-Events gesture handling into the existing vanilla-JS `app.js` render loop without regressing the frozen desktop path, plus closing a handful of table-stakes gaps the plan doesn't yet name (`touch-action`/`overscroll-behavior` CSS, `dvh`/`svh` viewport units, safe-area insets, flyout focus-trapping, wake lock, visibilitychange pause). Workstream 2 (autonomous curation) has no locked plan yet — it inserts a new pipeline stage between `find_text_backed_rolls.py` and `derive_roll_facts.py` that uses the Anthropic Python SDK's Message Batches API + structured outputs + prompt caching to curate the ~77-80 remaining chapters, gated by a confidence framework mined from the 118-chapter hand-curated exemplar corpus.

The recommended approach for both tracks is conservative and reuse-heavy: no new frameworks, no build step, no parallel implementations. Workstream 1 reuses the app's existing render/state architecture (full-teardown structural `render()`, shared setters, `localStorage` versioning) and adds native browser APIs only (Pointer Events, `matchMedia`, `touch-action`, `dvh`/`svh`). Workstream 2 reuses existing pipeline primitives verbatim — `find_text_backed_rolls.py`'s prose-window extraction, `miss_quote_matcher.py`'s quote-matching, `perk_name_resolver.py`'s resolution ladder — rather than building a second, competing implementation of any of them.

The key risks cluster around two failure modes, one per workstream. For mobile UX, the dominant risk is state/lifecycle bugs where mobile-only side effects (gesture listeners, layout-mode side effects) leak into code paths that also run on desktop, or where gesture listeners double-bind across the app's re-render loop (a React-prototype assumption — `useEffect` cleanup — that doesn't hold in vanilla re-render semantics). Mitigation: strict phase sequencing (state/gesture plumbing before any mobile render function exists), an explicit attach/detach contract, and a desktop smoke test re-run at every phase gate, not once at the end. For LLM curation, the dominant risk is silent corpus contamination: an LLM that computes its own word positions, paraphrases "verbatim" quotes, or self-reports miscalibrated confidence (especially across the story's mid-chapter CP-regime transitions) can write plausible-but-wrong data into the trusted `chapter_roll_overrides.json`. Mitigation: never let the LLM compute values with an existing deterministic source of truth (word positions, roll ordinals); exact-only quote verification (never fuzzy); and a confidence gate built from structural/mechanical signals (verifier pass/fail, regime-transition adjacency) rather than model self-report alone.

## Key Findings

### Recommended Stack

No new frameworks or libraries for either workstream. Workstream 1 (mobile UX) uses native browser APIs exclusively — Pointer Events, `touch-action` CSS, `matchMedia`, `navigator.vibrate` (feature-detected, iOS-silent), and the existing `localStorage`/`STORAGE_VERSION` migration pattern already implemented in `app.js`. Workstream 2 (curation pipeline) uses the official `anthropic` Python SDK against `claude-opus-5` (initial calibration pass) or `claude-sonnet-5` (validated bulk pass), driven through the Message Batches API (50% cost savings, purpose-built for ~80 independent offline requests) with prompt caching on the shared exemplar/instruction prefix, and structured outputs (`output_config.format`) to guarantee schema-exact roll extraction.

**Core technologies:**
- Pointer Events + `touch-action` CSS (native) — unified touch/mouse/pen gesture input without a gesture library; already the correct choice validated against the existing prototype
- `window.matchMedia` (not `screen.orientation`) — reliable, CSS-synchronized orientation/breakpoint detection
- `anthropic` Python SDK + Message Batches API — cost-efficient, purpose-built batch processing for the ~80-chapter curation pass
- Structured outputs (`output_config.format`) + prompt caching — schema-guaranteed extraction output, reusing a cached exemplar/instruction prefix across all chapter requests
- Custom exact/normalized-substring quote verification (no fuzzy-matching library) — the sole acceptable gate for evidence-quote trust

### Expected Features

**Must have (table stakes):**
- Workstream 1: `touch-action`/`overscroll-behavior` CSS on gesture surfaces; pause on `document.visibilitychange`; `dvh`/`svh` viewport units; `env(safe-area-inset-*)` in dock/rail CSS; focus-trap + `role="dialog"` on flyouts; back-button handling for open overlays; Screen Wake Lock during playback — all gaps in the otherwise-locked `INTEGRATION_PLAN.md`
- Workstream 2: provenance marker per curated entry (human vs. agent + version); confidence score/threshold routing high→overrides, low→proposals; review queue in the existing Forge Curator TUI; validation-harness reuse (never a second validator); never-overwrite guarantee for hand-curated chapters; idempotent re-runs as the epub grows

**Should have (differentiators, already-planned or worth adding):**
- Scrubber cluster-binning at all zoom levels (already planned)
- Landscape cinema-scrub auto-hide two-stage reveal/pause (already planned)
- Confidence-framework versioning tagged per entry (WS2)
- Simple per-batch calibration summary (WS2)

**Defer (v2+):**
- Deep-link/shareable URL fragment to word position, PWA manifest (WS1)
- Pinch-to-zoom, long-press preview, throw inertia, real constellation rendering — already deferred by the locked plan (WS1)
- Token/cost tracking dashboard, agent rationale/self-critique notes (WS2)
- Formal inter-annotator agreement metrics, multi-model ensemble voting, dedicated annotation platform, continuous CI regression dashboard — explicit anti-features for a single-maintainer, single-ground-truth-curator project (WS2)

### Architecture Approach

Both workstreams graft onto existing architecture rather than introducing new structural patterns. Workstream 1 branches `render()` on a new `app.layoutMode` field (desktop/portrait/landscape), calling exactly one of the frozen `renderAppShell()` or new `renderMobilePortrait()`/`renderMobileLandscape()` — with all shared domain state (`app.wordPos`, `setWordPos`, etc.) flowing through the same existing setters both surfaces already use, so isolation lives at the render-dispatch level, not in a duplicated state container. Workstream 2 inserts one new pipeline stage (`curate_chapters_agentic.py`) between `find_text_backed_rolls.py` and `derive_roll_facts.py`, consuming the already-computed `roll_text_evidence.json` (prose windows + evidence classification) and writing into the existing `chapter_roll_overrides.json` schema (extended with a provenance field) or a new sidecar proposals file — no new read path is needed downstream.

**Major components:**
1. `render()` dispatcher + `mobile-gestures.js` — layout-mode branching and Pointer-Events-to-semantic-callback translation, decoupled from app state
2. Shared model layer (`setWordPos`, `chapterAtWord`, etc.) — the single, intentional sharing surface between desktop and mobile render paths
3. Exemplar miner + mechanical verifier (exact-quote match, word-position lookup via the pipeline's own tokenizer, perk-name resolution) — deterministic components built and validated against the 118 known-good chapters before any agent call exists
4. Confidence gate — routes agent output to `chapter_roll_overrides.json` (with provenance) or `agent_curation_proposals.json`, using structural/mechanical signals as the hard gate and model self-report only as a tiebreaker
5. Forge Curator TUI proposals surface — extends the existing review tool rather than building a second UI

### Critical Pitfalls

1. **Gesture listeners double-binding across the vanilla re-render loop** (a React-`useEffect`-cleanup assumption that doesn't hold here) — a single swipe can fire the roll-step handler multiple times. Avoid by deciding the render loop's node-identity model up front and pairing every gesture attach with explicit teardown or attach-once guarding.
2. **Mobile-only side effects leaking into pre-render layout-mode detection code**, which then also fires on desktop. Avoid by confining all mobile-only side effects to inside `renderMobilePortrait`/`renderMobileLandscape`, never in the `resize`/`orientationchange` handler itself.
3. **iOS Safari's `100vh` dynamic-toolbar behavior and `resize`/`orientationchange` timing races** — both invisible in Chrome DevTools emulation, both requiring real-device verification and `svh` units + rAF-debounced layout recompute.
4. **LLM-computed word positions and paraphrased "verbatim" quotes silently polluting the trusted corpus** — the single highest-stakes pitfall for Workstream 2. Avoid by never letting the LLM emit `mention_word_position` or `source_ordinal` (compute deterministically via the pipeline's existing tokenizer/predictor-mapping code) and by exact-substring-only quote verification, never fuzzy matching.
5. **Confidence miscalibration concentrated at CP-regime transitions** — the model is most confident exactly where exemplar density is lowest (post-transition chapters). Avoid by tagging exemplars with regime metadata, constraining retrieval to same-regime exemplars, and forcing low confidence when a target chapter straddles or follows a `regime_transitions.json` boundary.

## Implications for Roadmap

Based on research, suggested phase structure (two independent tracks — order between tracks is flexible, but each track's internal order is dependency-driven):

### Track A: Mobile UX Port

### Phase A1: State & Gesture Plumbing
**Rationale:** `app.layoutMode` detection, new `LS_*` keys, `STORAGE_VERSION` bump, and the `mobile-gestures.js` attach/detach contract are inputs every later mobile render function depends on; this phase is checkable with zero new UI, isolating "did we regress desktop" from "does new UI work."
**Delivers:** Layout-mode detection (`matchMedia`, debounced via rAF), gesture-helper file ported with an explicit attach/detach contract, viewport meta / `touch-action` / `svh` decisions made, visibilitychange-pause resolved and added to acceptance checklist.
**Addresses:** Table-stakes gaps: `touch-action`/`overscroll-behavior`, `dvh`/`svh`, `visibilitychange` pause, `user-scalable=no` a11y tension (resolved early via Lighthouse run).
**Avoids:** Pitfalls 1, 2, 3, 5, 6 — all explicitly flagged as needing Phase-A-level architectural decisions, not late fixes.

### Phase A2: Portrait Layout
**Rationale:** Builds on the proven Phase A1 attach/detach convention before Landscape has to reuse it; sequencing avoids two independently-invented interpretations of the one nontrivial new pattern.
**Delivers:** `renderMobilePortrait()`, mobile scrubber with cluster-binning, safe-area-inset consumption, flyout focus-trap + back-button handling built alongside the flyouts themselves (not deferred to polish).
**Uses:** Pointer Events, `touch-action`, shared model setters.
**Implements:** `renderMobilePortrait` component boundary per architecture research.

### Phase A3: Landscape Layout
**Rationale:** Reuses the Phase A2-proven gesture/attach pattern; rotation mid-playthrough is the explicit acceptance gate here and is where the `resize`/`orientationchange` race (Pitfall 3) must be verified on a real device.
**Delivers:** `renderMobileLandscape()`, cinema-scrub auto-hide two-stage reveal/pause, Screen Wake Lock.
**Addresses:** Landscape-specific differentiator (auto-hide) and the `100vh`/toolbar CSS pitfall's Phase-C acceptance gate.

### Phase A4: Cutover & A11y Polish
**Rationale:** Only safe once Portrait+Landscape both pass their gates (portrait banner is the fallback safety net until then); a11y work keys off render/update call sites established in A2/A3.
**Delivers:** Portrait-banner deletion, `aria-live`, keyboard equivalents, `prefers-reduced-motion` timing (not just animation curves), final Lighthouse a11y ≥ 90 verification.
**Avoids:** Lighthouse regressions discovered only at the end (config decisions from Phase A1 must be re-verified here, not first-verified here).

### Track B: Autonomous Curation Pipeline

### Phase B1: Epub Refresh & Exemplar Mining
**Rationale:** Hard precondition — chapter count and predicted-roll integrity must be current before anything downstream; exemplar mining is pure analysis over the existing 118-chapter corpus, needs no LLM calls, and its findings shape the confidence-gate design in B3.
**Delivers:** Refreshed epub/pipeline outputs; regime-tagged exemplar index (evidence-quote patterns, roll-shape distribution, perk-link conventions) built from `chapter_roll_overrides.json`.
**Avoids:** Pitfall 10 (exemplar overfitting) — regime tagging must exist before retrieval logic is built, not retrofitted.

### Phase B2: Mechanical Verifier
**Rationale:** Deterministic, buildable/testable without any LLM in the loop — validated against all 118 known-good chapters first (should pass 100%), giving agent output a real bar to clear from its first run.
**Delivers:** Exact/normalized-substring quote verification (reusing `miss_quote_matcher.py`), word-position lookup via the pipeline's existing tokenizer (never LLM-computed), perk-name resolution via `perk_name_resolver.py`.
**Avoids:** Pitfalls 7, 8, 11 — the core "never let the LLM compute a value with a deterministic source of truth" architectural rule.

### Phase B3: Confidence Framework & Agent Curation Pipeline
**Rationale:** The provenance-marker schema change is the true root dependency for this workstream — routing, review queue, never-overwrite enforcement, and idempotent reruns all need it. Confidence gating must be structurally grounded (verifier pass/fail + regime adjacency), tuned against a pilot batch on the known 118 chapters, before running on the 77 uncurated ones.
**Delivers:** Provenance-marker schema extension (full rewrite across `derive_roll_facts`, TUI, validators per no-shims policy); per-chapter curation agent using Message Batches API + structured outputs + prompt caching; confidence gate; overrides/proposals writers with idempotent, fingerprint-keyed re-run semantics.
**Avoids:** Pitfall 9 (confidence miscalibration) — regime-transition-adjacent chapters must show measurably lower high-confidence rates as a build-time diagnostic.

### Phase B4: Forge Curator TUI Review Surface
**Rationale:** Depends on the finalized proposals-file schema from B3; otherwise independent UI work layered on an existing, well-understood TUI codebase.
**Delivers:** Proposal review/accept/edit/reject flow in the existing Forge Curator TUI, reusing its interaction model rather than building a second review surface.

### Phase Ordering Rationale

- Both tracks are independent (different files, different data) and can proceed in either relative order or in parallel; internal ordering within each track is strict due to genuine dependency chains, not just convention.
- Track A's order follows the plan's own phase structure (§5) — state/gesture plumbing must exist before any mobile render function has something correct to branch on or attach to; portrait before landscape lets landscape reuse a proven attach/detach convention.
- Track B's order is stricter because each stage's quality bar depends on the previous stage's output being trustworthy — building the confidence gate before the verifier exists, for instance, would mean re-tuning thresholds every time the verifier changes.
- In both tracks, the "cheap to fix early, expensive to retrofit" gaps (CSS units/safe-area in A1; provenance schema in B3) are deliberately pulled forward rather than left as end-of-track polish.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase A2/A3 (Portrait/Landscape):** Real-device iOS Safari behavior (toolbar animation, `orientationchange` timing) is not reliably reproducible in emulation — planning should budget for real-device verification loops, not just code review.
- **Phase B3 (Confidence Framework & Agent Pipeline):** No external domain-specific precedent for this exact regime-aware, single-maintainer confidence-gating shape — the confidence rubric must be empirically derived from a pilot batch against the known 118 chapters, which is itself a research/calibration activity, not a fixed spec to implement.

Phases with standard patterns (skip research-phase):
- **Phase A1 (State & Gesture Plumbing):** Native browser APIs already fully documented and prototyped; no open design questions beyond what's covered here.
- **Phase A4 (Cutover & A11y Polish):** Standard WCAG/WAI media-player patterns, already spec-cited.
- **Phase B1/B2 (Exemplar Mining, Mechanical Verifier):** Deterministic, reuses existing codebase primitives (`find_text_backed_rolls.py`, `miss_quote_matcher.py`, `perk_name_resolver.py`) verbatim — no new research surface.
- **Phase B4 (TUI Review Surface):** Extends an existing, well-understood 7.5K-line TUI codebase with a known interaction pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Web platform APIs cross-checked against MDN/caniuse; Claude API patterns from Anthropic's own bundled skill docs (vendor-authoritative, HIGH within that scope) |
| Features | MEDIUM | A11y/spec-backed items (WCAG, WAI media player pattern) are HIGH; general mobile-gesture/HITL-pipeline best-practice synthesis is MEDIUM (cross-referenced but not single-canonical-source) |
| Architecture | HIGH | Grounded in direct reads of `web/app.js`, `scripts/pipeline.py`, `scripts/derive_roll_facts.py`, `scripts/forge_curator/*`, and the integration plan — not generic pattern recall; industry framing for LLM-pipeline idempotency/gating is MEDIUM |
| Pitfalls | HIGH (mobile/CSS/DOM); HIGH (LLM extraction, verified against this repo's own tokenizer code); MEDIUM (regime-transition/exemplar-overfitting specifics — inferred from `regime_transitions.json`, not an external case study of this exact failure) |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Workstream 1:** No dedicated primary-source guidance was found specifically on "first-run help overlay for a media/timeline app" (vs. generic app onboarding) — the plan's existing design is trusted as-is; validate via the fresh-perspective review gate rather than further research.
- **Workstream 2:** The confidence-framework rubric (what mechanical/structural signal combination actually produces well-calibrated high/low routing) cannot be fully specified before the exemplar-mining and verifier phases produce real data — treat Phase B3's confidence-gate design as a calibration activity with a pilot-batch checkpoint, not a fixed upfront spec.
- **Both tracks:** Real-iOS-Safari-device testing capacity/access wasn't addressed in research and should be confirmed as a practical planning input before Phase A2/A3 gates are set.

## Sources

### Primary (HIGH confidence)
- Direct codebase reads: `web/app.js`, `web/style.css`, `scripts/pipeline.py`, `scripts/derive_roll_facts.py`, `scripts/perk_name_resolver.py`, `scripts/find_text_backed_rolls.py`, `scripts/forge_curator/*`, `data/manual/chapter_roll_overrides.json`, `data/manual/regime_transitions.json`
- `design/mobile-ux/INTEGRATION_PLAN.md` and `design/mobile-ux/prototype/gestures.js` (locked plan + working prototype)
- `.planning/PROJECT.md` (Workstream 2 requirements and constraints)
- Anthropic `claude-api` bundled skill documentation (Batches API, structured outputs, prompt caching, model recommendations) — vendor-authoritative

### Secondary (MEDIUM confidence)
- W3C WAI "Media Players" pattern, WCAG 2.5.8/1.4.4 implementation guides — a11y baseline citations
- WebSearch corroboration on Pointer Events vs. Touch Events, `touch-action`, `navigator.vibrate` iOS support (caniuse/MDN-adjacent, cross-referenced)
- iOS Safari `100vh`/`dvh`/`svh` dynamic-toolbar behavior articles (multiple independent, converging sources)
- LLM structured-extraction hallucination/grounding literature (arXiv, industry blog posts on idempotent/fault-tolerant agentic pipelines)

### Tertiary (LOW confidence)
- None retained without corroboration — sources with single-source, uncorroborated claims were explicitly excluded rather than reported (e.g., one uncorroborated GitHub issue on vibration API was flagged and discounted).

---
*Research completed: 2026-07-25*
*Ready for roadmap: yes*
