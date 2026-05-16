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
  - chapter_publication_dates.json  publish + last-edit dates (manual)

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

import datetime as dt
import json
import re
import zipfile
from collections import Counter

from _common import write_validated_json
from data_paths import DERIVED, MANUAL, RAW, ROOT
from data_release import refresh_current_runtime_manifest
from eligibility_spans import (
    merge_word_ranges,
    section_cp_word_count,
    section_span_overrides,
)
from find_roll_locations import _build_chapter_index, _split_sections

EPUB = RAW / "Brocktons_Celestial_Forge.epub"
CHAPTERS = DERIVED / "chapters.json"
SECTIONS = DERIVED / "chapter_sections.json"
CLASSIFICATIONS = MANUAL / "section_classifications.json"
ROLL_FACTS = DERIVED / "roll_facts.json"
ROLL_VALIDATION = DERIVED / "roll_validation.json"
PREDICTED_ROLLS = DERIVED / "predicted_rolls.json"
CHAPTER_ROLL_OVERRIDES = MANUAL / "chapter_roll_overrides.json"
OBTAINED_PERKS = DERIVED / "obtained_perks.json"
PERK_DIRECTORY = DERIVED / "perk_directory.json"
PUBLICATION_DATES = MANUAL / "chapter_publication_dates.json"
TIMELINE = DERIVED / "timeline.json"
OUT = DERIVED / "chapter_facts.json"

CONSTELLATION_ORDER = [
    "Toolkits", "Knowledge", "Vehicles", "Time", "Crafting",
    "Clothing", "Magic", "Quality", "Size",
    "Resources and Durability", "Magitech", "Alchemy",
    "Capstone", "Personal Reality",
]


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


def _chapter_key(chapter_num: str | None) -> tuple[int, int]:
    if not chapter_num:
        return (0, 0)
    head, _, tail = str(chapter_num).partition(".")
    return (int(head or 0), int(tail or 0))


def _countable_directory_perk(perk: dict) -> bool:
    return (
        not perk.get("free", False)
        and perk.get("cost") is not None
        and perk.get("status") != "Locked"
    )


def _roll_constellation_counts(rolls: list[dict]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for roll in rolls:
        if roll.get("outcome") != "hit" and roll.get("evidence_kind") != "untracked_acquisition":
            continue
        for perk in roll.get("purchased_perks") or []:
            constellation = perk.get("constellation") or roll.get("constellation")
            if constellation:
                counts[constellation] += 1
        for perk in roll.get("free_perks") or []:
            constellation = perk.get("constellation") or roll.get("constellation")
            if constellation:
                counts[constellation] += 1
    return counts


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


def _range_overlap_len(
    ranges: list[tuple[int, int]], start: int, end: int
) -> int:
    return sum(max(0, min(r_end, end) - max(r_start, start)) for r_start, r_end in ranges)


def _story_section_word_count(
    *,
    word_count: int,
    section_start: int,
    section_end: int,
    marker_kind: str,
    classification: str | None,
    span_overrides: list[dict],
) -> int:
    """Words that belong on the visualization's story-word axis.

    ``chapter_sections.json`` preserves raw EPUB section counts for curator
    navigation. ``chapter_facts.json`` is the web runtime contract, so its
    word axis excludes meta sections and passage-level ineligible spans
    such as section headers and author notes.
    """
    if marker_kind in {"abilities", "author_note"}:
        return 0
    if classification == "non_mc_meta":
        return 0
    excluded_ranges = merge_word_ranges([
        (int(span["word_offset_start"]), int(span["word_offset_end"]))
        for span in span_overrides
        if not bool(span.get("counts_for_cp"))
    ])
    excluded_in_section = _range_overlap_len(
        excluded_ranges,
        section_start,
        section_end,
    )
    return max(0, word_count - excluded_in_section)


def _chapter_story_word_count(
    *,
    chapter_num: str,
    full_title: str,
    sec_meta: dict,
    classifications: dict[str, dict],
) -> int:
    total = 0
    sec_word_start = 0
    for i, s in enumerate(sec_meta["sections"]):
        word_count = int(s["word_count"])
        sec_word_end = sec_word_start + word_count
        marker_kind = parse_marker_kind(s.get("header"), full_title)
        cls = classifications.get(f"{chapter_num}@{i}", {})
        total += _story_section_word_count(
            word_count=word_count,
            section_start=sec_word_start,
            section_end=sec_word_end,
            marker_kind=marker_kind,
            classification=s.get("classification"),
            span_overrides=section_span_overrides(
                cls,
                sec_word_start,
                sec_word_end,
            ),
        )
        sec_word_start = sec_word_end
    return total


def _load_chapter_roll_overrides() -> dict[str, dict]:
    if not CHAPTER_ROLL_OVERRIDES.exists():
        return {}
    data = json.loads(CHAPTER_ROLL_OVERRIDES.read_text())
    return {
        str(chapter_num): override
        for chapter_num, override
        in data.get("chapter_roll_overrides", {}).items()
        if isinstance(override, dict)
    }


def _predicted_rolls_by_chapter(predicted_doc: dict) -> dict[str, list[dict]]:
    by_chapter: dict[str, list[dict]] = {}
    for roll in predicted_doc.get("predicted", []):
        chapter_num = str(roll.get("chapter_num"))
        if not chapter_num:
            continue
        by_chapter.setdefault(chapter_num, []).append(roll)
    for rolls in by_chapter.values():
        rolls.sort(key=lambda roll: int(roll.get("word_position") or 0))
    return by_chapter


def _skipped_predicted_roll_markers(
    chapter_num: str,
    predicted_rolls: list[dict],
    override: dict | None,
    *,
    chapter_cp_start: int,
) -> list[dict]:
    markers: list[dict] = []
    if not override:
        return markers
    for slot_index, roll_override in enumerate(override.get("rolls") or [], start=1):
        if not isinstance(roll_override, dict) or not roll_override.get("skipped"):
            continue
        predicted_index = slot_index - 1
        if predicted_index < 0 or predicted_index >= len(predicted_rolls):
            continue
        predicted_roll = predicted_rolls[predicted_index]
        predicted_word_position = int(predicted_roll["word_position"])
        markers.append({
            "slot_index": slot_index,
            "roll_number": int(predicted_roll["roll_number"]),
            "mechanical_chapter_num": str(chapter_num),
            "mechanical_word_position": max(
                0,
                predicted_word_position - int(chapter_cp_start),
            ),
            "mechanical_cumulative_word_offset": predicted_word_position,
            "predicted_word_position_epub": predicted_word_position,
            "reason": "skipped_to_align_narrative",
        })
    return markers


# ---------- main builder ---------------------------------------------------

def main() -> None:
    if not EPUB.exists():
        raise SystemExit(f"missing {EPUB.relative_to(ROOT)}")

    chapters = json.loads(CHAPTERS.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))

    sections_data = json.loads(SECTIONS.read_text())
    sections_by_chap = {c["chapter_num"]: c for c in sections_data["chapters"]}
    classifications = json.loads(CLASSIFICATIONS.read_text())["classifications"]
    chapter_story_words_by_num = {
        c["chapter_num"]: _chapter_story_word_count(
            chapter_num=c["chapter_num"],
            full_title=c["full_title"],
            sec_meta=sections_by_chap[c["chapter_num"]],
            classifications=classifications,
        )
        for c in chapters
    }
    chapter_story_starts: dict[str, int] = {}
    running_story_words = 0
    for c in chapters:
        chapter_story_starts[c["chapter_num"]] = running_story_words
        running_story_words += chapter_story_words_by_num[c["chapter_num"]]
    roll_facts_doc = json.loads(ROLL_FACTS.read_text())
    roll_validation_doc = json.loads(ROLL_VALIDATION.read_text())
    predicted_rolls_doc = json.loads(PREDICTED_ROLLS.read_text())
    predicted_by_chapter = _predicted_rolls_by_chapter(predicted_rolls_doc)
    chapter_roll_overrides = _load_chapter_roll_overrides()
    obtained_doc = json.loads(OBTAINED_PERKS.read_text())
    obtained_counts_by_chapter: dict[str, dict[str, int]] = {}
    for perk in obtained_doc.get("perks", []):
        cn = str(perk["chapter_num"])
        counts = obtained_counts_by_chapter.setdefault(
            cn, {"paid": 0, "free": 0}
        )
        if perk.get("free", False):
            counts["free"] += 1
        else:
            counts["paid"] += 1
    perk_directory_doc = json.loads(PERK_DIRECTORY.read_text())
    countable_perks = [
        perk for perk in perk_directory_doc.get("perks", [])
        if _countable_directory_perk(perk)
    ]
    constellation_totals: Counter[str] = Counter(
        perk["constellation"] for perk in countable_perks
    )
    acquired_by_chapter: dict[str, Counter[str]] = {}
    for perk in countable_perks:
        chapter_num = perk.get("acquired_chapter_num")
        if not chapter_num:
            continue
        acquired_by_chapter.setdefault(str(chapter_num), Counter())[perk["constellation"]] += 1
    model_checks_by_chapter = {
        str(row["chapter_num"]): row
        for row in roll_validation_doc.get("chapter_checks", [])
    }
    pub_rows = json.loads(PUBLICATION_DATES.read_text())["chapters"]
    pub_by_chap = {r["chapter_num"]: r for r in pub_rows}

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
    cumulative_story_words = 0
    cumulative_cp_words = 0
    cumulative_perks = 0
    cumulative_roll_constellations: Counter[str] = Counter()
    cumulative_acquired_constellations: Counter[str] = Counter()
    shadow_periods: list[dict] = []

    for c in chapters:
        cn = c["chapter_num"]
        sec_meta = sections_by_chap[cn]
        sections_html_offsets = chapter_section_offsets.get(cn, [])

        # ---------- sections ----------
        sections_out: list[dict] = []
        cp_to_story_points: list[tuple[int, int, int, int]] = []
        pov_set: set[str] = set()
        marker_kinds_seen: list[str] = []
        struct_markers_aggregate: set[str] = set()
        sec_word_start = 0
        story_word_cursor = 0
        cp_word_cursor = 0
        for i, s in enumerate(sec_meta["sections"]):
            cls_key = f"{cn}@{i}"
            if cls_key not in classifications:
                raise SystemExit(
                    f"missing section classification for {cls_key}; run "
                    "scripts/build_section_classifications.py before building chapter facts"
                )
            cls = classifications[cls_key]
            counts_for_cp = bool(cls.get("counts_for_cp"))
            word_count = int(s["word_count"])
            sec_word_end = sec_word_start + word_count
            span_overrides = section_span_overrides(
                cls,
                sec_word_start,
                sec_word_end,
            )
            cp_word_count = section_cp_word_count(
                section_word_start=sec_word_start,
                section_word_end=sec_word_end,
                base_counts_for_cp=counts_for_cp,
                span_overrides=span_overrides,
            )
            mk = parse_marker_kind(s.get("header"), c["full_title"])
            story_word_count = _story_section_word_count(
                word_count=word_count,
                section_start=sec_word_start,
                section_end=sec_word_end,
                marker_kind=mk,
                classification=s.get("classification"),
                span_overrides=span_overrides,
            )
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
                "word_count": story_word_count,
                "cp_earning_word_count": cp_word_count,
                "counts_for_cp": counts_for_cp,
                "span_overrides": span_overrides,
                "classification": s.get("classification"),
                "classification_confidence": s.get("confidence"),
                "structural_markers": s.get("structural_markers") or [],
                "char_offset_start_in_chapter": cs,
                "char_offset_end_in_chapter": ce,
                "in_world_start_time_of_day": None,    # stubbed
                "in_world_end_time_of_day": None,      # stubbed
            })
            if cp_word_count > 0:
                cp_to_story_points.append((
                    cp_word_cursor,
                    cp_word_cursor + cp_word_count,
                    story_word_cursor,
                    story_word_cursor + story_word_count,
                ))
            sec_word_start = sec_word_end
            story_word_cursor += story_word_count
            cp_word_cursor += cp_word_count

        # ---------- rolls + attribution ----------
        chapter_cp_start = cumulative_cp_words
        chapter_cp_words = sum(s["cp_earning_word_count"] for s in sections_out)
        chapter_story_words = sum(s["word_count"] for s in sections_out)
        chap_roll_facts = rolls_by_chapter.get(cn, [])
        skipped_predicted_rolls = _skipped_predicted_roll_markers(
            cn,
            predicted_by_chapter.get(cn, []),
            chapter_roll_overrides.get(cn),
            chapter_cp_start=chapter_cp_start,
        )
        rolls_out: list[dict] = []
        hits = 0
        misses = 0
        unknowns = 0
        obtained_counts = obtained_counts_by_chapter.get(cn, {"paid": 0, "free": 0})
        paid_count_in_chap = int(obtained_counts["paid"])
        free_count_in_chap = int(obtained_counts["free"])
        banked_cp_at_start = None
        banked_cp_at_end = None
        chapter_roll_constellations: Counter[str] = Counter()

        def _display_cp_position(index: int, total: int) -> int | None:
            if chapter_cp_words <= 0 or total <= 0:
                return None
            fraction = (index + 1) / (total + 1)
            return int(round(chapter_cp_start + chapter_cp_words * fraction))

        def _story_local_from_cp_local(cp_local: int | None) -> int | None:
            if cp_local is None:
                return None
            cp_local = max(0, int(cp_local))
            for cp_start, cp_end, story_start, story_end in cp_to_story_points:
                if cp_start <= cp_local <= cp_end:
                    if cp_end == cp_start:
                        return story_start
                    frac = (cp_local - cp_start) / (cp_end - cp_start)
                    return int(round(story_start + frac * (story_end - story_start)))
            if cp_to_story_points:
                last_cp_end, last_story_end = cp_to_story_points[-1][1], cp_to_story_points[-1][3]
                if cp_local >= last_cp_end:
                    return last_story_end
            return min(cp_local, chapter_story_words)

        def _story_cumulative_for_roll(roll: dict) -> int | None:
            display_chapter_num = str(roll.get("display_chapter_num") or cn)
            local_pos = roll.get("display_word_position")
            if roll.get("source_kind") == "trigger" and display_chapter_num == cn:
                return cumulative_story_words
            if local_pos is None:
                return None
            if display_chapter_num == cn:
                story_local = (
                    int(local_pos)
                    if roll.get("display_position_policy") == "source_marker"
                    else _story_local_from_cp_local(int(local_pos))
                )
                if story_local is None:
                    return None
                return cumulative_story_words + story_local
            if roll.get("display_position_policy") == "source_marker":
                return chapter_story_starts.get(display_chapter_num, 0) + int(local_pos)
            return None

        def _section_index_for_roll(roll: dict) -> int | None:
            char_offset = roll.get("predicted_char_offset_in_chapter")
            if char_offset is None:
                return None
            for i, (s_start, s_end) in enumerate(sections_html_offsets):
                if s_start <= char_offset < s_end:
                    return i
            return None

        def _append_shadow_if_needed(roll: dict) -> None:
            # Shadow is triggered by the largest single paid perk cost in
            # the multi-grab — not the total. Only 600/800 trigger shadows.
            paid = roll.get("purchased_perks") or []
            principal_cost = max(
                (int(p.get("cost") or 0) for p in paid if not p.get("free", False)),
                default=0,
            )
            if (principal_cost not in SHADOW_TRIGGER_COSTS
                    or int(cn.split(".")[0]) < SHADOW_TRIGGER_MIN_CHAPTER):
                return
            principal_name = (
                next(
                    (p.get("name") for p in paid
                     if int(p.get("cost") or 0) == principal_cost),
                    None,
                )
                if paid else None
            )
            start_pos = (
                roll["display_word_position_epub"]
                if roll["display_word_position_epub"] is not None
                else roll["predicted_word_position_epub"]
            )
            shadow_words = (principal_cost // 2) * (REGIME_3_WORDS_PER_100_CP // 100)
            shadow_periods.append({
                "trigger_perk_id": roll["purchased_perk_id"],
                "trigger_perk_name": principal_name,
                "trigger_perk_cost": principal_cost,
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
            display_pos = _story_cumulative_for_roll(roll)
            roll_record = {
                "roll_number": roll["roll_number"],
                "section_index": _section_index_for_roll(roll),
                "outcome": roll["outcome"],
                "constellation": roll["constellation"],
                "mechanical_chapter_num": roll["mechanical_chapter_num"],
                "mechanical_word_position": roll["mechanical_word_position"],
                "mechanical_cumulative_word_offset": roll["mechanical_cumulative_word_offset"],
                "mention_chapter_num": roll["mention_chapter_num"],
                "mention_word_position": roll["mention_word_position"],
                "display_position_policy": roll["display_position_policy"],
                "display_chapter_num": roll["display_chapter_num"],
                "display_word_position": roll["display_word_position"],
                "display_cumulative_word_offset": display_pos,
                "source_chapter_num": roll["source_chapter_num"],
                "source_roll_index": roll["source_roll_index"],
                "source_word_position": roll["source_word_position"],
                "source_cumulative_word_offset": roll["source_cumulative_word_offset"],
                "visible_chapter_nums": roll["visible_chapter_nums"],
                "purchased_perk_id": roll["purchased_perk_id"],
                "purchased_perks": roll.get("purchased_perks") or [],
                "purchased_perk_cost_total": roll.get("purchased_perk_cost_total"),
                "purchased_perk_jump": roll["purchased_perk_jump"],
                "free_perks": roll["free_perks"],
                "word_position": roll.get("word_position"),
                "cumulative_word_offset": display_pos,
                "predicted_word_position_epub": roll["predicted_word_position_epub"],
                "display_word_position_epub": display_pos,
                "predicted_char_offset_in_chapter": roll["predicted_char_offset_in_chapter"],
                "anchor_char_offset_in_chapter": roll["anchor_char_offset_in_chapter"],
                "evidence_kind": roll["evidence_kind"],
                "evidence_quotes": roll.get("evidence_quotes") or [],
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
                _append_shadow_if_needed(roll_record)
            elif roll["outcome"] == "miss":
                misses += 1
            else:
                unknowns += 1
        chapter_roll_constellations.update(_roll_constellation_counts(rolls_out))

        model_check = model_checks_by_chapter.get(cn, {
            "status": "unknown",
            "has_discrepancy": False,
            "raw_has_discrepancy": False,
            "source_priority": "none",
            "predicted_roll_count": 0,
            "required_paid_roll_count": 0,
            "known_attempt_count": 0,
            "paid_roll_capacity_ok": True,
            "known_attempt_capacity_ok": True,
            "cost_schedule_ok": True,
            "synthetic_slot_count": 0,
            "resolved_issue_codes": [],
            "issues": [],
        })

        # ---------- chapter row ----------
        pub = pub_by_chap[cn]
        published_at = pub["published_at"]
        last_edited_at = pub["last_edited_at"]
        edited_lag_days = (
            (dt.date.fromisoformat(last_edited_at) - dt.date.fromisoformat(published_at)).days
            if last_edited_at else None
        )
        cumulative_story_words += chapter_story_words
        cumulative_cp_words += chapter_cp_words
        cumulative_perks += paid_count_in_chap + free_count_in_chap
        cumulative_roll_constellations.update(chapter_roll_constellations)
        for acquired_chapter, by_constellation in acquired_by_chapter.items():
            if _chapter_key(acquired_chapter) == _chapter_key(cn):
                cumulative_acquired_constellations.update(by_constellation)
        constellation_progress = []
        for name in CONSTELLATION_ORDER:
            total = int(constellation_totals.get(name, 0))
            acquired = int(cumulative_acquired_constellations.get(name, 0))
            count = int(cumulative_roll_constellations.get(name, 0))
            visible = total > 0 and count > 0
            constellation_progress.append({
                "name": name,
                "count": count,
                "total": total,
                "discovered": acquired,
                "discovered_pct": (
                    round((acquired / total) * 100) if total > 0 else 0
                ),
                "complete": total > 0 and acquired >= total,
                "visible": visible,
            })

        out_chapters.append({
            "chapter_num": cn,
            "full_title": c["full_title"],
            "sort_key": c["sort_key"],
            "point_calculation_regime": regime_for_chapter(cn),
            "epub_href": title_to_href.get(c["full_title"], ""),

            "published_at": published_at,
            "published_source": pub["published_source"],
            "last_edited_at": last_edited_at,
            "last_edited_source": pub["last_edited_source"],
            "edited_lag_days": edited_lag_days,
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

            "total_word_count": chapter_story_words,
            "cp_earning_word_count": chapter_cp_words,
            "rolls_count": len(rolls_out),
            "hits_count": hits,
            "misses_count": misses,
            "unknowns_count": unknowns,
            "perks_gained": paid_count_in_chap + free_count_in_chap,
            "paid_perks_gained": paid_count_in_chap,
            "free_perks_gained": free_count_in_chap,

            "cumulative_words_through_chapter": cumulative_story_words,
            "cumulative_cp_earning_words": cumulative_cp_words,
            "cumulative_perks_through_chapter": cumulative_perks,
            "banked_cp_at_start": banked_cp_at_start,
            "banked_cp_at_end": banked_cp_at_end,
            "model_validation": {
                "status": model_check["status"],
                "current_discrepancy": bool(model_check["has_discrepancy"]),
                "raw_current_discrepancy": bool(
                    model_check.get("raw_has_discrepancy", model_check["has_discrepancy"])
                ),
                "prior_discrepancy": False,
                "first_discrepancy_chapter_num": None,
                "source_priority": model_check["source_priority"],
                "predicted_roll_count": model_check["predicted_roll_count"],
                "required_paid_roll_count": model_check["required_paid_roll_count"],
                "known_attempt_count": model_check["known_attempt_count"],
                "paid_roll_capacity_ok": model_check["paid_roll_capacity_ok"],
                "known_attempt_capacity_ok": model_check["known_attempt_capacity_ok"],
                "cost_schedule_ok": model_check["cost_schedule_ok"],
                "synthetic_slot_count": model_check["synthetic_slot_count"],
                "resolved_issue_codes": model_check.get("resolved_issue_codes", []),
                "issues": model_check["issues"],
            },
            "constellation_progress": constellation_progress,

            "pov_characters": sorted(pov_set),
            "structural_markers": sorted(struct_markers_aggregate),

            "sections": sections_out,
            "skipped_predicted_rolls": skipped_predicted_rolls,
            "rolls": rolls_out,
        })

    first_discrepancy_chapter_num: str | None = None
    prior_discrepancy = False
    for chapter in out_chapters:
        model_validation = chapter["model_validation"]
        model_validation["prior_discrepancy"] = prior_discrepancy
        model_validation["first_discrepancy_chapter_num"] = first_discrepancy_chapter_num
        if model_validation["current_discrepancy"]:
            if first_discrepancy_chapter_num is None:
                first_discrepancy_chapter_num = chapter["chapter_num"]
            prior_discrepancy = True

    # Resolve shadow_periods.shadow_end_chapter_num on the same story-word
    # axis used by chapter_facts and the web scrubber.
    chapter_story_starts_final: dict[str, int] = {}
    cum_story = 0
    for c in out_chapters:
        chapter_story_starts_final[c["chapter_num"]] = cum_story
        cum_story += c["total_word_count"]
    chap_order = [c["chapter_num"] for c in out_chapters]

    def chapter_at(story_word_pos: int) -> str | None:
        for i, ch in enumerate(chap_order):
            start = chapter_story_starts_final[ch]
            end = (
                chapter_story_starts_final[chap_order[i + 1]]
                if i + 1 < len(chap_order)
                else cum_story
            )
            if start <= story_word_pos < end:
                return ch
        return None

    for sp in shadow_periods:
        # Patch any synthetic-acquisition shadows with chapter-start
        # word positions. (regime-simulator-anchored shadows already
        # have their start position set.)
        if sp["trigger_word_position_epub"] is None:
            sp["trigger_word_position_epub"] = chapter_story_starts_final.get(
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
        "schema_version": 1,
        "_source": (
            "Chapter-grain fact table for the visualization. One row "
            "per published chapter with sections and rolls as nested "
            "1:N dimensions; shadow_periods are top-level because they "
            "can span chapters."
        ),
        "_method": (
            "Cross-join of chapters.json + chapter_sections.json + "
            "section_classifications.json + roll_facts.json + "
            "chapter_publication_dates.json. Roll facts are pre-reconciled "
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
            "shadow_periods.shadow_end_chapter_num approximate (uses story-word shadow length)",
        ],
        "shadow_periods": shadow_periods,
        "in_world_timeline": in_world_timeline,
        "chapters": out_chapters,
    }

    write_validated_json(OUT, payload, "chapter_facts")
    refresh_current_runtime_manifest(source_dir=DERIVED)

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
