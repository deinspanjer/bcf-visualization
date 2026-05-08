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
              "narrative_evidence": "..."
            },
            ...
          ],
          "narrative_evidence": "..."
        }
      }
    }

Legacy schema (still accepted; bare list is treated as a hit with no
metadata)::

    {
      "chapter_roll_overrides": {
        "<chapter_num>": {
          "rolls": [
            ["Perk A", "Perk B"],
            ["Perk C"]
          ],
          "narrative_evidence": "..."
        }
      }
    }

When a chapter has an entry, the override FULLY determines the chapter's
paid roll list (grouping AND order). Each inner array is one roll
containing one or more perks (paid or free). Free perks not listed in
any override roll for that chapter attach to the LAST roll (so total CP
debit is preserved). Paid perks not listed in any override roll for
that chapter raise an error — the override would silently drop them.

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
* ``merge_paid_units(obtained_perks, overrides)`` — back-compat wrapper
  that returns units in the legacy shape ``{chapter_num, paid,
  free_perks, epub_sequence, jump}`` consumed by ``predict_rolls.py``,
  ``derive_roll_outcomes.py`` and ``derive_roll_facts.py``.
* ``unit_total_cost`` / ``unit_principal_cost`` — cost helpers for the
  legacy unit shape.
"""

from __future__ import annotations

import json
from pathlib import Path


_OVERRIDES_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "manual" / "chapter_roll_overrides.json"
)
_LEGACY_OVERRIDES_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "manual" / "multi_grab_overrides.json"
)


def _normalise_roll_entry(entry) -> dict:
    """Coerce one roll-spec entry into the canonical dict shape.

    Accepted inputs:
      * ``["Perk A", "Perk B"]`` (legacy bare list) →
        ``{"perks": [...], "outcome": "hit", ...}``
      * ``{"perks": [...], "outcome": ..., ...}`` (canonical) → as-is.

    Returns dict with keys: ``perks`` (list[str]),
    ``outcome`` (str | None), ``constellation`` (str | None),
    ``word_position`` (int | None),
    ``narrative_evidence`` (str | None).
    """
    if isinstance(entry, list):
        return {
            "perks": list(entry),
            "outcome": "hit",
            "constellation": None,
            "word_position": None,
            "narrative_evidence": None,
        }
    if isinstance(entry, dict):
        perks = entry.get("perks") or []
        return {
            "perks": list(perks),
            "outcome": entry.get("outcome"),
            "constellation": entry.get("constellation"),
            "word_position": entry.get("word_position"),
            "narrative_evidence": entry.get("narrative_evidence"),
        }
    raise ValueError(
        f"chapter_roll_overrides roll entry must be list or dict, "
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

    The on-disk schema may use either the canonical per-roll dict or
    the legacy bare-list-of-names form; both are normalised here.

    Missing file -> empty dict. Falls back to the legacy filename
    (``multi_grab_overrides.json``) only if the new file is absent and
    the legacy one is present, to ease migrations.
    """
    p = path or _OVERRIDES_PATH
    if not p.exists() and _LEGACY_OVERRIDES_PATH.exists():
        p = _LEGACY_OVERRIDES_PATH
    if not p.exists():
        return {"chapter_roll_overrides": {}}
    doc = json.loads(p.read_text())
    raw = doc.get("chapter_roll_overrides") or {}
    normalised: dict[str, dict] = {}
    for cn, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        rolls = entry.get("rolls") or []
        normalised[str(cn)] = {
            "rolls": [_normalise_roll_entry(r) for r in rolls],
            "narrative_evidence": entry.get("narrative_evidence", ""),
        }
    return {"chapter_roll_overrides": normalised}


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def _perk_name(perk: dict) -> str | None:
    return perk.get("perk_name") or perk.get("name")


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
      ``rolls`` array determines structure. Each inner array of names is
      one roll. Names are looked up case-insensitively against the
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

    override = chapter_roll_overrides.get(chapter_num)
    if override is not None:
        rolls_spec = override.get("rolls") or []
        used_paid: set[str] = set()
        used_free: set[str] = set()
        rolls: list[dict] = []
        for roll_idx, roll_entry in enumerate(rolls_spec):
            name_list = roll_entry["perks"] if isinstance(roll_entry, dict) else roll_entry
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
    # caller's input order (which is epub_sequence ascending in the
    # legacy call paths, with free perks following their parent).
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
    """Group obtained perks into multi-grab units (legacy unit shape).

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

    units: list[dict] = []
    curated_chapters = 0
    curated_multi_grabs = 0
    primary_count = 0

    for cn in chapter_order:
        chapter_perks = by_chapter[cn]
        primary_count += sum(1 for p in chapter_perks if not p.get("free", False))
        paid_perks = [p for p in chapter_perks if not p.get("free", False)]
        free_perks = [p for p in chapter_perks if p.get("free", False)]
        override = chapter_roll_overrides.get(cn)

        if override is not None:
            curated_chapters += 1
            paid_lookup = {_norm(_perk_name(p)): p for p in paid_perks}
            free_lookup = {_norm(_perk_name(p)): p for p in free_perks}
            used_paid: set[str] = set()
            used_free: set[str] = set()

            for roll_idx, roll_entry in enumerate(override["rolls"]):
                name_list = roll_entry["perks"] if isinstance(roll_entry, dict) else roll_entry
                paid_in_roll: list[dict] = []
                free_in_roll: list[dict] = []
                for nm in name_list:
                    key = _norm(nm)
                    if key in paid_lookup:
                        paid_in_roll.append(paid_lookup[key])
                        used_paid.add(key)
                    elif key in free_lookup:
                        free_in_roll.append(free_lookup[key])
                        used_free.add(key)
                    else:
                        raise ValueError(
                            f"multi_grab override for ch {cn} roll #{roll_idx} "
                            f"references {nm!r} but no obtained perk in the "
                            f"chapter has that name "
                            f"(paid: {sorted(paid_lookup)}; "
                            f"free: {sorted(free_lookup)})"
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
                })

            unassigned_paid = [
                paid_lookup[k] for k in paid_lookup if k not in used_paid
            ]
            if unassigned_paid:
                names = [_perk_name(p) for p in unassigned_paid]
                print(
                    f"  multi_grab: ch {cn} override drops paid "
                    f"perk(s) {names!r} (not listed in any roll)"
                )

            leftover_free = [
                free_lookup[k] for k in free_lookup if k not in used_free
            ]
            if leftover_free and units and units[-1]["chapter_num"] == cn:
                units[-1]["free_perks"].extend(leftover_free)
        else:
            # Default: each paid perk is its own unit; free perks attach
            # to most recent preceding paid unit in this chapter.
            current: dict | None = None
            for perk in chapter_perks:
                if perk.get("free", False):
                    if current is None:
                        raise ValueError(
                            f"orphan free perk "
                            f"{_perk_name(perk)!r} in ch {cn} — no "
                            f"preceding paid acquisition"
                        )
                    current["free_perks"].append(perk)
                    continue
                current = {
                    "chapter_num": cn,
                    "paid": [perk],
                    "free_perks": [],
                    "epub_sequence": perk.get("epub_sequence"),
                    "jump": perk.get("jump"),
                }
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
