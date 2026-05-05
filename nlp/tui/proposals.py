"""Async wrapper around nlp.bootstrap.propose() for the TUI.

Runs proposal calls in a background thread so the Textual event loop is
never blocked.  Errors are surfaced as a status-line message instead of
crashing the app.

Public API
----------
ProposalResult
    Dataclass returned via the ``on_result`` callback or awaitable.

propose_async(passage_text, *, passage_id, ...) -> ProposalResult
    Non-blocking entry point for the TUI worker.  Called with
    ``app.run_worker(propose_async(...))``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ProposalResult", "propose_async"]


@dataclass
class ProposalResult:
    """Result of a proposal call (success or failure)."""

    passage_id: str
    spans: list[dict[str, Any]] = field(default_factory=list)
    model_name: str = ""
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def avg_confidence(self) -> float | None:
        """Mean confidence across all proposed spans, or None."""
        scores = [s.get("score") for s in self.spans if s.get("score") is not None]
        return sum(scores) / len(scores) if scores else None


async def propose_async(
    passage_text: str,
    *,
    passage_id: str,
    model_name: str = "",
    extra_prompt: str = "",
) -> ProposalResult:
    """Call ``nlp.bootstrap.propose`` in a thread and return a ProposalResult.

    This coroutine is designed to be run with Textual's ``run_worker``::

        self.run_worker(propose_async(text, passage_id=pid), exclusive=True)

    Errors (import failures, network failures, bad JSON) are caught and
    returned as ``ProposalResult(error=...)`` so the TUI shows a status
    warning rather than crashing.
    """
    t0 = time.monotonic()

    try:
        # Import here so the TUI is importable even without bootstrap landed
        from nlp.bootstrap import propose  # type: ignore[import]
    except ImportError:
        return ProposalResult(
            passage_id=passage_id,
            error="nlp.bootstrap not available (bootstrap agent not landed yet)",
            elapsed_s=time.monotonic() - t0,
        )

    loop = asyncio.get_running_loop()

    def _call() -> Any:
        kwargs: dict[str, Any] = {"passage_id": passage_id}
        if model_name:
            kwargs["model_name"] = model_name
        if extra_prompt:
            kwargs["extra_prompt"] = extra_prompt
        return propose(passage_text, **kwargs)

    try:
        result = await loop.run_in_executor(None, _call)
        elapsed = time.monotonic() - t0

        # Normalise span dicts from the Proposal object
        raw_spans: list[dict[str, Any]] = []
        for sp in getattr(result, "spans", []):
            if hasattr(sp, "model_dump"):
                raw_spans.append(sp.model_dump())
            elif isinstance(sp, dict):
                raw_spans.append(sp)

        return ProposalResult(
            passage_id=passage_id,
            spans=raw_spans,
            model_name=getattr(result, "model_name", model_name),
            raw_response=getattr(result, "raw_response", {}),
            elapsed_s=elapsed,
        )
    except Exception as exc:  # noqa: BLE001
        return ProposalResult(
            passage_id=passage_id,
            error=f"Proposal failed: {exc}",
            elapsed_s=time.monotonic() - t0,
        )
