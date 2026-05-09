# Local NLP runbook

_Operator-facing checklist for bringing the Phase 0 scaffold up on a
Windows GPU box and verifying it from the iMac. Everything below is
copy-paste-ready. Reference docs: `local_nlp_setup.md` (full install
detail), `local_nlp_serving.md` (endpoint contracts),
`local_nlp_plan.md` (where Phase 0 sits in the larger arc)._

Phase 0 + Phase 1 are **scaffolded**:

- Package layout, FastAPI server with `/health`, `/version`,
  `/extract`, `/classify_section`, an iMac client, and a smoke test.
- llama.cpp labeling-assistant lane (`nlp.bootstrap`) and a CLI driver
  (`scripts/bootstrap_proposals.py`) for dry-run proposal generation.
- Textual review TUI (`python -m nlp.tui.app`) wired to bootstrap
  proposals and the JSONL store with WAL-backed crash safety.
- Training entry points (`nlp/train_span.py`, `nlp/train_section.py`,
  `nlp/evaluate.py`) plus a pure-function BIO encoder (`nlp/encode.py`)
  with tiny fixtures under `tests/fixtures/` for a smoke training run.

There are no trained checkpoints yet — by design, `/extract` and
`/classify_section` return `503` with the documented
`*_model_not_loaded` body. That's what proves the routes are wired.

## What you're verifying

- The Windows GPU box can install dependencies and pre-cache
  ModernBERT-base offline.
- `uvicorn nlp.serve:app` boots cleanly with no checkpoints.
- The iMac can reach `:8000` (FastAPI) and `:11434` (llama.cpp) over
  LAN.
- `scripts/smoke_test_nlp.py` reports PASS on `/health`, `/version`,
  and the `/extract` 503.

## Windows GPU box

Open **PowerShell** in the repo root.

```powershell
# 1. One-shot setup. Idempotent; safe to re-run.
pwsh -File scripts\setup_windows.ps1
```

That script installs `uv`, pins Python 3.11, creates `.venv`, runs
`uv sync --extra gpu --extra dev`, verifies torch sees the GPU, and
pre-caches `answerdotai/ModernBERT-base` to `HF_HOME` (or the default
user cache).

```powershell
# 2. Confirm llama.cpp is up locally (it should already be).
curl http://localhost:11434/v1/models
```

```powershell
# 3. Start the FastAPI server in this shell. Ctrl-C to stop.
pwsh -File scripts\start-server.ps1
```

You should see uvicorn log a startup line that mentions
`schema_version=1` and the resolved `git_commit`. The first time
uvicorn binds `0.0.0.0:8000`, Windows Defender Firewall pops a prompt
— allow inbound on the **Private** network.

In a second PowerShell on the same box:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/version
```

`/health` returns `status: ok` with `loaded: false` for both span and
section models. That is correct for Phase 0.

## iMac smoke test

```sh
# from the iMac, with the repo cloned and requirements installed
.venv/bin/python -m pip install -r requirements.txt    # one-time

.venv/bin/python scripts/smoke_test_nlp.py \
    --nlp-url   http://<windows-ip>:8000 \
    --llama-url http://<windows-ip>:11434
```

Or set the env vars once and rely on defaults:

```sh
export BCF_NLP_URL=http://<windows-ip>:8000
export BCF_LLAMACPP_URL=http://<windows-ip>:11434
.venv/bin/python scripts/smoke_test_nlp.py
```

Expected output:

```
PASS GET /health - status=ok span.loaded=False section.loaded=False
PASS GET /version - service=0.1.0 commit=<hash> schema=1
PASS POST /extract (expect 503 span_model_not_loaded) - 503 span_model_not_loaded (route wired, checkpoint absent)
PASS GET {llama}/v1/models - models=[...]
All checks passed.
```

Any FAIL line prints a hint pointing at the most common cause.

## Python tests (either box)

```sh
.venv/bin/pytest
```

New verification should use pytest. Focused modules can be run with
`.venv/bin/pytest tests/<module>.py`; most tests do not require torch,
transformers, or a GPU, and dependency-heavy tests skip when their
optional packages are unavailable.

## If something fails

| Symptom | First thing to check |
|---|---|
| `smoke_test_nlp.py: could not connect` to `:8000` | `uvicorn` not started, or bound to `127.0.0.1`. `start-server.ps1` uses `0.0.0.0` by default. |
| `smoke_test_nlp.py: could not connect` to `:11434` | llama-server not running. Start it with the existing `run-llama-server.bat`. |
| Port-blocked from iMac, works locally on Windows | Windows Defender Firewall. Add an inbound TCP rule for 8000 (and 11434 if needed). |
| `/health` returns 500 with `BCF_LABEL_SCHEMA_VERSION` in the message | The env var is pinned to a value other than `1`. Unset it or set it to `1`. |
| `setup_windows.ps1` reports `cuda=False` | torch picked the CPU wheel. Re-install with `uv pip install torch --index-url https://download.pytorch.org/whl/cu124`. |
| `uv sync` fails with hash mismatch | Delete `uv.lock` (only if you understand you'll get fresh resolutions) and re-run. Otherwise look at the offending package. |
| `import nlp.client` fails on the iMac with `No module named 'pydantic'` | `pip install -r requirements.txt` on the iMac. |
| Serve prints `git_commit: unknown` | Repo is not a git checkout (e.g. zip download). Clone via git to get a real commit. |

## Phase 1 dry-run — bootstrap proposals on Windows

Once Phase 0 smoke-tests pass and `llama-server` is up, you can
exercise the labeling-assistant lane end-to-end without the TUI:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\bootstrap_proposals.py `
    --strategy event_focused `
    --limit 3 `
    --out data\labeled\spans\_proposals_dryrun.jsonl `
    --llama-url http://localhost:11434
```

Add `--epub data\raw\<your>.epub` if the EPUB is on disk; otherwise
the script falls back to `chapter_sections.json` `sample` fields and
flags each record with `source="section_first_chars"`. A successful
run prints a per-passage summary plus a final tally.

If llama.cpp is unreachable, the script exits 1 with the URL it tried
and a remediation hint — no stack trace.

## Phase 1 dry-run — review TUI

```powershell
.\.venv\Scripts\Activate.ps1
python -m nlp.tui.app `
    --jsonl data\labeled\spans\pilot.jsonl `
    --strategy event_focused
```

Keys: `s` save+next, `S` save in place, `k` skip, `b` back, `a` add
span, `e` edit, `d` delete, `Space` toggle a section flag, `r`
re-propose, `?` help, `q` quit. A few keybindings from the playbook
spec are stubbed for the next pass (`l`/`L` cycle-label shortcuts,
custom-prompt re-propose, mouse text selection); the modals cover
the same operations.

`scripts/tui_smoke.py` populates a tmp queue with 3 synthetic
candidates so you can exercise the UI without llama.cpp or the EPUB.

## Phase 2 dry-run — training scripts

The training entry points fail loudly if torch isn't installed.
Once `setup_windows.ps1` has run, you can verify the pipeline shape
with the tiny fixtures:

```powershell
uv run python nlp\train_span.py `
    --train tests\fixtures\tiny_spans.jsonl `
    --eval  tests\fixtures\tiny_spans.jsonl `
    --version vtest --epochs 1 --batch-size 1
```

Same shape for `train_section.py`. These are sanity checks, not real
training runs — the fixtures are five hand-crafted records each.

## What's intentionally not yet there

- Trained checkpoints under `checkpoints/span/v1/best` and
  `checkpoints/section/v1/best`. Those land after Phase 1
  (annotation) and Phase 2 (training). `/extract` and
  `/classify_section` will keep returning `503` until then.
- The end-to-end pipeline-replay section in `nlp.evaluate`. Stubbed
  with a clear "not yet implemented" message; promote in Phase 2.
- Embedding endpoint (`/embed`). Disabled until `BCF_EMBED_MODEL` is
  set; the contract appears in `local_nlp_serving.md`.

## Persistent run on Windows

`scripts/start-server.ps1` is the entry point for either Task
Scheduler or NSSM (see `local_nlp_setup.md` §8). Both options survive
reboot; pick one once Phase 0 is signed off.
