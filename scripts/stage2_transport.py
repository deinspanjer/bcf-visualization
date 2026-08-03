"""The single mockable seam between Stage 2 and the inference harness.

Inference rides an **already-subscribed agent harness** (the ``claude``
CLI), never a metered API. The ``anthropic`` SDK is deliberately absent
from ``pyproject.toml`` and must not be added (D-25).

Three measured facts shape every line of this module:

1. **Never pass the prompt positionally.** ``--tools``, ``--allowed-tools``
   and ``--mcp-config`` are variadic and swallow a trailing positional
   prompt, producing "Input must be provided either through stdin or as a
   prompt argument" *despite a prompt being present*. The prompt goes on
   stdin (04-RESEARCH.md Pitfall 6, reproduced twice).

2. **Never use ``--bare``.** Its help text states Anthropic auth becomes
   strictly ``ANTHROPIC_API_KEY``/``apiKeyHelper``, with OAuth and keychain
   never read — which would silently convert this into the metered path
   D-25 exists to avoid.

3. **Never treat exit 0 as success.** Refusals, permission denials, and
   MCP-connection failures *all* report ``is_error: false`` and
   ``subtype: "success"``. Success is **handler-side state** — did a
   schema-valid submission reach the handler — checked by this caller
   after the subprocess returns. ``is_error``, ``subtype``, ``num_turns``,
   ``permission_denials`` and ``usage`` are logged as corroborating
   signals and gated on by nothing (04-RESEARCH.md Pitfall 1).

The CLI's ``result`` string is not the channel and is never parsed for
structured data: given a prose-inviting prompt the model called the submit
tool *and* answered in prose, so the prose is not evidence either way.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from stage2_mcp_server import RunningStage2Server
except ImportError:  # pragma: no cover - import-path shim
    from scripts.stage2_mcp_server import RunningStage2Server  # type: ignore[no-redef]


CLAUDE_BIN = "claude"
DEFAULT_MODEL = "opus"
# Measured floor is ~9s of harness overhead; 180s is ~20x headroom.
DEFAULT_TIMEOUT_SECONDS = 180.0

MCP_TOOL_NAMES = (
    "mcp__bcf__submit_stage2_rolls",
    "mcp__bcf__get_prose_span",
    "mcp__bcf__check_quote",
)

# Ledger states (Phase 5 consumes these; Phase 4 only reports them).
STATE_ROUTED = "routed"
STATE_NO_SUBMISSION = "no_submission"
STATE_TRANSPORT_ERROR = "transport_error"
STATE_TIMEOUT = "timeout"
STATE_AUTH_ERROR = "auth_error"


@dataclass
class HarnessResult:
    """Outcome of one chapter invocation.

    ``submitted`` is the ONLY success signal. Everything else is
    diagnostic.
    """

    submitted: bool
    submission: dict[str, Any] | None
    state: str
    turns: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
    permission_denials: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: int = 0
    is_error: bool = False
    subtype: str | None = None
    returncode: int | None = None
    total_cost_usd: float | None = None
    raw_envelope: dict[str, Any] = field(default_factory=dict)
    error_detail: str | None = None


class Stage2Transport(Protocol):
    def run_chapter(
        self,
        chapter_num: str,
        system_prompt: str,
        user_message: str,
        *,
        model: str = DEFAULT_MODEL,
    ) -> HarnessResult:
        ...


def build_claude_argv(
    *, mcp_config_json: str, model: str, system_prompt: str
) -> list[str]:
    """Assemble the verified flag set.

    ``--allowed-tools`` is placed last precisely because it is variadic —
    nothing may follow it that could be swallowed. The prompt never
    appears here at all; it goes on stdin.
    """
    return [
        CLAUDE_BIN,
        "-p",
        "--strict-mcp-config",
        "--mcp-config",
        mcp_config_json,
        "--output-format",
        "json",
        "--model",
        model,
        # `dontAsk` enforces the allowlist and denies rather than
        # prompting, so a misconfigured run fails fast instead of hanging
        # on stdin. NEVER `bypassPermissions`: it was measured ignoring
        # --allowed-tools entirely.
        "--permission-mode",
        "dontAsk",
        # Remove Read/Write/Bash and every other built-in from the run.
        "--tools",
        "",
        "--system-prompt",
        system_prompt,
        "--no-session-persistence",
        "--allowed-tools",
        *MCP_TOOL_NAMES,
    ]


@dataclass
class ClaudeCliTransport:
    """Production transport: warm loopback MCP server + ``claude -p``."""

    running: RunningStage2Server
    # Returns the submission the handler received for this chapter, or
    # None. This is the success oracle -- never the exit code.
    take_submission: Callable[[str], dict[str, Any] | None]
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    def run_chapter(
        self,
        chapter_num: str,
        system_prompt: str,
        user_message: str,
        *,
        model: str = DEFAULT_MODEL,
    ) -> HarnessResult:
        argv = build_claude_argv(
            mcp_config_json=self.running.mcp_config_json(),
            model=model,
            system_prompt=system_prompt,
        )
        try:
            completed = subprocess.run(
                argv,
                input=user_message,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return HarnessResult(
                submitted=False,
                submission=self.take_submission(chapter_num),
                state=STATE_TIMEOUT,
                error_detail=f"no exit within {self.timeout}s",
            )

        envelope: dict[str, Any] = {}
        if completed.stdout:
            try:
                envelope = json.loads(completed.stdout)
            except json.JSONDecodeError:
                envelope = {}

        submission = self.take_submission(chapter_num)
        return _classify(
            submission=submission,
            envelope=envelope,
            returncode=completed.returncode,
            stderr=completed.stderr,
        )


def _classify(
    *,
    submission: dict[str, Any] | None,
    envelope: dict[str, Any],
    returncode: int | None,
    stderr: str = "",
) -> HarnessResult:
    """Turn an envelope plus handler-side state into a result.

    Deliberately reads ``submission`` first: the envelope cannot promote a
    run to success, and cannot demote one either.
    """
    is_error = bool(envelope.get("is_error", False))
    result = HarnessResult(
        submitted=submission is not None,
        submission=submission,
        state=STATE_ROUTED if submission is not None else STATE_NO_SUBMISSION,
        turns=int(envelope.get("num_turns") or 0),
        usage=envelope.get("usage") or {},
        permission_denials=envelope.get("permission_denials") or [],
        duration_ms=int(envelope.get("duration_ms") or 0),
        is_error=is_error,
        subtype=envelope.get("subtype"),
        returncode=returncode,
        total_cost_usd=envelope.get("total_cost_usd"),
        raw_envelope=envelope,
    )

    if submission is not None:
        return result

    # No submission: distinguish "the model declined" from "the transport
    # broke", because they have different restart behaviour. An auth error
    # must abort the whole run rather than burn every remaining chapter.
    if returncode not in (0, None) or is_error:
        blob = f"{stderr}\n{envelope.get('result') or ''}".lower()
        if "auth" in blob or "login" in blob or "unauthor" in blob:
            result.state = STATE_AUTH_ERROR
        else:
            result.state = STATE_TRANSPORT_ERROR
        result.error_detail = (stderr or envelope.get("result") or "").strip()[:500]
    return result


@dataclass
class RecordedTransport:
    """Test transport: replays a canned submission. No subprocess, no MCP.

    Only the final submission payload is replayed -- never a multi-turn
    transcript. With read tools in the surface a transcript replay is
    brittle and proves nothing the payload does not.
    """

    submission: dict[str, Any] | None = None
    state: str = STATE_ROUTED
    usage: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def run_chapter(
        self,
        chapter_num: str,
        system_prompt: str,
        user_message: str,
        *,
        model: str = DEFAULT_MODEL,
    ) -> HarnessResult:
        self.calls.append(
            {
                "chapter_num": chapter_num,
                "system_prompt": system_prompt,
                "user_message": user_message,
                "model": model,
            }
        )
        return HarnessResult(
            submitted=self.submission is not None,
            submission=self.submission,
            state=self.state,
            usage=dict(self.usage),
            turns=1,
        )
