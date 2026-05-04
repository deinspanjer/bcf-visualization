"""Build the canonical perk directory.

Source:  data/raw/Brocktons_Celestial_Forge_Reference.xlsx#Unabridged List

The Unabridged List is the master roster of every perk in the gacha:
constellation, name, jump (source media), and a status flag. Multi-perk
rows have newline-separated names in column 2; we expand them so each
perk gets its own row.

We enrich each perk with:
  - cost / cost_text / repeatable / description from perks_catalog.json
    (the Complete List of Perks sheet) when we can match
  - acquisition info (chapter_num, epub_sequence) from obtained_perks.json
    when matched. Repeatable perks use their EARLIEST acquisition chapter.

Filter: drop only Status == "Excluded"; keep Obtained, Available,
Partial, Locked, Unknown, Repeatable.

Output: data/derived/perk_directory.json (validated against
data/derived/_schemas/perk_directory.schema.json).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import load_workbook

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge_Reference.xlsx"
PERKS_CATALOG_JSON = ROOT / "data" / "derived" / "perks_catalog.json"
OBTAINED_JSON = ROOT / "data" / "derived" / "obtained_perks.json"
OUT = ROOT / "data" / "derived" / "perk_directory.json"


_CONSTELLATIONS = {
    "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
    "Clothing", "Magic", "Quality", "Size",
    "Resources and Durability", "Magitech", "Alchemy",
    "Capstone", "Personal Reality", "Felyne Perks",
}

_KEEP_STATUSES = {
    "Obtained", "Available", "Partial", "Locked", "Unknown", "Repeatable",
}


# Same logic as scripts/parse_reference.py::_normalize. Lowercase, fold
# curly quotes to ASCII, replace any non-word char (other than the
# apostrophe) with a space, collapse whitespace. Treats "-", ":", "—"
# as separators rather than preserved characters.
def _normalize(s: str | None) -> str:
    if not s:
        return ""
    out = s.lower()
    for a, b in [("’", "'"), ("‘", "'")]:
        out = out.replace(a, b)
    out = re.sub(r"[^\w\s']", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _id_for(constellation: str, jump: str, name: str) -> str:
    return f"{constellation}__{jump}__{_normalize(name)}"


_PREFIX_SEPARATORS = (":", " - ", " – ", " — ")


def _name_prefix_variants(name: str) -> list[str]:
    """Yield progressively shorter prefixes of `name`. Mirrors
    scripts/parse_reference.py::_prefix_candidates so multi-instance
    names like "Workshop: Metalworking" or "Unnatural Skill: Smith"
    fold back to the generic "Workshop" / "Unnatural Skill" entry.
    """
    out: list[str] = []
    seen = {name}
    for sep in _PREFIX_SEPARATORS:
        if sep in name:
            prefix = name.split(sep, 1)[0].strip()
            if prefix and prefix not in seen:
                out.append(prefix)
                seen.add(prefix)
    return out


def _norm_chapter(ch: str) -> tuple[int, int]:
    """Sort key for chapter ids like '12' or '43.1'."""
    if not ch:
        return (0, 0)
    if "." in ch:
        a, b = ch.split(".", 1)
        return (int(a), int(b))
    return (int(ch), 0)


@dataclass
class DirectoryPerk:
    id: str
    constellation: str
    name: str
    jump: str
    status: str
    cost: int | None
    cost_text: str | None
    free: bool
    repeatable: bool
    description: str
    acquired_chapter_num: str | None
    acquired_epub_sequence: int | None
    first_acquired_at_word_offset: int | None
    matched_to_obtained: bool


# ---------- catalog index ---------------------------------------------------


def _build_catalog_index(catalog: dict) -> dict[str, dict]:
    """Build progressive lookup tables from perks_catalog.json.

    Returned: {
      "exact": (name, source) -> catalog perk,
      "norm":  (norm_name, norm_source) -> catalog perk,
    }
    """
    by_exact: dict[tuple[str, str], dict] = {}
    by_norm: dict[tuple[str, str], dict] = {}
    for p in catalog.get("perks", []):
        name = p.get("name", "")
        source = p.get("source", "") or ""
        by_exact.setdefault((name, source), p)
        by_norm.setdefault((_normalize(name), _normalize(source)), p)
    return {"exact": by_exact, "norm": by_norm}


def _catalog_lookup(idx: dict, name: str, jump: str) -> dict | None:
    """Look up cost/description for a directory perk.

    Tries exact (name, jump), then case+punct-normalized (name, jump).
    No name-only fallback: cost is jump-specific (Workshop costs 100
    in Personal Reality but 200 in Samurai Jack), so folding by name
    alone would silently use the wrong cost.
    """
    if (name, jump) in idx["exact"]:
        return idx["exact"][(name, jump)]
    key = (_normalize(name), _normalize(jump))
    if key in idx["norm"]:
        return idx["norm"][key]
    return None


# ---------- obtained index --------------------------------------------------


def _build_obtained_index(obtained: dict) -> dict[str, dict]:
    """Index obtained_perks acquisitions for join.

    Repeatable perks may appear multiple times; collect *all* matches
    per key so we can pick the earliest chapter.

    The normalized (name, jump) index is seeded with prefix variants
    of each obtained name (e.g. "Workshop: Metalworking" in Personal
    Reality registers under both ("workshop metalworking", "personal
    reality") AND ("workshop", "personal reality")). That folds the
    generic Unabridged List entry "Workshop (Personal Reality)" to
    all the specific Joe-acquired instances in the same jump - without
    polluting cross-jump (Samurai Jack's "Workshop" entry never
    resolves to Personal Reality Workshops).
    """
    by_exact: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_norm: dict[tuple[str, str], list[dict]] = defaultdict(list)
    by_name_only: dict[str, list[dict]] = defaultdict(list)
    for p in obtained.get("perks", []):
        name = p.get("perk_name", "")
        jump = p.get("jump") or ""
        nn = _normalize(name)
        nj = _normalize(jump)
        by_exact[(name, jump)].append(p)
        by_norm[(nn, nj)].append(p)
        by_name_only[nn].append(p)
        for prefix in _name_prefix_variants(name):
            pn = _normalize(prefix)
            by_norm[(pn, nj)].append(p)
            by_name_only[pn].append(p)
    return {"exact": by_exact, "norm": by_norm, "name_only": by_name_only}


def _obtained_lookup(idx: dict, name: str, jump: str) -> list[dict]:
    """Return acquisitions matching this directory entry. Order per
    the spec:

       1. exact (name, jump),
       2. case+punct-normalized (name, jump),
       3. case+punct-normalized name only - only when the directory
          entry has no jump.

    Step 2 picks up prefix-variant matches scoped to the same jump
    (directory "Workshop"/"Personal Reality" finds the obtained
    "Workshop: Metalworking"/"Personal Reality" entries) but doesn't
    cross jumps. Cross-jump cosmetic drift ("Star Trek: TNG" vs
    "Star Trek - TNG+DS9", "Halo" vs "Halo UNSC", etc.) leaves the
    obtained acquisition orphaned in the spot-check - this is a
    surface-able data quality finding, not a silent over-match.
    """
    if (name, jump) in idx["exact"]:
        return idx["exact"][(name, jump)]
    key = (_normalize(name), _normalize(jump))
    if key in idx["norm"]:
        return idx["norm"][key]
    if not jump:
        nn = _normalize(name)
        if nn in idx["name_only"]:
            return idx["name_only"][nn]
    return []


def _earliest(acquisitions: list[dict]) -> dict:
    """The acquisition with the lowest chapter; ties broken by epub_sequence."""
    return min(
        acquisitions,
        key=lambda p: (
            _norm_chapter(p.get("chapter_num", "0")),
            p.get("epub_sequence", 0),
        ),
    )


# ---------- main ------------------------------------------------------------


def _norm_cell(value) -> str:
    return str(value).replace("\r", "").strip() if value is not None else ""


def _normalize_constellation(raw: str) -> str:
    """Trim ' Constellation' suffix if present and validate."""
    c = raw.strip()
    if c.endswith(" Constellation"):
        c = c[: -len(" Constellation")]
    if c not in _CONSTELLATIONS:
        raise ValueError(
            f"Unknown constellation {raw!r} - expected one of {sorted(_CONSTELLATIONS)}"
        )
    return c


def build_directory(
    wb,
    catalog_idx: dict,
    obtained_idx: dict,
) -> tuple[list[DirectoryPerk], dict[str, int], int, set[tuple[str, str]]]:
    """Walk the Unabridged List sheet and build the directory.

    Returns (perks, status_distribution, expanded_excluded_count,
    matched_obtained_keys).
    """
    ws = wb["Unabridged List"]
    perks: list[DirectoryPerk] = []
    status_dist: Counter[str] = Counter()
    excluded_expanded = 0
    matched_obtained_keys: set[tuple[str, str]] = set()

    # Track ids we've already emitted so multi-perk rows that re-list
    # the same name (or accidental dupes between rows of the same
    # constellation+jump) don't double up.
    seen_ids: set[str] = set()

    for r in range(2, ws.max_row + 1):
        const_raw = _norm_cell(ws.cell(r, 1).value)
        names_raw = _norm_cell(ws.cell(r, 2).value)
        jump = _norm_cell(ws.cell(r, 3).value)
        status = _norm_cell(ws.cell(r, 4).value)
        if not names_raw:
            continue

        names = [n.strip() for n in names_raw.split("\n") if n.strip()]

        if status == "Excluded":
            excluded_expanded += len(names)
            continue
        if status not in _KEEP_STATUSES:
            raise ValueError(
                f"Row {r}: unexpected status {status!r} (name={names_raw!r}, "
                f"jump={jump!r}). Update _KEEP_STATUSES if this is intentional."
            )

        if not const_raw:
            raise ValueError(f"Row {r}: missing constellation for name={names_raw!r}")
        constellation = _normalize_constellation(const_raw)

        if not jump:
            # All non-excluded rows have a jump in the current data;
            # keep this strict so we notice if that ever changes.
            raise ValueError(
                f"Row {r}: missing jump for {constellation}/{names_raw!r}"
            )

        for name in names:
            pid = _id_for(constellation, jump, name)
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            cat = _catalog_lookup(catalog_idx, name, jump)
            obtained_matches = _obtained_lookup(obtained_idx, name, jump)

            cost: int | None = None
            cost_text: str | None = None
            free = False
            repeatable = False
            description = ""

            if cat is not None:
                cost = cat.get("cost")
                cost_text = cat.get("cost_text")
                free = bool(
                    cat.get("cost") == 0
                    and (cat.get("cost_text") or "").lower().startswith("free")
                )
                repeatable = bool(cat.get("repeatable"))
                description = cat.get("description", "") or ""
            elif obtained_matches:
                # Fall back to obtained_perks's cost info
                first = obtained_matches[0]
                cost = first.get("cost")
                cost_text = first.get("cost_text")
                free = bool(first.get("free"))
                description = first.get("perk_text", "") or ""

            acquired_chapter_num: str | None = None
            acquired_epub_sequence: int | None = None
            matched = False
            if obtained_matches:
                matched = True
                earliest = _earliest(obtained_matches)
                acquired_chapter_num = earliest.get("chapter_num")
                acquired_epub_sequence = earliest.get("epub_sequence")
                # Track every acquisition we covered so the spot-check
                # can report which obtained rows aren't represented in
                # the directory at all.
                for m in obtained_matches:
                    matched_obtained_keys.add(
                        (m.get("perk_name", ""), m.get("jump") or "")
                    )

            perks.append(
                DirectoryPerk(
                    id=pid,
                    constellation=constellation,
                    name=name,
                    jump=jump,
                    status=status,
                    cost=cost,
                    cost_text=cost_text,
                    free=free,
                    repeatable=repeatable,
                    description=description,
                    acquired_chapter_num=acquired_chapter_num,
                    acquired_epub_sequence=acquired_epub_sequence,
                    first_acquired_at_word_offset=None,  # future work
                    matched_to_obtained=matched,
                )
            )
            status_dist[status] += 1

    # Sort for deterministic output: by constellation, jump, then name.
    perks.sort(key=lambda p: (p.constellation, p.jump, p.name))
    return perks, dict(status_dist), excluded_expanded, matched_obtained_keys


def main() -> None:
    wb = load_workbook(SRC, data_only=True)
    catalog = json.loads(PERKS_CATALOG_JSON.read_text())
    obtained = json.loads(OBTAINED_JSON.read_text())

    catalog_idx = _build_catalog_index(catalog)
    obtained_idx = _build_obtained_index(obtained)

    perks, status_dist, excluded_expanded, matched_keys = build_directory(
        wb, catalog_idx, obtained_idx
    )

    acquired = sum(1 for p in perks if p.matched_to_obtained)

    write_validated_json(
        OUT,
        {
            "_source": "data/raw/Brocktons_Celestial_Forge_Reference.xlsx#Unabridged List",
            "_count": len(perks),
            "_status_distribution": status_dist,
            "_acquired_count": acquired,
            "_note": (
                "Canonical roster of every rollable perk in the gacha. One row "
                "per perk; multi-perk rows in the Unabridged List "
                "(newline-separated names in column B) are expanded. Status "
                "'Excluded' rows are dropped. cost / cost_text / repeatable / "
                "description are joined from perks_catalog.json by (name, jump) "
                "with cosmetic-tolerant fallbacks; acquisition fields are "
                "joined from obtained_perks.json the same way, with prefix-split "
                "matching so generic entries like 'Workshop' fold in all the "
                "specific instances Joe acquired ('Workshop: Metalworking', "
                "etc.). For repeatable perks, acquired_chapter_num is the "
                "EARLIEST chapter in which Joe acquired the perk. "
                "first_acquired_at_word_offset is reserved for future work."
            ),
            "perks": [asdict(p) for p in perks],
        },
        "perk_directory",
    )

    # ---- summary --------------------------------------------------------
    by_const = Counter(p.constellation for p in perks)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(perks)} perks "
          f"(dropped {excluded_expanded} Excluded)")
    print(f"  acquired (matched to obtained_perks): {acquired}/{len(perks)}")
    print("  status distribution:")
    for s in sorted(status_dist, key=lambda k: -status_dist[k]):
        print(f"    {s:12s}  {status_dist[s]}")
    print("  by constellation:")
    for c in sorted(by_const, key=lambda k: -by_const[k]):
        print(f"    {c:25s}  {by_const[c]}")

    # ---- spot check: every obtained_perks acquisition should map to a
    # directory entry. Most repeatable instances fold via prefix-split.
    obtained_keys = {
        (p.get("perk_name", ""), p.get("jump") or "")
        for p in obtained.get("perks", [])
    }
    orphans = obtained_keys - matched_keys
    print(f"  obtained_perks acquisitions: {obtained.get('_count', 0)} rows, "
          f"{len(obtained_keys)} unique (name, jump) pairs")
    print(f"  matched into directory:      "
          f"{len(obtained_keys) - len(orphans)}/{len(obtained_keys)}")
    if orphans:
        print(f"  ORPHANS - obtained acquisitions with no directory entry "
              f"({len(orphans)}):", file=sys.stderr)
        for name, jump in sorted(orphans):
            print(f"    - {name!r}  ({jump!r})", file=sys.stderr)


if __name__ == "__main__":
    main()
