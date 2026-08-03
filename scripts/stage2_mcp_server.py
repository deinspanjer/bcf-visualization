"""Propose-only MCP server for Stage 2 agent curation.

This module is the **access-control boundary** of the whole phase. The
propose-only guarantee is enforced by what this server exposes, never by
CLI flags: research measured ``claude --permission-mode bypassPermissions``
successfully calling an MCP tool that was *not* in ``--allowed-tools``
(04-RESEARCH.md, Pitfall 2). Flags are defense in depth only.

Three tools, and nothing else (D-30):

===================== ====== =============================================
``submit_stage2_rolls`` submit The only delivery channel.
``get_prose_span``      read   Bounded prose around a stated offset.
``check_quote``         read   Non-authoritative Tier-1/Tier-2 dry run.
===================== ====== =============================================

There is no ``write_*``, no ``route_*``, no ``set_confidence``, and no tool
that accepts or returns a destination. **No Stage 2 module may import the
corpus writer from ``chapter_roll_overrides_io``** — Phase 4 has no corpus
write path at all, and a grep test asserts that absence by searching these
sources for the writer's name, so the name must not appear even in prose.

Transport is a **pre-started warm loopback HTTP server**, not stdio. This
is measured, not stylistic: an official-SDK stdio server lost a startup
race to ``claude -p`` 3 times out of 3 (``--debug`` printed "Connecting MCP
server (tools not available yet)"), and adding an artificial 1.5s delay to
a pure-stdlib server that otherwise worked reproduced the failure —
isolating latency, not the SDK, as the cause. A warm HTTP endpoint
connected reliably (D-31).
"""

from __future__ import annotations

import json
import socket
import threading
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

import mcp.types as types
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from stage2_schema import (
        CHECK_QUOTE_SCHEMA,
        GET_PROSE_SPAN_SCHEMA,
        MAX_CHECK_QUOTE_CALLS,
        MAX_PROSE_SPAN_CALLS,
        MAX_PROSE_SPAN_WORDS,
        SUBMIT_STAGE2_ROLLS_SCHEMA,
    )
except ImportError:  # pragma: no cover - import-path shim, see 03-01 decision
    from scripts.stage2_schema import (  # type: ignore[no-redef]
        CHECK_QUOTE_SCHEMA,
        GET_PROSE_SPAN_SCHEMA,
        MAX_CHECK_QUOTE_CALLS,
        MAX_PROSE_SPAN_CALLS,
        MAX_PROSE_SPAN_WORDS,
        SUBMIT_STAGE2_ROLLS_SCHEMA,
    )


SERVER_NAME = "bcf-stage2"
MCP_CONFIG_SERVER_KEY = "bcf"


class ReadToolCapExceeded(RuntimeError):
    """Raised when a read tool is called past its per-chapter budget.

    The low-level ``Server`` converts a raised exception into an
    ``isError`` tool result, which is the correction signal the model
    sees.
    """


class Stage2Context(Protocol):
    """What the tool handlers delegate to.

    Task 1 supplies :class:`RecordingStage2Context`; Task 2 supplies the
    real pipeline context whose ``submit_rolls`` runs
    ``process_stage2_response``. Keeping this a Protocol is what lets the
    whole verify -> route path be tested with no transport, no subprocess,
    and no MCP.
    """

    def submit_rolls(self, chapter_num: str, rolls: list[dict[str, Any]]) -> str:
        """Handle a submission. Returns a model-facing summary.

        The summary must state *what was accepted*, never *where it went* —
        the model must not learn the destination, or the next turn's
        proposals get steered by it.
        """

    def prose_span(self, chapter_num: str, start_word: int, end_word: int) -> str:
        ...

    def check_quote(self, chapter_num: str, quote_text: str) -> dict[str, Any]:
        ...


@dataclass
class ReadToolBudget:
    """Per-chapter read-tool call budget.

    Caps are inclusive integer comparisons — the 5th ``get_prose_span``
    and the 20th ``check_quote`` for a chapter succeed; the 6th and 21st
    are refused. No floating-point arithmetic anywhere in this path.
    """

    prose_span_calls: dict[str, int] = field(default_factory=dict)
    check_quote_calls: dict[str, int] = field(default_factory=dict)

    def consume_prose_span(self, chapter_num: str) -> None:
        used = self.prose_span_calls.get(chapter_num, 0)
        if used >= MAX_PROSE_SPAN_CALLS:
            raise ReadToolCapExceeded(
                f"get_prose_span budget exhausted for chapter {chapter_num}: "
                f"at most {MAX_PROSE_SPAN_CALLS} spans per chapter. Work with "
                "the candidate paragraphs you already have."
            )
        self.prose_span_calls[chapter_num] = used + 1

    def consume_check_quote(self, chapter_num: str) -> None:
        used = self.check_quote_calls.get(chapter_num, 0)
        if used >= MAX_CHECK_QUOTE_CALLS:
            raise ReadToolCapExceeded(
                f"check_quote budget exhausted for chapter {chapter_num}: "
                f"at most {MAX_CHECK_QUOTE_CALLS} checks per chapter."
            )
        self.check_quote_calls[chapter_num] = used + 1


@dataclass
class RecordingStage2Context:
    """Task-1 stub context: records what arrived, computes nothing.

    Exists so the tracer can prove a submission reached the handler before
    any pipeline logic exists. Task 2 replaces it with the real context.
    """

    submissions: list[dict[str, Any]] = field(default_factory=list)
    prose_span_requests: list[dict[str, Any]] = field(default_factory=list)
    check_quote_requests: list[dict[str, Any]] = field(default_factory=list)
    prose_span_reply: str = "(stub prose span)"

    def submit_rolls(self, chapter_num: str, rolls: list[dict[str, Any]]) -> str:
        self.submissions.append({"chapter_num": chapter_num, "rolls": rolls})
        return (
            f"Received {len(rolls)} roll(s) for chapter {chapter_num}. "
            "Quote locating and verification run separately."
        )

    def prose_span(self, chapter_num: str, start_word: int, end_word: int) -> str:
        self.prose_span_requests.append(
            {
                "chapter_num": chapter_num,
                "start_word": start_word,
                "end_word": end_word,
            }
        )
        return self.prose_span_reply

    def check_quote(self, chapter_num: str, quote_text: str) -> dict[str, Any]:
        self.check_quote_requests.append(
            {"chapter_num": chapter_num, "quote_text": quote_text}
        )
        return {
            "found": False,
            "tier": None,
            "word_position": None,
            "occurrence_count": 0,
        }


def stage2_tools() -> list[types.Tool]:
    """The complete tool surface, with hand-written input schemas."""
    return [
        types.Tool(
            name="submit_stage2_rolls",
            description=(
                "Submit your proposed rolls for a chapter. This is the only "
                "way to deliver results; answering in prose delivers nothing. "
                "Propose quote TEXT and structure only -- word positions and "
                "roll ordinals are derived mechanically from your quotes, so "
                "there is no field to put them in. Partial output is correct "
                "output: name what you could not evidence in unfilled_fields "
                "rather than guessing, and submit a roll with no quotes "
                "rather than inventing one."
            ),
            inputSchema=SUBMIT_STAGE2_ROLLS_SCHEMA,
        ),
        types.Tool(
            name="get_prose_span",
            description=(
                f"Read at most {MAX_PROSE_SPAN_WORDS} CP-earning words of "
                "chapter prose around a stated word offset, for evidence "
                "that falls outside the candidate paragraphs you were "
                f"given. At most {MAX_PROSE_SPAN_CALLS} spans per chapter."
            ),
            inputSchema=GET_PROSE_SPAN_SCHEMA,
        ),
        types.Tool(
            name="check_quote",
            description=(
                "Dry-run a candidate quote against the real chapter prose "
                "before submitting it. Returns {found, tier, word_position, "
                "occurrence_count}. Non-authoritative and records nothing -- "
                "the real verifier re-runs on submission regardless. Use it "
                "to fix a near-miss quote (whitespace drift, a truncated "
                f"clause). At most {MAX_CHECK_QUOTE_CALLS} checks per chapter."
            ),
            inputSchema=CHECK_QUOTE_SCHEMA,
        ),
    ]


def build_stage2_server(
    ctx: Stage2Context, *, budget: ReadToolBudget | None = None
) -> Server:
    """Build the propose-only server around ``ctx``.

    ``validate_input=True`` is passed explicitly rather than relied on as a
    default. It is the reason this dependency was taken on at all: it runs
    ``jsonschema.validate`` against each tool's ``inputSchema`` and returns
    an ``isError`` correction result on failure, which is what restores the
    D-08 no-free-text-parse guarantee at the MCP layer (D-26/D-32).
    """
    server: Server = Server(SERVER_NAME)
    read_budget = budget if budget is not None else ReadToolBudget()

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return stage2_tools()

    @server.call_tool(validate_input=True)
    async def call_tool(name: str, arguments: dict[str, Any]):
        if name == "submit_stage2_rolls":
            summary = ctx.submit_rolls(
                arguments["chapter_num"], arguments["rolls"]
            )
            return [types.TextContent(type="text", text=summary)]

        if name == "get_prose_span":
            chapter_num = arguments["chapter_num"]
            start_word = arguments["start_word"]
            end_word = arguments["end_word"]
            span_words = end_word - start_word
            if span_words > MAX_PROSE_SPAN_WORDS:
                raise ReadToolCapExceeded(
                    f"requested span of {span_words} CP words exceeds the "
                    f"{MAX_PROSE_SPAN_WORDS}-word maximum; narrow the range."
                )
            read_budget.consume_prose_span(chapter_num)
            text = ctx.prose_span(chapter_num, start_word, end_word)
            return [types.TextContent(type="text", text=text)]

        if name == "check_quote":
            chapter_num = arguments["chapter_num"]
            read_budget.consume_check_quote(chapter_num)
            result = ctx.check_quote(chapter_num, arguments["quote_text"])
            return [
                types.TextContent(type="text", text=json.dumps(result, indent=2))
            ]

        raise ValueError(f"unknown tool: {name}")

    return server


# ---------------------------------------------------------------------------
# Warm loopback HTTP transport
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunningStage2Server:
    host: str
    port: int

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"

    def mcp_config(self) -> dict[str, Any]:
        """The ``--mcp-config`` payload naming this server."""
        return {
            "mcpServers": {
                MCP_CONFIG_SERVER_KEY: {"type": "http", "url": self.url}
            }
        }

    def mcp_config_json(self) -> str:
        return json.dumps(self.mcp_config())


def _build_asgi_app(server: Server) -> Starlette:
    session_manager = StreamableHTTPSessionManager(
        app=server, json_response=True, stateless=True
    )

    async def handle_mcp(scope, receive, send):
        await session_manager.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(_app):
        async with session_manager.run():
            yield

    return Starlette(routes=[Mount("/mcp", app=handle_mcp)], lifespan=lifespan)


@contextmanager
def serve_stage2_http(
    server: Server,
    *,
    host: str = "127.0.0.1",
    port: int = 0,
    startup_timeout: float = 30.0,
) -> Iterator[RunningStage2Server]:
    """Serve ``server`` on a warm loopback HTTP endpoint.

    Binds ``127.0.0.1`` only -- **never** ``0.0.0.0`` -- on an ephemeral
    port (bind 0, read back the assignment) so nothing is discoverable at
    a fixed address. Shutdown runs in a ``finally`` on every exit path
    including exception and KeyboardInterrupt: a leaked server is a real
    hazard, because its handler is what routes.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    uvicorn_server: uvicorn.Server | None = None
    thread: threading.Thread | None = None
    try:
        sock.bind((host, port))
        sock.listen(128)
        bound_host, bound_port = sock.getsockname()[:2]

        config = uvicorn.Config(
            _build_asgi_app(server),
            log_level="warning",
            lifespan="on",
            access_log=False,
        )
        uvicorn_server = uvicorn.Server(config)
        # uvicorn installs signal handlers only on the main thread; running
        # it on a worker thread keeps KeyboardInterrupt handling with the
        # caller, where the finally below can act on it.
        uvicorn_server.config.setup_event_loop = lambda: None  # type: ignore[method-assign]
        thread = threading.Thread(
            target=uvicorn_server.run,
            kwargs={"sockets": [sock]},
            name="stage2-mcp-http",
            daemon=True,
        )
        thread.start()

        deadline = threading.Event()
        waited = 0.0
        while not uvicorn_server.started:
            if not thread.is_alive():
                raise RuntimeError("Stage 2 MCP server thread died during startup")
            if waited >= startup_timeout:
                raise TimeoutError(
                    f"Stage 2 MCP server did not start within {startup_timeout}s"
                )
            deadline.wait(0.05)
            waited += 0.05

        yield RunningStage2Server(host=bound_host, port=bound_port)
    finally:
        if uvicorn_server is not None:
            uvicorn_server.should_exit = True
        if thread is not None:
            thread.join(timeout=10.0)
        # uvicorn closes the sockets it was handed, but a startup failure
        # can leave it unclosed; closing twice is harmless.
        try:
            sock.close()
        except OSError:  # pragma: no cover - defensive
            pass
