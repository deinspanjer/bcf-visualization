"""Phase 2: static charts as a sanity gate over the derived data.

Reads only data/derived/*.json. Writes PNG files to figures/. Each
function produces one chart and saves to a fixed path so the output
is reproducible and reviewable in git diffs.

Run all charts:
    python3 scripts/make_charts.py
"""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
FIGURES = ROOT / "figures"

# Reference points from the documented mechanics.
CURATOR_END_CHAPTER = 75    # rolls.json stops here
MECHANIC_CHANGE_CHAPTER = 97  # ch97 author note


def _load(name: str) -> dict:
    return json.loads((DERIVED / f"{name}.json").read_text())


def _chapter_sort_key(num: str) -> tuple[int, int]:
    parts = num.split(".", 1)
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path.relative_to(ROOT)}")


# ---------- chart 1: publish pace -------------------------------------------


def chart_publish_pace() -> None:
    """Real-world publish date vs cumulative word count."""
    chapters = _load("chapters")["chapters"]
    chapters.sort(key=lambda c: c["publish_ts"])

    dates = [dt.datetime.fromtimestamp(c["publish_ts"]) for c in chapters]
    cumulative = []
    running = 0
    for c in chapters:
        running += c["words_approx"]
        cumulative.append(running)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.step(dates, cumulative, where="post", linewidth=1.5, color="tab:blue")
    ax.fill_between(dates, cumulative, step="post", alpha=0.15, color="tab:blue")

    # Annotate the two structural reference points
    annotations = [
        (CURATOR_END_CHAPTER, "ch 75: curator's roll log ends"),
        (MECHANIC_CHANGE_CHAPTER, "ch 97: mechanic change"),
    ]
    for chap_num, label in annotations:
        match = next((c for c in chapters if c["chapter_num"] == str(chap_num)), None)
        if not match:
            continue
        d = dt.datetime.fromtimestamp(match["publish_ts"])
        running_at = sum(c["words_approx"] for c in chapters if c["publish_ts"] <= match["publish_ts"])
        ax.axvline(d, color="tab:red", linestyle="--", alpha=0.5, linewidth=1)
        ax.annotate(
            label,
            xy=(d, running_at),
            xytext=(8, -10),
            textcoords="offset points",
            fontsize=9,
            color="tab:red",
        )

    ax.set_title("Brockton's Celestial Forge: cumulative word count over time")
    ax.set_xlabel("Real-world publish date")
    ax.set_ylabel("Cumulative words")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v/1000):,}k"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(True, axis="y", alpha=0.3)

    total = cumulative[-1]
    span_days = (dates[-1] - dates[0]).days
    ax.text(
        0.99, 0.05,
        f"194 chapters  ·  {total/1e6:.2f}M words  ·  {span_days} days  ·  ~{total/span_days:.0f} words/day avg",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=9, color="black",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="lightgray"),
    )
    _save(fig, FIGURES / "publish_pace.png")


# ---------- chart 2: rolls per chapter (1-75) -------------------------------


def chart_rolls_per_chapter() -> None:
    """Hits/misses per chapter for the curator-covered range."""
    rolls = _load("rolls")["rolls"]
    by_chap_hit: dict[str, int] = defaultdict(int)
    by_chap_miss: dict[str, int] = defaultdict(int)
    for r in rolls:
        if r["kind"] == "miss":
            by_chap_miss[r["chapter_num"]] += 1
        elif r["kind"] in ("trigger", "roll"):
            by_chap_hit[r["chapter_num"]] += 1

    chap_keys = sorted(set(by_chap_hit) | set(by_chap_miss), key=_chapter_sort_key)
    chap_keys = [c for c in chap_keys if c not in {"Edits:", "Reference", "Total", "0"}]

    hits = [by_chap_hit.get(c, 0) for c in chap_keys]
    misses = [by_chap_miss.get(c, 0) for c in chap_keys]
    x = list(range(len(chap_keys)))

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(x, hits, color="tab:green", label=f"perks acquired ({sum(hits)})")
    ax.bar(x, misses, bottom=hits, color="tab:gray", alpha=0.7, label=f"misses ({sum(misses)})")

    ax.set_title("Rolls per chapter (chapters 1–75, curator-covered range)")
    ax.set_xlabel("Chapter")
    ax.set_ylabel("Roll attempts in chapter")
    # Tick every Nth chapter to avoid clutter
    step = max(1, len(chap_keys) // 25)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([chap_keys[i] for i in x[::step]], rotation=45, ha="right", fontsize=8)
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, FIGURES / "rolls_per_chapter.png")


# ---------- chart 3: acquisitions per chapter (full story) ------------------


def chart_acquisitions_per_chapter() -> None:
    """Paid + free perks acquired per chapter across the full story."""
    obtained = _load("obtained_perks")["perks"]
    by_chap_paid: dict[str, int] = defaultdict(int)
    by_chap_free: dict[str, int] = defaultdict(int)
    for p in obtained:
        bucket = by_chap_free if p["free"] else by_chap_paid
        bucket[p["chapter_num"]] += 1

    chap_keys = sorted(set(by_chap_paid) | set(by_chap_free), key=_chapter_sort_key)
    paid = [by_chap_paid.get(c, 0) for c in chap_keys]
    free = [by_chap_free.get(c, 0) for c in chap_keys]
    x = list(range(len(chap_keys)))

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(x, paid, color="tab:blue", label=f"paid ({sum(paid)})")
    ax.bar(x, free, bottom=paid, color="tab:orange", alpha=0.85, label=f"free bonus ({sum(free)})")

    # Mark ch97 (mechanic change)
    try:
        idx = chap_keys.index(str(MECHANIC_CHANGE_CHAPTER))
        ax.axvline(idx, color="tab:red", linestyle="--", alpha=0.6, linewidth=1)
        y_top = max(p + f for p, f in zip(paid, free))
        ax.annotate(
            "ch 97: mechanic change",
            xy=(idx, y_top),
            xytext=(8, -20),
            textcoords="offset points",
            fontsize=9, color="tab:red", va="top",
        )
    except ValueError:
        pass

    ax.set_title("Perks acquired per chapter (full story)")
    ax.set_xlabel("Chapter")
    ax.set_ylabel("Perks acquired")
    step = max(1, len(chap_keys) // 30)
    ax.set_xticks(x[::step])
    ax.set_xticklabels([chap_keys[i] for i in x[::step]], rotation=45, ha="right", fontsize=8)
    ax.legend(loc="upper left")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, FIGURES / "acquisitions_per_chapter.png")


# ---------- chart 4: constellation growth (ch 1-75) -------------------------


_CONSTELLATION_ORDER = [
    "Toolkits", "Knowledge", "Vehicles", "Time",
    "Crafting", "Clothing", "Magic", "Quality",
    "Size", "Resources and Durability",
    "Magitech", "Alchemy", "Capstone", "Personal Reality",
]


def chart_constellation_growth() -> None:
    """Cumulative perks per constellation across chapters 1-75 from rolls.json."""
    rolls = _load("rolls")["rolls"]

    # Walk rolls in roll-number order; for each successful roll, count
    # paid+free perks and bin them by constellation.
    sequence: list[tuple[str, str]] = []   # (chapter_num, constellation)
    for r in sorted(
        (r for r in rolls if r["kind"] in ("trigger", "roll") and r["roll_number"]),
        key=lambda r: r["roll_number"],
    ):
        const = r["constellation"]
        if not const:
            continue
        for _ in r["perks"]:
            sequence.append((r["chapter_num"], const))

    # Convert to a chapter-ordered list of (chapter_idx, constellation)
    chap_order = sorted({s[0] for s in sequence}, key=_chapter_sort_key)
    chap_to_idx = {c: i for i, c in enumerate(chap_order)}

    # Cumulative count per constellation at each chapter index
    counts = {c: [0] * len(chap_order) for c in _CONSTELLATION_ORDER}
    other = [0] * len(chap_order)

    by_chap: dict[str, list[str]] = defaultdict(list)
    for ch, const in sequence:
        by_chap[ch].append(const)

    running: dict[str, int] = {c: 0 for c in _CONSTELLATION_ORDER}
    other_running = 0
    for i, ch in enumerate(chap_order):
        for const in by_chap.get(ch, []):
            if const in running:
                running[const] += 1
            else:
                other_running += 1
        for c in _CONSTELLATION_ORDER:
            counts[c][i] = running[c]
        other[i] = other_running

    fig, ax = plt.subplots(figsize=(14, 6))
    cmap = plt.colormaps["tab20"]
    series = list(_CONSTELLATION_ORDER)
    if any(other):
        series.append("(other)")
    series_data = [counts[c] if c != "(other)" else other for c in series]

    ax.stackplot(
        list(range(len(chap_order))),
        *series_data,
        labels=series,
        colors=[cmap(i % 20) for i in range(len(series))],
        alpha=0.9,
    )
    ax.set_title("Cumulative perks per constellation (chapters 1–75)")
    ax.set_xlabel("Chapter")
    ax.set_ylabel("Cumulative perks acquired (incl. free bonuses)")
    step = max(1, len(chap_order) // 25)
    ax.set_xticks(list(range(0, len(chap_order), step)))
    ax.set_xticklabels(chap_order[::step], rotation=45, ha="right", fontsize=8)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, FIGURES / "constellation_growth.png")


# ---------- chart 5: real-world vs in-world time ----------------------------


def chart_time_dilation() -> None:
    """Real-world publish dates per chapter alongside in-world timeline."""
    chapters = _load("chapters")["chapters"]
    chapters.sort(key=_chapter_sort_key_chapter)
    timeline = _load("timeline")["entries"]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7), sharex=False)

    # Top: real-world publish date per chapter
    pub = [dt.datetime.fromtimestamp(c["publish_ts"]) for c in chapters]
    ax1.scatter(range(len(chapters)), pub, s=8, color="tab:blue", alpha=0.7)
    ax1.plot(range(len(chapters)), pub, linewidth=0.5, color="tab:blue", alpha=0.4)
    ax1.set_title("Real-world publish date by chapter")
    ax1.set_ylabel("Publish date")
    ax1.yaxis.set_major_locator(mdates.YearLocator())
    ax1.yaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    step = max(1, len(chapters) // 20)
    ax1.set_xticks(list(range(0, len(chapters), step)))
    ax1.set_xticklabels([chapters[i]["chapter_num"] for i in range(0, len(chapters), step)],
                        rotation=45, ha="right", fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Bottom: in-world timeline. Split events into "backstory references"
    # (mentioned but not actively narrated) and "actively-narrated days"
    # (the protagonist's experienced time). The split is by date - the
    # "Story Begins" entry on 2011-04-08 is the boundary, regardless of
    # which curator contributed each entry.
    iso_entries = [e for e in timeline if e["in_world_date_iso"]]
    iso_entries.sort(key=lambda e: e["in_world_date_iso"])
    STORY_START_ISO = "2011-04-08"
    backstory = [e for e in iso_entries if e["in_world_date_iso"] < STORY_START_ISO]
    in_story = [e for e in iso_entries if e["in_world_date_iso"] >= STORY_START_ISO]
    bs_dates = [dt.date.fromisoformat(e["in_world_date_iso"]) for e in backstory]
    is_dates = [dt.date.fromisoformat(e["in_world_date_iso"]) for e in in_story]

    ax2.scatter(bs_dates, [0.5] * len(bs_dates), s=40, c="tab:purple",
                alpha=0.7, label=f"backstory references ({len(bs_dates)})")
    ax2.scatter(is_dates, [0.5] * len(is_dates), s=40, c="tab:green",
                alpha=0.85, label=f"actively-narrated days ({len(is_dates)})")

    # Story-start divider line
    if is_dates:
        story_start = dt.date.fromisoformat(STORY_START_ISO)
        ax2.axvline(story_start, color="tab:red", linestyle="--", alpha=0.5, linewidth=1)
        ax2.annotate(
            f"Story begins\n{STORY_START_ISO}",
            xy=(story_start, 0.5),
            xytext=(0, 50),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=8, color="tab:red",
            arrowprops=dict(arrowstyle="-", color="tab:red", linewidth=0.6, alpha=0.5),
        )

    ax2.set_title("In-world timeline events")
    ax2.set_xlabel("In-world date")
    ax2.set_ylim(0, 1.5)
    ax2.set_yticks([])
    ax2.xaxis.set_major_locator(mdates.YearLocator())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax2.grid(True, axis="x", alpha=0.3)
    ax2.legend(loc="upper left", fontsize=9)

    rw_span_days = (pub[-1] - pub[0]).days
    in_story_span = (is_dates[-1] - is_dates[0]).days if len(is_dates) >= 2 else 0
    fig.suptitle(
        f"Time dilation: {rw_span_days} real-world days of writing cover "
        f"~{in_story_span} actively-narrated in-story days "
        f"(ratio ~{rw_span_days // max(in_story_span, 1)}:1). Backstory references "
        f"reach back to 2007 but aren't narrated time.",
        fontsize=11, y=1.0,
    )
    fig.tight_layout()
    _save(fig, FIGURES / "time_dilation.png")


def _chapter_sort_key_chapter(c: dict) -> tuple[int, int]:
    return tuple(c["sort_key"])  # type: ignore[return-value]


# ---------- main ------------------------------------------------------------


def main() -> None:
    print("Generating Phase 2 charts...")
    chart_publish_pace()
    chart_rolls_per_chapter()
    chart_acquisitions_per_chapter()
    chart_constellation_growth()
    chart_time_dilation()
    print("done.")


if __name__ == "__main__":
    main()
