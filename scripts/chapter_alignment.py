"""Re-alignment guard: detect when curator-anchored data references a
predicted-roll shape that has shifted upstream.

Each chapter in ``data/manual/chapter_roll_overrides.json`` carries a
``_fingerprint`` (sha256 of the canonical predicted-roll sequence at
the time the override was authored — see
``scripts/predict_rolls.py::chapter_alignment_fingerprint``). On every
build, the guard recomputes the current fingerprint and errors out
for any chapter where the stamped fingerprint disagrees, with
instructions to re-align curator state via the curator TUI.

Run modes:
- Programmatic: ``check()`` returns a list of mismatches (used by
  ``build_chapter_facts.py`` at startup).
- CLI: ``python scripts/chapter_alignment.py check`` exits non-zero
  on mismatch with a human-readable summary.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from data_paths import DERIVED, MANUAL

ANCHOR_FIELD = "_fingerprint"
OVERRIDES_PATH = MANUAL / "chapter_roll_overrides.json"
FINGERPRINTS_PATH = DERIVED / "chapter_alignment_fingerprints.json"


@dataclass(frozen=True)
class Mismatch:
    chapter_num: str
    stored: str
    current: str


def _load_stored() -> dict[str, str]:
    if not OVERRIDES_PATH.exists():
        return {}
    doc = json.loads(OVERRIDES_PATH.read_text())
    out: dict[str, str] = {}
    for cn, entry in (doc.get("chapter_roll_overrides") or {}).items():
        if isinstance(entry, dict) and entry.get(ANCHOR_FIELD):
            out[str(cn)] = entry[ANCHOR_FIELD]
    return out


def _load_current() -> dict[str, str]:
    if not FINGERPRINTS_PATH.exists():
        raise SystemExit(
            f"missing {FINGERPRINTS_PATH}; run scripts/predict_rolls.py first"
        )
    doc = json.loads(FINGERPRINTS_PATH.read_text())
    return dict(doc.get("chapter_alignment_fingerprints") or {})


def check() -> list[Mismatch]:
    """Return chapters whose stored fingerprint disagrees with current.

    A chapter override with no stored fingerprint is NOT a mismatch
    (the bootstrap should have stamped them; warn separately if
    needed). The guard only fires when stamped AND different.
    """
    stored = _load_stored()
    current = _load_current()
    mismatches: list[Mismatch] = []
    for cn, fp in stored.items():
        cur = current.get(cn, "sha256:none")
        if fp != cur:
            mismatches.append(Mismatch(chapter_num=cn, stored=fp, current=cur))
    return mismatches


def chapters_overridden_but_unstamped() -> list[str]:
    """Chapters with an override entry but no stamped fingerprint."""
    if not OVERRIDES_PATH.exists():
        return []
    doc = json.loads(OVERRIDES_PATH.read_text())
    return [
        str(cn)
        for cn, entry in (doc.get("chapter_roll_overrides") or {}).items()
        if isinstance(entry, dict) and not entry.get(ANCHOR_FIELD)
    ]


def fail_if_misaligned() -> None:
    """Raise SystemExit with a human-readable message on any mismatch.

    Called from ``build_chapter_facts.py`` at the top of ``main()``.
    """
    unstamped = chapters_overridden_but_unstamped()
    if unstamped:
        raise SystemExit(
            "chapter_roll_overrides has chapters without an alignment "
            f"fingerprint: {sorted(unstamped)}. Run "
            "scripts/bootstrap_chapter_alignment_anchors.py to stamp them."
        )
    mismatches = check()
    if not mismatches:
        return
    lines = [
        f"  ch {m.chapter_num}: stored={m.stored} current={m.current}"
        for m in sorted(mismatches, key=lambda m: tuple(
            int(p) for p in m.chapter_num.split(".")
        ))
    ]
    raise SystemExit(
        f"{len(mismatches)} chapter(s) have curator overrides anchored to a "
        "stale predicted-roll shape:\n"
        + "\n".join(lines)
        + "\n\nThe predicted-roll positions in these chapters have shifted "
        "since the overrides were authored (likely cause: edits to "
        "section_classifications.json / regime_transitions.json / "
        "obtained_perks.json). Re-align via the curator TUI (`<space>a`) "
        "or, if you've manually reconciled, re-stamp with "
        "`python scripts/bootstrap_chapter_alignment_anchors.py`."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="exit non-zero on any mismatch")
    args = parser.parse_args()
    if args.cmd == "check":
        fail_if_misaligned()
        print(
            "alignment ok: all chapter overrides match current "
            "predicted-roll fingerprints"
        )


if __name__ == "__main__":
    main()
