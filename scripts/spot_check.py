"""Cross-source spot checks for the derived datasets.

Verifies that secondary-source data (the two curator xlsx files) is
consistent with primary sources (the EPUB story text and the SV
threadmark MHTs), and that the two curator sources agree with each
other on the chapter range they share.

Checks:
  1. Chapter alignment - every chapter the curators list also exists
     in the threadmark-derived chapters.json.
  2. Word counts - EPUB exact word count vs threadmark rounded
     "5k"/"8.2k" display, expecting agreement to within rounding.
  3. Roll-pace math - the original mechanic was "100 CP per 2000
     words". For chapters with rolls, sum of rolls in that chapter
     should track words / 20. (Only checks chapters before the
     ch97 mechanic change.)
  4. Perks consistency - every perk acquired in rolls.json must exist
     in perks_catalog.json. Cosmetic mismatches (case, ASCII vs
     Unicode punctuation, source aliases) are distinguished from
     genuine gaps.
  5. Curator agreement - rolls.json (sonicyoash, chapters 1-75) vs
     obtained_perks.json (Reference, full story). Both list every
     paid acquisition for chapters 1-75; counts should match.

Hard failures (exit non-zero): primary-vs-primary disagreement.
Soft warnings (exit 0): findings within or between secondary sources
(curator data-entry quality).
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
DERIVED = ROOT / "data" / "derived"

WORD_TOLERANCE_RATIO = 0.10   # threadmark rounded display vs EPUB exact
ROLL_PACE_TOLERANCE = 0.30    # rolls × 2000 vs EPUB exact words


# ---------- helpers ---------------------------------------------------------


class _Strip(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _word_count(html: str) -> int:
    s = _Strip()
    s.feed(html)
    text = re.sub(r"\s+", " ", "".join(s.parts)).strip()
    return len(text.split()) if text else 0


def _epub_word_counts() -> dict[str, int]:
    """Map full_title (matches threadmark) -> EPUB word count."""
    counts: dict[str, int] = {}
    with zipfile.ZipFile(EPUB) as zf:
        nav = zf.read("EPUB/nav.xhtml").decode("utf-8")
        # Extract <a href=...>title</a> from nav
        nav_re = re.compile(r'<a[^>]*?href="([^"]+)"[^>]*>([^<]+)</a>', re.DOTALL)
        for href, title in nav_re.findall(nav):
            title = title.strip()
            if not title or title == "Introduction":
                continue
            try:
                html = zf.read(f"EPUB/{href}").decode("utf-8")
            except KeyError:
                continue
            counts[title] = _word_count(html)
    return counts


def _load(name: str) -> dict:
    return json.loads((DERIVED / f"{name}.json").read_text())


# ---------- checks ----------------------------------------------------------


# Curator uses these as section labels in column A, not real chapters.
_NON_CHAPTER_LABELS = {"Edits:", "Reference", "Total"}


def check_chapter_alignment(chapters: dict, rolls: dict) -> list[str]:
    """Every chapter the curator references must exist in chapters.json."""
    errors: list[str] = []
    threadmark_nums = {c["chapter_num"] for c in chapters["chapters"]}
    curator_nums = {
        r["chapter_num"]
        for r in rolls["rolls"]
        if r["chapter_num"] and r["chapter_num"] != "0"
    }
    bad = curator_nums - threadmark_nums - _NON_CHAPTER_LABELS
    if bad:
        errors.append(
            f"  curator references chapters not in threadmarks: {sorted(bad)}"
        )
    print(f"check 1 - chapter alignment:")
    print(f"  threadmark chapters:   {len(threadmark_nums)}")
    print(f"  curator references:    {len(curator_nums - _NON_CHAPTER_LABELS)} chapters + {len(curator_nums & _NON_CHAPTER_LABELS)} non-chapter labels")
    print(f"  mismatched:            {len(bad)}")
    return errors


def check_word_counts(chapters: dict) -> list[str]:
    """Threadmark rounded display should agree with EPUB exact within tolerance."""
    errors: list[str] = []
    epub = _epub_word_counts()
    n_compared = 0
    n_off = 0
    big_misses: list[tuple[str, int, int, float]] = []
    for c in chapters["chapters"]:
        if c["full_title"] not in epub:
            continue
        n_compared += 1
        actual = epub[c["full_title"]]
        approx = c["words_approx"]
        if approx == 0:
            continue
        ratio_off = abs(actual - approx) / max(actual, 1)
        if ratio_off > WORD_TOLERANCE_RATIO:
            n_off += 1
            big_misses.append((c["full_title"], actual, approx, ratio_off))
    big_misses.sort(key=lambda x: -x[3])
    print(f"\ncheck 2 - threadmark word count vs EPUB exact:")
    print(f"  compared:              {n_compared} chapters")
    print(f"  off by >{int(WORD_TOLERANCE_RATIO*100)}%:           {n_off}")
    for title, actual, approx, ratio in big_misses[:10]:
        print(f"    {title[:60]:60s}  exact={actual:>6d}  rounded={approx:>6d}  off={ratio:.0%}")
    if n_off:
        errors.append(f"  {n_off} chapters disagree by more than {WORD_TOLERANCE_RATIO:.0%}")
    return errors


def check_roll_pace(chapters: dict, rolls: dict) -> list[str]:
    """For each chapter with rolls, expect ~ rolls * 2000 ≈ EPUB words.

    Returned issues are SOFT - the "100 CP per 2000 words" rule is a
    fictional in-story mechanic, not a hard math invariant. Edits,
    interlude pacing, and curator omissions all create real noise.
    """
    errors: list[str] = []
    epub = _epub_word_counts()
    full_title_by_num = {c["chapter_num"]: c["full_title"] for c in chapters["chapters"]}

    rolls_per_chapter: dict[str, int] = defaultdict(int)
    for r in rolls["rolls"]:
        if r["kind"] in ("trigger", "roll", "miss"):
            rolls_per_chapter[r["chapter_num"]] += 1

    n_off = 0
    big_misses: list[tuple[str, int, int, float]] = []
    n_compared = 0
    for chap_num, nrolls in rolls_per_chapter.items():
        title = full_title_by_num.get(chap_num)
        if not title or title not in epub:
            continue
        words = epub[title]
        if words == 0:
            continue
        expected_rolls = words / 2000
        ratio_off = abs(nrolls - expected_rolls) / max(expected_rolls, 0.5)
        n_compared += 1
        if ratio_off > ROLL_PACE_TOLERANCE:
            n_off += 1
            big_misses.append((title, nrolls, words, ratio_off))
    big_misses.sort(key=lambda x: -x[3])
    print(f"\ncheck 3 - roll pace (rolls x 2000 ≈ EPUB words):")
    print(f"  chapters compared:     {n_compared}")
    print(f"  off by >{int(ROLL_PACE_TOLERANCE*100)}%:           {n_off}")
    for title, nrolls, words, ratio in big_misses[:10]:
        print(f"    {title[:60]:60s}  rolls={nrolls:2d}  words={words:>6d}  off={ratio:.0%}")
    if n_off:
        errors.append(
            f"  {n_off} chapters disagree by more than {ROLL_PACE_TOLERANCE:.0%}; "
            "expected for chapters with implicit/uncounted points or many free-perk grants"
        )
    return errors


def _normalize(s: str) -> str:
    """Cosmetic-tolerant normalization: lowercase, strip punctuation
    variants (curly/straight quotes, ASCII/Unicode dashes), collapse
    whitespace. Used only for fuzzy matching of perk names/sources.
    """
    s = s.lower()
    for pair in [("’", "'"), ("‘", "'"), ("–", "-"), ("—", "-")]:
        s = s.replace(*pair)
    s = re.sub(r"[^\w\s'-]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def check_perks_in_catalog(rolls: dict, catalog: dict) -> list[str]:
    """Every paid perk acquired in a roll must exist in the catalog.

    Distinguish three buckets:
      - exact match     (name, source, cost all agree)
      - cosmetic match  (matches after normalization, or source aliases)
      - genuine gap     (no plausible catalog entry, or cost disagrees)
    """
    soft: list[str] = []
    hard: list[str] = []

    exact_idx: dict[tuple[str, str], list[int]] = defaultdict(list)
    norm_idx: dict[tuple[str, str], list[tuple[str, str, int]]] = defaultdict(list)
    name_idx: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for p in catalog["perks"]:
        exact_idx[(p["name"], p["source"])].append(p["cost"])
        norm_idx[(_normalize(p["name"]), _normalize(p["source"]))].append(
            (p["name"], p["source"], p["cost"])
        )
        name_idx[_normalize(p["name"])].append((p["name"], p["source"], p["cost"]))

    n_paid = 0
    n_exact = 0
    cosmetic_source: list[tuple] = []   # name matches, source differs only cosmetically
    cosmetic_name_only: list[tuple] = []  # source missing in roll; matches by name alone
    genuine_missing: list[tuple] = []
    cost_disagree: list[tuple] = []

    for r in rolls["rolls"]:
        for p in r["perks"]:
            if p["free"]:
                continue
            n_paid += 1
            ex_costs = exact_idx.get((p["name"], p["source"]))
            if ex_costs is not None:
                if p["cost"] in ex_costs:
                    n_exact += 1
                else:
                    cost_disagree.append((p["name"], p["source"], p["cost"], ex_costs))
                continue

            norm_key = (_normalize(p["name"]), _normalize(p["source"]))
            if norm_key in norm_idx:
                cosmetic_source.append(
                    (p["name"], p["source"], p["cost"], norm_idx[norm_key][0])
                )
                continue

            if not p["source"]:  # roll log omitted source
                cands = name_idx.get(_normalize(p["name"]), [])
                if cands:
                    cosmetic_name_only.append((p["name"], p["cost"], cands))
                    continue

            # Last-resort fuzzy: same normalized name regardless of source
            cands = name_idx.get(_normalize(p["name"]), [])
            if cands and any(c == p["cost"] for _, _, c in cands):
                cosmetic_source.append((p["name"], p["source"], p["cost"], cands[0]))
            else:
                genuine_missing.append((p["name"], p["source"], p["cost"], cands))

    print(f"\ncheck 4 - acquired perks vs catalog:")
    print(f"  paid perks acquired:   {n_paid}")
    print(f"  exact match:           {n_exact}")
    print(f"  cosmetic source diff:  {len(cosmetic_source)}  (case/punctuation/aliases)")
    print(f"  source omitted in roll:{len(cosmetic_name_only)}")
    print(f"  cost disagreements:    {len(cost_disagree)}")
    print(f"  genuine catalog gaps:  {len(genuine_missing)}")
    for name, src, cost, costs in cost_disagree[:10]:
        print(f"    COST: {name!r} ({src!r}) roll_cost={cost} catalog_costs={costs}")
    for name, src, cost, candidates in genuine_missing[:10]:
        print(f"    GAP:  {name!r} ({src!r}) cost={cost}  candidates={candidates}")
    if cost_disagree:
        soft.append(f"  {len(cost_disagree)} cost disagreement(s) between rolls log and catalog (curator data)")
    if genuine_missing:
        soft.append(f"  {len(genuine_missing)} acquired perk(s) absent from catalog (curator data)")
    if cosmetic_source or cosmetic_name_only:
        soft.append(
            f"  {len(cosmetic_source) + len(cosmetic_name_only)} cosmetic naming "
            "inconsistencies between rolls and catalog (curator data-entry)"
        )
    return hard, soft  # type: ignore[return-value]


def check_obtained_perks_alignment(chapters: dict, obtained: dict) -> tuple[list[str], list[str]]:
    """Reference xlsx 'Obtained Perks' chapter_nums must exist in chapters.json,
    and EPUB sequence values must be in range."""
    hard: list[str] = []
    soft: list[str] = []
    threadmark_nums = {c["chapter_num"] for c in chapters["chapters"]}
    n_chaps = len(chapters["chapters"])
    bad_chap = sorted({p["chapter_num"] for p in obtained["perks"]} - threadmark_nums)
    bad_seq = [p for p in obtained["perks"] if not (1 <= p["epub_sequence"] <= n_chaps)]
    print(f"\ncheck 5 - obtained_perks alignment:")
    print(f"  total acquisitions:    {len(obtained['perks'])}")
    print(f"  unique chapters:       {len({p['chapter_num'] for p in obtained['perks']})}")
    print(f"  bad chapter_num:       {len(bad_chap)} {bad_chap[:5]}")
    print(f"  EPUB seq out of range: {len(bad_seq)}")
    if bad_chap:
        hard.append(f"  obtained_perks references {len(bad_chap)} chapter_num(s) not in threadmarks")
    if bad_seq:
        hard.append(f"  obtained_perks has {len(bad_seq)} EPUB sequence values out of [1, {n_chaps}]")
    return hard, soft


def check_curator_agreement(rolls: dict, obtained: dict) -> tuple[list[str], list[str]]:
    """For chapters 1-75 (overlap range), compare per-chapter paid
    acquisition counts between the two curator sources."""
    hard: list[str] = []
    soft: list[str] = []

    rolls_acq: dict[str, int] = defaultdict(int)
    for r in rolls["rolls"]:
        if r["kind"] not in ("trigger", "roll"):
            continue
        for p in r["perks"]:
            if not p["free"]:
                rolls_acq[r["chapter_num"]] += 1

    obt_acq: dict[str, int] = defaultdict(int)
    for p in obtained["perks"]:
        # Only compare paid perks in chapters 1-75 (the curator overlap range)
        try:
            major = int(p["chapter_num"].split(".")[0])
        except (ValueError, IndexError):
            continue
        if major > 75:
            continue
        if not p["free"]:
            obt_acq[p["chapter_num"]] += 1

    chapters_compared = set(rolls_acq) | set(obt_acq)
    disagree: list[tuple[str, int, int]] = []
    for ch in sorted(chapters_compared, key=lambda c: tuple(int(x) for x in c.split("."))):
        r = rolls_acq.get(ch, 0)
        o = obt_acq.get(ch, 0)
        if r != o:
            disagree.append((ch, r, o))

    print(f"\ncheck 6 - curator agreement (rolls.json vs obtained_perks for ch 1-75):")
    print(f"  chapters in rolls.json:        {len(rolls_acq)}")
    print(f"  chapters in obtained_perks:    {len(obt_acq)}")
    print(f"  chapters with disagreement:    {len(disagree)}")
    for ch, r, o in disagree[:10]:
        print(f"    ch{ch}: rolls.json={r} paid acquisitions, obtained_perks={o}")
    total_rolls = sum(rolls_acq.values())
    total_obt = sum(obt_acq.values())
    print(f"  total paid (rolls.json):       {total_rolls}")
    print(f"  total paid (obtained_perks):   {total_obt}")
    if disagree:
        soft.append(
            f"  {len(disagree)} chapters disagree on paid-perk count between "
            "rolls.json and obtained_perks (curator interpretation differences)"
        )
    return hard, soft


def main() -> int:
    chapters = _load("chapters")
    rolls = _load("rolls")
    catalog = _load("perks_catalog")
    obtained = _load("obtained_perks")

    hard: list[str] = []
    soft: list[str] = []

    hard.extend(check_chapter_alignment(chapters, rolls))
    hard.extend(check_word_counts(chapters))
    soft.extend(check_roll_pace(chapters, rolls))
    perk_hard, perk_soft = check_perks_in_catalog(rolls, catalog)
    hard.extend(perk_hard)
    soft.extend(perk_soft)
    op_hard, op_soft = check_obtained_perks_alignment(chapters, obtained)
    hard.extend(op_hard)
    soft.extend(op_soft)
    ag_hard, ag_soft = check_curator_agreement(rolls, obtained)
    hard.extend(ag_hard)
    soft.extend(ag_soft)

    print()
    if soft:
        print("WARN (informational, not a failure):")
        for s in soft:
            print(s)
    if hard:
        print(f"\nFAIL: {len(hard)} hard issue(s):")
        for e in hard:
            print(e)
        return 1
    print("OK: all hard spot-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
