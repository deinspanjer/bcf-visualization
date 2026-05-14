"""Phase 2: static charts as a sanity gate over the derived data.

Reads only data/derived/*.json. Writes PNG files to figures/. Each
function produces one chart and saves to a fixed path so the output
is reproducible and reviewable in git diffs.

Style: leans on Tufte's principles — minimal grids, range-frame axes,
direct labels rather than legends, gray for context, saturated color
only where the chart's argument lives.

Run all charts:
    python3 scripts/make_charts.py
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "derived"
FIGURES = ROOT / "figures"

# Reference points from the documented mechanics.
CURATOR_END_CHAPTER = 75       # rolls.json stops here
MECHANIC_CHANGE_R1 = 91         # ch91 cadence change
MECHANIC_CHANGE_R2 = 97         # ch97 rate + shadow change
MECHANIC_CHANGE_CHAPTER = MECHANIC_CHANGE_R2  # legacy alias

REGIME_COLORS = {1: "#cfd8e8", 2: "#e8d5c0", 3: "#e0c8d8"}  # muted band tints


def _load(name: str) -> dict:
    return json.loads((DERIVED / f"{name}.json").read_text())


def _chapter_sort_key(num: str) -> tuple[int, int]:
    parts = num.split(".", 1)
    return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def _regime(chapter_num: str) -> int:
    """1 = original (ch ≤ 91), 2 = ch91 cadence change, 3 = ch97 rate + shadow."""
    major = int(chapter_num.split(".")[0])
    if major <= MECHANIC_CHANGE_R1:
        return 1
    if major < MECHANIC_CHANGE_R2:
        return 2
    return 3


def _strip_chartjunk(ax, keep=("bottom", "left")) -> None:
    """Remove the spines we don't want and make the kept ones thin."""
    for side, spine in ax.spines.items():
        if side in keep:
            spine.set_linewidth(0.6)
            spine.set_color("0.4")
        else:
            spine.set_visible(False)
    ax.tick_params(direction="out", length=3, width=0.6, color="0.4", labelsize=9)


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {path.relative_to(ROOT)}")


# ---------- chart 1: publish pace -------------------------------------------


def chart_publish_pace() -> None:
    """Cumulative word count over real-world publish date.

    Regime backgrounds shaded; regime change events labelled inline;
    year-end totals labelled directly on the line. No legend, no fill,
    no decorative box.
    """
    chapters = _load("chapters")["chapters"]
    chapters.sort(key=lambda c: c["publish_ts"])

    dates = [dt.datetime.fromtimestamp(c["publish_ts"]) for c in chapters]
    cumulative: list[int] = []
    running = 0
    for c in chapters:
        running += c["words_approx"]
        cumulative.append(running)

    fig, ax = plt.subplots(figsize=(12, 5.5))

    # Regime band backgrounds: shade the date span of each regime.
    regime_dates: dict[int, list[dt.datetime]] = defaultdict(list)
    for d, c in zip(dates, chapters):
        regime_dates[_regime(c["chapter_num"])].append(d)
    for r, ds in regime_dates.items():
        ax.axvspan(min(ds), max(ds), color=REGIME_COLORS[r], alpha=0.45, zorder=0)

    ax.plot(dates, cumulative, linewidth=1.4, color="0.15", zorder=2)

    # Regime change markers: thin vertical lines reaching from line to top,
    # labels float in the upper area so they don't collide with year labels
    # which sit directly on the curve.
    y_top = max(cumulative) * 1.04
    # ha="right" makes the text extend leftward from the anchor; "left"
    # extends rightward. We want labels to flow OUT into the wide open
    # space, not in toward each other.
    changes = [
        (MECHANIC_CHANGE_R1, "ch 91: cadence → 200 CP/roll ", "right"),
        (MECHANIC_CHANGE_R2, " ch 97: words rate + 600/800 shadow", "left"),
    ]
    for chap_num, label, ha in changes:
        match = next((c for c in chapters if c["chapter_num"] == str(chap_num)), None)
        if not match:
            continue
        d = dt.datetime.fromtimestamp(match["publish_ts"])
        running_at = sum(
            c["words_approx"] for c in chapters
            if c["publish_ts"] <= match["publish_ts"]
        )
        ax.plot([d, d], [running_at, y_top], color="0.4", linewidth=0.6, zorder=1)
        ax.annotate(
            label,
            xy=(d, y_top),
            xytext=(0, -2),
            textcoords="offset points",
            fontsize=8.5,
            color="0.2",
            ha=ha, va="top",
        )

    # Year-end labels: direct labels on the line at each Dec-31 (or final point).
    by_year: dict[str, tuple[dt.datetime, int]] = {}
    for d, total in zip(dates, cumulative):
        by_year[d.strftime("%Y")] = (d, total)
    last_year = max(by_year)
    for y, (d, total) in by_year.items():
        if y == last_year:
            continue
        ax.annotate(
            f" {y}: {total/1e6:.2f}M",
            xy=(d, total),
            xytext=(2, 4),
            textcoords="offset points",
            fontsize=8.5,
            color="0.25",
        )
    ax.annotate(
        f" {last_year}: {by_year[last_year][1]/1e6:.2f}M words total",
        xy=by_year[last_year],
        xytext=(4, 0),
        textcoords="offset points",
        fontsize=9.5,
        color="0.0",
        weight="bold",
        va="center",
    )

    # Range-frame: spines span the data range only.
    _strip_chartjunk(ax)
    ax.spines["bottom"].set_bounds(mdates.date2num(min(dates)), mdates.date2num(max(dates)))
    ax.spines["left"].set_bounds(0, max(cumulative))

    ax.set_title("Cumulative word count by publish date  ·  regimes shaded",
                 fontsize=11, color="0.1", loc="left", pad=10)
    ax.set_xlabel("")
    ax.set_ylabel("words", fontsize=9, color="0.3")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v/1000):,}k"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylim(0, max(cumulative) * 1.05)
    ax.set_xlim(min(dates) - dt.timedelta(days=20),
                max(dates) + dt.timedelta(days=160))   # right margin for labels
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
    """Small multiples: one mini-chart per constellation, all on the same axes.

    Replaces the previous stacked area, which Tufte criticizes because
    every series except the bottom one sits on a wobbling baseline.
    Small multiples let the eye compare each constellation's growth
    independently while still showing the full set at a glance.
    """
    rolls = _load("rolls")["rolls"]

    sequence: list[tuple[str, str]] = []
    for r in sorted(
        (r for r in rolls if r["kind"] in ("trigger", "roll") and r["roll_number"]),
        key=lambda r: r["roll_number"],
    ):
        const = r["constellation"]
        if not const:
            continue
        for _ in r["perks"]:
            sequence.append((r["chapter_num"], const))

    chap_order = sorted({s[0] for s in sequence}, key=_chapter_sort_key)
    by_chap: dict[str, list[str]] = defaultdict(list)
    for ch, const in sequence:
        by_chap[ch].append(const)

    counts: dict[str, list[int]] = {c: [0] * len(chap_order) for c in _CONSTELLATION_ORDER}
    running: dict[str, int] = {c: 0 for c in _CONSTELLATION_ORDER}
    for i, ch in enumerate(chap_order):
        for const in by_chap.get(ch, []):
            if const in running:
                running[const] += 1
        for c in _CONSTELLATION_ORDER:
            counts[c][i] = running[c]

    # Sort panels by total at end of range, descending — visual ordering
    # is itself information.
    ordered = sorted(_CONSTELLATION_ORDER, key=lambda c: -counts[c][-1])
    y_max = max(counts[c][-1] for c in ordered)

    n = len(ordered)
    rows, cols = 4, 4
    fig, axes = plt.subplots(rows, cols, figsize=(13, 8.5), sharex=True, sharey=True)
    x = list(range(len(chap_order)))

    for i, const in enumerate(ordered):
        ax = axes[i // cols][i % cols]
        # Context: thin gray line of the largest constellation (Toolkits)
        ax.plot(x, counts[ordered[0]], color="0.85", linewidth=0.7, zorder=1)
        # The series this panel is about
        ax.plot(x, counts[const], color="tab:blue", linewidth=1.4, zorder=2)
        ax.text(0.04, 0.92, const, transform=ax.transAxes,
                fontsize=9, color="0.1", weight="bold", va="top")
        ax.text(0.04, 0.78, f"final: {counts[const][-1]}", transform=ax.transAxes,
                fontsize=8, color="0.4", va="top")
        _strip_chartjunk(ax)
        ax.set_xlim(0, len(chap_order) - 1)
        ax.set_ylim(0, y_max * 1.05)
        ax.spines["bottom"].set_bounds(0, len(chap_order) - 1)
        ax.spines["left"].set_bounds(0, y_max)
        ax.tick_params(labelsize=8)

    # Hide unused panels (16 cells, 14 constellations)
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")

    # Bottom-row chapter ticks
    step = max(1, len(chap_order) // 6)
    for ax in axes[-1]:
        if ax.has_data():
            ax.set_xticks(x[::step])
            ax.set_xticklabels([chap_order[i] for i in x[::step]],
                               rotation=45, ha="right", fontsize=7)

    fig.suptitle(
        "Cumulative perks acquired by constellation, chapters 1–75  "
        "·  small multiples sorted by final total  "
        "·  thin gray line = Toolkits (largest) for context",
        fontsize=11, y=0.995, color="0.1",
    )
    fig.supxlabel("Chapter", fontsize=9, color="0.3")
    fig.supylabel("Cumulative perks (incl. free bonuses)", fontsize=9, color="0.3")
    fig.tight_layout()
    _save(fig, FIGURES / "constellation_growth.png")


# ---------- chart 6: throughput by year (small multiples) -------------------


def chart_throughput_by_year() -> None:
    """Small multiples: one panel per calendar year, cumulative words within year.

    Same axes (Jan 1 → Dec 31, 0 → max) across all panels so slopes are
    directly comparable. Steeper slope = faster pace that year.
    """
    chapters = _load("chapters")["chapters"]
    chapters.sort(key=lambda c: c["publish_ts"])

    by_year: dict[str, list[tuple[dt.date, int]]] = defaultdict(list)
    for c in chapters:
        d = dt.datetime.fromtimestamp(c["publish_ts"]).date()
        by_year[d.strftime("%Y")].append((d, c["words_approx"]))

    years = sorted(by_year)
    n = len(years)
    cols = min(4, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(13, 3.2 * rows),
                             sharex=True, sharey=True)
    if rows == 1:
        axes = [axes]
    elif cols == 1:
        axes = [[a] for a in axes]

    # X domain: day-of-year 1..366 (handle leap years)
    # Y domain: max year-cumulative across all years
    max_y = 0
    year_cumulative: dict[str, list[tuple[int, int]]] = {}
    for y in years:
        running = 0
        seq = []
        for d, w in sorted(by_year[y]):
            running += w
            doy = d.timetuple().tm_yday
            seq.append((doy, running))
        year_cumulative[y] = seq
        max_y = max(max_y, running)

    for i, y in enumerate(years):
        ax = axes[i // cols][i % cols]
        seq = year_cumulative[y]
        xs = [doy for doy, _ in seq]
        ys = [w for _, w in seq]
        # Light gray context: all other years' final lines
        for other in years:
            if other == y:
                continue
            o_seq = year_cumulative[other]
            ax.plot([d for d, _ in o_seq], [w for _, w in o_seq],
                    color="0.88", linewidth=0.6, zorder=1)
        ax.plot(xs, ys, color="tab:blue", linewidth=1.6, zorder=3)
        ax.scatter(xs, ys, s=8, color="tab:blue", zorder=4)
        # Inline label: year + total + chapter count
        ax.text(0.04, 0.94, y, transform=ax.transAxes,
                fontsize=11, color="0.1", weight="bold", va="top")
        n_chap = len(seq)
        total = ys[-1] if ys else 0
        first_d = sorted(by_year[y])[0][0]
        last_d = sorted(by_year[y])[-1][0]
        span = (last_d - first_d).days + 1
        rate = total / span if span else 0
        ax.text(0.04, 0.84, f"{n_chap} chapters · {total/1000:.0f}k words",
                transform=ax.transAxes, fontsize=8.5, color="0.3", va="top")
        ax.text(0.04, 0.76, f"{rate:.0f} words/day (active)",
                transform=ax.transAxes, fontsize=8.5, color="0.3", va="top")
        _strip_chartjunk(ax)
        ax.set_xlim(0, 366)
        ax.set_ylim(0, max_y * 1.1)
        ax.spines["bottom"].set_bounds(0, 365)
        ax.spines["left"].set_bounds(0, max_y)
        # Month-name x ticks
        month_starts = [1, 91, 182, 274]
        ax.set_xticks(month_starts)
        ax.set_xticklabels(["Jan", "Apr", "Jul", "Oct"], fontsize=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v/1000)}k"))
        ax.tick_params(labelsize=8)

    # Hide unused
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")

    fig.suptitle(
        "Word-count throughput by year  ·  small multiples, same axes  "
        "·  thin gray = all other years for context",
        fontsize=11, y=0.995, color="0.1",
    )
    fig.tight_layout()
    _save(fig, FIGURES / "throughput_by_year.png")


# ---------- chart 7: throughput by mechanic regime --------------------------


def chart_throughput_by_regime() -> None:
    """Cleveland dot plot: four metrics, each compared across the three regimes.

    The slope between dots within a metric tells the story of how the
    rule changes affected each pace measure. Words/acquisition is the
    headline: rules tripled the words spent per perk in regime 3.
    """
    chapters = _load("chapters")["chapters"]
    obtained = _load("obtained_perks")["perks"]

    by_regime: dict[int, dict[str, float]] = {}
    for r_id in (1, 2, 3):
        chs = [c for c in chapters if _regime(c["chapter_num"]) == r_id]
        if not chs:
            continue
        words = sum(c["words_approx"] for c in chs)
        n_chap = len(chs)
        first_d = min(dt.datetime.fromtimestamp(c["publish_ts"]) for c in chs)
        last_d = max(dt.datetime.fromtimestamp(c["publish_ts"]) for c in chs)
        span_days = (last_d - first_d).days + 1
        n_acq = sum(1 for p in obtained if _regime(p["chapter_num"]) == r_id)
        wpc = [c["words_approx"] for c in chs]
        by_regime[r_id] = {
            "chapters": n_chap,
            "words": words,
            "span_days": span_days,
            "words_per_day": words / span_days,
            "words_per_chapter_median": statistics.median(wpc),
            "acquisitions": n_acq,
            "words_per_acquisition": words / max(n_acq, 1),
        }

    metrics = [
        ("Words per real-world day",      "words_per_day",            "{:.0f}"),
        ("Words per chapter (median)",    "words_per_chapter_median", "{:.0f}"),
        ("Words per perk acquired",       "words_per_acquisition",    "{:.0f}"),
        ("Chapters published per month",  None,                       "{:.1f}"),
    ]

    # Plug in chapters/month
    for r_id, s in by_regime.items():
        s["chapters_per_month"] = s["chapters"] / (s["span_days"] / 30.44)

    metrics[3] = ("Chapters published per month", "chapters_per_month", "{:.1f}")

    regime_labels = [
        "Regime 1\nch 1–91\n(original)",
        "Regime 2\nch 92–96\n(ch91 cadence)",
        "Regime 3\nch 97+\n(rate + shadow)",
    ]
    regime_colors = ["#3b6ea5", "#a3733b", "#a33b6e"]

    fig, axes = plt.subplots(1, 4, figsize=(13, 4.5))

    for ax_i, (label, key, fmt) in enumerate(metrics):
        ax = axes[ax_i]
        values = [by_regime[r][key] for r in (1, 2, 3)]
        x_positions = [0, 1, 2]
        ax.plot(x_positions, values, color="0.7", linewidth=0.8, zorder=1)
        for i, (xv, v) in enumerate(zip(x_positions, values)):
            ax.scatter(xv, v, s=70, color=regime_colors[i], zorder=3,
                       edgecolor="white", linewidth=1.2)
            ax.text(xv, v, "  " + fmt.format(v),
                    fontsize=9, color="0.1", va="center", ha="left")
        ax.set_title(label, fontsize=10, color="0.1", pad=10)
        ax.set_xticks(x_positions)
        ax.set_xticklabels(regime_labels, fontsize=7.5, color="0.3")
        _strip_chartjunk(ax, keep=("bottom",))
        ax.spines["bottom"].set_visible(False)
        ax.tick_params(axis="x", length=0)
        ax.tick_params(axis="y", labelleft=False, length=0)
        lo = min(values) * 0.7
        hi = max(values) * 1.4
        ax.set_ylim(lo, hi)
        ax.set_yticks([])

    fig.suptitle(
        "Word-count throughput across the three mechanic regimes  ·  "
        "dot per regime, slope between shows direction of change",
        fontsize=11, y=1.02, color="0.1",
    )
    fig.text(
        0.5, -0.01,
        "Regime 1: 100 CP/2000 words, roll every 100 CP.   "
        "Regime 2: same rate, roll every 200 CP.   "
        "Regime 3: 100 CP/3000 words, roll every 200 CP, plus 9k/12k word shadow on 600/800 perks.",
        fontsize=8, color="0.45", ha="center", style="italic",
    )
    fig.tight_layout()
    _save(fig, FIGURES / "throughput_by_regime.png")


# ---------- chart 8: words per perk acquired (high resolution) --------------


def _regime_markers(chapters: list[dict]) -> list[tuple[dt.datetime, str, str]]:
    """Return (date, label, ha) for each regime change to draw on time-axes."""
    markers = []
    for chap_num, label, ha in [
        (str(MECHANIC_CHANGE_R1), "ch 91", "right"),
        (str(MECHANIC_CHANGE_R2), "ch 97", "left"),
    ]:
        c = next((c for c in chapters if c["chapter_num"] == chap_num), None)
        if c:
            markers.append((dt.datetime.fromtimestamp(c["publish_ts"]), label, ha))
    return markers


def chart_words_per_perk() -> None:
    """Words spent between consecutive paid acquisitions, per acquisition.

    For chapters with multiple acquisitions, the chapter's word count
    is distributed evenly across them so each has a positional offset
    in cumulative-words. Scatter shows raw per-acquisition deltas
    (noisy by nature); a rolling median over a 21-acquisition window
    shows the trend. Regime change markers anchor the regime shifts.
    """
    chapters = _load("chapters")["chapters"]
    obtained = _load("obtained_perks")["perks"]
    chap_ordered = sorted(chapters, key=lambda c: c["publish_ts"])
    chap_pub = {c["chapter_num"]: dt.datetime.fromtimestamp(c["publish_ts"])
                for c in chap_ordered}

    # Cumulative words at start of each chapter
    chapter_word_start: dict[str, int] = {}
    running = 0
    for c in chap_ordered:
        chapter_word_start[c["chapter_num"]] = running
        running += c["words_approx"]

    chap_words = {c["chapter_num"]: c["words_approx"] for c in chapters}

    # Group paid acquisitions by chapter, preserving order
    acqs_by_chap: dict[str, list[dict]] = defaultdict(list)
    for p in obtained:
        if p["free"]:
            continue
        if p["chapter_num"] not in chapter_word_start:
            continue
        acqs_by_chap[p["chapter_num"]].append(p)

    # Sort chapters in publish order, then assign each acquisition a
    # cumulative-word position (chapter_start + slot * words_per_slot).
    points: list[dict] = []
    for c in chap_ordered:
        cn = c["chapter_num"]
        chap_acqs = acqs_by_chap.get(cn, [])
        if not chap_acqs:
            continue
        slot = chap_words[cn] / len(chap_acqs)
        for i, _ in enumerate(chap_acqs):
            position = chapter_word_start[cn] + (i + 0.5) * slot
            points.append({
                "chapter_num": cn,
                "publish_dt": chap_pub[cn],
                "cumulative_words_at_acq": position,
            })

    # Words since previous paid acquisition
    prev = 0
    for p in points:
        p["delta"] = p["cumulative_words_at_acq"] - prev
        prev = p["cumulative_words_at_acq"]

    if not points:
        return

    fig, ax = plt.subplots(figsize=(13, 5))

    xs = [p["publish_dt"] for p in points]
    ys = [p["delta"] for p in points]

    # Scatter (light, the underlying noise)
    ax.scatter(xs, ys, s=14, color="0.7", alpha=0.8, zorder=2)

    # Rolling median (the signal)
    window = 21
    half = window // 2
    smoothed = []
    smoothed_x = []
    for i in range(len(points)):
        lo = max(0, i - half)
        hi = min(len(points), i + half + 1)
        smoothed.append(statistics.median(ys[lo:hi]))
        smoothed_x.append(xs[i])
    ax.plot(smoothed_x, smoothed, color="tab:blue", linewidth=1.8, zorder=3)

    # Regime markers
    y_top = max(ys) * 1.04
    for d, label, ha in _regime_markers(chapters):
        ax.axvline(d, color="0.4", linewidth=0.6, zorder=1)
        x_off = -4 if ha == "right" else 4
        ax.annotate(
            label,
            xy=(d, y_top),
            xytext=(x_off, -2),
            textcoords="offset points",
            fontsize=9, color="0.2",
            ha=ha, va="top",
        )

    # Direct label on the rolling median at the right edge
    ax.annotate(
        f"  rolling median\n  (window=21)",
        xy=(smoothed_x[-1], smoothed[-1]),
        xytext=(8, 0),
        textcoords="offset points",
        fontsize=9, color="tab:blue", va="center",
    )

    _strip_chartjunk(ax)
    ax.set_title(
        "Words written between paid acquisitions  ·  per-acquisition scatter, rolling-median trend",
        fontsize=11, color="0.1", loc="left", pad=10,
    )
    ax.set_ylabel("words since previous paid acquisition", fontsize=9, color="0.3")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{int(v/1000):,}k"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylim(0, max(ys) * 1.08)
    ax.set_xlim(min(xs) - dt.timedelta(days=20),
                max(xs) + dt.timedelta(days=200))
    ax.spines["bottom"].set_bounds(mdates.date2num(min(xs)), mdates.date2num(max(xs)))
    ax.spines["left"].set_bounds(0, max(ys))
    _save(fig, FIGURES / "words_per_perk.png")


# ---------- chart 9: monthly throughput dashboard ---------------------------


def chart_monthly_throughput() -> None:
    """Three-panel monthly bar chart: chapters/month, words/month, median chapter size.

    Bars at monthly resolution, regime change markers as thin vertical
    lines on each panel. Bar color shifts by regime.
    """
    chapters = _load("chapters")["chapters"]
    chap_ordered = sorted(chapters, key=lambda c: c["publish_ts"])

    by_month: dict[str, list[dict]] = defaultdict(list)
    for c in chap_ordered:
        d = dt.datetime.fromtimestamp(c["publish_ts"]).date()
        key = f"{d.year:04d}-{d.month:02d}"
        by_month[key].append(c)

    months = sorted(by_month)
    month_dates = [dt.date(int(m.split("-")[0]), int(m.split("-")[1]), 15) for m in months]

    chap_counts = [len(by_month[m]) for m in months]
    word_sums = [sum(c["words_approx"] for c in by_month[m]) for m in months]
    median_lengths = [statistics.median(c["words_approx"] for c in by_month[m]) for m in months]

    # Color each bar by regime (use first chapter in the month to pick)
    regime_colors_bg = ["#3b6ea5", "#a3733b", "#a33b6e"]
    bar_colors = []
    for m in months:
        first_chap = sorted(by_month[m], key=lambda c: c["publish_ts"])[0]
        bar_colors.append(regime_colors_bg[_regime(first_chap["chapter_num"]) - 1])

    fig, axes = plt.subplots(3, 1, figsize=(13, 8.5), sharex=True)
    panels = [
        (axes[0], chap_counts, "Chapters published per month",
         lambda v, _: f"{int(v)}"),
        (axes[1], word_sums,   "Words published per month",
         lambda v, _: f"{int(v/1000):,}k"),
        (axes[2], median_lengths, "Median chapter word count per month",
         lambda v, _: f"{int(v/1000)}k"),
    ]

    markers = _regime_markers(chap_ordered)

    for ax, ys, title, fmt in panels:
        ax.bar(month_dates, ys, width=24, color=bar_colors,
               edgecolor="white", linewidth=0.4, zorder=2)
        # Regime markers
        y_top = max(ys) * 1.05
        for d, label, ha in markers:
            ax.axvline(d.date(), color="0.3", linewidth=0.7, zorder=1)
        ax.set_ylabel(title, fontsize=9.5, color="0.2")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(fmt))
        _strip_chartjunk(ax)
        ax.set_ylim(0, max(ys) * 1.12)
        ax.spines["bottom"].set_bounds(
            mdates.date2num(min(month_dates)),
            mdates.date2num(max(month_dates)),
        )
        ax.spines["left"].set_bounds(0, max(ys))

    # Only the top panel gets regime change labels
    y_top = max(chap_counts) * 1.10
    for d, label, ha in markers:
        x_off = -4 if ha == "right" else 4
        axes[0].annotate(label, xy=(d.date(), y_top),
                         xytext=(x_off, -2), textcoords="offset points",
                         fontsize=9, color="0.2", ha=ha, va="top")

    axes[-1].xaxis.set_major_locator(mdates.YearLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].set_xlim(min(month_dates) - dt.timedelta(days=20),
                      max(month_dates) + dt.timedelta(days=20))

    fig.suptitle(
        "Monthly throughput  ·  bar color encodes regime  ·  "
        "blue = regime 1, brown = regime 2, magenta = regime 3",
        fontsize=11, y=0.995, color="0.1",
    )
    fig.tight_layout()
    _save(fig, FIGURES / "monthly_throughput.png")


# ---------- chart 5: real-world vs in-world time ----------------------------


STORY_START_ISO = "2011-04-08"

# Best-guess mapping of timeline events to story chapter numbers, derived
# from event descriptions matched against chapter titles. The two anchor
# points are well-supported (ch 3 "First Fight" = April 10, ch 35
# "Closing Words" = April 19 with Master Craftsman acquisition); the rest
# are approximate. Replacing this with a deterministic chapter→in-world
# mapping is the Future Work item that pairs with word-count→roll
# matching.
_TIMELINE_CHAPTER_BY_DATE: dict[str, str] = {
    "2011-04-08": "1",    # Story Begins → ch 1 (Introduction)
    "2011-04-10": "3",    # First Fight - title match
    "2011-04-14": "5",    # bank robbery → ch 5 (Negotiation)
    "2011-04-15": "7",    # Garment Gloves, motorcycle → ch 7 (Accessory)
    "2011-04-16": "9",    # Bakuda fight, ABB bombings → ch 8-10 area
    "2011-04-17": "13",   # rescues Weld
    "2011-04-18": "19",   # ABB financial center, Aisha rescue
    "2011-04-19": "35",   # Master Craftsman acquired - per obtained_perks
    "2011-04-20": "42",
    "2011-04-21": "50",
    "2011-04-22": "56",
    "2011-04-23": "62",
    "2011-04-24": "68",
    "2011-04-25": "75",
}


def chart_time_dilation() -> None:
    """In-world day progression vs real-world days and cumulative words.

    The actually-narrated story spans April 8-25 2011 (17 days, 14
    dated events). This chart shows how slowly that in-world clock
    advances compared to two real-world dimensions:
      - real-world calendar days since chapter 1 was published
      - cumulative word count

    Both panels share a y-axis (in-world day) so the eye can compare
    how the same in-world progression maps to each real-world axis.
    The vertical axes are otherwise mostly empty space on the right
    side - that's the time-dilation message: in-world barely moves
    while the x-axes span huge distances.
    """
    chapters = _load("chapters")["chapters"]
    chapters.sort(key=_chapter_sort_key_chapter)

    # Cumulative word count and elapsed real-world days per chapter
    pub_dt0 = dt.datetime.fromtimestamp(chapters[0]["publish_ts"])
    cumulative_words_by_chapter: dict[str, int] = {}
    rw_days: dict[str, int] = {}
    running = 0
    for c in chapters:
        running += c["words_approx"]
        cumulative_words_by_chapter[c["chapter_num"]] = running
        d = dt.datetime.fromtimestamp(c["publish_ts"])
        rw_days[c["chapter_num"]] = (d - pub_dt0).days

    timeline = _load("timeline")["entries"]
    story_start = dt.date.fromisoformat(STORY_START_ISO)

    rows = []
    for e in timeline:
        iso = e["in_world_date_iso"]
        if not iso or iso < STORY_START_ISO:
            continue
        chap = _TIMELINE_CHAPTER_BY_DATE.get(iso)
        if chap is None or chap not in cumulative_words_by_chapter:
            continue
        in_world_day = (dt.date.fromisoformat(iso) - story_start).days  # 0..17
        rows.append({
            "in_world_day": in_world_day,
            "in_world_date": iso,
            "chapter": chap,
            "rw_days": rw_days[chap],
            "cumulative_words": cumulative_words_by_chapter[chap],
            "events": e.get("events") or e.get("event_text", ""),
        })
    rows.sort(key=lambda r: r["in_world_day"])

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 6), sharey=True)

    def draw_panel(ax, x_values, x_label, x_format):
        x = list(x_values)
        y = [r["in_world_day"] for r in rows]
        ax.step(x, y, where="post", color="0.15", linewidth=1.4, zorder=2)
        ax.scatter(x, y, s=42, color="tab:green", zorder=3,
                   edgecolor="0.15", linewidth=0.5)
        # First and last point labels (Tufte-style direct labelling)
        first = rows[0]
        last = rows[-1]
        ax.annotate(f"  Day 0\n  Apr 8 (ch {first['chapter']})",
                    xy=(x[0], y[0]), xytext=(8, -2), textcoords="offset points",
                    fontsize=8.5, color="0.2", va="top")
        ax.annotate(f"Day {last['in_world_day']}\nApr 25 (ch {last['chapter']})  ",
                    xy=(x[-1], y[-1]), xytext=(-8, 2), textcoords="offset points",
                    fontsize=8.5, color="0.2", ha="right", va="bottom")
        ax.set_xlabel(x_label, color="0.3")
        ax.set_ylim(-0.7, last["in_world_day"] + 1.2)
        ax.set_yticks(range(0, last["in_world_day"] + 1, 2))
        ax.xaxis.set_major_formatter(plt.FuncFormatter(x_format))
        _strip_chartjunk(ax)
        ax.spines["bottom"].set_bounds(0, max(x))
        ax.spines["left"].set_bounds(0, last["in_world_day"])

    axL.set_ylabel("In-world day (since story begin)", color="0.3")
    draw_panel(axL,
               (r["rw_days"] for r in rows),
               "Real-world days since chapter 1 published",
               lambda v, _: f"{int(v):,}")
    draw_panel(axR,
               (r["cumulative_words"] for r in rows),
               "Cumulative words in story",
               lambda v, _: f"{int(v/1e6*100)/100}M" if v >= 1e6 else f"{int(v/1000)}k")

    # Title with the punchline at the right scale
    last = rows[-1]
    ratio_days = last["rw_days"] / max(last["in_world_day"], 1)
    ratio_words = last["cumulative_words"] / max(last["in_world_day"], 1)
    fig.suptitle(
        f"In-world time dilation: 17 narrated days unfold over "
        f"~{last['rw_days']} real-world days of writing and "
        f"~{last['cumulative_words']/1e6:.1f}M words "
        f"(roughly {ratio_days:.0f} real-world days and {ratio_words/1e3:.0f}k words per in-world day)",
        fontsize=11, y=1.0, color="0.1",
    )
    # Caveat about chapter mapping
    fig.text(
        0.5, -0.02,
        "Chapter mapping for each in-world day is approximate (best-effort match of "
        "timeline-event descriptions to chapter titles). "
        "Day 0 = April 8 2011; Day 17 = April 25 2011.",
        fontsize=8, color="0.45", ha="center", style="italic",
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
    chart_throughput_by_year()
    chart_throughput_by_regime()
    chart_words_per_perk()
    chart_monthly_throughput()
    print("done.")


if __name__ == "__main__":
    main()
