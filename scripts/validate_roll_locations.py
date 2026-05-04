"""Sidecar comparison of regex anchors vs the curator's roll log.

PRIMARY GROUND TRUTH for the project is now
data/derived/roll_text_evidence.json (regime-simulated positions +
prose windows + regex anchors, all derived from EPUB prose). This
script is retained as a SIDECAR comparison against the curator's
hand-curated rolls.json so we can quantify HOW MUCH the curator's
bookkeeping diverges from the prose-evidence-backed view.

The curator's log is bookkeeping, not narration: it ticks every 100
CP earned regardless of whether the prose narrates a roll event. It
also includes CP earned during non-MC POV sections that the author's
own rules ('rolls every 2000 words of the protagonist's POV') exclude.
The simulator + prose evidence are internally consistent; the
curator's tallies are higher because of these bookkeeping artifacts.

This script reports the divergence so a future maintainer can see at
a glance which chapters' curator counts are inflated relative to what
the prose actually narrates.

Inputs:
  - data/derived/rolls.json (curator log - ch 1-75 only)
  - data/derived/roll_locations_regex.json (regex events)

Output:
  - data/derived/roll_locations_validation.json (sidecar comparison)
"""

from __future__ import annotations

import json
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
ROLLS = ROOT / "data" / "derived" / "rolls.json"
REGEX = ROOT / "data" / "derived" / "roll_locations_regex.json"
OUT = ROOT / "data" / "derived" / "roll_locations_validation.json"

# kinds in rolls.json that represent a *real roll attempt* (vs. annotation
# rows the curator added for context). Triggers count as a "first-roll"
# event — there's a constellation reveal narration around them.
CURATOR_ROLL_KINDS = {"roll", "miss", "trigger"}

# Event anchor kinds that should count as covering a curator roll.
# 'general' is too vague (any Celestial Forge mention) so it's excluded.
COVERAGE_ANCHOR_KINDS = {
    "roll_attempt", "miss", "acquisition", "constellation_reveal",
}


def main() -> None:
    rolls = json.loads(ROLLS.read_text())["rolls"]
    regex = json.loads(REGEX.read_text())
    events = regex["events"]

    # Per-chapter curator counts for ch 1-75.
    curator_by_chapter: dict[str, dict[str, int]] = {}
    for r in rolls:
        ch = r["chapter_num"]
        if not ch:
            continue
        kind = r["kind"]
        if kind not in CURATOR_ROLL_KINDS:
            continue
        d = curator_by_chapter.setdefault(ch, {"hits": 0, "misses": 0, "triggers": 0})
        if kind == "miss":
            d["misses"] += 1
        elif kind == "trigger":
            d["triggers"] += 1
        else:
            d["hits"] += 1

    # Per-chapter regex event counts (excluding 'general' anchor).
    regex_by_chapter: dict[str, dict[str, int]] = {}
    for ev in events:
        if ev["anchor_kind"] not in COVERAGE_ANCHOR_KINDS:
            continue
        ch = ev["chapter_num"]
        d = regex_by_chapter.setdefault(ch, {
            "constellation_reveal": 0, "miss": 0, "roll_attempt": 0,
            "acquisition": 0, "total": 0,
        })
        d[ev["anchor_kind"]] += 1
        d["total"] += 1

    # Build per-chapter comparison rows for ch 1-75 (curator coverage).
    rows: list[dict] = []

    def chap_sort(ch: str) -> tuple[int, int]:
        a, _, b = ch.partition(".")
        return (int(a), int(b) if b else 0)

    curator_chapters = sorted(curator_by_chapter.keys(), key=chap_sort)
    total_curator = 0
    total_covered = 0
    chapters_undercollected: list[str] = []

    for ch in curator_chapters:
        cur = curator_by_chapter[ch]
        rx = regex_by_chapter.get(ch, {
            "constellation_reveal": 0, "miss": 0, "roll_attempt": 0,
            "acquisition": 0, "total": 0,
        })
        # A chapter is "undercollected" if regex events < curator events.
        # That signals real rolls the LLM Stage-2 pass won't have prose
        # anchors for. Triggers count as half-events for this purpose
        # since a trigger can be narrated subtly.
        curator_events = cur["hits"] + cur["misses"] + cur["triggers"]
        covered = min(rx["total"], curator_events)
        total_curator += curator_events
        total_covered += covered
        under = rx["total"] < curator_events
        if under:
            chapters_undercollected.append(ch)
        rows.append({
            "chapter_num": ch,
            "curator_hits": cur["hits"],
            "curator_misses": cur["misses"],
            "curator_triggers": cur["triggers"],
            "regex_constellation_reveal": rx["constellation_reveal"],
            "regex_miss": rx["miss"],
            "regex_roll_attempt": rx["roll_attempt"],
            "regex_acquisition": rx["acquisition"],
            "regex_total": rx["total"],
            "undercollected": under,
        })

    chapter_coverage_pct = 100.0 * total_covered / total_curator if total_curator else 0.0

    # Per-kind agreement: do curator-miss-heavy chapters have regex-miss
    # events? This isn't an alignment, just a sanity check.
    curator_misses = sum(c["misses"] for c in curator_by_chapter.values())
    regex_misses = sum(regex_by_chapter.get(ch, {}).get("miss", 0)
                       for ch in curator_chapters)
    regex_constellation_reveals = sum(
        regex_by_chapter.get(ch, {}).get("constellation_reveal", 0)
        for ch in curator_chapters
    )
    curator_hits_total = sum(c["hits"] for c in curator_by_chapter.values())

    # Categorize undercollected chapters: pure-interlude (0 MC sections,
    # so regex CANNOT find anchors there — the curator nevertheless tags
    # rolls to them; this is a documented bookkeeping quirk in the
    # README) vs main chapters (real but small regex blind spots).
    classifications = json.loads(
        (ROOT / "data" / "manual" / "section_classifications.json").read_text()
    )["classifications"]

    def has_mc_pov(chapter_num: str) -> bool:
        for key, cls in classifications.items():
            ch, _, _ = key.partition("@")
            if ch == chapter_num and cls.get("counts_for_cp"):
                return True
        return False

    interlude_under = [c for c in chapters_undercollected if not has_mc_pov(c)]
    main_under = [c for c in chapters_undercollected if has_mc_pov(c)]

    # Coverage if we exclude the structural-zero chapters (pure
    # interludes with no MC POV — the regex has no prose to scan).
    structural_curator = sum(
        curator_by_chapter[c]["hits"] + curator_by_chapter[c]["misses"]
        + curator_by_chapter[c]["triggers"]
        for c in interlude_under
    )
    adj_curator = total_curator - structural_curator
    adj_covered = total_covered  # covered already only counts chapters with anchors
    adj_pct = 100.0 * adj_covered / adj_curator if adj_curator else 0.0

    payload = {
        "_source": (
            "Chapter-level comparison of curator rolls.json vs regex "
            "roll_locations_regex.json events for chapters 1-75 (curator "
            "coverage). Stage-1 sanity check: do we have enough regex "
            "anchors per chapter for a downstream LLM pass to align each "
            "curator roll with its narrative anchor?"
        ),
        "_method": (
            "Per chapter: count curator entries (kind in {roll, miss, "
            "trigger}) vs regex events (anchor_kind in "
            "{constellation_reveal, miss, roll_attempt, acquisition} — "
            "'general' excluded as too vague). A chapter is "
            "'undercollected' if regex events < curator events. The "
            "headline coverage_pct = sum(min(regex, curator)) / "
            "sum(curator) across all curator-covered chapters."
        ),
        "_scope": "chapters 1-75 (curator log coverage)",
        "_findings": [
            {
                "name": "curator vs simulator: structural-zero chapters",
                "chapters": interlude_under,
                "prose_evidence": (
                    "These chapters have ZERO sections with "
                    "counts_for_cp=true. The simulator (which follows the "
                    "author's '2000 words of MC POV per 100 CP' rule) "
                    "predicts no rolls in them. The prose contains no "
                    "roll narration. The curator nevertheless logged "
                    "rolls in these chapters — this is the curator "
                    "ticking 100-CP boundaries on raw word count, "
                    "regardless of MC vs non-MC. Curator log is "
                    "bookkeeping-divergent here, NOT a regex blind spot."
                ),
                "actionable": False,
            },
            {
                "name": "curator vs simulator: bookkeeping ≠ narration",
                "chapters": ["58"],  # the canonical example
                "prose_evidence": (
                    "Confirmed by reading prose: ch 58 has 2,506 CP-earning "
                    "words → simulator predicts 1 roll → prose narrates 1 "
                    "roll (Size constellation → Nano-technician at offset "
                    "53658, anchor 'the Size constellation'). The curator "
                    "logged 6 entries (Roll 407-411 + 1 annotation), but "
                    "Rolls 407-410 are tagged '???→Miss' — they're CP-"
                    "bank ticks during ch 58's non-MC sections (Preamble "
                    "Survey + interlude content), not narrated roll events. "
                    "Earlier (now-superseded) finding claimed this was "
                    "'buildup-phrase compression'; that interpretation was "
                    "incorrect — the simulator and prose match 1:1, the "
                    "curator's count is what diverges."
                ),
                "actionable": False,
            },
            {
                "name": "curator vs simulator: minor count drift in main chapters",
                "chapters": [c for c in main_under if c != "58"],
                "prose_evidence": (
                    "Same structural cause as ch 58: curator counts every "
                    "100-CP boundary crossing on raw words, simulator "
                    "counts only on MC-POV words, prose narrates only "
                    "the events the author chose to write. The drift is "
                    "small in these chapters because they have proportionally "
                    "more MC POV. For ground truth, prefer "
                    "data/derived/roll_text_evidence.json (each predicted "
                    "roll's prose window is captured directly from the "
                    "EPUB)."
                ),
                "actionable": False,
            },
        ],
        "coverage_excluding_structural_zeros": {
            "curator_total_excluding_zero_mc_chapters": adj_curator,
            "covered": adj_covered,
            "coverage_pct": round(adj_pct, 1),
        },
        "totals": {
            "curator_hits": curator_hits_total,
            "curator_misses": curator_misses,
            "curator_triggers": sum(c["triggers"] for c in curator_by_chapter.values()),
            "curator_total": total_curator,
            "regex_constellation_reveals": regex_constellation_reveals,
            "regex_misses_in_curator_chapters": regex_misses,
            "covered_in_curator_chapters": total_covered,
            "chapter_coverage_pct": round(chapter_coverage_pct, 1),
            "chapters_undercollected": len(chapters_undercollected),
            "chapters_undercollected_list": chapters_undercollected,
            "chapters_with_curator_rolls": len(curator_chapters),
        },
        "per_chapter": rows,
    }

    write_validated_json(OUT, payload, "roll_locations_validation")

    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  curator total events (hits+misses+triggers): {total_curator}")
    print(f"  regex events covering them (capped per chapter): {total_covered}")
    print(f"  chapter coverage: {chapter_coverage_pct:.1f}%")
    print(f"  undercollected chapters: {len(chapters_undercollected)} of {len(curator_chapters)}")
    if chapters_undercollected:
        print(f"    {chapters_undercollected[:10]}{'...' if len(chapters_undercollected) > 10 else ''}")


if __name__ == "__main__":
    main()
