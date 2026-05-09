"""FastAPI scaffold tests using `TestClient`.

Verifies the Phase 0 contract: server boots without checkpoints, the
metadata endpoints work, and the inference endpoints return the
documented 503 body shape until the runners are real.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from nlp.serve import app
from nlp.schema import SCHEMA_VERSION


def _client() -> TestClient:
    # `with TestClient` triggers lifespan startup, which sets started_at
    # and git_commit. Tests below that need /version use the context
    # manager form.
    return TestClient(app)


def test_health_returns_loaded_false_when_checkpoints_absent():
    with _client() as c:
        r = c.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["models"]["span"]["loaded"] is False
    assert body["models"]["section"]["loaded"] is False
    assert body["models"]["embed"]["loaded"] is False
    assert "available" in body["gpu"]


def test_version_returns_documented_keys():
    with _client() as c:
        r = c.get("/version")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("service_version", "git_commit", "schema_version", "started_at", "models"):
        assert key in body, key
    assert body["schema_version"] == SCHEMA_VERSION
    assert "span" in body["models"]
    assert "section" in body["models"]


def test_extract_returns_503_with_documented_body():
    with _client() as c:
        r = c.post(
            "/extract",
            json={
                "passages": [{"passage_id": "smoke", "text": "Joe gained Perfect Pitch."}]
            },
        )
    assert r.status_code == 503, r.text
    assert r.json() == {"error": "span_model_not_loaded"}


def test_classify_section_returns_503_with_documented_body():
    with _client() as c:
        r = c.post(
            "/classify_section",
            json={
                "sections": [
                    {
                        "chapter_num": "1",
                        "section_index": 0,
                        "header": "1.1",
                        "text": "It was the morning of April 14th.",
                    }
                ]
            },
        )
    assert r.status_code == 503, r.text
    assert r.json() == {"error": "section_model_not_loaded"}


def test_extract_validates_input():
    with _client() as c:
        r = c.post("/extract", json={"passages": []})
    # Empty passages list is rejected by pydantic before reaching the
    # runner; this is a 422, not a 503.
    assert r.status_code == 422, r.text
