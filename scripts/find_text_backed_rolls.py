"""For each predicted roll, find prose evidence in the chapter text.

This produces a *text-evidence-backed* roll log — each entry is a
predicted roll position from `predicted_rolls.json` with the prose
window around its predicted location, the regex anchors that landed in
that window, and a classification of the evidence quality.

The point: stop using the curator's `rolls.json` as ground truth. The
curator's bookkeeping has known quirks (rolls tagged to entire-interlude
chapters, batched cycles compressed onto single chapter labels). The
prose IS the truth — every real roll has either a direct narration at
its predicted position, a forward-reference shortly after, or in rare
cases is intentionally not narrated. This script lets downstream
consumers see all three classes and decide for themselves.

Inputs:
  - data/raw/Brocktons_Celestial_Forge.epub
  - data/derived/predicted_rolls.json (regime-simulated positions)
  - data/derived/chapters.json
  - data/derived/chapter_sections.json
  - data/manual/section_classifications.json (which sections count_for_cp)
  - data/derived/roll_locations_regex.json (the regex anchor catalog)

Output:
  - data/derived/roll_text_evidence.json (validated)

For each predicted roll we record:
  - predicted (chapter, word index in chapter, char offset,
    cp_rule_regime, roll_trigger_cp_threshold)
  - prose window: ±WORD_RADIUS CP-earning words of prose centered on the
    predicted position, with [[X]] marking the predicted-position word
  - matching_events: regex events whose anchor falls within the prose
    window (subset of roll_locations_regex.json events)
  - evidence_kind:
      * "direct"          - at least one anchor with kind in
                            {miss, constellation_reveal, roll_attempt,
                             acquisition} sits within the window
      * "general_only"    - only 'general' (catch-all) anchors in window
      * "forward_ref"     - no anchors in window, but specific anchors
                            exist later in the same chapter; LLM stage-2
                            should look for retrospective phrasing like
                            "the missed mote my power had attempted to grab"
      * "no_evidence"     - no specific anchors anywhere in chapter
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from _common import write_validated_json
from find_roll_locations import (
    _split_sections, _strip_to_spaces, _build_chapter_index, _to_plain,
)

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
PREDICTED = ROOT / "data" / "derived" / "predicted_rolls.json"
CHAPTERS = ROOT / "data" / "derived" / "chapters.json"
SECTIONS = ROOT / "data" / "derived" / "chapter_sections.json"
CLASSIFICATIONS = ROOT / "data" / "manual" / "section_classifications.json"
REGEX = ROOT / "data" / "derived" / "roll_locations_regex.json"
OUT = ROOT / "data" / "derived" / "roll_text_evidence.json"

# Window size in CP-earning words around the predicted position. The
# user's spec was "a couple hundred words" — 250 either side is generous
# enough to catch an immediate narration phrase but tight enough that we
# don't routinely glob a whole roll-cluster (rolls fire every 2k-6k
# words depending on regime).
WORD_RADIUS = 250

# Anchor kinds that count as "direct evidence" of a roll event.
SPECIFIC_ANCHOR_KINDS = {
    "constellation_reveal", "miss", "roll_attempt", "acquisition",
}


def _chapter_word_index(
    chapter_html: str,
    section_classifications: dict[str, dict],
    chapter_num: str,
) -> list[int]:
    """Return a list of char offsets, one per CP-earning word in the
    chapter, in order. Index N gives the start char of the (N+1)-th
    CP-earning word in this chapter's HTML.

    Sections whose span starts before the opening <body> tag (i.e. the
    XML declaration, DOCTYPE, and <head> preamble) are clamped to start
    at the first byte after <body>.  This prevents the chapter title
    inside <title>...</title> from being counted as CP-earning prose
    words when a section's html_start == 0.
    """
    # Locate the end of the <body...> opening tag so we never count words
    # in the XML/DOCTYPE/head preamble.  If somehow the file has no <body>
    # tag, fall back to 0 (no clamping).
    body_m = re.search(r"<body[^>]*>", chapter_html)
    body_content_start = body_m.end() if body_m else 0

    out: list[int] = []
    for section_index, (_header, s_start, s_end) in enumerate(_split_sections(chapter_html)):
        cls = section_classifications.get(f"{chapter_num}@{section_index}")
        if not cls or not cls.get("counts_for_cp"):
            continue
        # Clamp: skip any bytes that fall inside the XML/HTML preamble.
        effective_start = max(s_start, body_content_start)
        if effective_start >= s_end:
            continue
        spaced = _strip_to_spaces(chapter_html[effective_start:s_end])
        for m in re.finditer(r"\S+", spaced):
            out.append(effective_start + m.start())
    return out


def _prose_window(
    chapter_html: str, word_index: list[int],
    center_word_idx: int, radius: int,
    matching_events: list[dict],
) -> tuple[str, int, int]:
    """Build a plain-text prose window. Returns (snippet, char_start, char_end).

    The snippet brackets the predicted-position word with [[*]], plus
    each matching regex anchor with <<phrase>> so a downstream reader
    (or LLM) can see anchor placement in the prose.
    """
    n = len(word_index)
    if n == 0:
        return ("", 0, 0)
    lo_word = max(0, center_word_idx - radius)
    hi_word = min(n - 1, center_word_idx + radius)
    char_start = word_index[lo_word]
    char_end = word_index[hi_word]
    # Extend hi to next word's start (so we include the last word fully)
    if hi_word + 1 < n:
        char_end = word_index[hi_word + 1]
    else:
        char_end = len(chapter_html)

    # Build a marker map: char_offset -> (open_str, close_str)
    # We mark predicted center with [[*]] and each matching event with
    # <<event.anchor_phrase>> at its anchor_offset.
    markers: list[tuple[int, str, str]] = []  # (offset, open, close, len)
    if 0 <= center_word_idx < n:
        center_char = word_index[center_word_idx]
        # Center the marker on a single word: find the word's end
        word_match = re.match(r"\S+", chapter_html[center_char:center_char + 200])
        word_len = word_match.end() if word_match else 1
        markers.append((center_char, "[[*", "*]]", word_len))
    for ev in matching_events:
        markers.append((ev["anchor_offset"], "<<",
                        f"|{ev['anchor_kind']}>>",
                        len(ev["anchor_phrase"])))

    # Walk the window inserting markers; we render to plain text after.
    pieces: list[str] = []
    cursor = char_start
    markers_in_window = sorted(
        [m for m in markers if char_start <= m[0] < char_end],
        key=lambda x: x[0],
    )
    for offset, open_s, close_s, length in markers_in_window:
        if offset > cursor:
            pieces.append(chapter_html[cursor:offset])
        end_off = offset + length
        pieces.append(open_s)
        pieces.append(chapter_html[offset:end_off])
        pieces.append(close_s)
        cursor = end_off
    if cursor < char_end:
        pieces.append(chapter_html[cursor:char_end])
    raw = "".join(pieces)
    plain = _to_plain(raw)
    return (plain, char_start, char_end)


def main() -> None:
    if not EPUB.exists():
        raise SystemExit(f"missing {EPUB.relative_to(ROOT)}")

    chapters = json.loads(CHAPTERS.read_text())["chapters"]
    chapters.sort(key=lambda c: tuple(c["sort_key"]))
    sections_by_chap = {
        c["chapter_num"]: c for c in json.loads(SECTIONS.read_text())["chapters"]
    }
    classifications = json.loads(CLASSIFICATIONS.read_text())["classifications"]
    predicted = json.loads(PREDICTED.read_text())["predicted"]
    events = json.loads(REGEX.read_text())["events"]

    # Group events by chapter once.
    events_by_chapter: dict[str, list[dict]] = {}
    for ev in events:
        events_by_chapter.setdefault(ev["chapter_num"], []).append(ev)
    for ch_evs in events_by_chapter.values():
        ch_evs.sort(key=lambda e: e["anchor_offset"])

    # Build cumulative-CP-words per chapter so we can convert
    # predicted.word_position (EPUB-cumulative) to within-chapter index.
    #
    # BUG FIX: previously this used sections_by_chap[cn]["cp_earning_word_count"],
    # which is the pre-computed value written by extract_chapter_sections.py using
    # its automated POV heuristic.  predict_rolls.py uses the MANUAL overrides in
    # section_classifications.json (same `classifications` dict we already loaded)
    # to decide which sections earn CP.  Those two can differ — e.g. chapter 1
    # section 0 is auto-classified as MC but manually overridden to
    # counts_for_cp=False.  Using the pre-computed field causes cum_cp_before to
    # diverge from predict_rolls.py's cumulative word totals, so
    # target_word_in_chapter = word_position - cum_cp_before[ch] can be wildly
    # negative, causing the offset to clamp to 0 and land in the EPUB XML preamble.
    # Fix: mirror predict_rolls.py exactly — sum only the sections whose
    # manual classification says counts_for_cp=True (default True when absent,
    # matching predict_rolls._load_cp_words_per_chapter).
    cum_cp_before: dict[str, int] = {}
    running = 0
    for c in chapters:
        cn = c["chapter_num"]
        cum_cp_before[cn] = running
        c_secs = sections_by_chap[cn]["sections"]
        chapter_cp_words = sum(
            s["word_count"]
            for i, s in enumerate(c_secs)
            if classifications.get(f"{cn}@{i}", {}).get("counts_for_cp", True)
        )
        running += chapter_cp_words

    # Precompute chapter word indexes only for chapters that have any
    # predicted rolls (avoids parsing all 194 chapters every run).
    predicted_chapters = {p["chapter_num"] for p in predicted}

    chapter_word_index: dict[str, list[int]] = {}
    chapter_html_cache: dict[str, str] = {}
    with zipfile.ZipFile(EPUB) as zf:
        title_to_href = _build_chapter_index(zf)
        for c in chapters:
            ch = c["chapter_num"]
            if ch not in predicted_chapters:
                continue
            href = title_to_href.get(c["full_title"])
            if not href:
                continue
            html = zf.read(f"EPUB/{href}").decode("utf-8")
            chapter_html_cache[ch] = html
            chapter_word_index[ch] = _chapter_word_index(html, classifications, ch)

    # Walk predicted rolls, attach evidence.
    out_rolls: list[dict] = []
    counts_by_kind: dict[str, int] = {
        "direct": 0, "general_only": 0, "forward_ref": 0, "no_evidence": 0,
    }
    for p in predicted:
        ch = p["chapter_num"]
        word_idx = chapter_word_index.get(ch, [])
        chapter_html = chapter_html_cache.get(ch, "")
        # Within-chapter word index (0-based) of the predicted position.
        target_word_in_chapter = p["word_position"] - cum_cp_before.get(ch, 0)
        # Clamp to valid range; if predicted pushes past the chapter's
        # CP-word count, the predicted lands at the chapter's tail.
        if word_idx and target_word_in_chapter >= len(word_idx):
            target_word_in_chapter = len(word_idx) - 1
        if target_word_in_chapter < 0:
            target_word_in_chapter = 0

        # Window char range.
        if word_idx:
            lo = max(0, target_word_in_chapter - WORD_RADIUS)
            hi = min(len(word_idx) - 1, target_word_in_chapter + WORD_RADIUS)
            window_char_lo = word_idx[lo]
            window_char_hi = (word_idx[hi + 1] if hi + 1 < len(word_idx)
                              else len(chapter_html))
            center_char = word_idx[target_word_in_chapter]
        else:
            window_char_lo = window_char_hi = center_char = 0

        # Filter regex events by chapter + window.
        ch_events = events_by_chapter.get(ch, [])
        in_window = [
            e for e in ch_events
            if window_char_lo <= e["anchor_offset"] < window_char_hi
        ]
        out_window_specific = [
            e for e in ch_events
            if e["anchor_offset"] >= window_char_hi
            and e["anchor_kind"] in SPECIFIC_ANCHOR_KINDS
        ]

        specific_in = [e for e in in_window if e["anchor_kind"] in SPECIFIC_ANCHOR_KINDS]
        general_in = [e for e in in_window if e["anchor_kind"] == "general"]

        if specific_in:
            kind = "direct"
        elif general_in:
            kind = "general_only"
        elif out_window_specific:
            kind = "forward_ref"
        else:
            kind = "no_evidence"
        counts_by_kind[kind] += 1

        snippet, _, _ = _prose_window(
            chapter_html, word_idx, target_word_in_chapter,
            WORD_RADIUS, in_window,
        ) if word_idx else ("", 0, 0)

        # anchor_string: last ~15 whitespace-separated words of raw prose
        # immediately before predicted_char_offset, verbatim (no markers).
        if center_char > 0 and chapter_html:
            before = chapter_html[:center_char]
            words = before.split()
            if words:
                tail_words = words[-15:]
                # Reconstruct verbatim: find the start of the first tail word
                # in the original slice so we preserve inter-word whitespace.
                first_tail_word = tail_words[0]
                # Search backwards from center_char for the first tail word.
                # Use rfind on the prefix to locate its last occurrence.
                start_of_anchor = before.rfind(first_tail_word)
                if start_of_anchor == -1:
                    anchor_string = " ".join(tail_words)
                else:
                    anchor_string = before[start_of_anchor:].rstrip()
                    # Trim to at most 15 words in case rfind landed earlier.
                    anchor_words = anchor_string.split()
                    if len(anchor_words) > 15:
                        # Re-locate using the last 15 words of the verbatim slice.
                        last15_first = anchor_words[-15]
                        idx = anchor_string.rfind(last15_first)
                        anchor_string = anchor_string[idx:].rstrip()
            else:
                anchor_string = ""
        else:
            anchor_string = ""

        out_rolls.append({
            "roll_number": p["roll_number"],
            "chapter_num": ch,
            "cp_rule_regime": p["cp_rule_regime"],
            "roll_trigger_cp_threshold": p["roll_trigger_cp_threshold"],
            "predicted_word_position_epub": p["word_position"],
            "predicted_word_in_chapter": target_word_in_chapter,
            "predicted_char_offset": center_char,
            "anchor_string": anchor_string,
            "window_char_start": window_char_lo,
            "window_char_end": window_char_hi,
            "evidence_kind": kind,
            "matching_anchor_kinds": sorted({e["anchor_kind"] for e in in_window}),
            "matching_event_count": len(in_window),
            "matching_events": [
                {
                    "anchor_kind": e["anchor_kind"],
                    "anchor_phrase": e["anchor_phrase"],
                    "anchor_offset": e["anchor_offset"],
                    "kinds_present": e["kinds_present"],
                    "hit_count": e["hit_count"],
                }
                for e in in_window
            ],
            "next_specific_event_offset": (
                out_window_specific[0]["anchor_offset"]
                if out_window_specific else None
            ),
            "prose_window": snippet,
        })

    # Aggregate counters per chapter.
    by_chapter: dict[str, dict[str, int]] = {}
    for r in out_rolls:
        d = by_chapter.setdefault(r["chapter_num"], {
            "direct": 0, "general_only": 0, "forward_ref": 0, "no_evidence": 0,
            "total": 0,
        })
        d[r["evidence_kind"]] += 1
        d["total"] += 1

    # Chapter-level rollup. Each chapter is "covered" if at least one of
    # its predicted rolls has a specific anchor (direct or forward_ref).
    # This is the author's natural narration grain: one anchor per
    # roll-burst, not per-cycle.
    chapters_covered = sum(
        1 for v in by_chapter.values()
        if v["direct"] > 0 or v["forward_ref"] > 0
    )
    chapters_with_direct = sum(1 for v in by_chapter.values() if v["direct"] > 0)
    chapter_total = len(by_chapter)

    payload = {
        "_source": (
            "Per-predicted-roll prose evidence: for each entry in "
            "predicted_rolls.json, find the regex anchors within ±250 "
            "CP-earning words and emit a plain-text prose window. The "
            "predicted positions come from the regime simulator and are "
            "computed from CP-earning word counts; this script anchors "
            "them in real prose by walking each chapter's MC sections "
            "and locating the Nth non-whitespace token."
        ),
        "_method": (
            "For each predicted roll: target_word_in_chapter = "
            "predicted.word_position - cumulative CP-earning words "
            "before this chapter. Walk chapter HTML through "
            "_split_sections + _strip_to_spaces (same tokenizer "
            "extract_chapter_sections.py uses) and collect char offsets "
            "for every CP-earning word. Window = ±250 words. Match "
            "regex events from roll_locations_regex.json by char "
            "offset within the window."
        ),
        "_framing_note": (
            "Two coverage metrics matter here, and they answer different "
            "questions:\n"
            "  PER-CHAPTER coverage = 'does the chapter narrate any of "
            "its predicted rolls?' Authors typically narrate ONE prose "
            "anchor per burst (e.g. ch 2 has 4 predicted rolls but only "
            "1 narrated event — 'a new constellation approached'). At "
            "this grain we should expect ~90%+ of chapters covered.\n"
            "  PER-ROLL direct rate = 'does each predicted roll fall "
            "into its own narration window?' Much lower (~10-15%) "
            "because the author bursts rather than cycle-by-cycle. The "
            "rest land in forward_ref: the simulator predicts a roll at "
            "word X, the prose narrates that roll's outcome at word "
            "X+500 with retrospective phrasing.\n"
            "Use chapter-level coverage as the headline. Use per-roll "
            "data for Stage-2 LLM alignment (each predicted cycle to "
            "its retrospective narration phrase)."
        ),
        "_window_size_words": WORD_RADIUS,
        "_evidence_kinds": {
            "direct": "≥1 specific anchor (miss/reveal/attempt/acquisition) inside the window",
            "general_only": "only 'general' (catch-all Forge mention) anchors inside the window",
            "forward_ref": "no anchors in window, but specific anchors exist later in the chapter (likely retrospective narration)",
            "no_evidence": "no specific anchors anywhere in the chapter — either the prose genuinely doesn't narrate the roll, or the regex catalog has a real blind spot",
        },
        "_total_predicted": len(out_rolls),
        "_evidence_kind_totals": counts_by_kind,
        "_evidence_kind_pct": {
            k: round(100.0 * v / len(out_rolls), 1) if out_rolls else 0.0
            for k, v in counts_by_kind.items()
        },
        "_chapter_coverage": {
            "chapters_with_predicted_rolls": chapter_total,
            "chapters_with_any_specific_anchor": chapters_covered,
            "chapter_coverage_pct": round(
                100.0 * chapters_covered / chapter_total, 1) if chapter_total else 0.0,
            "chapters_with_direct_anchor": chapters_with_direct,
            "chapter_direct_pct": round(
                100.0 * chapters_with_direct / chapter_total, 1) if chapter_total else 0.0,
        },
        "_by_chapter": dict(sorted(
            by_chapter.items(),
            key=lambda kv: (int(kv[0].split('.')[0]),
                            int(kv[0].split('.')[1]) if '.' in kv[0] else 0),
        )),
        "rolls": out_rolls,
    }

    write_validated_json(OUT, payload, "roll_text_evidence")

    print(f"wrote {OUT.relative_to(ROOT)}: {len(out_rolls)} predicted rolls")
    print(f"  evidence_kind: {counts_by_kind}")
    pct = payload["_evidence_kind_pct"]
    print(f"  per-roll pct: direct={pct['direct']}%, general_only={pct['general_only']}%, "
          f"forward_ref={pct['forward_ref']}%, no_evidence={pct['no_evidence']}%")
    cov = payload["_chapter_coverage"]
    print(f"  per-chapter coverage: {cov['chapter_coverage_pct']}% "
          f"({cov['chapters_with_any_specific_anchor']}/{cov['chapters_with_predicted_rolls']} chapters with ≥1 specific anchor)")
    print(f"  per-chapter direct: {cov['chapter_direct_pct']}% "
          f"({cov['chapters_with_direct_anchor']}/{cov['chapters_with_predicted_rolls']} chapters with ≥1 in-window direct anchor)")


if __name__ == "__main__":
    main()
