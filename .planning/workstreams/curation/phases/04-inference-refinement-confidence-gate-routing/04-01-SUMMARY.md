---
phase: 04-inference-refinement-confidence-gate-routing
plan: 01
status: stopped
outcome: stopped-by-decision
completed_tasks: 3
total_tasks: 3
date: 2026-08-03
---

# Plan 04-01 — Summary

**Status: STOPPED at Dre's decision.** All three tasks executed and committed. At Task 3's
`checkpoint:decision` — "does this actually save you work?" — Dre answered **no**. Stage 2 is
parked. This document exists so the state is legible if anyone returns to it.

## What was built and committed

| Task | Commit | What |
|---|---|---|
| 1 | `ed31a1e` | Propose-only MCP server on warm loopback HTTP + `claude -p` transport |
| 2 | `ec29ed3` | Prose adapter, prompt assembly, mechanical position derivation, proposals writer |
| 3 | `f2d60ac` | Batch runner + first real run on 5 curated chapters |

New modules, all under `scripts/`: `stage2_schema.py`, `stage2_mcp_server.py`,
`stage2_transport.py`, `stage2_prose.py`, `stage2_prompt.py`, `stage2_response.py`,
`stage2_proposals_io.py`, `run_stage2_chapter.py`. Plus
`data/derived/_schemas/agent_proposals.schema.json` and three test files.
`pyproject.toml` gained a `curation` optional extra carrying `mcp>=1.29,<2`.

## What the run actually showed

5 hand-curated chapters (92, 104, 88, 81, 36), opus, concurrency 2, 42–107s each.

**Quote finding worked.** 52 quotes proposed, all 52 located in real prose at verifier Tier 1.
Zero hallucinated. Zero rolls left without evidence. On ch 104 it reproduced Dre's curated rolls at
byte-identical word positions (2861, 2986, 8440, 8613) and correctly declined the CURATION-CONVENTIONS
§5 Entrance Hall trap, flagging per-unit evidence gaps rather than attaching the `Aisha`/`Tetra`/`Tybalt`
mentions thousands of words upstream.

**Roll structure did not.** Hit/miss and constellation assignment diverged from the corpus on two of
five chapters:

- **ch 81** — proposed five `hit / Personal Reality` rolls where the corpus has misses (Magitech,
  Knowledge, Vehicles, Quality). Quote overlap 7/13. A genuine misread, not a boundary quibble.
- **ch 88** — 16/17 proposed quotes overlap curated passages, but called 5 hits against 2 curated.
- **ch 36** — corpus leaves outcome and constellation `null` on 7 of 8 rolls; no ground truth to score against.

Exact position matches were 12/52, almost entirely boundary width — it starts a quote a clause early
("As Tetra was pondering the possibilities I felt the Forge move again…" vs the curated
"I felt the Forge move again…"). Distinct from, and much smaller than, the ch 81 problem.

## Decisions recorded at the stop

- **Stop Stage 2** (Dre, 2026-08-03). Quote finding solved the tedious half; structure assignment did
  not, and the phase had already consumed disproportionate planning effort across three attempts (five
  plans against a metered API, six against the subscribed harness, one after descope). The judgment is
  about total cost-to-date, not about this run's numbers in isolation.
- **`get_prose_span` is dead weight** (Dre, 2026-08-03). 1 call across the entire run, 3 verified
  quotes. Verdict: delete. **Not executed** — removing code from a workstream that was just parked is
  the kind of busywork the stop was meant to end. Recorded here so a resumer does not have to re-derive it.
- **`check_quote` is the tool that mattered.** 50 calls, and almost certainly why nothing was lost —
  the model iterated toward exact prose before submitting, the same move a human makes with the TUI
  search. If Stage 2 is ever revived, this is the piece to keep.
- **Open ruling, never made:** on ch 104 the model submitted 3 rolls where Stage 1 predicted 1,
  including a Knowledge miss present in neither Stage 1 nor the corpus. The handler currently accepts
  slot indices with no Stage 1 candidate. Left accepting, since Stage 1 is known to under-predict ch 104.

## State of the repo

- **`data/manual/chapter_roll_overrides.json` is byte-unchanged.** Verified with
  `git diff --exit-code`. No Stage 2 module imports `write_chapter_roll_overrides_doc` — the
  guarantee is structural, not test-asserted, and `grep` proves it.
- **Full suite: 691 passed**, failure set exactly the documented 5-failure baseline (4 in
  `tests/test_forge_curator.py`, 1 in `tests/test_roll_ordinal_contract.py`). No new failures.
- **`mcp` is isolated** behind the `curation` extra. `verify.py`, the Forge Curator TUI, and the
  derived-data pipeline all run on a base install and are unaffected.
- `data/derived/agent_proposals.json` holds the run's output for those 5 chapters. They are already
  hand-curated, so it has no curation value — it is evidence of what the run did, nothing more.

## Where everything lives now (updated 2026-08-03)

Dre asked for the code parked off `main` so future agents can't mistake it for a foundation, and for
the quotes preserved as a durable reference. Both done:

| What | Where |
|---|---|
| The implementation (8 modules, 3 test files, schema, `mcp` dependency) | Branch **`parked/stage2-inference`**, pushed to `origin`. Removed from `main`. |
| The 52 verified quotes, per chapter and per roll | **`docs/stage2_agent_curation_trial_2026-08.md`** on `main` |
| Measured transport findings, the D-05a/D-33 adapter, the pitfalls | `04-RESEARCH.md` (carries a ⛔ STOPPED banner) |

`data/derived/agent_proposals.json` was gitignored and has been deleted — its substance is in the
`docs/` file. The `curation` optional extra is gone from `pyproject.toml`, so `mcp` is no longer a
dependency of this repo on any branch but the parked one.

To restore the code: `git checkout parked/stage2-inference -- scripts/stage2_*.py scripts/run_stage2_chapter.py tests/test_stage2_*.py tests/fixtures/stage2_submission_sample.json data/derived/_schemas/agent_proposals.schema.json`, then re-add `curation = ["mcp>=1.29,<2"]` to `pyproject.toml`.

The honest read on what was learned: **the retrieval-plus-verify half is sound and the structural-
inference half is not.** Anyone resuming should not re-plan the transport — it works, it is measured,
and `04-RESEARCH.md` records the flags and the two failure modes that matter (stdio loses a startup
race; subprocess exit 0 does not mean success). The unsolved problem is teaching hit/miss and
constellation assignment, which is a prompt and exemplar problem, not a plumbing problem.
