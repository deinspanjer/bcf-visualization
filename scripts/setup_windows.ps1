# One-shot setup for the Windows GPU box.
#
# Idempotent: re-running on an already-set-up box only verifies state.
# Pairs with docs/local_nlp_setup.md.
#
#   pwsh -File scripts/setup_windows.ps1

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# 1. Install uv if missing -------------------------------------------------
if (-not (Test-Command 'uv')) {
    Write-Host '==> Installing uv (no admin required)'
    Invoke-RestMethod 'https://astral.sh/uv/install.ps1' | Invoke-Expression
    # uv installer prepends to PATH for *new* shells. Pick it up now.
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
} else {
    Write-Host "==> uv already installed: $(uv --version)"
}

# 2. Pin Python and create the venv ---------------------------------------
Write-Host '==> Pinning Python 3.11'
uv python install 3.11

if (-not (Test-Path '.\.venv')) {
    Write-Host '==> Creating .venv with Python 3.11'
    uv venv --python 3.11
} else {
    Write-Host '==> .venv already exists; skipping create'
}

# 3. Install dependencies (incl. the GPU extra for torch) -----------------
Write-Host '==> uv sync (with gpu extra for CUDA torch)'
uv sync --extra gpu --extra dev

# 4. Verify torch sees the GPU --------------------------------------------
Write-Host '==> Verifying torch CUDA visibility'
$cudaCheck = uv run python -c "import torch; print('cuda=' + str(torch.cuda.is_available()) + ' name=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'))"
Write-Host $cudaCheck
if ($cudaCheck -notmatch 'cuda=True') {
    Write-Warning 'torch.cuda.is_available() is False. You probably got the CPU wheel; reinstall with:'
    Write-Warning '  uv pip install torch --index-url https://download.pytorch.org/whl/cu124'
}

# 5. Pre-download the encoder backbone ------------------------------------
$Backbone = if ($env:BCF_BACKBONE) { $env:BCF_BACKBONE } else { 'answerdotai/ModernBERT-base' }
Write-Host "==> Pre-downloading $Backbone (offline-safe training/serving)"
uv run python -c "from transformers import AutoTokenizer, AutoModel; AutoTokenizer.from_pretrained('$Backbone'); AutoModel.from_pretrained('$Backbone'); print('backbone cached: $Backbone')"

# 6. Create checkpoint placeholders ---------------------------------------
foreach ($p in @('checkpoints\span\v1', 'checkpoints\section\v1')) {
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p | Out-Null
    }
}

Write-Host ''
Write-Host '==> Setup complete.'
Write-Host ''
Write-Host 'Next steps:'
Write-Host '  1. Confirm llama.cpp is reachable:    curl http://localhost:11434/v1/models'
Write-Host '  2. Start the FastAPI server:          pwsh -File scripts\start-server.ps1'
Write-Host '  3. From the iMac, smoke-test:'
Write-Host '         python3 scripts/smoke_test_nlp.py --nlp-url http://<windows-ip>:8000 \'
Write-Host '             --llama-url http://<windows-ip>:11434'
Write-Host '  4. See docs/local_nlp_runbook.md for the full Phase 0 checklist.'
