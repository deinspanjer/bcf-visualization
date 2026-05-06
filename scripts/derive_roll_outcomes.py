"""Derive interpolated per-roll hit/miss outcomes.

Placeholder pipeline used until NLP-extracted ground-truth roll outcomes
(from `roll_text_evidence.json` and friends) are available at scale.

Approach
--------

For each chapter we know:

  * N predicted roll positions (`predicted_rolls.json`) — the word
    offsets where the predicted-rolls model thinks Joe rolled.
  * K obtained perks (`obtained_perks.json`) — the canonical count of
    perks Joe actually acquired in that chapter, in narrative order.

We treat K as ground truth (canon) and N as the model's best guess for
WHEN within the chapter rolls occurred. We do NOT trust the model's
implicit hit/miss judgment — the canonical K hits are spread evenly
across the N predicted slots using:

    hit_slot_index(i) = floor((i + 0.5) * N / K)   for i in [0, K)

Worked example: N=5 predicted slots, K=2 perks acquired ->
positions 1 and 3 -> outcome pattern `0X0X0` (miss, hit, miss, hit, miss).

Edge cases
----------

  * K == 0           -> all N predicted rolls are misses.
  * K == N           -> all rolls are hits.
  * K > N            -> we synthesize (K - N) additional roll slots at
                        evenly-spaced word positions using the chapter's
                        `words_approx`. Total slots become K, all hits.
                        Synthesized slots are tagged `source: "synthetic"`.
  * N == 0, K > 0    -> all K slots are synthesized (no predicted slots
                        existed for this chapter).
  * Both zero        -> nothing emitted for that chapter.

Perk assignment
---------------

Perks are attached to hit slots in `epub_sequence` order (canonical
narrative order) -> hit slots in `word_position` ascending order.

Output
------

`data/derived/roll_outcomes.json` with per-roll records containing
`{chapter_num, word_position, outcome, perk, source, ...}`. Suitable for
direct consumption by the planetarium timeline view.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PREDICTED = ROOT / "data" / "derived" / "predicted_rolls.json"
DEFAULT_PERKS = ROOT / "data" / "derived" / "obtained_perks.json"
DEFAULT_CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
DEFAULT_OUTPUT = ROOT / "data" / "derived" / "roll_outcomes.json"

SCHEMA_VERSION = 1


def _hit_slot_indices(n_slots: int, k_hits: int) -> list[int]:
    """Return the slot indices (0-based, ascending) that should be hits.

    Uses the proportional-spacing rule documented in the module docstring.
    Handles the K > N case by clamping to N (caller is expected to grow
    the slot count first); K == 0 returns []; K >= N returns all indices.
    """
    if k_hits <= 0 or n_slots <= 0:
        return []
    if k_hits >= n_slots:
        return list(range(n_slots))
    return [int((i + 0.5) * n_slots / k_hits) for i in range(k_hits)]


def _synthetic_positions(words: int, count: int, after_real: list[int]) -> list[int]:
    """Generate `count` synthetic word positions inside a chapter of
    `words` words, avoiding collision with already-placed positions.

    We spread synthetic slots evenly across the chapter then nudge any
    that collide with a real position by +1. Word positions are integers
    and uniqueness only matters for downstream sorting stability.
    """
    if count <= 0:
        return []
    # Evenly spaced fractional positions: 1/(count+1), 2/(count+1), ...
    positions = [max(1, int(words * (i + 1) / (count + 1))) for i in range(count)]
    used = set(after_real)
    out: list[int] = []
    for p in positions:
        while p in used:
            p += 1
        used.add(p)
        out.append(p)
    return out


def _build_chapter_slots(
    chapter_num: str,
    predicted: list[dict],
    perks: list[dict],
    words_approx: int,
) -> list[dict]:
    """Build the ordered slot list for one chapter.

    Returns slots in word_position ascending order. Each slot is a dict
    with keys:
        chapter_num, word_position, source, outcome, perk,
        regime (predicted only), cp_threshold (predicted only),
        roll_number (predicted only)
    """
    n = len(predicted)
    k = len(perks)
    if n == 0 and k == 0:
        return []

    # Real predicted slots (already sorted by word_position upstream, but
    # sort defensively).
    real = sorted(predicted, key=lambda r: r["word_position"])
    real_positions = [r["word_position"] for r in real]

    # If we need more slots than predictions, synthesize the difference.
    extra = max(0, k - n)
    synth_positions = _synthetic_positions(
        words_approx or 1000, extra, real_positions
    )

    slots: list[dict] = []
    for r in real:
        slots.append({
            "chapter_num": chapter_num,
            "word_position": r["word_position"],
            "source": "predicted",
            "outcome": "miss",  # default; flipped to "hit" below
            "perk": None,
            "roll_number": r.get("roll_number"),
            "regime": r.get("regime"),
            "cp_threshold": r.get("cp_threshold"),
        })
    for pos in synth_positions:
        slots.append({
            "chapter_num": chapter_num,
            "word_position": pos,
            "source": "synthetic",
            "outcome": "miss",
            "perk": None,
            "roll_number": None,
            "regime": None,
            "cp_threshold": None,
        })

    slots.sort(key=lambda s: s["word_position"])

    # Pick which slots are hits using the proportional-spacing rule.
    n_slots = len(slots)
    hit_idxs = _hit_slot_indices(n_slots, k)
    for idx, perk in zip(hit_idxs, perks):
        slot = slots[idx]
        slot["outcome"] = "hit"
        slot["perk"] = {
            "name": perk["perk_name"],
            "constellation": perk.get("constellation"),
            "jump": perk.get("jump"),
            "cost": perk.get("cost"),
            "free": perk.get("free", False),
            "epub_sequence": perk.get("epub_sequence"),
        }

    return slots


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--predicted", type=Path, default=DEFAULT_PREDICTED)
    p.add_argument("--perks", type=Path, default=DEFAULT_PERKS)
    p.add_argument("--chapters", type=Path, default=DEFAULT_CHAPTERS)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    predicted_raw = json.loads(args.predicted.read_text())
    perks_raw = json.loads(args.perks.read_text())
    chapters_raw = json.loads(args.chapters.read_text())

    predicted_rolls: list[dict] = predicted_raw["predicted"]
    obtained_perks: list[dict] = sorted(
        perks_raw["perks"], key=lambda p: p.get("epub_sequence", 0)
    )
    chapters: list[dict] = chapters_raw["chapters"]

    # Index chapter metadata.
    chapter_order: list[str] = [c["chapter_num"] for c in chapters]
    chapter_pos = {c: i for i, c in enumerate(chapter_order)}
    words_by_chapter: dict[str, int] = {
        c["chapter_num"]: int(c.get("words_approx") or 0) for c in chapters
    }

    # Group inputs by chapter.
    pred_by_ch: dict[str, list[dict]] = defaultdict(list)
    for r in predicted_rolls:
        pred_by_ch[r["chapter_num"]].append(r)

    perks_by_ch: dict[str, list[dict]] = defaultdict(list)
    for p in obtained_perks:
        perks_by_ch[p["chapter_num"]].append(p)

    # Build slots in canonical chapter order, falling back to the union
    # of seen chapter_nums for anything that isn't in chapters.json (this
    # shouldn't happen for the main story but section keys like "58.2"
    # are present in both predictions and perks and need handling).
    seen_chapter_nums = set(pred_by_ch) | set(perks_by_ch)
    extra_chapter_nums = sorted(
        seen_chapter_nums - set(chapter_order),
        key=lambda c: (float(c) if _isfloat(c) else float("inf"), c),
    )
    iteration_order = chapter_order + extra_chapter_nums

    all_rolls: list[dict] = []
    per_chapter_summary: list[dict] = []

    for chapter_num in iteration_order:
        preds = pred_by_ch.get(chapter_num, [])
        perks = perks_by_ch.get(chapter_num, [])
        if not preds and not perks:
            continue
        slots = _build_chapter_slots(
            chapter_num,
            preds,
            perks,
            words_by_chapter.get(chapter_num, 0),
        )
        all_rolls.extend(slots)

        n_pred = len(preds)
        k_perks = len(perks)
        n_synth = sum(1 for s in slots if s["source"] == "synthetic")
        per_chapter_summary.append({
            "chapter_num": chapter_num,
            "predicted_rolls": n_pred,
            "obtained_perks": k_perks,
            "slots_emitted": len(slots),
            "synthetic_slots": n_synth,
            "hits": sum(1 for s in slots if s["outcome"] == "hit"),
            "misses": sum(1 for s in slots if s["outcome"] == "miss"),
        })

    # Counts for the file header.
    chapters_with_pred = sum(1 for c in pred_by_ch if pred_by_ch[c])
    chapters_with_perks = sum(1 for c in perks_by_ch if perks_by_ch[c])
    chapters_with_both = sum(
        1 for c in seen_chapter_nums if pred_by_ch.get(c) and perks_by_ch.get(c)
    )
    chapters_pred_only = sum(
        1 for c in seen_chapter_nums if pred_by_ch.get(c) and not perks_by_ch.get(c)
    )
    chapters_perks_only = sum(
        1 for c in seen_chapter_nums if perks_by_ch.get(c) and not pred_by_ch.get(c)
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "_source": (
            "Interpolated from data/derived/predicted_rolls.json + "
            "data/derived/obtained_perks.json"
        ),
        "_method": (
            "Per chapter, K obtained perks distributed proportionally across "
            "max(N,K) roll slots using floor((i+0.5)*M/K) for hit-slot index i. "
            "Where K > N, additional slots are synthesized at evenly-spaced "
            "word positions using chapters.json words_approx."
        ),
        "_caveat": (
            "PLACEHOLDER until NLP-extracted ground-truth roll outcomes are "
            "available. Per-chapter HIT COUNT is canonical; within-chapter "
            "hit/miss timing is the predicted-rolls model's guess interpolated "
            "by even spacing."
        ),
        "_counts": {
            "rolls_emitted": len(all_rolls),
            "hits": sum(1 for r in all_rolls if r["outcome"] == "hit"),
            "misses": sum(1 for r in all_rolls if r["outcome"] == "miss"),
            "synthetic_slots": sum(1 for r in all_rolls if r["source"] == "synthetic"),
            "predicted_input_count": len(predicted_rolls),
            "obtained_perks_input_count": len(obtained_perks),
            "chapters_with_predictions": chapters_with_pred,
            "chapters_with_perks": chapters_with_perks,
            "chapters_with_both": chapters_with_both,
            "chapters_predictions_only": chapters_pred_only,
            "chapters_perks_only": chapters_perks_only,
        },
        "rolls": all_rolls,
        "per_chapter": per_chapter_summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    rel = args.output.relative_to(ROOT)
    counts = payload["_counts"]
    print(f"wrote {rel}")
    print(f"  rolls emitted:           {counts['rolls_emitted']}")
    print(f"    hits:                  {counts['hits']}")
    print(f"    misses:                {counts['misses']}")
    print(f"    synthetic slots:       {counts['synthetic_slots']}")
    print(f"  chapters with both:      {counts['chapters_with_both']}")
    print(f"  chapters predictions only:{counts['chapters_predictions_only']}")
    print(f"  chapters perks only:     {counts['chapters_perks_only']}")


def _isfloat(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    main()
