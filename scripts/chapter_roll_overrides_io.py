"""The ONE place that reads ``data/manual/chapter_roll_overrides.json``.

D-11 (Phase 3 provenance schema): pattern mapping found this file was read
via four independent bare ``json.loads`` call sites with no schema
enforcement at all — ``scripts/multi_grab.py:load_overrides``,
``scripts/build_chapter_facts.py:_load_chapter_roll_overrides`` /
``_load_association_review_marker``, the
``scripts/forge_curator/data_loader.py`` ``chapter_roll_overrides``
property, and ``scripts/forge_curator/persistence.py``'s
``CurationPersistence.__init__``. That meant D-01's "an absent
``curated_by`` is a validation error, never a silent default" had no
single hook to attach to, and adding the check to four loaders
separately would itself violate the project's no-parallel-implementations
rule.

This module consolidates all four into ``load_chapter_roll_overrides_doc``,
which validates the document against
``data/derived/_schemas/chapter_roll_overrides.schema.json`` on every read.
``curated_by`` is schema-required (enum ``["human", "agent"]``) on every
chapter entry — an existing entry missing it, or an existing file that
fails to parse as JSON, raises ``ValueError``/``json.JSONDecodeError``.

IMPORTANT: callers must NOT wrap this call in a broad try/except that
substitutes a default on any exception. A genuinely *missing* file is the
only case that defaults cleanly (handled internally, before any
validation runs). A file that exists but is malformed or missing
``curated_by`` must raise and propagate — silently swallowing that error
and returning an empty document is exactly the bug this module fixes in
``forge_curator/persistence.py``: an empty in-memory document, if later
auto-saved, would overwrite the real 118-chapter hand-curated corpus with
nothing.
"""

from __future__ import annotations

from pathlib import Path

try:
    from _common import read_validated_json, write_validated_json
    from data_paths import MANUAL
except ImportError:  # pragma: no cover - import-context fallback
    # This module is imported two ways: bare (``import
    # chapter_roll_overrides_io``) from top-level scripts run with
    # ``scripts/`` on sys.path (e.g. via PYTHONPATH=scripts), and
    # package-qualified (``from scripts.chapter_roll_overrides_io import
    # ...``) from the forge_curator TUI package, which runs as ``python -m
    # scripts.forge_curator`` with only the repo root on sys.path. Fall
    # back to the package-qualified sibling imports for the latter case.
    from scripts._common import read_validated_json, write_validated_json
    from scripts.data_paths import MANUAL

CHAPTER_ROLL_OVERRIDES_PATH = MANUAL / "chapter_roll_overrides.json"

DEFAULT_DOC = {"chapter_roll_overrides": {}}


def load_chapter_roll_overrides_doc(
    path: Path | None = None, *, default: dict | None = None
) -> dict:
    """Load and schema-validate the chapter-roll-overrides document.

    ``path`` defaults to the real ``data/manual/chapter_roll_overrides.json``
    (via ``data_paths.MANUAL``, which honours ``BCF_DATA_DIR`` in tests).
    A missing file returns ``default`` (or ``{"chapter_roll_overrides": {}}``
    if ``default`` is not given) without validation. An existing file is
    always validated; a JSON syntax error or a schema violation (most
    notably a chapter entry missing ``curated_by``) raises.
    """
    return read_validated_json(
        path or CHAPTER_ROLL_OVERRIDES_PATH,
        "chapter_roll_overrides",
        default=default if default is not None else DEFAULT_DOC,
    )


def write_chapter_roll_overrides_doc(doc: dict, path: Path | None = None) -> None:
    """Schema-validate and write the chapter-roll-overrides document.

    This is the ONLY sanctioned way to write
    ``data/manual/chapter_roll_overrides.json``. It mirrors
    ``load_chapter_roll_overrides_doc``'s validation gate on the write
    side: the document is validated against the same
    ``chapter_roll_overrides`` schema (``curated_by`` required on every
    chapter entry) BEFORE anything touches disk, and it is serialized
    with ``indent=2, ensure_ascii=False`` plus a trailing newline —
    matching the file's established on-disk convention exactly (a
    round-trip through this writer produces a zero-diff on the real
    corpus). Delegates to ``_common.write_validated_json`` rather than
    hand-rolling a second JSON serializer.

    A prior bug class this closes: two call sites
    (``bootstrap_chapter_alignment_anchors.py``,
    ``realign_chapters.py``) wrote this file via bare
    ``json.dumps(doc, indent=2)`` with no ``ensure_ascii=False`` and no
    schema validation — the missing ``ensure_ascii=False`` caused every
    literal unicode character (en-dash, ellipsis, curly quotes) across
    the whole 467KB hand-curated file to be escaped into ``\\uXXXX``
    sequences on every re-stamp, producing large spurious diffs in
    trusted curation data.
    """
    write_validated_json(
        path or CHAPTER_ROLL_OVERRIDES_PATH,
        doc,
        "chapter_roll_overrides",
    )
