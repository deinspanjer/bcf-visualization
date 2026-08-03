---
phase: 4
slug: inference-refinement-confidence-gate-routing
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` § Validation Architecture. Supersedes the pre-D-25 draft,
> which assumed a metered API and a mocked `anthropic` client.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + `pytest-asyncio` (async MCP handlers) — both already in the `dev` extra, no install needed |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-q"`) |
| **Quick run command** | `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q` |
| **Full suite command** | `.venv/bin/python scripts/verify.py` |
| **Estimated runtime** | ~120s full suite |
| **Data isolation** | `tests/conftest.py` copies `data/` to `tests/.tmp-data/data-<pid>/` via `BCF_DATA_DIR` at import time — already active, so routing tests cannot touch the real corpus |

---

## The core principle for this phase

**No live inference in the default test path — none, anywhere.** The transport is proven once
by an explicitly-marked manual step in the tracer, and never again in CI. Everything downstream
is a pure function over a *recorded submission payload*.

Do **not** build a recorded multi-turn transcript fixture — with read tools in the surface a
transcript replay is brittle and buys nothing. Record only the final submission payload and
drive `process_stage2_response()` with it.

---

## Sampling Rate

- **After every task commit:** `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q`
- **After every plan wave:** `.venv/bin/python -m pytest -q` — compare the failure set against the baseline below
- **Before `/gsd-verify-work`:** `.venv/bin/python scripts/verify.py` — **no NEW failures**
- **Max feedback latency:** ~120 seconds

### Known-accepted failure baseline (do NOT chase)

5 pre-existing failures: 4 in `tests/test_forge_curator.py`, 1 in
`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`.
`scripts/verify.py` exits 1 for that reason. **Judge by "no NEW failures", never by exit 0.**

---

## Per-Task Verification Map

Task IDs filled by the planner. Behaviors and commands are fixed by research and must be preserved.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-02-T1 | 04-02 | 2 | ACUR-01 | T-04-13 | D-05a adapter starts byte-identical to `_chapter_word_index`; length preserved | unit | `pytest tests/test_stage2_retrieval.py::test_adapter_offsets_match_cp_word_index -x` | ❌ W0 | ⬜ pending |
| 04-02-T1 | 04-02 | 2 | ACUR-01 | T-04-14 | Adapter yields >3 paragraphs on a real chapter (Pitfall 3 regression guard) | unit | `pytest tests/test_stage2_retrieval.py::test_paragraph_segmentation -x` | ❌ W0 | ⬜ pending |
| 04-02-T2 | 04-02 | 2 | ACUR-01 | — | D-01 union includes miss-matcher output for every miss-outcome candidate | unit | `pytest tests/test_stage2_retrieval.py::test_union_includes_miss_candidates -x` | ❌ W0 | ⬜ pending |
| 04-02-T2 | 04-02 | 2 | ACUR-01 | T-04-15 | Exemplar self-exclusion: target chapter never appears in its own prefix | unit | `pytest tests/test_stage2_prompt.py::test_target_chapter_excluded -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | T-04-05 | `submit_stage2_rolls` `inputSchema` rejects a malformed payload (the D-26 guarantee) | unit | `pytest tests/test_stage2_mcp_schema.py -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | MCP tool handler is a thin delegate — invokes `process_stage2_response` and nothing else | unit (async) | `pytest tests/test_stage2_mcp_server.py::test_handler_delegates -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | T-04-01 | **Server exposes no write/route/destination tool** (propose-only invariant) | unit | `pytest tests/test_stage2_mcp_server.py::test_tool_surface_is_propose_only -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | T-04-02 | Read tools record nothing and return no destination | unit | `pytest tests/test_stage2_mcp_server.py::test_read_tools_are_side_effect_free -x` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 2 | ACUR-02 | T-04-04 | Gate: pass + agreement → high even with `self_reported_confidence: "low"` | unit | `pytest tests/test_stage2_confidence.py::test_self_report_never_promotes -x` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 2 | ACUR-02 | T-04-04 | Gate: verifier fail + self-report "high" → low | unit | `pytest tests/test_stage2_confidence.py -x` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 2 | ACUR-02 | T-04-16 | Gate: `bundle_source is None` → `structural_agreement False` even on passing verify | unit | `pytest tests/test_stage2_confidence.py -x` | ❌ W0 | ⬜ pending |
| 04-03-T1 | 04-03 | 2 | ACUR-02 | — | Gate: `constellation_check == "mechanical_overrides"` → low | unit | `pytest tests/test_stage2_confidence.py -x` | ❌ W0 | ⬜ pending |
| 04-03-T3 | 04-03 | 2 | ACUR-03 | T-04-01 | High-confidence chapter → corpus entry with `curated_by: "agent"` | integration | `pytest tests/test_stage2_routing.py::test_high_confidence_writes_corpus -x` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 1 | ACUR-03 | — | Low-confidence chapter → proposals sidecar, validating against its schema | integration | `pytest tests/test_stage2_routing.py::test_low_confidence_writes_proposals -x` | ❌ W0 | ⬜ pending |
| 04-03-T2 | 04-03 | 2 | ACUR-03 | T-04-17 | D-17: proposals and corpus branches receive **identical** assembled roll objects | unit | `pytest tests/test_stage2_routing.py::test_proposal_richness_equals_corpus -x` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 1 | CINF-04 | T-04-01 | A `curated_by: "human"` chapter is NEVER written to corpus, whatever the confidence | integration | `pytest tests/test_stage2_routing.py::test_never_overwrites_human -x` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04-04 | 3 | CINF-04 | T-04-19 | D-20: prose / candidates / `prompt_version` / `tool_surface_version` / `model` each change the fingerprint | unit (5 params) | `pytest tests/test_stage2_ledger.py::test_fingerprint_covers_all_inputs -x` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04-04 | 3 | CINF-04 | T-04-19 | D-20: a chapter at an unchanged fingerprint is skipped and produces no diff | integration | `pytest tests/test_stage2_ledger.py::test_rerun_is_noop -x` | ❌ W0 | ⬜ pending |
| 04-04-T1 | 04-04 | 3 | CINF-04 | T-04-08 | `read_set` is recorded but does **not** affect the fingerprint | unit | `pytest tests/test_stage2_ledger.py::test_read_set_not_in_fingerprint -x` | ❌ W0 | ⬜ pending |
| 04-04-T2 | 04-04 | 3 | CINF-04 | T-04-11 | Every transport failure mode maps to its ledger state and writes no partial entry | unit | `pytest tests/test_stage2_transport.py::test_failure_states -x` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 1 | — | T-04-05 | **Guard: no test constructs a live transport** | grep | `! grep -rn "ClaudeCliTransport(" tests/` | ❌ W0 | ⬜ pending |
| 04-04-T3 | 04-04 | 3 | CINF-04 | T-04-20 | `--allow-uncurated` defaults to refusing; no in-repo caller passes it | unit + grep | `pytest tests/test_stage2_transport.py -q` and `grep -rn 'allow_uncurated' scripts/ \| grep -v run_stage2_batch.py` | ❌ W0 | ⬜ pending |
| 04-04-T3 | 04-04 | 3 | ACUR-01 | T-04-06 | The warm MCP server is torn down even when the batch body raises | unit | `pytest tests/test_stage2_transport.py -q` | ❌ W0 | ⬜ pending |
| 04-05-T2 | 04-05 | 4 | ACUR-02 | T-04-15 | The calibration/held-out split is deterministic, disjoint, and re-derives the stub set | unit | `pytest tests/test_stage2_calibration_split.py -q` | ❌ W0 | ⬜ pending |
| 04-06-T2 | 04-06 | 5 | ACUR-01 | T-04-23 | Stage 2 is scored on Phase 3's three-tier curated-position ladder, per evidence class | unit | `pytest tests/test_measure_stage2_accuracy.py -q` | ❌ W0 | ⬜ pending |
| 04-06-T3 | 04-06 | 5 | ACUR-02 | T-04-24 | `is_boundary` is a measurement partition only and is consulted by no routing module | unit + grep | `pytest tests/test_measure_stage2_accuracy.py -q` and `grep -rn 'is_boundary' scripts/stage2_confidence.py scripts/stage2_routing.py scripts/stage2_response.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### What each layer proves

- **The MCP `inputSchema`** proves *shape only* — that a submission is structurally well-formed.
  It proves nothing about correctness and is never a substitute for the confidence gate (D-26 says
  exactly this). Test it directly against the schema constant with `jsonschema`; no server, no transport.
- **The recorded-submission fixture** proves the entire verify → grade → route → never-overwrite
  path. This is where the phase's real behavior lives, and it needs zero inference.
- **Pure functions** (retrieval union, D-05a adapter, fingerprint, gate, ledger skip rule, proposals
  assembly) are directly unit-testable with synthetic fixtures, per the repo's `build_*`/`verify_*`
  test convention.

---

## Wave 0 Requirements

- [ ] `tests/test_stage2_mcp_schema.py` — ACUR-01 (the D-26 schema guarantee) — **Plan 04-01 T2**
- [ ] `tests/test_stage2_mcp_server.py` — ACUR-01 (propose-only invariant, thin delegation, read-tool purity, cap boundaries) — **Plan 04-01 T2**
- [ ] `tests/test_stage2_routing.py` — ACUR-03 + CINF-04 (proposals landing, never-overwrite) — **Plan 04-01 T3**; extended with corpus write, richness parity and the agent-rewrite case in **Plan 04-03 T2/T3**
- [ ] `tests/fixtures/stage2_submission_ch92.json` — the recorded submission payload every downstream test drives from — **Plan 04-01 T3**
- [ ] `tests/test_stage2_retrieval.py` — ACUR-01 (D-05a adapter, D-01 union, dedupe/order/empty) — **Plan 04-02 T1/T2**
- [ ] `tests/test_stage2_prompt.py` — ACUR-01 (exemplar self-exclusion, prefix composition) — **Plan 04-02 T2**
- [ ] `tests/test_stage2_confidence.py` — ACUR-02 (four gate cases, self-report inertness) — **Plan 04-03 T1**
- [ ] `tests/test_stage2_ledger.py` — CINF-04 (fingerprint coverage, rerun no-op, read-set exclusion) — **Plan 04-04 T1**
- [ ] `tests/test_stage2_transport.py` — failure-mode → ledger-state mapping, uncurated guard, server teardown — **Plan 04-04 T2/T3**
- [ ] `tests/test_stage2_calibration_split.py` — ACUR-02 (deterministic, disjoint, re-derived stub set) — **Plan 04-05 T2**
- [ ] `tests/test_measure_stage2_accuracy.py` — ACUR-01/ACUR-02 (position ladder, class denominators, boundary partition) — **Plan 04-06 T2/T3**
- [ ] Framework install: **none needed** — `pytest` and `pytest-asyncio` are already in the `dev` extra

---

## Manual-Only Verifications

Only these four genuinely require a live harness. Each is an explicitly-marked manual or
checkpoint step, never a CI test.

| Task ID | Behavior | Requirement | Why Manual | Test Instructions |
|---------|----------|-------------|------------|-------------------|
| 04-01-T1 | Package-legitimacy gate for `mcp>=1.29,<2` (threat T-04-05) | ACUR-01 | Supply-chain judgement a seam cannot make; D-27 explicitly does not waive it, and it is never auto-approvable | `checkpoint:human-verify` `gate="blocking-human"` **before** any install; confirm LF stewardship, release history, MIT license and the 1.x pin on `pypi.org/project/mcp` |
| 04-01-T2 | Transport smoke test — warm loopback HTTP MCP server connects and a submission lands | ACUR-01 | Requires a live subscribed harness; retires the D-25/D-26 integration risk before pipeline code exists | `scripts/stage2_mcp_server.py --smoke-test` starts the server on the loopback interface at an ephemeral port, invokes `claude -p` per the researched flag set, and asserts **handler-side state** (a valid submission arrived) — never the subprocess exit code |
| 04-01-T3 | Tracer's one real end-to-end run on a single curated chapter | ACUR-01/02/03 | The tracer's whole point is that the real transport is exercised, not stubbed | `scripts/run_stage2_chapter.py --chapter 92 --model opus`; verify the proposals entry landed, the corpus diff is empty, and the `usage` block was recorded |
| 04-05-T1 | Calibration run-size approval | ACUR-02 | Consumes Dre's subscription usage window; D-29 re-framed this from a dollar approval to a run-size approval | `checkpoint:decision`; present calibration-side chapter count, measured per-chapter wall clock and `usage` from 04-01, and projected totals per tier |
| 04-05-T3 | D-28 Opus-vs-Sonnet comparison | ACUR-02 | Model-tiering must be data-driven, not asserted; requires two live runs over identical inputs | Operator-invoked at the approved size; recommendation is provisional until 04-06 confirms it on held-out |
| 04-06-T1 | Held-out run-size approval and end-of-tuning confirmation | ACUR-01/02 | Reading held-out is a once-only act; after it, no parameter may change | `checkpoint:decision`; present the three calibration verdicts with their numbers and the held-out chapter and `is_boundary` counts |
| Phase 5 | D-24 approval before the first run against **uncurated** chapters | ACUR-03 | No ground truth exists past that line — money was never the justification | `checkpoint:decision`; Dre reviews calibration and held-out numbers first. **Phase 4 never crosses it**; Plan 04-04 T3 builds the `--allow-uncurated` guard, and Phase 5 must add the checkpoint — the flag alone is necessary but not sufficient |

**Spend policy (revised per D-29):** there is no per-token dollar cost, so the struck D-23 cost
estimator and `--ceiling-usd` cap are gone. The scarce resources are Dre's subscription usage
window and wall clock. Bound runs by **chapter count and concurrency**, log the harness's
`usage` block into every ledger entry, and rely on ledger resumability so an interrupted run
restarts free.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] **No test in the default suite performs live inference**
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
