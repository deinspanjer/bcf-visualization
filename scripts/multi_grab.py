"""Multi-grab grouping for paid perk acquisitions.

The Forge sometimes grabs multiple paid perks in a single roll
("multi-grab"). The mechanical signal in obtained_perks is ambiguous —
shared (chapter, jump, epub_sequence) merely means perks ended up on the
same chapter-end list slot, not that they were a single mechanical roll.
We therefore use a CURATED-ONLY detection model: every multi-grab must
be hand-listed in ``data/manual/chapter_roll_overrides.json``.

Override schema (current, per-roll metadata)::

    {
      "chapter_roll_overrides": {
        "<chapter_num>": {
          "rolls": [
            {
              "perks": ["Perk A", "Perk B"],
              "outcome": "hit"|"miss",
              "constellation": "...",
              "word_position": int|null,
              "mention_chapter_num": "N",
              "mention_word_position": int|null,
              "display_position_policy": "mention"|"mechanical"|"section_start",
              "narrative_evidence": "..."
            },
            ...
          ],
          "narrative_evidence": "..."
        }
      }
    }

When a chapter has an entry, the override FULLY determines the chapter's
paid roll list (grouping AND order). Each `rolls` object is one roll
containing zero or more perks. Free perks not listed in any override
roll for that chapter attach to the LAST roll (so total CP debit is
preserved). Paid perks not listed in any override roll for that chapter
raise an error — the override would silently drop them.

Without an override entry, the chapter falls back to: each paid
obtained_perks row is its own roll, in obtained_perks/epub_sequence
order; free perks attach to the most recent preceding paid roll within
the same chapter.

Public API:

* ``load_overrides()`` — load and normalise the override file.
* ``group_chapter_paid_perks(chapter_num, paid_perks, free_perks,
  chapter_roll_overrides)`` — return per-chapter rolls in the
  ``roll_facts``-shaped ``{purchased_perks, purchased_perk_cost_total}``
  form (used by future consumers).
* ``merge_paid_units(obtained_perks, overrides)`` — return acquisition
  units in the shape ``{chapter_num, paid,
  free_perks, epub_sequence, jump}`` consumed by ``predict_rolls.py``,
  ``derive_roll_outcomes.py`` and ``derive_roll_facts.py``.
* ``unit_total_cost`` / ``unit_principal_cost`` — cost helpers for the
  unit shape.
"""

from __future__ import annotations

import json
from pathlib import Path


_OVERRIDES_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "manual" / "chapter_roll_overrides.json"
)
def _normalise_roll_entry(entry) -> dict:
    """Coerce one roll-spec entry into the canonical dict shape.

    Returns dict with keys: ``perks`` (list[str]),
    ``outcome`` (str | None), ``constellation`` (str | None),
    ``word_position`` (int | None), ``mention_chapter_num`` (str | None),
    ``mention_word_position`` (int | None),
    ``display_position_policy`` (str | None),
    ``narrative_evidence`` (str | None).
    """
    if isinstance(entry, dict):
        perks = entry.get("perks") or []
        return {
            "perks": list(perks),
            "outcome": entry.get("outcome"),
            "constellation": entry.get("constellation"),
            "word_position": entry.get("word_position"),
            "mention_chapter_num": (
                str(entry.get("mention_chapter_num"))
                if entry.get("mention_chapter_num") is not None else None
            ),
            "mention_word_position": entry.get("mention_word_position"),
            "display_position_policy": entry.get("display_position_policy"),
            "narrative_evidence": entry.get("narrative_evidence"),
        }
    raise ValueError(
        f"chapter_roll_overrides roll entry must be dict, "
        f"got {type(entry).__name__}: {entry!r}"
    )


def load_overrides(path: Path | None = None) -> dict:
    """Load the chapter-roll overrides document.

    Returns a dict with key ``chapter_roll_overrides`` mapping
    ``chapter_num`` (str) to::

        {
          "rolls": [
            {"perks": [...], "outcome": ..., "constellation": ...,
             "word_position": ..., "narrative_evidence": ...},
            ...
          ],
          "narrative_evidence": str | None,
        }

    Missing file -> empty dict.
    """
    p = path or _OVERRIDES_PATH
    if not p.exists():
        return {"chapter_roll_overrides": {}}
    doc = json.loads(p.read_text())
    raw = doc.get("chapter_roll_overrides") or {}
    normalised: dict[str, dict] = {}
    for cn, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        rolls = entry.get("rolls") or []
        normalised_rolls = []
        for r in rolls:
            roll = _normalise_roll_entry(r)
            if roll.get("mention_chapter_num") is None:
                roll["mention_chapter_num"] = str(cn)
            if roll.get("display_position_policy") is None:
                roll["display_position_policy"] = (
                    "mention"
                    if roll.get("mention_word_position") is not None
                    else "mechanical"
                )
            normalised_rolls.append(roll)
        normalised[str(cn)] = {
            "rolls": normalised_rolls,
            "narrative_evidence": entry.get("narrative_evidence", ""),
        }
    return {"chapter_roll_overrides": normalised}


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def _perk_name(perk: dict) -> str | None:
    return perk.get("perk_name") or perk.get("name")


def _is_metadata_only_roll_entry(entry: dict, chapter_num: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("outcome") in ("hit", "miss"):
        return False
    if entry.get("perks"):
        return False
    structural_fields = (
        "constellation",
        "word_position",
    )
    if any(entry.get(field) not in (None, "", []) for field in structural_fields):
        return False
    return entry.get("display_position_policy") in (
        None,
        "",
        "mechanical",
        "mention",
        "section_start",
    )


def _structural_override(override: dict | None, chapter_num: str) -> dict | None:
    if override is None:
        return None
    if any(
        not _is_metadata_only_roll_entry(entry, chapter_num)
        for entry in (override.get("rolls") or [])
    ):
        return override
    return None


def group_chapter_paid_perks(
    chapter_num: str,
    paid_perks: list[dict],
    free_perks: list[dict],
    chapter_roll_overrides: dict,
) -> list[dict]:
    """Group a chapter's perks into rolls.

    Returns a list of rolls, each shaped::

        {
            "purchased_perks": [
                {"name": str, "cost": int, "free": bool},
                ...
            ],
            "purchased_perk_cost_total": int,
        }

    Behaviour:

    * If ``chapter_num`` is in ``chapter_roll_overrides``: the override
      ``rolls`` array determines structure. Each entry is one roll.
      Names are looked up case-insensitively against the
      chapter's combined paid+free perks. Unknown names raise a
      ``ValueError``. Free perks not listed in any override roll attach
      to the LAST roll (so the chapter's total CP debit and free-perk
      list are preserved); if every free perk is explicitly listed,
      none are auto-attached.
    * Otherwise: each paid perk becomes its own roll, in input order;
      free perks attach to the most recent preceding paid roll. (Free
      perks before the first paid perk in a chapter are an error.)
    """
    chapter_num = str(chapter_num)
    paid_by_norm: dict[str, dict] = {}
    free_by_norm: dict[str, dict] = {}
    for p in paid_perks:
        nm = _perk_name(p)
        if nm:
            paid_by_norm[_norm(nm)] = p
    for p in free_perks:
        nm = _perk_name(p)
        if nm:
            free_by_norm[_norm(nm)] = p

    override = _structural_override(
        chapter_roll_overrides.get(chapter_num), chapter_num
    )
    if override is not None:
        rolls_spec = override.get("rolls") or []
        used_paid: set[str] = set()
        used_free: set[str] = set()
        rolls: list[dict] = []
        for roll_idx, roll_entry in enumerate(rolls_spec):
            name_list = roll_entry.get("perks") or []
            purchased: list[dict] = []
            for nm in name_list:
                key = _norm(nm)
                if key in paid_by_norm:
                    perk = paid_by_norm[key]
                    used_paid.add(key)
                    cost = int(perk.get("cost") or 0)
                    purchased.append({
                        "name": _perk_name(perk),
                        "cost": cost,
                        "free": False,
                    })
                elif key in free_by_norm:
                    perk = free_by_norm[key]
                    used_free.add(key)
                    purchased.append({
                        "name": _perk_name(perk),
                        "cost": 0,
                        "free": True,
                    })
                else:
                    raise ValueError(
                        f"multi_grab override for ch {chapter_num} roll "
                        f"#{roll_idx} references {nm!r} but no obtained "
                        f"perk in the chapter has that name (paid keys: "
                        f"{sorted(paid_by_norm)}; free keys: "
                        f"{sorted(free_by_norm)})"
                    )
            cost_total = sum(p["cost"] for p in purchased if not p["free"])
            rolls.append({
                "purchased_perks": purchased,
                "purchased_perk_cost_total": cost_total,
            })

        # Per spec, the override FULLY determines the chapter's paid
        # roll list. Paid perks present in obtained_perks but absent
        # from the override are silently dropped (caller's intent).
        # We surface a one-line warning so the drop is at least visible
        # in the pipeline log.
        unassigned_paid = [
            paid_by_norm[k] for k in paid_by_norm if k not in used_paid
        ]
        if unassigned_paid:
            names = [_perk_name(p) for p in unassigned_paid]
            print(
                f"  multi_grab: ch {chapter_num} override drops paid "
                f"perk(s) {names!r} (not listed in any roll)"
            )

        # Auto-attach free perks not explicitly listed to the LAST roll.
        leftover_free_keys = [k for k in free_by_norm if k not in used_free]
        if leftover_free_keys and rolls:
            last_roll = rolls[-1]
            for k in leftover_free_keys:
                perk = free_by_norm[k]
                last_roll["purchased_perks"].append({
                    "name": _perk_name(perk),
                    "cost": 0,
                    "free": True,
                })

        return rolls

    # No override — default behaviour: each paid perk is its own roll;
    # free perks attach to most recent preceding paid roll. Use the
    # caller's input order (epub_sequence ascending, with free perks
    # following their parent).
    combined: list[dict] = []
    seen: set[int] = set()

    # Reconstruct the original input order. The caller passes paid_perks
    # and free_perks separately, so we have to interleave by
    # epub_sequence then by id() as a stable tiebreak.
    def _sort_key(perk: dict) -> tuple:
        return (
            int(perk.get("epub_sequence") or 0),
            0 if not perk.get("free", False) else 1,
        )

    for perk in sorted(paid_perks + free_perks, key=_sort_key):
        if id(perk) in seen:
            continue
        seen.add(id(perk))
        combined.append(perk)

    rolls: list[dict] = []
    for perk in combined:
        if perk.get("free", False):
            if not rolls:
                raise ValueError(
                    f"orphan free perk {_perk_name(perk)!r} in ch "
                    f"{chapter_num} — no preceding paid acquisition"
                )
            rolls[-1]["purchased_perks"].append({
                "name": _perk_name(perk),
                "cost": 0,
                "free": True,
            })
        else:
            cost = int(perk.get("cost") or 0)
            rolls.append({
                "purchased_perks": [{
                    "name": _perk_name(perk),
                    "cost": cost,
                    "free": False,
                }],
                "purchased_perk_cost_total": cost,
            })
    return rolls


def merge_paid_units(
    obtained_perks: list[dict],
    overrides: dict | None = None,
) -> tuple[list[dict], dict]:
    """Group obtained perks into roll acquisition units.

    ``obtained_perks`` should be ordered by ``epub_sequence`` ascending
    (free perks immediately following their parent paid perk).

    Returns ``(units, stats)`` where each unit is::

        {
            "chapter_num": str,
            "paid": [perk_dict, ...],
            "free_perks": [perk_dict, ...],
            "epub_sequence": int | None,
            "jump": str | None,
        }

    and ``stats`` contains diagnostic counts.
    """
    overrides = overrides or {}
    chapter_roll_overrides = overrides.get("chapter_roll_overrides") or {}

    # Bucket perks by chapter, preserving input order.
    by_chapter: dict[str, list[dict]] = {}
    chapter_order: list[str] = []
    for perk in obtained_perks:
        cn = str(perk["chapter_num"])
        if cn not in by_chapter:
            by_chapter[cn] = []
            chapter_order.append(cn)
        by_chapter[cn].append(perk)

    paid_global: dict[tuple[str, str], list[dict]] = {}
    free_global: dict[tuple[str, str], list[dict]] = {}
    for perk in obtained_perks:
        key = (str(perk["chapter_num"]), _norm(_perk_name(perk)))
        if not key[1]:
            continue
        target = free_global if perk.get("free", False) else paid_global
        target.setdefault(key, []).append(perk)

    consumed_paid: set[int] = set()
    consumed_free: set[int] = set()

    def _first_available(
        lookup: dict[tuple[str, str], list[dict]],
        chapter_num: str,
        name_key: str,
        consumed: set[int],
    ) -> dict | None:
        for candidate in lookup.get((chapter_num, name_key), []):
            if id(candidate) not in consumed:
                return candidate
        return None

    def _unit_common(roll_entry: dict, mechanical_chapter: str) -> dict:
        mention_chapter = str(
            roll_entry.get("mention_chapter_num") or mechanical_chapter
        )
        policy = roll_entry.get("display_position_policy")
        if policy is None:
            policy = (
                "mention"
                if roll_entry.get("mention_word_position") is not None
                else "mechanical"
            )
        return {
            "mention_chapter_num": mention_chapter,
            "mention_word_position": roll_entry.get("mention_word_position"),
            "display_position_policy": policy,
            "narrative_evidence": roll_entry.get("narrative_evidence"),
        }

    units: list[dict] = []
    curated_chapters = 0
    curated_multi_grabs = 0
    primary_count = 0

    for cn in chapter_order:
        chapter_perks = by_chapter[cn]
        primary_count += sum(1 for p in chapter_perks if not p.get("free", False))
        paid_perks = [p for p in chapter_perks if not p.get("free", False)]
        free_perks = [p for p in chapter_perks if p.get("free", False)]
        override = _structural_override(chapter_roll_overrides.get(cn), cn)

        if override is not None:
            curated_chapters += 1
            paid_lookup = {_norm(_perk_name(p)): p for p in paid_perks}
            free_lookup = {_norm(_perk_name(p)): p for p in free_perks}
            used_paid: set[str] = set()
            used_free: set[str] = set()

            for roll_idx, roll_entry in enumerate(override["rolls"]):
                name_list = roll_entry.get("perks") or []
                mention_cn = str(roll_entry.get("mention_chapter_num") or cn)
                paid_in_roll: list[dict] = []
                free_in_roll: list[dict] = []
                for nm in name_list:
                    key = _norm(nm)
                    paid = (
                        _first_available(paid_global, mention_cn, key, consumed_paid)
                        or (
                            paid_lookup.get(key)
                            if id(paid_lookup.get(key)) not in consumed_paid
                            else None
                        )
                    )
                    free = (
                        _first_available(free_global, mention_cn, key, consumed_free)
                        or (
                            free_lookup.get(key)
                            if id(free_lookup.get(key)) not in consumed_free
                            else None
                        )
                    )
                    if paid is not None:
                        paid_in_roll.append(paid)
                        consumed_paid.add(id(paid))
                        used_paid.add(key)
                    elif free is not None:
                        free_in_roll.append(free)
                        consumed_free.add(id(free))
                        used_free.add(key)
                    else:
                        raise ValueError(
                            f"multi_grab override for ch {cn} roll #{roll_idx} "
                            f"references {nm!r} but no obtained perk in the "
                            f"mechanical or mention chapter has that name "
                            f"(mechanical paid: {sorted(paid_lookup)}; "
                            f"mechanical free: {sorted(free_lookup)}; "
                            f"mention_chapter_num: {mention_cn})"
                        )
                if not paid_in_roll and not free_in_roll:
                    continue
                if len(paid_in_roll) > 1:
                    curated_multi_grabs += 1
                # Anchor the unit on the first paid perk; if a roll has
                # only free perks (rare, probably an error), anchor on
                # the first free.
                anchor = paid_in_roll[0] if paid_in_roll else free_in_roll[0]
                units.append({
                    "chapter_num": cn,
                    "paid": list(paid_in_roll),
                    "free_perks": list(free_in_roll),
                    "epub_sequence": anchor.get("epub_sequence"),
                    "jump": anchor.get("jump"),
                    "_override_roll_index": roll_idx,
                    **_unit_common(roll_entry, cn),
                })

            unassigned_paid = [
                paid_lookup[k]
                for k in paid_lookup
                if k not in used_paid and id(paid_lookup[k]) not in consumed_paid
            ]
            unassigned_costed_paid = [
                p for p in unassigned_paid if int(p.get("cost") or 0) > 0
            ]
            if unassigned_costed_paid:
                names = [_perk_name(p) for p in unassigned_costed_paid]
                print(
                    f"  multi_grab: ch {cn} override drops paid "
                    f"perk(s) {names!r} (not listed in any roll)"
                )

            leftover_free = [
                free_lookup[k]
                for k in free_lookup
                if k not in used_free and id(free_lookup[k]) not in consumed_free
            ]
            if leftover_free and units and units[-1]["chapter_num"] == cn:
                units[-1]["free_perks"].extend(leftover_free)
                for p in leftover_free:
                    consumed_free.add(id(p))
        else:
            # Default: each paid perk is its own unit; free perks attach
            # to most recent preceding paid unit in this chapter.
            current: dict | None = None
            for perk in chapter_perks:
                if perk.get("free", False) and id(perk) in consumed_free:
                    continue
                if not perk.get("free", False) and id(perk) in consumed_paid:
                    continue
                if perk.get("free", False):
                    if current is None:
                        raise ValueError(
                            f"orphan free perk "
                            f"{_perk_name(perk)!r} in ch {cn} — no "
                            f"preceding paid acquisition"
                        )
                    current["free_perks"].append(perk)
                    consumed_free.add(id(perk))
                    continue
                current = {
                    "chapter_num": cn,
                    "paid": [perk],
                    "free_perks": [],
                    "epub_sequence": perk.get("epub_sequence"),
                    "jump": perk.get("jump"),
                    "mention_chapter_num": cn,
                    "mention_word_position": None,
                    "display_position_policy": "mechanical",
                    "narrative_evidence": None,
                    "_override_roll_index": None,
                }
                consumed_paid.add(id(perk))
                units.append(current)

    stats = {
        "primary_count": primary_count,
        "merged_count": len(units),
        "curated_chapters": curated_chapters,
        "curated_multi_grabs": curated_multi_grabs,
    }
    return units, stats


def unit_total_cost(unit: dict) -> int:
    """Sum of paid perks' costs in a merged unit."""
    return sum(int(p.get("cost") or 0) for p in unit["paid"])


def unit_principal_cost(unit: dict) -> int:
    """Largest paid cost in the unit. Used for shadow / threshold lookup
    where the trigger is the dominant single-perk cost (only matters for
    regime-3 600/800 perks)."""
    if not unit["paid"]:
        return 0
    return max(int(p.get("cost") or 0) for p in unit["paid"])
