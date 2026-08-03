"""Shared helpers for the parser scripts.

Exposes `write_validated_json`, which validates a payload against its
registered JSON schema before writing to disk, and `read_validated_json`,
its read-side counterpart. Validation runs on every parser invocation so
structural drift fails the pipeline rather than silently producing (or
silently accepting) malformed data.

`write_validated_json` writes atomically (tmp-file-then-`os.replace`)
rather than a plain `write_text`. This was added as part of closing the
sixth unvalidated write path to `chapter_roll_overrides.json` (the Forge
Curator TUI's auto-save, previously routed around this module entirely
via its own `_atomic_write_json` helper in
`scripts/forge_curator/persistence.py`). Rather than hand-roll a second
atomic-write implementation in `chapter_roll_overrides_io.py` for just
that one file, the atomicity is added here, at the one place all
schema-validated writers already funnel through -- every derived-artifact
writer in `scripts/*.py` gains the same crash-safety for free, and no
second JSON serializer is introduced anywhere.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
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


def _validate(payload: dict[str, Any], schema: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        details = "\n".join(
            f"  - at {'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:20]
        )
        more = f"\n  ...and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise ValueError(
            f"{schema_name}: {len(errors)} schema violation(s):\n{details}{more}"
        )


def write_validated_json(out_path: Path, payload: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    # Serialize first so tuples become arrays and any other JSON-only
    # coercions happen; validate the serialized form to match what gets
    # written to disk.
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    _validate(json.loads(text), schema, schema_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: a validation failure above never touches disk (raises
    # before this point), and a mid-write crash never leaves a torn file
    # at ``out_path`` -- the tmp file is written in full first, then
    # ``os.replace`` swaps it in with a single filesystem rename.
    tmp_path = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp_path.write_text(text)
    os.replace(tmp_path, out_path)


def read_validated_json(
    path: Path, schema_name: str, *, default: Any = None
) -> Any:
    """Read and schema-validate a JSON document.

    A genuinely missing file returns ``deepcopy(default)`` without any
    validation — there is nothing on disk to validate. An *existing* file
    is always parsed and validated: a JSON syntax error or a schema
    violation raises. Callers must not wrap this call in a broad
    try/except that silently substitutes ``default`` for either failure —
    that reintroduces the exact silent-data-loss bug this helper exists
    to prevent (see scripts/chapter_roll_overrides_io.py).
    """
    if not path.exists():
        return deepcopy(default)
    schema = _load_schema(schema_name)
    payload = json.loads(path.read_text())
    _validate(payload, schema, schema_name)
    return payload
