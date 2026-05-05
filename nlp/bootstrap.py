"""LLM-based annotation bootstrap for the BCF labeling pipeline.

Calls llama.cpp's OpenAI-compatible /v1/chat/completions endpoint to
obtain span proposals for a passage, then validates and persists them.

Typical usage::

    from nlp.bootstrap import propose, propose_batch
    proposal = propose(passage_text, passage_id="ch1_p0")

Environment variables
---------------------
BCF_LLAMACPP_URL : base URL for llama.cpp (default http://localhost:11434)

See docs/local_nlp_annotation_playbook.md §"Bootstrap proposals".
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from nlp.proposals import Proposal, ProposedSpan

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_SYSTEM_PROMPT_PATH = _HERE / "prompts" / "labeling_system.txt"
_QUICKREF_PATH = _HERE / "prompts" / "label_quickref.md"

_QUICKREF_MARKER = "<INSERT label quickref here at proposal time>"

# Cheap token proxy: 1 token ≈ 4 chars
_CHARS_PER_TOKEN = 4
_MAX_SYSTEM_TOKENS = 2000
_MAX_SYSTEM_CHARS = _MAX_SYSTEM_TOKENS * _CHARS_PER_TOKEN
_WARN_SYSTEM_CHARS = 8000  # warn if still above this after capping

_DEFAULT_TIMEOUT = 120.0
_DEFAULT_RAW_DIR = Path("data/labeled/.proposals_raw")
_MAX_RETRIES = 2

_CHAT_PARAMS: dict[str, Any] = {
    "temperature": 0.1,
    "top_p": 0.9,
    "max_tokens": 512,
    "response_format": {"type": "json_object"},
}

_CORRECTIVE_ADDENDUM = (
    "Your previous output had span offsets that did not match the substring. "
    "Re-emit valid JSON with corrected start/end offsets so that "
    "passage_text[start:end] equals the span text you intended."
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_system_prompt() -> str:
    """Load and expand the system prompt, then truncate to token budget."""
    system_raw = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    quickref = _QUICKREF_PATH.read_text(encoding="utf-8")
    system = system_raw.replace(_QUICKREF_MARKER, quickref)

    if len(system) > _MAX_SYSTEM_CHARS:
        # Trim the quickref by shortening it proportionally
        overflow = len(system) - _MAX_SYSTEM_CHARS
        trimmed_quickref = quickref[: max(0, len(quickref) - overflow)]
        system = system_raw.replace(_QUICKREF_MARKER, trimmed_quickref)
        warnings.warn(
            f"System prompt truncated to ~{_MAX_SYSTEM_TOKENS} tokens "
            f"(quickref trimmed by {overflow} chars).",
            stacklevel=3,
        )

    if len(system) > _WARN_SYSTEM_CHARS:
        warnings.warn(
            f"System prompt is {len(system)} chars (>{_WARN_SYSTEM_CHARS}). "
            "Consider trimming the quickref.",
            stacklevel=3,
        )

    return system


def _build_user_prompt(passage_text: str) -> str:
    return f'Passage:\n"""\n{passage_text}\n"""\n\nEmit only the JSON object.'


def _validate_spans(
    passage_text: str, raw_spans: list[dict[str, Any]]
) -> tuple[list[ProposedSpan], list[str]]:
    """Parse and validate spans from LLM output.

    Returns (valid_spans, error_messages).  A span is invalid if
    passage_text[start:end] does not match the declared text field (when
    present) or if offsets are out of range.
    """
    valid: list[ProposedSpan] = []
    errors: list[str] = []
    n = len(passage_text)

    for item in raw_spans:
        try:
            layer = str(item.get("layer", ""))
            label = str(item.get("label", ""))
            start = int(item["start"])
            end = int(item["end"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"Span missing required field: {exc}")
            continue

        if start < 0 or end < 0 or start > n or end > n or start >= end:
            errors.append(
                f"Span {label!r} offsets out of range or inverted: [{start},{end}) "
                f"for text of length {n}"
            )
            continue

        declared_text: Optional[str] = item.get("text")
        if declared_text is not None:
            actual = passage_text[start:end]
            if actual != declared_text:
                errors.append(
                    f"Span {label!r} text mismatch: declared {declared_text!r} "
                    f"but passage[{start}:{end}] is {actual!r}"
                )
                continue

        confidence_raw = item.get("confidence")
        confidence: Optional[float] = None
        if confidence_raw is not None:
            try:
                confidence = float(confidence_raw)
                confidence = max(0.0, min(1.0, confidence))
            except (TypeError, ValueError):
                pass

        valid.append(
            ProposedSpan(
                layer=layer,
                label=label,
                start=start,
                end=end,
                confidence=confidence,
            )
        )

    return valid, errors


def _mean_confidence(spans: list[ProposedSpan]) -> Optional[float]:
    scores = [s.confidence for s in spans if s.confidence is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _persist_raw(
    raw_dir: Path,
    passage_id: str,
    attempt: int,
    raw_response: dict[str, Any],
) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if attempt == 0 else f"_attempt{attempt}"
    out_path = raw_dir / f"{passage_id}{suffix}.json"
    out_path.write_text(json.dumps(raw_response, indent=2, ensure_ascii=False), encoding="utf-8")


def _chat_completions(
    client: httpx.Client,
    base_url: str,
    messages: list[dict[str, str]],
    model: Optional[str],
    timeout: float,
) -> dict[str, Any]:
    """POST /v1/chat/completions and return parsed JSON."""
    payload: dict[str, Any] = {
        "messages": messages,
        **_CHAT_PARAMS,
    }
    if model:
        payload["model"] = model

    url = base_url.rstrip("/") + "/v1/chat/completions"
    resp = client.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose(
    passage_text: str,
    *,
    passage_id: str,
    llama_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = _DEFAULT_TIMEOUT,
    persist_raw_dir: Optional[Path] = None,
    _client: Optional[httpx.Client] = None,  # injection point for tests
) -> Proposal:
    """Call llama.cpp to propose spans for *passage_text*.

    Parameters
    ----------
    passage_text:
        The verbatim passage to annotate.
    passage_id:
        Stable identifier (e.g. ``"ch1_p0"``).
    llama_url:
        Base URL for llama.cpp.  Falls back to the ``BCF_LLAMACPP_URL``
        environment variable, then ``http://localhost:11434``.
    model:
        Model name to request.  If *None*, the llama.cpp router picks.
    timeout:
        HTTP request timeout in seconds.
    persist_raw_dir:
        Directory for raw model output.  Defaults to
        ``data/labeled/.proposals_raw``.

    Returns
    -------
    Proposal
        Validated span proposals plus audit data.

    Raises
    ------
    httpx.HTTPError
        On any HTTP-level failure (connection refused, 4xx, 5xx).
    """
    base_url = llama_url or os.environ.get("BCF_LLAMACPP_URL", "http://localhost:11434")
    raw_dir = persist_raw_dir if persist_raw_dir is not None else _DEFAULT_RAW_DIR

    system_prompt = _load_system_prompt()
    user_prompt = _build_user_prompt(passage_text)

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    own_client = _client is None
    client = _client or httpx.Client()

    try:
        spans: list[ProposedSpan] = []
        raw_response: dict[str, Any] = {}
        model_name: str = model or ""

        for attempt in range(_MAX_RETRIES + 1):
            raw_response = _chat_completions(client, base_url, messages, model, timeout)

            # Extract model name from response when not supplied
            if not model_name:
                model_name = raw_response.get("model", model or "")

            # Parse content
            content_str: str = ""
            try:
                content_str = raw_response["choices"][0]["message"]["content"]
                content_obj = json.loads(content_str)
                raw_spans = content_obj.get("spans", [])
            except (KeyError, IndexError, json.JSONDecodeError) as exc:
                if attempt < _MAX_RETRIES:
                    messages.append(
                        {"role": "assistant", "content": content_str or ""}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Your previous output was not valid JSON. "
                                "Re-emit a single JSON object with a 'spans' array."
                            ),
                        }
                    )
                    continue
                # Exhausted retries
                _persist_raw(raw_dir, passage_id, attempt, raw_response)
                warnings.warn(
                    f"bootstrap: could not parse JSON for {passage_id!r} after "
                    f"{attempt+1} attempt(s): {exc}",
                    stacklevel=2,
                )
                return Proposal(
                    passage_id=passage_id,
                    model_name=model_name,
                    spans=[],
                    raw_response=raw_response,
                    mean_confidence=None,
                )

            valid_spans, errors = _validate_spans(passage_text, raw_spans)

            if errors and attempt < _MAX_RETRIES:
                error_summary = "; ".join(errors[:3])
                messages.append({"role": "assistant", "content": content_str})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"{_CORRECTIVE_ADDENDUM} "
                            f"Specific errors: {error_summary}"
                        ),
                    }
                )
                continue

            # Persist raw (final attempt)
            _persist_raw(raw_dir, passage_id, attempt, raw_response)

            if errors:
                warnings.warn(
                    f"bootstrap: {len(errors)} span(s) dropped for {passage_id!r} "
                    f"after {attempt+1} attempt(s): {errors[0]}",
                    stacklevel=2,
                )

            spans = valid_spans
            break

        return Proposal(
            passage_id=passage_id,
            model_name=model_name,
            spans=spans,
            raw_response=raw_response,
            mean_confidence=_mean_confidence(spans),
        )

    finally:
        if own_client:
            client.close()


def propose_batch(
    passages: Iterable[tuple[str, str]],
    **kwargs: Any,
) -> list[Proposal]:
    """Call :func:`propose` for each ``(passage_id, text)`` pair.

    Sequential — llama.cpp is single-stream.  Shows a tqdm progress bar
    if tqdm is available.

    Parameters
    ----------
    passages:
        Iterable of ``(passage_id, passage_text)`` tuples.
    **kwargs:
        Forwarded to :func:`propose` (``llama_url``, ``model``, etc.).
    """
    passage_list = list(passages)

    try:
        from tqdm import tqdm  # type: ignore[import-untyped]

        iterable: Iterable[tuple[str, str]] = tqdm(
            passage_list, desc="Bootstrapping proposals", unit="passage"
        )
    except ImportError:
        iterable = passage_list

    results: list[Proposal] = []
    for passage_id, text in iterable:
        results.append(propose(text, passage_id=passage_id, **kwargs))
    return results


__all__ = ["propose", "propose_batch"]
