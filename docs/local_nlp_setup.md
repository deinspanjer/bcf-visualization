# Local NLP setup playbook

_How to install, configure, and smoke-test the Windows GPU box and
the iMac client side. Pair with `docs/local_nlp_plan.md`._

## Hardware assumptions

- **Windows GPU box**: 12+ GB VRAM (you've reported having more); CUDA
  13.1 already installed via the prebuilt llama.cpp distribution; no
  pre-existing Python toolchain.
- **iMac (or any dev box)**: development machine with the repo cloned,
  Python 3.11 available, network access to the Windows box.

LAN reachability is required: the iMac must be able to open TCP to
the Windows box on at least port `11434` (llama.cpp, already running)
and `8000` (the FastAPI service we're adding). Confirm now:

```sh
# from iMac
nc -zv <windows-ip> 11434
```

## Repo layout for the new code

All new NLP code lives under `nlp/` so it stays separable from the
existing parser scripts in `scripts/`.

```
bcf-visualization/
├── data/
│   ├── raw/                        # existing
│   ├── derived/                    # existing
│   ├── manual/                     # existing
│   └── labeled/                    # NEW (committed)
│       ├── spans/
│       │   ├── pilot.jsonl
│       │   ├── train.jsonl
│       │   ├── eval.jsonl
│       │   └── heldout.jsonl       # blind eval; never opened by LLM
│       └── sections/
│           ├── train.jsonl
│           └── eval.jsonl
├── docs/
│   ├── local_nlp_research.md       # existing
│   ├── local_nlp_plan.md           # NEW
│   ├── local_nlp_label_schema.md   # NEW
│   ├── local_nlp_setup.md          # NEW (this file)
│   ├── local_nlp_annotation_playbook.md  # NEW
│   ├── local_nlp_training.md       # NEW
│   └── local_nlp_serving.md        # NEW
├── nlp/                            # NEW (committed)
│   ├── __init__.py
│   ├── schema.py                   # label sets + JSONL pydantic models
│   ├── encode.py                   # char-span -> token-BIO conversion
│   ├── train_span.py               # span model training entry point
│   ├── train_section.py            # section classifier training entry point
│   ├── evaluate.py                 # offline eval harness
│   ├── serve.py                    # FastAPI server (Windows box)
│   ├── client.py                   # iMac-side HTTP wrapper
│   ├── bootstrap.py                # llama.cpp prompt + JSON proposals
│   └── tui/
│       ├── __init__.py
│       ├── app.py                  # Textual app entry
│       ├── candidates.py           # which passages to propose next
│       └── persist.py              # JSONL read/write with locking
├── checkpoints/                    # NEW (gitignored)
│   ├── span/
│   │   └── v1/
│   └── section/
│       └── v1/
├── pyproject.toml                  # NEW (top-level uv project)
├── uv.lock                         # NEW (committed)
├── scripts/                        # existing
└── ...
```

`pyproject.toml` is added at the repo root so `uv` manages a single
venv. The existing `requirements.txt` keeps working for the parser
scripts; the NLP work is opt-in by activating the uv venv.

## Windows box install

### 1. Install `uv` (one binary, no admin)

In PowerShell:

```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

This drops `uv.exe` into `%USERPROFILE%\.local\bin` and prepends it to
`PATH` for new shells. Confirm:

```powershell
uv --version
```

### 2. Pin Python and create the venv

From the repo root on the Windows box (clone the repo there if you
haven't already):

```powershell
uv python install 3.11
uv venv --python 3.11
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

The `pyproject.toml` (to be added by the next implementation step)
declares:

```toml
[project]
name = "bcf-nlp"
version = "0.1.0"
requires-python = ">=3.11,<3.13"

dependencies = [
  "torch>=2.4",
  "transformers>=4.45",
  "tokenizers>=0.20",
  "accelerate>=0.34",
  "datasets>=3.0",
  "evaluate>=0.4",
  "seqeval>=1.2",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "httpx>=0.27",
  "textual>=0.79",
  "rich>=13.8",
  "regex>=2024.7",
  "rapidfuzz>=3.9",
  "tqdm>=4.66",
]

[project.optional-dependencies]
dev = ["ruff", "pytest"]
```

PyTorch CUDA wheel: `uv` auto-resolves the right CUDA build. If it
picks a CPU-only build for any reason, force it:

```powershell
uv pip install torch --index-url https://download.pytorch.org/whl/cu124
```

CUDA 13.1 forward-runs CUDA 12.x wheels; no recompilation needed.

Install everything:

```powershell
uv sync
```

### 4. Pre-download the encoder backbone (optional but recommended)

Download once so training and serving are offline-safe:

```powershell
uv run python -c "from transformers import AutoModel, AutoTokenizer; m='answerdotai/ModernBERT-base'; AutoTokenizer.from_pretrained(m); AutoModel.from_pretrained(m)"
```

Default cache: `%USERPROFILE%\.cache\huggingface\hub`. Optionally set
`HF_HOME` to point at a larger drive:

```powershell
[Environment]::SetEnvironmentVariable('HF_HOME', 'C:\Apps\hf_cache', 'User')
```

### 5. Verify GPU is visible to PyTorch

```powershell
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)"
```

Expected: `True <some GPU name>`. If `False`, torch picked a CPU
wheel; reinstall with the `cu124` index URL above.

### 6. Confirm llama.cpp is reachable

Verify the existing endpoint still works from the Windows box itself:

```powershell
curl http://localhost:11434/v1/models
```

You should see the resolved model entry. If `--models-max 1
--parallel 1` and router-mode mean nothing is loaded yet, the first
real request will warm it; that's fine.

### 7. Standalone smoke test of the FastAPI scaffold

Once `nlp/serve.py` is implemented (per `docs/local_nlp_serving.md`),
launch with:

```powershell
uv run uvicorn nlp.serve:app --host 0.0.0.0 --port 8000
```

Hit it from the iMac:

```sh
curl http://<windows-ip>:8000/health
```

Expected response: `{"status":"ok","span_model":null,"section_model":null}`
on a fresh install (no checkpoints yet).

### 8. Persistent run (optional)

For unattended operation, two reasonable options on Windows:

1. **Task Scheduler**: create a task that runs at user logon and kicks
   off `pwsh -File C:\Apps\bcf-nlp\start-server.ps1`. Lowest install
   cost.
2. **NSSM** (`https://nssm.cc/`): wrap uvicorn as a Windows service.
   More robust restart behavior; small extra install.

A `start-server.ps1` template:

```powershell
Set-Location C:\Apps\bcf-visualization
.\.venv\Scripts\Activate.ps1
$env:HF_HOME = 'C:\Apps\hf_cache'
uv run uvicorn nlp.serve:app --host 0.0.0.0 --port 8000 --log-level info
```

## iMac install

The iMac is a thin client. Install only what's needed to call the
Windows endpoints from existing scripts.

### 1. Existing dependencies

Already covered by `requirements.txt`:

```sh
pip install -r requirements.txt
```

### 2. NLP client deps

Add to `requirements.txt` (smallest surface):

```
httpx>=0.27
pydantic>=2.8
```

That's it on the iMac. No torch, no transformers, no models. The
`nlp/client.py` module wraps the HTTP calls into a typed Python API.

### 3. Configure the endpoint

The endpoints are configurable via env vars; defaults match the
documented setup:

```sh
export BCF_LLAMACPP_URL=http://<windows-ip>:11434
export BCF_NLP_URL=http://<windows-ip>:8000
```

Add a one-line resolver to `scripts/_common.py` so every consumer
reads the same env. Default to `localhost` so a Windows-only operator
can run iMac-style scripts directly on the GPU box.

### 4. Smoke test from the iMac

```sh
python3 -c "import httpx; print(httpx.get('http://<windows-ip>:8000/health').json())"
python3 -c "import httpx; print(httpx.get('http://<windows-ip>:11434/v1/models').json())"
```

Both should respond. If they don't:

- Check Windows Defender Firewall on the GPU box. The first time
  uvicorn binds `0.0.0.0:8000`, Windows pops a firewall prompt; if it
  was missed, allow inbound on port 8000 manually.
- `--host 0.0.0.0` is required for LAN; `127.0.0.1` only listens
  locally.

## Configuration reference

| Env var | Default | Purpose |
|---|---|---|
| `BCF_LLAMACPP_URL` | `http://localhost:11434` | llama.cpp endpoint |
| `BCF_NLP_URL` | `http://localhost:8000` | FastAPI endpoint |
| `BCF_SPAN_MODEL_PATH` | `checkpoints/span/v1/best` | Span model directory |
| `BCF_SECTION_MODEL_PATH` | `checkpoints/section/v1/best` | Section model directory |
| `HF_HOME` | unset | Hugging Face cache root |
| `BCF_LABEL_SCHEMA_VERSION` | `1` | Asserts schema version on load |

`nlp/serve.py` reads `BCF_*` on startup; `nlp/client.py` reads them on
import. None are required when running on defaults.

## Updating dependencies

```powershell
uv lock --upgrade
uv sync
```

Commit `uv.lock` after every successful upgrade. Pin `pyproject.toml`
versions only when a real incompatibility appears.

## Disk-space planning

- Encoder backbone (ModernBERT-base): ~600 MB on disk + ~600 MB in
  GPU memory.
- Each fine-tuned checkpoint: ~600 MB (full weights, no LoRA).
- Hugging Face cache for typical workflow: budget 5 GB.
- llama.cpp GGUF models you already have: ~20 GB total.

A 60-80 GB free space target on the Windows box covers everything
including a few rounds of checkpoints with room for retraining
artifacts.

## What's deliberately not installed

- **Argilla / Label Studio**: not used; we use the in-repo Textual
  TUI. Revisit if a second annotator joins.
- **vLLM / TGI**: overkill; llama.cpp is already serving generation.
- **Docker**: avoidable on Windows for this workload; the prebuilt
  llama.cpp + uv venv covers it.
- **A separate embedding server**: skipped until a concrete need
  emerges.

## What to do next

After this doc's steps complete:

1. Phase 0 complete; both endpoints healthy.
2. Move to `docs/local_nlp_annotation_playbook.md` for the labeling
   workflow.
3. Move to `docs/local_nlp_training.md` once the pilot set is in
   place.
