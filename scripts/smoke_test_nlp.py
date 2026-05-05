#!/usr/bin/env python3
"""Smoke-test the NLP service and llama.cpp endpoints.

Runnable from either the iMac or the Windows GPU box. Prints a PASS or
FAIL line per check and exits 0 only if every required check passes.

Examples
--------
    python3 scripts/smoke_test_nlp.py \
        --nlp-url http://192.168.1.20:8000 \
        --llama-url http://192.168.1.20:11434

Env vars `BCF_NLP_URL` and `BCF_LLAMACPP_URL` are honored as defaults.

Required dependency: `httpx` (already in `requirements.txt`).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("FAIL: httpx is not installed. Run `pip install -r requirements.txt`.")
    sys.exit(2)


# --- pretty print helpers -------------------------------------------------


def _pass(name: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"PASS {name}{suffix}")


def _fail(name: str, detail: str, hint: Optional[str] = None) -> None:
    print(f"FAIL {name} - {detail}")
    if hint:
        print(f"     hint: {hint}")


# --- checks ---------------------------------------------------------------


def check_health(client: httpx.Client, base: str) -> bool:
    name = "GET /health"
    try:
        r = client.get(f"{base}/health")
    except httpx.RequestError as exc:
        _fail(
            name,
            f"could not connect: {exc}",
            "is uvicorn running? `uv run uvicorn nlp.serve:app --host 0.0.0.0 --port 8000`",
        )
        return False
    if r.status_code != 200:
        _fail(name, f"HTTP {r.status_code}: {r.text[:200]}")
        return False
    body = r.json()
    if body.get("status") != "ok":
        _fail(name, f"unexpected body: {body}")
        return False
    span_loaded = body.get("models", {}).get("span", {}).get("loaded")
    section_loaded = body.get("models", {}).get("section", {}).get("loaded")
    _pass(
        name,
        f"status=ok span.loaded={span_loaded} section.loaded={section_loaded}",
    )
    return True


def check_version(client: httpx.Client, base: str) -> bool:
    name = "GET /version"
    try:
        r = client.get(f"{base}/version")
    except httpx.RequestError as exc:
        _fail(name, f"could not connect: {exc}")
        return False
    if r.status_code != 200:
        _fail(name, f"HTTP {r.status_code}: {r.text[:200]}")
        return False
    body = r.json()
    expected_keys = {
        "service_version",
        "git_commit",
        "schema_version",
        "started_at",
        "models",
    }
    missing = expected_keys - body.keys()
    if missing:
        _fail(name, f"missing keys: {sorted(missing)}")
        return False
    _pass(
        name,
        f"service={body['service_version']} commit={body['git_commit'][:8]} "
        f"schema={body['schema_version']}",
    )
    return True


def check_extract_503(client: httpx.Client, base: str) -> bool:
    """Until checkpoints are trained, /extract should 503 with the
    documented error body. That's the success signal here."""
    name = "POST /extract (expect 503 span_model_not_loaded)"
    body = {
        "passages": [{"passage_id": "smoke", "text": "Joe gained Perfect Pitch."}]
    }
    try:
        r = client.post(f"{base}/extract", json=body)
    except httpx.RequestError as exc:
        _fail(name, f"could not connect: {exc}")
        return False
    if r.status_code == 200:
        _pass(name, "model already loaded — returning 200 with results")
        return True
    if r.status_code != 503:
        _fail(name, f"unexpected HTTP {r.status_code}: {r.text[:200]}")
        return False
    try:
        err = r.json().get("error")
    except ValueError:
        _fail(name, f"503 with non-JSON body: {r.text[:200]}")
        return False
    if err != "span_model_not_loaded":
        _fail(name, f"503 with unexpected body: {r.text[:200]}")
        return False
    _pass(name, "503 span_model_not_loaded (route wired, checkpoint absent)")
    return True


def check_llama_models(client: httpx.Client, base: str) -> bool:
    name = "GET {llama}/v1/models"
    try:
        r = client.get(f"{base}/v1/models")
    except httpx.RequestError as exc:
        _fail(
            name,
            f"could not connect: {exc}",
            "is `llama-server` running on the GPU box? defaults to :11434",
        )
        return False
    if r.status_code != 200:
        _fail(name, f"HTTP {r.status_code}: {r.text[:200]}")
        return False
    try:
        body = r.json()
    except ValueError:
        _fail(name, f"non-JSON response: {r.text[:200]}")
        return False
    data = body.get("data") or []
    ids = [m.get("id", "?") for m in data] if isinstance(data, list) else []
    _pass(name, f"models={ids}")
    return True


# --- main -----------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--nlp-url",
        default=os.environ.get("BCF_NLP_URL", "http://localhost:8000"),
        help="FastAPI base URL (default: $BCF_NLP_URL or http://localhost:8000)",
    )
    ap.add_argument(
        "--llama-url",
        default=os.environ.get("BCF_LLAMACPP_URL", "http://localhost:11434"),
        help="llama.cpp base URL (default: $BCF_LLAMACPP_URL or http://localhost:11434)",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout per request in seconds (default: 10)",
    )
    ap.add_argument(
        "--skip-llama",
        action="store_true",
        help="Skip the llama.cpp /v1/models check (e.g. running before llama-server is up)",
    )
    args = ap.parse_args()

    nlp = args.nlp_url.rstrip("/")
    llama = args.llama_url.rstrip("/")
    print(f"NLP URL:   {nlp}")
    print(f"llama URL: {llama}")
    print()

    results: list[bool] = []
    with httpx.Client(timeout=args.timeout) as client:
        results.append(check_health(client, nlp))
        results.append(check_version(client, nlp))
        results.append(check_extract_503(client, nlp))
        if args.skip_llama:
            print("SKIP llama.cpp /v1/models (--skip-llama)")
        else:
            results.append(check_llama_models(client, llama))

    print()
    if all(results):
        print("All checks passed.")
        return 0
    print("One or more checks failed. Common causes:")
    print("  - Windows Defender Firewall blocking inbound 8000 / 11434")
    print("  - uvicorn bound to 127.0.0.1 instead of 0.0.0.0")
    print("  - Wrong --nlp-url / --llama-url (or stale env var)")
    print("  - llama-server not started yet (warm-up takes a few seconds)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
