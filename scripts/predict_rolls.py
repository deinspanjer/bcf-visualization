"""Predict where each roll fires by simulating the mechanic word-by-word.

Reads:
  - data/derived/chapters.json
  - data/derived/obtained_perks.json
  - data/raw/Brocktons_Celestial_Forge.epub  (for exact per-chapter word counts)

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

The prediction is then cross-validated against rolls.json for
chapters 1-75 (where actual rolls are logged), and used to project
roll counts for chapters 76+ where the curator stopped maintaining.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path

from _common import write_validated_json

ROOT = Path(__file__).resolve().parent.parent
EPUB = ROOT / "data" / "raw" / "Brocktons_Celestial_Forge.epub"
CHAPTERS_JSON = ROOT / "data" / "derived" / "chapters.json"
OBTAINED_JSON = ROOT / "data" / "derived" / "obtained_perks.json"
ROLLS_JSON = ROOT / "data" / "derived" / "rolls.json"
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


# ---------- EPUB word counts (CP-earning content only) ---------------------


# MC POV identifier - the protagonist is Joe Wilkins.
_MC_NAME = "joe"

# Section headers that are always non-MC regardless of any character name.
_NON_MC_HEADER_PREFIXES = (
    "jumpchain abilities", "jumpchain perks",
    "new abilities for",
    "author", "a/n", "note",
)


def _section_counts_for_cp(header: str | None) -> bool:
    """Decide whether a section's words contribute to CP-earning.

    Per the author's mechanic and corroborated by the user:
      - Implicit pre-first-marker content (no header): counts by default.
        Usually just HTML scaffolding before the first real heading.
      - "Jumpchain abilities" / "New Abilities for" / "Note" / "Author":
        always non-MC.
      - "Preamble X" / "Addendum X" / "Interlude X": non-MC unless X
        starts with "Joe" (Joe is the MC, so "Addendum Joe" within an
        interlude chapter counts).
      - Anything else (chapter title repetitions, in-story headings):
        counts by default.
    """
    if header is None:
        return True
    h = header.strip()
    hl = h.lower()
    if any(hl.startswith(p) for p in _NON_MC_HEADER_PREFIXES):
        return False
    m = re.match(r"^(preamble|addendum|interlude)\b\s*:?\s*(.*)", h, re.I)
    if m:
        target = m.group(2).strip().lower()
        return target.startswith(_MC_NAME)
    return True


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


_MARKER_RE = re.compile(
    r"<p[^>]*>\s*<strong[^>]*>([^<]+)</strong>\s*</p>", re.IGNORECASE,
)


def _cp_earning_word_count(full_title: str, html: str) -> int:
    """Return the count of words in this chapter that contribute to CP.

    Walks all `<p><strong>X</strong></p>` section markers, splits the
    chapter into sections each headed by a marker (plus any pre-first-
    marker implicit section), and sums word counts only for sections
    whose header is MC POV per `_section_counts_for_cp`.
    """
    markers = list(_MARKER_RE.finditer(html))
    if not markers:
        return _word_count(html)

    sections: list[tuple[int, int, str | None]] = []
    if markers[0].start() > 0:
        sections.append((0, markers[0].start(), None))
    for i, m in enumerate(markers):
        start = m.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(html)
        sections.append((start, end, m.group(1)))

    total = 0
    for start, end, header in sections:
        if _section_counts_for_cp(header):
            total += _word_count(html[start:end])
    return total


def _epub_word_counts_by_full_title() -> dict[str, int]:
    """Map full_title -> CP-earning word count (post-section-filter)."""
    counts: dict[str, int] = {}
    with zipfile.ZipFile(EPUB) as zf:
        nav = zf.read("EPUB/nav.xhtml").decode("utf-8")
        for href, title in re.findall(
            r'<a[^>]*?href="([^"]+)"[^>]*>([^<]+)</a>', nav, re.DOTALL
        ):
            title = title.strip()
            if not title or title == "Introduction":
                continue
            try:
                html = zf.read(f"EPUB/{href}").decode("utf-8")
            except KeyError:
                continue
            counts[title] = _cp_earning_word_count(title, html)
    return counts


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

    # Get EPUB exact word counts. Fail loudly if the EPUB isn't there;
    # this script is build-time only.
    if not EPUB.exists():
        raise SystemExit(
            f"missing {EPUB.relative_to(ROOT)}; this script needs the source "
            "EPUB to compute exact per-chapter word counts."
        )
    exact_words = _epub_word_counts_by_full_title()
    missing_titles = [c for c in chapters if c["full_title"] not in exact_words]
    if missing_titles:
        raise SystemExit(
            f"{len(missing_titles)} chapter title(s) in chapters.json not found "
            f"in EPUB nav (first: {missing_titles[0]['full_title']!r}). "
            "Verify the EPUB matches the threadmark exports."
        )

    paid_by_chapter: dict[str, list[dict]] = {}
    for p in obtained:
        if p["free"]:
            continue
        paid_by_chapter.setdefault(p["chapter_num"], []).append(p)

    predicted, chap_start, chap_end, total_words = _simulate(
        chapters, paid_by_chapter, exact_words,
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
            "Simulated from chapters.json + obtained_perks.json + EPUB exact "
            "word counts using the documented three-regime model."
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
