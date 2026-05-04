"""Build the chapter-grain fact table for the visualization.

This is the backbone of the planned scrubber UI: one row per published
chapter with sections and rolls as nested 1:N dimensions, plus a
top-level shadow_periods array (since regime-3 recovery shadows can
span chapter boundaries).

Joins:
  - chapters.json ............. real-world post metadata
  - chapter_sections.json ..... section word counts + classification
  - section_classifications.json  counts_for_cp truth
  - roll_text_evidence.json ... predicted rolls + prose anchor info
  - obtained_perks.json ....... acquisitions (paid + free siblings)
  - perk_directory.json ....... canonical perk IDs and constellations
  - chapter_last_edited.json .. SV edit timestamps

In-world dates are stubbed out (every field null, confidence="stub").
A future derivation pass will populate them.

Output:
  - data/derived/chapter_facts.json (validated)

Roll attribution heuristic (per spec):
  Within a chapter, sort paid acquisitions by epub_sequence and
  predicted rolls by predicted_word_position_epub. Pair the i-th
  acquisition with the i-th predicted roll → outcome="hit". Surplus
  predicted rolls → outcome="unknown" (we lack the prose-evidence to
  classify them as miss without confirmation). Free perks attach to
  the same roll as their paid sibling (matched by epub_sequence).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import zipfile
from pathlib import Path

from _common import write_validated_json
from find_roll_locations import _build_chapter_index, _split_sections

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
SECTIONS = ROOT / "data" / "derived" / "chapter_sections.json"
CLASSIFICATIONS = ROOT / "data" / "manual" / "section_classifications.json"
EVIDENCE = ROOT / "data" / "derived" / "roll_text_evidence.json"
OBTAINED = ROOT / "data" / "derived" / "obtained_perks.json"
DIRECTORY = ROOT / "data" / "derived" / "perk_directory.json"
LAST_EDITED = ROOT / "data" / "derived" / "chapter_last_edited.json"
OUT = ROOT / "data" / "derived" / "chapter_facts.json"


# ---------- regime + shadow constants (mirroring predict_rolls.py) ---------

def regime_for_chapter(chap_num: str) -> int:
    a, _, b = chap_num.partition(".")
    n = int(a)
    if n <= 91:
        return 1
    if n <= 96:
        return 2
    return 3


# Regime 3 words-per-CP and shadow ratio (per README mechanic notes).
REGIME_3_WORDS_PER_100_CP = 3000
SHADOW_TRIGGER_COSTS = {600, 800}
SHADOW_TRIGGER_MIN_CHAPTER = 97   # rule introduced in ch97 author note


# ---------- header parsing -------------------------------------------------

_NAME_RE = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
_MARKER_RE = re.compile(
    rf"\b(Preamble|Addendum|Interlude)\s+({_NAME_RE})"
)
_TITLE_RE = re.compile(r"^\s*\d+(\.\d+)?\s+[A-Z]")


def parse_marker_kind(header: str | None, full_title: str) -> str:
    """Categorize a section header into a fixed enum."""
    if header is None:
        return "main_implicit"
    h = header.strip()
    if h == full_title or _TITLE_RE.match(h):
        return "main_titled"
    hl = h.lower()
    if "jumpchain abilities" in hl or "new abilities for" in hl:
        return "abilities"
    if "author" in hl and "note" in hl:
        return "author_note"
    if "preamble" in hl:
        return "preamble"
    if "addendum" in hl:
        return "addendum"
    if "interlude" in hl:
        return "interlude"
    return "other"


def parse_pov_character(header: str | None, full_title: str) -> str | None:
    """Best-effort POV character from a section header.

    None means the section is non-narrative (perk listing, author note).
    For headers with multiple marker subjects (e.g. 'Interlude Lily -
    Addendum Joe') we take the first marker's subject — the user
    confirmed POV stays as the header indicates and rare omniscient
    narration (e.g. ch 119.4 Elle) is fine.
    """
    if header is None:
        return "Joe"
    h = header.strip()
    if h == full_title or _TITLE_RE.match(h):
        return "Joe"
    hl = h.lower()
    if "jumpchain abilities" in hl or "new abilities for" in hl:
        return None
    if "author" in hl and "note" in hl:
        return None
    m = _MARKER_RE.search(h)
    if m:
        return m.group(2).strip()
    return None


# ---------- main builder ---------------------------------------------------

def main() -> None:
    if not EPUB.exists():
        raise SystemExit(f"missing {EPUB.relative_to(ROOT)}")

    chapters = json.loads(CHAPTERS.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    sections_data = json.loads(SECTIONS.read_text())
    sections_by_chap = {c["chapter_num"]: c for c in sections_data["chapters"]}

    classifications = json.loads(CLASSIFICATIONS.read_text())["classifications"]
    evidence = json.loads(EVIDENCE.read_text())["rolls"]
    evidence_by_roll = {e["roll_number"]: e for e in evidence}

    obtained = json.loads(OBTAINED.read_text())["perks"]
    directory = json.loads(DIRECTORY.read_text())["perks"]
    last_edited = json.loads(LAST_EDITED.read_text())["chapters"]
    last_edited_by_chap = {r["chapter_num"]: r for r in last_edited}

    # perk_directory id lookup: (perk_name, jump) → id (and constellation)
    perk_id_by_name_jump: dict[tuple[str, str], dict] = {}
    for p in directory:
        key = (p["name"].strip().lower(), p["jump"].strip().lower())
        perk_id_by_name_jump[key] = p

    # Walk obtained_perks IN ORDER and bucket each paid perk with its
    # trailing free siblings into an "acquisition unit". Within a
    # chapter, paid perks appear in author/curator order; each free
    # perk that follows a paid attaches to that paid until the next
    # paid starts a new unit.
    #
    # Verified shape: ch 1 = [paid Workshop, free Access Key, free
    # Entrance Hall] → 1 unit. Ch 2 = [paid Fashion, paid Bling of War,
    # paid Alchemist] → 3 units, each with 0 free siblings.
    acquisition_units: list[dict] = []   # global list, in obtained_perks order
    current_unit: dict | None = None
    for o in obtained:
        if not o["free"]:
            current_unit = {
                "chapter_num": o["chapter_num"],
                "paid": o,
                "free_siblings": [],
            }
            acquisition_units.append(current_unit)
        else:
            if current_unit is None or current_unit["chapter_num"] != o["chapter_num"]:
                # Free perk without a preceding paid in the same chapter —
                # rare or impossible by spec, but log + skip rather than
                # crash. (We could attach to a synthetic placeholder;
                # this hasn't been observed in the data.)
                raise SystemExit(
                    f"orphan free perk {o['perk_name']!r} in ch {o['chapter_num']} — "
                    "no preceding paid acquisition in same chapter"
                )
            current_unit["free_siblings"].append(o)

    # Index by chapter, preserving order.
    units_by_chapter: dict[str, list[dict]] = {}
    for u in acquisition_units:
        units_by_chapter.setdefault(u["chapter_num"], []).append(u)

    # Group predicted rolls by chapter (already in word-position order).
    rolls_by_chapter: dict[str, list[dict]] = {}
    for ev in evidence:
        rolls_by_chapter.setdefault(ev["chapter_num"], []).append(ev)
    for rolls_list in rolls_by_chapter.values():
        rolls_list.sort(key=lambda r: r["predicted_word_position_epub"])

    # Open EPUB once; for each chapter compute section char-offsets.
    chapter_section_offsets: dict[str, list[tuple[int, int]]] = {}
    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            href = title_to_href.get(c["full_title"])
            if not href:
                chapter_section_offsets[c["chapter_num"]] = []
                continue
            html = zf.read(f"EPUB/{href}").decode("utf-8")
            offsets = [(s, e) for _h, s, e in _split_sections(html)]
            chapter_section_offsets[c["chapter_num"]] = offsets

    # Build per-chapter rows and accumulate running totals + shadow periods.
    out_chapters: list[dict] = []
    cum_words = 0
    cum_cp_words = 0
    cum_perks = 0
    shadow_periods: list[dict] = []

    for c in chapters:
        cn = c["chapter_num"]
        sec_meta = sections_by_chap[cn]
        sections_html_offsets = chapter_section_offsets.get(cn, [])

        # ---------- sections ----------
        sections_out: list[dict] = []
        pov_set: set[str] = set()
        marker_kinds_seen: list[str] = []
        struct_markers_aggregate: set[str] = set()
        for i, s in enumerate(sec_meta["sections"]):
            cls = classifications.get(f"{cn}@{i}", {})
            counts_for_cp = bool(cls.get("counts_for_cp", False))
            mk = parse_marker_kind(s.get("header"), c["full_title"])
            pov = parse_pov_character(s.get("header"), c["full_title"])
            if pov:
                pov_set.add(pov)
            marker_kinds_seen.append(mk)
            for sm in s.get("structural_markers") or []:
                struct_markers_aggregate.add(sm)
            cs, ce = (sections_html_offsets[i]
                      if i < len(sections_html_offsets) else (0, 0))
            sections_out.append({
                "section_index": i,
                "header": s.get("header"),
                "marker_kind": mk,
                "pov_character": pov,
                "word_count": s["word_count"],
                "cp_earning_word_count": s["word_count"] if counts_for_cp else 0,
                "counts_for_cp": counts_for_cp,
                "classification": s.get("classification"),
                "classification_confidence": s.get("confidence"),
                "structural_markers": s.get("structural_markers") or [],
                "char_offset_start_in_chapter": cs,
                "char_offset_end_in_chapter": ce,
                "in_world_start_time_of_day": None,    # stubbed
                "in_world_end_time_of_day": None,      # stubbed
            })

        # ---------- rolls + attribution ----------
        chap_predicted = rolls_by_chapter.get(cn, [])
        chap_units = units_by_chapter.get(cn, [])
        rolls_out: list[dict] = []
        hits = 0
        misses = 0
        unknowns = 0
        paid_count_in_chap = len(chap_units)
        free_count_in_chap = 0

        def _attribute_unit(unit: dict) -> dict:
            """Resolve paid perk metadata and free-perk structs for a unit.

            Free perks rarely have their own perk_directory entry (the
            directory promotes only the canonical 416 perks; free
            ride-alongs live as acquired_instances of their parent).
            We surface the free perk's name+jump+constellation so the
            visualization can render them in tooltips without a join.
            """
            paid_perk = unit["paid"]
            name = paid_perk["perk_name"]
            cons = paid_perk.get("constellation")
            key = (name.strip().lower(), paid_perk["jump"].strip().lower())
            paid_dir = perk_id_by_name_jump.get(key)
            free_perks_out: list[dict] = []
            for f in unit["free_siblings"]:
                fkey = (f["perk_name"].strip().lower(),
                        f["jump"].strip().lower())
                fdir = perk_id_by_name_jump.get(fkey)
                free_perks_out.append({
                    "id": fdir["id"] if fdir else None,
                    "name": f["perk_name"],
                    "jump": f["jump"],
                    "constellation": f.get("constellation"),
                })
            return {
                "id": paid_dir["id"] if paid_dir else None,
                "name": name,
                "jump": paid_dir["jump"] if paid_dir else paid_perk["jump"],
                "constellation": cons,
                "cost": paid_dir["cost"] if paid_dir else paid_perk.get("cost"),
                "free_perks": free_perks_out,
            }

        # Pair the first min(predicted, units) regime-rolls with paid
        # acquisitions in chapter order. Surplus predicted rolls
        # become outcome=unknown. Surplus paid acquisitions (the
        # chapters where the simulator excludes the chapter from CP
        # earning despite an acquisition being tagged here) become
        # synthetic rolls with evidence_kind=untracked_acquisition.
        n_paired = min(len(chap_predicted), len(chap_units))

        for idx in range(len(chap_predicted)):
            ev_row = chap_predicted[idx]
            unit = chap_units[idx] if idx < n_paired else None
            outcome = "hit" if unit is not None else "unknown"
            constellation = None
            purchased_perk_id = None
            purchased_perk_name = None
            purchased_perk_cost = None
            purchased_perk_jump = None
            free_perks: list[str] = []
            if unit is not None:
                paid_meta = _attribute_unit(unit)
                purchased_perk_id = paid_meta["id"]
                purchased_perk_name = paid_meta["name"]
                purchased_perk_cost = paid_meta["cost"]
                purchased_perk_jump = paid_meta["jump"]
                constellation = paid_meta["constellation"]
                free_perks = paid_meta["free_perks"]
                free_count_in_chap += len(free_perks)

            sec_idx = 0
            for i, (s_start, s_end) in enumerate(sections_html_offsets):
                if s_start <= ev_row["predicted_char_offset"] < s_end:
                    sec_idx = i
                    break

            anchor_offset = None
            if ev_row["matching_events"]:
                anchor_offset = ev_row["matching_events"][0]["anchor_offset"]

            ev_kind = ev_row["evidence_kind"]
            if ev_kind == "no_evidence":
                ev_kind = "silent"

            rolls_out.append({
                "roll_number": ev_row["roll_number"],
                "section_index": sec_idx,
                "outcome": outcome,
                "constellation": constellation,
                "purchased_perk_id": purchased_perk_id,
                "purchased_perk_name": purchased_perk_name,
                "purchased_perk_cost": purchased_perk_cost,
                "purchased_perk_jump": purchased_perk_jump,
                "free_perks": free_perks,
                "predicted_word_position_epub": ev_row["predicted_word_position_epub"],
                "predicted_char_offset_in_chapter": ev_row["predicted_char_offset"],
                "anchor_char_offset_in_chapter": anchor_offset,
                "evidence_kind": ev_kind,
            })

            if outcome == "hit":
                hits += 1
                paid_perk = unit["paid"]
                if (paid_perk.get("cost") in SHADOW_TRIGGER_COSTS
                        and int(cn.split(".")[0]) >= SHADOW_TRIGGER_MIN_CHAPTER):
                    shadow_words = (paid_perk["cost"] // 2) * (
                        REGIME_3_WORDS_PER_100_CP // 100)
                    start_pos = ev_row["predicted_word_position_epub"]
                    end_pos = start_pos + shadow_words
                    shadow_periods.append({
                        "trigger_perk_id": purchased_perk_id,
                        "trigger_perk_name": purchased_perk_name,
                        "trigger_perk_cost": paid_perk["cost"],
                        "trigger_chapter_num": cn,
                        "trigger_word_position_epub": start_pos,
                        "shadow_word_length": shadow_words,
                        "shadow_end_word_position_epub": end_pos,
                        "shadow_end_chapter_num": None,
                    })
            elif outcome == "unknown":
                unknowns += 1
            else:
                misses += 1   # not currently produced; kept for future

        # Synthetic rolls for paid acquisitions tagged to this chapter
        # but not paired with a regime-simulator roll. These represent
        # the curator/author bookkeeping where Joe banked CP in earlier
        # MC chapters and the author narrates the acquisition here.
        for surplus_unit in chap_units[n_paired:]:
            paid_meta = _attribute_unit(surplus_unit)
            purchased_perk_id = paid_meta["id"]
            purchased_perk_name = paid_meta["name"]
            purchased_perk_cost = paid_meta["cost"]
            purchased_perk_jump = paid_meta["jump"]
            constellation = paid_meta["constellation"]
            free_perks = paid_meta["free_perks"]
            free_count_in_chap += len(free_perks)
            paid_perk = surplus_unit["paid"]
            rolls_out.append({
                "roll_number": None,                       # no global ordering
                "section_index": None,                     # position unknown
                "outcome": "hit",
                "constellation": constellation,
                "purchased_perk_id": purchased_perk_id,
                "purchased_perk_name": purchased_perk_name,
                "purchased_perk_cost": purchased_perk_cost,
                "purchased_perk_jump": purchased_perk_jump,
                "free_perks": free_perks,
                "predicted_word_position_epub": None,
                "predicted_char_offset_in_chapter": None,
                "anchor_char_offset_in_chapter": None,
                "evidence_kind": "untracked_acquisition",
            })
            hits += 1
            # Shadow period: regime-3 600/800 acquisitions with no
            # regime-simulator roll still produce a shadow. Anchor
            # the shadow at the chapter's first word position as an
            # approximation (the precise narrated position is unknown).
            if (paid_perk.get("cost") in SHADOW_TRIGGER_COSTS
                    and int(cn.split(".")[0]) >= SHADOW_TRIGGER_MIN_CHAPTER):
                shadow_words = (paid_perk["cost"] // 2) * (
                    REGIME_3_WORDS_PER_100_CP // 100)
                # Approximate trigger word position by chapter cumulative
                # start (exact position unknown).
                start_pos_approx = None  # filled in second pass below
                shadow_periods.append({
                    "trigger_perk_id": purchased_perk_id,
                    "trigger_perk_name": purchased_perk_name,
                    "trigger_perk_cost": paid_perk["cost"],
                    "trigger_chapter_num": cn,
                    "trigger_word_position_epub": start_pos_approx,  # patched below
                    "shadow_word_length": shadow_words,
                    "shadow_end_word_position_epub": None,           # patched below
                    "shadow_end_chapter_num": None,                  # patched below
                })

        # ---------- chapter row ----------
        last_ed = last_edited_by_chap.get(cn, {})
        # Use the manual-classification-aware CP word count (matches
        # predict_rolls.py's coordinate system). chapter_sections.json's
        # cp_earning_word_count is rule-based and disagrees in the
        # ~21 chapters where the manual classifier overrides.
        chapter_cp_words = sum(s["cp_earning_word_count"] for s in sections_out)
        cum_words += sec_meta["total_word_count"]
        cum_cp_words += chapter_cp_words
        cum_perks += paid_count_in_chap + free_count_in_chap

        out_chapters.append({
            "chapter_num": cn,
            "full_title": c["full_title"],
            "sort_key": c["sort_key"],
            "point_calculation_regime": regime_for_chapter(cn),
            "epub_href": title_to_href.get(c["full_title"], ""),

            "published_at": c["publish_iso"],
            "last_edited_at": last_ed.get("last_edited_at"),
            "last_edited_known": last_ed.get("last_edited_known", False),
            "edited_lag_days": last_ed.get("edited_lag_days"),
            "post_url": c.get("post_url", ""),
            "likes": c.get("likes", 0),

            "in_world": {
                "start_date": None,
                "start_time_of_day": None,
                "end_date": None,
                "end_time_of_day": None,
                "spans_days": None,
                "confidence": "stub",
                "evidence": None,
            },

            "total_word_count": sec_meta["total_word_count"],
            "cp_earning_word_count": chapter_cp_words,
            "rolls_count": len(rolls_out),
            "hits_count": hits,
            "misses_count": misses,
            "unknowns_count": unknowns,
            "perks_gained": paid_count_in_chap + free_count_in_chap,
            "paid_perks_gained": paid_count_in_chap,
            "free_perks_gained": free_count_in_chap,

            "cumulative_words_through_chapter": cum_words,
            "cumulative_cp_earning_words": cum_cp_words,
            "cumulative_perks_through_chapter": cum_perks,
            # Banked CP at start/end deferred — replicating the regime
            # simulator's shadow-aware state machine here would
            # duplicate predict_rolls.py. v2 will either re-export the
            # state from predict_rolls or import its simulator.
            "banked_cp_at_start": None,
            "banked_cp_at_end": None,

            "pov_characters": sorted(pov_set),
            "structural_markers": sorted(struct_markers_aggregate),

            "sections": sections_out,
            "rolls": rolls_out,
        })

    # Resolve shadow_periods.shadow_end_chapter_num. predicted_rolls'
    # word_position is cumulative CP-earning words across the EPUB, so
    # we build a parallel cumulative-CP-words index for the lookup —
    # mismatched units (CP-words vs total words) was a v0 bug.
    chapter_cp_starts: dict[str, int] = {}
    cum_cp = 0
    for c in out_chapters:
        chapter_cp_starts[c["chapter_num"]] = cum_cp
        cum_cp += c["cp_earning_word_count"]
    chap_order = [c["chapter_num"] for c in out_chapters]

    def chapter_at(cp_word_pos: int) -> str | None:
        for i, ch in enumerate(chap_order):
            start = chapter_cp_starts[ch]
            end = chapter_cp_starts[chap_order[i + 1]] if i + 1 < len(chap_order) else cum_cp
            if start <= cp_word_pos < end:
                return ch
        return None

    for sp in shadow_periods:
        # Patch any synthetic-acquisition shadows with chapter-start
        # word positions. (regime-simulator-anchored shadows already
        # have their start position set.)
        if sp["trigger_word_position_epub"] is None:
            sp["trigger_word_position_epub"] = chapter_cp_starts.get(
                sp["trigger_chapter_num"], 0)
        if sp["shadow_end_word_position_epub"] is None:
            sp["shadow_end_word_position_epub"] = (
                sp["trigger_word_position_epub"] + sp["shadow_word_length"]
            )
        sp["shadow_end_chapter_num"] = (
            chapter_at(sp["shadow_end_word_position_epub"])
            or sp["trigger_chapter_num"]
        )

    payload = {
        "_source": (
            "Chapter-grain fact table for the visualization. One row "
            "per published chapter with sections and rolls as nested "
            "1:N dimensions; shadow_periods are top-level because they "
            "can span chapters."
        ),
        "_method": (
            "Cross-join of chapters.json + chapter_sections.json + "
            "section_classifications.json + roll_text_evidence.json + "
            "obtained_perks.json + perk_directory.json + "
            "chapter_last_edited.json. Roll attribution: within a "
            "chapter, sort paid acquisitions by epub_sequence and "
            "predicted rolls by predicted_word_position_epub; pair "
            "i-th to i-th. Surplus predicted rolls are outcome=unknown. "
            "Free perks attach to their epub_sequence-sibling paid "
            "roll. In-world dates are stubbed (every field null, "
            "confidence='stub') pending a separate derivation."
        ),
        "_count": len(out_chapters),
        "_grain": "published chapter",
        "_deferred": [
            "in_world.* — stubbed; needs chapter→date derivation pass",
            "banked_cp_at_start/end — null; needs replicated regime simulator state",
            "shadow_periods.shadow_end_chapter_num approximate (uses total-word boundaries vs cp-word boundaries)",
        ],
        "shadow_periods": shadow_periods,
        "chapters": out_chapters,
    }

    write_validated_json(OUT, payload, "chapter_facts")

    # Console summary
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out_chapters)} chapters")
    total_rolls = sum(c["rolls_count"] for c in out_chapters)
    total_hits = sum(c["hits_count"] for c in out_chapters)
    total_unknowns = sum(c["unknowns_count"] for c in out_chapters)
    total_paid = sum(c["paid_perks_gained"] for c in out_chapters)
    total_free = sum(c["free_perks_gained"] for c in out_chapters)
    print(f"  rolls: {total_rolls} ({total_hits} hit, {total_unknowns} unknown)")
    print(f"  perks: {total_paid} paid + {total_free} free = {total_paid + total_free}")
    print(f"  shadow_periods: {len(shadow_periods)}")
    pov_set = set()
    for c in out_chapters:
        pov_set.update(c["pov_characters"])
    print(f"  distinct POVs: {len(pov_set)} ({sorted(pov_set)[:8]}...)")


if __name__ == "__main__":
    main()
