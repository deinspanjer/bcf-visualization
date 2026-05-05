"""Runner placeholders for the span and section models.

The serve module loads these lazily on first request so the FastAPI
process can boot on a fresh checkout with no checkpoints (and without
torch/transformers installed at all). The real implementations land
alongside `train_span.py` / `train_section.py`.

Each runner's constructor or `.run()` raises `RuntimeError` so the
serve layer can convert it to the documented 503 body shape.
"""

from __future__ import annotations

from pathlib import Path

from .schema import (
    ClassifySectionRequest,
    ClassifySectionResponse,
    ExtractRequest,
    ExtractResponse,
)


class _BaseRunner:
    """Common load-failure machinery shared by both runner stubs."""

    name: str = "model"
    error_code: str = "model_not_loaded"

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        # Heavy ML imports happen lazily inside `_load`. The scaffold
        # must work without torch/transformers installed.
        try:
            self._load()
        except NotImplementedError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError(
                f"{self.name} runner failed to load from {model_path!r}: {exc}"
            ) from exc

    def _load(self) -> None:
        path = Path(self.model_path)
        if not path.exists():
            raise RuntimeError(
                f"{self.error_code}: checkpoint directory missing at {self.model_path!r}"
            )
        # Real implementation will:
        #   import torch
        #   from transformers import AutoTokenizer, AutoModel
        #   ...
        # Until trained checkpoints exist, raising NotImplemented keeps
        # the contract clear for callers and parallel agents.
        raise NotImplementedError(
            f"{self.name} runner not yet implemented; pending training pipeline"
        )


class SpanRunner(_BaseRunner):
    """Runs the two-head token classifier behind `POST /extract`."""

    name = "span"
    error_code = "span_model_not_loaded"

    def run(self, req: ExtractRequest) -> ExtractResponse:
        raise RuntimeError(self.error_code)


class SectionRunner(_BaseRunner):
    """Runs the multi-label section classifier behind `POST /classify_section`."""

    name = "section"
    error_code = "section_model_not_loaded"

    def run(self, req: ClassifySectionRequest) -> ClassifySectionResponse:
        raise RuntimeError(self.error_code)


__all__ = ["SpanRunner", "SectionRunner"]
