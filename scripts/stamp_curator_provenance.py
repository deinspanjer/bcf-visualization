"""Stamp ``curated_by: "human"`` onto every existing chapter-roll-override
entry.

This is a one-time bulk edit (D-01/D-12): all 118 chapter entries
hand-curated before this phase get the field so the schema gate in
``scripts/chapter_roll_overrides_io.py`` can make ``curated_by`` genuinely
required going forward. Mirrors
``scripts/bootstrap_chapter_alignment_anchors.py``'s idempotent
one-time-stamp shape: re-running this script after everything is already
stamped is a no-op.

Only ``doc["chapter_roll_overrides"]`` entries are iterated —
``doc["association_review"]`` is a separate top-level key (baseline
fingerprint / reviewed-through marker), never a chapter entry, and must
never be touched by this script.

Run once against the real file: ``.venv/bin/python
scripts/stamp_curator_provenance.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from chapter_roll_overrides_io import write_chapter_roll_overrides_doc
from data_paths import MANUAL

OVERRIDES_PATH = MANUAL / "chapter_roll_overrides.json"


def stamp(path: Path | None = None) -> tuple[int, int]:
    """Stamp ``curated_by: "human"`` onto every chapter entry lacking it.

    Returns ``(newly_stamped, already_had)``. Writes back through
    ``chapter_roll_overrides_io.write_chapter_roll_overrides_doc`` — the
    one sanctioned writer for this file (gap-closure follow-up, CINF-01)
    — rather than calling ``_common.write_validated_json`` directly; this
    both persists the stamp and proves the file now validates against the
    schema.
    """
    p = path or OVERRIDES_PATH
    doc = json.loads(p.read_text())
    entries = doc.get("chapter_roll_overrides") or {}
    newly_stamped = 0
    already_had = 0
    for entry in entries.values():
        if not isinstance(entry, dict):
            continue
        if "curated_by" in entry:
            already_had += 1
            continue
        entry["curated_by"] = "human"
        newly_stamped += 1
    write_chapter_roll_overrides_doc(doc, p)
    return newly_stamped, already_had


def main() -> None:
    newly_stamped, already_had = stamp()
    print(
        f"stamped {newly_stamped} chapter override(s) with curated_by=human; "
        f"{already_had} already had it"
    )


if __name__ == "__main__":
    main()
