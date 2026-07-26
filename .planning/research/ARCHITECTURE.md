# Architecture Research

**Domain:** Brownfield mode-branched single-page vanilla-JS app (Workstream 1) + exemplar-driven LLM data-curation pipeline bolted onto an existing Python ETL DAG (Workstream 2)
**Researched:** 2026-07-25
**Confidence:** HIGH (both sections grounded in direct reads of `web/app.js`, `web/style.css`, `scripts/pipeline.py`, `scripts/derive_roll_facts.py`, `scripts/forge_curator/*`, `data/manual/chapter_roll_overrides.json`, and `design/mobile-ux/INTEGRATION_PLAN.md` / prototype source — not generic pattern recall). Industry framing for the LLM pipeline (confidence gating, idempotency) is MEDIUM — general web-sourced best practice, not domain-specific.

This project has two independent architecture questions. They're answered as two self-contained sections because they don't share components, data, or build order — Workstream 1 touches only `web/`, Workstream 2 touches only `scripts/` + `data/manual/`.

---

# Part A — Mode-branched mobile/desktop architecture (`web/app.js`)

## A.1 What the existing app already gives you for free

Before designing anything new, the two mechanisms that make "desktop provably cannot regress" *achievable* already exist in `app.js` and should be reused, not reinvented:

1. **Full-teardown structural render.** `render()` (app.js:873) does `clear(root)` then rebuilds the entire subtree from scratch every time it's called. There is no vdom diffing. This means: **any DOM node — and any listener attached to it via `el()`'s `on*` props (app.js:229-230) — is discarded and garbage-collected on the next structural render.** You never need to manually `removeEventListener` for per-render listeners; the browser does it when the node is detached. This is the load-bearing fact for the whole answer to "event listener lifecycle."
2. **A second, cheaper render tier.** `updatePlaybackFrame()` / `tickPlayback` (app.js:2551, 2524, the rAF loop at app.js:856-870) mutate cached DOM refs (`app.dom.*`) directly, at animation-frame frequency, **without calling `render()` and without touching `root`**. Full structural `render()` is reserved for discrete state transitions (data loaded, mode toggled, viewport class changed) — never called from the animation loop.
3. **Two listener lifetimes already coexist by design**, and mobile code must slot into the same taxonomy rather than invent a third:
   - **Module-scope, attach-once, never-detached** — `window.addEventListener("keydown"/"pagehide")`, `document.addEventListener("visibilitychange")` (app.js:2754-2782). Safe because they're attached exactly once at script load, outside any render cycle, and their handlers are idempotent/mode-checked internally.
   - **Delegated on a stable ancestor** — `document.body.addEventListener("click", …)` (app.js:2728) dispatches on `[data-action]` regardless of which render pass created the target node. This is how "hot" controls (play/pause, reset) survive structural re-renders without needing re-attachment.
   - **Per-node, re-attached every structural render** — everything wired via `el(tag, { onClick: fn })`. Cheap because `render()` already discards and rebuilds the whole tree; correctness comes from *always* being inside the render pass, never outside it.

## A.2 The one real risk: gesture handlers that outlive a render pass

The mobile prototype's `attachSkyGestures` / `attachRailScrub` (`design/mobile-ux/prototype/gestures.js`) are **not** delegated — they call `el.addEventListener("pointerdown"/"pointermove"/"pointerup"/"pointercancel", …)` directly on the sky/rail element and use `setPointerCapture`. They return an explicit teardown closure (the prototype is React and calls it from a `useEffect` cleanup — there is no React here, so nothing calls it today).

This is the one place the existing "attach inside render, let GC handle cleanup" convention breaks down, for two reasons specific to gestures (not applicable to plain click handlers):

- **Pointer capture is bound to the exact DOM node.** If a structural `render()` fires *while a finger is down* (mid-drag), the node holding the capture is removed from the document, the drag silently dies, and the user's thumb is now dragging nothing. Desktop has no analogous risk today because nothing calls `render()` mid-interaction — pointer/mouse drags on desktop use scroll-based scrub (`scrubberScroller.scrollLeft`), not pointer capture.
- **Window/rail-level listeners registered outside the render loop would leak.** The prototype's helpers attach to the *element itself*, not `window`/`document`, so they die correctly with the node under the existing full-teardown model — but only if you actually port them attached to the per-render element, not lifted to module scope "for efficiency." Don't hoist them.

**Prevention pattern (do this):**
- Call `attachSkyGestures(...)` / `attachRailScrub(...)` **inside** `renderMobilePortrait()` / `renderMobileLandscape()`, after the target element is appended to the tree in that same render pass — mirroring `cachePlaybackDomRefs()`, which already runs once per structural render (app.js:889). Store the returned teardown on `app.dom` (e.g. `app.dom.skyGestureTeardown`) purely as a defensive measure — the plan is for GC to handle it via full-teardown, but calling teardown explicitly before the next `render()` is one extra line and removes any doubt about pointer-capture edge cases.
- **Never call full `render()` from inside a gesture callback while `down`/drag state is active.** `onSwipeStep` / `onScrub` must write to `app.wordPos` and call the *incremental* update path (the mobile equivalent of `updatePlaybackFrame`), not `render()`. Reserve `render()` for gesture-*end* transitions (mode toggles, settings changes) and for the `resize`/`orientationchange`/`matchMedia` listener that flips `app.layoutMode`.
- The `resize`/`orientationchange` listener that triggers a layout-mode switch is itself a "module-scope, attach-once" listener (bucket 1 above) — add it once near the other `window.addEventListener` calls at the bottom of the file, guarded so a rapid resize burst doesn't call `render()` more than once per animation frame (debounce via `requestAnimationFrame`, matching the existing rAF discipline elsewhere in the file).

## A.3 State isolation: one `app` object, namespaced additions, no shared render path

The plan (§0.4, §3.1) already prescribes the correct pattern — this section is why it's correct, so it survives paraphrase during planning:

- **Single source of truth, new fields only.** `app.layoutMode`, `app.helpOpen`, `app.settingsOpen`, `app.infoOpen`, `app.chromeHidden`, `app.tapToPause`, `app.haptics` get added to the existing flat `app` object (app.js:88-121+), not a nested `app.mobile = {...}` sub-object. Reason: `app.wordPos`, `app.playing`, `app.speed`, `app.zoom`, `app.mode`, `app.rollLocation` are shared model state that both desktop and mobile read and write through the *same* existing setters (`setWordPos`, `setMode`, `setRollLocation` — explicitly called out as reusable in plan §3.1). A nested namespace would tempt someone into duplicating that state per-surface, which is the actual regression vector (state divergence, not code duplication). Isolation is achieved by **new render functions**, not new state containers.
- **Isolation lives at the `render()` dispatch, not deeper.** `render()` becomes: read `app.layoutMode` → call exactly one of `renderAppShell()` (existing, untouched) / `renderMobilePortrait()` (new) / `renderMobileLandscape()` (new). Nothing below that branch is shared. This matches the plan's explicit prohibition on extracting shared components (§0.1.3, §7) — and the architectural reason it's right, not just a style preference, is that `renderAppShell`'s children (`renderScrubber`, `renderCarousel`, `renderSkyCamera`, etc.) close over layout assumptions (pixel math, animation timing keyed to `app.frameKeys`) that a shared component would have to parameterize, and that parameterization surface is exactly where desktop regressions creep in silently.
- **Read-only surface enforcement.** The plan's §0.2 list of frozen `render*` functions is best treated as a literal lint boundary: a pre-commit/CI check (e.g., `git diff` against the frozen function bodies, or an AST check that the byte range of each named function is unchanged) is cheap to add and directly enforces "provably cannot regress" rather than relying on code review discipline alone. This is worth a phase-level acceptance criterion, not just a written rule.
- **CSS isolation mirrors JS isolation.** New rules live behind the existing breakpoint media query already in `web/style.css` (`@media (max-width: 900px), (orientation: portrait) and (max-width: 1100px)` at style.css:360 — currently scoping `.portrait-banner`, to be reused/extended, not reinvented). No existing rule or `:root` variable is edited; new mobile rules are additive-only, appended in a new block (optionally split into `web/mobile.css` per plan §3.5 once `style.css` gets unwieldy).

## A.4 Media-query-driven mode detection: JS must mirror CSS, not replace it

Two independent mechanisms need to agree on the same breakpoint, and the risk is drift between them:

1. **CSS** hides/shows chrome via the media query at style.css:360 (today gates `.portrait-banner`; after this work, gates the mobile-only rule block).
2. **JS** (`app.layoutMode`) decides *which render functions run at all* — CSS alone cannot do this because desktop and mobile render fundamentally different DOM trees (different components, not just different styling of the same tree).

**Pattern:** derive `app.layoutMode` from `window.matchMedia(...)` using **the exact same query string** as the CSS breakpoint, not a hand-rolled `innerWidth` check that could drift from the stylesheet:

```js
const MOBILE_MQ = window.matchMedia("(max-width: 900px), (orientation: portrait) and (max-width: 1100px)");
const PORTRAIT_MQ = window.matchMedia("(orientation: portrait)");

function detectLayoutMode() {
  if (!MOBILE_MQ.matches) return "desktop";
  return PORTRAIT_MQ.matches ? "portrait" : "landscape";
}
```

Subscribe via `MOBILE_MQ.addEventListener("change", onLayoutChange)` (and the portrait one, for in-place rotation while already mobile) rather than a generic `resize` listener — `matchMedia` change events fire only at the actual breakpoint crossing, which is both fewer spurious `render()` calls and a stronger guarantee that JS and CSS never disagree about which side of the breakpoint the viewport is on. Keep a `resize` listener too only if content reflow *within* a mode (e.g. scrubber pixel math) needs recomputation — route that through the incremental update path, not a structural `render()`.

**Anti-pattern to flag explicitly in planning:** duplicating the breakpoint numbers (900/1100) as separate constants in JS and CSS. Define them once (e.g. as a JS template literal injected... no — simplest robust option given this is a static site with no build step: keep the numbers in a single commented constant block in `app.js`, and add a code comment in `style.css` pointing at it, since there's no shared-constants mechanism between a static CSS file and JS without introducing a build step this project doesn't have. This is a known, accepted small duplication — call it out once in the plan so a future edit updates both sites deliberately instead of by accident.

## A.5 Component boundaries (Workstream 1)

| Component | Responsibility | Talks to |
|---|---|---|
| `render()` dispatcher | Reads `app.layoutMode`, calls exactly one top-level render function, resets `app.dom`/`app.frameKeys`/`app.carousel.visibleSlots` (existing behavior, untouched) | `renderAppShell` (frozen) / `renderMobilePortrait` (new) / `renderMobileLandscape` (new) |
| `renderAppShell` + frozen `render*` set | Desktop DOM tree | Shared model functions only (`setWordPos`, `chapterAtWord`, etc.) — never new mobile code |
| `renderMobilePortrait` / `renderMobileLandscape` | Mobile DOM trees (two, not one — no shared mobile base component either, per plan §7) | Same shared model functions; gesture attach helpers; new mobile-only render helpers (`renderMobileScrubber`, flyouts, etc.) |
| `web/mobile-gestures.js` (new file, loaded before `app.js`) | Pointer-event interpretation → semantic callbacks (`onTap`, `onSwipeStep`, `onScrubEnd`, …); no app-state knowledge | Called by mobile render functions; writes nothing directly to `app` |
| Shared model layer (`setWordPos`, `setMode`, `setRollLocation`, `chapterAtWord`, `recentRolls`, `cumulativeAt`, `formatWords`, `viz-model.js` exports) | Single computation of word-position/roll/CP domain quantities | Read by both desktop and mobile render paths — this is the *only* intentional sharing surface |
| `localStorage` (`bcf:*` namespace + `STORAGE_VERSION`) | Persisted prefs, versioned migration on bump | Read at init by `app` object literal; written by prefs helpers from either render path |
| `app.layoutMode` detection (matchMedia listeners) | Owns the desktop/portrait/landscape decision | Sets `app.layoutMode`, calls `render()` — the single point where mode changes propagate |

## A.6 Data flow (Workstream 1)

```
matchMedia change  ──┐
window resize (debounced, rAF-gated) ──┼──▶ app.layoutMode = "desktop"|"portrait"|"landscape" ──▶ render()
initial page load  ──┘

render()
  ├─ app.layoutMode === "desktop"   → renderAppShell()          (frozen path, byte-identical to pre-change)
  ├─ app.layoutMode === "portrait"  → renderMobilePortrait()    → attachSkyGestures/attachRailScrub on mount
  └─ app.layoutMode === "landscape" → renderMobileLandscape()   → attachSkyGestures/attachRailScrub on mount

user gesture (tap/swipe/drag) ──▶ mobile-gestures.js callback ──▶ setWordPos()/setMode()/etc. (SHARED setters)
                                                                        │
                                                          ┌─────────────┴─────────────┐
                                                          ▼                           ▼
                                            updatePlaybackFrame()          persistBookmarkSoon() → localStorage
                                            (incremental DOM mutation,
                                             desktop AND mobile both use
                                             this for hot-path updates —
                                             it doesn't touch `root`)
```

The key property this diagram is meant to make explicit: **gestures never call `render()` directly for continuous interaction** (drag/swipe-in-progress). They call the same shared setters desktop already calls from keyboard/click handlers, which is what guarantees mobile input can't desync from the model desktop also reads.

## A.7 Build order (Workstream 1)

This mirrors the plan's own phase order (§5) — restated here with the *dependency reasoning*, since that's what the roadmap needs:

1. **Phase A (state + gesture plumbing) must ship before any mobile render function exists.** `app.layoutMode` detection, new `LS_*` keys, `STORAGE_VERSION` bump, and the gesture-helper file are all *inputs* to Phase B/C render functions — building a mobile render function first would have nothing correct to branch on or attach to. Phase A's gate ("desktop unchanged; layoutMode flips correctly and survives rotation") is checkable with **zero new UI**, which is exactly why it should be the first milestone: it isolates "did we regress desktop" from "does the new UI work" as two separable questions.
2. **Phase B (Portrait) before Phase C (Landscape), not in parallel.** Both consume the same gesture helpers and the same shared model layer; building them in parallel risks two people converging on two different interpretations of "how do I attach gestures inside a render pass," which is the one nontrivial new pattern this workstream introduces. Sequencing lets Phase C reuse a *proven* attach/detach convention from Phase B instead of re-deriving it.
3. **Phase D (cutover: delete portrait banner) only after B+C both pass their gates**, because the portrait banner is the fallback behavior for any viewport the new code doesn't yet handle correctly — deleting it early removes the safety net.
4. **Phase E (a11y/polish) last**, because `aria-live` announcements and reduced-motion branches key off the same render/update call sites Phases B/C establish — adding them earlier means retrofitting every call site touched by B and C a second time.
5. **The §0.5 desktop smoke test runs at every phase gate, not once at the end** — this is a build-order implication, not just a QA note: it means each phase's "done" criteria must include a fast, repeatable desktop check, which argues for scripting §0.5 (even a manual checklist automated into a Playwright/Puppeteer smoke script) as part of Phase A rather than leaving it purely manual through Phase E.

## A.8 Anti-patterns to flag in the roadmap

- **Extracting a shared `renderFieldLog`-style component** between `renderNarrativeReadout` (desktop) and the landscape rail. The plan explicitly forbids this (§7) and the reason is architectural, not stylistic: the two surfaces have different scroll containers, different sizing assumptions, and (per §A.3 above) parameterizing a shared component to serve both is exactly the surface where a desktop-affecting change sneaks in disguised as a mobile fix. Read the same model (`fieldLogModel`), build two views.
- **Attaching gesture listeners at module scope "to avoid re-attaching every render."** This looks like an optimization and is actually the regression vector described in §A.2 — it breaks the "listener lifetime tied to node lifetime" invariant the whole app already relies on.
- **A generic `resize` listener as the sole mode-detection mechanism.** Drifts from the CSS breakpoint over time (see §A.4); use `matchMedia` with the identical query string.
- **A third "tablet" breakpoint or a nested `app.mobile` state namespace.** Both explicitly excluded by the plan (§7, §0.4) for reasons that hold up under scrutiny: a third breakpoint multiplies the render-branch surface for no design requirement, and a nested namespace tempts duplicate model state as noted in §A.3.

---

# Part B — Exemplar-driven LLM chapter-curation pipeline

## B.1 Where this slots into the existing DAG (don't build a parallel pipeline)

`scripts/pipeline.py:build_steps()` declares this exact stage order today:

```
parse_chapters → extract_chapter_sections → predict_rolls → find_text_backed_rolls
  → derive_roll_outcomes → derive_timeline → build_perk_directory → derive_outstanding_perks
  → derive_roll_facts → build_chapter_facts → derive_constellation_lifecycle
  → build_constellation_wireframes → build_visualization_facts → package_data_release → …
```

Two facts here decide the whole architecture of Workstream 2:

1. **`find_text_backed_rolls.py` already produces almost exactly the input a curation agent needs**: for every *predicted* roll, a prose window (±N words) centered on the predicted position, the regex anchors inside that window, and a coarse `evidence_kind` classification (`direct` / `general_only` / `forward_ref` / `no_evidence`) — output at `data/derived/roll_text_evidence.json`. This is the mechanical evidence-mining stage the question asks about ("mining exemplars... word-position validation") — **it exists**. The agent pipeline is a consumer of this artifact, not a reimplementation of it.
2. **`derive_roll_facts.py` already treats `chapter_roll_overrides.json` as fully authoritative** the moment a chapter has an entry (`_has_structural_roll_override`), and already has precedent for a boolean provenance-style flag (`curator_added`, app.js parity: `_is_metadata_only_roll_override` checks it) and a metadata-only vs. structural distinction. Adding agent-provenance is a **schema extension of an already-provenance-aware structure**, not a new concept.

**Therefore the agent curation pipeline is a new stage inserted between `find_text_backed_rolls` and `derive_roll_facts`** — call it `curate_chapters_agentic.py` in the pipeline stage list — that:
- reads `predicted_rolls.json`, `roll_text_evidence.json`, and the existing `chapter_roll_overrides.json` (both as the withheld-from-overwrite authoritative set *and* as the exemplar corpus),
- writes **only** to chapters absent from `chapter_roll_overrides.json`'s `chapter_roll_overrides` key,
- produces two outputs: high-confidence rows merged into `chapter_roll_overrides.json` under a new provenance marker, and low-confidence rows into a **separate** proposals file (`data/manual/agent_curation_proposals.json`) that the Forge Curator TUI reads as a new surface.

Running it downstream of `find_text_backed_rolls` but upstream of `derive_roll_facts` means the existing validated consumer (`derive_roll_facts` → `build_chapter_facts` → … → `visualization_facts.json`) needs **no new read path** for roll data — it already reads `chapter_roll_overrides.json` as one input. This is the direct application of the project's "no parallel implementations" constraint: the agent pipeline produces data in the *existing* schema/location, not a second data path `derive_roll_facts` (or anything downstream) has to learn to merge.

## B.2 Component boundaries (Workstream 2)

| Component | Responsibility | Reads | Writes |
|---|---|---|---|
| **Exemplar miner** (new, one-time + re-run on corpus growth) | Extract few-shot patterns from the 118 hand-curated chapters: evidence-quote phrasing conventions, roll-grouping (multi-grab) shapes, perk-link conventions, `display_position_policy` usage distribution | `chapter_roll_overrides.json` (curated subset only) | An exemplar index/cache (e.g. `data/manual/agent_curation_exemplars.json` or in-memory per run) — **not** a new corpus, a derived index over the existing one |
| **`find_text_backed_rolls.py`** (existing, reused unmodified) | Prose-window + regex-anchor evidence per predicted roll | EPUB, `predicted_rolls.json`, section classifications | `roll_text_evidence.json` (existing artifact) |
| **Per-chapter curation agent** (new) | For each chapter with no hand-curated entry: given predicted rolls + text evidence + retrieved exemplars, propose a roll list (perks, outcome, constellation, evidence_quotes, display_position_policy) matching the hand-curated schema exactly | `roll_text_evidence.json`, exemplar index, `perk_directory` (for name grounding) | In-memory / per-chapter proposal object |
| **Mechanical verifier** (new, but built from existing primitives) | Exact-quote match against actual prose (reuse `find_text_backed_rolls`'s prose-loading + the quote-matching logic pattern already in `scripts/forge_curator/miss_quote_matcher.py`); word-position validation against chapter word offsets; perk-name resolution via the existing ladder (`scripts/perk_name_resolver.py`: alias lookup → directory match index → fuzzy prefix match) | Chapter prose, `chapter_facts.json` word offsets, `perk_directory`, perk aliases | Pass/fail + failure-reason annotations on each proposed roll |
| **Confidence gate** (new) | Combine agent self-report + mechanical-verification pass/fail + `evidence_kind` from `roll_text_evidence.json` into accept/review buckets | Verifier output | Routes to overrides-writer or proposals-writer |
| **Overrides writer** (new) | Merge accepted (high-confidence) chapters into `chapter_roll_overrides.json` with a provenance marker; never touches chapters that already have a hand-curated entry | `chapter_roll_overrides.json` (read-modify-write), confidence-gate output | `chapter_roll_overrides.json` (updated) |
| **Proposals writer** (new) | Write low-confidence chapters to a sidecar file in the same roll-object schema plus rejection/uncertainty reasons | Confidence-gate output | `data/manual/agent_curation_proposals.json` |
| **Forge Curator TUI — proposals surface** (extension of existing `scripts/forge_curator/`) | Let Dre review/accept/edit/reject agent proposals chapter-by-chapter, same interaction model as hand curation today | `agent_curation_proposals.json` | `chapter_roll_overrides.json` (on accept — becomes hand-curated, same as today) |
| **`derive_roll_facts.py`** (existing, reused unmodified except for the provenance-field schema addition applied uniformly per the project's no-shims policy) | Build ground-truth roll facts from whichever source (hand-curated, agent-curated-accepted, or predicted-fallback) has authority for each chapter | `chapter_roll_overrides.json`, `predicted_rolls.json` | `roll_facts.json` |

## B.3 Data flow (Workstream 2)

```
                         ┌────────────────────────────┐
                         │ chapter_roll_overrides.json │  (118/195 hand-curated — EXEMPLAR CORPUS)
                         └──────────────┬─────────────┘
                                        │ mine
                                        ▼
                          exemplar index (evidence-quote patterns,
                          roll-shape patterns, perk-link conventions)
                                        │
predicted_rolls.json ──┐               │
                        ├──▶ find_text_backed_rolls.py (EXISTING, unmodified)
EPUB + section data ────┘               │
                                        ▼
                          roll_text_evidence.json (prose windows +
                          evidence_kind per predicted roll)
                                        │
                    (skip chapters already in chapter_roll_overrides.json)
                                        ▼
                       per-chapter curation agent  ◀── exemplar index
                                        │
                            proposed roll list (chapter schema)
                                        ▼
                       mechanical verifier: exact-quote match,
                       word-position validation, perk-name resolution
                       (reuses miss_quote_matcher.py pattern + perk_name_resolver.py)
                                        │
                              pass/fail + evidence_kind
                                        ▼
                                confidence gate
                        ┌───────────────┴────────────────┐
                        ▼ high confidence                ▼ low confidence
        chapter_roll_overrides.json                agent_curation_proposals.json
        (+ provenance marker,                              │
         chapter absent-only merge)                         ▼
                        │                          Forge Curator TUI
                        │                          (Dre reviews → accept)
                        │◀─────────────────────────────────┘
                        ▼
              derive_roll_facts.py (EXISTING, unmodified logic,
              schema-extended for provenance) → roll_facts.json
                        │
                        ▼
              …rest of pipeline (unchanged) → visualization_facts.json
```

## B.4 Build order (Workstream 2)

The dependency chain is stricter here than in Workstream 1 because each stage's *quality bar* depends on the previous stage's output being trustworthy — building out of order means re-tuning downstream thresholds every time an upstream stage changes.

1. **Epub refresh gate first** (already an Active requirement, listed before the confidence framework in PROJECT.md) — must run before anything else in this workstream, since chapter count and predicted-roll integrity are inputs to every later stage. Re-running `sync_private_source_repo.py` → `hydrate_source_epub.py` → `pipeline.py` and verifying counts is a hard precondition, not parallelizable with the rest.
2. **Exemplar mining second, standalone, no LLM calls yet.** This is pure analysis over the existing 118-chapter corpus (evidence-quote phrasing stats, roll-shape/multi-grab distribution, `display_position_policy` frequency, perk-link conventions) and can be fully built and validated before a single agent call exists. It's also the piece most likely to reveal that the "confidence framework" requirement (PROJECT.md Active) needs corpus-derived thresholds rather than guessed ones — build it early enough that its findings can shape the confidence-gate design in step 4, not retrofit it.
3. **Mechanical verifier third, before the agent.** Exact-quote match, word-position validation, and perk-name resolution are deterministic and don't need an LLM in the loop to build or test — they can be validated standalone against the *existing* hand-curated corpus (run the verifier against all 118 known-good chapters first; it should pass 100%, which both validates the verifier and gives a regression baseline before agent output ever touches it). Building this before the agent means agent output has a real bar to clear from its first run, not a stub.
4. **Per-chapter agent fourth**, now that it has (a) a real exemplar index to prompt/retrieve from, (b) a real verifier to score against, and (c) `roll_text_evidence.json`'s `evidence_kind` as a pre-filter (chapters classified `no_evidence` are a strong signal to route straight to low-confidence/proposals without spending an agent call, or route to a different agent strategy — cheap early-exit that step 2's data already supports).
5. **Confidence gate fifth**, tuned using real (agent output, verifier result) pairs from a small pilot batch — not designed in the abstract. This is where "what makes a curation high-confidence" (an explicit open Active requirement) gets an empirical answer instead of a guess: run the agent against a held-out slice of the *already hand-curated* 118 chapters (whose true answer is known), and tune the accept/review split against measured precision, not intuition.
6. **Overrides/proposals writers sixth** — mechanically simple once the gate exists; this is also where **idempotent re-run** design must be decided (see B.5) since it determines the writer's merge semantics.
7. **Pipeline wiring seventh** (insert as a `pipeline.py` stage between `find_text_backed_rolls` and `derive_roll_facts`, per B.1) plus the `derive_roll_facts.py` schema extension for the provenance field — done together in one change per the project's no-shims/full-rewrite policy (PROJECT.md constraints: schema changes touch every consumer in the same change).
8. **Forge Curator TUI proposals surface last** — depends on the proposals file schema being final (step 6) and is otherwise independent UI work layered on an existing, well-understood TUI codebase (`scripts/forge_curator/app.py`, 7.5K lines — the review surface is additive there, following whatever interaction pattern the existing hand-curation flow already uses).

## B.5 Confidence gating and idempotent re-runs

**Confidence signal composition** (informed by general industry pattern of multi-signal gating — MEDIUM confidence, general web best practice, not domain-specific — combined with the two domain-specific signals that already exist in this codebase, HIGH confidence):
- `evidence_kind` from `roll_text_evidence.json` (`direct` > `general_only` > `forward_ref` > `no_evidence`) — an existing, already-computed signal, free to use as a first-pass filter before spending any agent budget.
- Mechanical verifier pass/fail (exact quote found verbatim in prose at/near the claimed position; word position within tolerance; perk name resolves through the existing alias→directory→fuzzy ladder without falling to the fuzzy tier) — a **hard gate**, not a soft signal: any verification failure should force low-confidence regardless of what the agent claims about itself, mirroring the general pattern of routing schema/validation failures straight to human review regardless of model self-confidence.
- Agent self-reported confidence — useful as a tiebreaker but should never independently promote a mechanically-failed roll to high-confidence; self-report from a generative model is the least trustworthy of the three signals here and should be weighted last.

**Idempotency requirements**, given this pipeline will re-run repeatedly as the epub gets new chapters and as the exemplar corpus grows from 118 toward 195+:
- Key each per-chapter agent run by `(chapter_num, corpus_fingerprint)` where `corpus_fingerprint` is a hash of the hand-curated corpus subset used for exemplar retrieval (the existing `_fingerprint` field already present on override entries, e.g. `"sha256:614faef15c5b1c54"` seen on chapter 97, is direct precedent for this pattern in this codebase — reuse it rather than inventing a new fingerprinting scheme).
- Re-running the pipeline on an unchanged chapter with an unchanged corpus should be a no-op (skip, don't re-call the agent) — cache the accept/review decision keyed on that fingerprint, matching general LLM-pipeline idempotency guidance (cache the unit of work, not the raw API call).
- Re-running after the corpus grows (more hand-curated exemplars available) should be an explicit, opt-in re-curation pass, not automatic on every pipeline run — since the pipeline runs are relatively frequent (epub refreshes) and re-curation is comparatively expensive (LLM calls), the writer should distinguish "chapter never curated" (always process) from "chapter was low-confidence, corpus has since grown" (re-process only when explicitly requested) from "chapter was low-confidence, corpus unchanged" (skip, still cached as low-confidence).
- The overrides writer must **never overwrite an existing hand-curated entry** (explicit project constraint) and should treat its own prior agent-written entries as safely overwritable **only** by a fresh agent run with a higher-or-equal fingerprint — never by re-reading stale cached output. This is the concrete meaning of "idempotent" for the overrides file specifically: same inputs → same output written; changed inputs → deliberate re-derivation, not silent drift.

## B.6 Anti-patterns to flag in the roadmap

- **Reimplementing prose-window extraction or regex-anchor scanning inside the new agent stage.** `find_text_backed_rolls.py` already does this and is upstream in the DAG — call it, don't duplicate it. This is the direct "no parallel implementations" constraint applied to Workstream 2's most tempting shortcut.
- **A separate quote-verification implementation from the one `scripts/forge_curator/miss_quote_matcher.py` already contains.** Extract/share the matching primitives rather than writing new regex from scratch — same constraint, same reasoning.
- **Letting agent self-confidence alone gate acceptance.** The mechanical verifier (deterministic, testable against the 118 known-good chapters) must be a hard veto, not an input averaged against a soft LLM confidence score.
- **A second roll-data file format for agent output that isn't the existing roll-object schema.** Both `chapter_roll_overrides.json` entries and `agent_curation_proposals.json` entries should use the *identical* roll-object shape (`perks`, `outcome`, `constellation`, `word_position`, `evidence_quotes`, etc.) so that TUI-accept is a straight copy from proposals into overrides, not a transform.
- **Skipping the "run the verifier against the 118 known-good chapters first" validation step.** Without this baseline, there's no way to distinguish "the agent curated chapter 130 badly" from "the verifier has a bug" once real low-confidence output starts appearing.

## B.7 Integration points

| Boundary | Communication | Notes |
|---|---|---|
| Curation pipeline ↔ `derive_roll_facts.py` | File: `chapter_roll_overrides.json` (existing schema, extended with a provenance field applied to every consumer per no-shims policy) | This is the only integration surface into the validated part of the DAG — keep it that way |
| Curation pipeline ↔ Forge Curator TUI | File: `agent_curation_proposals.json` (new, same roll-object schema) | TUI is the human-in-the-loop for the low-confidence bucket; accept-path writes into `chapter_roll_overrides.json`, same file/schema hand curation already writes |
| Curation pipeline ↔ EPUB prose | Local filesystem read only, never committed/redistributed (copyright constraint) | Verifier and agent both need local prose access; neither may emit full passages beyond the existing evidence-quote convention (already how hand curation handles this) |
| Curation pipeline ↔ `perk_name_resolver.py` | Function-level import/call | Reuse the existing alias → directory-match → fuzzy-prefix ladder verbatim for perk-name resolution in the verifier |

## Sources

- Direct reads: `web/app.js`, `web/style.css`, `scripts/pipeline.py`, `scripts/derive_roll_facts.py`, `scripts/perk_name_resolver.py`, `scripts/find_text_backed_rolls.py`, `scripts/validate_roll_locations.py`, `scripts/forge_curator/miss_quote_matcher.py`, `scripts/forge_curator/quote_autofill.py`, `scripts/forge_curator/evidence_scorer.py`, `data/manual/chapter_roll_overrides.json`, `design/mobile-ux/INTEGRATION_PLAN.md`, `design/mobile-ux/prototype/gestures.js` — HIGH confidence, this project's own source of truth.
- [Lessons from Running an LLM Document Processing Pipeline in Production](https://medium.com/alan/lessons-from-running-an-llm-document-processing-pipeline-in-production-33d87f99cdb1) — confidence-threshold gating, validation-driven human-review routing. MEDIUM confidence (general industry practice, not domain-specific verification).
- [Idempotency Is Not Optional in LLM Pipelines](https://tianpan.co/blog/2026-04-20-idempotency-llm-pipelines) — scoping idempotency keys to the unit of work, not the raw API call. MEDIUM confidence.
- [Designing Fault-Tolerant AI Agent Pipelines: Idempotency, Retries, and State Management](https://mightybot.ai/blog/fault-tolerant-ai-agent-pipelines/) — checkpoint/resume and content-addressed run caching pattern, informed the fingerprint-keyed re-run design in B.5. MEDIUM confidence.
- [Reproducing Variance: Caching in Agentic LLM Pipelines (AI21)](https://www.ai21.com/blog/caching-in-agentic-llm-pipelines/) — cache-key design for multi-call agentic pipelines. MEDIUM confidence.

---
*Architecture research for: BCF Visualization — Mobile UX + Autonomous Curation milestone*
*Researched: 2026-07-25*
