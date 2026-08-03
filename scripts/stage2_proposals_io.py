"""Validated, atomic read/write for the Stage 2 proposals sidecar.

**This file is not the trusted corpus and must never be loaded as one.**
It lives under ``data/derived/`` because it is machine-produced and fully
regenerable from a re-run, while ``data/manual/`` is Dre's hand-authored
territory and the corpus's home. That physical separation is what makes
"never loaded as the corpus" structural rather than a convention people
have to remember.

Its roll objects mirror the corpus roll shape exactly (D-15) so the Phase
5 review flow needs no translation layer. That costs nothing: the corpus
schema is deliberately permissive about roll contents.

Serialization goes through ``_common.write_validated_json`` — the same
call the corpus writer uses — so schema validation and crash-safe atomic
replacement come for free and no second JSON serializer is introduced.
Note this writes ``ensure_ascii=False``; do not reproduce
``realign_chapters.py``'s ``ensure_ascii=True`` unicode churn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from _common import read_validated_json, write_validated_json
    from data_paths import DERIVED
except ImportError:  # pragma: no cover - import-path shim
    from scripts._common import (  # type: ignore[no-redef]
        read_validated_json,
        write_validated_json,
    )
    from scripts.data_paths import DERIVED  # type: ignore[no-redef]


SCHEMA_NAME = "agent_proposals"
SCHEMA_VERSION = 1

DEFAULT_PROPOSALS_PATH = DERIVED / "agent_proposals.json"


def empty_proposals_doc() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "agent_proposals": {}}


def load_agent_proposals_doc(path: Path | None = None) -> dict[str, Any]:
    """Read the proposals sidecar, or an empty document if absent.

    Deliberately does NOT swallow a schema violation or a JSON syntax
    error into the empty default — that is the silent-data-loss bug
    ``chapter_roll_overrides_io`` was fixed for. A missing file returns
    empty; a malformed existing file raises.
    """
    target = path or DEFAULT_PROPOSALS_PATH
    return read_validated_json(target, SCHEMA_NAME, default=empty_proposals_doc())


def write_agent_proposals_doc(
    doc: dict[str, Any], path: Path | None = None
) -> None:
    """Validate and atomically write the proposals sidecar."""
    target = path or DEFAULT_PROPOSALS_PATH
    payload = dict(doc)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    write_validated_json(target, payload, SCHEMA_NAME)


def upsert_chapter_proposal(
    chapter_entry: dict[str, Any],
    chapter_num: str,
    path: Path | None = None,
) -> dict[str, Any]:
    """Insert or replace one chapter's proposal entry and persist.

    Replacing a *proposal* is safe and intended — proposals are
    regenerable and carry no human edits. Nothing in this module can
    touch the hand-curated corpus; there is no code path from here to it.
    """
    target = path or DEFAULT_PROPOSALS_PATH
    doc = load_agent_proposals_doc(target)
    doc.setdefault("agent_proposals", {})[str(chapter_num)] = chapter_entry
    write_agent_proposals_doc(doc, target)
    return doc
