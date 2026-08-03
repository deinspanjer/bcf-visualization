# Phase 4 — MCP Tool-Surface Decision Matrix

**Decided:** 2026-08-02 (planner, from `04-CONTEXT.md` D-26/D-30 and `04-RESEARCH.md` §Q3)
**Scope:** the propose-only MCP server this phase builds (`scripts/stage2_mcp_server.py`)

This phase integrates **no metered external API**. That is the whole point of D-25: inference rides
an already-subscribed `claude` CLI, and no vendor SDK enters `pyproject.toml`. The API-coverage
gate's three detector signals were two struck decisions (the Batches API, the vendor SDK) and the
MCP server built here. This file is therefore the **decided tool-surface record** for that server,
not a vendor-API coverage matrix.

**Default is INTEGRATE.** Every `OPT-OUT` carries a one-line reason.

## The decided surface

D-30 fixes the Phase 4 surface at **exactly three tools**. "Propose-only" binds *write authority*,
not information flow — every one of D-26's three prohibitions names a write or a destination choice,
and a read tool can do neither.

| capability | decision | reason |
|---|---|---|
| `submit_stage2_rolls(chapter_num, rolls[])` | INTEGRATE | The only delivery channel. Its handler runs derive → `verify_roll()` → `grade_roll()` → `route_and_write()` and decides the destination in code. Tool inputs are JSON-Schema-validated by `Server.call_tool(validate_input=True)`, which is what carries D-08's never-free-text-then-parse guarantee after D-25 removed `output_config.format`. |
| `get_prose_span(chapter_num, start_word, end_word)` | INTEGRATE | Reaches D-04's residual quotes that live outside the retrieved union, where *which* span is needed is only knowable after the model reads the candidates. Hard caps: ≤400 CP words per span, ≤5 calls per chapter. **The one LOW-confidence element of the design — instrumented for a data-driven keep-or-drop on the calibration split (Plan 04-05 T3).** Do not tune the caps upward to chase recall. |
| `check_quote(chapter_num, quote_text)` | INTEGRATE | Non-authoritative dry run of the Tier-1/Tier-2 quote search, returning `{found, tier, word_position, occurrence_count}` and recording nothing. Turns a near-miss quote into a correct one before submission — a direct hit on the value function. Cap ≤20 calls per chapter. This is not tuning to the verifier: the verifier is exact-or-reject over real prose, so iterating toward an exact substring is the desired behavior and is literally what a human curator does with the TUI search. It cannot loosen the gate, because the gate re-runs `verify_roll()` on submission regardless. |
| `get_candidate_paragraphs(chapter_num)` | OPT-OUT | Pre-loaded — always needed and bounded (~1.8k tokens/chapter); a round trip buys nothing. |
| `get_exemplars(regime, k)` | OPT-OUT | Pre-loaded in the shared prefix per D-05; `exemplar_index.json` (419 KB) must never be reachable whole. |
| `resolve_perk_name(raw_name)` | OPT-OUT | Pre-loaded; the resolution ladder is the handler's job on submission, not the model's. |
| `get_chapter_facts` / `get_obtained_perks` | OPT-OUT | Tiny per chapter — pre-loaded. |
| TUI / curation-state reads (chapters needing curation, current overrides, session journal) | OPT-OUT | Phase 5+; in Phase 4 they would let the model see the hand-curated corpus it is proposing against (calibration contamination). |
| any `write_*` / `route_*` / destination-returning tool | OPT-OUT | Voids D-26's propose-only guarantee and PROJECT.md's curation-authority constraint. |
| `set_confidence` or any tool accepting a confidence value | OPT-OUT | Confidence is code-computed (D-13 TIGHTENED); a model-settable confidence would make self-report a routing input. |
| any tool reading `chapter_roll_overrides.json` | OPT-OUT | Named explicitly in D-30 as excluded; it is both a contamination surface and a step toward the model knowing its destination. |
| `get_stage1_derivation(chapter_num, slot_index)` | OPT-OUT | Pre-loaded with the candidate object; a round trip buys nothing and the `_derivation` block is what `structural_agreement` reads in code, not what the model reasons over. |
| `list_chapters` / `get_run_status` / any ledger read | OPT-OUT | Run bookkeeping is the pipeline's; exposing it would let the model observe idempotency state, which is an input to nothing it should influence. |
| `report_progress` / `log_note` or any tool with a side effect on pipeline state | OPT-OUT | D-30 requires read tools to record nothing the gate later consults; a logging tool is a recording tool. |
| bearer-token auth header on the loopback transport | OPT-OUT (optional hardening, not required) | Loopback bind plus an ephemeral port is the primary control. `claude mcp add --transport http --header` confirms headers are supported, but the corresponding `--mcp-config` JSON key is `[ASSUMED]` to be `"headers"` and must be confirmed before being relied on (research assumption A1). |

## Enforcement

The surface is enforced by **what the server exposes**, never by CLI flags. This is measured, not
assumed: with `--permission-mode bypassPermissions` the harness successfully called an MCP tool that
was absent from `--allowed-tools`. Production uses `--permission-mode dontAsk` (which does enforce)
as defense in depth only.

`tests/test_stage2_mcp_server.py::test_tool_surface_is_propose_only` asserts the exposed set by
equality against `{submit_stage2_rolls, get_prose_span, check_quote}`, so adding a fourth tool fails
the suite rather than passing review.

## Fingerprint consequence

Read tools mean a run's inputs are no longer a static set, so `compute_fingerprint` covers the
**closed set of source artifacts the read tools could possibly serve** — a superset, never a subset —
and gains `tool_surface_version` alongside `prompt_version` and `model`. Changing what
`get_prose_span` returns changes achievable output exactly as much as a prompt edit does. The
tool-call transcript is never fingerprinted; the read-set is recorded in the ledger as audit metadata
only (Plan 04-04 T1).
