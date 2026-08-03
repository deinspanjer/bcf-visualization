"""Structural guarantees of the Stage 2 propose-only MCP tool surface.

These tests never perform live inference and never speak JSON-RPC. They
call the registered handlers directly, which is enough to exercise the
real ``jsonschema`` validation path because that validation lives inside
the low-level ``Server``'s ``call_tool`` wrapper.

Handlers are async; the tests drive them with ``asyncio.run`` rather than
``pytest.mark.asyncio`` so they do not depend on the repo's
``asyncio_mode`` configuration.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# `mcp` lives in the optional `curation` extra. A base install must keep
# `scripts/verify.py`, the Forge Curator TUI, and the derived-data
# pipeline runnable, so these tests skip rather than fail when it is
# absent.
pytest.importorskip("mcp", reason="requires the `curation` optional extra")

import mcp.types as types  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

from scripts.stage2_mcp_server import (  # noqa: E402
    ReadToolBudget,
    RecordingStage2Context,
    build_stage2_server,
    serve_stage2_http,
)
from scripts.stage2_schema import (  # noqa: E402
    MAX_CHECK_QUOTE_CALLS,
    MAX_PROSE_SPAN_CALLS,
    MAX_PROSE_SPAN_WORDS,
    STAGE2_TOOL_NAMES,
    SUBMIT_STAGE2_ROLLS_SCHEMA,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _list_tools(server) -> list[types.Tool]:
    result = asyncio.run(server.request_handlers[types.ListToolsRequest](None))
    return list(result.root.tools)


def _call_tool(server, name: str, arguments: dict) -> types.CallToolResult:
    req = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    result = asyncio.run(server.request_handlers[types.CallToolRequest](req))
    return result.root


def _text_of(result: types.CallToolResult) -> str:
    return "\n".join(
        block.text for block in result.content if isinstance(block, types.TextContent)
    )


# ---------------------------------------------------------------------------
# T-04-01 -- the propose-only invariant
# ---------------------------------------------------------------------------

def test_tool_surface_is_propose_only() -> None:
    """The tool set is exactly three tools, asserted by set equality.

    Set equality rather than a membership check is deliberate: it is what
    makes adding a fourth tool fail a test instead of passing silently.
    """
    server = build_stage2_server(RecordingStage2Context())
    tools = _list_tools(server)
    names = {tool.name for tool in tools}

    assert names == {"submit_stage2_rolls", "get_prose_span", "check_quote"}
    assert names == set(STAGE2_TOOL_NAMES)

    # No tool may write, route, set confidence, or name a destination.
    forbidden = ("write", "route", "set_confidence", "destination", "overrides")
    for tool in tools:
        for token in forbidden:
            assert token not in tool.name.lower(), f"{tool.name} suggests write authority"
        properties = (tool.inputSchema.get("properties") or {}).keys()
        for prop in properties:
            assert "destination" not in prop.lower()
            assert "confidence" not in prop.lower() or prop == "self_reported_confidence"

    # Every tool carries a hand-written schema that closes the object.
    for tool in tools:
        assert tool.inputSchema.get("additionalProperties") is False


def test_no_corpus_write_path_in_stage2_modules() -> None:
    """Phase 4 has no corpus write path at all.

    This removes the failure mode rather than checking for it, and so
    proves more than any routing test could.
    """
    targets = sorted(SCRIPTS.glob("stage2_*.py"))
    runner = SCRIPTS / "run_stage2_chapter.py"
    if runner.exists():
        targets.append(runner)
    assert targets, "expected Stage 2 modules to exist"

    for path in targets:
        source = path.read_text()
        assert "write_chapter_roll_overrides_doc" not in source, (
            f"{path.name} imports or calls the corpus writer; Phase 4 must "
            "have no corpus write path"
        )


# ---------------------------------------------------------------------------
# T-04-05 -- schema strictness is the D-26 guarantee
# ---------------------------------------------------------------------------

def test_submit_schema_rejects_malformed() -> None:
    """Explicit schemas reject what a signature-derived schema coerces."""
    validator = Draft202012Validator(SUBMIT_STAGE2_ROLLS_SCHEMA)

    valid = {"chapter_num": "104", "rolls": [{"slot_index": 0}]}
    assert validator.is_valid(valid)

    # The exact coercion research measured FastMCP performing: integer 104
    # silently becoming "104". A coerced chapter_num feeds mechanical
    # position derivation, so this must be a hard rejection.
    assert not validator.is_valid({"chapter_num": 104, "rolls": []})

    # A string where an integer is required.
    assert not validator.is_valid(
        {"chapter_num": "104", "rolls": [{"slot_index": "0"}]}
    )

    # Unknown top-level key.
    assert not validator.is_valid(
        {"chapter_num": "104", "rolls": [], "destination": "corpus"}
    )

    # Unknown per-roll key -- notably any attempt to supply a position,
    # which D-10 reserves for mechanical derivation.
    assert not validator.is_valid(
        {"chapter_num": "104", "rolls": [{"slot_index": 0, "word_position": 2861}]}
    )
    assert not validator.is_valid(
        {
            "chapter_num": "104",
            "rolls": [
                {
                    "slot_index": 0,
                    "evidence_quotes": [
                        {"text": "a quote", "mention_word_position": 8241}
                    ],
                }
            ],
        }
    )

    # slot_index is mandatory -- mapping is never positional.
    assert not validator.is_valid({"chapter_num": "104", "rolls": [{"perks": []}]})

    # Legitimate partial outcomes stay valid.
    assert validator.is_valid({"chapter_num": "121.1", "rolls": []})
    assert validator.is_valid(
        {
            "chapter_num": "121.1",
            "rolls": [
                {
                    "slot_index": 0,
                    "outcome": "miss",
                    "constellation": "Knowledge",
                    "evidence_quotes": [],
                    "unfilled_fields": ["evidence_quotes"],
                }
            ],
        }
    )


def test_malformed_submission_returns_is_error_through_the_server() -> None:
    """The correction signal reaches the model, not just the test.

    ``validate_input=True`` is what turns a schema violation into an
    ``isError`` tool result. Without it there is no guarantee at all --
    the MCP spec places the input-validation MUST on servers.
    """
    ctx = RecordingStage2Context()
    server = build_stage2_server(ctx)

    result = _call_tool(server, "submit_stage2_rolls", {"chapter_num": 104, "rolls": []})

    assert result.isError is True
    assert "validation" in _text_of(result).lower()
    # A rejected submission never reaches the handler.
    assert ctx.submissions == []


def test_valid_submission_reaches_the_handler() -> None:
    ctx = RecordingStage2Context()
    server = build_stage2_server(ctx)

    payload = {
        "chapter_num": "92",
        "rolls": [
            {
                "slot_index": 0,
                "outcome": "miss",
                "constellation": "Knowledge",
                "evidence_quotes": [
                    {"text": "I felt the Forge fail to connect to a massive mote"}
                ],
            }
        ],
    }
    result = _call_tool(server, "submit_stage2_rolls", payload)

    assert result.isError in (False, None)
    assert len(ctx.submissions) == 1
    assert ctx.submissions[0]["chapter_num"] == "92"
    assert ctx.submissions[0]["rolls"][0]["slot_index"] == 0

    # The model must not learn where its submission went, or the next
    # turn's proposals get steered by the destination.
    summary = _text_of(result).lower()
    for leak in ("corpus", "proposals", "chapter_roll_overrides", "high confidence"):
        assert leak not in summary


# ---------------------------------------------------------------------------
# T-04-07 / D-30 -- read-tool caps
# ---------------------------------------------------------------------------

def test_read_tool_caps_inclusive() -> None:
    """Caps are inclusive integer comparisons.

    The 5th ``get_prose_span`` and the 20th ``check_quote`` for a chapter
    succeed; the 6th and 21st are refused. An off-by-one here silently
    costs the model its last allowed read.
    """
    ctx = RecordingStage2Context()
    server = build_stage2_server(ctx, budget=ReadToolBudget())

    for call_number in range(1, MAX_PROSE_SPAN_CALLS + 1):
        result = _call_tool(
            server,
            "get_prose_span",
            {"chapter_num": "92", "start_word": 0, "end_word": 100},
        )
        assert result.isError in (False, None), f"span call {call_number} refused"
    assert len(ctx.prose_span_requests) == MAX_PROSE_SPAN_CALLS

    over = _call_tool(
        server, "get_prose_span", {"chapter_num": "92", "start_word": 0, "end_word": 100}
    )
    assert over.isError is True
    assert len(ctx.prose_span_requests) == MAX_PROSE_SPAN_CALLS

    for call_number in range(1, MAX_CHECK_QUOTE_CALLS + 1):
        result = _call_tool(
            server, "check_quote", {"chapter_num": "92", "quote_text": "a quote"}
        )
        assert result.isError in (False, None), f"quote call {call_number} refused"
    assert len(ctx.check_quote_requests) == MAX_CHECK_QUOTE_CALLS

    over = _call_tool(
        server, "check_quote", {"chapter_num": "92", "quote_text": "a quote"}
    )
    assert over.isError is True
    assert len(ctx.check_quote_requests) == MAX_CHECK_QUOTE_CALLS


def test_prose_span_budget_is_per_chapter() -> None:
    ctx = RecordingStage2Context()
    server = build_stage2_server(ctx, budget=ReadToolBudget())

    for _ in range(MAX_PROSE_SPAN_CALLS):
        _call_tool(
            server,
            "get_prose_span",
            {"chapter_num": "92", "start_word": 0, "end_word": 10},
        )
    # A different chapter gets its own budget.
    result = _call_tool(
        server, "get_prose_span", {"chapter_num": "104", "start_word": 0, "end_word": 10}
    )
    assert result.isError in (False, None)


def test_exactly_max_span_words_is_served_in_full() -> None:
    """A span of exactly MAX_PROSE_SPAN_WORDS is allowed, not truncated."""
    ctx = RecordingStage2Context()
    ctx.prose_span_reply = "word " * MAX_PROSE_SPAN_WORDS
    server = build_stage2_server(ctx, budget=ReadToolBudget())

    result = _call_tool(
        server,
        "get_prose_span",
        {"chapter_num": "92", "start_word": 1000, "end_word": 1000 + MAX_PROSE_SPAN_WORDS},
    )
    assert result.isError in (False, None)
    assert len(_text_of(result).split()) == MAX_PROSE_SPAN_WORDS

    oversized = _call_tool(
        server,
        "get_prose_span",
        {
            "chapter_num": "92",
            "start_word": 1000,
            "end_word": 1001 + MAX_PROSE_SPAN_WORDS,
        },
    )
    assert oversized.isError is True


def test_read_tools_are_side_effect_free() -> None:
    """Read tools serve information and return no destination.

    A read tool cannot make the model the writer, cannot mutate the
    corpus, and cannot choose a destination -- which is why "propose-only"
    binds write authority rather than information flow.
    """
    ctx = RecordingStage2Context()
    server = build_stage2_server(ctx, budget=ReadToolBudget())

    _call_tool(
        server, "get_prose_span", {"chapter_num": "92", "start_word": 0, "end_word": 50}
    )
    result = _call_tool(
        server, "check_quote", {"chapter_num": "92", "quote_text": "a quote"}
    )

    # Nothing was submitted by a read call.
    assert ctx.submissions == []

    payload = json.loads(_text_of(result))
    assert set(payload) == {"found", "tier", "word_position", "occurrence_count"}
    for banned in ("destination", "route", "confidence", "corpus", "proposals"):
        assert banned not in payload


def test_duplicate_slot_index_returns_is_error_to_the_model() -> None:
    """The correction signal for a duplicate slot reaches the model."""

    class _Rejecting(RecordingStage2Context):
        def submit_rolls(self, chapter_num, rolls):
            from scripts.stage2_response import _index_submitted_rolls

            _index_submitted_rolls(rolls)
            return "ok"

    server = build_stage2_server(_Rejecting())
    result = _call_tool(
        server,
        "submit_stage2_rolls",
        {
            "chapter_num": "92",
            "rolls": [{"slot_index": 1}, {"slot_index": 1}],
        },
    )

    assert result.isError is True
    assert "slot_index" in _text_of(result)


# ---------------------------------------------------------------------------
# T-04-06 -- the server never outlives its run
# ---------------------------------------------------------------------------

def _port_is_free(host: str, port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.settimeout(1.0)
        return probe.connect_ex((host, port)) != 0
    finally:
        probe.close()


def test_server_shutdown_on_exception() -> None:
    """Raising inside the run body still closes the listening socket.

    A leaked propose-only server is a real hazard: its handler is what
    routes and writes. Teardown therefore lives in a ``finally``, not at
    the end of the happy path.
    """
    server = build_stage2_server(RecordingStage2Context())

    captured_port = None
    with pytest.raises(RuntimeError, match="boom"):
        with serve_stage2_http(server) as running:
            captured_port = running.port
            assert running.host == "127.0.0.1", "must never bind 0.0.0.0"
            assert not _port_is_free("127.0.0.1", running.port)
            raise RuntimeError("boom")

    assert captured_port is not None
    assert _port_is_free("127.0.0.1", captured_port), "server socket leaked"


def test_server_binds_loopback_on_ephemeral_port() -> None:
    server = build_stage2_server(RecordingStage2Context())

    with serve_stage2_http(server) as running:
        assert running.host == "127.0.0.1"
        assert running.port != 0
        config = running.mcp_config()
        assert config["mcpServers"]["bcf"]["type"] == "http"
        assert config["mcpServers"]["bcf"]["url"] == (
            f"http://127.0.0.1:{running.port}/mcp"
        )
        port = running.port

    assert _port_is_free("127.0.0.1", port)


# ---------------------------------------------------------------------------
# Transport flag discipline (measured failure modes)
# ---------------------------------------------------------------------------

def test_claude_argv_never_passes_prompt_positionally() -> None:
    from scripts.stage2_transport import build_claude_argv

    argv = build_claude_argv(
        mcp_config_json='{"mcpServers":{}}', model="opus", system_prompt="PREFIX"
    )

    # `--bare` forces ANTHROPIC_API_KEY auth and would silently defeat the
    # no-metered-spend decision.
    assert "--bare" not in argv
    assert "bypassPermissions" not in argv
    assert "--permission-mode" in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"

    # --allowed-tools is variadic, so nothing may follow it.
    assert argv.index("--allowed-tools") < len(argv) - 1
    tail = argv[argv.index("--allowed-tools") + 1:]
    assert all(item.startswith("mcp__bcf__") for item in tail)


def test_exit_zero_is_not_success() -> None:
    """A clean exit with no submission is a failure, not a success."""
    from scripts.stage2_transport import STATE_NO_SUBMISSION, _classify

    envelope = {
        "is_error": False,
        "subtype": "success",
        "num_turns": 1,
        "result": "I'm sorry, I can't help with that.",
        "permission_denials": [],
        "usage": {"input_tokens": 8},
    }
    result = _classify(submission=None, envelope=envelope, returncode=0)

    assert result.submitted is False
    assert result.state == STATE_NO_SUBMISSION
    # Corroborating signals are recorded, never gated on.
    assert result.turns == 1
    assert result.usage == {"input_tokens": 8}


def test_submission_defines_success_even_with_noisy_envelope() -> None:
    from scripts.stage2_transport import STATE_ROUTED, _classify

    envelope = {"is_error": False, "subtype": "success", "num_turns": 4}
    result = _classify(
        submission={"chapter_num": "92", "rolls": []},
        envelope=envelope,
        returncode=0,
    )

    assert result.submitted is True
    assert result.state == STATE_ROUTED
