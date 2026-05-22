"""Regression test: every paid purchased_perk[*].name resolves to a
canonical wireframe star.

If this fails, the curator-typed string didn't make it through the
alias / overlay / variant ladder in scripts/derive_roll_facts.py.
That's a build-time data-quality bug, not a runtime concern — fix the
producer (perk_aliases.json, unabridged_overlay.json, or the resolver),
not this test.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"


def _load(name: str) -> dict:
    return json.loads((DERIVED / name).read_text())


def test_paid_purchased_perk_names_match_wireframe_stars() -> None:
    rolls_doc = _load("roll_facts.json")
    wireframes = _load("constellation_wireframes.json")

    star_names: set[str] = set()
    for cluster in wireframes.get("cluster_constellations") or []:
        for jump in cluster.get("jumps") or []:
            for star in jump.get("stars") or []:
                name = star.get("perk_name")
                if name:
                    star_names.add(name)
    # Some wireframe builders nest jumps under different keys; fall
    # back to scanning the doc recursively for "perk_name".
    if not star_names:
        def walk(node) -> None:
            if isinstance(node, dict):
                if "perk_name" in node and isinstance(node["perk_name"], str):
                    star_names.add(node["perk_name"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(wireframes)

    missing: list[dict] = []
    for roll in rolls_doc.get("rolls", []):
        for perk in roll.get("purchased_perks") or []:
            if perk.get("free"):
                continue
            name = perk.get("name")
            if name not in star_names:
                missing.append({
                    "roll_number": roll.get("roll_number"),
                    "roll_key": roll.get("roll_key"),
                    "raw_instance": perk.get("instance"),
                    "resolved_name": name,
                    "resolved_id": perk.get("id"),
                    "jump": perk.get("jump"),
                    "constellation": roll.get("constellation"),
                })

    if missing:
        lines = ["paid purchased_perks[*].name not present as a wireframe star:"]
        for m in missing[:50]:
            lines.append(
                f"  roll {m['roll_number']} ({m['roll_key']}): "
                f"resolved={m['resolved_name']!r} "
                f"instance={m['raw_instance']!r} "
                f"jump={m['jump']!r} const={m['constellation']!r} "
                f"id={m['resolved_id']!r}"
            )
        if len(missing) > 50:
            lines.append(f"  ... +{len(missing) - 50} more")
        raise AssertionError("\n".join(lines))


def test_free_perk_names_match_wireframe_stars() -> None:
    """Free perks (ride-along bonus perks bundled with a paid parent)
    should also resolve to wireframe stars. Free perks whose directory
    lookup failed (id=None) are skipped — they're flagged in the test
    output for visibility but don't fail.

    Regression guard: a future change that misroutes free-perk names
    through a different code path would slip through the paid-only
    assertion above. This test catches that.
    """
    rolls_doc = _load("roll_facts.json")
    wireframes = _load("constellation_wireframes.json")

    star_names: set[str] = set()
    for cluster in wireframes.get("cluster_constellations") or []:
        for jump in cluster.get("jumps") or []:
            for star in jump.get("stars") or []:
                name = star.get("perk_name")
                if name:
                    star_names.add(name)
    if not star_names:
        def walk(node) -> None:
            if isinstance(node, dict):
                if "perk_name" in node and isinstance(node["perk_name"], str):
                    star_names.add(node["perk_name"])
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(wireframes)

    missing: list[dict] = []
    unresolved: list[dict] = []
    for roll in rolls_doc.get("rolls", []):
        for perk in roll.get("free_perks") or []:
            name = perk.get("name")
            if not perk.get("id"):
                unresolved.append({
                    "roll_number": roll.get("roll_number"),
                    "roll_key": roll.get("roll_key"),
                    "name": name,
                    "jump": perk.get("jump"),
                })
                continue
            if name not in star_names:
                missing.append({
                    "roll_number": roll.get("roll_number"),
                    "roll_key": roll.get("roll_key"),
                    "resolved_name": name,
                    "resolved_id": perk.get("id"),
                    "jump": perk.get("jump"),
                    "constellation": perk.get("constellation"),
                })

    if unresolved:
        # Flag for visibility (does not fail the test).
        print(
            f"\nfree_perks with id=None (skipped, not asserted): "
            f"{len(unresolved)}"
        )
        for u in unresolved[:20]:
            print(
                f"  roll {u['roll_number']} ({u['roll_key']}): "
                f"name={u['name']!r} jump={u['jump']!r}"
            )

    if missing:
        lines = ["free_perks[*].name not present as a wireframe star:"]
        for m in missing[:50]:
            lines.append(
                f"  roll {m['roll_number']} ({m['roll_key']}): "
                f"resolved={m['resolved_name']!r} "
                f"jump={m['jump']!r} const={m['constellation']!r} "
                f"id={m['resolved_id']!r}"
            )
        if len(missing) > 50:
            lines.append(f"  ... +{len(missing) - 50} more")
        raise AssertionError("\n".join(lines))
