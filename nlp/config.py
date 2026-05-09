"""Shared environment-variable configuration for the NLP package.

Read once at import time so every caller (server, client, training,
TUI) sees the same view. All values are overridable via env. Defaults
match `docs/local_nlp_setup.md`.
"""

from __future__ import annotations

import os

from .schema import SCHEMA_VERSION

LLAMACPP_URL: str = os.environ.get("BCF_LLAMACPP_URL", "http://localhost:11434")
NLP_URL: str = os.environ.get("BCF_NLP_URL", "http://localhost:8000")
SPAN_MODEL_PATH: str = os.environ.get(
    "BCF_SPAN_MODEL_PATH", "checkpoints/span/v1/best"
)
SECTION_MODEL_PATH: str = os.environ.get(
    "BCF_SECTION_MODEL_PATH", "checkpoints/section/v1/best"
)
EMBED_MODEL: str | None = os.environ.get("BCF_EMBED_MODEL")
LABEL_SCHEMA_VERSION: int = int(
    os.environ.get("BCF_LABEL_SCHEMA_VERSION", str(SCHEMA_VERSION))
)
BACKBONE: str = os.environ.get("BCF_BACKBONE", "answerdotai/ModernBERT-base")
NLP_TOKEN: str | None = os.environ.get("BCF_NLP_TOKEN")
SERVICE_VERSION: str = "0.1.0"


__all__ = [
    "LLAMACPP_URL",
    "NLP_URL",
    "SPAN_MODEL_PATH",
    "SECTION_MODEL_PATH",
    "EMBED_MODEL",
    "LABEL_SCHEMA_VERSION",
    "BACKBONE",
    "NLP_TOKEN",
    "SERVICE_VERSION",
]
