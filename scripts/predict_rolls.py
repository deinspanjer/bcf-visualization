"""Predict where each roll fires by simulating the mechanic word-by-word.

Reads:
  - data/derived/chapters.json
  - data/derived/obtained_perks.json
  - data/derived/chapter_sections.json   (per-section CP-earning word counts)

Writes:
  - data/derived/predicted_rolls.json

Simulates CP accumulation through the three documented regimes:

  Regime 1 (ch 1-91):   100 CP per 2000 words, roll every 100 CP.
  Regime 2 (ch 92-96):  100 CP per 2000 words, roll every 200 CP.
  Regime 3 (ch 97+):    100 CP per 3000 words, roll every 200 CP, plus
                        a 9000-word "shadow" after each 600-CP perk and
                        a 12000-word shadow after each 800-CP perk
                        during which no CP is banked.

The simulation walks events (chapter starts and paid acquisitions)
in cumulative-word order. Between events, it accumulates CP at the
regime rate, subtracting any active shadow. When banked CP crosses
the roll threshold, a roll is predicted at that exact word offset.

CP-earning word counts come from chapter_sections.json, which classifies
each section of each chapter (Preamble/Addendum/Interlude/perks/news/
PHO posts) and records only the MC-POV word count per chapter. Run
`scripts/extract_chapter_sections.py` first to populate that file.

The prediction is then cross-validated against rolls.json for
chapters 1-75 (where actual rolls are logged), and used to project
roll counts for chapters 76+ where the curator stopped maintaining.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_JSON = ROOT / "data" / "derived" / "chapters.json"
OBTAINED_JSON = ROOT / "data" / "derived" / "obtained_perks.json"
ROLLS_JSON = ROOT / "data" / "derived" / "rolls.json"
SECTIONS_JSON = ROOT / "data" / "derived" / "chapter_sections.json"
CLASSIFICATIONS_JSON = ROOT / "data" / "manual" / "section_classifications.json"
LABELED_SPANS_DIR = ROOT / "data" / "labeled" / "spans"
OUT = ROOT / "data" / "derived" / "predicted_rolls.json"


# ---------- regime model ----------------------------------------------------


# (words_per_100_cp, cp_per_roll). The author's notes for ch91 and ch97
# define these; see the project README "Mechanics" section.
REGIMES = {
    1: {"words_per_100_cp": 2000, "cp_per_roll": 100},
    2: {"words_per_100_cp": 2000, "cp_per_roll": 200},
    3: {"words_per_100_cp": 3000, "cp_per_roll": 200},
}
SHADOW_CP_RATIO = 0.5    # half the perk's cost worth of CP is the shadow


def regime_for_chapter(chapter_num: str) -> int:
    major = int(chapter_num.split(".")[0])
    if major <= 91:
        return 1
    if major <= 96:
        return 2
    return 3


def shadow_words(perk_cost: int, regime: int) -> int:
    """Words of zero-CP-banking after a 600/800-CP perk in regime 3."""
    if regime != 3 or perk_cost not in (600, 800):
        return 0
    shadow_cp = int(perk_cost * SHADOW_CP_RATIO)
    return shadow_cp * REGIMES[3]["words_per_100_cp"] // 100


# ---------- per-chapter CP-earning word counts ------------------------------


def _load_labeled_an_words() -> dict[tuple[str, int], int]:
    """Sum AUTHOR_NOTE-labeled span words per (chapter_num, section_index).

    These are human-curated additions on top of whatever the regex
    detector already wrote into chapter_sections.json. Currently the
    spans dataset is empty in the repo; this loader is a no-op until
    `data/labeled/spans/*.jsonl` is populated. We trust labeled spans
    to be disjoint from regex-detected ranges (the labeler curates
    "what regex missed"), so we sum without overlap reconciliation.
    """
    if not LABELED_SPANS_DIR.exists():
        return {}
    out: dict[tuple[str, int], int] = {}
    for path in sorted(LABELED_SPANS_DIR.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = rec.get("text", "")
            cn = rec.get("chapter_num")
            si = rec.get("section_index")
            if cn is None or si is None:
                continue
            for span in rec.get("spans", []):
                if span.get("label") != "AUTHOR_NOTE":
                    continue
                s, e = int(span["start"]), int(span["end"])
                snippet = text[s:e]
                wc = len(snippet.split())
                if wc:
                    out[(cn, int(si))] = out.get((cn, int(si)), 0) + wc
    return out


def _load_cp_words_per_chapter() -> dict[str, int]:
    """Read chapter_sections.json + manual section_classifications.json
    and return cp-earning word count keyed by chapter full_title.

    The manual classifications file contains a per-section
    counts_for_cp boolean (one per (chapter_num, section_index) pair).
    For each chapter, sum the word counts of just the CP-eligible
    sections, then subtract author-note words: both the regex-detected
    ranges recorded in chapter_sections.json (`author_note_word_count`)
    and any human-labeled AUTHOR_NOTE spans from
    `data/labeled/spans/*.jsonl`.
    """
    if not SECTIONS_JSON.exists():
        raise SystemExit(
            f"missing {SECTIONS_JSON.relative_to(ROOT)}; run "
            "scripts/extract_chapter_sections.py first"
        )
    if not CLASSIFICATIONS_JSON.exists():
        raise SystemExit(
            f"missing {CLASSIFICATIONS_JSON.relative_to(ROOT)}; run "
            "scripts/build_section_classifications.py first"
        )
    sections_data = json.loads(SECTIONS_JSON.read_text())
    cls_data = json.loads(CLASSIFICATIONS_JSON.read_text())["classifications"]
    labeled_an = _load_labeled_an_words()

    out: dict[str, int] = {}
    for c in sections_data["chapters"]:
        total = 0
        for i, s in enumerate(c["sections"]):
            key = f"{c['chapter_num']}@{i}"
            if cls_data.get(key, {}).get("counts_for_cp", True):
                eligible = s["word_count"]
                eligible -= s.get("author_note_word_count", 0)
                eligible -= labeled_an.get((c["chapter_num"], i), 0)
                if eligible < 0:
                    eligible = 0
                total += eligible
        out[c["full_title"]] = total
    return out


# ---------- simulation ------------------------------------------------------


@dataclass
class PredictedRoll:
    roll_number: int
    word_position: int          # cumulative word offset where the roll fires
    chapter_num: str            # chapter containing that word position
    regime: int                 # 1, 2, or 3
    cp_threshold: int           # 100 or 200 (the per-roll requirement)


@dataclass
class _Event:
    word: int                   # cumulative word offset of this event
    kind: str                   # "chapter_start" | "acquisition"
    chapter_num: str
    perk_cost: int = 0          # for acquisitions only


def _sort_key(num: str) -> tuple[int, int]:
    parts = num.split(".", 1)
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _simulate(chapters_in_order, paid_by_chapter, exact_words):
    """Walk events in word order, simulating CP accumulation and shadows.

    Returns (predicted_rolls, summary_per_chapter). Rolls are recorded
    at the precise cumulative-word offset where they fire.
    """
    events: list[_Event] = []
    cumulative = 0
    chapter_word_start: dict[str, int] = {}
    chapter_word_end: dict[str, int] = {}

    for c in chapters_in_order:
        cn = c["chapter_num"]
        chapter_word_start[cn] = cumulative
        events.append(_Event(word=cumulative, kind="chapter_start", chapter_num=cn))
        # Slot acquisitions evenly within the chapter
        words = exact_words[c["full_title"]]
        chap_acqs = paid_by_chapter.get(cn, [])
        if chap_acqs:
            slot = words / len(chap_acqs)
            for i, a in enumerate(chap_acqs):
                offset_in_chap = (i + 0.5) * slot
                events.append(_Event(
                    word=cumulative + int(offset_in_chap),
                    kind="acquisition",
                    chapter_num=cn,
                    perk_cost=a["cost"],
                ))
        cumulative += words
        chapter_word_end[cn] = cumulative
    total_words = cumulative

    # Sort: chapter_start at a position must come BEFORE acquisitions in
    # that chapter (which share or follow that word offset).
    events.sort(key=lambda e: (e.word, 0 if e.kind == "chapter_start" else 1))

    predicted: list[PredictedRoll] = []
    banked_cp_x100 = 0          # banked CP * 100 to avoid float drift
    shadow_remaining = 0
    current_chapter = chapters_in_order[0]["chapter_num"]
    current_regime = regime_for_chapter(current_chapter)
    last_word = 0

    def fire_rolls(now_word: int) -> None:
        """Fire any rolls allowed by the current banked CP."""
        nonlocal banked_cp_x100
        threshold_x100 = REGIMES[current_regime]["cp_per_roll"] * 100
        while banked_cp_x100 >= threshold_x100:
            predicted.append(PredictedRoll(
                roll_number=len(predicted) + 1,
                word_position=now_word,
                chapter_num=current_chapter,
                regime=current_regime,
                cp_threshold=REGIMES[current_regime]["cp_per_roll"],
            ))
            banked_cp_x100 -= threshold_x100

    for event in events:
        # Words elapsed since the last event under the current regime
        elapsed = event.word - last_word
        if elapsed > 0:
            # First, burn off any active shadow
            if shadow_remaining > 0:
                consumed = min(shadow_remaining, elapsed)
                shadow_remaining -= consumed
                elapsed -= consumed
            # Whatever's left earns CP at the current regime's rate
            words_per_100 = REGIMES[current_regime]["words_per_100_cp"]
            cp_x100 = elapsed * 10000 // words_per_100   # 100 * (elapsed*100/words_per_100)
            banked_cp_x100 += cp_x100
            fire_rolls(event.word)
        last_word = event.word

        if event.kind == "chapter_start":
            current_chapter = event.chapter_num
            current_regime = regime_for_chapter(current_chapter)
        elif event.kind == "acquisition":
            sw = shadow_words(event.perk_cost, current_regime)
            if sw:
                shadow_remaining += sw

    # Drain remaining banked at end-of-story (final partial roll if any)
    fire_rolls(total_words)

    return predicted, chapter_word_start, chapter_word_end, total_words


# ---------- main ------------------------------------------------------------


def main() -> None:
    chapters_data = json.loads(CHAPTERS_JSON.read_text())
    chapters = sorted(chapters_data["chapters"], key=lambda c: tuple(c["sort_key"]))
    obtained = json.loads(OBTAINED_JSON.read_text())["perks"]

    cp_words = _load_cp_words_per_chapter()
    missing_titles = [c for c in chapters if c["full_title"] not in cp_words]
    if missing_titles:
        raise SystemExit(
            f"{len(missing_titles)} chapter title(s) in chapters.json missing "
            f"from chapter_sections.json (first: {missing_titles[0]['full_title']!r}). "
            "Re-run scripts/extract_chapter_sections.py."
        )

    paid_by_chapter: dict[str, list[dict]] = {}
    for p in obtained:
        if p["free"]:
            continue
        paid_by_chapter.setdefault(p["chapter_num"], []).append(p)

    predicted, chap_start, chap_end, total_words = _simulate(
        chapters, paid_by_chapter, cp_words,
    )

    # Cross-validate per-chapter roll counts against rolls.json (ch 1-75).
    rolls_data = json.loads(ROLLS_JSON.read_text())
    actual_per_chap: dict[str, int] = {}
    for r in rolls_data["rolls"]:
        if r["kind"] in ("trigger", "roll", "miss"):
            actual_per_chap[r["chapter_num"]] = actual_per_chap.get(r["chapter_num"], 0) + 1

    predicted_per_chap: dict[str, int] = {}
    for pr in predicted:
        predicted_per_chap[pr.chapter_num] = predicted_per_chap.get(pr.chapter_num, 0) + 1

    # Build comparison rows for chapters with actual data
    comparison = []
    for cn in sorted(actual_per_chap, key=_sort_key):
        comparison.append({
            "chapter_num": cn,
            "actual_rolls": actual_per_chap[cn],
            "predicted_rolls": predicted_per_chap.get(cn, 0),
            "delta": predicted_per_chap.get(cn, 0) - actual_per_chap[cn],
        })

    payload = {
        "_source": (
            "Simulated from chapters.json + obtained_perks.json + per-section "
            "CP-earning word counts (chapter_sections.json) using the "
            "documented three-regime model."
        ),
        "_count": len(predicted),
        "_total_words_epub_exact": total_words,
        "_regime_summary": {
            "1": "ch 1-91: 100 CP / 2000 words, roll every 100 CP",
            "2": "ch 92-96: 100 CP / 2000 words, roll every 200 CP",
            "3": "ch 97+: 100 CP / 3000 words, roll every 200 CP, "
                 "plus 9k/12k word shadow after 600/800 perks",
        },
        "_validation_chapters_1_75": {
            "actual_total_attempts": sum(actual_per_chap[cn] for cn in actual_per_chap
                                          if int(cn.split(".")[0]) <= 75),
            "predicted_total_in_same_chapters": sum(
                predicted_per_chap.get(cn, 0) for cn in actual_per_chap
                if int(cn.split(".")[0]) <= 75
            ),
        },
        "predicted": [asdict(p) for p in predicted],
        "comparison_per_chapter": comparison,
    }

    write_validated_json(OUT, payload, "predicted_rolls")

    # Print a small summary
    by_regime = {1: 0, 2: 0, 3: 0}
    for p in predicted:
        by_regime[p.regime] += 1
    print(f"wrote {OUT.relative_to(ROOT)}: {len(predicted)} predicted rolls")
    print(f"  by regime: {by_regime}")
    val = payload["_validation_chapters_1_75"]
    print(f"  ch 1-75: actual={val['actual_total_attempts']}, "
          f"predicted={val['predicted_total_in_same_chapters']}, "
          f"delta={val['predicted_total_in_same_chapters'] - val['actual_total_attempts']:+d}")
    # Show top deltas
    big_deltas = sorted(comparison, key=lambda r: -abs(r["delta"]))[:5]
    if big_deltas:
        print("  top per-chapter deltas (predicted - actual):")
        for row in big_deltas:
            print(f"    ch{row['chapter_num']:>5s}: actual={row['actual_rolls']} "
                  f"predicted={row['predicted_rolls']} delta={row['delta']:+d}")


if __name__ == "__main__":
    main()
