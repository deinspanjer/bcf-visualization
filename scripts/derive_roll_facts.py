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

import datetime as _dt
import json
from pathlib import Path

from _common import write_validated_json
from multi_grab import (
    load_overrides as load_multi_grab_overrides,
    merge_paid_units,
    unit_principal_cost,
    unit_total_cost,
)
from predict_rolls import _load_cp_words_per_chapter
from regime_simulator import (
    REGIMES,
    ShadowState,
    _accumulate_x100,
    load_regime_transitions,
    regime_for_chapter,
    regimes_for_chapter,
)
from roll_scheduler import (
    HitInput,
    SlotInput,
    diagnose_infeasible,
    schedule_chapter,
)

ROOT = Path(__file__).resolve().parent.parent
CURATOR_ROLLS = ROOT / "data" / "derived" / "rolls.json"
ROLL_OUTCOMES = ROOT / "data" / "derived" / "roll_outcomes.json"
PREDICTED_ROLLS = ROOT / "data" / "derived" / "predicted_rolls.json"
OBTAINED_PERKS = ROOT / "data" / "derived" / "obtained_perks.json"
CHAPTERS_JSON = ROOT / "data" / "derived" / "chapters.json"
EVIDENCE = ROOT / "data" / "derived" / "roll_text_evidence.json"
DIRECTORY = ROOT / "data" / "derived" / "perk_directory.json"
OUTSTANDING = ROOT / "data" / "derived" / "outstanding_perks_by_chapter.json"
ROLL_OVERRIDES = ROOT / "data" / "manual" / "roll_overrides.json"
OUT = ROOT / "data" / "derived" / "roll_facts.json"
VALIDATION_OUT = ROOT / "data" / "derived" / "roll_validation.json"


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
) -> tuple[dict | None, list[dict], list[dict]]:
    """Returns (principal_meta, purchased_perks_array, free_perks_array).

    `purchased_perks_array` contains every paid perk (multi-grab) as
    `{name, cost, free}` dicts (free always False here for paid). The
    principal is the first paid perk (preserves source order).
    """
    if not perks:
        return None, [], []
    paid_perks = [p for p in perks if not p.get("free", False)]
    free_perks_raw = [p for p in perks if p.get("free", False)]
    if not paid_perks:
        # All perks are free: still return a principal for legacy fields.
        principal = perks[0]
        principal_meta = perk_meta(by_name_jump, by_name, principal, parent_constellation)
        free_perks: list[dict] = []
        for perk in perks[1:]:
            free_meta = perk_meta(
                by_name_jump, by_name, perk,
                parent_constellation or principal_meta["constellation"],
            )
            free_perks.append({
                "id": free_meta["id"],
                "name": free_meta["name"],
                "jump": free_meta["jump"],
                "constellation": free_meta["constellation"],
            })
        return principal_meta, [], free_perks
    principal = paid_perks[0]
    principal_meta = perk_meta(by_name_jump, by_name, principal, parent_constellation)
    purchased_perks: list[dict] = []
    for p in paid_perks:
        meta = perk_meta(by_name_jump, by_name, p, parent_constellation)
        purchased_perks.append({
            "name": meta["name"] or p.get("name") or p.get("perk_name"),
            "cost": int(meta["cost"]) if meta["cost"] is not None else int(p.get("cost") or 0),
            "free": False,
        })
    free_perks: list[dict] = []
    for perk in free_perks_raw:
        free_meta = perk_meta(
            by_name_jump, by_name, perk,
            parent_constellation or principal_meta["constellation"],
        )
        free_perks.append({
            "id": free_meta["id"],
            "name": free_meta["name"],
            "jump": free_meta["jump"],
            "constellation": free_meta["constellation"],
        })
    return principal_meta, purchased_perks, free_perks


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


def _build_scheduler_inputs() -> dict[str, dict]:
    """Build per-chapter scheduler inputs: slots, hits, banked_cp_in,
    shadow_state, chapter_words, chapter_word_start.

    Walks chapters in canonical order. For each chapter we compute the
    starting banked CP and shadow state by replaying earlier chapters'
    "no-hits" simulation (hits are scheduler-decided per chapter, but for
    the inter-chapter ledger we use the SAME inputs predict_rolls used:
    proportional-spread hits, since obtained_perks gives us the hit
    counts and costs; even spread inside a chapter doesn't change the
    chapter-end banked CP if all hits land in-chapter and the scheduler
    is consistent).

    We use obtained_perks (paid only) as the canonical hit list per
    chapter; their order within a chapter is `epub_sequence` ascending.
    """
    chapters_doc = json.loads(CHAPTERS_JSON.read_text())
    perks_doc = json.loads(OBTAINED_PERKS.read_text())
    pred_doc = json.loads(PREDICTED_ROLLS.read_text())
    transitions = load_regime_transitions()
    multi_overrides = load_multi_grab_overrides()

    chapters = sorted(chapters_doc["chapters"], key=lambda c: tuple(c["sort_key"]))
    full_titles = {c["chapter_num"]: c["full_title"] for c in chapters}
    cp_words_by_title = _load_cp_words_per_chapter()
    chapter_words: dict[str, int] = {
        c["chapter_num"]: int(cp_words_by_title.get(c["full_title"], 0))
        for c in chapters
    }

    # Multi-grab merging: paid perks sharing (chapter, jump, epub_seq)
    # belong to the same Forge roll. Each merged unit produces ONE hit.
    perks_sorted = sorted(perks_doc["perks"], key=lambda p: p.get("epub_sequence", 0))
    units, _stats = merge_paid_units(perks_sorted, multi_overrides)
    units_by_chapter: dict[str, list[dict]] = {}
    for unit in units:
        units_by_chapter.setdefault(unit["chapter_num"], []).append(unit)

    # Group predicted rolls by chapter; word_position is story-global.
    pred_by_chapter: dict[str, list[dict]] = {}
    for r in pred_doc["predicted"]:
        pred_by_chapter.setdefault(r["chapter_num"], []).append(r)

    # Compute per-chapter starting word offsets (cumulative CP-earning words).
    chapter_word_start: dict[str, int] = {}
    cum = 0
    for c in chapters:
        chapter_word_start[c["chapter_num"]] = cum
        cum += chapter_words[c["chapter_num"]]

    # Walk to compute banked_cp_in / shadow_state at each chapter start.
    banked_in_per_chapter: dict[str, int] = {}
    shadow_in_per_chapter: dict[str, ShadowState] = {}
    segments_per_chapter: dict[str, list] = {}
    banked_x100 = 0
    shadow = ShadowState()
    from regime_simulator import shadow_words as _shadow_words
    for c in chapters:
        cn = c["chapter_num"]
        banked_in_per_chapter[cn] = banked_x100 // 100
        shadow_in_per_chapter[cn] = shadow.copy()
        # Walk this chapter's words at its regime(s), applying hits for
        # shadow bookkeeping. Hit positions: even-spread of merged units.
        words = chapter_words[cn]
        ch_units = units_by_chapter.get(cn, [])
        # Resolve regime segments for this chapter (mid-chapter transitions).
        segs = regimes_for_chapter(
            cn, transitions,
            [u["paid"][0] for u in ch_units] if ch_units else [],
            words,
        )
        segments_per_chapter[cn] = segs
        # Hit events: one per merged unit, position by even spread.
        if ch_units and words > 0:
            slot_w = words / len(ch_units)
            hit_events = sorted([
                (
                    int((i + 0.5) * slot_w),
                    sum(int(p.get("cost") or 0) for p in u["paid"]),
                    max(int(p.get("cost") or 0) for p in u["paid"]),
                )
                for i, u in enumerate(ch_units)
            ])
        else:
            hit_events = []
        last = 0
        seg_idx = 0
        current_regime = segs[seg_idx].regime

        def _walk(target: int) -> None:
            nonlocal banked_x100, last, seg_idx, current_regime
            while last < target:
                seg_end = segs[seg_idx].end_word_local
                if seg_end is None or seg_end >= target:
                    step = target - last
                    if step > 0:
                        banked_x100 = _accumulate_x100(
                            step, current_regime, banked_x100, shadow,
                        )
                    last = target
                    return
                step = seg_end - last
                if step > 0:
                    banked_x100 = _accumulate_x100(
                        step, current_regime, banked_x100, shadow,
                    )
                last = seg_end
                seg_idx += 1
                current_regime = segs[seg_idx].regime

        for hw, total_cost, principal_cost in hit_events:
            _walk(hw)
            banked_x100 -= total_cost * 100
            if banked_x100 < 0:
                banked_x100 = 0
            sw = _shadow_words(principal_cost, current_regime)
            if sw:
                shadow.remaining += sw
        if words > last:
            _walk(words)

    # Build scheduler inputs per chapter.
    out: dict[str, dict] = {}
    for c in chapters:
        cn = c["chapter_num"]
        words = chapter_words[cn]
        ws_global = chapter_word_start[cn]
        preds = pred_by_chapter.get(cn, [])
        # Slot list (chapter-local word_position).
        slots = [
            SlotInput(
                word_position=max(0, int(r["word_position"]) - ws_global),
                cp_threshold=int(r.get("cp_threshold", REGIMES[regime_for_chapter(cn)]["cp_per_roll"])),
                source="predicted",
            )
            for r in preds
        ]
        # Hits = merged paid units in narrative order.
        ch_units = units_by_chapter.get(cn, [])
        hits = [
            HitInput(
                cost=sum(int(p.get("cost") or 0) for p in u["paid"]),
                perk=u["paid"][0],
                paid_perks=list(u["paid"]),
                free_perks=list(u["free_perks"]),
            )
            for u in ch_units
        ]
        # If K > N, synthesize extra slots with even spread (matching
        # derive_roll_outcomes.py).
        n, k = len(slots), len(hits)
        if k > n and words > 0:
            extra = k - n
            # Evenly spaced at (i+1)/(extra+1) of words; collision-avoid
            # against existing slot positions.
            existing = {s.word_position for s in slots}
            for i in range(extra):
                pos = max(1, int(words * (i + 1) / (extra + 1)))
                while pos in existing:
                    pos += 1
                existing.add(pos)
                slots.append(SlotInput(
                    word_position=pos,
                    cp_threshold=REGIMES[regime_for_chapter(cn)]["cp_per_roll"],
                    source="synthetic",
                ))
            slots.sort(key=lambda s: s.word_position)
        out[cn] = {
            "slots": slots,
            "hits": hits,
            "chapter_words": words,
            "chapter_word_start": ws_global,
            "banked_cp_in": banked_in_per_chapter.get(cn, 0),
            "shadow_in": shadow_in_per_chapter.get(cn, ShadowState()),
            "segments": segments_per_chapter.get(cn),
        }
    return out


def _norm_name(s: str | None) -> str:
    return (s or "").strip().lower()


def _restructure_curator_rows(
    chapter_num: str,
    curator_rows: list[tuple[int, dict]],
    override: dict,
) -> list[dict]:
    """Restructure curator rows for an override-covered chapter.

    Returns a list of "synthetic curator-equivalent" row dicts in narrative
    order. Each row dict has the same shape as a curator row (kind,
    perks, banked_before, banked_after, constellation, raw, roll_number)
    plus extra keys ``_source_idx`` (carry-over) and
    ``_override_origin`` (set on rebuilt hit rows so downstream code can
    tell they came from the override).

    Algorithm:
      1. Walk curator rows; misses pass through unchanged.
      2. For each curator hit row, determine which override-rolls cover
         its perks (override roll perks ⊆ curator row's combined perks).
         Replace the curator hit row with the matching override-rolls,
         in override order. Walk banked_before/after across the
         override-rolls using the curator hit row's banked_before as the
         starting CP for the first override-roll, debiting paid costs.
      3. Sanity: the last override-roll's banked_after for the chapter
         should match curator's recorded banked_after for the chapter
         (last curator hit row that maps to a tail override-roll).
         Mismatch -> warn.
    """
    override_rolls = override.get("rolls") or []
    # Normalize override rolls to (paid_names_set, all_names_in_order_with_meta)
    # We need cost info, but at this point we don't have it -- the caller
    # passes in curator perks (which carry cost). For each override roll,
    # we'll match by name against the host curator hit row's perks.

    # Build name -> perk dict lookup from ALL curator hit rows in this
    # chapter (so override names always resolve).
    name_to_perk: dict[str, dict] = {}
    for _, row in curator_rows:
        for p in row.get("perks") or []:
            nm = _norm_name(p.get("name"))
            if nm and nm not in name_to_perk:
                name_to_perk[nm] = p

    # Validate every override-roll perk is present in this chapter.
    for roll_idx, name_list in enumerate(override_rolls):
        for nm in name_list:
            if _norm_name(nm) not in name_to_perk:
                raise ValueError(
                    f"multi_grab override for ch {chapter_num} roll #{roll_idx} "
                    f"references {nm!r} but no curator hit row in the chapter "
                    f"contains a perk by that name "
                    f"(known: {sorted(name_to_perk)})"
                )

    # For each override-roll, find which curator hit row "hosts" it
    # (i.e. the curator row whose perks superset all of the override-roll's
    # perks). If no single host covers it, fall back to the FIRST host
    # that covers any of its perks.
    def _curator_hit_index_for_override(
        ov_names: list[str], curator_rows: list[tuple[int, dict]]
    ) -> int:
        ov_set = {_norm_name(n) for n in ov_names}
        # First pass: full superset.
        for i, (_, row) in enumerate(curator_rows):
            if row.get("kind") == "miss":
                continue
            row_set = {_norm_name((p.get("name") or "")) for p in row.get("perks") or []}
            if ov_set.issubset(row_set):
                return i
        # Fallback: any overlap.
        for i, (_, row) in enumerate(curator_rows):
            if row.get("kind") == "miss":
                continue
            row_set = {_norm_name((p.get("name") or "")) for p in row.get("perks") or []}
            if ov_set & row_set:
                return i
        raise ValueError(
            f"multi_grab override for ch {chapter_num}: roll {ov_names!r} "
            f"could not be matched to any curator hit row"
        )

    # Map override-roll index -> host curator row index.
    override_to_host: list[int] = [
        _curator_hit_index_for_override(name_list, curator_rows)
        for name_list in override_rolls
    ]

    # For each curator row, build the list of override-roll indices it hosts.
    host_to_overrides: dict[int, list[int]] = {}
    for ov_idx, host_idx in enumerate(override_to_host):
        host_to_overrides.setdefault(host_idx, []).append(ov_idx)

    # Sanity: every curator hit row should be hosted by at least one
    # override-roll. (If not, the override silently drops perks; warn.)
    for i, (_, row) in enumerate(curator_rows):
        if row.get("kind") == "miss":
            continue
        if i not in host_to_overrides:
            print(
                f"  derive_roll_facts: ch {chapter_num} override does not "
                f"cover curator hit row #{i} (perks: "
                f"{[(p.get('name')) for p in row.get('perks') or []]})"
            )

    # Walk curator rows; emit misses unchanged, replace each hit with the
    # override-rolls it hosts. Walk banked across the override-rolls using
    # the curator hit row's banked_before as the entry CP.
    out_rows: list[dict] = []
    for i, (source_idx, row) in enumerate(curator_rows):
        if row.get("kind") == "miss":
            # Pass through (preserve curator banked_before/after).
            out_rows.append({
                "_source_idx": source_idx,
                "_override_origin": None,
                "kind": "miss",
                "perks": [],
                "banked_before": row.get("banked_before"),
                "banked_after": row.get("banked_after"),
                "constellation": row.get("constellation"),
                "constellation_revealed": row.get("constellation_revealed", False),
                "roll_number": row.get("roll_number"),
                "raw": row.get("raw"),
            })
            continue

        ov_indices = host_to_overrides.get(i, [])
        if not ov_indices:
            # Override doesn't cover this curator hit row -- emit it
            # untouched as a fallback.
            out_rows.append({
                "_source_idx": source_idx,
                "_override_origin": None,
                "kind": row.get("kind"),
                "perks": list(row.get("perks") or []),
                "banked_before": row.get("banked_before"),
                "banked_after": row.get("banked_after"),
                "constellation": row.get("constellation"),
                "constellation_revealed": row.get("constellation_revealed", False),
                "roll_number": row.get("roll_number"),
                "raw": row.get("raw"),
            })
            continue

        host_before = int_or_none(row.get("banked_before"))
        host_after = int_or_none(row.get("banked_after"))
        running = host_before if host_before is not None else 0
        for j, ov_idx in enumerate(ov_indices):
            name_list = override_rolls[ov_idx]
            ov_perks: list[dict] = []
            ov_cost_total = 0
            for nm in name_list:
                src = name_to_perk[_norm_name(nm)]
                ov_perks.append({
                    "name": src.get("name"),
                    "source": src.get("source"),
                    "cost": src.get("cost", 0),
                    "free": bool(src.get("free", False)),
                    "constellation": src.get("constellation"),
                })
                if not src.get("free", False):
                    ov_cost_total += int(src.get("cost") or 0)
            before = running
            after = before - ov_cost_total
            running = after
            # Last override-roll for this host inherits curator's roll_number /
            # raw / constellation_revealed; earlier ones get None roll_number
            # so downstream evidence lookup doesn't double-attach.
            is_last_for_host = (j == len(ov_indices) - 1)
            out_rows.append({
                "_source_idx": source_idx,
                "_override_origin": ov_idx,
                "kind": "roll",
                "perks": ov_perks,
                "banked_before": before,
                "banked_after": after,
                "constellation": (
                    ov_perks[0].get("constellation") if ov_perks
                    else row.get("constellation")
                ),
                "constellation_revealed": (
                    row.get("constellation_revealed", False)
                    if is_last_for_host else False
                ),
                "roll_number": (
                    row.get("roll_number") if is_last_for_host else None
                ),
                "raw": row.get("raw") if is_last_for_host else None,
            })
        # Sanity: final running balance should equal host_after for the
        # last override hosted by this curator row.
        if host_after is not None and running != host_after:
            print(
                f"  derive_roll_facts: ch {chapter_num} override walk "
                f"banked_after mismatch for curator hit row #{i}: "
                f"override={running} curator={host_after} (rolls "
                f"{[override_rolls[k] for k in ov_indices]})"
            )

    return out_rows


def _apply_overrides(rolls: list[dict], overrides_doc: dict) -> int:
    """Apply hand-curation overrides as a final pass. Returns count."""
    roll_overrides = overrides_doc.get("roll_overrides") or {}
    applied = 0
    for r in rolls:
        patch = roll_overrides.get(r.get("roll_key"))
        if not patch:
            continue
        for k, v in patch.items():
            if k.startswith("_"):
                continue
            r[k] = v
        r["slot_source"] = "override"
        applied += 1
    return applied


def main() -> None:
    curator_doc = json.loads(CURATOR_ROLLS.read_text())
    outcomes_doc = json.loads(ROLL_OUTCOMES.read_text())
    evidence_doc = json.loads(EVIDENCE.read_text())
    directory = json.loads(DIRECTORY.read_text())["perks"]
    outstanding_doc = json.loads(OUTSTANDING.read_text())
    overrides_doc: dict = {}
    if ROLL_OVERRIDES.exists():
        overrides_doc = json.loads(ROLL_OVERRIDES.read_text())

    multi_overrides_doc = load_multi_grab_overrides()
    multi_overrides = multi_overrides_doc.get("chapter_roll_overrides") or {}

    curator_covered: set[str] = set()
    for row in curator_doc["rolls"]:
        if row.get("kind") in {"trigger", "roll", "miss"}:
            curator_covered.add(row["chapter_num"])

    # ---- scheduler pass: per-chapter feasibility + slot assignment ----
    scheduler_inputs = _build_scheduler_inputs()
    # Build a quick lookup of word offset (chapter-local) per slot index
    # per chapter, plus chapter_word_start for cumulative offsets.
    chapter_word_start_global = {
        cn: inp["chapter_word_start"] for cn, inp in scheduler_inputs.items()
    }
    scheduler_results: dict = {}
    infeasible_records: list[dict] = []
    for cn, inp in scheduler_inputs.items():
        # Apply chapter-level overrides (e.g., banked_cp_in nudge).
        ch_override = (overrides_doc.get("chapter_overrides") or {}).get(cn) or {}
        banked_in = (
            int(ch_override["banked_cp_in"])
            if "banked_cp_in" in ch_override
            else inp["banked_cp_in"]
        )
        result = schedule_chapter(
            cn,
            inp["slots"],
            inp["hits"],
            banked_cp_in=banked_in,
            shadow_in=inp["shadow_in"],
            chapter_words=inp["chapter_words"],
            segments=inp.get("segments"),
        )
        if not result.feasible:
            diag, expl = diagnose_infeasible(
                cn, inp["slots"], inp["hits"],
                banked_cp_in=banked_in,
                shadow_in=inp["shadow_in"],
                chapter_words=inp["chapter_words"],
                segments=inp.get("segments"),
            )
            result.diagnostic = diag
            result.explanation = expl
            # Curator-covered chapters with infeasible solver result are
            # NOT a hard pipeline error — curator is canonical there.
            # They surface as divergences instead.
            if cn not in curator_covered:
                infeasible_records.append({
                    "chapter_num": cn,
                    "banked_cp_in": banked_in,
                    "predicted_slots": [
                        {"word_position": s.word_position,
                         "cp_threshold": s.cp_threshold,
                         "source": s.source}
                        for s in inp["slots"]
                    ],
                    "recorded_hits": [
                        {
                            "cost": h.cost,
                            "names": [
                                (p.get("perk_name") or p.get("name"))
                                for p in (h.paid_perks or ([h.perk] if h.perk else []))
                            ],
                        }
                        for h in inp["hits"]
                    ],
                    "diagnostic": diag,
                    "explanation": expl,
                })
        scheduler_results[cn] = result

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
    curator_solver_divergences: list[dict] = []
    for chapter_num in all_chapters:
        sched = scheduler_results.get(chapter_num)
        if chapter_num in curator_by_chapter:
            rows_raw = curator_by_chapter[chapter_num]
            chapter_override = multi_overrides.get(chapter_num)
            if chapter_override is not None:
                # Override beats curator: rebuild rows from override.
                synthetic = _restructure_curator_rows(
                    chapter_num, rows_raw, chapter_override,
                )
                # Re-pack into (source_idx, row) tuples; source_idx points
                # at the original curator row (kept stable for evidence /
                # roll_key generation). Emit a unique roll_key per synthetic
                # row so override-split rows don't collide.
                rows = [
                    (s["_source_idx"], s) for s in synthetic
                ]
            else:
                rows = rows_raw
            total = len(rows)
            # Cross-check: compare curator outcomes vs scheduler decision.
            if sched and sched.feasible:
                curator_outcomes = [
                    "hit" if r[1]["kind"] != "miss" else "miss"
                    for r in rows
                ]
                solver_outcomes = [a.outcome for a in sched.assignments]
                # Trim the solver's decision to the curator-recorded count
                # (curator may merge/duplicate roll_numbers; align by length
                # and emit a soft warning if they differ).
                if (
                    len(solver_outcomes) != len(curator_outcomes)
                    or solver_outcomes != curator_outcomes
                ):
                    curator_solver_divergences.append({
                        "chapter_num": chapter_num,
                        "curator_outcomes": curator_outcomes,
                        "solver_outcomes": solver_outcomes,
                        "solver_slack": sched.slack,
                    })
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
                purchased_perks: list[dict] = []
                purchased_perk_cost_total: int | None = None
                purchased_perk_id = None
                purchased_perk_jump = None
                constellation = row.get("constellation")
                if outcome == "hit":
                    paid_meta, purchased_perks, free_perks = split_hit_perks(
                        by_name_jump,
                        by_name,
                        row.get("perks") or [],
                        constellation,
                    )
                    if paid_meta:
                        purchased_perk_id = paid_meta["id"]
                        purchased_perk_jump = paid_meta["jump"]
                        constellation = paid_meta["constellation"] or constellation
                    purchased_perk_cost_total = sum(
                        int(p["cost"]) for p in purchased_perks
                        if not p.get("free", False)
                    )
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
                ov_origin = row.get("_override_origin") if isinstance(row, dict) else None
                if ov_origin is not None:
                    roll_key = f"curator:{source_idx:04d}.{ov_origin}"
                else:
                    roll_key = f"curator:{source_idx:04d}"
                record = roll_base(
                    roll_key=roll_key,
                    roll_number=roll_number,
                    chapter_num=chapter_num,
                    predicted_chapter_num=predicted_chapter_num,
                    source="curator_rolls",
                    source_kind=source_kind,
                    outcome=outcome,
                    source_row_index=source_idx,
                    ev=ev,
                )
                # Curator's predicted_word_position_epub is in EPUB-words,
                # whereas the simulator's chapter_word_start is in
                # CP-earning words; these aren't directly subtractable.
                # Leave both None for curator rows; ordering uses
                # roll_sequence_in_chapter.
                word_position_local = None
                cum_word = None
                principal_name = paid_meta["name"] if paid_meta else None
                record.update({
                    "constellation": constellation,
                    "constellation_revealed": bool(row.get("constellation_revealed", False)),
                    "available_cp": available_cp,
                    "banked_cp_after_roll": banked_after,
                    "purchased_perk_id": purchased_perk_id,
                    "purchased_perks": purchased_perks,
                    "purchased_perk_cost_total": purchased_perk_cost_total,
                    "purchased_perk_jump": purchased_perk_jump,
                    "free_perks": free_perks,
                    "rolled_perk_name": principal_name,
                    "rolled_perk_cost": (
                        purchased_perk_cost_total if outcome == "hit" else miss_estimate
                    ),
                    "miss_cost_estimate": miss_estimate,
                    "raw": row.get("raw"),
                    "roll_sequence_in_chapter": seq,
                    "rolls_in_chapter": total,
                    "slot_source": (
                        "curator+override" if ov_origin is not None
                        else "curator"
                    ),
                    "word_position": word_position_local,
                    "cumulative_word_offset": (
                        int(cum_word) if cum_word is not None else None
                    ),
                })
                rolls.append(record)
            continue

        rows = outcome_by_chapter.get(chapter_num, [])
        total = len(rows)
        sched_inp = scheduler_inputs.get(chapter_num)
        sched_assignments = (
            sched.assignments if sched and sched.feasible else None
        )
        # Build a fast lookup: which "hit_index" (in the scheduler's hit
        # list, which is paid-acquisitions in epub_sequence) corresponds
        # to each slot.
        for seq, (source_idx, row) in enumerate(rows, start=1):
            roll_number = row.get("roll_number")
            ev = evidence_by_roll.get(roll_number) if roll_number is not None else None
            assignment = (
                sched_assignments[seq - 1]
                if sched_assignments and seq - 1 < len(sched_assignments)
                else None
            )
            if assignment is not None:
                outcome = assignment.outcome
            else:
                outcome = "hit" if row.get("outcome") == "hit" else "miss"
            # Pick perk source:
            # - If the scheduler assigned a hit, use the paid_perks list
            #   from sched_inp.hits[assignment.hit_index].
            # - Otherwise (no scheduler / miss), keep the row's perk
            #   metadata if it exists (so manual data is preserved).
            raw_paid_list: list[dict] = []
            free_perks_payload: list[dict] = []
            if (
                outcome == "hit"
                and assignment is not None
                and assignment.hit_index is not None
                and sched_inp is not None
            ):
                hit = sched_inp["hits"][assignment.hit_index]
                raw_paid_list = list(hit.paid_perks or ([hit.perk] if hit.perk else []))
                free_perks_payload = hit.free_perks or []
            elif outcome == "hit":
                row_paid = row.get("paid_perks") or []
                if row_paid:
                    raw_paid_list = list(row_paid)
                elif row.get("perk"):
                    raw_paid_list = [row["perk"]]
                free_perks_payload = row.get("free_perks") or []
            principal_raw = raw_paid_list[0] if raw_paid_list else None
            paid_meta = (
                perk_meta(
                    by_name_jump, by_name, principal_raw,
                    principal_raw.get("constellation") if principal_raw else None,
                )
                if principal_raw
                else None
            )
            purchased_perks: list[dict] = []
            for p in raw_paid_list:
                pm = perk_meta(by_name_jump, by_name, p, p.get("constellation"))
                purchased_perks.append({
                    "name": pm["name"] or p.get("perk_name") or p.get("name"),
                    "cost": int(pm["cost"]) if pm["cost"] is not None else int(p.get("cost") or 0),
                    "free": False,
                })
            purchased_perk_cost_total = (
                sum(int(p["cost"]) for p in purchased_perks)
                if purchased_perks else None
            )
            free_perks = []
            if paid_meta:
                for raw_free in free_perks_payload:
                    # raw_free dicts come from obtained_perks (perk_name) or
                    # roll_outcomes (name); perk_meta handles both.
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
            if assignment is not None:
                available_cp = assignment.available_cp
                banked_cp_after = assignment.banked_cp_after_roll
            else:
                available_cp = int_or_none(row.get("available_cp"))
                if available_cp is None:
                    available_cp = int_or_none(row.get("cp_threshold"))
                banked_cp_after = int_or_none(row.get("banked_cp_after_roll"))
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
            ch_start = chapter_word_start_global.get(chapter_num, 0)
            # Prefer the scheduler's slot word_position (uniformly
            # chapter-local). Fall back to the row's word_position only
            # if no scheduler input exists; treat that as chapter-local
            # too if it's clearly small (synthetic) and as cumulative
            # otherwise.
            if sched_inp is not None and seq - 1 < len(sched_inp["slots"]):
                word_position_local = sched_inp["slots"][seq - 1].word_position
                cum_word = ch_start + word_position_local
            else:
                row_wp = row.get("word_position")
                if row_wp is None:
                    word_position_local = None
                    cum_word = None
                elif int(row_wp) >= ch_start:
                    cum_word = int(row_wp)
                    word_position_local = cum_word - ch_start
                else:
                    word_position_local = int(row_wp)
                    cum_word = ch_start + word_position_local
            record.update({
                "constellation": constellation,
                "constellation_revealed": False,
                "available_cp": available_cp,
                "banked_cp_after_roll": banked_cp_after,
                "purchased_perk_id": paid_meta["id"] if paid_meta else None,
                "purchased_perks": purchased_perks,
                "purchased_perk_cost_total": purchased_perk_cost_total,
                "purchased_perk_jump": paid_meta["jump"] if paid_meta else None,
                "free_perks": free_perks,
                "rolled_perk_name": paid_meta["name"] if paid_meta else None,
                "rolled_perk_cost": (
                    purchased_perk_cost_total if paid_meta else miss_estimate
                ),
                "miss_cost_estimate": miss_estimate,
                "raw": None,
                "roll_sequence_in_chapter": seq,
                "rolls_in_chapter": total,
                "slot_source": "solver" if assignment is not None else "interpolated",
                "word_position": word_position_local,
                "cumulative_word_offset": cum_word,
            })
            rolls.append(record)

    # ---- apply overrides as a final pass ----
    overrides_applied = _apply_overrides(rolls, overrides_doc)

    payload = {
        "schema_version": 1,
        "_source": (
            "Merged from data/derived/rolls.json and "
            "data/derived/roll_outcomes.json with perk/evidence enrichment."
        ),
        "_method": (
            "Use every trigger/roll/miss row from the curator roll log as "
            "authoritative for chapters it covers, preserving source order and "
            "duplicate roll numbers. For chapters without curator rows, the "
            "scheduler (scripts/roll_scheduler.py) decides which predicted "
            "slots are hits via latest-feasible backtracking. Free perks "
            "attach to the paid hit and do not consume separate roll slots. "
            "Manual roll/chapter overrides land last (slot_source='override')."
        ),
        "_caveat": (
            "Curator rows are the trusted source. Solver rows are "
            "constraint-satisfaction reconstructions; ambiguous chapters "
            "and infeasible chapters are listed in roll_validation.json."
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

    # ---- write validation report ----
    ambiguous = [
        {
            "chapter_num": cn,
            "feasible_assignment_count": r.ambiguity,
            "slack": r.slack,
        }
        for cn, r in scheduler_results.items()
        if r.feasible and r.ambiguity > 1
    ]
    validation_payload = {
        "_generated": _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds"),
        "_source": "scripts/derive_roll_facts.py",
        "summary": {
            "chapters_total": len(scheduler_results),
            "feasible": sum(1 for r in scheduler_results.values() if r.feasible),
            "infeasible": len(infeasible_records),
            "curator_divergences": len(curator_solver_divergences),
            "ambiguous": len(ambiguous),
            "overrides_applied": overrides_applied,
        },
        "infeasible": infeasible_records,
        "curator_solver_divergences": curator_solver_divergences,
        "ambiguous_chapters": ambiguous,
    }
    VALIDATION_OUT.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_OUT.write_text(
        json.dumps(validation_payload, indent=2, ensure_ascii=False) + "\n"
    )

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
    print(f"wrote {VALIDATION_OUT.relative_to(ROOT)}: "
          f"infeasible={len(infeasible_records)}, "
          f"divergences={len(curator_solver_divergences)}, "
          f"ambiguous={len(ambiguous)}, overrides={overrides_applied}")
    if infeasible_records:
        print("  INFEASIBLE chapters:")
        for r in infeasible_records:
            print(f"    ch{r['chapter_num']}: {r['diagnostic']} - {r['explanation']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
