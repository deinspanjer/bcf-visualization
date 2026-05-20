"""Interactive re-alignment of chapter overrides whose stamped
predicted-roll fingerprint disagrees with the current one.

When the alignment guard (``scripts/chapter_alignment.py``) reports
mismatches, this tool walks each affected chapter and shows the
diff between the predicted-roll shape the override was authored
against and the current shape. Per-chapter, the user can:

  accept  — re-stamp the chapter's ``_fingerprint`` with the current
            value. Override data left untouched.
  skip    — leave the chapter mismatched; the alignment guard will
            keep failing builds until handled.
  abort   — exit immediately, no changes.

This tool DOES NOT modify the override's ``rolls`` array. If the
predicted-roll shape changed in a way that requires re-mapping (e.g.
roll N is now slot N+1 because an extra roll was inserted earlier),
edit the override in the curator TUI first, save, then run this
tool to re-stamp.
"""

from __future__ import annotations

import argparse
import json
import sys

from chapter_alignment import (
    ANCHOR_FIELD,
    FINGERPRINTS_PATH,
    OVERRIDES_PATH,
    Mismatch,
    check,
)


def _load_predicted_by_chapter() -> dict[str, list[dict]]:
    from predict_rolls import OUT as PREDICTED_PATH
    doc = json.loads(PREDICTED_PATH.read_text())
    by_chapter: dict[str, list[dict]] = {}
    for roll in doc.get("predicted", []):
        cn = str(roll.get("chapter_num"))
        by_chapter.setdefault(cn, []).append(roll)
    for rolls in by_chapter.values():
        rolls.sort(key=lambda r: int(r.get("cp_offset") or 0))
    return by_chapter


def _format_predicted_rolls(rolls: list[dict]) -> list[str]:
    return [
        (
            f"  slot {i+1}: roll#{r.get('roll_number'):<3d} "
            f"cp={r.get('cp_offset'):>7d} epub={r.get('epub_offset'):>7d} "
            f"regime={r.get('cp_rule_regime')} threshold={r.get('roll_trigger_cp_threshold')}"
        )
        for i, r in enumerate(rolls)
    ]


def _print_chapter_diff(m: Mismatch, current_rolls: list[dict]) -> None:
    print()
    print(f"=== chapter {m.chapter_num} ===")
    print(f"  stored fingerprint:  {m.stored}")
    print(f"  current fingerprint: {m.current}")
    print(f"  current predicted-roll shape ({len(current_rolls)} slot(s)):")
    for line in _format_predicted_rolls(current_rolls):
        print(line)
    print()
    print(
        "  NOTE: the override's `rolls` array is anchored by 1-based slot "
        "index. If the slot count or order has changed, edit the "
        "override in the curator TUI BEFORE re-stamping."
    )


def _restamp(chapter_num: str, new_fingerprint: str) -> None:
    doc = json.loads(OVERRIDES_PATH.read_text())
    overrides = doc.get("chapter_roll_overrides") or {}
    entry = overrides.get(str(chapter_num))
    if not isinstance(entry, dict):
        raise SystemExit(f"no override entry for chapter {chapter_num}")
    entry[ANCHOR_FIELD] = new_fingerprint
    OVERRIDES_PATH.write_text(json.dumps(doc, indent=2) + "\n")


def _prompt(prompt_text: str, choices: list[str]) -> str:
    valid = {c[0]: c for c in choices}
    options = "/".join(choices)
    while True:
        try:
            raw = input(f"{prompt_text} [{options}] ").strip().lower()
        except EOFError:
            return "abort"
        if not raw:
            continue
        if raw in valid:
            return valid[raw]
        if raw in choices:
            return raw
        print(f"  please type one of: {', '.join(choices)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--yes", action="store_true",
        help="accept every mismatch without prompting (dangerous; "
        "use only after you've manually verified all overrides are "
        "still correct against the new predicted-roll shape).",
    )
    args = parser.parse_args()

    mismatches = check()
    if not mismatches:
        print("alignment ok: no chapters need re-stamping")
        return

    print(
        f"{len(mismatches)} chapter(s) have curator overrides anchored "
        "to a stale predicted-roll shape:"
    )
    for m in mismatches:
        print(f"  - chapter {m.chapter_num}")

    predicted_by_chapter = _load_predicted_by_chapter()

    accepted = 0
    skipped = 0
    for m in sorted(mismatches, key=lambda x: tuple(
        int(p) for p in x.chapter_num.split(".")
    )):
        current_rolls = predicted_by_chapter.get(m.chapter_num, [])
        _print_chapter_diff(m, current_rolls)
        if args.yes:
            choice = "accept"
        else:
            choice = _prompt(
                f"re-stamp chapter {m.chapter_num}?",
                ["accept", "skip", "abort"],
            )
        if choice == "abort":
            print("aborted; no changes saved beyond previously accepted chapters")
            sys.exit(2)
        if choice == "skip":
            skipped += 1
            continue
        _restamp(m.chapter_num, m.current)
        accepted += 1
        print(f"  re-stamped chapter {m.chapter_num}")

    print()
    print(f"done: {accepted} re-stamped, {skipped} skipped")
    if skipped:
        print("  WARNING: skipped chapters will keep failing the alignment guard")
        sys.exit(1)


if __name__ == "__main__":
    main()
