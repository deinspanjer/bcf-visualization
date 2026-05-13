"""Predict where each roll fires by simulating the mechanic word-by-word.

Reads:
  - data/derived/chapters.json
  - data/derived/obtained_perks.json
  - data/derived/chapter_sections.json   (per-section CP-earning word counts)

Writes:
  - data/derived/predicted_rolls.json

Simulates CP accumulation through the three documented regimes:

  Regime 1 (ch 1-91):   100 CP per 2000 words, roll every 100 CP.
  Regime 2 (ch 92-96):  100 CP per 2000 words, roll every 200 CP.
  Regime 3 (ch 97+):    100 CP per 3000 words, roll every 200 CP, plus
                        a 9000-word "shadow" after each 600-CP perk and
                        a 12000-word shadow after each 800-CP perk
                        during which no CP is banked.

The simulation walks events (chapter starts and paid acquisitions)
in cumulative-word order. Between events, it accumulates CP at the
regime rate, subtracting any active shadow. When banked CP crosses
the roll threshold, a roll is predicted at that exact word offset.

CP-earning word counts come from chapter_sections.json, which classifies
each section of each chapter (Preamble/Addendum/Interlude/perks/news/
PHO posts) and records only the MC-POV word count per chapter. Run
`scripts/extract_chapter_sections.py` first to populate that file.

The prediction is then cross-validated against rolls.json for
chapters 1-75 (where actual rolls are logged), and used to project
roll counts for chapters 76+ where the curator stopped maintaining.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from _common import write_validated_json
from data_paths import DERIVED, MANUAL, ROOT
from multi_grab import (
    load_overrides as load_multi_grab_overrides,
    merge_paid_units,
    unit_principal_cost,
    unit_total_cost,
)
from regime_simulator import (
    REGIMES,
    SHADOW_CP_RATIO,
    PredictedRoll,
    load_regime_transitions,
    regime_for_chapter,
    shadow_words,
    simulate_story,
)

CHAPTERS_JSON = DERIVED / "chapters.json"
OBTAINED_JSON = DERIVED / "obtained_perks.json"
ROLLS_JSON = DERIVED / "rolls.json"
SECTIONS_JSON = DERIVED / "chapter_sections.json"
CLASSIFICATIONS_JSON = MANUAL / "section_classifications.json"
OUT = DERIVED / "predicted_rolls.json"


# Regime model lives in scripts/regime_simulator.py; re-exported above.


# ---------- per-chapter CP-earning word counts ------------------------------


_HEADER_CORRECTIONS_JSON = MANUAL / "header_corrections.json"


def _load_header_correction_ranges_by_chapter() -> dict[str, list[tuple[int, int]]]:
    """Per-chapter list of (word_start, word_end) header-correction
    ranges, in chapter-local word coords.

    Read from ``data/manual/header_corrections.json``; the TUI writes
    chapter-local word offsets there.
    """
    if not _HEADER_CORRECTIONS_JSON.exists():
        return {}
    doc = json.loads(_HEADER_CORRECTIONS_JSON.read_text())
    out: dict[str, list[tuple[int, int]]] = {}
    for c in (doc.get("corrections") or []):
        cn = str(c.get("chapter_num"))
        ws = c.get("word_offset_start")
        we = c.get("word_offset_end")
        if ws is None or we is None or int(we) <= int(ws):
            continue
        out.setdefault(cn, []).append((int(ws), int(we)))
    return out


def _merge_word_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Sort + merge overlapping/adjacent ranges. Mirrors
    ``extract_chapter_sections._merge_word_ranges``; kept here too so
    the consumer doesn't have to import from another script."""
    out: list[list[int]] = []
    for s, e in sorted(ranges):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def _intersect_section_with_excluded(
    section_word_start: int,
    section_word_end: int,
    excluded: list[tuple[int, int]],
) -> int:
    """Total words in ``[section_word_start, section_word_end)`` that
    are also in any of the merged ``excluded`` ranges.
    """
    total = 0
    for ws, we in excluded:
        lo = max(ws, section_word_start)
        hi = min(we, section_word_end)
        if hi > lo:
            total += hi - lo
    return total


def _load_cp_words_per_chapter() -> dict[str, int]:
    """Canonical CP-eligible word count per chapter, keyed by full_title.

    Walks each chapter's CP-eligible sections (``counts_for_cp=True``
    AND ``cls_data`` doesn't override to False) and subtracts the union
    of CP-exclusion word ranges (AN + auto-header from
    ``chapter_sections.json:excluded_word_ranges`` + manual
    header_corrections from ``data/manual/header_corrections.json``).
    Range-merging guarantees overlapping exclusions are counted once.
    """
    if not SECTIONS_JSON.exists():
        raise SystemExit(
            f"missing {SECTIONS_JSON.relative_to(ROOT)}; run "
            "scripts/extract_chapter_sections.py first"
        )
    if not CLASSIFICATIONS_JSON.exists():
        raise SystemExit(
            f"missing {CLASSIFICATIONS_JSON.relative_to(ROOT)}; run "
            "scripts/build_section_classifications.py first"
        )
    sections_data = json.loads(SECTIONS_JSON.read_text())
    cls_data = json.loads(CLASSIFICATIONS_JSON.read_text())["classifications"]
    manual_header_by_chapter = _load_header_correction_ranges_by_chapter()

    out: dict[str, int] = {}
    for c in sections_data["chapters"]:
        cn = str(c["chapter_num"])
        # Build per-chapter union of excluded word ranges (chapter-local).
        chapter_excl = list(c.get("excluded_word_ranges") or [])
        chapter_excl_tuples = [(int(s), int(e)) for s, e in chapter_excl]
        chapter_excl_tuples.extend(manual_header_by_chapter.get(cn, []))
        merged = _merge_word_ranges(chapter_excl_tuples)
        # Walk sections in order, accumulating eligible words.
        total = 0
        word_cursor = 0
        for i, s in enumerate(c["sections"]):
            wc = int(s["word_count"])
            sec_start = word_cursor
            sec_end = word_cursor + wc
            key = f"{cn}@{i}"
            section_eligible = (
                bool(s.get("counts_for_cp", True))
                and cls_data.get(key, {}).get("counts_for_cp", True)
            )
            if section_eligible:
                excluded_in_section = _intersect_section_with_excluded(
                    sec_start, sec_end, merged,
                )
                total += max(0, wc - excluded_in_section)
            word_cursor = sec_end
        out[c["full_title"]] = max(0, total)
    return out


# ---------- simulation ------------------------------------------------------


def _sort_key(num: str) -> tuple[int, int]:
    parts = num.split(".", 1)
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _simulate(chapters_in_order, paid_by_chapter, exact_words, transitions=None):
    """Thin shim around `regime_simulator.simulate_story`."""
    return simulate_story(
        chapters_in_order, paid_by_chapter, exact_words, transitions,
    )


# ---------- per-chapter prediction ------------------------------------------


def predict_chapter(
    chapter_num: str,
    chapters: list[dict] | None = None,
    obtained_perks: list[dict] | None = None,
    cp_words: dict[str, int] | None = None,
    transitions: list[dict] | None = None,
    multi_overrides: dict | None = None,
) -> dict:
    """Predict rolls for a single chapter, in isolation.

    This is a Phase 0 scaffold for the Forge Curator's per-chapter
    in-memory recompute (Phase 3). It re-runs the whole-story
    simulation but slices the output to the requested chapter; the
    cost is negligible at story scale and avoids reimplementing the
    cumulative banked-CP / shadow walk.

    All arguments are optional and default to disk-loaded values, so
    callers can do ``predict_chapter("97")`` for a quick lookup.

    Returns ``{
        "chapter_num": str,
        "predicted": [asdict(PredictedRoll), ...],
        "chapter_word_start": int,
        "chapter_word_end": int,
    }``.
    """
    if chapters is None:
        chapters = sorted(
            json.loads(CHAPTERS_JSON.read_text())["chapters"],
            key=lambda c: tuple(c["sort_key"]),
        )
    if obtained_perks is None:
        obtained_perks = json.loads(OBTAINED_JSON.read_text())["perks"]
    if cp_words is None:
        cp_words = _load_cp_words_per_chapter()
    if transitions is None:
        transitions = load_regime_transitions()
    if multi_overrides is None:
        multi_overrides = load_multi_grab_overrides()

    obtained_sorted = sorted(obtained_perks, key=lambda p: p.get("epub_sequence", 0))
    units, _ = merge_paid_units(obtained_sorted, multi_overrides)
    paid_by_chapter: dict[str, list[dict]] = {}
    for unit in units:
        paid_by_chapter.setdefault(unit["chapter_num"], []).append({
            "cost": unit_total_cost(unit),
            "principal_cost": unit_principal_cost(unit),
        })

    predicted, chap_start, chap_end, _ = simulate_story(
        chapters, paid_by_chapter, cp_words, transitions,
    )
    return {
        "chapter_num": str(chapter_num),
        "predicted": [
            asdict(p) for p in predicted if str(p.chapter_num) == str(chapter_num)
        ],
        "chapter_word_start": chap_start.get(str(chapter_num)),
        "chapter_word_end": chap_end.get(str(chapter_num)),
    }


# ---------- main ------------------------------------------------------------


def main() -> None:
    chapters_data = json.loads(CHAPTERS_JSON.read_text())
    chapters = sorted(chapters_data["chapters"], key=lambda c: tuple(c["sort_key"]))
    obtained = json.loads(OBTAINED_JSON.read_text())["perks"]

    cp_words = _load_cp_words_per_chapter()
    missing_titles = [c for c in chapters if c["full_title"] not in cp_words]
    if missing_titles:
        raise SystemExit(
            f"{len(missing_titles)} chapter title(s) in chapters.json missing "
            f"from chapter_sections.json (first: {missing_titles[0]['full_title']!r}). "
            "Re-run scripts/extract_chapter_sections.py."
        )

    obtained_sorted = sorted(obtained, key=lambda p: p.get("epub_sequence", 0))
    multi_overrides = load_multi_grab_overrides()
    units, _ = merge_paid_units(obtained_sorted, multi_overrides)

    # For the simulator we treat each merged unit as ONE acquisition event.
    # We pass the unit's TOTAL cost as the perk_cost so any shadow logic
    # for 600/800 CP triggers correctly when the unit's largest paid cost
    # crosses the threshold; total cost matches what the Forge actually
    # debits in a multi-grab.
    paid_by_chapter: dict[str, list[dict]] = {}
    for unit in units:
        cn = unit["chapter_num"]
        # The largest-cost perk drives shadow (only 600/800 trigger shadows).
        # But total cost matches the actual debit. Use total cost for `cost`
        # since simulate_story uses it to debit banked CP; shadow is keyed on
        # the cost passed in. To preserve shadow correctness, use principal
        # for shadow lookup *and* total for debit, simulate_story uses cost
        # for both — pass the principal cost when it triggers a shadow, else
        # total. (The total != principal case is rare and only matters for
        # ch 97 where Nano-Forge 600 sits with 200+200 multi-grab.)
        cost = unit_total_cost(unit)
        paid_by_chapter.setdefault(cn, []).append({
            "cost": cost,
            "principal_cost": unit_principal_cost(unit),
        })

    transitions = load_regime_transitions()

    predicted, chap_start, chap_end, total_words = _simulate(
        chapters, paid_by_chapter, cp_words, transitions,
    )

    # Cross-validate per-chapter roll counts against rolls.json (ch 1-75).
    rolls_data = json.loads(ROLLS_JSON.read_text())
    actual_per_chap: dict[str, int] = {}
    for r in rolls_data["rolls"]:
        if r["kind"] in ("trigger", "roll", "miss"):
            actual_per_chap[r["chapter_num"]] = actual_per_chap.get(r["chapter_num"], 0) + 1

    predicted_per_chap: dict[str, int] = {}
    for pr in predicted:
        predicted_per_chap[pr.chapter_num] = predicted_per_chap.get(pr.chapter_num, 0) + 1

    # Build comparison rows for chapters with actual data
    comparison = []
    for cn in sorted(actual_per_chap, key=_sort_key):
        comparison.append({
            "chapter_num": cn,
            "actual_rolls": actual_per_chap[cn],
            "predicted_rolls": predicted_per_chap.get(cn, 0),
            "delta": predicted_per_chap.get(cn, 0) - actual_per_chap[cn],
        })

    payload = {
        "_source": (
            "Simulated from chapters.json + obtained_perks.json + per-section "
            "CP-earning word counts (chapter_sections.json) using the "
            "documented three-regime model."
        ),
        "_count": len(predicted),
        "_total_words_epub_exact": total_words,
        "_regime_summary": {
            "1": "ch 1-91: 100 CP / 2000 words, roll every 100 CP",
            "2": "ch 92-96: 100 CP / 2000 words, roll every 200 CP",
            "3": "ch 97+: 100 CP / 3000 words, roll every 200 CP, "
                 "plus 9k/12k word shadow after 600/800 perks",
        },
        "_validation_chapters_1_75": {
            "actual_total_attempts": sum(actual_per_chap[cn] for cn in actual_per_chap
                                          if int(cn.split(".")[0]) <= 75),
            "predicted_total_in_same_chapters": sum(
                predicted_per_chap.get(cn, 0) for cn in actual_per_chap
                if int(cn.split(".")[0]) <= 75
            ),
        },
        "predicted": [asdict(p) for p in predicted],
        "comparison_per_chapter": comparison,
    }

    write_validated_json(OUT, payload, "predicted_rolls")

    # Print a small summary
    by_regime = {1: 0, 2: 0, 3: 0}
    for p in predicted:
        by_regime[p.cp_rule_regime] += 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(predicted)} predicted rolls")
    print(f"  by regime: {by_regime}")
    val = payload["_validation_chapters_1_75"]
    print(f"  ch 1-75: actual={val['actual_total_attempts']}, "
          f"predicted={val['predicted_total_in_same_chapters']}, "
          f"delta={val['predicted_total_in_same_chapters'] - val['actual_total_attempts']:+d}")
    # Show top deltas
    big_deltas = sorted(comparison, key=lambda r: -abs(r["delta"]))[:5]
    if big_deltas:
        print("  top per-chapter deltas (predicted - actual):")
        for row in big_deltas:
            print(f"    ch{row['chapter_num']:>5s}: actual={row['actual_rolls']} "
                  f"predicted={row['predicted_rolls']} delta={row['delta']:+d}")


if __name__ == "__main__":
    main()
