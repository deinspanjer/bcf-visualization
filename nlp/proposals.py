"""Proposal-only types for the llama.cpp bootstrap lane.

These types are intentionally separate from nlp/schema.py so the
foundation agent can keep that module stable. If these types are
useful enough to graduate into the shared schema, the foundation agent
can absorb them post-merge (see report notes).

Differences from SpanRecord / Span in schema.py:
- ``Span`` here carries ``confidence`` (float 0-1) from the LLM output
  instead of the generic ``score`` field.  At review time the TUI
  converts to ``SpanAnnotation`` for the JSONL record.
- ``Proposal`` wraps LLM output before it is committed to reviewed JSONL;
  it is intentionally NOT a JSONL record itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ProposedSpan:
    """One span as emitted by the LLM — includes confidence."""

    layer: str          # "A" or "B"
    label: str
    start: int
    end: int
    confidence: Optional[float] = None  # 0.0-1.0 from LLM; may be absent


@dataclass
class Proposal:
    """Result of a single bootstrap call for one passage.

    ``spans`` has already been validated (offset consistency checked,
    invalid spans dropped on retry-exhaustion).  ``raw_response`` is
    the full JSON dict from the LLM for audit; it is also persisted to
    ``data/labeled/.proposals_raw/<passage_id>.json``.
    """

    passage_id: str
    model_name: str
    spans: list[ProposedSpan] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    # Mean confidence across accepted spans; None if no spans.
    mean_confidence: Optional[float] = None


__all__ = ["ProposedSpan", "Proposal"]
