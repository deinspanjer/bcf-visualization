"""Build the chapter-grain fact table for the visualization.

This is the backbone of the planned scrubber UI: one row per published
chapter with sections and rolls as nested 1:N dimensions, plus a
top-level shadow_periods array (since regime-3 recovery shadows can
span chapter boundaries).

Joins:
  - chapters.json ............. real-world post metadata
  - chapter_sections.json ..... section word counts + classification
  - section_classifications.json  counts_for_cp truth
  - rolls.json ................ curator hit/miss roll log when available
  - roll_outcomes.json ........ interpolated fallback hit/miss sequence
  - roll_text_evidence.json ... predicted rolls + prose anchor info
  - obtained_perks.json ....... acquisitions used by fallback derivation
  - perk_directory.json ....... canonical perk IDs and constellations
  - outstanding_perks_by_chapter.json  miss-size estimates
  - chapter_last_edited.json .. SV edit timestamps

In-world dates are stubbed out (every field null, confidence="stub").
A future derivation pass will populate them.

Output:
  - data/derived/chapter_facts.json (validated)

Roll attribution:
  For chapters covered by the curator roll log, use that sequential
  HIT/MISS log directly. For later chapters, use roll_outcomes.json,
  which interpolates hit/miss timing from predicted rolls and paid
  acquisitions. Free perks attach to the paid hit and do not occupy
  independent roll slots.
"""

from __future__ import annotations

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
ROLL_FACTS = ROOT / "data" / "derived" / "roll_facts.json"
LAST_EDITED = ROOT / "data" / "derived" / "chapter_last_edited.json"
TIMELINE = ROOT / "data" / "derived" / "timeline.json"
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
    roll_facts_doc = json.loads(ROLL_FACTS.read_text())
    last_edited = json.loads(LAST_EDITED.read_text())["chapters"]
    last_edited_by_chap = {r["chapter_num"]: r for r in last_edited}

    # Canonical in-world timeline: built upstream by scripts/derive_timeline.py
    # by merging xlsx + wiki + TUI annotations + manual entries. We embed it
    # verbatim into chapter_facts so the visualization loads a single file.
    if not TIMELINE.exists():
        raise SystemExit(
            f"missing {TIMELINE.relative_to(ROOT)} — "
            "run `python scripts/derive_timeline.py` first"
        )
    timeline_doc = json.loads(TIMELINE.read_text())
    in_world_timeline = {
        "_sources_used":         timeline_doc["_sources_used"],
        "_count":                timeline_doc["_count"],
        "_first_in_world_date":  timeline_doc["_first_in_world_date"],
        "_last_in_world_date":   timeline_doc["_last_in_world_date"],
        "entries":               timeline_doc["entries"],
    }

    rolls_by_chapter: dict[str, list[dict]] = {}
    for roll in roll_facts_doc["rolls"]:
        rolls_by_chapter.setdefault(roll["chapter_num"], []).append(roll)
    for rolls in rolls_by_chapter.values():
        rolls.sort(key=lambda r: (
            r["roll_sequence_in_chapter"],
            r["source_row_index"],
        ))

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
        chapter_cp_start = cum_cp_words
        chapter_cp_words = sum(s["cp_earning_word_count"] for s in sections_out)
        chap_roll_facts = rolls_by_chapter.get(cn, [])
        rolls_out: list[dict] = []
        hits = 0
        misses = 0
        unknowns = 0
        paid_count_in_chap = 0
        free_count_in_chap = 0
        banked_cp_at_start = None
        banked_cp_at_end = None

        def _display_cp_position(index: int, total: int) -> int | None:
            if chapter_cp_words <= 0 or total <= 0:
                return None
            fraction = (index + 1) / (total + 1)
            return int(round(chapter_cp_start + chapter_cp_words * fraction))

        def _section_index_for_roll(roll: dict) -> int | None:
            char_offset = roll.get("predicted_char_offset_in_chapter")
            if char_offset is None:
                return None
            for i, (s_start, s_end) in enumerate(sections_html_offsets):
                if s_start <= char_offset < s_end:
                    return i
            return None

        def _append_shadow_if_needed(roll: dict) -> None:
            cost = roll["purchased_perk_cost"]
            if (cost not in SHADOW_TRIGGER_COSTS
                    or int(cn.split(".")[0]) < SHADOW_TRIGGER_MIN_CHAPTER):
                return
            start_pos = (
                roll["display_word_position_epub"]
                if roll["display_word_position_epub"] is not None
                else roll["predicted_word_position_epub"]
            )
            shadow_words = (cost // 2) * (REGIME_3_WORDS_PER_100_CP // 100)
            shadow_periods.append({
                "trigger_perk_id": roll["purchased_perk_id"],
                "trigger_perk_name": roll["purchased_perk_name"],
                "trigger_perk_cost": cost,
                "trigger_chapter_num": cn,
                "trigger_word_position_epub": start_pos,
                "shadow_word_length": shadow_words,
                "shadow_end_word_position_epub": (
                    start_pos + shadow_words if start_pos is not None else None
                ),
                "shadow_end_chapter_num": None,
            })

        for idx, roll in enumerate(chap_roll_facts):
            if idx == 0:
                banked_cp_at_start = roll.get("available_cp")
            banked_cp_at_end = roll.get("banked_cp_after_roll")
            display_pos = _display_cp_position(idx, len(chap_roll_facts))
            roll_record = {
                "roll_number": roll["roll_number"],
                "section_index": _section_index_for_roll(roll),
                "outcome": roll["outcome"],
                "constellation": roll["constellation"],
                "purchased_perk_id": roll["purchased_perk_id"],
                "purchased_perk_name": roll["purchased_perk_name"],
                "purchased_perk_cost": roll["purchased_perk_cost"],
                "purchased_perk_jump": roll["purchased_perk_jump"],
                "free_perks": roll["free_perks"],
                "predicted_word_position_epub": roll["predicted_word_position_epub"],
                "display_word_position_epub": display_pos,
                "predicted_char_offset_in_chapter": roll["predicted_char_offset_in_chapter"],
                "anchor_char_offset_in_chapter": roll["anchor_char_offset_in_chapter"],
                "evidence_kind": roll["evidence_kind"],
                "available_cp": roll["available_cp"],
                "banked_cp_after_roll": roll["banked_cp_after_roll"],
                "rolled_perk_name": roll["rolled_perk_name"],
                "rolled_perk_cost": roll["rolled_perk_cost"],
                "miss_cost_estimate": roll["miss_cost_estimate"],
                "roll_sequence_in_chapter": roll["roll_sequence_in_chapter"],
                "rolls_in_chapter": roll["rolls_in_chapter"],
                "fact_source": roll["source"],
                "source_kind": roll["source_kind"],
            }
            rolls_out.append(roll_record)
            if roll["outcome"] == "hit":
                hits += 1
                paid_count_in_chap += 1
                free_count_in_chap += len(roll["free_perks"])
                _append_shadow_if_needed(roll_record)
            elif roll["outcome"] == "miss":
                misses += 1
            else:
                unknowns += 1

        # ---------- chapter row ----------
        last_ed = last_edited_by_chap.get(cn, {})
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
            "banked_cp_at_start": banked_cp_at_start,
            "banked_cp_at_end": banked_cp_at_end,

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
            "section_classifications.json + roll_facts.json + "
            "chapter_last_edited.json. Roll facts are pre-reconciled "
            "upstream: curator roll rows win where present, and "
            "interpolated rows are provenance-marked fallback. Free perks "
            "attach to their paid hit. In-world dates are stubbed (every "
            "field null, confidence='stub') pending a separate derivation."
        ),
        "_count": len(out_chapters),
        "_grain": "published chapter",
        "_deferred": [
            "in_world.* — stubbed; needs chapter→date derivation pass",
            "banked_cp_at_start/end — populated only where roll_facts has banked CP",
            "shadow_periods.shadow_end_chapter_num approximate (uses total-word boundaries vs cp-word boundaries)",
        ],
        "shadow_periods": shadow_periods,
        "in_world_timeline": in_world_timeline,
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
    total_misses = sum(c["misses_count"] for c in out_chapters)
    print(
        f"  rolls: {total_rolls} "
        f"({total_hits} hit, {total_misses} miss, {total_unknowns} unknown)"
    )
    print(f"  perks: {total_paid} paid + {total_free} free = {total_paid + total_free}")
    print(f"  shadow_periods: {len(shadow_periods)}")
    print(f"  in_world_timeline: {in_world_timeline['_count']} entries "
          f"from sources {in_world_timeline['_sources_used']} "
          f"({in_world_timeline['_first_in_world_date']} .. "
          f"{in_world_timeline['_last_in_world_date']})")
    pov_set = set()
    for c in out_chapters:
        pov_set.update(c["pov_characters"])
    print(f"  distinct POVs: {len(pov_set)} ({sorted(pov_set)[:8]}...)")


if __name__ == "__main__":
    main()
