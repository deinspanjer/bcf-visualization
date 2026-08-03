# Phase 4: Inference Refinement, Confidence Gate & Routing — Research

> ## ⛔ STOPPED — do not build from this document
>
> **Phase 4 was stopped by Dre on 2026-08-03.** This research is accurate and its transport findings
> were measured by execution, but the effort it describes **was tried and abandoned**. The code was
> written, run on 5 curated chapters, and removed from `main`.
>
> **Before acting on anything below, read:**
> - `04-01-SUMMARY.md` — what was built, what the run actually showed, and why it was stopped
> - `docs/stage2_agent_curation_trial_2026-08.md` — the 52 verified quotes the run produced
> - Branch `parked/stage2-inference` — the removed implementation
>
> **The short version:** quote finding worked (52/52 located at verifier Tier 1, zero hallucinated);
> roll structure did not (ch 81 proposed five `hit / Personal Reality` rolls where the corpus curates
> misses). The unsolved problem is structural inference — outcome and constellation assignment — not
> the transport, retrieval, or verification this document spends most of its length on.
>
> Do not re-plan this phase without an explicit instruction from Dre. It consumed three planning
> passes before producing code.

**Researched:** 2026-08-02
**Domain:** Subscribed-harness LLM inference over a propose-only MCP server; deterministic evidence retrieval; composite confidence gating; fingerprint-keyed idempotency
**Confidence:** HIGH for the transport, package selection, and the D-05a offset trap (all verified first-hand in this session by running the real `claude` CLI, the real MCP SDK, and the real epub). MEDIUM for wall-clock projections at Phase 5 scale.

> **Method note.** The two highest-risk claims in this phase were not researched from documentation — they were *executed*. A real `claude` CLI (v2.1.220) was pointed at a real locally-spawned MCP server and made to submit a schema-conformant payload; and the two prose/word-offset pipelines were run against the real epub and their divergence measured. Everything tagged `[VERIFIED: local execution]` below was produced by running it.

---

## Directed Questions — Resolutions

### Q1 — Which Python MCP server SDK? → **`mcp` (the official SDK), pinned `mcp>=1.29,<2`, installed as an optional extra, using `mcp.server.lowlevel.Server` with explicit JSON Schemas**

**Recommendation:** add to `pyproject.toml` under a new optional-dependency group, **not** core `dependencies`:

```toml
[project.optional-dependencies]
curation = ["mcp>=1.29,<2"]
```

**Import surface for the server** (verified by installing 1.29.0 into a throwaway venv and introspecting) `[VERIFIED: local execution]`:

```python
import mcp.types as types
from mcp.server.lowlevel import Server        # mcp.server.lowlevel.server.Server
from mcp.server.stdio import stdio_server     # stdio transport
# for the recommended warm-HTTP transport (see Q2 / Integration Risk):
from mcp.server.fastmcp import FastMCP        # bundled INSIDE `mcp` — no separate dep
```

The canonical low-level shape (this exact server was run end-to-end against `claude -p` in this session):

```python
server = Server("bcf-stage2")

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [types.Tool(name="submit_stage2_rolls",
                       description="...",
                       inputSchema=SUBMIT_STAGE2_ROLLS_SCHEMA)]

@server.call_tool()                # validate_input=True is the DEFAULT
async def call_tool(name: str, arguments: dict):
    ...
```

#### Provenance — verified against the registry and the repo, not from memory

| Signal | `mcp` | `fastmcp` |
|---|---|---|
| PyPI latest | **2.0.0**, uploaded 2026-07-28 | **3.4.5**, uploaded 2026-07-27 |
| Recommended pin | **`>=1.29,<2`** (1.29.0 is the mature 1.x head) | — (rejected) |
| First release | 0.9.1, 2024-11-20 | 0.1.0, 2024-11-30 |
| Release count | 66 | 110 |
| Author field | **"Model Context Protocol a Series of LF Projects, LLC"** — Linux Foundation | Jeremiah Lowin (PrefectHQ) |
| Repository | `github.com/modelcontextprotocol/python-sdk` | `github.com/PrefectHQ/fastmcp` |
| Docs | `py.sdk.modelcontextprotocol.io` | `gofastmcp.com` |
| License | **MIT** | Apache-2.0 |
| `requires-python` | `>=3.10` | `>=3.10` |
| Vendor-official? | **Yes** — this is *the* protocol authors' SDK | No — community, though historically upstream of `mcp`'s bundled FastMCP |

All rows `[VERIFIED: PyPI JSON API, queried 2026-08-02]`.

#### Compatibility with this repo's actual Python constraint

`pyproject.toml` declares `requires-python = ">=3.11,<3.15"` `[VERIFIED: read from /Users/dre/src/bcf-visualization/pyproject.toml]` — **not** an assumption. The live `.venv` is **Python 3.14** `[VERIFIED: .venv/bin/python3.14]`. `mcp>=1.29` declares `>=3.10` and ships explicit `python_version >= "3.14"` dependency branches, so 3.14 is a supported target, not an accident.

#### Transitive dependency footprint — resolved, not estimated

`pip install --dry-run --report` against the live venv `[VERIFIED: local execution]`:

- **`mcp>=1.29,<2` → 29 packages total.** New to this repo (jsonschema and its `attrs`/`referencing`/`rpds-py`/`jsonschema-specifications` chain are already present via `jsonschema>=4.0`): `anyio`, `certifi`, `cffi`, `click`, **`cryptography==50.0.0`** (compiled), `h11`, `httpcore`, `httpx`, `httpx-sse`, `idna`, `mcp`, `pycparser`, `PyJWT`, `pydantic`, `pydantic_core`, `pydantic-settings`, `python-dotenv`, `python-multipart`, `sse-starlette`, `starlette`, `typing-inspection`, `typing_extensions`, `uvicorn`.
- `mcp>=2.0` → 28 packages; swaps `httpx`→`httpx2`, adds `opentelemetry-api`, `mcp-types`, `truststore`.

This is a **heavy** footprint for a server that will only ever talk to localhost — roughly half of it (`starlette`, `uvicorn`, `sse-starlette`, `PyJWT[crypto]`→`cryptography`) is HTTP/auth machinery. Accept it anyway; see "alternatives rejected" below. Isolating it behind an optional extra keeps `scripts/verify.py`'s normal test path, the Forge Curator TUI, and the derived-data pipeline unaffected by it.

#### Why `>=1.29,<2` and not `>=2.0`

`mcp` 2.0.0 is **5 days old** at the time of this research `[VERIFIED: PyPI upload_time 2026-07-28T13:45:28Z]` and is a major-version bump that swaps the HTTP client (`httpx` → `httpx2`) and splits out `mcp-types`. Pinning the mature 1.x head is the conservative call for a tracer; migrating to 2.x is a later deliberate step, not a Phase 4 concern. **Note for the planner:** this is the same "too-new" signal the legitimacy seam flagged — pinning to 1.x is the mitigation, not a reason to skip the checkpoint.

#### Alternatives considered and rejected

**`fastmcp` — REJECTED on footprint.** `fastmcp==3.4.5` is a meta-package resolving to `fastmcp-slim[client,server]==3.4.5`, whose `server` extra depends on **`mcp<2.0,>=1.24`** plus ~25 further packages (`authlib`, `cyclopts`, `griffelib`, `joserfc`, `jsonref`, `jsonschema-path`, `openapi-pydantic`, `py-key-value-aio[filetree,keyring,memory]`, `pyperclip`, `pyyaml`, `uncalled-for`, `watchfiles`, `websockets`, …) `[VERIFIED: PyPI JSON API]`. It is a **strict superset of `mcp`** — everything it adds (OpenAPI generation, auth providers, key-value stores, hot reload) is irrelevant here. Decisively: **the ergonomic decorator API is already bundled inside `mcp` as `mcp.server.fastmcp.FastMCP`** `[VERIFIED: local execution]`, so choosing `mcp` forfeits nothing.

**Raw JSON-RPC over stdio with no SDK — REJECTED, but it is genuinely viable and was proven working.** A 120-line pure-stdlib server written in this session successfully handshook with the real `claude` CLI, served `tools/list`, and received two `tools/call` invocations `[VERIFIED: local execution]`. It was rejected for three reasons: (1) it is a hand-rolled implementation of a published, versioned protocol — a "parallel implementation" in exactly the sense this project's own rule forbids, with the protocol as upstream; (2) the spec version moves (2024-11-05 → 2025-03-26 → 2025-06-18 → …) and the SDK absorbs that churn; (3) it would require re-implementing the input-validation-and-structured-error path the SDK already provides (see next). Its one real advantage — sub-50ms startup — is genuinely decisive for *stdio* transport (see Integration Risk), which is why the recommendation is warm-HTTP rather than stdio.

#### The load-bearing thing the SDK actually buys — and a correction to D-26's wording

D-26 says "tool inputs are JSON-Schema-validated by the protocol." **That is imprecise and the plan must not rely on it as written.** The MCP specification places the obligation on the *server*, not on the wire:

> **Security Considerations — 1. Servers MUST: Validate all tool inputs** … 2. Clients SHOULD: … Validate tool **results** before passing to LLM
> — `[CITED: modelcontextprotocol.io/specification/2025-06-18/server/tools]`

There is **no client-side MUST for validating tool inputs against `inputSchema`**; the only client-side schema-validation SHOULD is for *structured results* against `outputSchema`. So the guarantee is real only because the server enforces it.

The official SDK enforces it, by default, using the library this repo already depends on `[VERIFIED: read from mcp/server/lowlevel/server.py in the probe venv]`:

```python
def call_tool(self, *, validate_input: bool = True):
    ...
    if validate_input and tool:
        try:
            jsonschema.validate(instance=arguments, schema=tool.inputSchema)
        except jsonschema.ValidationError as e:
            return self._make_error_result(f"Input validation error: {e.message}")
```

That failure path returns an `isError: true` tool result to the model — **the immediate correction signal D-26 wants** — rather than a silent post-hoc rejection. This closes the D-08→D-26 guarantee properly. It also uses `jsonschema`, matching `_common.read_validated_json`/`write_validated_json`, so the phase introduces **no new validation mechanism**.

**Use `Server` (low-level) + an explicit `inputSchema` dict, NOT `FastMCP`'s signature-derived schema.** Measured difference `[VERIFIED: local execution]`: a `FastMCP`-decorated tool typed `chapter_num: str` **silently coerced an integer `104` to `"104"`** (pydantic leniency); the low-level server with an explicit `{"type": "string"}` schema rejects it. This phase's whole posture is exact-or-reject; take the strict path. The explicit schema is also a first-class artifact that can live under `data/derived/_schemas/` next to every other schema in this repo.

---

### Q2 — Own plan or folded into the tracer? → **Folded into the tracer (option b). One plan, `04-01`, ends with a real end-to-end run.**

**Rationale grounded in what "tracer" means here:** the tracer's whole point is to prove the real transport on one real curated chapter. A stub transport defeats it; a separate MCP plan ahead of it defers the first real end-to-end signal by a whole plan boundary and produces a plan whose only possible verification is "a server starts and echoes" — which proves nothing about *this phase*. And the server is genuinely thin: D-26 already mandates that its handler **is** `process_stage2_response()`, so the MCP module is transport plumbing over code the tracer must build anyway. Building it separately would mean building the handler first with no caller, or building the server first with a fake handler — both worse.

**Cost of the alternative (a), stated plainly:** an extra plan boundary and commit cycle; the package-legitimacy checkpoint fires in a plan that cannot demonstrate the package working against the real pipeline; and the integration risk (below) gets retired in isolation rather than against the real payload sizes, which is where it would actually bite.

**Resulting plan boundary for 04-01:**

| Task | Content | Gate |
|---|---|---|
| 1 | `checkpoint:blocking-human` — package legitimacy for `mcp>=1.29,<2` (T-04-05, transferred per D-27). Then add the `curation` optional extra and install. | **blocking-human** |
| 2 | Transport smoke test: start the propose-only server warm on loopback, invoke `claude -p --strict-mcp-config --mcp-config …`, assert a submission reached the handler. **No pipeline logic yet.** | automated |
| 3 | Pure-function core: `stage2_retrieval` (D-01 union + the D-05a adapter), `stage2_prompt`, `stage2_verify`, `stage2_confidence`, `stage2_proposals_io`, `stage2_routing`, and the shared `process_stage2_response()`. | automated (unit) |
| 4 | MCP server module = thin `@server.call_tool()` wrapper delegating to `process_stage2_response()`; harness invoker `run_stage2_chapter(..., transport=None)`. | automated |
| 5 | One real end-to-end run on chapter **92** (hand-curated → exercises the CINF-04 never-overwrite divert to proposals as part of the same live call). | manual/checkpoint |
| 6 | Mocked-transport test suite. | automated |

Task 2 is the payoff of folding: the integration risk is retired *before* any pipeline code exists, in the same plan, without a plan boundary.

---

### Q3 — Does "propose-only" forbid READ tools? → **No. D-26 binds write authority only. Dre is right. Offer exactly two read tools in Phase 4.**

#### The decision text, quoted

> "The server exposes a **submission** tool (`submit_stage2_rolls(chapter_num, rolls[])` or equivalent). It MUST NOT expose any tool that **writes a curation edit**, **mutates `chapter_roll_overrides.json`**, or otherwise **lets the model choose a destination**."
> "**The handler decides corpus vs proposals and enforces CINF-04 never-overwrite. The model never does.**"
> "Rationale: a **write-through** tool would make the model **the writer**, voiding this phase's core guarantee…"
> — `04-CONTEXT.md` D-26

Every one of the three prohibitions names a *write* or a *destination choice*. The rationale names *the writer*. The read surface is not mentioned anywhere in D-26, and a read tool cannot make the model the writer, cannot mutate the corpus, and cannot choose a destination. **"Propose-only" constrains authority, not information flow.** The phrase "submit-only" that appeared in the earlier discussion was imprecise shorthand, exactly as Dre suspected.

**Recommended clarifying amendment (non-substantive, for precision):** append to D-26 — *"'Propose-only' governs write authority. Read-only tools that serve information the pipeline already owns are permitted and do not weaken the guarantee, provided (a) no read tool returns a destination or a routing decision, (b) no read tool records anything the gate later consults, and (c) every read tool's underlying source artifact is covered by the D-20 fingerprint."* Flagged so the planner can carry it forward; the plan does not require the amendment to proceed, since nothing in D-26 forbids reads.

#### Tool-by-tool evaluation

The test applied: **pre-loading into the prompt is strictly better unless the payload is large *and* only conditionally needed, or the need depends on what the model concludes mid-reasoning.**

| Candidate | Verdict | Reasoning |
|---|---|---|
| **`get_prose_span(chapter_num, start_word, end_word)`** — bounded prose window via `cp_word_index` | **ADD (read)** | Strongest case. D-04's residual ~1 quote in 7 lives *outside* the retrieved union, and *which* span is needed is only knowable after the model reads the candidate paragraphs. Pre-loading spans is precisely the ~1.7M-token design Dre killed. Pull-on-demand recovers part of that residual at a fraction of the token cost. **Hard caps required:** ≤400 CP words per span, ≤5 calls per chapter, and the tool must be instrumented so its contribution is measurable on the calibration split. Per D-04 this is *bounded opportunism*, not a recall-maximization loop — do not tune it upward to chase the residual. |
| **`check_quote(chapter_num, quote_text)`** — dry-run verification, non-authoritative | **ADD (read)** | Converts a near-miss quote (whitespace drift, truncated at a paragraph boundary, off-by-a-clause) from a *failed* proposal into a *correct* one before submission. That is a direct hit on the value function: it raises pre-fill richness (D-17) without touching the gate. Returns `{found, tier: 1\|2\|null, word_position, occurrence_count}` and **records nothing**. **This does not constitute tuning to the verifier** — the verifier is exact-or-reject over real prose, so iterating toward an exact prose substring is the *desired* behavior and is literally what a human curator does with the TUI's search. It cannot loosen the gate, because the gate re-runs `verify_roll()` on submission regardless. Cap at ≤20 calls per chapter. |
| `get_candidate_paragraphs(chapter_num)` — the D-01 union | **Pre-load, no tool** | Always needed, bounded (~363k tokens over 198 chapters ≈ **~1.8k tokens/chapter**, measured in `04-CONTEXT.md`). A round trip buys nothing and costs latency. |
| `get_exemplars(regime, k)` — `query_exemplars.retrieve()` | **Pre-load, no tool** | D-05 already says exemplars live in the shared prefix. Fixed for the whole run; `exemplar_index.json` is 419 KB and must never be reachable whole. |
| `resolve_perk_name(raw_name)` — `perk_name_resolver` ladder | **Pre-load, no tool** | The chapter's `obtained_perks.json` bundle is a handful of rows. Pre-load the bundle; the resolution ladder is the *handler's* job on submission, not the model's. |
| `get_chapter_facts` / `obtained_perks` | **Pre-load, no tool** | Tiny per chapter. |
| Anything reading TUI/curation state (chapters needing curation, current overrides, session journal) | **OUT OF SCOPE for Phase 4** | These serve D-26's noted secondary motivation (Codex/Claude driving Forge Curator interactively). They belong on the same server *eventually* — Phase 5+ — but in Phase 4 they would let the model see the corpus it is proposing against, which is a contamination risk during calibration (calibration runs against **hand-curated** chapters, so their answers would be readable). **Explicitly exclude.** |

#### Hard consequence 1 — D-20 idempotency

**Does an agentic read loop break fingerprint-keyed idempotency? No — provided the fingerprint is taken over the *closed set of source artifacts the read tools can possibly serve*, not over the conversation.**

The read tools are pure functions of a small, enumerable set of on-disk inputs. So:

```
fingerprint = sha256(canonical_json({
    "chapter_num":        <str>,
    "chapter_html_sha":   sha256(load_chapter_html(EPUB, href)),
    "section_class_sha":  sha256 of this chapter's slice of section_classifications.json,
    "stage1_candidates":  this chapter's slice of candidate_rolls.json,
    "obtained_perks":     this chapter's slice of obtained_perks.json,
    "exemplar_index_sha": sha256(exemplar_index.json),
    "perk_directory_sha": sha256(perk_directory.json) + sha256(perk_aliases.json),
    "prompt_version":     STAGE2_PROMPT_VERSION,     # bump on any prompt edit
    "tool_surface_version": STAGE2_TOOL_SURFACE_VERSION,  # bump on any tool schema/behaviour change
    "model":              <harness model id>,
    "harness":            "claude-cli",
}))
```

Key properties:

- **Superset, not subset.** It covers everything the read tools *could* serve, whether or not the model actually pulled it. This over-invalidates (an unrelated exemplar-index rebuild busts every chapter's fingerprint) but **never under-invalidates**. D-20's requirement is one-directional — "unchanged inputs produce no diff" — so over-invalidation is the safe failure and under-invalidation is the unsafe one. Take the safe one.
- **`tool_surface_version` is the piece a naive fingerprint would miss.** Changing what `get_prose_span` returns changes the achievable output exactly as much as a prompt edit does. D-20's own list ("prose, Stage 1 candidates, conventions/prompt version, model id") predates read tools; this is the fourth term it needs.
- **Do NOT fingerprint the tool-call transcript.** The transcript is an *output*. Keying on it makes every run its own key and idempotency becomes vacuous.
- **Do record the read-set** — `[{tool, args, response_sha256}]` — in the ledger entry, as an audit and diagnostic record only. It explains *why* a chapter came out the way it did, and it is what you would diff when a re-run unexpectedly differs. It is never an input to the key.

Nondeterminism note: with `temperature` not controllable through this transport, two runs at the *same* fingerprint may still produce different model output. D-20's "no diff" is therefore satisfied by **skipping** — the ledger says "this chapter was processed at this fingerprint; do not reprocess" — not by re-running and hoping for byte equality. That is the correct reading of D-20 and it is unchanged by read tools.

#### Hard consequence 2 — D-29 wall-clock / usage window

Measured this session against the real harness `[VERIFIED: local execution, Sonnet tier, trivial payloads]`:

| Shape | `num_turns` | `duration_ms` |
|---|---|---|
| 1 read tool + 1 submit | 4 | 11,859 |
| 1 read + 1 submit, built-ins disabled | 3 | 12,677 |
| submit only (no read) | 3 | 12,677 → *see note* |
| warm-HTTP, 2 submits (one probing, one real) | 3 | 10,817 |
| refusal, zero tool calls | 1 | 8,419–13,818 |

**Reading these honestly:** the floor is ~8–9 s of harness overhead *before any work*, and an additional tool round trip costs roughly **+2–4 s**. The overhead floor is dominated by Claude Code's own system prompt — the envelope reported `cache_read_input_tokens: 168,153` on a run whose actual user input was 8 tokens. That overhead is **per invocation** and is the single strongest argument for fewer, larger invocations.

Projection for Phase 5's ~80 chapters (real payloads will be larger and Opus slower, so treat these as **lower bounds**):

| Configuration | Sequential | Concurrency 4 |
|---|---|---|
| Submit-only, one shot | ~80 × 12 s ≈ **16 min** | ≈ **4 min** |
| + 2 read tools, ~3 extra round trips/chapter | ~80 × 22 s ≈ **29 min** | ≈ **7 min** |
| Realistic Opus + 20–40k-token prompts (est.) | 2–4× the above | **~15–30 min** |

**Conclusion: read tools roughly double wall clock, and even doubled it is comfortably inside an hour at 80 chapters with bounded concurrency.** Wall clock is not the binding constraint. The binding constraint is the **subscription usage window**, and the harness hands you a free proxy for it: the `--output-format json` envelope reports full `usage` (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`) and an imputed `total_cost_usd` **even on a subscription** — a trivial run reported `0.1778` `[VERIFIED: local execution]`. **Log the whole `usage` block into each ledger entry.** That is what makes D-29's "run size" cap measurable instead of guessed, and it replaces D-23's struck dollar estimator with something real.

#### Hard consequence 3 — testability

Read tools do **not** complicate the seam, provided the seam is drawn at the transport boundary rather than at the call:

- Read-tool handlers are **pure functions over already-loaded documents**. They are unit-testable directly, with no transport, no subprocess, no MCP. They are the *easiest* thing in this phase to test.
- The MCP server module is a `@server.call_tool()` dispatch table. Testing it means calling the handler function, not speaking JSON-RPC.
- The one thing read tools genuinely change: **do not build a recorded-transcript fixture.** A multi-turn transcript replay is brittle and buys nothing. Record only the **final submission payload** as a JSON fixture and drive `process_stage2_response()` with it — every downstream behaviour (verify → grade → route → never-overwrite) is then exercised with zero inference. The live transport is proven once, by the tracer's manual step, and never in CI.
- MCP handlers are `async`; `pytest-asyncio` is already in this repo's `dev` extra `[VERIFIED: pyproject.toml]`, so no new test dependency.

#### Hard consequence 4 — scope

Phase 4: `submit_stage2_rolls` (submit), `get_prose_span` (read), `check_quote` (read). Phase 5+: everything that reads or drives curation state.

#### Recommended Phase 4 tool surface

| Tool | Kind | One-line purpose | Needs CONTEXT amendment? |
|---|---|---|---|
| `submit_stage2_rolls(chapter_num, rolls[])` | **submit** | The only delivery channel; handler runs derive → `verify_roll()` → `grade_roll()` → `route_and_write()` and decides the destination. | No — D-26 names it. |
| `get_prose_span(chapter_num, start_word, end_word)` | read | Return ≤400 CP-earning words of prose around a stated offset, via `cp_word_index`. Max 5 calls/chapter. | No (clarifying amendment recommended). |
| `check_quote(chapter_num, quote_text)` | read | Non-authoritative dry-run of the Tier-1/Tier-2 quote search; returns found/tier/position/occurrence-count and records nothing. Max 20 calls/chapter. | No (clarifying amendment recommended). |

**Nothing else.** No `write_*`, no `route_*`, no `set_confidence`, no tool that names or returns a destination, no tool that reads `chapter_roll_overrides.json`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

Copied verbatim from `04-CONTEXT.md`. **D-25 through D-29 supersede the earlier API-mechanics decisions and are not re-litigated here.**

**Carried forward (locked — do not re-litigate)**
- `CURATION-CONVENTIONS.md` is the domain contract. Read in full. Stage 2's prompts must teach the four-beat evidence shape, bundle-vs-multi-grab grouping, roll placement, miss handling, and §5's partial-evidence rule.
- Phase 2 D-13 posture: the mechanical verifier is exact-or-reject with no fuzzy path. Stage 2 may propose; the verifier judges. Never loosen the verifier to accommodate model output.
- Phase 2 D-06(c): paid perks resolve via the `perk_name_resolver` ladder, cost-0 ride-alongs via `obtained_perks.json`. Never add ride-alongs to the rollable directory.
- Phase 2 D-12: nothing bounds a quote's distance from its roll's `word_position` (measured max 7,392 words).
- Phase 3 D-01/D-02: `curated_by` is required and chapter-level. Agent-written chapters stamp `"agent"`.
- Curation authority: an existing hand-curated chapter entry is never overwritten (CINF-04).
- Writes go through `chapter_roll_overrides_io.write_chapter_roll_overrides_doc` (validated + atomic). No new write path.

**Input shape**
- **D-01:** Stage 2 receives, per chapter, the union of (1) `evidence_scorer` paragraphs at a tuned threshold, (2) paragraphs containing a known perk name from `obtained_perks.json` (variant-tolerant), (3) the roll's own `prose_window` from `roll_text_evidence.json`. Plus the Stage 1 candidate object and its `_derivation`. **Never whole chapters, never unbounded spans.**
- **D-02:** Pass a threshold parameter; **do not change the TUI default** `EVIDENCE_CANDIDATE_THRESHOLD = 4`. Threshold 3 is the measured knee — a starting point to tune, not a constant.
- **D-03 (reuse, don't rebuild):** `evidence_scorer.py`, `quote_autofill.py`, `miss_quote_matcher.py` already exist and are proven. Stage 2 consumes them. A second paragraph scorer or constellation extractor is a phase failure.
- **D-04:** the residual ~15% is a routing outcome, not a bug. Do NOT chase it by lowering the threshold toward 1.
- **D-05:** exemplars come from `query_exemplars.retrieve()`, bounded to a small k. `exemplar_index.json` (419 KB) must never be sent whole. Exemplars belong in the shared prefix.
- **D-05a:** **`cp_word_index` is the single source of prose text and word offsets for Stage 2.** Do not add a third pipeline; do not refactor the TUI's pipeline in this phase.

**Model boundary**
- **D-10:** the model proposes *quote text* and *structure*. It never emits word positions or roll ordinals. Positions are derived mechanically. A quote that cannot be located is a failed proposal, not a position to invent.
- **D-11:** every proposed quote passes `verify_roll()` before it can contribute to a high-confidence routing decision.
- **D-12:** §5 governs — partial output is correct output. Marking a field evidence-not-found is a success.

**Confidence gate & routing**
- **D-13 TIGHTENED:** confidence is composite and code-computed. **Self-report is explanatory metadata only and is never a routing input.** The gate is a two-part composite (`hard_pass` + `structural_agreement`), since `verify_roll()` already composes quote verification and perk resolution.
- **D-14:** regime-boundary chapters must route low more often — verify empirically, don't assert.
- **D-15:** proposals sidecar uses the **same roll-object schema** as the corpus. Location/shape is Claude's discretion; it is NOT the trusted corpus and must never be loaded as such.
- **D-16:** do not lower the bar to raise the count. A large proposals volume is a legitimate outcome.
- **D-17:** proposals carry everything the model found — located quote text with mechanically-derived position, constellation, bundle grouping, per-field evidenced/not-found record. Review is *confirm-or-correct*, never *start from blank*.
- **D-18:** report **fields pre-filled per chapter** and **chapters requiring no manual quote-hunting** alongside the confidence split.

**Idempotency & ledger**
- **D-19:** agent-run ledger is a separate file keyed by chapter. NOT part of the overrides schema.
- **D-20:** re-running a chapter with unchanged inputs produces **no diff**. The fingerprint must cover everything that could change the output — at minimum chapter prose, Stage 1 candidates, conventions/prompt version, and model id.

**Calibration**
- **D-21:** split the 108 curated chapters into calibration and **held-out**. Tune on calibration; report on held-out.
- **D-22:** report per evidence class against Phase 3's recorded Stage 1 baseline using the same three-tier position ladder.
- **D-24:** a `checkpoint:decision` before the first run against **uncurated** chapters. Unaffected by the transport reversal.

**Transport (the reversal — binding)**
- **D-25:** no metered API spend. Inference runs on an **already-subscribed agent harness**. The `anthropic` SDK is not added. **D-06 (Batches API) struck. D-07 (`cache_control`) struck. D-08's mechanism replaced by D-26; its intent — never free-text-then-parse — survives intact and is non-negotiable.**
- **D-26:** a **propose-only MCP server** is the structured-output mechanism. The tool surface must not expose any tool that writes a curation edit, mutates `chapter_roll_overrides.json`, or lets the model choose a destination. The handler is `process_stage2_response()` — a thin transport over existing code, not a second implementation. **The handler decides corpus vs proposals and enforces CINF-04 never-overwrite. The model never does.**
- **D-27:** an MCP Python server SDK enters `pyproject.toml` in place of `anthropic`. **Plan 04-01's `blocking-human` package-legitimacy checkpoint (threat T-04-05) transfers to whichever package is selected — it is not waived.**
- **D-28:** model tiering survives; selected via the harness's model flag. Calibrate on Opus, step down only on evidence, never Haiku.
- **D-29:** spend discipline becomes usage-window discipline. Cost estimator and `--ceiling-usd` are struck. Replace with a bounded chapter count per run, ledger resumability, and bounded concurrency. Pilot-then-scale stands.

**Note for the planner:** AI-SPEC does NOT apply. Skip the `ai-integration` hook, consistent with Phases 1–3.

**Known-accepted baseline (do NOT chase):** 5 pre-existing failures — 4 in `tests/test_forge_curator.py`, 1 in `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`. `scripts/verify.py` exits 1 for that reason. Judge by "no NEW failures".

### Claude's Discretion

- Prompt composition and the exact shared-prefix contents (must include the conventions and the output schema)
- Exemplar count `k` (D-05)
- Calibration/held-out split ratio and selection method — must be deterministic and recorded
- Ledger file location and serialization
- Proposals sidecar location/format within D-15's constraints
- Choice of MCP SDK (D-27) — but *not* the legitimacy gate

### Deferred Ideas (OUT OF SCOPE)

- Forge Curator proposal-review flow (ACUR-04) and the full 80-chapter batch (ACUR-05) — Phase 5.
- Per-roll `curated_by` granularity — only if a chapter ever legitimately mixes provenance.
- TUI dies on a validation error mid-session — pre-existing follow-up, not this phase's.
- Confidence/error dashboard (CUR2-01) and automated re-curation on epub revision (CUR2-02) — v2.
- The 10 stub chapters' real curation — Dre's.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **CINF-04** | Agent runs are idempotent (keyed by chapter + corpus fingerprint via the agent-run ledger) and never overwrite an existing hand-curated chapter entry | *Agent-Run Ledger* section: exact fingerprint composition including the `tool_surface_version` term read tools require; ledger state machine covering every new transport failure mode. Never-overwrite is enforced in `route_and_write()` by reading `curated_by` from `load_chapter_roll_overrides_doc()` before any write — verified as the caller's job, not `chapter_roll_overrides_io`'s. |
| **ACUR-01** (Stage 2) | Stage 2 inference refines/grades Stage 1 candidates and recovers what heuristics cannot; positions and ordinals always derived mechanically | *Transport* section (verified harness invocation), *D-05a Adapter* section (the verified code that makes `evidence_scorer` compose with the canonical tokenizer), *Reuse Audit* (exact signatures for every module the tracer calls). |
| **ACUR-02** | Confidence gate composed from mechanical verification signals; self-report is metadata only; tuned against held-out chapters with a regime-boundary check | *Confidence Gate* section: the two-part composite (`hard_pass` + `structural_agreement`) and the explicit statement that `self_reported_confidence` is carried but never read by a conditional. |
| **ACUR-03** | High-confidence → `chapter_roll_overrides.json` with provenance; low-confidence → proposals sidecar in the same roll-object schema | *Proposals Sidecar* section: concrete file location, schema shape mirroring the (deliberately loose) `chapter_roll_overrides.schema.json` roll array, and the serialization convention to copy. |
</phase_requirements>

---

## Summary

Almost everything this phase needs already exists in the repo; the phase is a **wiring exercise with two genuinely new pieces** (an MCP transport and a confidence gate) and **one sharp correctness trap**. The transport reversal (D-25…D-29) invalidated four of the five existing plans' spend-shaped machinery but left the pipeline design intact — retrieval, verification, grading, routing, and the ledger are all unchanged by it.

The single named integration risk — *"verify the chosen harness can be pointed at a locally-spawned stdio MCP server non-interactively"* — was **executed, not researched**, and the answer is nuanced: it works, but **not over stdio in the obvious way**. A `claude -p` run does **not block on MCP server connection**; a stdio server that takes ~0.5 s to start loses the race and the model runs the whole turn believing the tool does not exist, then exits with `is_error: false`. A pure-stdlib server (~50 ms) wins the race; the official SDK (~500 ms of imports) loses it, reproducibly. The robust fix is to run the propose-only server as a **pre-started, warm HTTP server on loopback**, which the pipeline owns for the whole batch — verified working, and independently better for D-29 (one warm process with warm prose/directory/exemplar caches across 80 chapters instead of 80 process spawns).

The second finding is a live correctness trap that `04-CONTEXT.md` D-05a identified but under-stated. D-05a says `evidence_scorer.evidence_candidates()` "composes with the canonical tokenizer without modification." Measured: **it does not.** Its `word_offsets` parameter composes; its `text` parameter does not. The epub HTML has essentially no newlines (13 in a 68 KB chapter), so feeding it the verifier's canonical `_prose_search_text()` collapses a 262-paragraph chapter into **3 paragraphs** and the scorer returns near-nothing. And the two word-index spaces disagree by **571–18,760 words** depending on chapter. A small, verified, length-preserving adapter fixes both; it is specified below with measured outputs.

**Primary recommendation:** fold the MCP server into the tracer (04-01); use `mcp>=1.29,<2`'s low-level `Server` with explicit JSON Schemas behind a warm loopback HTTP transport; offer exactly three tools (`submit_stage2_rolls`, `get_prose_span`, `check_quote`); fingerprint over the closed artifact set plus a `tool_surface_version` term; and make "the handler received a valid submission" — never the subprocess exit code — the definition of a successful run.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Candidate-paragraph retrieval (D-01 union) | Python pipeline (pure functions) | — | Deterministic; already exists in `evidence_scorer`/`miss_quote_matcher`; must never move into the model. |
| Prose text + CP word offsets | Python pipeline (`cp_word_index`) | — | D-05a: single source, verifier-canonical. |
| Prompt/shared-prefix assembly | Python pipeline | — | Deterministic; part of the D-20 fingerprint via `prompt_version`. |
| Inference (structure + quote text proposal) | **Subscribed agent harness** (`claude` CLI) | — | D-25. The only tier that reasons. |
| Structured delivery + schema enforcement | **MCP server boundary** (`jsonschema.validate` in `Server.call_tool`) | Python handler re-validates | D-26. The spec places input validation on the *server*, not on the wire. |
| Position derivation, constellation derivation | Python pipeline | — | D-10: code, never the model. |
| Verification | `mechanical_verifier.verify_roll()` | — | D-11: the hard gate. |
| Confidence grading + routing decision | **MCP tool handler** (`process_stage2_response`) | — | D-26: the handler decides, never the model. |
| Corpus write | `chapter_roll_overrides_io.write_chapter_roll_overrides_doc` | — | Only sanctioned write path. Never-overwrite enforced by the *caller*. |
| Proposals write | New `stage2_proposals_io` | — | D-15: same roll-object schema, different file, never loaded as corpus. |
| Idempotency / resumability | Agent-run ledger (new keyed store) | — | CINF-04 / D-19 / D-20. |
| Run-size and usage accounting | Python batch runner, fed by the harness's `usage` envelope | — | D-29. |

## The Integration Risk — RESOLVED, with a correction to the obvious design

**Harness:** `claude` CLI **v2.1.220**, `codex-cli` **0.145.0**, both installed `[VERIFIED: local execution]`.

### Recommended invocation (every flag verified against `claude --help` locally)

```bash
printf '%s' "$USER_MESSAGE" | claude -p \
  --strict-mcp-config \
  --mcp-config "$RUN_MCP_CONFIG_JSON" \
  --output-format json \
  --model "$MODEL" \
  --permission-mode dontAsk \
  --allowed-tools "mcp__bcf__submit_stage2_rolls" "mcp__bcf__get_prose_span" "mcp__bcf__check_quote" \
  --tools "" \
  --system-prompt "$SHARED_PREFIX" \
  --no-session-persistence \
  < /dev/null
```

| Flag | Purpose | Status |
|---|---|---|
| `-p, --print` | non-interactive | `[VERIFIED: --help + execution]` |
| `--mcp-config <configs...>` | "Load MCP servers from JSON files or strings" — accepts an inline JSON string, so the pipeline can generate a per-run config with no file on disk | `[VERIFIED: execution]` |
| `--strict-mcp-config` | "Only use MCP servers from `--mcp-config`, ignoring all other MCP configurations" — guarantees no user/project MCP servers leak into the run | `[VERIFIED: --help + execution]` |
| `--output-format json` | machine-readable envelope: `is_error`, `subtype`, `num_turns`, `result`, `permission_denials`, `usage`, `total_cost_usd`, `session_id`, `duration_ms` | `[VERIFIED: execution]` |
| `--model <model>` | **D-28 model tiering.** Accepts aliases (`opus`, `sonnet`) or full names | `[VERIFIED: --help + execution with `--model sonnet`]` |
| `--permission-mode dontAsk` | enforces the allowlist and *denies* rather than prompting — never hangs on stdin | `[VERIFIED: execution]` |
| `--allowed-tools` | defense in depth (see the caveat below) | `[VERIFIED: execution]` |
| `--tools ""` | "Use `\"\"` to disable all tools" — removes Read/Write/Bash/etc. from the run entirely | `[VERIFIED: --help + execution]` |
| `--system-prompt` | carries the shared conventions/schema/exemplar prefix | `[VERIFIED: --help]` |
| `--no-session-persistence` | no session files written for a batch run | `[VERIFIED: --help]` |

**Argument-parsing gotcha (cost me a failed run — put it in the plan).** `--tools`, `--allowed-tools`, and `--mcp-config` are **variadic**; a trailing positional prompt gets swallowed by whichever variadic option precedes it, producing `Error: Input must be provided either through stdin or as a prompt argument when using --print`. **Always pipe the prompt on stdin**, never pass it positionally. `[VERIFIED: local execution — reproduced twice]`

**Do NOT use `--bare`.** Its help text states: *"Anthropic auth is strictly `ANTHROPIC_API_KEY` or `apiKeyHelper` via `--settings` (OAuth and keychain are never read)"* `[VERIFIED: --help]`. That would silently defeat D-25's whole point by forcing metered auth. `--safe-mode` is also unsuitable — it disables MCP servers among other customizations.

### The startup race — the finding that changes the design

| Server | Startup | Result |
|---|---|---|
| Pure-stdlib stdio server (`import json, sys`, ~50 ms) | fast | **Connected.** `tools/list` served, 2 `tools/call` received, submission written. `num_turns: 4`. |
| Official-SDK stdio server (`import mcp` ≈ 380–490 ms) | slow | **FAILED, 3/3 attempts.** Model reported "I don't have a tool called `submit_stage2_rolls`". `--debug` showed literally: **"Connecting MCP server (tools not available yet): `bcf`"**. Server process *did* start (wrapper logged it) and exited cleanly — it simply lost the race. |
| Pure-stdlib stdio server + `sleep 1.5` before exec | slow | **FAILED.** Confirms latency is the variable, not the SDK. |
| Official-SDK server on **pre-started loopback HTTP** (`127.0.0.1:8931/mcp`, `streamable-http`) | already warm | **Connected reliably.** Submission written; `num_turns: 3`; `duration_ms: 10,817`. |

All `[VERIFIED: local execution]`.

**Conclusion: use a pre-started warm HTTP server on loopback, not stdio.** The MCP config the pipeline generates per run is then trivial:

```json
{"mcpServers": {"bcf": {"type": "http", "url": "http://127.0.0.1:<port>/mcp"}}}
```

Secondary benefits, all real:
- One warm process for the whole batch → the prose loader cache, `DirectoryMatchIndex`, `obtained_perks_index`, and exemplar index are built **once**, not 80 times.
- Removes ~0.5 s of process spawn from every chapter.
- Makes concurrency trivial: N concurrent `claude` invocations, one server.

Security requirements for the HTTP transport (the plan must state these):
- Bind **`127.0.0.1` only**, never `0.0.0.0`.
- Use an **ephemeral port** chosen by the pipeline and written into the generated `--mcp-config` JSON, so nothing is discoverable at a fixed address.
- Shut the server down in a `finally` block; a leaked propose-only server is not dangerous (it cannot write the corpus… but its handler *can*, since it routes) — **treat a leaked server as a real hazard and kill it deterministically.**
- Optional hardening: a per-run bearer token. `claude mcp add --transport http … --header "Authorization: Bearer …"` confirms headers are supported for HTTP servers `[VERIFIED: claude mcp --help]`; the corresponding `--mcp-config` JSON key is **`[ASSUMED]`** to be `"headers"` and must be confirmed by the executor before being relied on.

### Forcing and verifying that the tool is actually called

Two measured facts settle this:

1. **The `result` string is not the channel and must be discarded.** Given a deliberately prose-inviting prompt with no tool instruction, the model **still called the submit tool** *and* answered in prose. `[VERIFIED: local execution]` Detection is therefore "did my handler receive a valid submission?", never "parse the CLI's answer."
2. **Exit code 0 / `is_error: false` does NOT mean the submission happened.** With `--permission-mode dontAsk` and a read tool omitted from the allowlist, the run reported `subtype: "success"`, `is_error: false`, `num_turns: 2`, `permission_denials: [{tool_name: "mcp__bcf__get_candidate_paragraphs", …}]` — and **submitted nothing**. `[VERIFIED: local execution]` A refusal run behaved identically (`is_error: false`, zero tool calls).

**Therefore the success criterion is handler-side state, checked by the Python caller after the subprocess returns.** Corroborating signals to log but never to gate on: `permission_denials` non-empty (misconfiguration), `num_turns == 1` (refusal), `usage` (run sizing).

**Caveat on `--allowed-tools`:** with `--permission-mode bypassPermissions`, the allowlist is **ignored** — the model successfully called an MCP tool that was *not* in `--allowed-tools`. `[VERIFIED: local execution]` **This is the empirical proof of D-26's core thesis: the propose-only guarantee must be enforced by what the server exposes, never by CLI flags.** Use `dontAsk` (which does enforce), but treat it as defense in depth only.

### `codex` CLI — viable but a worse fit

`codex exec` offers `-m/--model`, `--json`, `-o/--output-last-message <FILE>`, `--output-schema <FILE>`, `--ephemeral`, `--ignore-user-config`, and `-c key=value` config overrides `[VERIFIED: codex exec --help]`. **It has no `--mcp-config` file flag and no `--strict-mcp-config` equivalent** — MCP servers come from `~/.codex/config.toml` or ad-hoc `-c mcp_servers.<name>.…` overrides, so per-run hermetic configuration is clumsier and run isolation is weaker. **Recommend `claude` as the harness**; keep `codex` behind the same seam as a documented fallback, not as a supported path in Phase 4.

### A noted alternative that is NOT the recommendation

`claude` also exposes **`--json-schema <schema>`** — "JSON Schema for structured output validation" `[VERIFIED: --help]`. This is a CLI-native answer to "never free-text-then-parse" and would satisfy D-08's *intent* without MCP. It is **not** a substitute for D-26, because it returns validated text to the caller and does not run the handler — the corpus-vs-proposals decision would move back into the caller, which is fine, but it forfeits the model's ability to *read* anything and forfeits the in-loop correction signal. Record it as the **documented fallback** if the MCP path ever regresses, and as evidence that D-25's transport does not force free-text parsing under any circumstance.

## The D-05a Trap — measured, with a verified adapter

D-05a is correct that `cp_word_index` must be the single source. Its *reasoning* about composition is where the plan must not follow it literally.

### Measurement 1 — the two word-index spaces disagree massively

`[VERIFIED: local execution against the real epub]`

| Chapter | `cp_word_index._chapter_word_index` (CP-earning words, offsets into raw HTML) | `data_loader._compute_word_offsets(_strip_html(html))` (all words, offsets into stripped text) | Divergence |
|---|---|---|---|
| 1 | 4,340 | 4,911 | **571** |
| 92 | 10,978 | 11,580 | **602** |
| 104 | 14,039 | 14,291 | **252** |
| 121.1 | 23,922 | 42,682 | **18,760** |

Two independent disagreements compound: a different **character space** (raw HTML vs. entity-decoded stripped text) *and* a different **word population** (CP-earning-only vs. every whitespace token). A quote located with TUI offsets and then checked against `word_position` would be wrong by hundreds to tens of thousands of words — **silently**, because both numbers are plausible integers. D-05a's "live correctness trap" framing is, if anything, understated.

Ancillary reason to avoid `data_loader`: importing it pulls `scripts.chapter_roll_overrides_io` → `_common` → `jsonschema` and the whole TUI object graph at module import `[VERIFIED: import traceback]`. Far heavier than a batch script wants.

### Measurement 2 — `evidence_scorer` does NOT compose with the canonical text as-is

`evidence_scorer._paragraph_matches` splits on blank lines: `re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", text)`. The epub HTML for chapter 92 contains **13 newlines** in 67,840 characters and **262 `<p>` tags** `[VERIFIED: local execution]`. Consequently:

| Text fed to `_paragraph_matches` | Paragraphs found (ch 92) |
|---|---|
| Raw chapter HTML | **1** |
| `mechanical_verifier._prose_search_text(html)` (the canonical, length-preserving, entity-decoded text) | **3** |
| TUI's `_strip_html(html)` | (many — but wrong offset space) |

**Feeding the canonical text straight into `evidence_candidates()` yields ~3 "paragraphs" per chapter and is useless.** The `word_offsets` parameter composes; the `text` parameter does not.

### The verified adapter — reuse-only, length-preserving

Two small pure functions. Both were written and run against chapters 1, 92, 104, and 121.1 in this session.

```python
# scripts/stage2_retrieval.py

_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|h[1-6]|li|blockquote|br|hr)\b[^>]*>", re.IGNORECASE
)

def paragraphized_prose_text(chapter_html: str) -> str:
    """`mechanical_verifier._prose_search_text` + length-preserving paragraph
    breaks, so `evidence_scorer._paragraph_matches` can segment it while every
    char offset stays a valid index into `chapter_html` (and therefore into
    `cp_word_index._chapter_word_index`'s offsets)."""
    buf = list(mechanical_verifier._prose_search_text(chapter_html))
    for m in _BLOCK_TAG_RE.finditer(chapter_html):
        if m.end() - m.start() >= 2:          # every block tag is >= 3 chars
            buf[m.start()] = "\n"
            buf[m.start() + 1] = "\n"
    return "".join(buf)

def word_starts_to_spans(word_starts: list[int], text_len: int) -> list[tuple[int, int]]:
    """Adapt `cp_word_index`'s `list[int]` of CP-word char starts into the
    `list[tuple[int,int]]` `evidence_scorer`/`miss_quote_matcher` expect.
    Contiguous spans reproduce `bisect_right(word_starts, c) - 1` semantics."""
    return [
        (s, word_starts[i + 1] if i + 1 < len(word_starts) else text_len)
        for i, s in enumerate(word_starts)
    ]
```

Verified properties `[VERIFIED: local execution]`:

| Chapter | Paragraphs after adapter | `evidence_candidates` @3 | @4 | `word_index` == `bisect_right(cp_index, char)-1`? |
|---|---|---|---|---|
| 1 | 98 | 9 | 7 | all but 1 (see edge case) |
| 92 | 264 | 12 | 8 | **all** |
| 104 | 336 | 13 | 7 | **all** |
| 121.1 | 781 | 37 | 10 | **all** |

- `len(paragraphized_prose_text(html)) == len(_prose_search_text(html)) == len(html)` on all four chapters.
- `[s for s, _ in word_starts_to_spans(...)]` is **byte-identical** to `_chapter_word_index(...)` on all four.
- **Edge case (ch 1, 1 mismatch):** a paragraph starting *before* the first CP-earning word maps to index `0` under `_word_index_for_char` but `-1` under `bisect_right(...)-1`. Harmless (both mean "before the corpus starts"), but the plan should note it rather than have a test discover it.

### One open decision for the planner: blank non-CP sections or not?

`_prose_search_text` covers the **whole** chapter HTML, including sections with `counts_for_cp: false`. A retrieved paragraph from such a section maps, via bisect, to the last CP word *before* it — potentially thousands of words away.

Measured on ch 121.1 `[VERIFIED: local execution]`: blanking non-CP sections (length-preservingly, before paragraph injection) drops paragraphs 781 → 455 and candidates@3 from 37 → 25.

**Recommendation: blank non-CP sections for retrieval.** It matches CP-word semantics, cuts ~32% of retrieval tokens on the worst chapter, and removes a class of nonsense positions. **Counter-consideration the planner must weigh:** `verify_roll()` searches the *unblanked* text, so a quote the model proposes from a non-CP section would still verify — blanking only changes what the model is *shown*, never what is accepted. That asymmetry is safe (it can only cause under-retrieval, which D-04 already classes as a routing outcome), but it should be a stated decision, not an accident.

## Reuse Audit (D-03 — no parallel implementations)

Every signature below `[VERIFIED: read from source in this session]`. **All are consumed, none are modified.**

| Module | Function / constant | Signature | Stage 2's use |
|---|---|---|---|
| `scripts/forge_curator/evidence_scorer.py` | `evidence_candidates` | `(text: str, word_offsets: list[tuple[int,int]], *, threshold: int = EVIDENCE_CANDIDATE_THRESHOLD) -> list[EvidenceCandidate]` | D-01 union component 1. Pass `threshold=3`. Feed it the adapter's outputs. |
| | `score_paragraph` | `(paragraph: str) -> tuple[int, list[str]]` | Available; not needed directly. |
| | `EVIDENCE_CANDIDATE_THRESHOLD` | `= 4` (line 24) | **Never modify** (D-02). |
| | `EvidenceCandidate` | frozen dataclass: `paragraph_index, char_start, char_end, word_index, score, matched_terms` | Retrieval snippet source. |
| `scripts/forge_curator/quote_autofill.py` | `single_constellation_reference` | `(quote: str) -> str \| None` | Mechanical constellation derivation. Run on every *verified* quote; the code-derived value beats the model's. |
| | `classify_quote_autofill` | `(quote: str) -> QuoteAutofillSuggestion \| None` | Cross-check of `outcome` + `constellation`; disagreement is a confidence signal. |
| | `KNOWN_CONSTELLATIONS` | 14-item list | Prompt content; never re-derived. |
| `scripts/forge_curator/miss_quote_matcher.py` | `find_miss_quote_candidates` | `(text, word_offsets, *, constellation, anchor_word_index, window_before=800, window_after=6500) -> list[MissQuoteCandidate]` | **D-01 union component 3 — mandatory for every miss-outcome Stage 1 candidate.** Perk-name matching is structurally inapplicable to a miss (no acquired perk), so without this a miss roll is served only by the generic scorer. |
| `scripts/query_exemplars.py` | `retrieve` | `(target_regime: int, index: dict, *, k: int \| None = None, target_chapter: str \| None = None) -> list[dict]` | D-05. **Filter the target chapter out of `index["exemplars"]` before calling** — a calibration run against a curated chapter must not be shown its own answer. |
| `scripts/mechanical_verifier.py` | `verify_roll` | `(chapter_num: str, roll_index: int, roll: dict, *, prose_loader, directory_index, obtained_perks_index) -> dict` | D-11 hard gate. Returns `{chapter_num, roll_index, status: pass\|fail\|no_evidence, issues: [{code, severity, message}]}`. |
| | `verify_chapter` | `(chapter_num: str, override_entry: dict, *, prose_loader, directory_index, obtained_perks_index) -> dict` | Per-chapter aggregate. |
| | `build_obtained_perks_index` | `(obtained_perks_doc: dict) -> dict[tuple[str,str], dict]` | D-06(c) cost branch point. |
| | `_prose_search_text` | `(chapter_html: str) -> str` | **Base for the retrieval adapter.** Length-preserving, entity-decoded. Never write a fourth text-prep pass. |
| | `_build_tier2_pattern` | `(quote_text: str) -> re.Pattern[str]` | Reuse for `check_quote` and for position derivation. |
| | `_build_prose_loader` | `(epub_path, chapters_doc, classifications_doc) -> Callable[[str], tuple[str, list[int]]]` | **Reuse this closure shape verbatim.** `build_candidate_rolls.py` already mirrors it — that makes two; a third is a D-03 violation. |
| | `POSITION_TOLERANCE_WORDS` | `= 50` | Do not bypass. Positions derived by exact location coincide by construction. |
| `scripts/cp_word_index.py` | `load_chapter_html` | `(epub_path: Path, epub_href: str) -> str` | Prose source. |
| | `_chapter_word_index` | `(chapter_html: str, section_classifications: dict[str, dict], chapter_num: str) -> list[int]` | **The single word-offset source (D-05a).** Note `section_classifications` is the `["classifications"]` sub-dict of `data/manual/section_classifications.json`, not the whole doc. |
| | `_strip_to_spaces`, `_split_sections` | — | Available if non-CP blanking is adopted. |
| `scripts/chapter_roll_overrides_io.py` | `load_chapter_roll_overrides_doc` | `(path: Path \| None = None, *, default: dict \| None = None) -> dict` | **Read before every write** — this is where CINF-04's never-overwrite is enforced (the module does not enforce it). |
| | `write_chapter_roll_overrides_doc` | `(doc: dict, path: Path \| None = None) -> None` | Only sanctioned corpus write. Already enforces `curated_by` ∈ {human, agent}. |
| `scripts/perk_name_resolver.py` | `build_directory_match_index` | `(directory_rows: list[dict], aliases: dict[str, list[str]] \| None = None) -> DirectoryMatchIndex` | Built once, held warm on the server. |
| | `load_perk_aliases` | `(path: Path \| None = None) -> dict[str, list[str]]` | Variant source for the perk-name-in-prose scan — **do not invent a second alias table**. |
| `scripts/build_candidate_rolls.py` | `_find_free_perk_evidence` | `(perk_name, search_text, word_index, start_word) -> {...} \| None` | Mirror its Tier-1/Tier-2 matching **shape** for D-01 union component 2 (paragraph membership, not single-match forward search). Do not import it. |
| | `_build_prose_loader` | as above | Existing second copy of the closure. |

**Genuinely new in this phase:** the perk-name-in-prose paragraph scanner (D-01 component 2), the D-05a adapter, the MCP server + harness invoker, `process_stage2_response()`, the confidence gate, the proposals sidecar writer, and the agent-run ledger. **Struck from the previous plan set and NOT to be rebuilt:** the Anthropic batch client, the `cache_control` prefix handling, `output_config.format` schema plumbing, and the dry-run dollar-cost estimator.

## The Mockable Seam

D-26 names `process_stage2_response()` as the shared handler; the previous plan's seam was `call_stage2_sync(..., client=None)`. For a subprocess+MCP transport the equivalent shape is:

```python
# scripts/stage2_transport.py
class Stage2Transport(Protocol):
    def run_chapter(self, chapter_num: str, system_prompt: str,
                    user_message: str, *, model: str) -> HarnessResult: ...

@dataclass
class HarnessResult:
    submitted: bool                 # <- the ONLY success signal
    submission: dict | None         # payload the handler received
    turns: int
    usage: dict                     # verbatim from --output-format json
    permission_denials: list[dict]
    duration_ms: int
    raw_envelope: dict

class ClaudeCliTransport:           # production
    """Starts/uses the warm loopback MCP server, invokes `claude -p`,
    and reports whether the handler received a submission."""

class RecordedTransport:            # tests
    """Returns a canned HarnessResult from a JSON fixture. No subprocess,
    no network, no MCP."""
```

and the entry point:

```python
def run_stage2_chapter(chapter_num: str, *, transport: Stage2Transport | None = None,
                       model: str = MODEL_CALIBRATION, ...) -> dict:
```

**Critical structural rule:** `process_stage2_response(chapter_num, submission, *, ctx) -> RoutingOutcome` must be importable and callable **with no transport, no MCP, and no subprocess** — it takes a plain dict and returns a routing outcome. The MCP tool handler is three lines calling it; `RecordedTransport` tests call it directly. That is what keeps the whole verify → grade → route → never-overwrite path testable with zero inference, and it is exactly what D-26 means by "thin transport over existing code."

`ctx` carries the warm objects (`prose_loader`, `directory_index`, `obtained_perks_index`, overrides doc path, proposals path, ledger) so the function is pure with respect to its inputs and trivially fixture-able.

## Failure Modes Unique to This Transport → Ledger States

The metered-API design had exactly two failure modes (HTTP error, malformed JSON). The subprocess+MCP design has eight. Each needs an explicit ledger state so an interrupted run restarts free (D-19/D-20).

| Failure | How it presents | Detection | Ledger state | Restart behaviour |
|---|---|---|---|---|
| **MCP server not connected in time** | Model says the tool doesn't exist; `is_error: false`; zero handler calls | `submitted == False` **and** `num_turns` low **and** zero `tools/list` on the server | `transport_error` | Retry. **Prevented** by the warm-HTTP design. |
| **Model finished without submitting** (answered in prose / refused) | `is_error: false`, `subtype: "success"`, `result` is prose | `submitted == False` | `no_submission` | Retry once with a stricter instruction; then leave unprocessed. Never write anything. |
| **Subprocess timeout / hang** | no exit within budget | wall-clock timeout on `subprocess.run(timeout=…)`; kill the process group | `timeout` | Retry. Recommended budget: 180 s/chapter (measured floor ~9 s, so this is ~20× headroom). |
| **Harness auth expiry** | non-zero exit or an auth error in the envelope | exit code ≠ 0, or `is_error: true` | `auth_error` | **Abort the whole run**, do not burn 79 more chapters. Surface to the operator. |
| **Partial submission** (some slots missing) | schema-valid payload, fewer rolls than Stage 1 slots | handler compares submitted `slot_index` set against the chapter's Stage 1 slots | `partial` **plus** the routing outcome | Not an error. Per D-12/§5 partial output is correct output → the missing slots are evidence-not-found and the chapter routes to proposals. |
| **Schema-invalid submission** | `jsonschema.ValidationError` at the tool boundary | SDK returns `isError: true` with the message; model may retry in-loop | (in-loop; only escalates if the run ends with `submitted == False`) | The correction signal is the point of D-26. Count retries in the ledger. |
| **Subscription rate limit / usage window** | envelope error or a stall | `is_error: true` with a rate-limit `api_error_status`; or repeated `no_submission` | `rate_limited` | **Abort the run**, record where it stopped, resume later from the ledger. This is D-29's real binding constraint. |
| **Concurrency limit** | some concurrent invocations fail while others succeed | correlated `rate_limited` across workers | `rate_limited` | Reduce concurrency. Start at **2**, raise only on evidence. |

**Governing rule for all of them:** the ledger entry is written **only after** the handler has routed successfully. An interrupted run leaves no partial ledger entry, so restart is a clean no-op for completed chapters and a fresh attempt for the rest — which is exactly D-29's "an interrupted run costs nothing to restart."

## Agent-Run Ledger (CINF-04 / D-19 / D-20)

**Location:** `data/derived/agent_run_ledger.json` (derived, regenerable-by-rerun, not hand-edited).
**Shape:** a keyed store, **not** an append-only journal — it is read before every chapter to answer "does this need reprocessing?" `persistence.py:_append_journal`'s per-session JSONL is the wrong shape (write-only, never read back); only its ISO-8601-UTC-with-`Z` timestamp convention transfers.

```json
{
  "schema_version": 1,
  "runs": {
    "92": {
      "fingerprint": "sha256:…",
      "run_id": "2026-08-03T14:22:07Z-…",
      "harness": "claude-cli",
      "harness_version": "2.1.220",
      "model": "opus",
      "prompt_version": "stage2-v1",
      "tool_surface_version": "stage2-tools-v1",
      "routed_to": "proposals",
      "confidence": {"high": 0, "low": 2},
      "state": "routed",
      "usage": { "...verbatim from the harness envelope..." },
      "duration_ms": 41230,
      "turns": 6,
      "read_set": [
        {"tool": "get_prose_span", "args": {"chapter_num": "92", "start_word": 8500, "end_word": 8900},
         "response_sha256": "…"}
      ],
      "started_at": "2026-08-03T14:21:26Z",
      "completed_at": "2026-08-03T14:22:07Z"
    }
  }
}
```

`read_set` is **audit metadata only** and is never an input to `fingerprint` (see Q3 consequence 1). `usage` is what makes D-29's run-size cap measurable.

**Skip rule:** reprocess chapter C **iff** `ledger.runs[C].fingerprint != compute_fingerprint(C)` **or** `ledger.runs[C].state != "routed"`. That, plus never-overwrite, is the whole of CINF-04.

## Proposals Sidecar (D-15 / D-17)

**Location:** `data/derived/agent_proposals.json`, with a registered schema at `data/derived/_schemas/agent_proposals.schema.json`.

**Why `data/derived/` and not `data/manual/`:** it is machine-produced and fully regenerable from a re-run; `data/manual/` is Dre's hand-authored territory and the corpus's home. Physical separation makes "never loaded as the trusted corpus" structural rather than a convention. Phase 5's TUI will read it explicitly by path; nothing else should.

**Schema shape.** `chapter_roll_overrides.schema.json` is deliberately permissive — `chapter_entry` requires only `curated_by` and `rolls`, and `rolls` is a bare `{"type": "array"}` `[VERIFIED: read from the schema]`. So D-15's "same roll-object schema" costs nothing: mirror the same loose array and add the Stage 2 sidecar block per roll.

```json
{
  "agent_proposals": {
    "<chapter_num>": {
      "curated_by": "agent",
      "rolls": [ { /* exact corpus roll shape */ } ],
      "_stage2": {
        "run_id": "...", "model": "...", "fingerprint": "...",
        "per_roll": [ {
          "slot_index": 0,
          "confidence": "low",
          "hard_pass": false,
          "structural_agreement": true,
          "constellation_check": "mechanical_agrees",
          "self_reported_confidence": "high",
          "reasoning": "...",
          "verify_issues": [ {"code": "...", "severity": "...", "message": "..."} ],
          "unfilled_fields": ["constellation"]
        } ]
      }
    }
  }
}
```

The corpus roll shape to mirror, read from a real curated entry `[VERIFIED: data/manual/chapter_roll_overrides.json ch 92]`: `perks, outcome, constellation, word_position, mention_chapter_num, mention_word_position, display_position_policy, skipped, source_ordinal, evidence_quotes[{text, mention_chapter_num, mention_word_position}], curator_note`.

**Serialization:** go through `_common.write_validated_json` (same call `chapter_roll_overrides_io` uses) — validated, atomic, `indent=2, ensure_ascii=False`, trailing newline. **Do not hand-roll a third JSON writer.** Note the repo has a known bug where `realign_chapters.py` writes `ensure_ascii=True` and causes unicode churn; don't reproduce it.

**D-17 obligation the planner must encode as a verification, not a hope:** proposals and corpus writes get the **same** assembly path. The gate reads `graded` and picks a destination; it must not be able to strip fields on the proposals branch. The cleanest structural guarantee: assemble the full roll object *once*, then route — never assemble twice.

## Confidence Gate (D-13 TIGHTENED)

Two-part composite, code-computed, per roll:

```
hard_pass            = verify_result["status"] == "pass"        # covers quote tiers AND perk resolution
structural_agreement = (perks agree with the Stage 1 bundle)
                       AND (outcome agrees)
                       AND (constellation_check != "mechanical_overrides")
                       AND (the Stage 1 candidate actually had a bundle to agree with)
confidence           = "high" if hard_pass and structural_agreement else "low"
```

- `self_reported_confidence` and `reasoning` are **carried into the output and never read by any conditional in this function.** The plan should include a test asserting that a `self_reported_confidence: "high"` roll with `status: "fail"` grades `low`, and that a `"low"` self-report with everything passing grades `high`.
- A fully-unfilled Stage 1 candidate (`_derivation.bundle_source is None`) has nothing to structurally agree with → `structural_agreement = False`, never `True` by default. **This is load-bearing:** Phase 3 measured 376 of 718 candidates as fully unfilled, so a permissive default here would hand ~52% of rolls a free pass.
- Reuse the verifier's `{code, severity, message}` issue vocabulary for gate rejections so Phase 5's TUI renders gate failures and verifier failures with one vocabulary.
- **D-16:** no config knob that weakens either term. If yield is low, that is the finding.
- **D-14:** the regime-boundary sensitivity check is a *measurement* over the held-out split (`is_boundary` chapters route low more often), never an input that forces a chapter low.
- **Route granularity:** per-chapter, not per-roll (a chapter is never split between corpus and proposals) — consistent with D-15's whole-chapter framing and with `curated_by` being chapter-level (Phase 3 D-01).

## Common Pitfalls

### Pitfall 1: Treating subprocess exit 0 as run success
**What goes wrong:** the pipeline records a chapter as processed when the model never submitted anything. **Why:** `claude -p` reports `is_error: false, subtype: "success"` for refusals, permission denials, and MCP-connection failures alike `[VERIFIED: local execution]`. **Avoid:** success == the handler received a schema-valid submission. **Warning signs:** `num_turns == 1`; non-empty `permission_denials`; a `result` string that reads like an apology.

### Pitfall 2: Trusting CLI flags to enforce the propose-only boundary
**What goes wrong:** an allowlist is assumed to bound what the model can do. **Why:** `--permission-mode bypassPermissions` ignores `--allowed-tools` entirely `[VERIFIED: local execution]`. **Avoid:** the server's exposed tool set is the boundary; flags are defense in depth. Use `dontAsk`, never `bypassPermissions`.

### Pitfall 3: Feeding `_prose_search_text` straight to `evidence_candidates`
**What goes wrong:** retrieval silently returns almost nothing and the phase looks like a model-quality problem. **Why:** epub HTML has no blank lines; 262 `<p>` tags collapse to 3 regex "paragraphs" `[VERIFIED: local execution]`. **Avoid:** the `paragraphized_prose_text` adapter. **Warning sign:** `len(evidence_candidates(...)) <= 3` for any chapter.

### Pitfall 4: Mixing TUI and verifier word offsets
**What goes wrong:** positions off by 571–18,760 words, presenting as model hallucination. **Avoid:** D-05a — `cp_word_index` only. **Warning sign:** `verify_roll` returning `position_out_of_tolerance` on quotes whose text matches exactly.

### Pitfall 5: Fingerprinting the transcript instead of the sources
**What goes wrong:** every run is its own key; idempotency becomes vacuous and D-20 silently fails. **Avoid:** hash the closed source-artifact set plus `prompt_version`, `tool_surface_version`, and `model`.

### Pitfall 6: Passing the prompt positionally after a variadic flag
**What goes wrong:** `Error: Input must be provided either through stdin or as a prompt argument when using --print`, despite a prompt being present. **Avoid:** always pipe on stdin `[VERIFIED: local execution — reproduced twice]`.

### Pitfall 7: Showing a calibration chapter its own exemplar
**What goes wrong:** calibration numbers are inflated and untrustworthy — the failure D-21 exists to prevent. **Avoid:** filter `target_chapter_num` out of `index["exemplars"]` before `query_exemplars.retrieve()`.

### Pitfall 8: Assembling proposals differently from corpus writes
**What goes wrong:** the value function inverts — a stripped proposal makes Dre start from blank. **Avoid:** assemble once, route after.

### Anti-patterns to avoid
- **An MCP tool that writes, routes, or names a destination.** Voids D-26.
- **A recorded multi-turn transcript fixture.** Brittle; record the submission payload instead.
- **A second prose/word-offset pipeline.** There are already two; a third is a phase failure.
- **`--bare`.** Forces metered auth, defeating D-25.
- **Chasing D-04's residual by lowering the retrieval threshold toward 1.** ~4× tokens for 2 points *less* recall than the union.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| MCP wire protocol + tool-input validation | A JSON-RPC stdio loop | `mcp.server.lowlevel.Server` (`validate_input=True`) | Protocol drift; the SDK validates with `jsonschema` and returns the `isError` correction signal D-26 depends on. |
| Paragraph scoring | A Stage-2 scorer | `evidence_scorer.evidence_candidates` | D-03; proven in the TUI. |
| Constellation extraction | A regex over the model's text | `quote_autofill.single_constellation_reference` | D-03; 14-item canonical list already exists. |
| Miss evidence retrieval | Generic keyword search | `miss_quote_matcher.find_miss_quote_candidates` | §4: misses have no perk anchor; this is the only module that knows that. |
| Quote matching tiers | A third matcher | `mechanical_verifier._prose_search_text` + `_build_tier2_pattern` | Exact-or-reject must be one implementation. |
| Prose loading + word index | A batch-local loader | `mechanical_verifier._build_prose_loader`'s closure shape | Two copies exist; a third violates D-03. |
| Perk name variants | A new alias table | `perk_name_resolver.load_perk_aliases` | `data/manual/perk_aliases.json` is the single source. |
| Validated atomic JSON write | `json.dumps` + `write_text` | `_common.write_validated_json` | Crash safety + schema enforcement for free. |
| Token/cost estimation | A tokenizer-based estimator | The harness's `usage` envelope | D-23/D-29: the estimator is struck; the envelope reports real usage. |

**Key insight:** this phase's failure mode is not "too little code" — it is **two implementations of the same thing disagreeing silently**. The measured 18,760-word offset divergence is that failure mode already latent in the repo.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---|---|---|---|---|---|---|
| `mcp` (pin `>=1.29,<2`) | PyPI | first release 2024-11-20; 66 releases; latest 2.0.0 on 2026-07-28 | PyPI publishes no download counts | `github.com/modelcontextprotocol/python-sdk` (Model Context Protocol, **a Series of LF Projects, LLC**) | **SUS** (seam) — reasons `too-new`, `unknown-downloads` | **Keep, pinned to 1.x.** `blocking-human` checkpoint T-04-05 **transfers here per D-27 and is NOT waived.** |
| `fastmcp` | PyPI | first release 2024-11-30; 110 releases; latest 3.4.5 on 2026-07-27 | none published | `github.com/PrefectHQ/fastmcp` | **SUS** (seam), same reasons | **REMOVED** — rejected on footprint (strict superset of `mcp` + ~25 packages); its ergonomic API is already bundled inside `mcp`. |
| `anthropic` | — | — | — | — | — | **REMOVED** — struck by D-25. Do not add. |

**Honest reading of the SUS verdicts.** `gsd-tools query package-legitimacy check --ecosystem pypi mcp fastmcp` returned `SUS` for both, with reasons `["too-new", "unknown-downloads"]` `[VERIFIED: seam execution]`. Both reasons are **artifacts of the seam's method against PyPI**, not real risk signals: `publishedAt` reflects the *latest* release (days old for any actively maintained package) rather than first publication, and PyPI simply does not expose download counts through the JSON API. The genuine provenance — Linux Foundation stewardship of `mcp`, 66 releases over 20 months, MIT, a real GitHub repo — is strong.

**This does not waive the checkpoint.** D-27 is explicit, and there is one real signal in the noise: `mcp` 2.0.0 genuinely *is* 5 days old and genuinely *is* a breaking major bump. Pinning `>=1.29,<2` is the response. `[VERIFIED: no postinstall equivalent applies — PyPI wheels for `mcp` are pure-Python; the compiled transitive is `cryptography`, a mainstream audited package.]`

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** `mcp`, `fastmcp` — `fastmcp` is removed on other grounds; `mcp` keeps the `checkpoint:blocking-human` as Plan 04-01 Task 1.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| `claude` CLI | D-25 inference transport | ✓ | 2.1.220 | `codex` CLI (worse MCP config story) |
| `codex` CLI | D-25 alternative | ✓ | codex-cli 0.145.0 | — |
| Python | pipeline | ✓ | 3.14 in `.venv` (constraint `>=3.11,<3.15`) | — |
| `mcp` PyPI package | D-26/D-27 MCP server | ✗ (not installed) | target `>=1.29,<2` | zero-dep stdio server (proven working, but rejected) |
| Source epub | prose/retrieval/verification | ✓ | `data/raw/Brocktons_Celestial_Forge.epub` | none — hard requirement |
| `data/derived/candidate_rolls.json` | Stage 2 input | ✓ | 718 candidates | none |
| `data/derived/roll_text_evidence.json` | prose windows | ✓ | present | none |
| `data/derived/exemplar_index.json` | D-05 | ✓ | 419 KB | none |
| `data/derived/obtained_perks.json`, `perk_directory.json` | perk resolution | ✓ | present | none |
| `data/manual/section_classifications.json` | CP word index | ✓ | present | none |
| `pytest`, `pytest-asyncio` | tests (async MCP handlers) | ✓ | in `dev` extra | — |
| Active Claude subscription auth | every inference call | ✓ (a live run succeeded in this session) | — | none — `auth_error` aborts the run |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `mcp` — install gated behind the T-04-05 checkpoint; the proven zero-dependency stdio server exists as a documented (rejected) fallback.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | `pytest` (+ `pytest-asyncio` for async MCP handlers) — both already in the `dev` extra |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-q"`) |
| Data isolation | `tests/conftest.py` copies `data/` into `tests/.tmp-data/data-<pid>/` at import time via `BCF_DATA_DIR` — **already active for every test**, so routing tests cannot touch the real corpus |
| Quick run | `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q` |
| Full suite | `.venv/bin/python scripts/verify.py` |

**Known-accepted baseline:** 5 pre-existing failures — 4 in `tests/test_forge_curator.py`, 1 in `tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`. `scripts/verify.py` exits 1 for that reason. **Judge by "no NEW failures", never by exit 0.**

### The core principle for this phase

**No live inference in the default test path — none, anywhere.** The transport is proven once by an explicitly-marked manual step in the tracer and never again in CI. Everything else is a pure function over a recorded submission payload.

### Phase Requirements → Test Map

| Req | Behavior | Test type | Automated command | Exists? |
|---|---|---|---|---|
| ACUR-01 | D-05a adapter: `word_starts_to_spans` starts are byte-identical to `_chapter_word_index`; `paragraphized_prose_text` preserves length | unit | `pytest tests/test_stage2_retrieval.py::test_adapter_offsets_match_cp_word_index -x` | ❌ Wave 0 |
| ACUR-01 | Adapter yields >3 paragraphs on a real chapter (regression guard for Pitfall 3) | unit (fixture HTML) | `pytest tests/test_stage2_retrieval.py::test_paragraph_segmentation -x` | ❌ Wave 0 |
| ACUR-01 | D-01 union includes miss-matcher output for every miss-outcome candidate | unit | `pytest tests/test_stage2_retrieval.py::test_union_includes_miss_candidates -x` | ❌ Wave 0 |
| ACUR-01 | Exemplar self-exclusion: target chapter never appears in its own prefix | unit | `pytest tests/test_stage2_prompt.py::test_target_chapter_excluded -x` | ❌ Wave 0 |
| ACUR-01 | `submit_stage2_rolls` `inputSchema` rejects a malformed payload (proves the D-26 guarantee) | unit — `jsonschema.validate` directly against the schema constant | `pytest tests/test_stage2_mcp_schema.py -x` | ❌ Wave 0 |
| ACUR-01 | The MCP tool handler is a thin delegate: calling it invokes `process_stage2_response` and nothing else | unit (async, monkeypatched) | `pytest tests/test_stage2_mcp_server.py::test_handler_delegates -x` | ❌ Wave 0 |
| ACUR-01 | **The server exposes no write/route/destination tool** (propose-only invariant) | unit — assert `{t.name for t in list_tools()} == {"submit_stage2_rolls","get_prose_span","check_quote"}` | `pytest tests/test_stage2_mcp_server.py::test_tool_surface_is_propose_only -x` | ❌ Wave 0 |
| ACUR-01 | Read tools record nothing and return no destination | unit | `pytest tests/test_stage2_mcp_server.py::test_read_tools_are_side_effect_free -x` | ❌ Wave 0 |
| ACUR-02 | Gate: pass + agreement → high, even with `self_reported_confidence: "low"` | unit | `pytest tests/test_stage2_confidence.py::test_self_report_never_promotes -x` | ❌ Wave 0 |
| ACUR-02 | Gate: verifier fail + `self_reported_confidence: "high"` → low | unit | same file | ❌ Wave 0 |
| ACUR-02 | Gate: `bundle_source is None` → `structural_agreement is False` even on a passing verify | unit | same file | ❌ Wave 0 |
| ACUR-02 | Gate: `constellation_check == "mechanical_overrides"` → low | unit | same file | ❌ Wave 0 |
| ACUR-03 | High-confidence chapter → corpus entry with `curated_by: "agent"` | integration (mocked transport, `BCF_DATA_DIR` isolation) | `pytest tests/test_stage2_routing.py::test_high_confidence_writes_corpus -x` | ❌ Wave 0 |
| ACUR-03 | Low-confidence chapter → proposals sidecar, validating against its schema | integration | `pytest tests/test_stage2_routing.py::test_low_confidence_writes_proposals -x` | ❌ Wave 0 |
| ACUR-03 (D-17) | Proposals and corpus branches receive **identical** assembled roll objects | unit | `pytest tests/test_stage2_routing.py::test_proposal_richness_equals_corpus -x` | ❌ Wave 0 |
| CINF-04 | A chapter with `curated_by: "human"` is NEVER written to corpus, whatever the confidence | integration | `pytest tests/test_stage2_routing.py::test_never_overwrites_human -x` | ❌ Wave 0 |
| CINF-04 (D-20) | Same inputs → same fingerprint; changing prose / candidates / `prompt_version` / `tool_surface_version` / `model` each changes it | unit (5 parametrized cases) | `pytest tests/test_stage2_ledger.py::test_fingerprint_covers_all_inputs -x` | ❌ Wave 0 |
| CINF-04 (D-20) | A chapter at an unchanged fingerprint is skipped and produces no diff | integration | `pytest tests/test_stage2_ledger.py::test_rerun_is_noop -x` | ❌ Wave 0 |
| CINF-04 | `read_set` is recorded but does **not** affect the fingerprint | unit | `pytest tests/test_stage2_ledger.py::test_read_set_not_in_fingerprint -x` | ❌ Wave 0 |
| CINF-04 | Every transport failure mode maps to its ledger state and writes no partial entry | unit (synthetic `HarnessResult`s) | `pytest tests/test_stage2_transport.py::test_failure_states -x` | ❌ Wave 0 |
| — | **Guard: no test constructs a live transport** | unit/grep | `! grep -rn "ClaudeCliTransport(" tests/` | ❌ Wave 0 |

### What each layer proves

- **The MCP `inputSchema`** proves shape only — that a submission is structurally well-formed. It proves nothing about correctness and is never a substitute for the gate (D-26 says exactly this). Test it directly against the schema constant with `jsonschema`; no server, no transport.
- **The recorded-submission fixture** proves the entire verify → grade → route → never-overwrite path. This is where the phase's real behavior lives and it needs zero inference.
- **Pure functions** (retrieval union, adapter, fingerprint, gate, ledger skip rule, proposals assembly) are directly unit-testable with synthetic fixtures, per the repo's established `build_*`/`verify_*` test convention.
- **Only these genuinely need a live harness**, and each is an explicitly-marked manual/checkpoint step, never a CI test: (1) the transport smoke test (server connects, a submission lands); (2) the tracer's one real chapter-92 run; (3) the D-28 Opus-vs-Sonnet calibration comparison; (4) the D-21/D-22 held-out measurement.

### Sampling Rate

- **Per task commit:** `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q`
- **Per wave merge:** `.venv/bin/python -m pytest -q` (compare failure set against the 5-failure baseline)
- **Phase gate:** `.venv/bin/python scripts/verify.py` — **no NEW failures** beyond the documented 5, before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_stage2_retrieval.py` — ACUR-01 (adapter, union, miss coverage)
- [ ] `tests/test_stage2_prompt.py` — ACUR-01 (exemplar self-exclusion, prefix composition)
- [ ] `tests/test_stage2_mcp_schema.py` — ACUR-01 (D-26 schema guarantee)
- [ ] `tests/test_stage2_mcp_server.py` — ACUR-01 (propose-only invariant, thin delegation, read-tool purity)
- [ ] `tests/test_stage2_confidence.py` — ACUR-02 (four gate cases)
- [ ] `tests/test_stage2_routing.py` — ACUR-03 + CINF-04 (corpus/proposals/never-overwrite/richness parity)
- [ ] `tests/test_stage2_ledger.py` — CINF-04 (fingerprint coverage, rerun no-op, read-set exclusion)
- [ ] `tests/test_stage2_transport.py` — failure-mode → ledger-state mapping
- [ ] `tests/fixtures/stage2_submission_ch92.json` — the recorded submission payload every downstream test drives from
- [ ] Framework install: none needed — `pytest` and `pytest-asyncio` are already in the `dev` extra

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | partial | Harness auth is the subscription's, not ours. **Never** pass `--bare` (forces `ANTHROPIC_API_KEY`). Treat `auth_error` as run-aborting. |
| V3 Session Management | no | `--no-session-persistence`; no sessions retained. |
| V4 Access Control | **yes** | The propose-only tool surface **is** the access-control boundary. Verified this session: `--permission-mode bypassPermissions` ignores `--allowed-tools`, so CLI flags cannot be the control. The server must expose no write/route tool; the handler is the sole writer. |
| V5 Input Validation | **yes** | `jsonschema.validate` at the MCP tool boundary (`Server.call_tool(validate_input=True)`); `_common.read_validated_json`/`write_validated_json` at every file boundary; `verify_roll()` as the semantic gate. |
| V6 Cryptography | partial | `hashlib.sha256` for fingerprints only — not a security control, an idempotency key. No hand-rolled crypto. |
| V13 API/Web Service | **yes** | The MCP server binds `127.0.0.1` on an ephemeral port and is torn down in a `finally`. Never `0.0.0.0`. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Model writes/overwrites hand-curated data through a tool | Tampering / Elevation | Propose-only surface + handler-side `curated_by` check before any write (CINF-04). Unit-tested as an invariant on the tool set. |
| Model picks its own destination (corpus vs proposals) | Elevation | No tool accepts or returns a destination; `route_and_write()` decides in code (D-26). |
| Hallucinated / paraphrased evidence enters the corpus | Tampering | `verify_roll()` exact-or-reject, Tier 1/2 only, no fuzzy path (Phase 2 D-13). `check_quote` is explicitly non-authoritative. |
| Self-reported confidence promotes a rejected roll | Tampering | D-13 TIGHTENED: self-report is never a routing input. Unit-tested. |
| Leaked MCP server left listening after a run | Information disclosure / Elevation | Loopback bind + ephemeral port + `finally` teardown; optional per-run bearer token. |
| Prompt injection from story prose into tool arguments | Tampering | Prose is untrusted input. Structural mitigation: the model cannot express a harmful action — the only expressible actions are "submit rolls", "read a bounded span", "check a quote". Every submitted value is re-derived or re-verified mechanically before it can affect anything. |
| Story prose leaking into committed artifacts | Information disclosure | Copyright constraint: proposals may carry evidence quotes (the established convention) but never bulk prose; `get_prose_span` responses are transient and are hashed, not stored, in the ledger. |
| Unbounded run consuming the subscription window | DoS (self-inflicted) | D-29: bounded chapter count, bounded concurrency (start at 2), ledger resumability, `usage` logged per chapter. |

## State of the Art

| Old approach (pre-2026-08-02 plans) | Current approach | Why |
|---|---|---|
| `anthropic` SDK + `client.messages.create()` | Subscribed `claude` CLI subprocess | D-25 — cost, not merit |
| Message Batches API, key by `custom_id` | Bounded-concurrency invocations + ledger resumability | D-25 — unreachable through this transport |
| `cache_control` on the shared prefix | Prefix still built once; caching is the harness's business | D-25 — not controllable |
| `output_config.format` JSON Schema | MCP `inputSchema` + `jsonschema.validate` at the tool boundary | D-26 — the guarantee moves layers |
| Dry-run token/cost estimator, `--ceiling-usd` | Run-size cap + the harness's `usage` envelope | D-29 — no per-token dollar cost to cap |
| `model="claude-opus-5"` parameter | `--model opus` harness flag | D-28 |

**Deprecated / do not build:** the batch client, the cost estimator, `cache_control` plumbing, `output_config.format` handling, `stage2_client.call_stage2_sync(client=…)`.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `--mcp-config` JSON accepts a `"headers"` key for HTTP servers (bearer-token hardening) | Integration Risk | Low — hardening is optional; loopback binding is the primary control. Executor confirms before relying on it. |
| A2 | Wall-clock projections for 80 chapters (16–30 min at concurrency 4) | Q3 consequence 2 | Medium — measured on trivial Sonnet payloads; real Opus runs with 20–40k-token prompts will be slower. Stated as a **lower bound**; the pilot re-measures. |
| A3 | `total_cost_usd` in the envelope is imputed accounting, not a subscription charge | Q3 consequence 2 | Low — it is used only as a *relative* usage proxy for run sizing, never as a budget. |
| A4 | Non-CP-section blanking is net-positive for retrieval | D-05a section | Low — measured token/noise reduction is real; the recall cost is unmeasured. Flagged as an explicit planner decision, not assumed. |
| A5 | Bounded concurrency of 2 is a safe starting point for subscription limits | Failure Modes | Low — conservative by construction; the ledger makes a throttled run free to resume. |
| A6 | The MCP startup race threshold sits between ~50 ms and ~500 ms | Integration Risk | Low — the *conclusion* (use warm HTTP) is verified regardless of where exactly the threshold sits. |
| A7 | `mcp` 1.x will remain maintained through this milestone | Q1 | Low — 2.x exists as the upgrade path; the SDK is LF-stewarded. |

## Open Questions

1. **Does `get_prose_span` actually move the needle on D-04's residual?**
   - Known: ~1 quote in 7 is unreachable by the D-01 union; the need is conditional on model reasoning, which is the textbook case for a read tool.
   - Unclear: whether the model uses it well, and whether recovered quotes verify.
   - Recommendation: ship it in the tracer with hard caps and **instrument it** (log calls/chapter and how many recovered quotes pass `verify_roll()`). Make keep-or-drop a data-driven call on the calibration split, exactly like D-28's tiering decision. Per D-04 this must not become a recall-chasing loop.

2. **Opus vs Sonnet for the bulk pass (D-28).**
   - Known: calibrate on Opus; step down only on evidence; never Haiku.
   - Unclear: whether Sonnet clears the same verifier + gate bar.
   - Recommendation: unchanged from D-28 — decide on the held-out split, not on price (there is no price now).

3. **Retrieval threshold tuning (D-02).**
   - Known: threshold 3 is the measured knee (85.5% recall in union with perk-name match, ~363k tokens).
   - Unclear: whether the optimum shifts once the D-05a adapter changes what "a paragraph" means — the paragraph segmentation this research introduces is not the segmentation the 85.5% figure was measured against.
   - Recommendation: **re-measure the union's recall under the new adapter before trusting the 85.5% number.** Flag this to the planner as a small measurement task inside the tracer, not a separate plan.

4. **Whether `claude` handles concurrent invocations gracefully on a subscription.**
   - Known: single invocations work; the envelope surfaces rate-limit status.
   - Unclear: the concurrency ceiling.
   - Recommendation: start at 2, raise on evidence, treat `rate_limited` as run-aborting-and-resumable.

## Code Examples

### Warm propose-only server + per-run harness invocation (shape verified end-to-end)

```python
# 1) Start ONE warm server for the whole run.
#    (mcp.server.fastmcp.FastMCP shown for brevity; production uses the
#     low-level Server + explicit inputSchema for strict validation.)
server = build_stage2_server(ctx)          # holds warm prose_loader/index caches
port = pick_ephemeral_port()
proc = start_http_server(server, host="127.0.0.1", port=port)   # streamable-http
mcp_config = json.dumps({"mcpServers": {"bcf": {
    "type": "http", "url": f"http://127.0.0.1:{port}/mcp"}}})

try:
    for chapter_num in chapters:
        if ledger.is_current(chapter_num, compute_fingerprint(chapter_num)):
            continue                                    # D-20: no diff, no work
        ctx.begin_chapter(chapter_num)                  # handler knows which chapter
        result = subprocess.run(
            ["claude", "-p",
             "--strict-mcp-config", "--mcp-config", mcp_config,
             "--output-format", "json",
             "--model", model,                          # D-28
             "--permission-mode", "dontAsk",
             "--tools", "",
             "--system-prompt", shared_prefix,
             "--no-session-persistence",
             "--allowed-tools",
             "mcp__bcf__submit_stage2_rolls",
             "mcp__bcf__get_prose_span",
             "mcp__bcf__check_quote"],
            input=user_message, capture_output=True, text=True, timeout=180,
        )
        envelope = json.loads(result.stdout)
        outcome = ctx.take_chapter_outcome(chapter_num)  # handler-side state
        if outcome is None:                              # NOT result.returncode!
            ledger.record_failure(chapter_num, state="no_submission", envelope=envelope)
            continue
        ledger.record(chapter_num, outcome, envelope=envelope)
finally:
    proc.terminate()                                     # never leak the server
```

### The propose-only tool handler (D-26 — the whole guarantee in five lines)

```python
@server.call_tool()                      # validate_input=True → jsonschema at the boundary
async def call_tool(name: str, arguments: dict):
    if name == "submit_stage2_rolls":
        outcome = process_stage2_response(          # verify → grade → route, in code
            arguments["chapter_num"], arguments["rolls"], ctx=ctx,
        )
        return [types.TextContent(type="text", text=outcome.model_facing_summary)]
    if name == "get_prose_span":
        return [types.TextContent(type="text", text=ctx.prose_span(**arguments))]
    if name == "check_quote":
        return [types.TextContent(type="text", text=json.dumps(ctx.dry_run_quote(**arguments)))]
    raise ValueError(f"unknown tool: {name}")
```

`outcome.model_facing_summary` must state *what was accepted*, never *where it went* — the model must not learn the destination, or the next turn's proposals will be steered by it.

## Sources

### Primary (HIGH confidence)
- **Local execution, this session (2026-08-02):** `claude` CLI 2.1.220 driven against a hand-written zero-dependency stdio MCP server and against an `mcp`-SDK server on both stdio and loopback HTTP; six distinct runs covering success, prose-invite, permission-denial, refusal, and the startup race. Startup-race isolation test with an artificial 1.5 s delay.
- **Local execution:** the real epub + `cp_word_index`, `mechanical_verifier`, `evidence_scorer`, `data_loader` run over chapters 1, 92, 104, 121.1 to measure both offset spaces and validate the adapter.
- **Source read:** `mcp/server/lowlevel/server.py` `call_tool` in an installed 1.29.0 — the `jsonschema.validate` / `_make_error_result` path.
- **PyPI JSON API:** metadata and full dependency graphs for `mcp` 1.29.0 / 2.0.0, `mcp-types`, `fastmcp`, `fastmcp-slim`; `pip install --dry-run --report` resolutions.
- **`claude --help`, `claude mcp --help`, `codex --help`, `codex exec --help`** read locally.
- **Repo source:** `pyproject.toml`, `evidence_scorer.py`, `cp_word_index.py`, `mechanical_verifier.py`, `chapter_roll_overrides_io.py`, `query_exemplars.py`, `build_candidate_rolls.py`, `data_loader.py`, `chapter_roll_overrides.schema.json`, `tests/conftest.py`, `candidate_rolls.json`, `chapter_roll_overrides.json`.
- **`gsd-tools query package-legitimacy check --ecosystem pypi mcp fastmcp`.**

### Secondary (MEDIUM confidence)
- `modelcontextprotocol.io/specification/2025-06-18/server/tools` — Security Considerations (servers MUST validate all tool inputs), tool result / error shapes, `outputSchema` semantics.

### Tertiary (LOW confidence)
- Wall-clock extrapolation to 80 chapters — arithmetic over five measured runs on trivial payloads. Explicitly a lower bound (A2).

## Metadata

**Confidence breakdown:**
- Package selection & provenance: **HIGH** — registry metadata and dependency graphs resolved directly; SDK installed and introspected.
- Harness integration: **HIGH** — every flag read from `--help` locally and the full path executed end-to-end, including three reproduced failure modes.
- D-05a adapter: **HIGH** — written and run against the real epub; offsets byte-verified against the canonical tokenizer on four chapters.
- Reuse audit: **HIGH** — every signature read from source.
- Confidence gate & routing: **HIGH** — inherited from D-13 TIGHTENED and Phase 2's proven verifier; nothing novel.
- Throughput / usage-window projections: **MEDIUM** — measured, but on trivial payloads.
- `get_prose_span` value: **LOW** — a reasoned bet, explicitly instrumented for a data-driven keep-or-drop.

**Research date:** 2026-08-02
**Valid until:** 2026-09-01 for the pipeline findings (stable, in-repo). **2026-08-16** for the harness-integration findings — `claude` CLI ships frequently and both the flag surface and the MCP-connection timing are version-sensitive; re-verify the transport smoke test if the CLI has moved before Phase 4 executes.

