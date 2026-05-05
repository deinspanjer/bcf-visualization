"""Thin httpx client for the NLP FastAPI service.

Used by iMac-side scripts that don't ship a torch/transformers stack.
Depends only on stdlib + httpx + pydantic.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import httpx

from . import config


class BcfNlpClient:
    """Synchronous HTTP wrapper around the local NLP service.

    Parameters
    ----------
    base_url:
        Override for the service URL. Defaults to ``BCF_NLP_URL`` (see
        ``nlp.config``).
    timeout:
        Per-request timeout in seconds. Inference requests can be slow
        on first warm-up; ``60s`` is the documented default.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        timeout: float = 60.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.base_url = (base_url or config.NLP_URL).rstrip("/")
        self._timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)

    # --- generic helpers -------------------------------------------------

    def _get(self, path: str) -> dict[str, Any]:
        r = self._client.get(f"{self.base_url}{path}")
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        r = self._client.post(f"{self.base_url}{path}", json=body)
        r.raise_for_status()
        return r.json()

    # --- endpoint wrappers ----------------------------------------------

    def health(self) -> dict[str, Any]:
        return self._get("/health")

    def version(self) -> dict[str, Any]:
        return self._get("/version")

    def extract(
        self,
        passages: Sequence[dict[str, Any]],
        *,
        min_score: float = 0.5,
        include_layer_a: bool = True,
        include_layer_b: bool = True,
        max_passage_chars: int = 16000,
    ) -> dict[str, Any]:
        body = {
            "passages": list(passages),
            "min_score": min_score,
            "include_layer_a": include_layer_a,
            "include_layer_b": include_layer_b,
            "max_passage_chars": max_passage_chars,
        }
        return self._post("/extract", body)

    def classify_sections(
        self,
        sections: Sequence[dict[str, Any]],
        *,
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        body = {"sections": list(sections), "threshold": threshold}
        return self._post("/classify_section", body)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BcfNlpClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


__all__ = ["BcfNlpClient"]
