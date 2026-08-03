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
> Rewritten 2026-08-02 for the descoped one-plan phase. The confidence-gate, ledger, and
> calibration test rows moved to Phase 5 along with the behaviors they cover.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + `pytest-asyncio` (async MCP handlers) — both already in the `dev` extra, no install needed |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `addopts = "-q"`) |
| **Quick run command** | `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q` |
| **Full suite command** | `.venv/bin/python scripts/verify.py` |
| **Estimated runtime** | ~120s full suite |
| **Data isolation** | `tests/conftest.py` copies `data/` to `tests/.tmp-data/data-<pid>/` via `BCF_DATA_DIR` at import time — already active |

---

## The core principle for this phase

**No live inference in the default test path — none, anywhere.** The transport is proven twice by
explicitly-marked manual steps (Task 1's smoke run, Task 3's real run) and never in CI. Everything
else is a pure function over the recorded submission fixture.

Do **not** build a multi-turn transcript fixture — with read tools in the surface a transcript replay
is brittle and buys nothing. Record only the final submission payload
(`tests/fixtures/stage2_submission_sample.json`) and drive `process_stage2_response()` with it.

**The strongest guarantee in this phase is structural, not behavioral:** there is no corpus write
path at all. `! grep -rn "write_chapter_roll_overrides_doc" scripts/stage2_*.py scripts/run_stage2_chapter.py`
proves more than any routing test could, because it removes the failure mode rather than checking for it.

---

## Sampling Rate

- **After every task commit:** `PYTHONPATH=scripts .venv/bin/python -m pytest tests/test_stage2_*.py -q`
- **After the wave:** `.venv/bin/python -m pytest -q` — compare the failure set against the baseline
- **Before `/gsd-verify-work`:** `.venv/bin/python scripts/verify.py` — **no NEW failures**
- **Max feedback latency:** ~120 seconds

### Known-accepted failure baseline (do NOT chase)

5 pre-existing failures: 4 in `tests/test_forge_curator.py`, 1 in
`tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction`.
`scripts/verify.py` exits 1 for that reason. **Judge by "no NEW failures", never by exit 0.**

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 04-01 | 1 | ACUR-01 | T-04-01 | Server exposes exactly the three propose-only tools (set equality) | unit | `pytest tests/test_stage2_mcp_server.py::test_tool_surface_is_propose_only -x` | ❌ W0 | ⬜ pending |
| 04-01-T1 | 04-01 | 1 | ACUR-01 | T-04-05 | `submit_stage2_rolls` schema rejects a malformed payload and unknown keys | unit | `pytest tests/test_stage2_mcp_server.py::test_submit_schema_rejects_malformed -x` | ❌ W0 | ⬜ pending |
| 04-01-T1 | 04-01 | 1 | ACUR-01 | T-04-06 | Server socket closes even when the run body raises | unit | `pytest tests/test_stage2_mcp_server.py::test_server_shutdown_on_exception -x` | ❌ W0 | ⬜ pending |
| 04-01-T1 | 04-01 | 1 | ACUR-01 | T-04-01 | **No corpus write path exists in any Stage 2 module** | grep | `! grep -rn "write_chapter_roll_overrides_doc" scripts/stage2_*.py scripts/run_stage2_chapter.py` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Adapter word starts byte-identical to `_chapter_word_index` on ≥3 real chapters | unit | `pytest tests/test_stage2_prose.py::test_adapter_offsets_match_cp_word_index -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Adapter yields >3 paragraphs on a real chapter (Pitfall 3 guard) | unit | `pytest tests/test_stage2_prose.py::test_paragraph_segmentation -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Adapter preserves string length | unit | `pytest tests/test_stage2_prose.py::test_adapter_preserves_length -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | One word-offset pipeline only — no `data_loader` import in Stage 2 | grep | `! grep -rn "data_loader" scripts/stage2_*.py` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Rolls map by explicit `slot_index`, never list position; duplicate → `isError` | unit | `pytest tests/test_stage2_response.py::test_slot_index_not_positional -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | An unverifiable quote becomes evidence-not-found with no invented position, model text preserved | unit | `pytest tests/test_stage2_response.py::test_unverified_quote_becomes_evidence_not_found -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Quote-less rolls (WoG, evidence-not-found) and an empty `rolls` array are valid outcomes | unit | `pytest tests/test_stage2_response.py::test_quoteless_roll_accepted -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | — | Proposals are maximally pre-filled (quote, position, constellation, grouping, per-field record) | unit | `pytest tests/test_stage2_response.py::test_proposal_is_fully_prefilled -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | T-04-07 | Read-tool caps are inclusive integers; 400-word span served in full | unit | `pytest tests/test_stage2_mcp_server.py::test_read_tool_caps_inclusive -x` | ❌ W0 | ⬜ pending |
| 04-01-T2 | 04-01 | 1 | ACUR-01 | T-04-02 | Read tools record nothing and return no destination | unit | `pytest tests/test_stage2_mcp_server.py::test_read_tools_are_side_effect_free -x` | ❌ W0 | ⬜ pending |
| 04-01-T3 | 04-01 | 1 | ACUR-01 | T-04-01 | The trusted corpus is byte-unchanged by a real run | integration | `git diff --exit-code data/manual/chapter_roll_overrides.json` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_stage2_mcp_server.py` — tool surface, schema rejection, shutdown, read-tool caps and purity
- [ ] `tests/test_stage2_prose.py` — D-33 adapter (offsets, segmentation, length)
- [ ] `tests/test_stage2_response.py` — slot mapping, evidence-not-found, quote-less rolls, pre-fill richness
- [ ] `tests/fixtures/stage2_submission_sample.json` — the recorded submission payload every downstream test drives from
- [ ] Framework install: **none needed** — `pytest` and `pytest-asyncio` are already in the `dev` extra

---

## Manual-Only Verifications

| Behavior | Task | Requirement | Why Manual | Test Instructions |
|----------|------|-------------|------------|-------------------|
| Package legitimacy for `mcp` | 04-01-T1 | ACUR-01 | Threat T-04-05 — a human eye on a new dependency before install. Short check, not a ceremony. | Confirm `modelcontextprotocol/python-sdk`, MIT, pin excludes the days-old 2.0.0 |
| Transport smoke run — warm server connects, stub handler records a submission | 04-01-T1 | ACUR-01 | Requires a live subscribed harness; retires the integration risk before pipeline code exists | One `claude -p` invocation; assert **handler-side state**, never the exit code. Record `num_turns`, `duration_ms`, `usage`. |
| Real run on 4–6 curated chapters | 04-01-T3 | ACUR-01 | Live harness | Run `run_stage2_chapter.py`; emit the per-chapter report |
| **Does this save Dre work?** | 04-01-T3 | ACUR-01 | This is the phase's actual success criterion, and only Dre can answer it | `checkpoint:decision` — review the proposals and report; also decide `get_prose_span`'s fate from its instrumented numbers |

**Spend policy:** no per-token dollar cost (D-25). Bound runs by chapter count and concurrency
(default 2), and log the harness `usage` block so run size is measurable rather than guessed.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] **No test in the default suite performs live inference**
- [ ] **No Stage 2 module imports the corpus writer** (structural, grep-proven)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
