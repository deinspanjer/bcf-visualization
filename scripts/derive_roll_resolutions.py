"""Derive the roll-resolution table from all available data sources.

For each predicted roll (from predicted_rolls.json) this script builds one
output record that captures:
  - Positional fields (roll_number, chapter_num, section_index, word/char
    offsets, anchor_string) pulled from predicted_rolls.json and
    roll_text_evidence.json.
  - Curator outcome fields (curator_outcome, curator_perk_name, …) looked up
    in rolls.json for ch 1-75; null for ch 76+.
  - banked_at_roll / banked_at_roll_source: curator value when available, else
    the predicted roll's roll_trigger_cp_threshold.
  - chapter_acquired_perks_in_order: all perks in obtained_perks.json for this
    chapter, in epub_sequence order.
  - outstanding_perks_with_cost_gt_banked: perks whose cost > banked_at_roll
    at chapter start (from outstanding_perks_by_chapter.json).
  - constellations_known_by_joe: before_chapter_known list from
    constellation_knowledge_by_chapter.json.

Output: data/derived/roll_resolutions.json
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from _common import write_validated_json

# ---------- default paths ---------------------------------------------------

PREDICTED_ROLLS_DEFAULT = ROOT / "data" / "derived" / "predicted_rolls.json"
CURATOR_ROLLS_DEFAULT   = ROOT / "data" / "derived" / "rolls.json"
OBTAINED_PERKS_DEFAULT  = ROOT / "data" / "derived" / "obtained_perks.json"
CONSTELLATION_KN_DEFAULT = ROOT / "data" / "derived" / "constellation_knowledge_by_chapter.json"
OUTSTANDING_PERKS_DEFAULT = ROOT / "data" / "derived" / "outstanding_perks_by_chapter.json"
ROLL_TEXT_EVIDENCE_DEFAULT = ROOT / "data" / "derived" / "roll_text_evidence.json"
CHAPTER_FACTS_DEFAULT   = ROOT / "data" / "derived" / "chapter_facts.json"
OUTPUT_DEFAULT          = ROOT / "data" / "derived" / "roll_resolutions.json"


# ---------- helpers ---------------------------------------------------------

def sort_key_for_chapter(chapter_num: str) -> tuple[int, int]:
    """Numeric sort key so '11' sorts after '2', and '3.1' stays with ch 3."""
    parts = chapter_num.split(".")
    try:
        return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except ValueError:
        return (0, 0)


# ---------- loader functions ------------------------------------------------

def load_predicted_rolls(path: Path) -> list[dict]:
    """Return list of predicted roll dicts, sorted by roll_number."""
    data = json.loads(path.read_text())
    rolls = data["predicted"]
    rolls.sort(key=lambda r: r["roll_number"])
    return rolls


def load_curator_rolls(path: Path) -> dict[int, dict]:
    """Return a mapping roll_number -> best curator entry.

    Only kind in {'roll', 'miss'} entries are kept.  When a roll_number has
    multiple entries that satisfy the filter (duplicate curator bookkeeping),
    prefer kind=='roll' over kind=='miss', then take the first remaining.
    roll_number=None entries (triggers/annotations) are silently ignored.
    """
    data = json.loads(path.read_text())
    by_rn: dict[int, list[dict]] = defaultdict(list)
    for entry in data["rolls"]:
        rn = entry.get("roll_number")
        if rn is None:
            continue
        if entry["kind"] not in ("roll", "miss"):
            continue
        by_rn[rn].append(entry)

    result: dict[int, dict] = {}
    for rn, entries in by_rn.items():
        # Prefer HIT ('roll') over MISS when duplicates exist.
        hits = [e for e in entries if e["kind"] == "roll"]
        if hits:
            result[rn] = hits[0]
        else:
            result[rn] = entries[0]
    return result


def load_obtained_perks_by_chapter(path: Path) -> dict[str, list[dict]]:
    """Return chapter_num -> list of perk dicts, sorted by epub_sequence."""
    data = json.loads(path.read_text())
    by_chap: dict[str, list[dict]] = defaultdict(list)
    for perk in data["perks"]:
        by_chap[perk["chapter_num"]].append(perk)
    for perks in by_chap.values():
        perks.sort(key=lambda p: p["epub_sequence"])
    return dict(by_chap)


def load_constellation_knowledge(path: Path) -> dict[str, list[str]]:
    """Return chapter_num -> before_chapter_known list."""
    data = json.loads(path.read_text())
    return {c["chapter_num"]: c["before_chapter_known"] for c in data["chapters"]}


def load_outstanding_perks(path: Path) -> dict[str, dict[str, list[dict]]]:
    """Return chapter_num -> before_chapter.by_constellation dict."""
    data = json.loads(path.read_text())
    return {
        c["chapter_num"]: c["before_chapter"]["by_constellation"]
        for c in data["chapters"]
    }


def load_roll_text_evidence(path: Path) -> dict[int, dict]:
    """Return roll_number -> evidence dict."""
    data = json.loads(path.read_text())
    return {e["roll_number"]: e for e in data["rolls"]}


def load_section_index_from_chapter_facts(path: Path) -> dict[int, int]:
    """Return roll_number -> section_index from the chapter_facts derivation.

    chapter_facts.py computed section_index for every predicted roll by
    comparing the predicted_char_offset against the EPUB HTML section
    boundaries.  Re-using that result avoids duplicating the EPUB parsing
    logic here.
    """
    data = json.loads(path.read_text())
    result: dict[int, int] = {}
    for chapter in data["chapters"]:
        for roll in chapter["rolls"]:
            rn = roll.get("roll_number")
            if rn is not None:
                result[rn] = roll["section_index"]
    return result


# ---------- per-roll builders -----------------------------------------------

def build_curator_fields(
    rn: int,
    curator_map: dict[int, dict],
) -> dict:
    """Return the curator_* sub-dict for this roll_number.

    All fields are None when no curator entry exists (ch 76+).
    For MISS entries the perk fields are None; constellation may be populated.
    For HIT entries:
      - curator_perk_name  = first non-free perk (principal acquisition)
      - curator_free_associated_perks = remaining perks (free or additional
        paid in a bundled roll; in practice the curator records extras after
        the first paid as free=True in the log even when there are two paid
        perks in the same roll — we preserve them all as associates)
    """
    entry = curator_map.get(rn)
    if entry is None:
        return {
            "curator_outcome": None,
            "curator_perk_name": None,
            "curator_constellation": None,
            "curator_cost": None,
            "curator_free_associated_perks": None,
            "curator_banked_before": None,
            "curator_banked_after": None,
        }

    is_hit = entry["kind"] == "roll"
    perks = entry.get("perks") or []

    if is_hit and perks:
        principal = perks[0]
        perk_name = principal["name"]
        perk_cost = principal.get("cost")
        associates = [
            {"name": p["name"], "constellation": entry.get("constellation")}
            for p in perks[1:]
        ] if len(perks) > 1 else None
    else:
        perk_name = None
        perk_cost = None
        associates = None

    return {
        "curator_outcome": "HIT" if is_hit else "MISS",
        "curator_perk_name": perk_name,
        "curator_constellation": entry.get("constellation"),
        "curator_cost": perk_cost,
        "curator_free_associated_perks": associates,
        "curator_banked_before": entry.get("banked_before"),
        "curator_banked_after": entry.get("banked_after"),
    }


def build_chapter_acquired_perks(
    chapter_num: str,
    obtained_by_chapter: dict[str, list[dict]],
) -> list[dict]:
    """Return ordered list of {name, constellation, cost, free} for the chapter."""
    perks = obtained_by_chapter.get(chapter_num, [])
    return [
        {
            "name": p["perk_name"],
            "constellation": p.get("constellation"),
            "cost": p.get("cost"),
            "free": bool(p.get("free")),
        }
        for p in perks
    ]


def build_outstanding_filtered(
    chapter_num: str,
    banked_at_roll: int | None,
    outstanding_by_chapter: dict[str, dict[str, list[dict]]],
) -> list[dict]:
    """Return outstanding perks whose cost > banked_at_roll at chapter start.

    Perks without a cost are excluded (cannot compare).
    If banked_at_roll is None we return an empty list.
    """
    if banked_at_roll is None:
        return []
    by_constellation = outstanding_by_chapter.get(chapter_num, {})
    result: list[dict] = []
    for constellation, perks in by_constellation.items():
        for perk in perks:
            cost = perk.get("cost")
            if cost is None:
                continue
            if cost > banked_at_roll:
                result.append({
                    "name": perk["name"],
                    "cost": cost,
                    "constellation": constellation,
                })
    # Sort for determinism: by cost desc, then name.
    result.sort(key=lambda p: (-p["cost"], p["name"]))
    return result


# ---------- main ------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive roll_resolutions.json from predicted rolls and curator data.",
    )
    parser.add_argument(
        "--predicted-rolls",
        type=Path,
        default=PREDICTED_ROLLS_DEFAULT,
        help="Path to predicted_rolls.json",
    )
    parser.add_argument(
        "--curator-rolls",
        type=Path,
        default=CURATOR_ROLLS_DEFAULT,
        help="Path to rolls.json (curator log, ch 1-75)",
    )
    parser.add_argument(
        "--obtained-perks",
        type=Path,
        default=OBTAINED_PERKS_DEFAULT,
        help="Path to obtained_perks.json",
    )
    parser.add_argument(
        "--constellation-knowledge",
        type=Path,
        default=CONSTELLATION_KN_DEFAULT,
        help="Path to constellation_knowledge_by_chapter.json",
    )
    parser.add_argument(
        "--outstanding-perks",
        type=Path,
        default=OUTSTANDING_PERKS_DEFAULT,
        help="Path to outstanding_perks_by_chapter.json",
    )
    parser.add_argument(
        "--roll-text-evidence",
        type=Path,
        default=ROLL_TEXT_EVIDENCE_DEFAULT,
        help="Path to roll_text_evidence.json",
    )
    parser.add_argument(
        "--chapter-facts",
        type=Path,
        default=CHAPTER_FACTS_DEFAULT,
        help="Path to chapter_facts.json (used for section_index lookup)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help="Output path for roll_resolutions.json",
    )
    args = parser.parse_args()

    # ---------- load all inputs ----------
    predicted = load_predicted_rolls(args.predicted_rolls)
    curator_map = load_curator_rolls(args.curator_rolls)
    obtained_by_chapter = load_obtained_perks_by_chapter(args.obtained_perks)
    constellation_knowledge = load_constellation_knowledge(args.constellation_knowledge)
    outstanding_by_chapter = load_outstanding_perks(args.outstanding_perks)
    evidence_map = load_roll_text_evidence(args.roll_text_evidence)
    section_index_map = load_section_index_from_chapter_facts(args.chapter_facts)

    # ---------- build output records ----------
    out_rolls: list[dict] = []
    n_hit = 0
    n_miss = 0
    n_unresolved = 0
    n_missing_section_index = 0

    # Counters for anomaly logging
    missing_curator_ch1_75: list[int] = []

    for pred in predicted:
        rn: int = pred["roll_number"]
        chapter_num: str = pred["chapter_num"]
        chapter_int = int(chapter_num.split(".")[0])
        # Only look up curator data for rolls whose PREDICTED chapter is ch 1-75.
        # Even if a roll_number exists in rolls.json (curator goes up to roll 503),
        # a roll predicted in ch 76+ should have no curator outcome per spec.  The
        # regime simulator and the curator can disagree on which chapter a roll
        # belongs to for the boundary rolls (485-503), so we gate on predicted chapter.
        has_curator = chapter_int <= 75

        # --- chapter attribution disagreement ---
        # Check whether the curator placed this roll in a different chapter than
        # the simulator.  We do this regardless of has_curator so that boundary
        # rolls (predicted ch 76+ but present in curator) are also captured.
        curator_entry = curator_map.get(rn)
        if curator_entry is not None:
            curator_chapter_num: str | None = str(curator_entry["chapter_num"])
        else:
            curator_chapter_num = None
        chapter_attribution_disagreement: bool = (
            curator_chapter_num is not None and curator_chapter_num != chapter_num
        )

        # --- identity + position fields ---
        ev = evidence_map.get(rn, {})
        predicted_word_position_epub: int = (
            ev.get("predicted_word_position_epub") or pred["word_position"]
        )
        predicted_char_offset: int | None = ev.get("predicted_char_offset")
        anchor_string: str | None = ev.get("anchor_string") or None

        # section_index from chapter_facts (covers all 626 rolls)
        section_index: int | None = section_index_map.get(rn)
        if section_index is None:
            n_missing_section_index += 1
            warnings.warn(
                f"roll_number={rn} ch={chapter_num}: could not resolve section_index",
                stacklevel=2,
            )

        # --- curator fields (only for predicted ch 1-75) ---
        if has_curator:
            curator_fields = build_curator_fields(rn, curator_map)
        else:
            curator_fields = build_curator_fields(-1, {})  # guaranteed null

        if has_curator and curator_fields["curator_outcome"] is None:
            missing_curator_ch1_75.append(rn)

        # --- banked_at_roll ---
        curator_banked_before = curator_fields["curator_banked_before"]
        if curator_banked_before is not None:
            banked_at_roll: int | None = curator_banked_before
            banked_at_roll_source = "curator"
        else:
            banked_at_roll = pred.get("roll_trigger_cp_threshold")
            banked_at_roll_source = "roll_trigger_cp_threshold"

        # --- chapter acquired perks ---
        chapter_acquired = build_chapter_acquired_perks(chapter_num, obtained_by_chapter)

        # --- outstanding perks with cost > banked ---
        outstanding_filtered = build_outstanding_filtered(
            chapter_num, banked_at_roll, outstanding_by_chapter
        )

        # --- constellations known ---
        constellations_known = constellation_knowledge.get(chapter_num, [])

        # --- outcome stats ---
        outcome = curator_fields["curator_outcome"]
        if outcome == "HIT":
            n_hit += 1
        elif outcome == "MISS":
            n_miss += 1
        else:
            n_unresolved += 1

        out_rolls.append({
            "roll_number": rn,
            "chapter_num": chapter_num,
            "section_index": section_index,
            "predicted_word_position_epub": predicted_word_position_epub,
            "predicted_char_offset": predicted_char_offset,
            "anchor_string": anchor_string,

            "banked_at_roll": banked_at_roll,
            "banked_at_roll_source": banked_at_roll_source,

            "curator_chapter_num": curator_chapter_num,
            "chapter_attribution_disagreement": chapter_attribution_disagreement,

            "curator_outcome": curator_fields["curator_outcome"],
            "curator_perk_name": curator_fields["curator_perk_name"],
            "curator_constellation": curator_fields["curator_constellation"],
            "curator_cost": curator_fields["curator_cost"],
            "curator_free_associated_perks": curator_fields["curator_free_associated_perks"],
            "curator_banked_before": curator_fields["curator_banked_before"],
            "curator_banked_after": curator_fields["curator_banked_after"],

            "chapter_acquired_perks_in_order": chapter_acquired,

            "outstanding_perks_with_cost_gt_banked": outstanding_filtered,

            "constellations_known_by_joe": constellations_known,
        })

    # ---------- assemble payload ----------
    payload = {
        "schema_version": 1,
        "generated_from": {
            "predicted_rolls": str(args.predicted_rolls.relative_to(ROOT)),
            "curator_rolls":   str(args.curator_rolls.relative_to(ROOT)),
            "obtained_perks":  str(args.obtained_perks.relative_to(ROOT)),
            "constellation_knowledge": str(args.constellation_knowledge.relative_to(ROOT)),
            "outstanding_perks":       str(args.outstanding_perks.relative_to(ROOT)),
            "roll_text_evidence":      str(args.roll_text_evidence.relative_to(ROOT)),
        },
        "rolls": out_rolls,
    }

    write_validated_json(args.output, payload, "roll_resolutions")

    # ---------- console summary ----------
    total = len(out_rolls)
    print(f"wrote {args.output.relative_to(ROOT)}: {total} rolls")
    print(f"  curator-HIT:  {n_hit}")
    print(f"  curator-MISS: {n_miss}")
    print(f"  unresolved (ch 76+): {n_unresolved}")
    if n_missing_section_index:
        print(f"  WARNING: {n_missing_section_index} rolls with no section_index resolved")
    else:
        print(f"  section_index resolved: all {total}")

    if missing_curator_ch1_75:
        print(f"\n  NOTE: {len(missing_curator_ch1_75)} predicted ch1-75 rolls missing from curator:")
        for rn in sorted(missing_curator_ch1_75):
            p = next(r for r in out_rolls if r["roll_number"] == rn)
            print(f"    roll_number={rn} ch={p['chapter_num']}")

    # --- 3 sample rolls ---
    print("\n--- Sample rolls ---")

    def _compact(r: dict) -> str:
        lines = [
            f"  roll_number:                     {r['roll_number']}",
            f"  chapter_num:                     {r['chapter_num']}",
            f"  curator_chapter_num:             {r['curator_chapter_num']}",
            f"  chapter_attribution_disagreement:{r['chapter_attribution_disagreement']}",
            f"  section_index:                   {r['section_index']}",
            f"  predicted_word_pos:              {r['predicted_word_position_epub']}",
            f"  predicted_char_offset:           {r['predicted_char_offset']}",
            f"  anchor_string:                   {repr(r['anchor_string'][:60] if r['anchor_string'] else None)}",
            f"  banked_at_roll:                  {r['banked_at_roll']} ({r['banked_at_roll_source']})",
            f"  curator_outcome:                 {r['curator_outcome']}",
            f"  curator_perk_name:               {r['curator_perk_name']}",
            f"  curator_constellation:           {r['curator_constellation']}",
            f"  curator_cost:                    {r['curator_cost']}",
            f"  curator_free_associates:         {r['curator_free_associated_perks']}",
            f"  curator_banked_before:           {r['curator_banked_before']}",
            f"  curator_banked_after:            {r['curator_banked_after']}",
            f"  chapter_acquired_perks:          {[p['name'] for p in r['chapter_acquired_perks_in_order']]}",
            f"  outstanding_gt_banked:           {len(r['outstanding_perks_with_cost_gt_banked'])} perks",
            f"  constellations_known:            {r['constellations_known_by_joe']}",
        ]
        return "\n".join(lines)

    # Sample 1: curator HIT (ch 1-75)
    hit_sample = next(
        (r for r in out_rolls if r["curator_outcome"] == "HIT"
         and int(r["chapter_num"].split(".")[0]) <= 10),
        None,
    )
    if hit_sample:
        print(f"\n[1] Curator HIT (ch {hit_sample['chapter_num']}):")
        print(_compact(hit_sample))

    # Sample 2: curator MISS (ch 1-75)
    miss_sample = next(
        (r for r in out_rolls if r["curator_outcome"] == "MISS"
         and int(r["chapter_num"].split(".")[0]) in range(30, 61)),
        None,
    )
    if miss_sample:
        print(f"\n[2] Curator MISS (ch {miss_sample['chapter_num']}):")
        print(_compact(miss_sample))

    # Sample 3: unresolved (ch 76+)
    unresolved_sample = next(
        (r for r in out_rolls if r["curator_outcome"] is None
         and int(r["chapter_num"].split(".")[0]) >= 90),
        None,
    )
    if unresolved_sample:
        print(f"\n[3] Unresolved (ch {unresolved_sample['chapter_num']}):")
        print(_compact(unresolved_sample))


if __name__ == "__main__":
    main()
