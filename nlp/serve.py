"""FastAPI server hosting the span and section models.

Phase 0 scaffold: the routes are wired but the runners are stubs that
raise on construction (no trained checkpoints yet). The server boots
cleanly on a fresh install; `/health` and `/version` always work,
`/extract` and `/classify_section` return the documented 503 body
until checkpoints land.

Heavy ML imports (torch, transformers) live inside the runner classes
so this module can be imported and started on a box without a CUDA
stack — useful for quick sanity checks from the iMac.
"""

from __future__ import annotations

import datetime as _dt
import logging
import subprocess
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import config
from .schema import (
    SCHEMA_VERSION,
    ClassifySectionRequest,
    ClassifySectionResponse,
    ExtractRequest,
    ExtractResponse,
    GpuHealth,
    HealthResponse,
    ModelHealth,
    ModelVersion,
    VersionResponse,
)

log = logging.getLogger("nlp.serve")


def _git_commit() -> str:
    """Return the current commit hash, or ``"unknown"`` if unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _isoformat(ts: float) -> str:
    return (
        _dt.datetime.fromtimestamp(ts, tz=_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _gpu_info() -> GpuHealth:
    """Best-effort GPU probe. Never raises; returns `available=false`
    if torch is missing or no CUDA device is present."""
    try:
        import torch  # type: ignore[import-not-found]
    except Exception:
        return GpuHealth(available=False)
    try:
        if not torch.cuda.is_available():
            return GpuHealth(available=False)
        idx = 0
        name = torch.cuda.get_device_name(idx)
        free, total = torch.cuda.mem_get_info(idx)
        return GpuHealth(
            available=True,
            name=name,
            vram_total_mb=int(total // (1024 * 1024)),
            vram_free_mb=int(free // (1024 * 1024)),
        )
    except Exception:  # pragma: no cover - depends on hardware
        return GpuHealth(available=False)


def _read_metrics(path: str) -> Optional[ModelVersion]:
    """Surface checkpoint metadata if a `metrics_final.json` exists."""
    p = Path(path).parent / "metrics_final.json"
    if not p.exists():
        return None
    try:
        import json

        meta = json.loads(p.read_text())
    except Exception:
        return None
    return ModelVersion(
        version=meta.get("model_version"),
        trained_at=meta.get("trained_at"),
        metrics_path=str(p),
    )


# Module-level state — set in lifespan, read by handlers.
_state: dict = {
    "started_at": 0.0,
    "git_commit": "unknown",
    "span": None,  # SpanRunner once loaded; otherwise None
    "section": None,  # SectionRunner once loaded; otherwise None
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if config.LABEL_SCHEMA_VERSION != SCHEMA_VERSION:
        # Hard fail with a clear log line; mismatched schemas will
        # silently produce wrong outputs otherwise.
        msg = (
            "BCF_LABEL_SCHEMA_VERSION="
            f"{config.LABEL_SCHEMA_VERSION} does not match nlp.schema "
            f"SCHEMA_VERSION={SCHEMA_VERSION}; refusing to start"
        )
        log.error(msg)
        raise RuntimeError(msg)
    _state["started_at"] = time.time()
    _state["git_commit"] = _git_commit()
    log.info(
        "nlp.serve up: schema_version=%s git_commit=%s span_path=%s section_path=%s",
        SCHEMA_VERSION,
        _state["git_commit"],
        config.SPAN_MODEL_PATH,
        config.SECTION_MODEL_PATH,
    )
    yield


app = FastAPI(
    title="BCF local NLP",
    version=config.SERVICE_VERSION,
    lifespan=lifespan,
)


def _model_not_loaded(error_code: str) -> JSONResponse:
    """Documented 503 body shape from `docs/local_nlp_serving.md`."""
    return JSONResponse(status_code=503, content={"error": error_code})


def _load_span():
    """Lazy-load the span runner. Returns the runner or a 503 response."""
    if _state["span"] is not None:
        return _state["span"]
    from .runners import SpanRunner

    try:
        _state["span"] = SpanRunner(config.SPAN_MODEL_PATH)
    except (NotImplementedError, RuntimeError) as exc:
        log.info("span model not loaded: %s", exc)
        return _model_not_loaded("span_model_not_loaded")
    return _state["span"]


def _load_section():
    if _state["section"] is not None:
        return _state["section"]
    from .runners import SectionRunner

    try:
        _state["section"] = SectionRunner(config.SECTION_MODEL_PATH)
    except (NotImplementedError, RuntimeError) as exc:
        log.info("section model not loaded: %s", exc)
        return _model_not_loaded("section_model_not_loaded")
    return _state["section"]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    span_loaded = _state["span"] is not None
    section_loaded = _state["section"] is not None
    return HealthResponse(
        status="ok",
        models={
            "span": ModelHealth(
                loaded=span_loaded,
                version="span/v1" if span_loaded else None,
                path=config.SPAN_MODEL_PATH,
            ),
            "section": ModelHealth(
                loaded=section_loaded,
                version="section/v1" if section_loaded else None,
                path=config.SECTION_MODEL_PATH,
            ),
            "embed": ModelHealth(
                loaded=False,
                version=None,
                path=None,
            ),
        },
        gpu=_gpu_info(),
    )


@app.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    span_meta = _read_metrics(config.SPAN_MODEL_PATH) or ModelVersion()
    section_meta = _read_metrics(config.SECTION_MODEL_PATH) or ModelVersion()
    return VersionResponse(
        service_version=config.SERVICE_VERSION,
        git_commit=_state["git_commit"],
        schema_version=SCHEMA_VERSION,
        started_at=_isoformat(_state["started_at"] or time.time()),
        models={"span": span_meta, "section": section_meta},
    )


@app.post("/extract", response_model=ExtractResponse)
def extract(req: ExtractRequest, request: Request):
    runner = _load_span()
    if isinstance(runner, JSONResponse):
        return runner
    try:
        return runner.run(req)
    except (NotImplementedError, RuntimeError) as exc:
        log.info("span runner.run failed: %s", exc)
        return _model_not_loaded("span_model_not_loaded")


@app.post("/classify_section", response_model=ClassifySectionResponse)
def classify_section(req: ClassifySectionRequest, request: Request):
    runner = _load_section()
    if isinstance(runner, JSONResponse):
        return runner
    try:
        return runner.run(req)
    except (NotImplementedError, RuntimeError) as exc:
        log.info("section runner.run failed: %s", exc)
        return _model_not_loaded("section_model_not_loaded")


__all__ = ["app"]
