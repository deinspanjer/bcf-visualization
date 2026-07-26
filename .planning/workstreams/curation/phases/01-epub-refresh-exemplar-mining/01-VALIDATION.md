---
phase: 1
slug: epub-refresh-exemplar-mining
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, `.venv/bin/python -m pytest`) |
| **Config file** | existing `tests/` suite in repo root |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -q -x --ignore=tests/test_desktop_smoke.py` (scope to touched contracts per task) |
| **Full suite command** | `.venv/bin/python -m pytest -q` plus `.venv/bin/python scripts/verify.py` |
| **Estimated runtime** | ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the task-scoped quick command
- **After every plan wave:** Run `.venv/bin/python -m pytest -q` and `scripts/verify.py`
- **Before `/gsd-verify-work`:** Full suite must be green (the 24 pre-existing Track B failures MUST be cleared by this phase — they are in-scope, not baseline)
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

*Filled by planner — every task maps to a requirement and an automated command.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-T1 | 01-01 | 1 | EPUB-01 | — | Pure freshness comparison; pipeline force-regen halts only at the documented ch95.5 error | unit/integration | `.venv/bin/python -m pytest tests/test_source_epub_hydration.py -q` | ✅ | ⬜ pending |
| 01-01-T2 | 01-01 | 1 | EPUB-01 | T-01-01-01, T-01-01-02 | Human-approved decision on the exact field/value change to `chapter_roll_overrides.json` | manual (checkpoint:decision) | N/A — Dre's checkpoint decision recorded | ✅ | ⬜ pending |
| 01-01-T3 | 01-01 | 1 | EPUB-01 | T-01-01-01, T-01-01-02 | Only the approved edit is applied; full pipeline regen completes to 198 chapters / ch121.1 | integration | `test -f data/derived/chapters.json && python3 -c "import json,sys; d=json.load(open('data/derived/chapters.json')); chs=d['chapters']; sys.exit(0 if (len(chs)>195 and chs[-1]['chapter_num']=='121.1') else 1)"` | ✅ | ⬜ pending |
| 01-02-T1 | 01-02 | 2 | EPUB-02 | — | Manifest re-stamped with a fresh sha256 for `perk_directory.json` | integration | `test -f data/derived/data_package.json && python3 -c "import json,sys; d=json.load(open('data/derived/data_package.json')); sys.exit(0 if 'perk_directory.json' in d.get('files', {}) else 1)"` | ✅ | ⬜ pending |
| 01-02-T2 | 01-02 | 2 | EPUB-02 | T-01-02-01 | Fingerprint re-stamp only via explicit per-chapter accept/skip/abort — never `--yes` | manual (checkpoint:human-verify) | N/A — auto-clears on 0 mismatches, else interactive `scripts/realign_chapters.py` session | ✅ | ⬜ pending |
| 01-02-T3 | 01-02 | 2 | EPUB-02 | T-01-02-02, T-01-02-03 | Full `verify.py` green; zero occurrences of the 24 named Track B failures | integration | `.venv/bin/python scripts/verify.py` | ✅ | ⬜ pending |
| 01-03-T1 | 01-03 | 3 | CINF-02 | T-01-03-01, T-01-03-02 | Exemplar index regime-tagged; ch97 dual-tagged `{2,3}`; no epub reads; no duplicate regime function | unit | `.venv/bin/python -m pytest tests/test_build_exemplar_index.py -q` | ✅ | ⬜ pending |
| 01-03-T2 | 01-03 | 3 | CINF-02 | — | `retrieve()` never returns a cross-regime exemplar; deterministic ordering | unit | `.venv/bin/python -m pytest tests/test_query_exemplars.py -q` | ✅ | ⬜ pending |
| 01-03-T3 | 01-03 | 3 | CINF-02 | T-01-03-03 | New Step wired into the pipeline DAG closure (`TARGET_FINAL_STEPS`); manifest-registered; full suite stays green | integration | `.venv/bin/python -m pytest tests/test_pipeline.py -q && .venv/bin/python scripts/data_release.py check-derived && .venv/bin/python -m pytest -q` | ✅ | ⬜ pending |
| 01-04-T1 | 01-04 | 4 | CINF-02 | T-01-04-01 | Report sourced from `exemplar_index.json`'s statistics only; no epub prose quoted | integration | `test -f .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md && grep -ci "regime" .planning/workstreams/curation/phases/01-epub-refresh-exemplar-mining/corpus-analysis-report.md` | ✅ | ⬜ pending |
| 01-04-T2 | 01-04 | 4 | CINF-02 | T-01-04-02 | Phase-closing `verify.py` green; `exemplar_index.json` confirmed manifest-registered | integration | `.venv/bin/python scripts/verify.py && python3 -c "import json,sys; d=json.load(open('data/derived/data_package.json')); sys.exit(0 if 'exemplar_index.json' in d.get('files', {}) else 1)"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] Test coverage for the new exemplar-index build + same-regime retrieval (new test file under `tests/`) — satisfied by `tests/test_build_exemplar_index.py` and `tests/test_query_exemplars.py` (Plan 01-03, Tasks 1-2)

*Existing infrastructure (pytest + `scripts/verify.py` + `data_release.py check-derived`) covers the epub-refresh and pipeline-green requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Any fingerprint drift accepted via `scripts/realign_chapters.py` | EPUB-02 | Interactive accept/skip by design — never `--yes` (hand-curated authority) | Dre reviews each flagged chapter alignment interactively |
| Residual failure tracing to hand-curated data (e.g. ch 95.5 override) | EPUB-02 | Curation authority — agents never edit hand-curated entries | Executor surfaces diagnosis; Dre applies/approves the fix |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 180s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
