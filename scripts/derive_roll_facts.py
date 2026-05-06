"""Build the canonical roll-attempt stream for downstream visualization.

This is the roll analogue of data/derived/timeline.json: it is the one
derived source `build_chapter_facts.py` should consume for roll attempts.

Inputs:
  - data/derived/rolls.json .............. curator roll log; wins where present
  - data/derived/roll_outcomes.json ...... interpolated fallback for uncovered chapters
  - data/derived/roll_text_evidence.json . predicted prose anchors
  - data/derived/perk_directory.json ..... canonical perk ids/constellations
  - data/derived/outstanding_perks_by_chapter.json  miss-size estimates

Output:
  - data/derived/roll_facts.json (validated)
"""

from __future__ import annotations

import json
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
CURATOR_ROLLS = ROOT / "data" / "derived" / "rolls.json"
ROLL_OUTCOMES = ROOT / "data" / "derived" / "roll_outcomes.json"
EVIDENCE = ROOT / "data" / "derived" / "roll_text_evidence.json"
DIRECTORY = ROOT / "data" / "derived" / "perk_directory.json"
OUTSTANDING = ROOT / "data" / "derived" / "outstanding_perks_by_chapter.json"
OUT = ROOT / "data" / "derived" / "roll_facts.json"


def sort_key_for_chapter(chapter_num: str) -> tuple[int, int]:
    parts = chapter_num.split(".")
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def int_or_none(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_directory_lookup(directory: list[dict]) -> tuple[dict, dict]:
    by_name_jump: dict[tuple[str, str], dict] = {}
    by_name: dict[str, list[dict]] = {}
    for perk in directory:
        name_key = perk["name"].strip().lower()
        by_name_jump[(name_key, perk["jump"].strip().lower())] = perk
        by_name.setdefault(name_key, []).append(perk)
    return by_name_jump, by_name


def lookup_perk(
    by_name_jump: dict[tuple[str, str], dict],
    by_name: dict[str, list[dict]],
    name: str | None,
    jump: str | None = None,
    constellation: str | None = None,
) -> dict | None:
    if not name:
        return None
    name_key = name.strip().lower()
    if jump:
        exact = by_name_jump.get((name_key, jump.strip().lower()))
        if exact:
            return exact
    candidates = by_name.get(name_key, [])
    if constellation:
        filtered = [
            p for p in candidates
            if p.get("constellation") == constellation
        ]
        if len(filtered) == 1:
            return filtered[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def normalized_evidence_kind(ev: dict | None, fallback: str) -> str:
    if ev is None:
        return fallback
    kind = ev.get("evidence_kind") or fallback
    return "silent" if kind == "no_evidence" else kind


def anchor_offset(ev: dict | None) -> int | None:
    if ev and ev.get("matching_events"):
        return ev["matching_events"][0]["anchor_offset"]
    return None


def next_cost_above(available_cp: int | None) -> int | None:
    if available_cp is None:
        return None
    for cost in (100, 200, 300, 400, 600, 800):
        if cost > available_cp:
            return cost
    return available_cp + 100


def miss_cost_estimate(
    outstanding_by_chapter: dict[str, dict[str, list[dict]]],
    chapter_num: str,
    constellation: str | None,
    available_cp: int | None,
) -> int | None:
    if available_cp is None:
        return None
    by_const = outstanding_by_chapter.get(chapter_num, {})
    candidates = by_const.get(constellation, []) if constellation else []
    if not candidates:
        candidates = [perk for perks in by_const.values() for perk in perks]
    costs = [
        int(perk["cost"])
        for perk in candidates
        if perk.get("cost") is not None and int(perk["cost"]) > available_cp
    ]
    return min(costs) if costs else next_cost_above(available_cp)


def perk_meta(
    by_name_jump: dict[tuple[str, str], dict],
    by_name: dict[str, list[dict]],
    raw_perk: dict,
    parent_constellation: str | None,
) -> dict:
    name = raw_perk.get("name") or raw_perk.get("perk_name")
    jump = raw_perk.get("source") or raw_perk.get("jump")
    constellation = raw_perk.get("constellation") or parent_constellation
    directory_meta = lookup_perk(by_name_jump, by_name, name, jump, constellation)
    return {
        "id": directory_meta["id"] if directory_meta else None,
        "name": name,
        "jump": (
            directory_meta["jump"] if directory_meta
            else (jump or "unknown")
        ),
        "constellation": (
            constellation
            or (directory_meta.get("constellation") if directory_meta else None)
        ),
        "cost": (
            int_or_none(raw_perk.get("cost"))
            if raw_perk.get("cost") is not None
            else (directory_meta.get("cost") if directory_meta else None)
        ),
    }


def split_hit_perks(
    by_name_jump: dict[tuple[str, str], dict],
    by_name: dict[str, list[dict]],
    perks: list[dict],
    parent_constellation: str | None,
) -> tuple[dict | None, list[dict]]:
    if not perks:
        return None, []
    paid_perks = [p for p in perks if not p.get("free", False)]
    principal = paid_perks[0] if paid_perks else perks[0]
    paid_meta = perk_meta(by_name_jump, by_name, principal, parent_constellation)
    free_perks = []
    for perk in perks:
        if perk is principal:
            continue
        free_meta = perk_meta(
            by_name_jump,
            by_name,
            perk,
            parent_constellation or paid_meta["constellation"],
        )
        free_perks.append({
            "id": free_meta["id"],
            "name": free_meta["name"],
            "jump": free_meta["jump"],
            "constellation": free_meta["constellation"],
        })
    return paid_meta, free_perks


def roll_base(
    *,
    roll_key: str,
    roll_number: int | None,
    chapter_num: str,
    predicted_chapter_num: str | None,
    source: str,
    source_kind: str,
    outcome: str,
    source_row_index: int,
    ev: dict | None,
) -> dict:
    return {
        "roll_key": roll_key,
        "roll_number": roll_number,
        "chapter_num": chapter_num,
        "predicted_chapter_num": predicted_chapter_num,
        "chapter_attribution_disagreement": (
            predicted_chapter_num is not None and predicted_chapter_num != chapter_num
        ),
        "source": source,
        "source_kind": source_kind,
        "outcome": outcome,
        "predicted_word_position_epub": (
            ev.get("predicted_word_position_epub") if ev else None
        ),
        "predicted_char_offset_in_chapter": (
            ev.get("predicted_char_offset") if ev else None
        ),
        "anchor_char_offset_in_chapter": anchor_offset(ev),
        "evidence_kind": normalized_evidence_kind(
            ev,
            "curator_log" if source == "curator_rolls" else "interpolated",
        ),
        "source_row_index": source_row_index,
    }


def main() -> None:
    curator_doc = json.loads(CURATOR_ROLLS.read_text())
    outcomes_doc = json.loads(ROLL_OUTCOMES.read_text())
    evidence_doc = json.loads(EVIDENCE.read_text())
    directory = json.loads(DIRECTORY.read_text())["perks"]
    outstanding_doc = json.loads(OUTSTANDING.read_text())

    by_name_jump, by_name = build_directory_lookup(directory)
    evidence_by_roll = {e["roll_number"]: e for e in evidence_doc["rolls"]}
    outstanding_by_chapter = {
        c["chapter_num"]: c["before_chapter"]["by_constellation"]
        for c in outstanding_doc["chapters"]
    }

    curator_by_chapter: dict[str, list[tuple[int, dict]]] = {}
    for idx, row in enumerate(curator_doc["rolls"]):
        if row.get("kind") not in {"trigger", "roll", "miss"}:
            continue
        curator_by_chapter.setdefault(row["chapter_num"], []).append((idx, row))

    outcome_by_chapter: dict[str, list[tuple[int, dict]]] = {}
    for idx, row in enumerate(outcomes_doc["rolls"]):
        outcome_by_chapter.setdefault(row["chapter_num"], []).append((idx, row))
    for rows in outcome_by_chapter.values():
        rows.sort(key=lambda item: (
            item[1].get("sequence_in_chapter") or 10**9,
            item[1].get("word_position")
            if item[1].get("word_position") is not None
            else 10**12,
            item[1].get("roll_number") or 10**9,
            item[0],
        ))

    all_chapters = sorted(
        set(curator_by_chapter) | set(outcome_by_chapter),
        key=sort_key_for_chapter,
    )

    rolls: list[dict] = []
    for chapter_num in all_chapters:
        if chapter_num in curator_by_chapter:
            rows = curator_by_chapter[chapter_num]
            total = len(rows)
            for seq, (source_idx, row) in enumerate(rows, start=1):
                roll_number = row.get("roll_number")
                ev = evidence_by_roll.get(roll_number) if roll_number is not None else None
                predicted_chapter_num = ev.get("chapter_num") if ev else None
                outcome = "miss" if row["kind"] == "miss" else "hit"
                source_kind = row["kind"]
                available_cp = int_or_none(row.get("banked_before"))
                banked_after = int_or_none(row.get("banked_after"))
                paid_meta = None
                free_perks: list[dict] = []
                purchased_perk_id = None
                purchased_perk_name = None
                purchased_perk_cost = None
                purchased_perk_jump = None
                constellation = row.get("constellation")
                if outcome == "hit":
                    paid_meta, free_perks = split_hit_perks(
                        by_name_jump,
                        by_name,
                        row.get("perks") or [],
                        constellation,
                    )
                    if paid_meta:
                        purchased_perk_id = paid_meta["id"]
                        purchased_perk_name = paid_meta["name"]
                        purchased_perk_cost = paid_meta["cost"]
                        purchased_perk_jump = paid_meta["jump"]
                        constellation = paid_meta["constellation"] or constellation
                miss_estimate = (
                    miss_cost_estimate(
                        outstanding_by_chapter,
                        chapter_num,
                        constellation,
                        available_cp,
                    )
                    if outcome == "miss"
                    else None
                )
                record = roll_base(
                    roll_key=f"curator:{source_idx:04d}",
                    roll_number=roll_number,
                    chapter_num=chapter_num,
                    predicted_chapter_num=predicted_chapter_num,
                    source="curator_rolls",
                    source_kind=source_kind,
                    outcome=outcome,
                    source_row_index=source_idx,
                    ev=ev,
                )
                record.update({
                    "constellation": constellation,
                    "constellation_revealed": bool(row.get("constellation_revealed", False)),
                    "available_cp": available_cp,
                    "banked_cp_after_roll": banked_after,
                    "purchased_perk_id": purchased_perk_id,
                    "purchased_perk_name": purchased_perk_name,
                    "purchased_perk_cost": purchased_perk_cost,
                    "purchased_perk_jump": purchased_perk_jump,
                    "free_perks": free_perks,
                    "rolled_perk_name": purchased_perk_name,
                    "rolled_perk_cost": (
                        purchased_perk_cost if outcome == "hit" else miss_estimate
                    ),
                    "miss_cost_estimate": miss_estimate,
                    "raw": row.get("raw"),
                    "roll_sequence_in_chapter": seq,
                    "rolls_in_chapter": total,
                })
                rolls.append(record)
            continue

        rows = outcome_by_chapter.get(chapter_num, [])
        total = len(rows)
        for seq, (source_idx, row) in enumerate(rows, start=1):
            roll_number = row.get("roll_number")
            ev = evidence_by_roll.get(roll_number) if roll_number is not None else None
            outcome = "hit" if row.get("outcome") == "hit" else "miss"
            raw_perk = row.get("perk")
            paid_meta = (
                perk_meta(by_name_jump, by_name, raw_perk, raw_perk.get("constellation"))
                if raw_perk
                else None
            )
            free_perks = []
            if paid_meta:
                for raw_free in row.get("free_perks") or []:
                    free_meta = perk_meta(
                        by_name_jump,
                        by_name,
                        raw_free,
                        paid_meta["constellation"],
                    )
                    free_perks.append({
                        "id": free_meta["id"],
                        "name": free_meta["name"],
                        "jump": free_meta["jump"],
                        "constellation": free_meta["constellation"],
                    })
            available_cp = int_or_none(row.get("cp_threshold"))
            constellation = paid_meta["constellation"] if paid_meta else None
            miss_estimate = (
                miss_cost_estimate(
                    outstanding_by_chapter,
                    chapter_num,
                    constellation,
                    available_cp,
                )
                if outcome == "miss"
                else None
            )
            record = roll_base(
                roll_key=f"interpolated:{source_idx:04d}",
                roll_number=roll_number,
                chapter_num=chapter_num,
                predicted_chapter_num=ev.get("chapter_num") if ev else chapter_num,
                source="roll_outcomes",
                source_kind="interpolated",
                outcome=outcome,
                source_row_index=source_idx,
                ev=ev,
            )
            if record["predicted_word_position_epub"] is None:
                record["predicted_word_position_epub"] = row.get("word_position")
            record["evidence_kind"] = (
                "synthetic" if row.get("source") == "synthetic"
                else record["evidence_kind"]
            )
            record.update({
                "constellation": constellation,
                "constellation_revealed": False,
                "available_cp": available_cp,
                "banked_cp_after_roll": None,
                "purchased_perk_id": paid_meta["id"] if paid_meta else None,
                "purchased_perk_name": paid_meta["name"] if paid_meta else None,
                "purchased_perk_cost": paid_meta["cost"] if paid_meta else None,
                "purchased_perk_jump": paid_meta["jump"] if paid_meta else None,
                "free_perks": free_perks,
                "rolled_perk_name": paid_meta["name"] if paid_meta else None,
                "rolled_perk_cost": (
                    paid_meta["cost"] if paid_meta else miss_estimate
                ),
                "miss_cost_estimate": miss_estimate,
                "raw": None,
                "roll_sequence_in_chapter": seq,
                "rolls_in_chapter": total,
            })
            rolls.append(record)

    payload = {
        "schema_version": 1,
        "_source": (
            "Merged from data/derived/rolls.json and "
            "data/derived/roll_outcomes.json with perk/evidence enrichment."
        ),
        "_method": (
            "Use every trigger/roll/miss row from the curator roll log as "
            "authoritative for chapters it covers, preserving source order and "
            "duplicate roll numbers. For chapters without curator rows, use "
            "roll_outcomes.json as an interpolated fallback. Free perks attach "
            "to the paid hit and do not consume separate roll slots."
        ),
        "_caveat": (
            "Curator rows are the trusted source. roll_outcomes rows are "
            "placeholder interpolation until text-backed or manually curated "
            "roll attempts exist for later chapters."
        ),
        "_counts": {
            "rolls_emitted": len(rolls),
            "curator_rows": sum(1 for r in rolls if r["source"] == "curator_rolls"),
            "interpolated_rows": sum(1 for r in rolls if r["source"] == "roll_outcomes"),
            "hits": sum(1 for r in rolls if r["outcome"] == "hit"),
            "misses": sum(1 for r in rolls if r["outcome"] == "miss"),
            "triggers": sum(1 for r in rolls if r["source_kind"] == "trigger"),
            "free_perks": sum(len(r["free_perks"]) for r in rolls),
        },
        "rolls": rolls,
    }

    write_validated_json(OUT, payload, "roll_facts")

    counts = payload["_counts"]
    print(f"wrote {OUT.relative_to(ROOT)}: {counts['rolls_emitted']} rows")
    print(
        f"  curator: {counts['curator_rows']}, "
        f"interpolated: {counts['interpolated_rows']}"
    )
    print(
        f"  hits: {counts['hits']}, misses: {counts['misses']}, "
        f"free perks: {counts['free_perks']}"
    )


if __name__ == "__main__":
    main()
