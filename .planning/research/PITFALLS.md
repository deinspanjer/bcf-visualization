# Pitfalls Research

**Domain:** Mobile web UX port onto a frozen vanilla-JS desktop app + autonomous LLM extraction/curation over long literary text
**Researched:** 2026-07-25
**Confidence:** HIGH (mobile/CSS/DOM pitfalls — verified against current browser behavior and this repo's own code); HIGH (LLM extraction pitfalls — verified against this repo's own tokenizer/anchoring code and current grounding-technique literature); MEDIUM (regime-transition/exemplar-overfitting specifics — inferred from `data/manual/regime_transitions.json` and project docs, not from an external case study of this exact failure mode)

## Critical Pitfalls

### Pitfall 1: The `render()` branch point isn't actually the *first* thing that runs

**What goes wrong:**
Plan §0.1.4 says `render()` "first thing... reads `app.layoutMode`." In practice, `app.layoutMode` gets set somewhere *before* `render()` (on init, on `resize`, on `orientationchange`), and it's easy to let a mobile-only side effect — attaching gesture listeners, opening the help overlay, mutating `app.chromeHidden` — run unconditionally in that pre-render code path, which then also fires on desktop. The regression isn't in `render()` itself; it's in the state-mutation code that decides *what to pass into* `render()`.

**Why it happens:**
The plan's mental model is "one branch point," but there are really two: (1) where `app.layoutMode` gets computed (resize/orientationchange handlers, init), and (2) where `render()` dispatches on it. Bugs cluster at (1) because that's new code with no existing desktop call sites to accidentally collide with — it feels "safe" to add logic there.

**How to avoid:**
Put every mobile-only side effect (gesture attach/detach, help auto-open, chrome-hide timers) *inside* `renderMobilePortrait`/`renderMobileLandscape`, never in the `resize`/`orientationchange` handler itself. The handler's only job is to recompute `app.layoutMode` and call `render()`; treat it as no different from the desktop resize path that already exists.

**Warning signs:**
Desktop-viewport smoke test (§0.5) passes on load but fails only after a resize-then-back-up cycle, or after the tab was briefly narrow and widened again. Gesture listeners firing on desktop after a resize round-trip.

**Phase to address:** Phase A (gesture + state plumbing) — write the resize/orientationchange handler test (§0.5 step 5–6) before Phase B adds real mobile rendering, so the discipline is established while there's nothing mobile-specific to blame the failure on.

---

### Pitfall 2: Double-bound gesture listeners across re-renders (React-prototype assumption leaking into vanilla re-render loop)

**What goes wrong:**
The prototype is React; `attachSkyGestures`/`attachRailScrub` were designed assuming a `useEffect` cleanup contract — attach on mount, detach on unmount, React guarantees it runs once per commit. Ported verbatim into a vanilla `render()` that runs on every state change (this app re-renders on every `resize`, every playhead tick during playthrough, every roll), the same DOM node can get `attachSkyGestures` called on it repeatedly without a matching detach, or the render can create a *new* DOM node each time while never removing the listener from the *old* one (leak) — or worse, `render()` reuses the same node (e.g., via `innerHTML` diffing that preserves the element) and each call adds another `addEventListener`, so a single swipe now fires the roll-step handler 2×, 3×, N× depending on how many renders happened since the sky node was created.

**Why it happens:**
Vanilla apps that re-render by rebuilding DOM subtrees (which is what `app.js`'s `el()`-based render appears to do, given the plan's language about "renders" and "remount") don't get React's automatic effect cleanup. The plan's own gate for Phase C — "rotating mid-playthrough swaps layouts without remounting state" — is explicit that they *want* to avoid remounting for state-preservation reasons, which directly increases the risk that the same DOM node persists across renders and accumulates listeners.

**How to avoid:**
Every `attachSkyGestures`/`attachRailScrub` call site needs a paired teardown, called either (a) once per node identity — track "already attached" via a WeakSet or a data attribute and skip re-attaching, or (b) explicitly detach-then-reattach on every render if node identity isn't stable. Decide *which* of these two models the render loop actually uses (stable nodes vs. rebuilt-per-render) before porting the gesture code — don't assume.

**Warning signs:**
A single swipe advances more than 1 roll per 56px (violates the acceptance criterion directly); haptic pulses fire multiple times per swipe; the issue only appears after the app has been running a while (more renders = more accumulated listeners), which makes it easy to miss in a quick manual test but guaranteed to surface in the §6 gesture checklist if that checklist is run after some playthrough time, not immediately on load.

**Phase to address:** Phase A (port `mobile-gestures.js`) for the attach/detach contract design; verify at Phase B gate with an explicit "swipe after 2 minutes of playthrough" test, not just "swipe immediately after load."

---

### Pitfall 3: `resize` and `orientationchange` race — layout mode flaps mid-transition on real iOS devices

**What goes wrong:**
On iOS Safari, rotating the device fires `orientationchange` *before* `window.innerWidth`/`innerHeight` have updated to the new values (this has been true across iOS versions with varying severity; some versions still read the pre-rotation dimensions inside the `orientationchange` handler itself, correcting only on a subsequent `resize`). A layout-mode detector that reads `matchMedia` or `innerWidth` synchronously inside the `orientationchange` handler can briefly compute the *wrong* `app.layoutMode` (e.g., stays "portrait" for one frame after rotating to landscape), causing the Phase C acceptance gate ("rotating mid-playthrough swaps layouts without remounting state") to visibly flash the old layout or, worse, mount the new layout with stale dimension-dependent values (e.g., cluster-binning pixel math computed against the old width).

**Why it happens:**
Two separate browser events (`orientationchange`, `resize`) can fire in either order and with different timing across iOS/Android/desktop-devtools-emulation, and neither is guaranteed to reflect final layout dimensions at fire time.

**How to avoid:**
Debounce: on both `resize` and `orientationchange`, schedule the layout-mode recompute on the next animation frame (`requestAnimationFrame`) rather than synchronously, and re-check dimensions once more after a short delay (~100ms) to catch the iOS Safari late-settle case. Don't trust the first `resize`/`orientationchange` firing after rotation to have final numbers.

**Warning signs:**
Cluster-binning or dock sizing looks correct on desktop-devtools device emulation (which fires clean resize events) but is subtly wrong only on a real phone; a one-frame flash of the wrong layout visible only when screen-recording a real-device rotation, invisible in a quick manual glance.

**Phase to address:** Phase C (landscape rotation is explicitly the acceptance gate for this) — but the debounce should be built once in Phase A's orientation-detection code so Phase B doesn't need it fixed twice.

---

### Pitfall 4: `100vh` / dynamic toolbar on iOS Safari breaks the "sky takes ~60%/~75% of viewport" acceptance criteria

**What goes wrong:**
iOS Safari's address bar and bottom toolbar dynamically show/hide as the user scrolls, and `100vh` is computed against the *largest* possible viewport (toolbars hidden), not the currently-visible one. A layout built with `height: 60vh` for the sky and the remainder for the dock will be taller than the actually-visible viewport whenever the toolbar is showing, pushing the dock partially off-screen — directly violating the "mini-rail dock always visible at bottom" and "top chips do not overlap the sky's focal label" acceptance criteria in §6, and doing so *only* on real iOS Safari, not in desktop-browser device emulation (which doesn't simulate the dynamic toolbar).

**Why it happens:**
This is a well-documented, still-live iOS Safari behavior. The fix (`dvh`/`svh` units) is real but has a rougher edge: `100dvh` reflows the layout *as the toolbar animates*, which can look janky for a full-bleed layout like this app's sky viewport (elements visibly resizing during a scroll-triggered toolbar transition).

**How to avoid:**
Use `100svh` (small viewport height — assumes toolbar always visible) for the outer app shell, not `100dvh`, since this app has no scrollable body content that would trigger the toolbar to hide/show — it's a fixed, gesture-driven, non-scrolling UI. `svh` avoids the reflow-during-scroll problem because there's nothing to scroll. Confirm this assumption holds once gestures are wired (a rail-drag or sky-swipe must not be interpretable by iOS as a page scroll, which would reintroduce toolbar animation — this needs `touch-action: none` or equivalent on the gesture surfaces, verified on-device). Fall back to a JS-computed `--vh` custom property only if `svh` support must be dropped for some target browser (unlikely to be needed; `svh`/`dvh` have been broadly supported since iOS 15.4/2022).

**Warning signs:**
Layout matches spec exactly in Chrome DevTools device emulation and fails only on a real iPhone; dock partially clipped at the bottom when the toolbar happens to be expanded (e.g., right after a page load, before any scroll/gesture).

**Phase to address:** Phase B (Portrait C) and Phase C (Landscape F) — this is a CSS unit choice made when the layout rules are first written; retrofitting is a full CSS block rewrite, not a small fix. Verify on a real iOS device, not only simulator/emulation, before the Phase B/C gate is signed off.

---

### Pitfall 5: `user-scalable=no` breaks accessibility even though the plan states it's needed for gesture-vs-page-zoom disambiguation

**What goes wrong:**
§3.3 sets `maximum-scale=1, user-scalable=no` on the viewport meta tag. This is a WCAG 2.1 SC 1.4.4 (Resize Text) / SC 1.4.10 (Reflow) failure mode: it disables the browser's native pinch-to-zoom for *all* users, including low-vision users who rely on OS-level pinch zoom rather than an app-provided zoom control. The plan's own §6 acceptance requires "Lighthouse Accessibility ≥ 90," and disabling pinch-zoom is a common Lighthouse a11y flag (`meta-viewport` audit) — this is a direct, known collision between two requirements in the same document (§1 wants `user-scalable=no` for gesture disambiguation, §6 wants a11y ≥ 90).

**Why it happens:**
Disabling page pinch-zoom is the simplest way to stop the browser from interpreting a two-finger gesture as native zoom instead of an app gesture, so it's an easy first reach — but it's a page-wide, permanent disable, not a scoped one.

**How to avoid:**
Since v1 explicitly defers pinch-zoom-as-app-gesture to v2 (§1, §8), there's no two-finger app gesture in v1 that needs disambiguating from native pinch zoom yet. Reconsider dropping `user-scalable=no` entirely for v1 and re-add it (scoped, if possible, via `touch-action: pan-x pan-y` on specific gesture surfaces rather than the viewport meta) only when v2 pinch-zoom is actually implemented. If `user-scalable=no` must stay for some other reason (e.g., preventing accidental double-tap-zoom colliding with the double-tap-live-edge gesture), that's a *different*, narrower problem — solvable with `touch-action: manipulation` on tap targets — not a page-wide zoom lock.
Run the actual Lighthouse mobile a11y audit early (Phase A, not Phase E) specifically on the `meta-viewport` rule, since this is a one-line config decision that's cheap to get right early and expensive to notice only at the Phase E gate after everything else has been tuned around the assumption.

**Warning signs:**
Lighthouse a11y score stuck below 90 with a `meta-viewport` violation called out explicitly; the score doesn't move no matter what other a11y work (aria-live, keyboard nav) is done in Phase E, because this one config line caps it.

**Phase to address:** Phase A (viewport meta is set then) — but *validate* at Phase E gate with an actual Lighthouse run, since Phase A has no visual UI yet to motivate re-checking it.

---

### Pitfall 6: `document.visibilitychange` autoplay-pause is listed as "strongly recommended, spec doesn't say" (§9) — shipping without it is a silent desktop-parity trap

**What goes wrong:**
§9 flags this as an open question the implementing agent should resolve with the design author, but if it's skipped (easy to do — it's not in §6's acceptance checklist at all), the mobile playthrough clock keeps advancing while the tab/app is backgrounded (phone locked, app switched). On resume, the user is dropped many rolls past where the sky cinematic last fired, which reads as "rolls got skipped" — a correctness-adjacent bug, not just a UX nit, because it can make it look like the roll-scrubber and the actual displayed state have desynced.

**Why it happens:**
It's explicitly called out as unresolved in the plan (§9), and unresolved-but-not-blocking items are the ones most likely to get silently dropped once phase-gate pressure is on acceptance-checklist items only (§6 doesn't mention it).

**How to avoid:**
Resolve this at the upfront interview gate (PROJECT.md already flags it as one of the three §9 questions to answer before coding starts) and, once resolved, add an explicit line item to §6's acceptance checklist so it isn't silently droppable later. Given the "strongly recommend yes" framing, implement: pause playthrough (not just visually — stop the position-advancing timer) on `visibilitychange` when `document.hidden`, and do not auto-resume on visible (respect existing pause state) unless that's also explicitly decided.

**Warning signs:**
QA report of "rolls jumped forward" after backgrounding the app; no test in the acceptance checklist ever exercises backgrounding, so this can ship silently.

**Phase to address:** Resolve at the pre-Phase-A interview gate (per PROJECT.md); implement in Phase A or B wherever the playthrough timer lives; add to §6 checklist explicitly so Phase D/E gates catch a regression.

---

### Pitfall 7: LLM word-position anchoring drifts from the pipeline's exact tokenizer, producing plausible-looking but silently wrong `mention_word_position` values

**What goes wrong:**
The existing hand-curated schema's `evidence_quotes[].mention_word_position` is defined against one specific tokenizer: `_split_sections + _strip_to_spaces` from `extract_chapter_sections.py`, counting "the Nth non-whitespace token" over CP-earning words only (per `find_text_backed_rolls.py`'s own `_method` documentation). An LLM asked to "find the word position of this quote" has no access to that exact tokenizer — it will count words using its own (invisible, un-auditable) notion of tokenization, which differs from the pipeline's in ways that compound over a chapter: hyphenated compounds, em-dash-joined clauses, italicized/emphasis-marked spans that may or may not survive HTML-to-text stripping, numbers written as digits vs. words, and quote-internal punctuation. Each of these differs from the pipeline's by ±0, ±1, or more per occurrence, and the error accumulates across a chapter, so a word position that's off by 5–40 words is a highly plausible-looking, non-obviously-wrong output — exactly the kind of error that damages a trusted corpus, because it doesn't fail loudly.

**Why it happens:**
LLMs do not internally tokenize the way the pipeline's regex/whitespace-split does, and nothing in a naive "extract evidence quotes with word positions" prompt forces the model to use the pipeline's counting rule rather than its own approximate sense of "word N."

**How to avoid:**
**Never let the LLM compute `mention_word_position` itself.** Structure the pipeline so the LLM's only output is the verbatim quote text (+ its role: which roll it's evidence for, hit/miss/perk-link), and have deterministic code — reusing the *exact* `_chapter_word_index` / `_split_sections` / `_strip_to_spaces` functions already in `find_text_backed_rolls.py` / `extract_chapter_sections.py`, not a reimplementation — locate that verbatim string in the chapter's tokenized word stream and compute the position. This also gives you a free validity check: if the LLM's quote string doesn't appear verbatim (exact substring match, after the same normalization the pipeline already applies) in the chapter text, the extraction is rejected outright rather than silently accepted with a guessed position. This directly satisfies the "no parallel implementations" constraint from PROJECT.md — reuse the pipeline's tokenizer, don't build a second one for agent curation.

**Warning signs:**
Any curation pipeline design where the LLM prompt output includes a numeric word position at all is a warning sign by itself — that's the mistake, structurally, regardless of how good the prompt is. In review, spot-check agent-curated `mention_word_position` values against a manual word-count in the actual chapter text for a sample of chapters; drift that grows with chapter length rather than staying constant indicates tokenizer mismatch rather than one-off error.

**Phase to address:** Confidence framework / agent curation pipeline design phase (Workstream 2, "Agent curation pipeline" requirement) — this must be an architectural decision (LLM never emits positions) made before any prompt is written, not a validation rule bolted on after.

---

### Pitfall 8: Verbatim-quote hallucination — paraphrase or light "cleanup" that reads as correct but doesn't exist in the prose

**What goes wrong:**
LLMs asked to extract "the quote where X happens" routinely produce text that is *semantically* faithful to the source but not *character-for-character* identical — smoothing awkward phrasing, fixing what looks like a typo, normalizing curly quotes/em-dashes/italics markup, dropping or adding a word that doesn't change meaning, or merging two nearby sentences into one "quote." Because this story's evidence-quote convention (per PROJECT.md context) is exact substrings tied to specific word positions, a paraphrased quote is not just "slightly wrong text" — it's an unfindable string that will fail (or worse, near-miss-match via fuzzy matching and silently anchor to the wrong nearby position) when the pipeline tries to locate it.

**Why it happens:**
This is a well-documented, general LLM extraction failure mode, not specific to this project: models are trained to produce fluent, plausible continuations, and "reproduce this exact string of characters including its imperfections" runs directly against that training pressure, especially over long context where the model's attention to the literal source text degrades relative to its own generative fluency.

**How to avoid:**
Validate every agent-proposed `evidence_quotes[].text` with an exact (not fuzzy) substring match against the chapter's raw extracted text, using the same normalization the pipeline already applies elsewhere (whitespace/HTML stripping) and nothing more permissive. Do not use `difflib.SequenceMatcher` or similar fuzzy matching to "rescue" near-miss quotes into acceptance — per the pipeline's own documented finding (`find_text_backed_rolls.py`), sequence-matching against large text chunks degrades badly and is not reliable for this kind of verification; a failed exact match should route the roll to the low-confidence proposals file, not to a fuzzy-accepted override. This is the single highest-leverage automatic gate available: it's cheap, deterministic, and catches the majority of hallucination cases without needing any model-based judgment call.

**Warning signs:**
Agent-curated evidence quotes that "read a little too smooth" compared to the author's actual prose style (LordRoustabout's voice has specific tics — run-ons, technical jargon, self-interruption — a suspiciously clean quote is a tell); any quote validation step that uses fuzzy/approximate matching instead of exact substring matching is itself a warning sign of a leaky gate.

**Phase to address:** Validation step of the agent curation pipeline (Workstream 2) — must be exact-match, and must run before anything reaches even the "high-confidence" bucket, let alone `chapter_roll_overrides.json`.

---

### Pitfall 9: Confidence miscalibration — the LLM's own stated confidence doesn't correlate with actual correctness, especially across CP-regime boundaries

**What goes wrong:**
If the confidence framework asks the LLM to self-report a confidence score, that score is known to be poorly calibrated to actual correctness — models are frequently *most* confident on cases that are subtly wrong (a roll structure that superficially matches the exemplar pattern but is actually misattributed) and can be uncertain-sounding on cases that are actually fine. Relying on model-reported confidence as the gate between "auto-write to overrides" and "route to proposals" risks exactly the failure PROJECT.md is most worried about: plausible-but-wrong curations polluting the trusted corpus, specifically because those are the ones the model will confidently mis-rate as high-confidence.

**Why it happens:**
LLM self-reported confidence is a generated token like any other — it reflects surface fluency and pattern-match strength to training/context data, not ground-truth correctness. It's a well-known general limitation, and it interacts especially badly here because this story has 3 CP regimes with mid-chapter transitions (per `data/manual/regime_transitions.json` — e.g., chapter 97's regime 2→3 transition triggered by the Nano-Forge acquisition event, not a chapter boundary): a model pattern-matching against 118 hand-curated exemplars that are unevenly distributed across regimes (more early-story chapters curated so far, per the 118/195 progress note) will be *most confident* exactly where it's *least trained* — post-transition chapters and mid-chapter-transition chapters — because it has no signal that its confidence should drop there.

**How to avoid:**
Don't gate on model-self-reported confidence alone. Build the confidence framework (per the Active requirement) primarily from *structural, checkable* signals mined from the 118-chapter corpus rather than the model's own assertion: does the proposed roll's evidence-quote count/pattern match the corpus's per-outcome norms (e.g., hits typically cite 2-4 quotes, misses cite 1, per the sample inspected)? Does the chapter straddle a `regime_transitions.json` boundary — if so, force low-confidence regardless of model confidence, since exemplar density there is guaranteed lower and the mechanic itself changes mid-chapter. Does the perk-name resolve cleanly through the existing resolver ladder, or did the agent invent/guess a name? Treat model-reported confidence, if used at all, as one weak input among several structural checks, never the sole gate.

**Warning signs:**
A confidence framework whose only signal is "ask the model how sure it is"; agent-curated chapters immediately following or straddling a `regime_transitions.json` entry landing in the high-confidence bucket at the same rate as chapters far from any transition (this is the diagnostic to actually run once the pipeline exists — regime-boundary chapters should show a *measurably lower* high-confidence rate, and if they don't, the confidence framework isn't sensitive to the thing most likely to break it).

**Phase to address:** Confidence framework design (Workstream 2, first Active requirement) — this determines the entire risk profile of everything downstream; get it structurally grounded before building the agent pipeline that depends on it.

---

### Pitfall 10: Exemplar overfitting to early-story roll mechanics that later chapters don't follow

**What goes wrong:**
118 of 195 (soon more, post-refresh) hand-curated chapters is a large exemplar set, but if curation to date has proceeded roughly front-to-back (a reasonable assumption for a hand-curation workflow reading a serialized story), the exemplars are skewed toward regime-1/early-regime-2 mechanics. An LLM few-shot-prompted or fine-tuned on this set will implicitly learn "how rolls look" from a period where multi-grab rolls, constellation drain/replacement, and roll-count-per-chapter norms may differ from later regimes. Applied to remaining (later, unrefreshed, or newly-released) chapters, it will pattern-match confidently to the *wrong* norm — e.g., expecting the roll cadence or grab structure of regime 1 in a regime-3 chapter — producing curations that are self-consistent with the exemplar set but wrong for the actual chapter's mechanics.

**Why it happens:**
Few-shot/RAG-style exemplar retrieval typically has no awareness of "which mechanical regime does this exemplar represent" unless that's explicitly encoded as retrieval metadata; the default behavior (retrieve textually/thematically similar exemplars, or use a fixed few-shot set) will happily mix regimes or default to whichever regime dominates the exemplar pool.

**How to avoid:**
Tag every exemplar chapter in the 118-chapter corpus with its applicable regime(s) (including mid-chapter-transition chapters as dual-tagged, per `regime_transitions.json`) and constrain exemplar retrieval/selection for a target chapter to same-regime exemplars only — never let a regime-1 chapter's roll structure serve as a few-shot example for a regime-3 target chapter. Where a target chapter falls in a regime with few or no same-regime exemplars yet (a real risk, since exemplar count will legitimately vary by regime given how far hand-curation has progressed per regime), that scarcity itself should force lower confidence rather than falling back to cross-regime exemplars silently.

**Warning signs:**
Agent curation error rate (measured via spot-check against the pipeline's existing predicted-roll cross-validation, which already checks predicted rolls against logged rolls) rising specifically for chapters in regime 3 or near the regime-2→3 transition at chapter 97, while staying low for regime-1 chapters — that pattern is the signature of this exact failure mode and should be checked for explicitly once the pipeline produces output, not assumed away.

**Phase to address:** Confidence framework + agent curation pipeline design (Workstream 2) — exemplar selection/retrieval logic must be regime-aware from the start; retrofitting regime-awareness after the pipeline exists means re-running/re-validating everything already curated.

---

### Pitfall 11: Curator vs. predictor `roll_number` sequence divergence gets silently violated by agent output

**What goes wrong:**
Per project memory, curator and predictor `roll_number` sequences diverge, and predicted-mode maps each curator roll to the next non-skipped predictor slot — a non-obvious accounting rule. An LLM generating new curator-schema entries for previously-uncurated chapters has no inherent reason to respect this mapping unless it's explicitly enforced by the pipeline's writer code, not by the LLM's own reasoning. A curation agent that assigns `source_ordinal` or roll sequencing by "just counting the rolls it found in this chapter" (a very natural, very wrong thing for an LLM to do) will desync from the predictor's accounting the moment there's any skipped roll in the chapter, which the model has no way to know about without querying the existing pipeline state.

**Why it happens:**
The roll-numbering scheme is a domain-specific pipeline invariant that exists nowhere in the prose text the LLM reads — it can only be respected by code that has access to the predictor's skip-accounting, not by an LLM reasoning from chapter text alone.

**How to avoid:**
Never let the LLM assign `source_ordinal` / roll sequence numbers. Have deterministic pipeline code compute these the same way it already does for hand-curated entries — the LLM's job is limited to identifying roll boundaries, outcomes, perks, and evidence quotes within a chapter; a wrapping function assigns sequence/ordinal fields using the existing predictor-slot-mapping logic, exactly as it would for a hand-curated entry. This is the same architectural pattern as Pitfall 7 (never let the LLM compute a value that has an existing deterministic source of truth) applied to a second field.

**Warning signs:**
Any curation-agent output schema where `source_ordinal` or `roll_number` appears as a field the LLM is asked to fill in, rather than one attached after the fact by pipeline code.

**Phase to address:** Agent curation pipeline design (Workstream 2) — enforce this in the writer/integration code that merges agent output into the schema, symmetric with how hand-curated entries already get this field assigned.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| Let the LLM emit `mention_word_position` directly instead of deterministic lookup | Faster to prototype, no need to wire pipeline internals into the agent | Silent, hard-to-detect position drift polluting the trusted corpus (Pitfall 7) | Never — not even for the low-confidence proposals file, since a human curator reviewing proposals will trust a pre-filled position field more than they should |
| Fuzzy-match agent quotes against prose to "rescue" near-misses | Higher apparent auto-accept rate | Reintroduces exactly the hallucination risk exact-matching was meant to catch (Pitfall 8); pipeline's own code already found fuzzy matching unreliable at this scale | Never for the high-confidence path; maybe acceptable as a *diagnostic* signal shown to a human curator in the TUI proposals view (not an auto-accept gate) |
| Use model self-reported confidence as the sole high/low gate | Fast to build, no corpus mining needed | Systematically miscalibrated exactly where regime transitions make it most dangerous (Pitfall 9) | Only as one weak input combined with structural checks — never alone |
| Share one `attachSkyGestures` call site across portrait and landscape without per-layout attach/detach bookkeeping | Less code to write in Phase B/C | Listener accumulation across layout swaps on rotation (Pitfall 2 interacting with Phase C's "no remount" gate) | Never — the "no remount" requirement makes this worse, not more acceptable |
| Skip the real-device iOS Safari test and rely on Chrome DevTools device emulation only | Faster iteration loop | `100vh`/toolbar and `orientationchange` timing bugs (Pitfalls 3, 4) are invisible in emulation | Acceptable for early layout iteration; never acceptable as the final Phase B/C/D gate check |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| `chapter_roll_overrides.json` schema vs. agent output | Adding a `provenance`/`confidence` field only to new agent-written entries, leaving hand-curated entries without it (implicit `null` = "hand-curated") | Per project's no-shims/no-parallel-implementations rule: rewrite the schema and every consumer (derive_roll_facts, TUI, validators) explicitly, so hand-curated entries carry an explicit provenance marker too, not an implicit absence |
| Predicted-roll cross-validation vs. agent-curated entries | Assuming the existing predicted-vs-logged cross-validation "just works" unchanged for agent-curated entries | Explicitly re-run cross-validation on agent-curated chapters as a Workstream 2 validation step (already an Active requirement) — treat it as the primary automated correctness signal, not just the exact-quote-match gate |
| Epub refresh (`sync_private_source_repo.py` → `hydrate_source_epub.py` → `pipeline.py`) | Running agent curation against a stale local epub cache because the refresh step was assumed already current | Treat the epub refresh as a hard gate (already flagged as such in PROJECT.md) — verify chapter count and predicted-roll integrity *before* any agent curation run, every time, not just once at milestone start |
| Perk name resolution ladder | Letting the agent invent a perk name string instead of resolving through the existing `perk_name_resolver.py` ladder | Agent output for perk names must be validated/resolved through the existing resolver before being considered high-confidence; an unresolvable perk name is itself a low-confidence signal (ties into Pitfall 9's structural-check list) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Gesture listener leak (Pitfall 2) treated as a "mobile only" concern | Extra memory/CPU from accumulated listeners, worse on longer sessions | Fix at the attach/detach architecture level in Phase A, not per-symptom later | Noticeable after minutes of playthrough on a real phone, not in a quick demo |
| Recomputing cluster-binning on every `resize`/`orientationchange` firing without debounce | Janky, dropped-frame layout during device rotation | `requestAnimationFrame`-debounce layout recompute (ties into Pitfall 3's fix) | On real devices during the rotation animation itself; invisible in static before/after screenshots |
| Re-running full-chapter tokenization per evidence quote in the agent pipeline instead of once per chapter | Slow, costly agent curation runs across ~80 remaining chapters | Tokenize each chapter once, reuse the word-offset index for all rolls/quotes in that chapter (mirrors what `find_text_backed_rolls.py` already does) | Noticeable at the scale of a full remaining-chapter batch curation run, not a single-chapter test |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Letting agent curation tooling read the epub but log/cache extracted prose snippets in a way that ends up in a committed artifact or LLM-provider-persisted context beyond the evidence-quote convention | Copyright exposure — epub is gitignored/private-repo-managed specifically to avoid redistributing prose | Confirm the LLM provider/tooling used for curation doesn't retain full-chapter prose beyond the call, and that only the already-established evidence-quote convention (bounded excerpts) ever reaches committed files — this is a stricter bar than "don't commit the whole epub," since even application-layer prompt logs could leak more prose than the convention allows |
| `user-scalable=no` framed as purely a UX/gesture decision | It's also an a11y compliance issue with real audit consequences (Pitfall 5) | Treat viewport-meta changes as needing the same review rigor as any other user-facing accessibility change, not a quick config tweak |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Chrome auto-hide (landscape) reveal-vs-pause ambiguity implemented backwards | User taps to unhide chrome, accidentally pauses playthrough too — jarring, feels broken | Implement exactly as spec'd: first tap after hidden reveals only, second tap (within the window) pauses — write this as an explicit two-state test, not just "tap toggles pause" reused from the always-visible-chrome case |
| Reduced-motion respected for the sky/carousel but not for the auto-hide timer doubling | Users with `prefers-reduced-motion` still get the fast 4000ms auto-hide, which is itself a jarring effect, even though transitions are disabled | Treat `prefers-reduced-motion` as touching *timing*, not just *animation curves* — the plan explicitly calls out doubling to 8000ms; verify it's wired to the media query, not a separate settings toggle that defaults off |
| First-run help overlay opens on every layout mode independently | User dismisses help in portrait, rotates, sees it again in landscape (if `bcf:help-seen` isn't correctly shared/read across the layout-mode branch) | Confirm `bcf:help-seen` is read once at the `app.*` state level, not re-checked independently inside each `renderMobile*` function in a way that could desync |

## "Looks Done But Isn't" Checklist

- [ ] **Desktop parity claim:** Passing the §0.5 smoke test once at the end of a phase is not sufficient — verify it was re-run *after* the most recent mobile-code change, not just before starting the phase.
- [ ] **Gesture porting:** "Ported verbatim from prototype/gestures.js" doesn't mean correct in this app — verify the attach/detach lifecycle was adapted for vanilla re-render semantics (Pitfall 2), not just copy-pasted.
- [ ] **Viewport height layout:** Verify on a real iOS device, not only Chrome DevTools emulation — emulation does not reproduce the dynamic-toolbar `100vh` behavior (Pitfall 4).
- [ ] **Accessibility score:** A Lighthouse a11y run late in Phase E that reveals a `meta-viewport` failure is not "almost done" — it's a config decision made in Phase A that needs revisiting, potentially with downstream gesture-disambiguation implications (Pitfall 5).
- [ ] **Agent curation "high confidence" output:** Passing the same pipeline validation hand-curated chapters pass (already an Active requirement) is necessary but not sufficient — also verify regime-transition-adjacent chapters specifically, since aggregate pass rates can hide a systematic failure concentrated in one regime (Pitfall 10).
- [ ] **Evidence quote validity:** "The quote text looks right" on manual read-through is not verification — verify exact substring match was run programmatically against the actual extracted chapter text for every agent-curated quote, not just a sample (Pitfall 8).
- [ ] **Word positions on agent-curated rolls:** Confirm they were computed by the pipeline's existing tokenizer function, not emitted by the LLM — check the code path, not just the output values, since plausible-looking positions can still be wrong (Pitfall 7).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|----------------|------------------|
| Gesture listener leak found late (Pitfall 2) | LOW–MEDIUM | Add attach-tracking (WeakSet/data-attribute guard) at the render call site; no schema or data changes needed, pure code fix |
| `100vh` layout bug found after Phase B/C sign-off (Pitfall 4) | LOW | Swap `vh` → `svh` in the mobile CSS block; scoped to the new mobile rules only, doesn't touch frozen desktop CSS |
| `user-scalable=no` flagged by Lighthouse late (Pitfall 5) | LOW | Single meta-tag line change plus confirming no gesture actually depended on it; re-run Lighthouse |
| Contaminated `chapter_roll_overrides.json` entries from agent output discovered post-merge (Pitfalls 7–11) | HIGH | Provenance marker (already planned as an Active requirement) is the recovery mechanism — filter by provenance, revert those entries specifically, and re-route the affected chapters to the proposals file for hand-curation; this is exactly why the provenance-marker requirement exists, so treat "can we cleanly identify and revert every agent-written row" as a hard property of the schema design, tested before the first real agent run, not discovered as a need after contamination |
| Regime-transition exemplar blind spot discovered after a curation batch has run (Pitfall 10) | MEDIUM–HIGH | Because entries carry provenance + should carry regime tags, re-filter agent output by regime-transition-adjacency and re-review that subset specifically, rather than re-reviewing everything — cost scales with how well regime metadata was captured up front |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|----------------|
| 1. Side effects leaking into pre-render layout-mode detection | Phase A | §0.5 smoke test run *after* a resize-down-then-up cycle, not just on fresh load |
| 2. Gesture listener double-binding | Phase A (design), Phase B gate | Swipe-after-2-minutes-of-playthrough test; count actual roll-advance per swipe |
| 3. resize/orientationchange race | Phase A (debounce built), Phase C gate | Real-device rotation test, not emulator; screen-record if needed to catch one-frame flashes |
| 4. `100vh` dynamic toolbar | Phase B & C (CSS unit choice) | Real iOS Safari device test against §6's exact viewport-percentage acceptance criteria |
| 5. `user-scalable=no` a11y conflict | Phase A (viewport meta set) | Lighthouse a11y run early, not deferred to Phase E |
| 6. Missing `visibilitychange` pause | Pre-Phase-A interview gate; implement Phase A/B | Add explicit line item to §6 checklist; manual background-and-resume test |
| 7. LLM-computed word positions | Confidence framework / pipeline design (Workstream 2, pre-implementation) | Code review confirms position computed by reused pipeline tokenizer function, never by LLM output field |
| 8. Verbatim quote hallucination | Agent pipeline validation step (Workstream 2) | Exact substring match required before any confidence bucketing; sample audit against prose |
| 9. Confidence miscalibration | Confidence framework design (Workstream 2, first) | Regime-transition-adjacent chapters show measurably lower high-confidence rate than the corpus average |
| 10. Exemplar overfitting to early regimes | Confidence framework + exemplar retrieval design (Workstream 2) | Exemplar corpus tagged by regime; retrieval constrained to same-regime; scarcity forces low confidence |
| 11. Roll-number/ordinal accounting violated by agent | Agent pipeline writer/integration code (Workstream 2) | Schema review confirms `source_ordinal`/roll sequencing is never an LLM-authored field |

## Sources

- [Fixing iOS Safari's Shifting UI with dvh](https://iifx.dev/en/articles/460170745/fixing-ios-safari-s-shifting-ui-with-dvh) — HIGH confidence, corroborates dynamic-toolbar `100vh` behavior and `dvh`/`svh` fix
- [100vh problem with iOS Safari — DEV Community](https://dev.to/maciejtrzcinski/100vh-problem-with-ios-safari-3ge9) — HIGH confidence, general web-search corroboration
- [Does Safari 15 finally fix viewport height? — Luke Channings](https://lukechannings.com/blog/2021-06-09-does-safari-15-fix-the-vh-bug/) — MEDIUM confidence, historical context on partial fixes
- [Understanding React Event Binding](https://www.dhiwise.com/post/understanding-react-event-binding-everything-you-need-to-know) — MEDIUM confidence, general corroboration of React-vs-vanilla listener lifecycle differences
- [React GitHub issue #3040 — Bind DOM event handlers to the component instance](https://github.com/facebook/react/issues/3040) — HIGH confidence, primary-source discussion of the binding pattern this project's port needs to reason about
- General web search on LLM verbatim-quote grounding and hallucination in long-document extraction (arXiv survey results, Anthropic/Claude Platform guidance on reducing hallucinations) — MEDIUM confidence, general-domain corroboration; the project-specific tokenizer/anchoring risk (Pitfall 7) is derived directly from this repo's own `scripts/find_text_backed_rolls.py` `_method`/`_framing_note` documentation, not from external sources — HIGH confidence for that portion
- `/Users/dre/src/bcf-visualization/scripts/find_text_backed_rolls.py` (read directly) — the `_method` field documents the exact tokenizer coupling (`_split_sections` + `_strip_to_spaces`, CP-earning-word counting) that Pitfall 7 is built on
- `/Users/dre/src/bcf-visualization/data/manual/regime_transitions.json` (read directly) — confirms the chapter-97 Nano-Forge-triggered regime 2→3 mid-chapter transition used as the concrete example in Pitfalls 9 and 10
- `/Users/dre/src/bcf-visualization/data/manual/chapter_roll_overrides.json` (read directly, sample chapter 67) — confirms the `evidence_quotes`/`mention_word_position`/`source_ordinal` schema shape referenced throughout
- `/Users/dre/src/bcf-visualization/design/mobile-ux/INTEGRATION_PLAN.md` (read directly) — source for all mobile-specific pitfalls' project-specific framing (§0 freeze rules, §1 locked decisions, §3 file-level changes, §6 acceptance, §9 open questions)
- `/Users/dre/src/bcf-visualization/.planning/PROJECT.md` (read directly) — source for curation-corpus schema notes, roll-numbering divergence rule (Pitfall 11), and copyright/private-source constraints

---
*Pitfalls research for: BCF Visualization mobile UX port + autonomous LLM chapter curation milestone*
*Researched: 2026-07-25*
