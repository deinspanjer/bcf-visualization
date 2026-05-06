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
    # Each span now carries a verbatim text field; budget room for ~10
    # spans plus their substrings (event spans can be 30-80 chars, entity
    # spans 5-30 chars).  Truncation mid-string causes JSON parse fails.
    "max_tokens": 2048,
    "response_format": {"type": "json_object"},
}

_CORRECTIVE_ADDENDUM = (
    "Some of your spans had text that does not appear verbatim in the passage, "
    "or were missing required fields. Re-emit valid JSON: every span MUST "
    "include a 'text' field whose value is a verbatim substring of the "
    "passage (same case, same punctuation, no quotes around it). Offsets "
    "are optional hints; the system locates the substring for you."
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


def _format_roll_context(ctx: dict) -> str:
    """Format a roll_context dict as a human-readable section for the user prompt.

    Skips any bullet that would have an empty/null value.  Uses defensive
    .get() throughout so missing keys never raise.
    """
    lines: list[str] = ["Chapter context for the predicted roll near this passage:"]

    chapter_num = ctx.get("chapter_num")
    section_index = ctx.get("section_index")
    if chapter_num is not None and section_index is not None:
        lines.append(f"- Chapter {chapter_num}, section {section_index}")
    elif chapter_num is not None:
        lines.append(f"- Chapter {chapter_num}")

    anchor = ctx.get("anchor_string")
    if anchor:
        lines.append(f'- Anchor string just before the predicted roll position:\n    "{anchor}"')

    banked = ctx.get("banked_at_roll")
    banked_src = ctx.get("banked_at_roll_source")
    if banked is not None:
        src_tag = f" ({banked_src})" if banked_src else ""
        lines.append(f"- Banked CP at roll: {banked}{src_tag}")

    # Chapter attribution disagreement disclaimer
    if ctx.get("chapter_attribution_disagreement"):
        curator_ch = ctx.get("curator_chapter_num")
        lines.append(
            f"- ⚠ Chapter attribution disagreement: the curator placed this roll in"
            f" chapter {curator_ch}, the simulator places it in chapter {chapter_num}."
            " The curator's reported perk may not appear in this passage."
        )

    # Outcome block
    outcome = ctx.get("curator_outcome")
    if outcome == "HIT":
        perk = ctx.get("curator_perk_name") or "unknown"
        constellation = ctx.get("curator_constellation") or "unknown"
        cost = ctx.get("curator_cost")
        cost_str = str(cost) if cost is not None else "unknown"
        free_raw = ctx.get("curator_free_associated_perks")
        if free_raw:
            if isinstance(free_raw, list):
                free_names = ", ".join(str(p) for p in free_raw)
            else:
                free_names = str(free_raw)
            free_str = f" Free associates: {free_names}."
        else:
            free_str = ""
        lines.append(
            f'- Curator-validated outcome: HIT for "{perk}" in "{constellation}"'
            f" (cost {cost_str}).{free_str}"
            " Find the prose narration of the Forge reaching and grabbing this perk near the anchor."
        )
    elif outcome == "MISS":
        constellation = ctx.get("curator_constellation")
        const_str = f'"{constellation}"' if constellation else "constellation unknown"
        banked_val = ctx.get("banked_at_roll")
        banked_note = (
            f" By definition, the rolled-for perk had a cost greater than {banked_val}."
            if banked_val is not None
            else ""
        )
        lines.append(
            f"- Curator-validated outcome: MISS in {const_str}."
            " Find the prose narration of the Forge reaching and failing near the anchor."
            + banked_note
        )
    elif outcome is None:
        lines.append(
            "- Outcome unknown — the prose narration will reveal HIT or MISS."
            " If HIT, the perk is one of the listed acquired perks (the next unmatched one"
            " in narrative order). If MISS, the rolled-for perk is somewhere in the"
            " outstanding-miss-candidates list (cost > banked)."
        )

    acquired = ctx.get("chapter_acquired_perks_in_order")
    if acquired:
        if isinstance(acquired, list):
            names = ", ".join(p.get("name", str(p)) if isinstance(p, dict) else str(p) for p in acquired)
        else:
            names = str(acquired)
        lines.append(f"- This chapter's acquired perks in order: {names}")

    outstanding = ctx.get("outstanding_perks_with_cost_gt_banked")
    if outstanding:
        if isinstance(outstanding, list):
            parts = []
            for p in outstanding:
                if isinstance(p, dict):
                    name = p.get("name", "?")
                    cost = p.get("cost")
                    cost_tag = f" ({cost} CP)" if cost is not None else ""
                    parts.append(f"{name}{cost_tag}")
                else:
                    parts.append(str(p))
            out_str = ", ".join(parts)
        else:
            out_str = str(outstanding)
        lines.append(f"- Outstanding miss candidates (cost > banked, top 5): {out_str}")

    known = ctx.get("constellations_known_by_joe")
    if known:
        if isinstance(known, list):
            known_str = ", ".join(str(k) for k in known)
        else:
            known_str = str(known)
        lines.append(f"- Constellations Joe currently knows by name: {known_str}")

    return "\n".join(lines)


def _build_user_prompt(passage_text: str, roll_context: Optional[dict] = None) -> str:
    """Build the user-turn prompt.

    Parameters
    ----------
    passage_text:
        Verbatim passage to annotate.
    roll_context:
        Optional per-roll context dict from roll_resolutions.json.  When
        provided, a formatted context block is appended after the passage.
    """
    parts = [f'Passage:\n"""\n{passage_text}\n"""']
    if roll_context is not None:
        parts.append(_format_roll_context(roll_context))
    parts.append("Emit only the JSON object.")
    return "\n\n".join(parts)


def _strip_code_fence(content: str) -> str:
    """Strip leading/trailing markdown code fences if present.

    Reasoning models (e.g. DeepSeek-R1-Distill) often wrap JSON in
    ``` ```json ... ``` ``` blocks even when ``response_format=json_object``
    is requested.  llama.cpp's enforcement is best-effort.
    """
    s = content.strip()
    if s.startswith("```"):
        # Drop opening fence (with optional language tag) and closing fence
        first_newline = s.find("\n")
        if first_newline > 0:
            s = s[first_newline + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].rstrip()
    return s


def _resolve_offsets(
    passage_text: str,
    declared_text: str,
    hint_start: Optional[int],
) -> Optional[tuple[int, int]]:
    """Find the offsets of *declared_text* in *passage_text*.

    Returns ``(start, end)`` if found, or ``None`` if the declared text
    does not appear at all.  When the substring appears multiple times,
    the occurrence closest to *hint_start* (if provided) wins; otherwise
    the first occurrence wins.
    """
    if not declared_text:
        return None

    occurrences: list[int] = []
    pos = 0
    n = len(passage_text)
    while pos <= n - len(declared_text):
        found = passage_text.find(declared_text, pos)
        if found < 0:
            break
        occurrences.append(found)
        pos = found + 1  # allow overlapping matches; rare but possible

    if not occurrences:
        return None

    if len(occurrences) == 1 or hint_start is None:
        start = occurrences[0]
    else:
        start = min(occurrences, key=lambda p: abs(p - hint_start))

    return start, start + len(declared_text)


def _validate_spans(
    passage_text: str, raw_spans: list[dict[str, Any]]
) -> tuple[list[ProposedSpan], list[str], dict[str, int]]:
    """Parse and validate spans from LLM output.

    The ``text`` field is the source of truth: when present, the system
    locates the substring in the passage and snaps offsets to the actual
    location (using LLM-provided offsets as a disambiguation hint when
    the substring appears multiple times).  When ``text`` is absent, the
    LLM's offsets are used directly as a backwards-compatible fallback.

    Returns ``(valid_spans, errors, stats)`` where ``stats`` counts how
    many spans were resolved by exact-offset, snap-via-text, or
    text-only fallback (useful for diagnostics).
    """
    valid: list[ProposedSpan] = []
    errors: list[str] = []
    stats = {"exact": 0, "snapped": 0, "offset_only": 0}
    n = len(passage_text)

    for item in raw_spans:
        try:
            layer = str(item.get("layer", ""))
            label = str(item.get("label", ""))
        except (TypeError, ValueError) as exc:
            errors.append(f"Span missing required field: {exc}")
            continue

        declared_text_raw = item.get("text")
        declared_text: Optional[str] = (
            declared_text_raw if isinstance(declared_text_raw, str) and declared_text_raw else None
        )

        # LLM offsets are now optional hints
        hint_start: Optional[int] = None
        hint_end: Optional[int] = None
        try:
            if item.get("start") is not None:
                hint_start = int(item["start"])
            if item.get("end") is not None:
                hint_end = int(item["end"])
        except (TypeError, ValueError):
            hint_start = hint_end = None

        if declared_text is not None:
            # Text-first: try the LLM-provided offsets first (cheap), then snap.
            start = end = -1
            if (
                hint_start is not None
                and hint_end is not None
                and 0 <= hint_start < hint_end <= n
                and passage_text[hint_start:hint_end] == declared_text
            ):
                start, end = hint_start, hint_end
                stats["exact"] += 1
            else:
                resolved = _resolve_offsets(passage_text, declared_text, hint_start)
                if resolved is None:
                    errors.append(
                        f"Span {label!r}: text {declared_text!r} not found in passage"
                    )
                    continue
                start, end = resolved
                stats["snapped"] += 1
        else:
            # Backwards-compatible fallback: trust LLM offsets.
            if hint_start is None or hint_end is None:
                errors.append(
                    f"Span {label!r}: missing both 'text' and offsets"
                )
                continue
            if hint_start < 0 or hint_end < 0 or hint_start > n or hint_end > n or hint_start >= hint_end:
                errors.append(
                    f"Span {label!r}: offsets out of range or inverted: "
                    f"[{hint_start},{hint_end}) for text of length {n}"
                )
                continue
            start, end = hint_start, hint_end
            stats["offset_only"] += 1

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

    return valid, errors, stats


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
    roll_context: Optional[dict[str, Any]] = None,
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
    roll_context:
        Optional per-roll context dict (from roll_resolutions.json via
        Candidate.roll_context).  When provided, a formatted context block
        is appended to the user-turn prompt so the LLM sees chapter context.

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
    user_prompt = _build_user_prompt(passage_text, roll_context=roll_context)

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
                content_obj = json.loads(_strip_code_fence(content_str))
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

            valid_spans, errors, stats = _validate_spans(passage_text, raw_spans)

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

            if stats["snapped"] or stats["offset_only"]:
                # Diagnostic — useful when comparing models or tuning prompts.
                warnings.warn(
                    f"bootstrap: {passage_id!r} resolution stats "
                    f"exact={stats['exact']} snapped={stats['snapped']} "
                    f"offset_only={stats['offset_only']}",
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
