"""Shared helpers for the parser scripts.

Currently exposes `write_validated_json`, which validates a payload
against its registered JSON schema before writing to disk. Validation
runs on every parser invocation so structural drift fails the pipeline
rather than silently producing malformed data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "data" / "derived" / "_schemas"


def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    schema = json.loads(path.read_text())
    # All schema refs in this project are local fragments. Keeping the
    # repository-relative $id here makes older jsonschema releases try to
    # resolve those fragments as external URLs in CI.
    schema.pop("$id", None)
    return schema


def write_validated_json(out_path: Path, payload: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    # Serialize first so tuples become arrays and any other JSON-only
    # coercions happen; validate the serialized form to match what gets
    # written to disk.
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(json.loads(text)), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(
            f"  - at {'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:20]
        )
        more = f"\n  ...and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise ValueError(
            f"{schema_name}: {len(errors)} schema violation(s):\n{details}{more}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
