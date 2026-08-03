# Phase 4: Inference Refinement, Confidence Gate & Routing - Context

**Gathered:** 2026-08-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Stage 2: an inference pass that consumes Stage 1's candidates, recovers what deterministic heuristics cannot, grades the result, and routes by confidence into the trusted corpus or a proposals sidecar. Plus CINF-04's agent-run ledger for idempotency.

**This is the first phase that spends real API budget.** Phase 3's measurement is the input that sizes it: Stage 1 is confirmed on 4 of 663 rolls, so inference carries essentially all the semantic load.

**In scope:** ACUR-01 Stage 2, ACUR-02 (confidence gate), ACUR-03 (routing), CINF-04 (ledger idempotency).
**Not in scope (Phase 5):** the Forge Curator proposal-review flow (ACUR-04) and the full batch over the 80 uncurated chapters (ACUR-05). Phase 4 calibrates and proves on curated chapters; Phase 5 runs at scale.

### The value function (Dre, 2026-08-02) — read this before optimizing anything

**Success is measured in Dre's saved effort, not in autonomous-write percentage.** In his words: the win is not having to spend days manually highlighting obvious quotes and attaching them to rolls. Scanning a few dozen chapters for low-confidence or not-found items is a fine outcome.

Three consequences that override the natural instinct to maximize the high-confidence share:

1. **The expensive human act is locating and attaching a quote, not deciding.** A proposal arriving with the quote already found, positioned, and attached — even flagged low-confidence — captures most of the value. A blank chapter captures none. So **proposal richness matters more than proposal routing.**
2. **Therefore: never trade pre-fill quality for a cleaner confidence split.** The gate decides *where* output lands (corpus vs. proposals); it must not decide *how much effort goes into filling it in*. Both destinations get maximally pre-filled output.
3. **Therefore: spending more tokens to pre-fill something Dre would otherwise hand-fill is a good trade.** The comparison is tokens against days of his time, not tokens against a coverage metric. This does not license unbounded spend — D-23/D-24's ceiling, pilot, and pre-uncurated checkpoint still hold — but it does mean "cheaper" is not automatically "better" when the cheaper option ships emptier proposals.

A run that auto-writes little but hands back 80 densely pre-filled chapters is a **success**. A run that auto-writes a proud fraction and leaves the rest blank is a failure, however good its precision looks.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (locked — do not re-litigate)

- **`CURATION-CONVENTIONS.md` is the domain contract.** Read in full. Stage 2's prompts must teach the four-beat evidence shape, bundle-vs-multi-grab grouping, roll placement, miss handling, and §5's partial-evidence rule.
- **Phase 2 D-13 posture:** the mechanical verifier is exact-or-reject with no fuzzy path. Stage 2 may propose; the verifier judges. Never loosen the verifier to accommodate model output.
- **Phase 2 D-06(c):** paid perks resolve via the `perk_name_resolver` ladder, cost-0 ride-alongs via `obtained_perks.json`. Never add ride-alongs to the rollable directory.
- **Phase 2 D-12:** nothing bounds a quote's distance from its roll's `word_position` (measured max 7,392 words).
- **Phase 3 D-01/D-02:** `curated_by` is required and chapter-level. Agent-written chapters stamp `"agent"`.
- **Curation authority:** an existing hand-curated chapter entry is never overwritten (CINF-04). Since agents never touch curated chapters, no chapter mixes provenance — D-02's per-roll deferral holds.
- **Writes go through `chapter_roll_overrides_io.write_chapter_roll_overrides_doc`** (validated + atomic). No new write path.

### Input shape — retrieve candidate paragraphs, don't feed spans (Dre, 2026-08-02)

**Dre redirected the original design and the measurements back him decisively.** The first draft fed prose windows plus bounded forward spans (~1.7M tokens) to the model. Dre's point: the important quotes almost always name the perk exactly or close to it, and the TUI *already* has deterministic machinery that flags likely roll-related paragraphs. So retrieve candidate paragraphs cheaply and deterministically, then ask the model only about those.

Measured over all 869 curated evidence quotes and 198 chapters (2026-08-02):

| Strategy | Recall | Tokens |
|---|---|---|
| Whole chapters | — | ~3,531k |
| Windows + bounded forward spans (original draft) | — | ~1,700k |
| `evidence_scorer` threshold 1 alone | 83.4% | 1,569k |
| `evidence_scorer` threshold 3 alone | 71.9% | 221k |
| **threshold 3 ∪ perk-name match** | **85.5%** | **~363k** |

- **D-01 (input is a retrieved paragraph set):** Stage 2 receives, per chapter, the union of:
  1. paragraphs scoring at/above a tuned threshold from the **existing** `scripts/forge_curator/evidence_scorer.py:score_paragraph` / `evidence_candidates`;
  2. paragraphs containing a known perk name for that chapter from `obtained_perks.json` (token-subset match, tolerant of variants — `Altmode` vs "alt-mode");
  3. the roll's own `prose_window` from `roll_text_evidence.json` as the positional prior.
  Plus the Stage 1 candidate object and its `_derivation`. **Never whole chapters, never unbounded spans.**
- **D-02 (threshold is Stage-2's, not the TUI's):** the scorer's shipped `EVIDENCE_CANDIDATE_THRESHOLD = 4` is correctly tuned as a *low-noise navigation aid* for Dre's `n`/`N` jumping. Stage 2 wants recall, not quiet. Pass a threshold parameter; **do not change the TUI default** — degrading interactive navigation to serve a batch job is a bad trade. Threshold 3 is the measured knee; treat it as a starting point to tune on the calibration split, not a constant.
- **D-03 (reuse, don't rebuild — this is the no-parallel-implementations rule):** `evidence_scorer.py` (paragraph scoring), `quote_autofill.py` (deterministic constellation extraction from `KNOWN_CONSTELLATIONS`), and `miss_quote_matcher.py` (miss-specific candidates) already exist and are proven in the TUI. Stage 2 consumes them. Writing a second paragraph scorer or constellation extractor is a phase failure. The original draft was about to build span-slicing that duplicates what `evidence_candidates` already does better.
- **D-04 (the residual ~15% is a routing outcome, not a bug):** roughly one quote in seven is reachable by neither signal. Per `CURATION-CONVENTIONS.md` §5 those become evidence-not-found and route to proposals. Do NOT chase them by lowering the threshold toward 1 — that costs 4× the tokens for 2 points *less* recall than the union.
- **D-05:** exemplars come from `query_exemplars.retrieve()` (same-regime, deterministic), bounded to a small k. `exemplar_index.json` is 419 KB and must never be sent whole. Exemplars belong in the cached shared prefix, not per-request.
- **D-05a (ONE word-offset source — added post-pattern-mapping, 2026-08-02):** pattern mapping found **two independent prose/word-offset pipelines**: `scripts/forge_curator/data_loader.py`'s TUI-coupled one, and `scripts/cp_word_index.py`'s verifier-canonical one. This is a live correctness trap, because D-15 requires every proposed quote to pass `verify_roll()`, and the verifier's positions are defined against `cp_word_index`. Retrieving paragraphs with TUI offsets and then verifying against verifier offsets would let the two disagree silently, producing position errors that look like model errors.

  **Decision: `cp_word_index` is the single source of prose text and word offsets for Stage 2.** `evidence_scorer.evidence_candidates()` already takes `word_offsets` as a parameter, so it composes with the canonical tokenizer without modification — pass `cp_word_index`'s offsets in rather than reaching for `data_loader`'s. Do not add a third pipeline, and do not refactor the TUI's own pipeline as part of this phase (that would be scope creep into a working interactive surface). If the two pipelines are found to disagree materially on real chapters, record it as a deferred item rather than fixing it here.

### API mechanics (auto-resolved 2026-08-02, per `.planning/research/STACK.md`)

- **D-06:** Message Batches API for any multi-chapter run — purpose-built for N independent non-latency-sensitive requests at 50% lower cost. Key results by `custom_id`; **results arrive in arbitrary order, never assume positional correspondence.**
- **D-07:** Prompt caching with a `cache_control` breakpoint on the shared system prefix (conventions + schema + retrieved exemplars). That prefix is identical across requests in a run, so each subsequent request pays ~0.1× for it. Batching and caching compose — use both.
- **D-08:** Structured outputs (`output_config.format` JSON Schema with `additionalProperties: false`, or `client.messages.parse()` with a Pydantic model). **No free-text-then-parse.** The output schema is the roll-object schema plus a self-reported confidence field and a one-line reasoning string.
- **D-09 (model tiering):** calibrate on `claude-opus-5`. Only step the bulk pass down to `claude-sonnet-5` once calibration shows it clears the same verifier + confidence bar — and make that a data-driven decision against held-out chapters, not an assumption. Never Haiku: exact-quote fidelity matters more than latency here.

### What the model may and may not produce (auto-resolved 2026-08-02)

- **D-10:** The model proposes *quote text* and *structure* (grouping, constellation, outcome). It never emits word positions or roll ordinals. Positions are derived mechanically by locating the proposed quote via Phase 2's `cp_word_index` + verifier, exactly as a human curation is verified. A quote that cannot be located is a failed proposal, not a position to invent.
- **D-11:** Every proposed quote passes Phase 2's `verify_roll()` before it can contribute to a high-confidence routing decision. The verifier is the hard gate (ACUR-02); the model's self-reported confidence is a **tiebreaker only** and can never promote a candidate the verifier rejected.
- **D-12:** §5 of the conventions still governs: partial output is correct output. Stage 2 marking a field evidence-not-found is a success, not a failure, and should route to proposals rather than being dropped or guessed.

### Confidence gate & routing (auto-resolved 2026-08-02)

- **D-13:** Confidence is composite and code-computed: (a) every evidence quote passes verifier Tier 1/Tier 2; (b) the roll's structure agrees with the mechanical bundle from `obtained_perks.json`; (c) perk names resolve per D-06(c). High confidence requires (a)+(b)+(c). Anything else routes to proposals.

  **D-13 TIGHTENED (planner, 2026-08-02 — adopted):** this originally said model self-report was a "tiebreaker." That wording leaves a path for poorly-calibrated model confidence to influence routing, which is exactly the failure STACK.md warns about. **Self-report is explanatory metadata only and is never a routing input** — it is recorded for human review and post-hoc calibration analysis, and nothing else. The planner also observed that `verify_roll()` already composes signals (a) and (c), so the gate is really a two-part composite (`hard_pass` + `structural_agreement`), not three. Both refinements are stricter than what this document originally specified and are adopted; D-15 below is superseded on the tiebreaker point.
- **D-14:** Regime-boundary sensitivity (ACUR-02): chapters carrying the `is_boundary` flag from Phase 1's exemplar index must route to low confidence more often — verify this empirically rather than asserting it.
- **D-15:** Proposals sidecar uses the **same roll-object schema** as the corpus (Phase 3 D-05 precedent), so Phase 5's TUI review needs no translation layer. Location and file shape are Claude's discretion; a `data/derived/` artifact or a `data/manual/`-adjacent proposals file both defensible — but it is NOT the trusted corpus and must never be loaded as such.
- **D-16 (do not lower the bar to raise the count):** per STACK.md, a large proposals volume is a legitimate outcome. If high-confidence yield is low, that is a finding for Dre's review queue — never a reason to relax verification.
- **D-17 (proposals carry everything the model found, not a stripped remainder):** a proposal is the primary deliverable for most chapters, not a consolation prize. It carries the located quote text with its mechanically-derived position, the constellation, the bundle grouping, and a per-field record of what is evidenced versus evidence-not-found — so review is *confirm-or-correct*, never *start from blank*. Deliberately emitting less into proposals than into corpus writes would invert the value function: the quote-locating work is exactly what Dre is paying tokens to avoid doing by hand.
- **D-18 (report the metric that reflects the value function):** alongside the high/low confidence split, report **fields pre-filled per chapter** and **chapters requiring no manual quote-hunting**. A run's worth is how much hand-work it removed, not what fraction it auto-wrote. Success criterion 1's comparison against Phase 3's baseline stays as-is; this is an additional reported measure, not a replacement.

### Idempotency & the ledger (auto-resolved 2026-08-02)

- **D-19:** Agent-run ledger is a separate file keyed by chapter (Workstream Gate 2), holding run bookkeeping: model, run_id, corpus fingerprint, confidence, timestamps. It is NOT part of the overrides schema.
- **D-20:** Re-running a chapter with unchanged inputs produces **no diff**. The fingerprint must cover everything that could change the output — at minimum the chapter's prose, its Stage 1 candidates, the conventions/prompt version, and the model id. A prompt or model change must invalidate the fingerprint, or "no diff" silently becomes "stale output preserved."

### Calibration & cost control (auto-resolved 2026-08-02)

Measured pool: **108 genuinely curated chapters** (10 stubs excluded), **80 uncurated** targets for Phase 5.

- **D-21:** Split the 108 curated chapters into a calibration set and a **held-out** set. Tune the rubric on calibration only; report final numbers on held-out. Tuning against the set you report on produces a number that cannot be trusted — and Phase 3 just demonstrated how easily a measurement can mislead.
- **D-22:** Report Stage 2's improvement **per evidence class against Phase 3's recorded Stage 1 baseline** (`candidate-accuracy-report.md`), using the same three-tier position ladder so the comparison is like-for-like. Success criterion 1 is comparative; a standalone Stage 2 number does not satisfy it.
- **D-23 (spend discipline):** before any batch, emit a **dry-run token estimate** (request count, cached-prefix size, per-request input, projected cost) and gate the run on an explicit ceiling. Start with a small pilot batch, verify the whole pipeline end-to-end, then scale. This phase must not be able to spend unbounded budget by accident.
- **D-24:** A `checkpoint:decision` before the first run against **uncurated** chapters (roadmap note). Calibration on curated chapters is self-checking because ground truth exists; uncurated output has none, so Dre sees the calibration numbers before that boundary is crossed.

### Claude's Discretion

- Prompt composition and the exact cached-prefix contents (must include the conventions and the output schema)
- The forward-span cap value and truncation-marking mechanism (D-02)
- Exemplar count `k` (D-03)
- Calibration/held-out split ratio and selection method — must be deterministic and recorded
- Ledger file location and serialization
- Proposals sidecar location/format within D-13's constraints

### Known-accepted baseline (do NOT chase)

5 pre-existing failures: 4 `tests/test_forge_curator.py`, 1 `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`. `scripts/verify.py` exits 1 for that reason. Judge by "no NEW failures".

### Note for the planner: AI-SPEC does NOT apply (Dre, 2026-08-02)

An earlier draft of this context flagged that `/gsd-ai-integration-phase` should fire here since Phase 4 "builds an AI system." **Dre pushed back and is right.** This is a targeted prompt to a pre-existing available agent, asking for an inference over heuristically-collected evidence — not an AI system. The capability produces framework selection, evaluation strategy, guardrails, and production monitoring; applying it to a single call site inside a data pipeline generates ceremony around one prompt.

**Skip the `ai-integration` hook, consistent with Phases 1–3.** The evaluation this phase actually needs is already specified concretely and quantitatively below (D-21/D-22: calibration/held-out split, per-evidence-class comparison against Phase 3's recorded baseline) — that is the real eval plan, and it is better grounded than a generated one because it is measured against this corpus.

### Inference transport — no metered API spend (Dre, 2026-08-02, mid-execution)

Raised at Plan 04-01's Task 1 checkpoint, before `anthropic` was installed or any code was written. Nothing had been committed; this reverses the transport half of the API-mechanics decisions above rather than amending shipped work.

- **D-25 (no metered API spend — supersedes D-06 and D-07, and the transport half of D-08):** Dre will not pay per-token API costs for this phase. Stage 2 inference runs on an **already-subscribed agent harness** — the `claude` CLI, the `codex` CLI, or a Claude Code subagent — never `client.messages.create()`. Consequences, all binding:
  - The `anthropic` Python SDK is **not** added to `pyproject.toml`. Plan 04-01's Task 1 package-legitimacy checkpoint for `anthropic` is void (see D-27 for its successor).
  - **D-06 (Message Batches API) is struck.** Not reachable through a CLI/subagent transport. Multi-chapter runs become bounded-concurrency invocations, resumable via the D-19/D-20 ledger.
  - **D-07 (`cache_control` prompt caching) is struck.** Not controllable through this transport. The shared conventions/schema/exemplar prefix is still built once and reused, but any caching is the harness's business, not ours to declare.
  - **D-08's mechanism is replaced by D-26.** Its *intent* — never free-text-then-parse — survives intact and is non-negotiable.

- **D-26 (a propose-only MCP server is the structured-output mechanism):** Server-enforced `output_config.format` is unavailable through this transport, and free-text-then-parse is forbidden by `.claude/CLAUDE.md`. The resolution is an MCP server: **tool inputs are JSON-Schema-validated by the protocol**, which restores the D-08 guarantee at a different layer and additionally gives the model an immediate correction signal on a malformed submission rather than a silent post-hoc rejection.

  **The tool surface is propose-only. This is the load-bearing constraint of the whole design.**
  - The server exposes a **submission** tool (`submit_stage2_rolls(chapter_num, rolls[])` or equivalent). It MUST NOT expose any tool that writes a curation edit, mutates `chapter_roll_overrides.json`, or otherwise lets the model choose a destination.
  - The tool handler runs the pipeline this phase already owns: mechanical position derivation → mechanical constellation derivation (D-03) → `verify_roll()` (D-11) → `grade_roll()` (D-13) → `route_and_write()`. **The handler decides corpus vs proposals and enforces CINF-04 never-overwrite. The model never does.**
  - Rationale: a write-through tool would make the model the writer, voiding this phase's core guarantee and PROJECT.md's curation-authority constraint. Schema validation at the tool boundary is a bonus *on top of* the confidence gate, never a substitute for it.
  - The handler is `process_stage2_response()` — the shared function already specified for extraction — so the MCP server is a **thin transport over existing code, not a second implementation** (D-03).
  - Note that this server is independently useful beyond this pipeline: it is the mechanism by which Codex or Claude could drive Forge Curator curation edits interactively, which was Dre's original reason for wanting one. No such server exists in this repo today — searched `scripts/`, `docs/`, `plans/`, and git history on 2026-08-02, nothing found. This is new construction.

- **D-27 (the dependency moves, it is not avoided):** an MCP Python server SDK enters `pyproject.toml` in place of `anthropic`. **Plan 04-01's `blocking-human` package-legitimacy checkpoint (threat T-04-05) transfers to whichever package is selected — it is not waived.** Choice of SDK is Claude's discretion; the legitimacy gate is not.

- **D-28 (model tiering survives; only the invocation changes — revises D-09):** the Opus-vs-Sonnet comparison still runs and is still data-driven against the held-out split. It is selected via the harness's model flag rather than an API `model` parameter. D-09's substance — calibrate on Opus, step down only on evidence, never Haiku — is unchanged.

- **D-29 (spend discipline becomes usage-window discipline — supersedes D-23):** with no per-token dollar cost, a cost estimator and a `--ceiling-usd` cap measure nothing. Both are struck. The scarce resources are now Dre's subscription usage window and wall-clock time. Replace with:
  - a bounded chapter count per run (the run-size cap, not a dollar cap),
  - resumability via the D-19/D-20 ledger so an interrupted run costs nothing to restart,
  - bounded concurrency across chapter invocations.

  D-23's pilot-then-scale posture stands unchanged. The two approval checkpoints (Plans 04-04 and 04-05) survive but are re-framed: they approve **run size**, not dollars. **D-24 is unaffected** — the uncurated-boundary checkpoint is about absence of ground truth, not about money, and money was never its justification.

  Throughput warning for planning: an agentic per-chapter loop is materially slower than a Batches API submission. Phase 5's ~80-chapter run must be sized against wall-clock and usage window, not against the Batches API's 24h SLA.

### Tool surface & transport, settled by research (Dre asked at plan time, 2026-08-02)

Raised by Dre when re-planning Phase 4: *"the previous discuss / plan mentioned the MCP being 'submit only', but I'm not sure if that is just imprecise phrasing or if it actually denies the possibility of the agent making read calls to the TUI via the MCP where appropriate."* Settled in `04-RESEARCH.md` §Q3 with a measured basis.

- **D-30 (read tools are permitted — "propose-only" binds write authority, not information flow; clarifies D-26):** Every one of D-26's three prohibitions names a *write* or a *destination choice*, and its rationale names *"the writer."* The read surface is not mentioned. A read tool cannot make the model the writer, cannot mutate the corpus, and cannot choose a destination. **Dre's reading is correct; "submit-only" was imprecise shorthand.** D-26 is amended by appending: *"'Propose-only' governs write authority. Read-only tools that serve information the pipeline already owns are permitted and do not weaken the guarantee, provided (a) no read tool returns a destination or a routing decision, (b) no read tool records anything the gate later consults, and (c) every read tool's underlying source artifact is covered by the D-20 fingerprint."*

  **The Phase 4 tool surface is exactly three tools. Nothing else:**

  | Tool | Kind | Purpose | Cap |
  |---|---|---|---|
  | `submit_stage2_rolls(chapter_num, rolls[])` | submit | The only delivery channel. Handler runs derive → `verify_roll()` → `grade_roll()` → `route_and_write()` and decides the destination. | — |
  | `get_prose_span(chapter_num, start_word, end_word)` | read | Bounded prose around a stated offset via `cp_word_index`, to reach D-04's residual quotes that live outside the retrieved union. | ≤400 CP words/span, ≤5 calls/chapter |
  | `check_quote(chapter_num, quote_text)` | read | Non-authoritative dry-run of the Tier-1/Tier-2 quote search; returns `{found, tier, word_position, occurrence_count}` and **records nothing**. | ≤20 calls/chapter |

  No `write_*`, no `route_*`, no `set_confidence`, no tool that names or returns a destination, no tool that reads `chapter_roll_overrides.json`.

  Binding qualifications:
  - **`check_quote` does not constitute tuning to the verifier.** The verifier is exact-or-reject over real prose, so iterating toward an exact prose substring is the desired behavior — literally what a human curator does with the TUI's search. It cannot loosen the gate, because the gate re-runs `verify_roll()` on submission regardless. It raises pre-fill richness (D-17) without touching routing.
  - **`get_prose_span` is bounded opportunism, not a recall-maximization loop.** Per D-04, do not tune its caps upward to chase the residual. It is the one LOW-confidence element of the design and **must be instrumented so its contribution is measurable on the calibration split, with an explicit keep-or-drop decision recorded there.**
  - **Anything reading TUI or curation state is OUT OF SCOPE for Phase 4** — chapters-needing-curation, current overrides, session journal. Those serve D-26's noted secondary motivation (Codex/Claude driving Forge Curator interactively) and belong on the same server in Phase 5+. In Phase 4 they would let the model see the corpus it is proposing against, which is a **calibration contamination risk** — calibration runs against hand-curated chapters, so their answers would be readable.
  - **D-20's fingerprint gains a fourth term.** Read tools mean the run's inputs are no longer a static set, so the fingerprint must be taken over the *closed set of source artifacts the read tools could possibly serve* — a superset, never a subset. It adds `tool_surface_version` alongside `prompt_version` and `model`: changing what `get_prose_span` returns changes achievable output exactly as much as a prompt edit does. **Never fingerprint the tool-call transcript** — the transcript is an output, and keying on it makes idempotency vacuous. Do record the read-set (`[{tool, args, response_sha256}]`) in the ledger entry as an audit/diagnostic record that is never an input to the key. Since `temperature` is not controllable through this transport, D-20's "no diff" is satisfied by **skipping** at an unchanged fingerprint, not by re-running and hoping for byte equality.

- **D-31 (the MCP server is a pre-started warm loopback HTTP server, not stdio — corrects D-26's implied shape):** Measured, not assumed. An official-SDK **stdio** server failed 3/3 against `claude -p`: `--debug` printed *"Connecting MCP server (tools not available yet)"* and the model reported the tool did not exist. The server process started fine — it lost a startup race to the ~380–490 ms `import mcp` cost. A pure-stdlib stdio server won the race; adding an artificial 1.5 s delay to *that* one reproduced the failure, isolating latency as the cause. The same SDK server on a pre-started loopback HTTP endpoint connected reliably.

  **Therefore: bind `127.0.0.1` only (never `0.0.0.0`), on an ephemeral port the pipeline chooses and writes into a generated per-run `--mcp-config` JSON. Shut it down in a `finally` block — a leaked server is a real hazard, because its handler is what routes and writes.** Secondary benefit, independently worth it for D-29: one warm process across the whole batch builds the prose-loader cache, `DirectoryMatchIndex`, `obtained_perks_index`, and exemplar index **once** instead of 80 times, and makes concurrency trivial (N invocations, one server).

  Two measured facts that must shape the code:
  - **Subprocess exit 0 does not mean success.** Refusals, permission denials, and MCP-connection failures all report `is_error: false, subtype: "success"`. **The success criterion is handler-side state — "did a valid submission arrive?" — checked by the Python caller after the subprocess returns.** Log `permission_denials`, `num_turns`, and `usage` as corroborating signals; never gate on them. The CLI's `result` string is not the channel and must be discarded.
  - **`--permission-mode bypassPermissions` ignores `--allowed-tools`** — a tool absent from the allowlist was called successfully. This is empirical proof of D-26's thesis: **the propose-only guarantee must be enforced by what the server exposes, never by CLI flags.** Use `dontAsk` (which does enforce) as defense in depth only.

  `claude` is the harness; `codex` stays behind the same seam as a documented fallback (it has no `--mcp-config`/`--strict-mcp-config` equivalent, so per-run hermetic config is clumsier). **Do not use `--bare`** — it forces `ANTHROPIC_API_KEY` auth and would silently defeat D-25.

- **D-32 (`mcp>=1.29,<2` is the selected SDK; the legitimacy gate stands):** The official Linux-Foundation-stewarded SDK (MIT, `github.com/modelcontextprotocol/python-sdk`), added as a `curation` optional extra, using `mcp.server.lowlevel.Server` with **explicit JSON Schemas** — not `FastMCP`'s signature-derived schema, which was measured silently coercing `104` → `"104"`, and not the standalone `fastmcp` package (a strict superset pulling ~25 more packages, whose ergonomic API is already bundled inside `mcp`). The upper pin exists because `mcp` 2.0.0 is a days-old breaking major bump.

  **The D-27 `blocking-human` package-legitimacy checkpoint (threat T-04-05) transfers to `mcp` and is NOT waived.** Note for whoever runs it: the automated seam returned **SUS** for both `mcp` and `fastmcp` with reasons `too-new` + `unknown-downloads`, and research judged both to be artifacts of the seam's method against PyPI (it reads *latest* release date, and PyPI publishes no download counts). That assessment is input to the human check, not a substitute for it.

  Also load-bearing and easy to get wrong: **the JSON-Schema guarantee is real only because `Server.call_tool(validate_input=True)` runs `jsonschema.validate` and returns an `isError` correction signal.** The MCP spec places the MUST on *servers* validating tool inputs; there is no client-side MUST. Do not describe the guarantee as coming from "the protocol" without that flag being set.

- **D-33 (D-05a's trap is worse than D-05a states — correction, measured):** D-05a claimed `evidence_scorer.evidence_candidates()` "composes without modification" because it takes `word_offsets` as a parameter. **That is half true and the wrong half is dangerous.** `word_offsets` composes; `text` does not. The epub HTML has 13 newlines in 68 KB, so the canonical `_prose_search_text` collapses a 262-paragraph chapter into **3** regex paragraphs — feeding it straight to `evidence_candidates` silently destroys retrieval. Separately, the two word-index spaces diverge by **571–18,760 words** (ch 121.1: 23,922 CP words vs 42,682 TUI words), so mixing them is a live position-error generator exactly as D-05a warned.

  The fix is a **length-preserving, reuse-only adapter** specified in `04-RESEARCH.md` §"The D-05a Trap", verified byte-identical against `_chapter_word_index` on four real chapters. D-05a's core ruling stands unchanged: **`cp_word_index` is the single source of prose text and word offsets for Stage 2**; do not add a third pipeline and do not refactor the TUI's.

  **Consequence for measurement:** the D-01 union's measured 85.5% recall / ~363k tokens predates this adapter's paragraph segmentation. **Re-measure it inside the tracer before treating those numbers as the baseline.** The threshold-3 knee is likewise a starting point to re-tune, per D-02.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Domain contract (read first)
- `.planning/workstreams/curation/CURATION-CONVENTIONS.md` — the practice Stage 2 must reproduce; §5 partial evidence and §6 search posture are load-bearing for the confidence gate.
- `.planning/workstreams/curation/WOG-NOTES.md` — quote-less rolls are legitimate (ch 121.1).

### Measured inputs
- `.../phases/03-.../candidate-accuracy-report.md` and `.json` — Stage 1's baseline, per evidence class, with the three-tier position ladder. Success criterion 1 measures against this.
- `.../phases/01-.../corpus-analysis-report.md` — corpus shape: 57.6% of hit rolls multi-grab, evidence-quote patterns.
- `.planning/research/STACK.md` — Batches API, prompt caching, structured outputs, model tiering, and the "never trust bare model confidence" rationale behind D-11.

### Prior locked decisions
- `.../phases/02-mechanical-verifier/02-CONTEXT.md` — D-03 quote tiers, D-04 position tolerance, D-05 three outcomes, D-06(c) paid/free resolution, D-12 evidence spread, D-13 search posture.
- `.../phases/03-.../03-CONTEXT.md` — D-01/D-02 provenance, D-04/D-05 candidate artifact and schema reuse, D-06 partial evidence, D-07 class expectations.
- `.planning/workstreams/curation/ROADMAP.md` Workstream Gate 2 — provenance shape and the separate ledger.

### Code (primary sources)
- `scripts/build_candidate_rolls.py` + `data/derived/candidate_rolls.json` — Stage 2's input (718 candidates, 712 with `unfilled_fields`).
- `data/derived/roll_text_evidence.json` — `prose_window` (250-word setting, ~500 words actual), `matching_events`, `evidence_kind`, and `next_specific_event_offset` (present for all 485 `forward_ref` rolls — the D-02 mechanism).
- `scripts/mechanical_verifier.py` — `verify_roll()` / `verify_chapter()`; the hard confidence signal.
- `scripts/cp_word_index.py` — tokenizer + prose loader for mechanical position derivation.
- `scripts/query_exemplars.py` + `data/derived/exemplar_index.json` (419 KB) — same-regime retrieval; `is_boundary` drives D-12.
- `scripts/chapter_roll_overrides_io.py` — the validated, atomic loader/writer. The only sanctioned corpus write path.
- `scripts/perk_name_resolver.py`, `data/derived/obtained_perks.json` — perk resolution per D-06(c).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 2's verifier is the confidence gate's hard signal — already exact-or-reject, already 100% on the corpus.
- Phase 1's exemplar retrieval is deterministic and same-regime constrained; `is_boundary` chapters are pre-tagged.
- `roll_text_evidence.json` already carries the forward-reference offsets that make D-02's bounded expansion possible without new scanning.
- Phase 3's `chapter_roll_overrides_io` gives validated + atomic writes — agent writes inherit crash-safety and schema enforcement for free.

### Established Patterns
- `build_*`/`derive_*` scripts: argparse + pure-function core + `SCHEMA_VERSION`; tests import pure functions with synthetic fixtures.
- Derived artifacts carry registered schemas under `data/derived/_schemas/`.
- Every phase so far has kept LLM out of the loop; this is the first that does not, so the boundary between "model proposes" and "code decides" must be explicit in the code structure, not just in prose.

### Integration Points
- Phase 5's TUI review reads the proposals sidecar — D-13's schema reuse is what keeps that free.
- The ledger anchors CINF-04 and is read by Phase 5's batch run for resumability.

</code_context>

<specifics>
## Specific Ideas

- The honest framing from Phase 3: Stage 1 enumerates and marks; Stage 2 does the reasoning. Plan for that rather than for Stage 2 polishing a mostly-correct input.
- `forward_ref` at 68% is the phase. If Stage 2 does not move that class, it has not earned its budget — and D-02's bounded span is the mechanism that makes attempting it affordable.
- Dre is budget-conscious and has said so explicitly. D-19's dry-run estimate and ceiling are not ceremony; they are the difference between a calibration run and a surprise bill.

</specifics>

<deferred>
## Deferred Ideas

- Forge Curator proposal-review flow (ACUR-04) and the full 80-chapter batch (ACUR-05) — Phase 5.
- Per-roll `curated_by` granularity — only if a chapter ever legitimately mixes provenance (Phase 3 D-02).
- TUI dies on a validation error mid-session — tracked as a follow-up task; pre-existing, not this phase's.
- Confidence/error dashboard (CUR2-01) and automated re-curation on epub revision (CUR2-02) — v2.
- The 10 stub chapters' real curation — Dre's, excluded from calibration pools.

</deferred>

---

*Phase: 4-Inference Refinement, Confidence Gate & Routing*
*Context gathered: 2026-08-02*
