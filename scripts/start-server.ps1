# Launch the BCF NLP FastAPI server on the Windows GPU box.
#
# Usage (foreground, current shell):
#   pwsh -File scripts/start-server.ps1
#
# Usage (Task Scheduler, NSSM, etc.): point the action at this file.
#
# Env vars honored (see docs/local_nlp_setup.md):
#   HF_HOME                       Hugging Face cache root (defaults to user profile cache)
#   BCF_NLP_URL                   informational only
#   BCF_SPAN_MODEL_PATH           span checkpoint dir
#   BCF_SECTION_MODEL_PATH        section checkpoint dir
#   BCF_LABEL_SCHEMA_VERSION      schema version (must match nlp.schema.SCHEMA_VERSION)

$ErrorActionPreference = 'Stop'

# Resolve the repo root from this script's location so the script works
# regardless of the current working directory at launch time.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..')
Set-Location $RepoRoot

if (-not (Test-Path '.\.venv\Scripts\Activate.ps1')) {
    Write-Error "Virtual env not found at .\.venv. Run scripts\setup_windows.ps1 first."
}
. .\.venv\Scripts\Activate.ps1

if (-not $env:HF_HOME) {
    Write-Host "HF_HOME not set; using default Hugging Face cache."
}

$Host = $env:BCF_NLP_HOST
if (-not $Host) { $Host = '0.0.0.0' }
$Port = $env:BCF_NLP_PORT
if (-not $Port) { $Port = '8000' }
$LogLevel = $env:BCF_NLP_LOG_LEVEL
if (-not $LogLevel) { $LogLevel = 'info' }

Write-Host "Starting nlp.serve on $Host`:$Port (log-level=$LogLevel)"
uv run uvicorn nlp.serve:app --host $Host --port $Port --log-level $LogLevel
