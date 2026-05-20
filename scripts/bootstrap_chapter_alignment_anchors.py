"""Stamp the current predicted-roll fingerprint onto every chapter
that has a curator-side ``chapter_roll_overrides`` entry.

This is a one-time bootstrap step. The fingerprint pairs an override
with the predicted-roll shape it was authored against. The
re-alignment guard (``build_chapter_facts.py``) compares the stamped
fingerprint with the freshly computed one and errors out for any
chapter where they disagree.

Idempotent: re-running the bootstrap with no upstream changes is a
no-op. Re-running it AFTER an intentional re-alignment (i.e. after
the user has reconciled curator state with the new prediction) is
the canonical way to refresh the stamp.

Run after ``scripts/predict_rolls.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from data_paths import DERIVED, MANUAL

ANCHOR_FIELD = "_fingerprint"
OVERRIDES_PATH = MANUAL / "chapter_roll_overrides.json"
FINGERPRINTS_PATH = DERIVED / "chapter_alignment_fingerprints.json"


def _load_current_fingerprints() -> dict[str, str]:
    if not FINGERPRINTS_PATH.exists():
        raise SystemExit(
            f"missing {FINGERPRINTS_PATH.relative_to(MANUAL.parent.parent)}; "
            "run scripts/predict_rolls.py first"
        )
    doc = json.loads(FINGERPRINTS_PATH.read_text())
    return dict(doc.get("chapter_alignment_fingerprints") or {})


def _load_overrides() -> dict:
    if not OVERRIDES_PATH.exists():
        raise SystemExit(
            f"missing {OVERRIDES_PATH.relative_to(MANUAL.parent.parent)}"
        )
    return json.loads(OVERRIDES_PATH.read_text())


def stamp(force: bool = False) -> tuple[int, int, list[str]]:
    """Stamp current fingerprints onto each chapter override entry.

    Returns ``(stamped, skipped, missing)`` — count of overrides
    updated, count already up to date, and a list of chapter_nums
    that have an override but no current predicted-roll fingerprint
    (meaning the chapter has no predicted rolls; the stamp is set to
    "sha256:none").
    """
    current = _load_current_fingerprints()
    doc = _load_overrides()
    overrides = doc.get("chapter_roll_overrides") or {}
    stamped = 0
    skipped = 0
    missing: list[str] = []
    for cn, entry in overrides.items():
        if not isinstance(entry, dict):
            continue
        current_fp = current.get(str(cn))
        target = current_fp if current_fp is not None else "sha256:none"
        if current_fp is None:
            missing.append(str(cn))
        stored = entry.get(ANCHOR_FIELD)
        if stored == target and not force:
            skipped += 1
            continue
        entry[ANCHOR_FIELD] = target
        stamped += 1
    if stamped:
        OVERRIDES_PATH.write_text(json.dumps(doc, indent=2) + "\n")
    return stamped, skipped, missing


def main() -> None:
    stamped, skipped, missing = stamp()
    print(f"stamped {stamped} chapter override(s); {skipped} already up to date")
    if missing:
        print(
            f"  WARNING: {len(missing)} chapter(s) have overrides but no "
            f"predicted rolls (stamped 'sha256:none'): {sorted(missing)[:10]}"
        )


if __name__ == "__main__":
    main()
