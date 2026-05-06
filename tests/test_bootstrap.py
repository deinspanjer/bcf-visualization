"""Tests for nlp.bootstrap — the llama.cpp proposal lane.

Uses httpx.MockTransport so no real network calls are made.
Requires only stdlib + httpx + pydantic.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import httpx
import pytest

from nlp.bootstrap import propose
from nlp.proposals import Proposal, ProposedSpan

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_PASSAGE = (
    "Joe felt the wheel spin. It slowed and clicked: he had gained Perfect Pitch. "
    "The Toolkit constellation unfolded around him."
)

_PASSAGE_ID = "ch1_p0"


def _make_llm_response(spans: list[dict], model: str = "test-model") -> dict:
    """Build a minimal /v1/chat/completions response dict."""
    content = json.dumps({"spans": spans})
    return {
        "id": "cmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


def _make_transport(responses: list[dict]) -> httpx.MockTransport:
    """Return a MockTransport that serves responses in order (cycling last)."""
    calls = [0]
    response_bytes = [json.dumps(r).encode() for r in responses]

    def handler(request: httpx.Request) -> httpx.Response:
        idx = min(calls[0], len(response_bytes) - 1)
        calls[0] += 1
        return httpx.Response(
            200,
            content=response_bytes[idx],
            headers={"content-type": "application/json"},
        )

    return httpx.MockTransport(handler)


def _make_error_transport(status_code: int) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=b'{"error":"bad"}')

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# Payload shape tests
# ---------------------------------------------------------------------------


def test_propose_sends_chat_completions(tmp_path: Path) -> None:
    """propose() must POST to /v1/chat/completions with correct fields."""
    captured: list[httpx.Request] = []

    valid_spans = [
        {"layer": "A", "start": 44, "end": 62, "label": "ACQUISITION", "confidence": 0.9}
    ]
    response_body = _make_llm_response(valid_spans)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(response_body).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    proposal = propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        model="test-model",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    assert len(captured) == 1
    req = captured[0]

    # URL
    assert str(req.url) == "http://fake:11434/v1/chat/completions"

    # Body
    body = json.loads(req.content)
    assert body["temperature"] == 0.1
    assert body["top_p"] == 0.9
    assert body["max_tokens"] == 2048
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "test-model"

    # Messages
    messages = body["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_system_message_contains_label_quickref(tmp_path: Path) -> None:
    """The system message must have the label quickref substituted in."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        body = _make_llm_response([])
        return httpx.Response(
            200,
            content=json.dumps(body).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    body = json.loads(captured[0].content)
    system_content = body["messages"][0]["content"]

    # The marker must be replaced, not left in
    assert "<INSERT label quickref here at proposal time>" not in system_content
    # Key label names should appear
    assert "ROLL_HIT" in system_content
    assert "PRESENCE_ACTION" in system_content


def test_user_message_contains_passage(tmp_path: Path) -> None:
    """The user message must include the passage text."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(_make_llm_response([])).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    body = json.loads(captured[0].content)
    user_content = body["messages"][1]["content"]
    assert _PASSAGE in user_content


# ---------------------------------------------------------------------------
# Happy-path span parsing
# ---------------------------------------------------------------------------


def test_propose_returns_valid_spans(tmp_path: Path) -> None:
    """Correctly-offset spans are returned in the Proposal."""
    # Find offsets for "gained Perfect Pitch" in _PASSAGE
    target = "gained Perfect Pitch"
    start = _PASSAGE.index(target)
    end = start + len(target)

    spans = [
        {"layer": "A", "start": start, "end": end, "label": "ACQUISITION", "confidence": 0.85}
    ]
    client = httpx.Client(
        transport=_make_transport([_make_llm_response(spans)])
    )
    proposal = propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    assert isinstance(proposal, Proposal)
    assert len(proposal.spans) == 1
    sp = proposal.spans[0]
    assert isinstance(sp, ProposedSpan)
    assert sp.label == "ACQUISITION"
    assert sp.layer == "A"
    assert sp.start == start
    assert sp.end == end
    assert abs(sp.confidence - 0.85) < 1e-6
    assert proposal.mean_confidence is not None


# ---------------------------------------------------------------------------
# Retry on invalid JSON
# ---------------------------------------------------------------------------


def test_retry_on_invalid_json(tmp_path: Path) -> None:
    """When the model returns non-JSON, propose() retries up to 2 times."""
    call_count = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        body = request.read()
        payload = json.loads(body)
        # Count how many messages have been exchanged
        n_messages = len(payload["messages"])
        if n_messages <= 2:
            # First call: return broken JSON
            bad_content = "not json at all %%"
        else:
            # Subsequent: return valid empty spans
            bad_content = json.dumps({"spans": []})
        resp_body = {
            "id": "cmpl-test",
            "model": "test-model",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": bad_content}, "finish_reason": "stop"}
            ],
        }
        return httpx.Response(
            200,
            content=json.dumps(resp_body).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    proposal = propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    # Should have retried at least once
    assert call_count[0] >= 2
    assert isinstance(proposal, Proposal)
    # After retry recovered, spans list should be valid (empty is fine)
    assert isinstance(proposal.spans, list)


def test_exhausted_retries_returns_empty_proposal(tmp_path: Path) -> None:
    """If all retries fail to parse JSON, return Proposal with empty spans."""
    def handler(request: httpx.Request) -> httpx.Response:
        resp_body = {
            "id": "cmpl-test",
            "model": "test-model",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "NOT JSON"}, "finish_reason": "stop"}
            ],
        }
        return httpx.Response(
            200,
            content=json.dumps(resp_body).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        proposal = propose(
            _PASSAGE,
            passage_id=_PASSAGE_ID,
            llama_url="http://fake:11434",
            persist_raw_dir=tmp_path / "raw",
            _client=client,
        )

    assert proposal.spans == []
    assert len(w) >= 1


# ---------------------------------------------------------------------------
# Span-text validation
# ---------------------------------------------------------------------------


def test_span_text_mismatch_triggers_retry(tmp_path: Path) -> None:
    """A span whose declared text doesn't match passage[start:end] triggers retry."""
    call_count = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        payload = json.loads(request.read())
        n_messages = len(payload["messages"])
        if n_messages <= 2:
            # First call: span with wrong declared text
            bad_spans = [
                {
                    "layer": "A",
                    "start": 0,
                    "end": 3,
                    "label": "ACQUISITION",
                    "text": "WRONG_TEXT",  # passage[0:3] = "Joe"
                    "confidence": 0.9,
                }
            ]
            content = json.dumps({"spans": bad_spans})
        else:
            # Retry: return valid empty spans
            content = json.dumps({"spans": []})
        resp_body = {
            "id": "cmpl-test",
            "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        }
        return httpx.Response(
            200,
            content=json.dumps(resp_body).encode(),
            headers={"content-type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    proposal = propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        _client=client,
    )

    assert call_count[0] >= 2


def test_span_offset_out_of_range_dropped(tmp_path: Path) -> None:
    """Spans with start/end beyond text length are dropped without retry."""
    n = len(_PASSAGE)
    bad_spans = [
        {"layer": "A", "start": n - 1, "end": n + 100, "label": "ACQUISITION", "confidence": 0.5}
    ]
    client = httpx.Client(
        transport=_make_transport([_make_llm_response(bad_spans)])
    )
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        proposal = propose(
            _PASSAGE,
            passage_id=_PASSAGE_ID,
            llama_url="http://fake:11434",
            persist_raw_dir=tmp_path / "raw",
            _client=client,
        )
    # Out-of-range span should be dropped
    assert all(
        s.end <= n for s in proposal.spans
    )


# ---------------------------------------------------------------------------
# Raw response persistence
# ---------------------------------------------------------------------------


def test_raw_response_persisted(tmp_path: Path) -> None:
    """Raw LLM output is written to persist_raw_dir/<passage_id>.json."""
    raw_dir = tmp_path / "raw"
    spans = [
        {"layer": "B", "start": 0, "end": 3, "label": "JOE_NAME", "confidence": 0.7}
    ]
    client = httpx.Client(
        transport=_make_transport([_make_llm_response(spans, model="mymodel")])
    )
    propose(
        _PASSAGE,
        passage_id=_PASSAGE_ID,
        llama_url="http://fake:11434",
        persist_raw_dir=raw_dir,
        _client=client,
    )

    raw_file = raw_dir / f"{_PASSAGE_ID}.json"
    assert raw_file.exists(), f"Expected raw file at {raw_file}"
    saved = json.loads(raw_file.read_text())
    assert "choices" in saved
    assert saved["model"] == "mymodel"


def test_raw_response_persisted_on_retry(tmp_path: Path) -> None:
    """Raw output is still persisted even when retry path is taken."""
    raw_dir = tmp_path / "raw"
    call_count = [0]

    def handler(request: httpx.Request) -> httpx.Response:
        call_count[0] += 1
        payload = json.loads(request.read())
        n_messages = len(payload["messages"])
        if n_messages <= 2:
            content = "NOT JSON"
        else:
            content = json.dumps({"spans": []})
        resp_body = {
            "id": "cmpl",
            "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        }
        return httpx.Response(200, content=json.dumps(resp_body).encode(),
                              headers={"content-type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id="ch99_p0",
        llama_url="http://fake:11434",
        persist_raw_dir=raw_dir,
        _client=client,
    )

    # Either the first attempt's raw file or a retry file must exist
    files = list(raw_dir.glob("ch99_p0*.json"))
    assert len(files) >= 1


# ---------------------------------------------------------------------------
# roll_context threading into the user prompt
# ---------------------------------------------------------------------------


def test_roll_context_hit_appears_in_user_prompt(tmp_path: Path) -> None:
    """When roll_context with a curator HIT is passed to propose(), the user
    prompt must contain the perk name, 'HIT for', and the anchor string."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(_make_llm_response([])).encode(),
            headers={"content-type": "application/json"},
        )

    roll_ctx = {
        "roll_number": 7,
        "chapter_num": "3",
        "section_index": 1,
        "predicted_char_offset": 12345,
        "anchor_string": "the wheel clicked and stopped",
        "banked_at_roll": 150,
        "banked_at_roll_source": "curator",
        "curator_outcome": "HIT",
        "curator_perk_name": "Resonance Forge",
        "curator_constellation": "Harmonics",
        "curator_cost": 150,
        "curator_free_associated_perks": ["Tuning Fork"],
        "chapter_acquired_perks_in_order": [
            {"name": "Resonance Forge", "constellation": "Harmonics", "cost": 150, "free": False}
        ],
        "outstanding_perks_with_cost_gt_banked": [
            {"name": "Grand Organ", "cost": 500, "constellation": "Harmonics"}
        ],
        "constellations_known_by_joe": ["Harmonics"],
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id="ch3_p0",
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        roll_context=roll_ctx,
        _client=client,
    )

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    user_content = body["messages"][1]["content"]

    # Passage text must still be present
    assert _PASSAGE in user_content

    # HIT marker, perk name, and anchor must appear
    assert "HIT for" in user_content, "Expected 'HIT for' in user prompt"
    assert "Resonance Forge" in user_content, "Expected perk name in user prompt"
    assert "the wheel clicked and stopped" in user_content, "Expected anchor string in user prompt"

    # Constellation and cost should appear
    assert "Harmonics" in user_content
    assert "150" in user_content


# ---------------------------------------------------------------------------
# chapter_attribution_disagreement disclaimer
# ---------------------------------------------------------------------------


def test_chapter_attribution_disclaimer_appears_when_flag_true(tmp_path: Path) -> None:
    """When roll_context has chapter_attribution_disagreement=True, the user
    prompt must contain the disclaimer mentioning both chapter numbers."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(_make_llm_response([])).encode(),
            headers={"content-type": "application/json"},
        )

    roll_ctx = {
        "roll_number": 107,
        "chapter_num": "22",           # simulator's chapter
        "curator_chapter_num": "23",   # curator's chapter
        "chapter_attribution_disagreement": True,
        "section_index": 0,
        "predicted_char_offset": 50000,
        "anchor_string": "the wheel clicked",
        "banked_at_roll": 100,
        "banked_at_roll_source": "curator",
        "curator_outcome": "HIT",
        "curator_perk_name": "Reliable Invention",
        "curator_constellation": "Crafting",
        "curator_cost": 100,
        "curator_free_associated_perks": None,
        "chapter_acquired_perks_in_order": [
            {"name": "Don't Need A Team", "constellation": "Crafting", "cost": 100, "free": False},
            {"name": "Most Holy Order of the Socket Wrench", "constellation": "Crafting", "cost": 200, "free": False},
        ],
        "outstanding_perks_with_cost_gt_banked": [],
        "constellations_known_by_joe": ["Crafting"],
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id="ch22_p0",
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        roll_context=roll_ctx,
        _client=client,
    )

    body = json.loads(captured[0].content)
    user_content = body["messages"][1]["content"]

    # Disclaimer must be present
    assert "Chapter attribution disagreement" in user_content, (
        "Expected disclaimer in user prompt when chapter_attribution_disagreement=True"
    )
    # Both chapter numbers must appear in the disclaimer
    assert "chapter 23" in user_content, "Expected curator chapter number in disclaimer"
    assert "chapter 22" in user_content, "Expected simulator chapter number in disclaimer"

    # Curator perk name and outcome must still appear
    assert "Reliable Invention" in user_content
    assert "HIT for" in user_content


def test_chapter_attribution_disclaimer_absent_when_flag_false(tmp_path: Path) -> None:
    """When chapter_attribution_disagreement is False (or absent), no disclaimer
    should appear in the user prompt."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(_make_llm_response([])).encode(),
            headers={"content-type": "application/json"},
        )

    roll_ctx = {
        "roll_number": 5,
        "chapter_num": "2",
        "curator_chapter_num": "2",
        "chapter_attribution_disagreement": False,
        "section_index": 0,
        "predicted_char_offset": 1000,
        "anchor_string": "the wheel stopped",
        "banked_at_roll": 200,
        "banked_at_roll_source": "curator",
        "curator_outcome": "HIT",
        "curator_perk_name": "Some Perk",
        "curator_constellation": "Toolkits",
        "curator_cost": 200,
        "curator_free_associated_perks": None,
        "chapter_acquired_perks_in_order": [
            {"name": "Some Perk", "constellation": "Toolkits", "cost": 200, "free": False}
        ],
        "outstanding_perks_with_cost_gt_banked": [],
        "constellations_known_by_joe": [],
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id="ch2_p0",
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        roll_context=roll_ctx,
        _client=client,
    )

    body = json.loads(captured[0].content)
    user_content = body["messages"][1]["content"]

    assert "Chapter attribution disagreement" not in user_content, (
        "Disclaimer must NOT appear when chapter_attribution_disagreement=False"
    )


def test_chapter_attribution_disclaimer_absent_when_key_missing(tmp_path: Path) -> None:
    """When roll_context lacks the chapter_attribution_disagreement key entirely
    (old shape), no disclaimer should appear — backwards compatible."""
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=json.dumps(_make_llm_response([])).encode(),
            headers={"content-type": "application/json"},
        )

    # Old-shape roll_context without the new keys
    roll_ctx = {
        "roll_number": 3,
        "chapter_num": "1",
        "section_index": 0,
        "predicted_char_offset": 500,
        "anchor_string": "some anchor",
        "banked_at_roll": 100,
        "banked_at_roll_source": "curator",
        "curator_outcome": "HIT",
        "curator_perk_name": "Old Perk",
        "curator_constellation": "Toolkits",
        "curator_cost": 100,
        "curator_free_associated_perks": None,
        "chapter_acquired_perks_in_order": [],
        "outstanding_perks_with_cost_gt_banked": [],
        "constellations_known_by_joe": [],
    }

    client = httpx.Client(transport=httpx.MockTransport(handler))
    propose(
        _PASSAGE,
        passage_id="ch1_p0_old",
        llama_url="http://fake:11434",
        persist_raw_dir=tmp_path / "raw",
        roll_context=roll_ctx,
        _client=client,
    )

    body = json.loads(captured[0].content)
    user_content = body["messages"][1]["content"]

    assert "Chapter attribution disagreement" not in user_content, (
        "Disclaimer must NOT appear when chapter_attribution_disagreement key is absent"
    )
