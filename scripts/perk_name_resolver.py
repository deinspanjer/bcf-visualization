"""Shared perk-name resolver.

Centralises the name-matching logic used by both
``scripts/build_perk_directory.py`` (folding obtained acquisitions into
canonical directory rows) and ``scripts/derive_roll_facts.py``
(resolving curator-typed paid-perk strings back to their canonical
directory entry).

Pipeline rule: canonicalisation is done at BUILD TIME. Web / TUI code
must not run another normalizer at render time — they consume the
already-resolved ``name`` field and treat ``instance`` purely as a
display hint.

The variant ladder (in order of preference at lookup time):

1. Exact ``(name, jump)`` match.
2. Canonical name from ``data/manual/perk_aliases.json`` (alias →
   canonical), then (1) again.
3. Normalised ``(name, jump)`` (lowercase, fold curly quotes, drop
   non-word punctuation, collapse whitespace).
4. Prefix / suffix splits on ``:`` / `` - `` / `` – `` / `` — `` —
   "Workshop: Metalworking" → "Workshop", "Innate Talent: Alchemist"
   → "Alchemist".
5. Normalised word-prefix variants — "Minor Blessing Aphrodite -
   Beauty" → "minor blessing".
6. Name-only fallback constrained to the same constellation (when one
   candidate matches).

Jump aliases (``JUMP_ALIASES``) handle cosmetic drift in jump names
between the curator's obtained log and the canonical Unabridged List.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from data_paths import MANUAL

PERK_ALIASES_JSON = MANUAL / "perk_aliases.json"


# obtained-form jump -> directory-form jump.
JUMP_ALIASES: dict[str, str] = {
    "Star Trek - TNG+DS9": "Star Trek: TNG",
    "Fullmetal Alchemist": "Full Metal Alchemist",
    "Mad Max Gauntlet": "Mad Max",
    "Binbougami Ga!": "Binbougami ga",
    "GUNNM/Battle Angel Alita": "GUNNM",
    "Highschool of the Dead": "High School of the Dead",
    "Totally Spies/Martin Mystery": "Totally Spies",
    "A Certain Scientific Railgun": "Raildex Science",
    "Sonic The Hedgehog": "Sonic",
    "Star Wars – Clone Wars": "Star Wars: The Clone Wars",
    "Thundercats 2011": "Thundercats",
    "Alpha Centauri": "Alpha Cenaturi",
    "Secret of Evermore": "Secrets of Evermore",
    "Overlord": "Overlord: Light Novel",
    "Halo UNSC": "Halo",
    "Bubblegum Crisis 2032": "Bubblegum Crisis",
    "Metal Gear": "Metal Gear Solid",
    "Fate": "Fate/",
    "Light of Terra DLC 3 - A Grand Day Out":
        "Warhammer 40,000: Light of Terra DLC 3 - A Grand Day Out",
    "Light of Terra DLC 4 - Lords of the Iron Line":
        "Warhammer 40,000: Light of Terra DLC 4 - Lords of the Iron Line",
    "Light of Terra 4 - Lords of the Iron Line - Warhammer 40,000":
        "Warhammer 40,000: Light of Terra DLC 4 - Lords of the Iron Line",
    "Light of Terra DLC 5 A Sky Filled With Steel - Warhammer 40,000":
        "Warhammer 40,000: Light of Terra DLC 5 - A Sky Filled With Steel",
    "LoT DLC 1 – The Heathen Trail – Warhammer 40,000":
        "Warhammer 40,000: Light of Terra DLC 1 - The Heathen Trail",
    # Curator log shorthand: the gacha supplement and the jump roll
    # under the same canonical name "Personal Reality" in the directory.
    "Personal Reality Supplement": "Personal Reality",
}


# Lowercase, fold curly quotes to ASCII, replace any non-word char
# (other than the apostrophe) with a space, collapse whitespace.
def _normalize(s: str | None) -> str:
    if not s:
        return ""
    out = s.lower()
    for a, b in [("’", "'"), ("‘", "'")]:
        out = out.replace(a, b)
    out = re.sub(r"[^\w\s']", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# Cost units that mean "this number IS already in CP". Personal Reality
# "WP" is treated as-is (pure CP-equivalent) because the rest of the
# pipeline already treats WP costs as CP. Everything else (e.g.
# "Customization Points") is denominated in something other than CP
# and must be multiplied by 100 to derive effective CP for visualization.
_CP_UNITS = {"cp", "wp", ""}


def parse_cost_text(cost_text: str) -> tuple[int, bool, str | None]:
    """Parse a raw cost-text into ``(effective_cp, is_free, cost_unit)``.

    The single source of truth for the ×100 rule used across the
    pipeline (parse_rolls catalog, parse_reference obtained perks, and
    parse_rolls roll-line perks).

    Accepted forms:
      - "Free", "Free?", "Free Soldier", ...     -> (0, True, None)
      - "100" / "100 CP" / "100 WP"               -> (100, False, None)
      - "3 Customization Points"                  -> (300, False, "Customization Points")
      - empty / unparseable                       -> (0, False, None)
    """
    s = (cost_text or "").strip()
    if not s:
        return 0, False, None
    low = s.lower()
    if low.startswith("free"):
        return 0, True, None
    m = re.match(r"^(\d+)(?:\s+(.*))?$", s)
    if not m:
        return 0, False, None
    value = int(m.group(1))
    unit = (m.group(2) or "").strip()
    if unit.lower() in _CP_UNITS:
        return value, False, None
    return value * 100, False, unit


_PREFIX_SEPARATORS = (":", " - ", " – ", " — ")


def _name_prefix_variants(name: str) -> list[str]:
    """Yield prefix AND suffix splits of `name` recursively."""
    out: list[str] = []
    seen = {name}
    queue: list[str] = [name]
    while queue:
        curr = queue.pop()
        for sep in _PREFIX_SEPARATORS:
            if sep in curr:
                pre, suf = curr.split(sep, 1)
                pre, suf = pre.strip(), suf.strip()
                for piece in (pre, suf):
                    if piece and piece not in seen:
                        seen.add(piece)
                        out.append(piece)
                        queue.append(piece)
                break  # one separator per pass; recursion handles the rest
    return out


def _normalized_word_prefixes(name: str) -> list[str]:
    """Word-prefix variants of the normalized name (>=2 words, >=1 word
    dropped). Folds sub-instances like "Minor Blessing Aphrodite -
    Beauty" back to "minor blessing"."""
    nn = _normalize(name)
    words = nn.split()
    if len(words) < 3:
        return []
    return [" ".join(words[:i]) for i in range(len(words) - 1, 1, -1)]


def load_perk_aliases(path: Path | None = None) -> dict[str, list[str]]:
    """Load ``{canonical: [alias, ...]}`` from data/manual/perk_aliases.json."""
    src = path or PERK_ALIASES_JSON
    data = json.loads(Path(src).read_text())
    out: dict[str, list[str]] = {}
    for canonical, aliases in data.items():
        if not isinstance(aliases, list):
            raise ValueError(
                f"perk_aliases.json: aliases for {canonical!r} must be a list"
            )
        out[canonical] = [str(a) for a in aliases]
    return out


def build_alias_lookup(aliases: dict[str, list[str]]) -> dict[str, str]:
    """Reverse-map every alias to its canonical name. Raises if any
    alias appears under two canonicals."""
    out: dict[str, str] = {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            if alias in out and out[alias] != canonical:
                raise ValueError(
                    f"perk alias {alias!r} maps to both {out[alias]!r} and "
                    f"{canonical!r}"
                )
            out[alias] = canonical
    return out


def resolve_canonical(raw_name: str, alias_lookup: dict[str, str]) -> str:
    """Return the canonical name for ``raw_name``, or ``raw_name``
    unchanged when no alias hits."""
    if not raw_name:
        return raw_name
    return alias_lookup.get(raw_name, raw_name)


class DirectoryMatchIndex:
    """Multi-key index over a directory of canonical perks.

    Keys registered per perk:
      - exact (name, jump)
      - normalised (name, jump)
      - separator-split prefix AND suffix variants of name (both raw
        and normalised) under same jump
      - normalised word-prefixes of name under same jump
      - every alias of the canonical name (raw + normalised) under
        same jump
      - name-only normalised fallback (last-resort, constellation
        filter applied at lookup time)
      - every JUMP_ALIASES form of the jump (so callers using the
        obtained-form jump still find the directory's canonical-form
        entry)
    """

    def __init__(
        self,
        directory_rows: list[dict],
        aliases: dict[str, list[str]],
        alias_lookup: dict[str, str] | None = None,
    ) -> None:
        self._aliases = aliases
        self._alias_lookup = alias_lookup or build_alias_lookup(aliases)
        self._by_exact: dict[tuple[str, str], dict] = {}
        self._by_norm: dict[tuple[str, str], list[dict]] = {}
        self._by_name_only: dict[str, list[dict]] = {}

        for perk in directory_rows:
            name = perk.get("name", "")
            jump = perk.get("jump") or ""
            if not name:
                continue
            # Collect every name form this row should answer to:
            #   - its own name
            #   - if name is a CANONICAL (key in aliases), every alias
            #     ("Workshop: Electronics" → Workshop parent row)
            #   - if name is an ALIAS (appears in alias_lookup), the
            #     canonical (xlsx typo "POWER OVERHELMING" → curator-
            #     log canonical "POWER OVERWHELMING")
            name_forms: list[str] = [name]
            for alias in self._aliases.get(name, []):
                if alias not in name_forms:
                    name_forms.append(alias)
            canonical = self._alias_lookup.get(name)
            if canonical and canonical not in name_forms:
                name_forms.append(canonical)

            jump_forms: list[str] = [jump]
            aliased_jump = JUMP_ALIASES.get(jump)
            if aliased_jump and aliased_jump != jump:
                jump_forms.append(aliased_jump)

            for j in jump_forms:
                for nm in name_forms:
                    self._register_perk(perk, nm, j)

    def _register_perk(self, perk: dict, name: str, jump: str) -> None:
        nn = _normalize(name)
        nj = _normalize(jump)
        # exact: first-write-wins so canonical (name, jump) beats
        # alias / variant collisions.
        self._by_exact.setdefault((name, jump), perk)
        self._by_norm.setdefault((nn, nj), []).append(perk)
        self._by_name_only.setdefault(nn, []).append(perk)
        for variant in _name_prefix_variants(name):
            vn = _normalize(variant)
            self._by_norm.setdefault((vn, nj), []).append(perk)
            self._by_name_only.setdefault(vn, []).append(perk)
        for nv in _normalized_word_prefixes(name):
            self._by_norm.setdefault((nv, nj), []).append(perk)
            self._by_name_only.setdefault(nv, []).append(perk)

    @property
    def alias_lookup(self) -> dict[str, str]:
        return self._alias_lookup

    def lookup(
        self,
        raw_name: str | None,
        jump: str | None = None,
        constellation: str | None = None,
    ) -> dict | None:
        """Return the canonical directory entry for ``raw_name``, or
        None if no resolution. ``jump`` and ``constellation`` narrow
        the search."""
        if not raw_name:
            return None
        # Resolve jump aliases up front so all subsequent steps see
        # the canonical jump name. JUMP_ALIASES maps curator-side
        # forms (e.g. "Personal Reality Supplement") to canonical
        # directory forms ("Personal Reality").
        jumps_to_try: list[str] = []
        if jump:
            jumps_to_try.append(jump)
            canonical_jump = JUMP_ALIASES.get(jump)
            if canonical_jump and canonical_jump != jump:
                jumps_to_try.append(canonical_jump)

        name = raw_name
        canonical_name = self._alias_lookup.get(name)

        # Step 1: exact (name, jump) across all jump forms. Prefer a
        # row that matches the requested constellation when one is
        # supplied (the (name, jump) key may map to multiple rows
        # across constellations; first-write-wins picked one of them).
        for j in jumps_to_try:
            row = self._by_exact.get((name, j))
            if row is None:
                continue
            if (
                constellation
                and row.get("constellation") != constellation
            ):
                # Look across norm-bucket for a same-constellation hit.
                cands = self._by_norm.get((_normalize(name), _normalize(j)), [])
                scoped = [
                    p for p in cands
                    if p.get("constellation") == constellation
                ]
                if scoped:
                    return scoped[0]
            return row
        # Step 2: alias-to-canonical exact
        if canonical_name:
            for j in jumps_to_try:
                row = self._by_exact.get((canonical_name, j))
                if row is None:
                    continue
                if (
                    constellation
                    and row.get("constellation") != constellation
                ):
                    cands = self._by_norm.get(
                        (_normalize(canonical_name), _normalize(j)), [],
                    )
                    scoped = [
                        p for p in cands
                        if p.get("constellation") == constellation
                    ]
                    if scoped:
                        return scoped[0]
                return row
        # Step 3: normalised (name, jump) — covers prefix/suffix &
        # word-prefix variants registered at index time, plus alias-
        # registered variants.
        for j in jumps_to_try:
            key = (_normalize(name), _normalize(j))
            cands = self._by_norm.get(key, [])
            if len(cands) == 1:
                return cands[0]
            if cands and constellation:
                scoped = [
                    p for p in cands
                    if p.get("constellation") == constellation
                ]
                if len(scoped) == 1:
                    return scoped[0]
                if scoped:
                    return scoped[0]
            if cands:
                return cands[0]
        # Step 4: name-only fallback, constellation filter.
        cands = self._by_name_only.get(_normalize(name), [])
        if constellation:
            scoped = [
                p for p in cands
                if p.get("constellation") == constellation
            ]
            if len(scoped) == 1:
                return scoped[0]
            if scoped:
                return scoped[0]
        if len(cands) == 1:
            return cands[0]
        return None


def build_directory_match_index(
    directory_rows: list[dict],
    aliases: dict[str, list[str]] | None = None,
) -> DirectoryMatchIndex:
    """Construct a ``DirectoryMatchIndex`` over the supplied directory.

    If ``aliases`` is None, loads from ``data/manual/perk_aliases.json``.
    """
    if aliases is None:
        aliases = load_perk_aliases()
    return DirectoryMatchIndex(directory_rows, aliases)
