"""Forge Curator TUI (Phase 1 read-only viewer).

Three-panel layout: stats (left), prose with cursor (centre, with a
gutter column), actions catalog (right, disabled in Phase 1). A regex
strip and status bar live at the bottom.

Vim-style cursor motions are inherited from the Forge Curator passage
view widget.

Run with::

    python -m scripts.forge_curator [--chapter X[.Y]]

F12 or Ctrl-S writes the current TUI state to
data/manual/.forge_curator_snapshot.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from rich.console import Console
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult, ScreenStackError
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from scripts.forge_curator.data_loader import ForgeCuratorData
from scripts.forge_curator.data_loader import MANUAL, ROOT
from scripts.forge_curator.passage_view import PassageView as BasePassageView
from scripts.forge_curator.persistence import CurationPersistence
from scripts.forge_curator.state import ForgeCuratorState
from scripts.eligibility_spans import section_cp_word_count, section_span_overrides

STATE_FILE = MANUAL / ".forge_curator_state.json"
# Fixed location for the TUI snapshot. Repeated use overwrites this file so
# "look at the snapshot" can mean one stable artifact.
SNAPSHOT_PATH = MANUAL / ".forge_curator_snapshot.json"

KNOWN_CONSTELLATIONS = [
    "Alchemy", "Capstone", "Clothing", "Crafting", "Knowledge",
    "Magic", "Magitech", "Personal Reality", "Quality",
    "Resources and Durability", "Size", "Time", "Toolkits", "Vehicles",
]
CONSTELLATION_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:"
    + "|".join(re.escape(name) for name in sorted(KNOWN_CONSTELLATIONS, key=len, reverse=True))
    + r")(?![A-Za-z])"
)

try:
    # Imported lazily so the top-level module remains usable in tests
    # that don't need regime arithmetic.
    from scripts.regime_simulator import REGIMES, regimes_for_chapter
except Exception:  # pragma: no cover - defensive
    REGIMES = {1: {"words_per_100_cp": 2000, "cp_per_roll": 100},
               2: {"words_per_100_cp": 2000, "cp_per_roll": 200},
               3: {"words_per_100_cp": 3000, "cp_per_roll": 200}}
    regimes_for_chapter = None  # type: ignore[assignment]


# ---------- prose widget ---------------------------------------------------


class PassageView(BasePassageView):
    """Forge Curator's prose widget.

    Wraps the shared :class:`scripts.forge_curator.passage_view.PassageView` so the App can
    intercept the ``]`` / ``[`` chord prefixes (used by ``]r``, ``][``,
    etc.) before the base widget's vim-style on_key handler eats
    them.

    The interception is purely cooperative: the widget exposes a
    ``chord_pending`` flag on the App, and ONLY when that flag is set
    does this override consume the next keypress. Plain motions like
    ``j`` after ``gg`` therefore pass through unmolested.
    """

    def on_key(self, event: events.Key) -> None:  # type: ignore[override]
        ch = event.character
        app = self.app

        # If a vim text-object scope is pending (a/i armed by base view in
        # visual mode), or a vim find-char operator is pending, defer to
        # the base immediately so the next key completes that operation.
        if getattr(self, "_pending_text_object", None) in ("a", "i"):
            super().on_key(event)
            return
        if getattr(self, "_pending_op", None) in ("f", "F", "t", "T"):
            super().on_key(event)
            return

        # 0) Completing a pending <space>-leader chord — single key after.
        if getattr(app, "_pending_space_chord", False):
            app._pending_space_chord = False
            handler = getattr(app, "_handle_space_chord", None)
            if handler is not None:
                handler(ch)
                event.prevent_default()
                event.stop()
                return

        # 1) Are we completing a pending bracket chord?
        pending = getattr(app, "_pending_chord", None)
        if pending in ("[", "]"):
            handler = getattr(app, "_handle_chord_completion", None)
            if handler is not None:
                handler(pending, ch)
                event.prevent_default()
                event.stop()
                return

        # 2) Start a chord on `[` or `]`.
        if ch in ("[", "]"):
            start = getattr(app, "_handle_bracket_chord_start", None)
            if start is not None:
                start(ch)
                event.prevent_default()
                event.stop()
                return

        # 3) `*` — search for word under cursor as the dedicated star regex.
        if ch == "*":
            handler = getattr(app, "_handle_star_search", None)
            if handler is not None:
                handler()
                event.prevent_default()
                event.stop()
                return

        # 4) `z` / `Z` — next / prev match in the dedicated star regex.
        if ch in ("z", "Z"):
            handler = getattr(app, "_handle_star_regex_search", None)
            if handler is not None:
                handler(forward=(ch == "z"))
                event.prevent_default()
                event.stop()
                return

        # 5) `x` / `X` — next / prev quote-start article.
        if ch in ("x", "X"):
            handler = getattr(app, "_handle_article_motion", None)
            if handler is not None:
                handler(forward=(ch == "x"))
                event.prevent_default()
                event.stop()
                return

        # 6) `c` — jump to the end of the next exact constellation name.
        if ch == "c":
            handler = getattr(app, "_handle_constellation_name_motion", None)
            if handler is not None:
                handler()
                event.prevent_default()
                event.stop()
                return

        # 7) In visual mode, `n` extends to the end of the next
        # connection/constellation word used as a quote boundary helper.
        if ch == "n" and (self.visual_mode or self.visual_line_mode):
            handler = getattr(app, "_handle_connection_word_motion", None)
            if handler is not None:
                handler()
                event.prevent_default()
                event.stop()
                return

        # 8) `n` / `N` — next / prev narrative evidence candidate.
        if ch in ("n", "N"):
            handler = getattr(app, "_handle_n_search", None)
            if handler is not None:
                handler(forward=(ch == "n"))
                event.prevent_default()
                event.stop()
                return

        # 9) Visual selection toggles are handled here so Forge-specific
        # key interception does not depend on Textual's binding phase.
        if ch == "v":
            self.action_toggle_visual()
            event.prevent_default()
            event.stop()
            return
        if ch == "V":
            self.action_toggle_visual_line()
            event.prevent_default()
            event.stop()
            return

        # 10) Space alone arms the action leader chord (overrides the base
        #    PassageView's space=toggle_visual binding for forge_curator).
        if ch == " ":
            app._pending_space_chord = True
            event.prevent_default()
            event.stop()
            return

        # Everything else flows to the base class as normal.
        super().on_key(event)

    # Override _maybe_extend / _set_cursor so the App can listen for
    # cursor moves and update stats + scroll.
    def _maybe_extend(self, new_cursor: int) -> None:  # type: ignore[override]
        super()._maybe_extend(new_cursor)
        self._notify_cursor()

    def _set_cursor(self, new_cursor: int) -> None:  # type: ignore[override]
        super()._set_cursor(new_cursor)
        self._notify_cursor()

    def _notify_cursor(self) -> None:
        notify = getattr(self.app, "_on_cursor_moved", None)
        if notify is not None:
            notify()

    def _sync_app_cursor(self) -> None:
        state = getattr(self.app, "state", None)
        cs = getattr(state, "chapter", None)
        if cs is not None:
            cs.cursor_char = self.cursor

    def on_mouse_down(self, event: events.MouseDown) -> None:  # type: ignore[override]
        super().on_mouse_down(event)
        self._sync_app_cursor()

    def on_mouse_move(self, event: events.MouseMove) -> None:  # type: ignore[override]
        super().on_mouse_move(event)
        self._sync_app_cursor()

    def on_mouse_up(self, event: events.MouseUp) -> None:  # type: ignore[override]
        super().on_mouse_up(event)
        self._sync_app_cursor()
        self._notify_cursor()


# ---------- gutter widget ---------------------------------------------------


# Glyph colors used by gutter Rich styles and prose highlights.
GLYPH_COLORS: dict[str, str] = {
    "═": "grey70",
    "R": "red",
    "H": "green",
    "M": "dark_orange",
    "A": "blue",
    "Q": "medium_purple1",
    "N": "yellow",
    ".": "orange1",
    "*": "white",
}
GLYPH_CSS_COLORS: dict[str, str] = {**GLYPH_COLORS}
GLYPH_STYLES: dict[str, str] = {
    glyph: f"bold {color}" for glyph, color in GLYPH_COLORS.items()
}

ROLL_HIGHLIGHT_STYLE = GLYPH_STYLES["R"]
QUOTE_HIGHLIGHT_STYLE = GLYPH_STYLES["Q"]
REGEX_HIGHLIGHT_STYLES = (
    GLYPH_STYLES["*"],
)
FORGE_KEYWORD_HIGHLIGHT_STYLE = GLYPH_STYLES["."]
FORGE_KEYWORD_PATTERN = re.compile(r"\b(?:Forge|[cC]onstellation|[mM]otes?)\b")
CONSTELLATION_NAME_HIGHLIGHT_STYLE = "bold cyan"

ROLL_EVIDENCE_GUTTER_GLYPH = "Q"

LEGEND = [
    ("═", "section break / header", GLYPH_STYLES["═"]),
    ("R", "predicted roll", GLYPH_STYLES["R"]),
    ("H", "hit (curated/derived)", GLYPH_STYLES["H"]),
    ("M", "miss (curated/derived)", GLYPH_STYLES["M"]),
    ("A", "ineligible passage", GLYPH_STYLES["A"]),
    (
        ROLL_EVIDENCE_GUTTER_GLYPH,
        "saved roll evidence",
        GLYPH_STYLES[ROLL_EVIDENCE_GUTTER_GLYPH],
    ),
    ("N", "narrative evidence candidate", GLYPH_STYLES["N"]),
    (".", "Forge/constellation/mote keyword", GLYPH_STYLES["."]),
    ("*", "regex *", GLYPH_STYLES["*"]),
]

ROLL_EVIDENCE_MARKERS = [
    ("Q", "curated quote"),
    ("T", "text evidence"),
    ("S", "spreadsheet/log"),
    ("I", "inferred"),
]


@dataclass(frozen=True)
class TerminalCompatibility:
    ok: bool
    reasons: list[str]


@dataclass(frozen=True)
class CurationDeleteCandidate:
    label: str
    item: dict


def check_terminal_compatibility(
    *,
    stream=None,
    env: dict[str, str] | None = None,
    color_system: str | None = None,
) -> TerminalCompatibility:
    """Return whether the current terminal can render Forge Curator safely."""
    stream = stream if stream is not None else sys.stdout
    env = env if env is not None else os.environ
    reasons: list[str] = []
    try:
        is_tty = bool(stream.isatty())
    except Exception:
        is_tty = False
    if not is_tty:
        reasons.append("Forge Curator requires an interactive terminal.")
    if env.get("NO_COLOR"):
        reasons.append("NO_COLOR is set, so TUI highlight colors are disabled.")

    term = env.get("TERM", "")
    detected_color_system = color_system
    if detected_color_system is None:
        try:
            detected_color_system = Console(file=stream).color_system
        except Exception:
            detected_color_system = None
    has_256_color = detected_color_system in {"256", "truecolor"} or "256color" in term
    if not has_256_color:
        reasons.append(
            "Forge Curator requires a 256-color terminal "
            "(for example TERM=xterm-256color)."
        )
    return TerminalCompatibility(ok=not reasons, reasons=reasons)


def _warn_terminal_compatibility(result: TerminalCompatibility) -> None:
    print("Forge Curator terminal compatibility check failed:", file=sys.stderr)
    for reason in result.reasons:
        print(f"  - {reason}", file=sys.stderr)
    print(
        "Use a terminal with 256-color support and unset NO_COLOR before running the TUI.",
        file=sys.stderr,
    )

# Lower rank values render first. A row can show up to five indicators
# followed by a blank spacer column.
_GLYPH_PRIORITY = {
    "H": 1,
    "M": 2,
    "R": 3,
    "═": 4,
    "A": 5,
    ROLL_EVIDENCE_GUTTER_GLYPH: 6,
    "N": 7,
    "*": 8,
    ".": 99,
}


class GutterMark(NamedTuple):
    proportion: float
    glyph: str
    word_idx: int | None = None


class GutterPanel(Static):
    """Minimap-style chapter indicator strip.

    Each renderable row maps to a fixed *proportion* of the chapter's
    word range, not to a visual line of the prose. So a 60-row gutter
    over a 6000-word chapter has each row representing 100 words of
    chapter progress regardless of scroll position. Indicators are placed
    at their proportional row; multiple items targeting the same row render
    in priority order across the two gutter columns.

    The cursor mark moves at chapter scale, not line scale — small
    motions inside one minimap row don't shift the cursor indicator.
    """

    DEFAULT_CSS = """
    GutterPanel {
        width: 6;
        min-width: 6;
        background: $panel;
        color: $text;
    }
    """

    _CURSOR_ROW_STYLE = "on color(236)"

    def __init__(self, **kw):
        super().__init__("", **kw)
        self._row_targets: list[list[int | None]] = []

    def render_minimap(
        self,
        items: list[GutterMark | tuple[float, str] | tuple[float, str, int]],
        cursor_proportion: float,
        height: int,
    ) -> None:
        """Render the minimap.

        ``items`` is a list of ``(proportion_in_[0,1], glyph)`` tuples.
        ``cursor_proportion`` is in [0, 1]. ``height`` is the row count
        to render (caller computes from the panel's actual size).
        """
        height = max(1, int(height))
        rows: list[list[tuple[str, int | None]]] = [[] for _ in range(height)]

        def row_for(prop: float) -> int:
            return max(0, min(height - 1, int(round(prop * (height - 1)))))

        for item in items:
            prop = float(item[0])
            glyph = str(item[1])
            word_idx = int(item[2]) if len(item) > 2 and item[2] is not None else None
            r = row_for(prop)
            if glyph not in _GLYPH_PRIORITY or any(existing == glyph for existing, _ in rows[r]):
                continue
            rows[r].append((glyph, word_idx))
            rows[r].sort(key=lambda item: _GLYPH_PRIORITY[item[0]])
            del rows[r][5:]
        self._row_targets = [[word_idx for _glyph, word_idx in row] for row in rows]

        cursor_row = row_for(max(0.0, min(1.0, cursor_proportion)))

        out = Text()
        for i, marks in enumerate(rows):
            on_cursor = (i == cursor_row)
            def append_cell(glyph: str, *, cursor_mark: bool = False) -> None:
                style = GLYPH_STYLES.get(glyph, "") if glyph else ""
                if on_cursor:
                    style = (style + " " + self._CURSOR_ROW_STYLE).strip()
                out.append(
                    glyph or ("▎" if cursor_mark and on_cursor else " "),
                    style=style,
                )

            for col in range(5):
                glyph = marks[col][0] if col < len(marks) else ""
                append_cell(
                    glyph,
                    cursor_mark=(col == 0),
                )
            out.append(" ", style=self._CURSOR_ROW_STYLE if on_cursor else "")
            if i < height - 1:
                out.append("\n")
        self.update(out)

    def on_click(self, event: events.Click) -> None:
        row = int(event.y)
        col = int(event.x)
        if row < 0 or row >= len(self._row_targets) or col < 0 or col >= 5:
            return
        targets = self._row_targets[row]
        if col >= len(targets) or targets[col] is None:
            return
        jump = getattr(self.app, "_jump_to_word", None)
        if jump is not None:
            jump(int(targets[col]))
            event.stop()


# ---------- stats panel -----------------------------------------------------

STATS_SCROLL_WIDTH = 48
STATS_PANEL_WIDTH = STATS_SCROLL_WIDTH - 1
STATS_PANEL_PADDING_X = 1
STATS_CONTENT_WIDTH = STATS_PANEL_WIDTH - (STATS_PANEL_PADDING_X * 2)


class StatsPanel(Static):
    DEFAULT_CSS = f"""
    StatsPanel {{
        width: {STATS_PANEL_WIDTH};
        min-width: {STATS_PANEL_WIDTH};
        max-width: {STATS_PANEL_WIDTH};
        background: $panel;
        padding: 1 {STATS_PANEL_PADDING_X};
        height: auto;
    }}
    """

    def on_click(self, event: events.Click) -> None:
        targets = getattr(self, "_roll_line_targets", {})
        target = targets.get(int(getattr(event, "y", -1)))
        if target is not None:
            app = getattr(self, "_render_app", None)
            if app is not None:
                app._select_roll_target(target)
                self.render_stats(app.state, app)
                event.stop()

    def render_stats(self, state: ForgeCuratorState, app: "ForgeCuratorApp") -> None:
        self._render_app = app
        cs = state.chapter
        if cs is None:
            self.update("(no chapter loaded)")
            return

        word_idx = cs.cursor_word_index
        sec_idx = cs.section_index_at(word_idx)
        cn = cs.meta.chapter_num
        chapter_ordinal = app._chapter_ordinal(cn)
        total_chapters = len(app.data.chapter_order)
        section_total = max(1, len(cs.meta.sections or []))
        section_ordinal = max(1, min(section_total, sec_idx + 1))

        content_word_idx = app._content_word_offset(cs, word_idx)
        chapter_content_total = app._chapter_content_total(cn, cs)
        story_content_cursor = app._chapter_content_start(cn) + content_word_idx
        story_content_total = app._story_content_total()

        cp_word_idx = app._cp_earning_word_offset(word_idx)
        chapter_cp_total = app._chapter_cp_total(cn, cs)
        story_cp_cursor = app._chapter_cp_start(cn) + cp_word_idx
        story_cp_total = app._story_cp_total()
        (
            since_last_predicted_roll,
            until_next_predicted_roll,
        ) = app._predicted_roll_distance_stats(story_cp_cursor)
        (
            since_last_curated_roll,
            until_next_curated_roll,
        ) = app._curated_roll_distance_stats(story_cp_cursor)
        (
            since_last_curated_evidence,
            until_next_curated_evidence,
        ) = app._curated_evidence_distance_stats(story_cp_cursor)

        eligibility = app._eligibility_at_cursor(cs, word_idx, sec_idx)
        section_status = (
            "CP eligible" if eligibility["section_eligible"] else "CP ineligible"
        )
        text_status = "CP eligible" if eligibility["text_eligible"] else "CP ineligible"

        cp_stats = app._cp_stats_at_cursor(cs, cp_word_idx)
        model_status = app._model_validation_summary(cs)
        curation_status = app._curation_status_line()
        title_block = "\n".join(
            _wrap_title_for_stats(cs.meta.full_title, STATS_CONTENT_WIDTH)
        )

        unified = app._unified_rolls(cs)
        chapter_rolls = app._roll_slot_rows(cs, unified)
        deferred_rolls = [
            roll for roll in unified
            if roll.get("display_kind") in {"deferred_in", "source_deferred"}
        ]
        deferred_rolls.extend(app._deferred_predicted_slot_rolls(cs, unified))
        selected_or_current = app._selected_or_default_roll_target()

        self._roll_line_targets: dict[int, dict] = {}
        pre_roll_body = (
            f"[bold]Chapter[/bold]\n"
            f"{title_block}\n"
            f"  chapter {_fmt_int(chapter_ordinal)} / {_fmt_int(total_chapters)}; "
            f"section {_fmt_int(section_ordinal)} / {_fmt_int(section_total)}\n"
            f"  Model: {model_status}\n\n"
            f"{curation_status}"
            f"  Section: {section_status}\n"
            f"  Text: {text_status} - {eligibility['reason']}\n\n"
            f"[bold]Words[/bold]\n"
            f"  Total content:\n"
            f"    story {_fmt_int(story_content_cursor)} / {_fmt_int(story_content_total)}\n"
            f"    chapter {_fmt_int(content_word_idx)} / {_fmt_int(chapter_content_total)}\n"
            f"  CP eligible:\n"
            f"    story {_fmt_int(story_cp_cursor)} / {_fmt_int(story_cp_total)}\n"
            f"    chapter {_fmt_int(cp_word_idx)} / {_fmt_int(chapter_cp_total)}\n"
            f"  Since last predicted roll: {_fmt_int(since_last_predicted_roll)}\n"
            f"  Since last curated roll: {_fmt_int(since_last_curated_roll)}\n"
            f"  Since last curated evidence: {_fmt_int(since_last_curated_evidence)}\n"
            f"  Until next predicted roll: {_fmt_int(until_next_predicted_roll)}\n"
            f"  Until next curated roll: {_fmt_int(until_next_curated_roll)}\n"
            f"  Until next curated evidence: {_fmt_int(until_next_curated_evidence)}\n\n"
            f"[bold]CP at cursor[/bold]\n"
            f"  Available: {_fmt_int(cp_stats['available'])}\n"
            f"  Gained:\n"
            f"    total {_fmt_int(cp_stats['gained_total'])}\n"
            f"    chapter {_fmt_int(cp_stats['gained_chapter'])}\n"
            f"  Spent:\n"
            f"    total {_fmt_int(cp_stats['spent_total'])}\n"
            f"    chapter {_fmt_int(cp_stats['spent_chapter'])}\n"
        )
        line_cursor = len(pre_roll_body.splitlines())

        def _register_block_line(line: str, target: dict | None = None) -> str:
            nonlocal line_cursor
            if target is not None:
                self._roll_line_targets[line_cursor] = target
            line_cursor += max(1, len(line.splitlines()))
            return line

        deferred_block = ""
        if deferred_rolls:
            line_cursor += 2
            lines = []
            for roll in deferred_rolls:
                marker = "▸" if app._same_roll_target(roll, selected_or_current) else " "
                lines.append(_register_block_line(
                    app._format_roll_stat_line(roll, marker), roll
                ))
            deferred_block = "\n\n[bold]Deferred rolls[/bold]\n" + "\n".join(lines)

        line_cursor += 2
        roll_lines: list[str] = []
        if not chapter_rolls:
            roll_lines.append(_register_block_line("  (no same-chapter rolls)"))
        else:
            for roll in chapter_rolls:
                marker = "▸" if app._same_roll_target(roll, selected_or_current) else " "
                line = app._format_roll_stat_line(roll, marker)
                if roll["word_position"] > cp_word_idx:
                    line = f"[dim]{line}[/]"
                roll_lines.append(_register_block_line(line, roll))
        rolls_block = "\n".join(roll_lines)

        evidence_block = app._evidence_block(cs)
        perks_block = app._perks_this_chapter_block(cs)

        body = (
            pre_roll_body +
            f"{deferred_block}"
            f"\n\n[bold]Rolls[/bold] [dim]({app._rolls_header_count(cs)})[/]\n"
            f"{rolls_block}\n\n"
            f"[bold]Evidence[/bold]\n{evidence_block}\n\n"
            f"[bold]Perks this chapter[/bold]\n{perks_block}\n"
        )
        self.update(body)


def _fmt_int(value: int | None) -> str:
    return "n/a" if value is None else f"{int(value):,}"


def _perk_display_label(perk: dict | None) -> str:
    """Render ``{name, instance, ...}`` for the curator's eye.

    ``name`` is the canonical directory name; ``instance`` is the
    curator-typed flavor string preserved from the raw log. We show
    both when they differ so the curator still sees what they wrote.
    """
    if not perk:
        return ""
    name = perk.get("name") or perk.get("perk_name") or ""
    instance = perk.get("instance")
    if not name:
        return str(instance or "")
    return f"{name} ({instance})" if instance else name


def _rolled_perk_display(roll: dict) -> str:
    name = roll.get("rolled_perk_name")
    instance = roll.get("rolled_perk_instance")
    if not name:
        return ""
    return f"{name} ({instance})" if instance else name


def _fmt_signed_int(value: int) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(int(value)):,}"


def _wrap_title_for_stats(title: str, content_width: int) -> list[str]:
    """Wrap chapter titles at structural hyphen delimiters when needed."""
    indent = "  "
    continuation = "    - "
    parts = title.split(" - ")
    lines = [f"{indent}{parts[0]}"]
    for part in parts[1:]:
        joined = f"{lines[-1]} - {part}"
        if len(joined) <= content_width:
            lines[-1] = joined
        else:
            lines.append(f"{continuation}{part}")
    return lines


def _word_index_for_char_offset(
    word_offsets: list[tuple[int, int]], char: int
) -> int | None:
    for index, (_start, end) in enumerate(word_offsets):
        if char < end:
            return index
    return len(word_offsets) - 1 if word_offsets else None



def _merge_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent (start, end) ranges. Input must be sorted."""
    out: list[tuple[int, int]] = []
    for s, e in ranges:
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _range_overlap_len(
    ranges: list[tuple[int, int]], start: int, end: int
) -> int:
    return sum(max(0, min(we, end) - max(ws, start)) for ws, we in ranges)


def _range_prefix_len(ranges: list[tuple[int, int]], upper: int) -> int:
    return _range_overlap_len(ranges, 0, max(0, upper))


# NOTE: Free functions ``_cp_word_to_raw_word`` and
# ``_raw_word_to_cp_word`` were removed in favour of canonical methods
# ``ForgeCuratorApp._cp_earning_word_offset`` (raw→cp) and
# ``ForgeCuratorApp._raw_word_for_cp_offset`` (cp→raw). The free
# functions ignored passage-level eligibility spans and would land
# ``]r`` and similar jumps a few words off from the actual
# threshold-crossing.


# ---------- actions panel ---------------------------------------------------


class ActionsPanel(Static):
    DEFAULT_CSS = """
    ActionsPanel {
        width: 32;
        min-width: 32;
        max-width: 38;
        background: $panel;
        padding: 1 1;
    }
    """

    def render_catalog(self) -> None:
        body = (
            "[bold]Actions[/bold] [dim](auto-save)[/dim]\n\n"
            "[bold]Chapter[/bold]\n"
            "  ⎵e  Toggle section eligibility\n"
            "  ⎵E  Selected passage eligibility\n\n"
            "[bold]Selection-based[/bold]\n"
            "  v / V    select char / line\n"
            "  ⎵q       quote = selection\n"
            "  ⎵Q       quote = selection, multiple rolls\n\n"
            "[bold]Quote metadata[/bold]\n"
            "  ⎵M       Move saved quote to another roll\n\n"
            "[bold]Roll metadata[/bold]\n"
            "  ⎵_  Source-only roll anchor at cursor\n"
            "  ⎵r  Resolve model discrepancy\n"
            "  ⎵R  Rebuild derived data\n"
            "  ⎵s  Predicted slot = skipped\n"
            "  ⎵S  Assign source roll to selected slot\n"
            "  ⎵h  Last roll = hit\n"
            "  ⎵m  Last roll = miss\n"
            "  ⎵d  Toggle evidence deferral to later chapter\n"
            "  ⎵v  Roll display position\n"
            "  ⎵c  Set constellation\n"
            "  ⎵p  Set perks\n\n"
            "[bold]Annotation cleanup[/bold]\n"
            "  ⎵D  Delete curation data for chapter\n\n"
            "[bold]Navigation[/bold]\n"
            "  ]] [[  next/prev chapter edge\n"
            "  ][ []  next/prev section\n"
            "  ]r [r  next/prev predicted roll\n"
            "  ]R [R  next/prev curated quote\n"
            "  n N    next/prev narrative evidence candidate\n"
            "  z Z    next/prev regex * match\n"
            "  x X    next/prev a/the\n"
            "  c      next constellation name end\n"
            "  *      seed/select regex *\n"
            "  /      focus regex *\n\n"
            "  u  undo last action\n"
            "  ?  help / legend\n"
            "  q  quit\n"
        )
        self.update(body)


# ---------- regex bar -------------------------------------------------------


class RegexBar(Horizontal):
    DEFAULT_CSS = f"""
    RegexBar {{
        height: 1;
        background: $panel;
        padding: 0;
    }}
    RegexBar > Input {{
        height: 1;
        width: 1fr;
        margin: 0 1;
    }}
    RegexBar > Input.active {{
        text-style: bold underline;
    }}
    RegexBar > Input.regex-slot-4 {{
        color: {GLYPH_CSS_COLORS["*"]};
        text-style: bold;
    }}
    RegexBar Static.label {{
        height: 1;
        width: auto;
        margin: 0 1;
    }}
    RegexBar Static.label.active {{
        text-style: bold underline;
    }}
    RegexBar Static.label.regex-slot-4 {{
        color: {GLYPH_CSS_COLORS["*"]};
        text-style: bold;
    }}
    """

    def compose(self) -> ComposeResult:
        yield Static("regex *:", id="regex_label_4", classes="label regex-slot-4")
        yield Input(
            id="regex_4", placeholder="(none)", compact=True, classes="regex-slot-4"
        )


# ---------- help overlay ----------------------------------------------------


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Container {
        width: 80%;
        height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    HelpScreen Static.body {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "close"),
        Binding("question_mark", "dismiss", "close"),
        Binding("q", "dismiss", "close"),
    ]

    def compose(self) -> ComposeResult:
        # Build the help body using rich Text so we don't have to escape
        # square brackets for markup. This avoids the ``\]r`` rendering bug.
        body = Text()
        body.append("Gutter legend\n", style="bold")
        for glyph, desc, style in LEGEND:
            body.append("  ")
            body.append(glyph, style=style)
            body.append(f"  {desc}\n")
        body.append("\nRoll evidence markers\n", style="bold")
        for glyph, desc in ROLL_EVIDENCE_MARKERS:
            body.append(f"  {glyph}  {desc}\n")
        body.append("\nVim motions (prose panel)\n", style="bold")
        body.append(
            "  h j k l, arrows  movement\n"
            "  w / b            word forward / back\n"
            "  W / B            WORD forward / back\n"
            "  e / E            end of word / WORD\n"
            "  0 / $            line start / end\n"
            "  g g / G          doc start / end\n"
            "  Ctrl-B / Ctrl-F  page back / forward\n"
            "  f<c> F<c> t<c> T<c>  find char\n"
            "  ; / ,            repeat find / reverse repeat\n"
            "  N motion         repeat motion N times\n"
            "  v / V / Esc      visual char / line / clear\n"
        )
        body.append("\nText objects (after v or V)\n", style="bold")
        body.append(
            "  iw / aw   inner / around word\n"
            "  iW / aW   inner / around WORD\n"
            "  is / as   inner / around sentence\n"
            "  ip / ap   inner / around paragraph\n"
        )
        body.append("\nNavigation\n", style="bold")
        body.append(
            "  ]] [[   next/prev chapter edge\n"
            "  ][ []   next/prev section\n"
            "  ]r [r   next/prev curated hit/miss\n"
            "  ]R [R   next/prev predicted roll\n"
            "  ]q [q   next/prev curated narrator quote\n"
            "  n / N   next/prev narrative evidence candidate\n"
            "  z / Z   next/prev regex * match\n"
            "  x / X   next/prev a/the\n"
            "  c       next constellation name end\n"
            "  *       seed/select regex * with word under cursor\n"
            "  F12 / Ctrl-S  snapshot state to data/manual/.forge_curator_snapshot.json\n"
        )
        body.append("\nRegex bar\n", style="bold")
        body.append(
            "  /     focus regex *\n"
            "  Tab   focus regex *\n"
            "  Enter apply regex\n"
        )
        body.append("\nAction panel keybinds\n", style="bold")
        body.append(
            "  <space>e         toggle section eligibility\n"
            "  <space>E         selected passage eligibility\n"
            "  <space>q         roll quote = current selection\n"
            "  <space>Q         roll quote = current selection, multi-roll\n"
            "  <space>M         move saved quote to another roll\n"
            "  <space>v         roll display position\n"
            "  <space>r         resolve current model discrepancy\n"
            "  <space>R         rebuild derived data\n"
            "  <space>s         predicted slot = skipped\n"
            "  <space>S         assign source roll to selected slot\n"
            "  <space>_         source-only roll anchor at cursor\n"
            "  <space>d         toggle roll evidence deferral to later chapter\n"
            "  <space>D         delete curation data for chapter\n"
            "  <space>h / m     last roll = hit / miss\n"
            "  <space>c / p     constellation / perks pickers\n"
            "  (no insert/delete: roll positions come from simulator)\n"
            "\n"
            "  u                undo the last curation action (one step)\n"
        )
        body.append("\nConstellation picker shortcuts\n", style="bold")
        body.append(
            "  1-9         select #1-9 directly\n"
            "  0 then 0-4  select #10-14 (Resources..Vehicles)\n"
            "  arrows + Enter, or first-letter type-ahead\n"
        )
        body.append("\nq or Esc to close\n", style="bold")
        with Container():
            yield Static(body, classes="body")

    def action_dismiss(self) -> None:  # type: ignore[override]
        self.app.pop_screen()


# ---------- pickers ---------------------------------------------------------


class EligibilitySpanModal(ModalScreen):
    """Collect CP-eligibility metadata for the current selection."""

    DEFAULT_CSS = """
    EligibilitySpanModal {
        align: center middle;
    }
    EligibilitySpanModal > Container {
        width: 76;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    EligibilitySpanModal Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    EligibilitySpanModal Input {
        margin-bottom: 1;
    }
    EligibilitySpanModal Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, on_confirm, selection_words: int, **kw):
        super().__init__(**kw)
        self._on_confirm = on_confirm
        self._selection_words = int(selection_words)

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(
                f"Mark selected passage ({self._selection_words} words)",
                classes="title",
            )
            yield Input(
                placeholder=(
                    "reason_code, e.g. joe_on_screen or joe_not_on_screen"
                ),
                id="eligibility_reason_code",
            )
            yield Input(
                placeholder="optional note",
                id="eligibility_note",
            )
            yield Button(
                "CP eligible",
                id="eligibility_true",
                variant="success",
            )
            yield Button(
                "CP ineligible",
                id="eligibility_false",
                variant="warning",
            )

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id not in {"eligibility_true", "eligibility_false"}:
            return
        counts_for_cp = event.button.id == "eligibility_true"
        try:
            reason = self.query_one("#eligibility_reason_code", Input).value.strip()
            note = self.query_one("#eligibility_note", Input).value.strip()
        except Exception:
            reason = ""
            note = ""
        if not reason:
            reason = "joe_on_screen" if counts_for_cp else "joe_not_on_screen"
        self.app.pop_screen()
        self._on_confirm(counts_for_cp, reason, note or None)

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class ConstellationPicker(ModalScreen):
    """Modal listing the 14 known constellations.

    Keyboard accelerators: digits 1-9 select items 1-9 directly; for
    items 10-14 use ``0`` then 0-4 (so ``10`` = Resources & Durability,
    ``11`` = Size, etc.) or use up/down arrows + Enter, or first-letter
    type-ahead (Textual's OptionList default).
    """

    DEFAULT_CSS = """
    ConstellationPicker {
        align: center middle;
    }
    ConstellationPicker > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConstellationPicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ConstellationPicker OptionList {
        height: auto;
        max-height: 18;
    }
    ConstellationPicker Static.hint {
        height: 1;
        content-align: center middle;
        margin-top: 1;
        color: $text 60%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_focused_perk", "toggle", show=False, priority=True),
        Binding("enter", "confirm_selection", "confirm", show=False, priority=True),
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, on_select, **kw):
        super().__init__(**kw)
        self._on_select = on_select
        self._pending_zero = False

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Pick a constellation (Esc to cancel)", classes="title")
            options = [
                Option(f" {i + 1:>2}. {name}", id=f"c_{i}")
                for i, name in enumerate(KNOWN_CONSTELLATIONS)
            ]
            yield OptionList(*options, id="constellation_list")
            yield Static(
                "1-9 = direct  ·  0 then 0-4 = 10-14  ·  ↑/↓ + Enter  ·  type a letter",
                classes="hint",
            )

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def _select_idx(self, idx: int) -> None:
        if 0 <= idx < len(KNOWN_CONSTELLATIONS):
            name = KNOWN_CONSTELLATIONS[idx]
            self.app.pop_screen()
            self._on_select(name)

    def on_key(self, event: events.Key) -> None:
        ch = event.character
        # Two-key chord for 10-14: pressing '0' arms; the next digit picks.
        if self._pending_zero:
            self._pending_zero = False
            if ch and ch.isdigit():
                idx = 9 + int(ch)  # 0->9 (10th), 1->10, ..., 4->13
                event.prevent_default()
                event.stop()
                self._select_idx(idx)
                return
        if ch == "0":
            self._pending_zero = True
            event.prevent_default()
            event.stop()
            return
        if ch and ch.isdigit():
            idx = int(ch) - 1
            event.prevent_default()
            event.stop()
            self._select_idx(idx)
            return

    @on(OptionList.OptionSelected)
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id or ""
        if not opt_id.startswith("c_"):
            return
        idx = int(opt_id[2:])
        self._select_idx(idx)

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class PerkPicker(ModalScreen):
    """Multi-select picker for perks acquired in the current chapter.

    Renders one button per perk; clicking toggles that perk's selection.
    A confirmation button at the bottom commits the selection.
    """

    DEFAULT_CSS = """
    PerkPicker {
        align: center middle;
    }
    PerkPicker > Container {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    PerkPicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    PerkPicker Button {
        width: 100%;
    }
    PerkPicker .selected {
        background: $accent 50%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_focused_perk", "toggle", show=False, priority=True),
        Binding("enter", "confirm_selection", "confirm", show=False, priority=True),
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, perks: list[dict], on_confirm, **kw):
        super().__init__(**kw)
        self._perks = perks
        self._on_confirm = on_confirm
        self._selected: set[str] = set()

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Select perks (click to toggle, Enter to confirm)", classes="title")
            for p in self._perks:
                name = p.get("name", "?")
                cost = p.get("cost", "")
                free = " (free)" if p.get("free") else ""
                label = f"{name}  {cost}{free}"
                yield Button(label, id=f"p_{abs(hash(name))}", name=name)
            yield Button("Confirm", id="confirm", variant="primary")

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm_selection()
            return
        self._toggle_button(event.button)

    def _toggle_button(self, button: Button) -> None:
        name = button.name
        if not name:
            return
        if name in self._selected:
            self._selected.discard(name)
            button.remove_class("selected")
        else:
            self._selected.add(name)
            button.add_class("selected")

    def action_toggle_focused_perk(self) -> None:
        if isinstance(self.focused, Button) and self.focused.id != "confirm":
            self._toggle_button(self.focused)

    def action_confirm_selection(self) -> None:
        self.app.pop_screen()
        self._on_confirm(sorted(self._selected))

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class SourceRollPicker(ModalScreen):
    """Single-select picker for assigning source spreadsheet evidence."""

    DEFAULT_CSS = """
    SourceRollPicker {
        align: center middle;
    }
    SourceRollPicker > Container {
        width: 84;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    SourceRollPicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    SourceRollPicker Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, rolls: list[dict], on_select, target_label: str, **kw):
        super().__init__(**kw)
        self._rolls = rolls
        self._on_select = on_select
        self._target_label = target_label

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(
                f"Assign source roll to {self._target_label}",
                classes="title",
            )
            for idx, roll in enumerate(self._rolls, start=1):
                roll_number = roll.get("roll_number")
                outcome = roll.get("outcome") or roll.get("source_kind") or "unknown"
                perk = _rolled_perk_display(roll)
                constellation = roll.get("constellation")
                detail = ""
                if perk and constellation:
                    detail = f"  {constellation} - {perk}"
                elif constellation:
                    detail = f"  {constellation}"
                raw = str(roll.get("raw") or "").strip()
                if raw:
                    raw = f"  {raw}"
                if roll.get("source_kind") == "obtained_perk":
                    label = f"Obtained: {outcome}{detail}{raw}"
                else:
                    label = f"Roll {roll_number}: {outcome}{detail}{raw}"
                if len(label) > 76:
                    label = label[:73] + "..."
                yield Button(
                    label,
                    id=f"source_roll_{idx}",
                    name=str(idx),
                )

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        name = event.button.name
        if not name:
            return
        idx = int(name)
        if 1 <= idx <= len(self._rolls):
            self.app.pop_screen()
            self._on_select(self._rolls[idx - 1])

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class SourceAssignmentTargetPicker(ModalScreen):
    """Single-select picker for choosing which roll slot receives a source."""

    DEFAULT_CSS = """
    SourceAssignmentTargetPicker {
        align: center middle;
    }
    SourceAssignmentTargetPicker > Container {
        width: 84;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    SourceAssignmentTargetPicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    SourceAssignmentTargetPicker Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, rolls: list[dict], on_select, **kw):
        super().__init__(**kw)
        self._rolls = rolls
        self._on_select = on_select

    @staticmethod
    def _roll_button_label(roll: dict) -> str:
        target = ForgeCuratorApp._roll_target_message_label(roll)
        roll_number = roll.get("roll_number")
        global_part = f"global #{roll_number}" if roll_number is not None else "global #?"
        outcome = roll.get("outcome") or "open"
        if roll.get("display_kind") == "deferred_in":
            label = f"{target}: deferred ({global_part})  {outcome}"
        else:
            label = f"{target}: {global_part}  {outcome}"
        perk = _rolled_perk_display(roll)
        constellation = roll.get("constellation")
        if perk and constellation:
            label = f"{label}  {constellation} - {perk}"
        elif constellation:
            label = f"{label}  {constellation}"
        if roll.get("source_roll_number") is not None:
            label = f"{label}  source Roll {roll.get('source_roll_number')}"
        if len(label) > 76:
            label = label[:73] + "..."
        return label

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Choose target slot for source roll", classes="title")
            for idx, roll in enumerate(self._rolls, start=1):
                yield Button(
                    self._roll_button_label(roll),
                    id=f"source_target_{idx}",
                    name=str(idx),
                )

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        name = event.button.name
        if not name:
            return
        idx = int(name)
        if 1 <= idx <= len(self._rolls):
            self.app.pop_screen()
            self._on_select(self._rolls[idx - 1])

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class SourceLinkPicker(ModalScreen):
    """Two-list picker for linking a target roll slot to source evidence."""

    DEFAULT_CSS = """
    SourceLinkPicker {
        align: center middle;
    }
    SourceLinkPicker > Container {
        width: 110;
        height: auto;
        max-height: 88%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    SourceLinkPicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    SourceLinkPicker Static.column-title {
        height: 1;
        content-align: center middle;
        text-style: bold;
    }
    SourceLinkPicker .column {
        width: 1fr;
        height: auto;
    }
    SourceLinkPicker OptionList.column-list {
        height: 18;
        border: none;
        padding: 0;
    }
    SourceLinkPicker Button {
        width: 100%;
    }
    SourceLinkPicker .selected {
        background: $accent 50%;
        text-style: bold;
    }
    SourceLinkPicker Static.selection-summary {
        height: auto;
        margin-bottom: 1;
        color: $warning;
    }
    SourceLinkPicker Static.links {
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, targets: list[dict], sources: list[dict], on_confirm, **kw):
        super().__init__(**kw)
        self._targets = targets
        self._sources = sources
        self._on_confirm = on_confirm
        self._target_index: int | None = 1 if targets else None
        self._source_index: int | None = 1 if sources else None

    @staticmethod
    def _target_label(roll: dict, *, selected: bool = False) -> str:
        prefix = "LEFT > " if selected else "       "
        target = ForgeCuratorApp._roll_target_message_label(roll)
        roll_number = roll.get("roll_number")
        outcome = roll.get("outcome") or "open"
        if roll.get("display_kind") == "deferred_in":
            label = f"{prefix}{target}  deferred  global {roll_number or '?'}  {outcome}"
        else:
            label = f"{prefix}{target}  global {roll_number or '?'}  {outcome}"
        perk = _rolled_perk_display(roll)
        constellation = roll.get("constellation")
        if perk and constellation:
            label = f"{label}  {constellation} - {perk}"
        elif constellation:
            label = f"{label}  {constellation}"
        if roll.get("source_roll_number") is not None:
            label = f"{label}  source Roll {roll.get('source_roll_number')}"
        return label[:73] + "..." if len(label) > 76 else label

    @staticmethod
    def _source_label(roll: dict, *, selected: bool = False) -> str:
        prefix = "RIGHT > " if selected else "        "
        roll_number = roll.get("roll_number")
        outcome = roll.get("outcome") or roll.get("source_kind") or "unknown"
        perk = _rolled_perk_display(roll)
        constellation = roll.get("constellation")
        detail = ""
        if perk and constellation:
            detail = f"  {constellation} - {perk}"
        elif constellation:
            detail = f"  {constellation}"
        deferred_from = roll.get("source_deferred_from_chapter")
        deferred = f"deferred from ch {deferred_from}  " if deferred_from else ""
        if roll.get("source_kind") == "obtained_perk":
            label = f"{prefix}{deferred}Obtained: {outcome}{detail}"
        else:
            label = f"{prefix}{deferred}Roll {roll_number}: {outcome}{detail}"
        return label[:73] + "..." if len(label) > 76 else label

    def _existing_links_text(self) -> str:
        by_roll = {
            int(source["roll_number"]): source
            for source in self._sources
            if source.get("roll_number") is not None
        }
        lines: list[str] = []
        for target in self._targets:
            source_roll_number = target.get("source_roll_number")
            if source_roll_number is None:
                continue
            try:
                source_roll_number = int(source_roll_number)
            except (TypeError, ValueError):
                continue
            if source_roll_number not in by_roll:
                continue
            lines.append(
                f"{ForgeCuratorApp._roll_target_message_label(target)} "
                f"──────── Roll {source_roll_number}"
            )
        return "\n".join(lines) if lines else "Existing links: none in this view."

    def _selection_summary(self) -> str:
        target = (
            ForgeCuratorApp._roll_target_message_label(
                self._targets[self._target_index - 1]
            )
            if self._target_index is not None
            and 1 <= self._target_index <= len(self._targets)
            else "none"
        )
        source = (
            f"Roll {self._sources[self._source_index - 1].get('roll_number')}"
            if self._source_index is not None
            and 1 <= self._source_index <= len(self._sources)
            else "none"
        )
        pending = (
            f"{target} ──────── {source}"
            if target != "none" and source != "none"
            else "(choose one target and one source)"
        )
        return (
            f"Selected target: {target}    Selected source: {source}\n"
            f"Pending link: {pending}"
        )

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Link target slot to source roll", classes="title")
            yield Static(self._existing_links_text(), classes="links")
            yield Static(
                self._selection_summary(),
                id="source_link_summary",
                classes="selection-summary",
            )
            with Horizontal():
                with Vertical(classes="column"):
                    yield Static("Target slots", classes="column-title")
                    target_options = OptionList(
                        *[
                            Option(
                                self._target_label(
                                    target,
                                    selected=idx == self._target_index,
                                ),
                                id=f"target_{idx}",
                            )
                            for idx, target in enumerate(self._targets, start=1)
                        ],
                        id="source_link_targets",
                        classes="column-list",
                        compact=True,
                    )
                    target_options.highlighted = (
                        self._target_index - 1
                        if self._target_index is not None else None
                    )
                    yield target_options
                with Vertical(classes="column"):
                    yield Static("Source rolls", classes="column-title")
                    source_options = OptionList(
                        *[
                            Option(
                                self._source_label(
                                    source,
                                    selected=idx == self._source_index,
                                ),
                                id=f"source_{idx}",
                            )
                            for idx, source in enumerate(self._sources, start=1)
                        ],
                        id="source_link_sources",
                        classes="column-list",
                        compact=True,
                    )
                    source_options.highlighted = (
                        self._source_index - 1
                        if self._source_index is not None else None
                    )
                    yield source_options
            yield Button("Confirm", id="confirm", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#source_link_targets", OptionList).focus()

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm_selection()

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "source_link_targets":
            self._target_index = int(event.option_index) + 1
            self._refresh_option_prompts()
        elif event.option_list.id == "source_link_sources":
            self._source_index = int(event.option_index) + 1
            self._refresh_option_prompts()

    def _refresh_option_prompts(self) -> None:
        try:
            targets = self.query_one("#source_link_targets", OptionList)
            for idx, target in enumerate(self._targets, start=1):
                targets.replace_option_prompt_at_index(
                    idx - 1,
                    self._target_label(
                        target,
                        selected=idx == self._target_index,
                    ),
                )
            sources = self.query_one("#source_link_sources", OptionList)
            for idx, source in enumerate(self._sources, start=1):
                sources.replace_option_prompt_at_index(
                    idx - 1,
                    self._source_label(
                        source,
                        selected=idx == self._source_index,
                    ),
                )
        except Exception:
            pass
        try:
            self.query_one("#source_link_summary", Static).update(
                self._selection_summary()
            )
        except Exception:
            pass

    def action_confirm_selection(self) -> None:
        if self._target_index is None or self._source_index is None:
            return
        if not (1 <= self._target_index <= len(self._targets)):
            return
        if not (1 <= self._source_index <= len(self._sources)):
            return
        self.app.pop_screen()
        self._on_confirm(
            self._targets[self._target_index - 1],
            self._sources[self._source_index - 1],
        )

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class ChapterCurationDeletePicker(ModalScreen):
    """Multi-select picker for deleting persisted curation records."""

    DEFAULT_CSS = """
    ChapterCurationDeletePicker {
        align: center middle;
    }
    ChapterCurationDeletePicker > Container {
        width: 110;
        height: auto;
        max-height: 88%;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    ChapterCurationDeletePicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ChapterCurationDeletePicker Static.help {
        height: auto;
        color: $warning;
        margin-bottom: 1;
    }
    ChapterCurationDeletePicker OptionList {
        height: 20;
        border: none;
    }
    ChapterCurationDeletePicker Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_focused_item", "toggle", show=False, priority=True),
        Binding("enter", "confirm_selection", "confirm", show=False, priority=True),
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(
        self,
        candidates: list[CurationDeleteCandidate],
        on_confirm,
        **kw,
    ):
        super().__init__(**kw)
        self._candidates = candidates
        self._on_confirm = on_confirm
        self._selected: set[int] = set()

    def _label(self, index: int, candidate: CurationDeleteCandidate) -> str:
        marker = "(x)" if index in self._selected else "( )"
        label = f"{marker} {candidate.label}"
        return label[:104] + "..." if len(label) > 107 else label

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Delete persisted curation data for this chapter", classes="title")
            yield Static(
                "Select only stale curation records. This does not delete derived JSON.",
                classes="help",
            )
            options = OptionList(
                *[
                    Option(self._label(idx, candidate), id=f"delete_{idx}")
                    for idx, candidate in enumerate(self._candidates, start=1)
                ],
                id="chapter_curation_delete_items",
                compact=True,
            )
            options.highlighted = 0 if self._candidates else None
            yield options
            yield Button("Delete selected", id="confirm", variant="error")

    def on_mount(self) -> None:
        self.query_one("#chapter_curation_delete_items", OptionList).focus()

    def _refresh_labels(self) -> None:
        try:
            options = self.query_one("#chapter_curation_delete_items", OptionList)
            for idx, candidate in enumerate(self._candidates, start=1):
                options.replace_option_prompt_at_index(
                    idx - 1,
                    self._label(idx, candidate),
                )
        except Exception:
            pass

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm_selection()

    @on(OptionList.OptionSelected)
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        idx = int(event.option_index) + 1
        if idx in self._selected:
            self._selected.remove(idx)
        else:
            self._selected.add(idx)
        self._refresh_labels()

    def action_toggle_focused_item(self) -> None:
        options = self.query_one("#chapter_curation_delete_items", OptionList)
        highlighted = options.highlighted
        if highlighted is None:
            return
        idx = int(highlighted) + 1
        if idx in self._selected:
            self._selected.remove(idx)
        else:
            self._selected.add(idx)
        self._refresh_labels()

    def action_confirm_selection(self) -> None:
        items = [
            self._candidates[idx - 1].item
            for idx in sorted(self._selected)
            if 1 <= idx <= len(self._candidates)
        ]
        self.app.pop_screen()
        self._on_confirm(items)

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class RollEvidencePicker(ModalScreen):
    """Multi-select roll picker for assigning one quote to several rolls."""

    DEFAULT_CSS = """
    RollEvidencePicker {
        align: center middle;
    }
    RollEvidencePicker > Container {
        width: 96;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 0 1;
    }
    RollEvidencePicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 0;
    }
    RollEvidencePicker Button {
        width: 100%;
        margin: 0;
    }
    RollEvidencePicker .roll-columns {
        width: 100%;
        height: auto;
    }
    RollEvidencePicker .roll-column {
        width: 1fr;
        height: auto;
        padding: 0;
    }
    RollEvidencePicker .selected {
        background: $accent 50%;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_focused_roll", "toggle", show=False, priority=True),
        Binding("enter", "confirm_selection", "confirm", show=False, priority=True),
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, rolls: list[dict], on_confirm, **kw):
        super().__init__(**kw)
        self._rolls = rolls
        self._on_confirm = on_confirm
        self._selected: set[int] = set()
        self._display_position_policy: str | None = None

    def _roll_button_label(self, index: int, roll: dict) -> str:
        marker = "(x)" if index in self._selected else "( )"
        global_num = roll.get("roll_number")
        global_part = f"global #{global_num}" if global_num is not None else "global #?"
        outcome = roll.get("outcome") or "unknown"
        if roll.get("display_kind") == "deferred_in":
            return (
                f"{marker} deferred from ch {roll.get('target_chapter_num')} "
                f"#{roll.get('target_roll_index')} ({global_part})  {outcome}"
            )
        stable_index = ForgeCuratorApp._display_roll_identity(roll)
        return f"{marker} #{stable_index} ({global_part})  {outcome}"

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Save quote to rolls (click to toggle)", classes="title")
            split = (len(self._rolls) + 1) // 2
            with Horizontal(classes="roll-columns"):
                with Container(id="roll_column_left", classes="roll-column"):
                    for idx, r in enumerate(self._rolls[:split], start=1):
                        yield Button(
                            self._roll_button_label(idx, r),
                            id=f"roll_{idx}",
                            name=str(idx),
                        )
                with Container(id="roll_column_right", classes="roll-column"):
                    for idx, r in enumerate(self._rolls[split:], start=split + 1):
                        yield Button(
                            self._roll_button_label(idx, r),
                            id=f"roll_{idx}",
                            name=str(idx),
                        )
            yield Button(self._display_position_label(), id="display_policy")
            yield Button("Confirm", id="confirm", variant="primary")

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.action_confirm_selection()
            return
        if event.button.id == "display_policy":
            self._toggle_display_position_policy(event.button)
            return
        self._toggle_button(event.button)

    def _toggle_button(self, button: Button) -> None:
        name = button.name
        if not name:
            return
        idx = int(name)
        if idx in self._selected:
            self._selected.discard(idx)
            button.remove_class("selected")
        else:
            self._selected.add(idx)
            button.add_class("selected")
        if 1 <= idx <= len(self._rolls):
            button.label = self._roll_button_label(idx, self._rolls[idx - 1])

    def action_toggle_focused_roll(self) -> None:
        if not isinstance(self.focused, Button) or self.focused.id == "confirm":
            return
        if self.focused.id == "display_policy":
            self._toggle_display_position_policy(self.focused)
            return
        self._toggle_button(self.focused)

    def _display_position_label(self) -> str:
        if self._display_position_policy == "mention":
            return "Display marker: quote"
        return "Display marker: predicted"

    def _toggle_display_position_policy(self, button: Button | None = None) -> None:
        self._display_position_policy = (
            "mention" if self._display_position_policy is None else None
        )
        if button is not None:
            button.label = self._display_position_label()

    def action_confirm_selection(self) -> None:
        try:
            self.app.pop_screen()
        except Exception:
            pass
        self._on_confirm(sorted(self._selected), self._display_position_policy)

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class QuoteMoveTargetPicker(ModalScreen):
    """Single-select roll picker for moving an existing saved quote."""

    DEFAULT_CSS = RollEvidencePicker.DEFAULT_CSS.replace(
        "RollEvidencePicker", "QuoteMoveTargetPicker"
    )

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(self, rolls: list[dict], on_select, **kw):
        super().__init__(**kw)
        self._rolls = rolls
        self._on_select = on_select

    def _roll_button_label(self, index: int, roll: dict) -> str:
        global_num = roll.get("roll_number")
        global_part = f"global #{global_num}" if global_num is not None else "global #?"
        outcome = roll.get("outcome") or "unknown"
        if roll.get("display_kind") in {"deferred_in", "source_deferred"}:
            return (
                f"ch {roll.get('target_chapter_num')} "
                f"#{roll.get('target_roll_index')} ({global_part})  {outcome}"
            )
        stable_index = ForgeCuratorApp._display_roll_identity(roll)
        return f"#{stable_index} ({global_part})  {outcome}"

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Move quote to roll", classes="title")
            for idx, roll in enumerate(self._rolls, start=1):
                yield Button(
                    self._roll_button_label(idx, roll),
                    id=f"roll_{idx}",
                    name=str(idx),
                )

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if not event.button.name:
            return
        self._select(int(event.button.name))

    def _select(self, index: int) -> None:
        if not (1 <= int(index) <= len(self._rolls)):
            return
        try:
            self.app.pop_screen()
        except Exception:
            pass
        self._on_select(self._rolls[int(index) - 1])

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class QuoteMoveSourcePicker(ModalScreen):
    """Picker for choosing which overlapping saved quote to move."""

    DEFAULT_CSS = RollEvidencePicker.DEFAULT_CSS.replace(
        "RollEvidencePicker", "QuoteMoveSourcePicker"
    )

    BINDINGS = QuoteMoveTargetPicker.BINDINGS

    def __init__(self, sources: list[dict], on_select, **kw):
        super().__init__(**kw)
        self._sources = sources
        self._on_select = on_select

    def _source_button_label(self, index: int, source: dict) -> str:
        quote = source.get("quote") or {}
        text = str(quote.get("text") or "").replace("\n", " ")
        return (
            f"ch {source.get('target_chapter')} #{source.get('target_index')}  "
            f"{text[:56]}"
        )

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Choose quote to move", classes="title")
            for idx, source in enumerate(self._sources, start=1):
                yield Button(
                    self._source_button_label(idx, source),
                    id=f"quote_source_{idx}",
                    name=str(idx),
                )

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if not event.button.name:
            return
        self._select(int(event.button.name))

    def _select(self, index: int) -> None:
        if not (1 <= int(index) <= len(self._sources)):
            return
        try:
            self.app.pop_screen()
        except Exception:
            pass
        self._on_select(self._sources[int(index) - 1])

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


class RollVisualizationPicker(ModalScreen):
    """Picker for choosing a roll's visualization anchor."""

    DEFAULT_CSS = RollEvidencePicker.DEFAULT_CSS.replace(
        "RollEvidencePicker", "RollVisualizationPicker"
    )

    BINDINGS = [
        Binding("escape", "dismiss_picker", "cancel"),
        Binding("q", "dismiss_picker", "cancel"),
    ]

    def __init__(
        self,
        *,
        roll: dict,
        cursor_chapter_num: str,
        cursor_word_position: int,
        on_select,
        **kw,
    ):
        super().__init__(**kw)
        self._roll = roll
        self._cursor_chapter_num = str(cursor_chapter_num)
        self._cursor_word_position = int(cursor_word_position)
        self._on_select = on_select

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Roll visualization position", classes="title")
            for idx, quote in enumerate(self._roll.get("evidence_quotes") or []):
                label = str(quote.get("text") or "").replace("\n", " ")
                yield Button(f"Quote {idx + 1}: {label[:56]}", id=f"quote_{idx}")
            yield Button("Predicted roll position", id="mechanical")
            yield Button("Current cursor position", id="cursor")

    @on(Button.Pressed)
    def _on_pressed(self, event: Button.Pressed) -> None:
        if event.button.id:
            self._select(event.button.id)

    def _select(self, choice: str) -> None:
        if choice.startswith("quote_"):
            idx = int(choice.split("_", 1)[1])
            quotes = self._roll.get("evidence_quotes") or []
            if not (0 <= idx < len(quotes)):
                return
            quote = quotes[idx]
            payload = {
                "mention_chapter_num": str(
                    quote.get("mention_chapter_num")
                    or self._cursor_chapter_num
                ),
                "mention_word_position": quote.get("mention_word_position"),
                "display_position_policy": "mention",
            }
        elif choice == "mechanical":
            payload = {
                "mention_chapter_num": str(
                    self._roll.get("mention_chapter_num")
                    or self._roll.get("mechanical_chapter_num")
                    or self._cursor_chapter_num
                ),
                "mention_word_position": self._roll.get("mention_word_position"),
                "display_position_policy": "mechanical",
            }
        elif choice == "cursor":
            payload = {
                "mention_chapter_num": self._cursor_chapter_num,
                "mention_word_position": self._cursor_word_position,
                "display_position_policy": "mention",
            }
        else:
            return
        try:
            self.app.pop_screen()
        except Exception:
            pass
        self._on_select(payload)

    def action_dismiss_picker(self) -> None:
        self.app.pop_screen()


# ---------- main TUI app ----------------------------------------------------


class ForgeCuratorApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        height: 1fr;
    }
    #stats_scroll {
        width: 48;
        min-width: 48;
        max-width: 48;
        height: 1fr;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    #stats {
        height: auto;
    }
    #prose_container {
        width: 1fr;
        height: 1fr;
        background: $surface;
    }
    PassageView {
        background: $surface;
        padding: 1 5;
    }
    GutterPanel {
        height: 1fr;
    }
    /* Narrow the scrollbar so it doesn't crowd the gutter visually. */
    #prose_scroll {
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    """

    BINDINGS = [
        Binding("question_mark", "show_help", "help", show=True),
        Binding("q", "quit_app", "quit", show=True),
        Binding("slash", "focus_regex_star", "/regex*"),
        Binding("u", "undo_last", "undo last action"),
        Binding("f12", "snapshot", "snapshot", show=True),
        Binding("ctrl+s", "snapshot", "snapshot", show=False),
    ]

    def __init__(
        self,
        start_chapter: str | None = "1",
        *,
        state_path: Path | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self.start_chapter = str(start_chapter) if start_chapter is not None else None
        self.state_path = state_path or STATE_FILE
        self.data = ForgeCuratorData()
        self.state = ForgeCuratorState(data=self.data)
        # Persistence layer — auto-save target for all curation actions.
        self.persistence = CurationPersistence()
        # Tracker for [/]<motif> chord state.
        self._pending_chord: str | None = None
        # Tracker for <space>X leader chord state.
        self._pending_space_chord: bool = False
        self.active_regex_slot: int = 3
        self._last_curation_error: str | None = None
        self._last_curation_message: str | None = None
        self._selected_roll_target: dict | None = None
    # ----- compose -----

    def compose(self) -> ComposeResult:
        with Horizontal(id="main"):
            with VerticalScroll(id="stats_scroll"):
                yield StatsPanel(id="stats")
            with Container(id="prose_container"):
                with VerticalScroll(id="prose_scroll"):
                    yield PassageView(id="prose")
            yield GutterPanel(id="gutter")
            yield ActionsPanel(id="actions")
        yield RegexBar(id="regex_bar")

    # ----- mount -----

    def on_mount(self) -> None:
        order = self.data.chapter_order
        target = None
        if self.start_chapter in order:
            target = self.start_chapter
        if target is None:
            restored = self._read_last_viewed_chapter()
            if restored in order:
                target = restored
        if target is None:
            target = order[0] if order else None
        if target is None:
            self.exit("No chapters available")
            return
        self._load_chapter(target)
        self.refresh_all_panels()
        prose = self.query_one("#prose", PassageView)
        prose.focus()
        # After layout settles, re-render so the gutter minimap uses the
        # real panel height instead of the zero size at mount time.
        self.call_after_refresh(self.refresh_all_panels)

    def _read_last_viewed_chapter(self) -> str | None:
        try:
            data = json.loads(self.state_path.read_text())
        except Exception:
            return None
        value = data.get("last_chapter")
        return str(value) if value is not None else None

    def _persist_last_viewed_chapter(self, chapter_num: str) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps({"last_chapter": str(chapter_num)}, indent=2) + "\n"
            )
        except Exception:
            pass

    def _load_chapter(self, chapter_num: str):
        cs = self.state.load_chapter(str(chapter_num))
        self._selected_roll_target = None
        self._persist_last_viewed_chapter(cs.meta.chapter_num)
        return cs

    # ----- panel refresh -----

    def refresh_all_panels(self) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        prose_view = self.query_one("#prose", PassageView)
        prose_view.set_text(cs.prose.text, spans=self._compute_prose_spans())
        prose_view.cursor = cs.cursor_char

        stats = self.query_one("#stats", StatsPanel)
        stats.render_stats(self.state, self)

        actions = self.query_one("#actions", ActionsPanel)
        actions.render_catalog()

        gutter = self.query_one("#gutter", GutterPanel)
        gutter_height = max(1, gutter.size.height or 1)
        gutter.render_minimap(
            self._compute_gutter_marks(),
            self._cursor_chapter_proportion(),
            gutter_height,
        )
        self._refresh_regex_bar()

    def _refresh_regex_bar(self) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        self.active_regex_slot = 3
        try:
            inp = self.query_one("#regex_4", Input)
            label = self.query_one("#regex_label_4", Static)
        except Exception:
            return
        if not inp.has_focus:
            inp.value = cs.regex_hits[3].pattern
        inp.set_class(True, "active")
        label.set_class(True, "active")

    def _compute_prose_spans(self) -> list[dict]:
        """Inline highlight spans for the prose view.

        Predicted roll words use the same red as the R gutter indicator.
        Curated narrator-quote rolls retain the layer-A evidence highlight.
        Regex matches use the same distinct colors as their gutter markers.
        """
        cs = self.state.chapter
        if cs is None:
            return []
        wo = cs.prose.word_offsets
        if not wo:
            return []
        spans: list[dict] = []
        for raw in self._predicted_roll_word_indices(cs):
            if 0 <= raw < len(wo):
                cs_, ce_ = wo[raw]
                spans.append({
                    "start": cs_,
                    "end": ce_,
                    "layer": "B",
                    "style": ROLL_HIGHLIGHT_STYLE,
                    "priority": 10,
                })
        for start, end in self._roll_evidence_char_spans(cs):
            spans.append({
                "start": start,
                "end": end,
                "layer": "A",
                "style": QUOTE_HIGHLIGHT_STYLE,
                "priority": 20,
            })
        for start, end in self._forge_keyword_char_spans(cs):
            spans.append({
                "start": start,
                "end": end,
                "style": FORGE_KEYWORD_HIGHLIGHT_STYLE,
                "priority": 25,
            })
        for start, end in self._constellation_name_char_spans(cs):
            spans.append({
                "start": start,
                "end": end,
                "style": CONSTELLATION_NAME_HIGHLIGHT_STYLE,
                "priority": 26,
            })
        for slot, hits in ((3, cs.regex_hits[3]),):
            style = REGEX_HIGHLIGHT_STYLES[0]
            for start, end in hits.char_spans:
                if 0 <= start < end <= len(cs.prose.text):
                    spans.append({
                        "start": start,
                        "end": end,
                        "style": style,
                        "priority": 30 + slot,
                    })
        return spans

    @staticmethod
    def _forge_keyword_char_spans(cs) -> list[tuple[int, int]]:
        return [
            match.span()
            for match in FORGE_KEYWORD_PATTERN.finditer(cs.prose.text)
        ]

    @staticmethod
    def _constellation_name_char_spans(cs) -> list[tuple[int, int]]:
        return [
            match.span()
            for match in CONSTELLATION_NAME_PATTERN.finditer(cs.prose.text)
        ]

    def _forge_keyword_word_indices(self, cs) -> list[int]:
        indices: list[int] = []
        seen: set[int] = set()
        for start, _end in self._forge_keyword_char_spans(cs):
            word_idx = _word_index_for_char_offset(cs.prose.word_offsets, start)
            if word_idx is not None and word_idx not in seen:
                seen.add(word_idx)
                indices.append(word_idx)
        return indices

    def _roll_evidence_char_spans(self, cs) -> list[tuple[int, int]]:
        """Return current-chapter prose spans backed by saved roll evidence.

        The derived roll fact owns whether evidence exists. The TUI only
        maps the saved quote back onto the already-loaded prose for display;
        if the quote is not present in this chapter, it falls back to the
        roll's display slot.
        """
        wo = cs.prose.word_offsets
        if not wo:
            return []
        spans: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for roll in self._roll_evidence_picker_rolls(cs):
            for quote in self._roll_evidence_quotes(roll):
                text = str(quote.get("text") or "")
                if not text:
                    continue
                start = cs.prose.text.find(text)
                if start >= 0:
                    span = (start, start + len(text))
                else:
                    quote_chapter = quote.get("mention_chapter_num")
                    if (
                        quote_chapter is not None
                        and str(quote_chapter) != cs.meta.chapter_num
                    ):
                        continue
                    raw = self._evidence_fallback_word_index(cs, roll)
                    if raw is None or not (0 <= raw < len(wo)):
                        continue
                    span = wo[raw]
                if span not in seen:
                    seen.add(span)
                    spans.append(span)
        return spans

    def _roll_evidence_word_indices(self, cs) -> list[int]:
        indices: list[int] = []
        seen: set[int] = set()
        for start, _end in self._roll_evidence_char_spans(cs):
            word_idx = _word_index_for_char_offset(cs.prose.word_offsets, start)
            if word_idx is not None and word_idx not in seen:
                seen.add(word_idx)
                indices.append(word_idx)
        return indices

    def _predicted_roll_word_indices(self, cs) -> list[int]:
        indices: list[int] = []
        seen: set[int] = set()
        cn = cs.meta.chapter_num
        chapter_cp_start = self._chapter_cp_start(cn)

        def _add(local_cp: int | None) -> None:
            if local_cp is None or local_cp < 0:
                return
            raw = self._roll_marker_word_index_from_cp(cs, local_cp)
            if raw is not None and raw not in seen:
                seen.add(raw)
                indices.append(raw)

        for roll in cs.derived.predicted_rolls:
            if str(roll.get("chapter_num")) != cn:
                continue
            global_cp = roll.get("cp_offset")
            if global_cp is None:
                continue
            _add(int(global_cp) - chapter_cp_start)

        for roll in (cs.derived.chapter_facts or {}).get("rolls", []):
            if str(roll.get("mechanical_chapter_num")) != cn:
                continue
            wp = roll.get("mechanical_word_position")
            if wp is None:
                wp = roll.get("word_position")
            if wp is not None:
                _add(int(wp))
        return indices

    def _roll_marker_word_index_from_cp(self, cs, cp_word_idx: int) -> int | None:
        if not cs.prose.word_offsets:
            return None
        raw = min(
            self._raw_word_for_cp_offset(cp_word_idx),
            len(cs.prose.word_offsets) - 1,
        )
        while raw > 0:
            sec_idx = cs.section_index_at(raw)
            if self._eligibility_at_cursor(cs, raw, sec_idx)["text_eligible"]:
                return raw
            raw -= 1
        return None

    def _curated_roll_word_index(self, cs, roll: dict) -> int | None:
        raw = roll.get("raw_word_position")
        if raw is not None:
            raw_idx = int(raw)
            if self._is_structural_word_index(cs, raw_idx):
                return None
            return raw_idx
        return None

    def _is_structural_word_index(self, cs, word_idx: int) -> bool:
        if not (0 <= int(word_idx) < len(cs.prose.word_offsets)):
            return True
        sec_idx = cs.section_index_at(int(word_idx))
        return not bool(
            self._eligibility_at_cursor(cs, int(word_idx), sec_idx)["text_eligible"]
        )

    def _evidence_fallback_word_index(self, cs, roll: dict) -> int | None:
        raw = self._curated_roll_word_index(cs, roll)
        if raw is not None:
            return raw
        if roll.get("word_position") is None:
            return None
        return self._raw_word_for_cp_offset(int(roll["word_position"]))

    def _evidence_reference_word_index(self, cs, roll: dict) -> int | None:
        if (
            str(roll.get("mechanical_chapter_num")) == cs.meta.chapter_num
            and roll.get("mechanical_word_position") is not None
        ):
            return self._roll_marker_word_index_from_cp(
                cs, int(roll["mechanical_word_position"])
            )
        if (
            str(roll.get("display_chapter_num")) == cs.meta.chapter_num
            and roll.get("display_word_position") is not None
        ):
            return self._roll_marker_word_index_from_cp(
                cs, int(roll["display_word_position"])
            )
        return roll.get("raw_word_position")

    def _cursor_chapter_proportion(self) -> float:
        """Return cursor's position within the chapter as a float in [0, 1]."""
        cs = self.state.chapter
        if cs is None:
            return 0.0
        total = max(1, len(cs.prose.word_offsets))
        wi = cs.cursor_word_index
        return max(0.0, min(1.0, wi / total))

    def _compute_gutter_items(self) -> list[tuple[float, str]]:
        return [
            (mark.proportion, mark.glyph)
            for mark in self._compute_gutter_marks()
        ]

    def _compute_gutter_marks(self) -> list[GutterMark]:
        """Return marks for the chapter minimap.

        Proportions are in [0, 1] over chapter word indices. Multi-word
        spans contribute a single mark at their start; the user asked
        for one indicator per logical mark, not many.
        """
        cs = self.state.chapter
        if cs is None:
            return []
        total = max(1, len(cs.prose.word_offsets))
        items: list[GutterMark] = []

        def _add(word_idx: int, glyph: str) -> None:
            items.append(GutterMark(word_idx / total, glyph, int(word_idx)))

        # Section breaks (single mark each).
        for word_idx in cs.prose.section_break_word_indices:
            if 0 <= word_idx < total:
                _add(word_idx, "═")
        # Auto-detected section headers — one mark at the start of each.
        for ws, _we in (cs.prose.implicit_header_word_ranges or []):
            if 0 <= ws < total:
                _add(ws, "═")
        for section in cs.meta.sections or []:
            for span in section.get("span_overrides") or []:
                if bool(span.get("counts_for_cp")):
                    continue
                reason = str(span.get("reason_code") or "")
                if reason in {"section_header", "chapter_title_header"}:
                    continue
                ws = int(span.get("word_offset_start") or 0)
                if 0 <= ws < total:
                    _add(ws, "A")

        # Predicted rolls — convert chapter-local CP-word to raw via
        # the canonical exclusion-aware inverse.
        for raw_idx in self._predicted_roll_word_indices(cs):
            if 0 <= raw_idx < total:
                _add(raw_idx, "R")

        # Hits / misses come from canonical chapter facts. The TUI only
        # converts the derived CP-word coordinate to a raw prose word for
        # minimap display.
        for r in self._unified_rolls(cs):
            outcome = r.get("outcome")
            if outcome not in ("hit", "miss"):
                continue
            raw_idx = self._curated_roll_word_index(cs, r)
            if raw_idx is not None and 0 <= raw_idx < total:
                _add(raw_idx, "H" if outcome == "hit" else "M")

        # Saved roll evidence quotes get their own persistent mark. When
        # possible, mark the quote's actual prose location; otherwise mark
        # the roll's display slot.
        for raw_idx in self._roll_evidence_word_indices(cs):
            if 0 <= raw_idx < total:
                _add(raw_idx, ROLL_EVIDENCE_GUTTER_GLYPH)

        # Narrative evidence candidates are paragraph-level scorer hits.
        # They intentionally do not create prose highlights; the gutter N
        # mark and n/N navigation are the low-noise review affordances.
        for candidate in cs.evidence_candidates:
            if 0 <= candidate.word_index < total:
                _add(candidate.word_index, "N")

        # User regex * matches.
        for wi in cs.regex_hits[3].word_indices:
            if 0 <= wi < total:
                _add(int(wi), "*")

        # Hard-coded Forge keywords are intentionally lowest priority.
        for wi in self._forge_keyword_word_indices(cs):
            if 0 <= wi < total:
                _add(int(wi), ".")

        return items

    # ----- helpers ---------------------------------------------------------

    def _ineligible_span_ranges(self, cs) -> list[tuple[int, int]]:
        """Passage-level ranges in the current chapter excluded from CP earning."""
        ranges: list[tuple[int, int]] = []
        for section in cs.meta.sections or []:
            for span in section.get("span_overrides") or []:
                if bool(span.get("counts_for_cp")):
                    continue
                try:
                    ranges.append((
                        int(span.get("word_offset_start")),
                        int(span.get("word_offset_end")),
                    ))
                except (TypeError, ValueError):
                    continue
        return _merge_ranges(sorted(ranges))

    def _chapter_ordinal(self, chapter_num: str) -> int:
        try:
            return self.data.chapter_order.index(str(chapter_num)) + 1
        except ValueError:
            return 0

    def _canonical_ineligible_span_ranges(self, cs=None) -> list[tuple[int, int]]:
        """Chapter-local passage-level content exclusions."""
        ranges: list[tuple[int, int]] = []
        if cs is not None:
            ranges.extend(self._ineligible_span_ranges(cs))
        return _merge_ranges(sorted(ranges))

    def _content_word_offset(self, cs, raw_word_idx: int) -> int:
        total = len(cs.prose.word_offsets)
        raw_word_idx = max(0, min(int(raw_word_idx), total))
        excluded = self._canonical_ineligible_span_ranges(cs)
        return max(0, raw_word_idx - _range_prefix_len(excluded, raw_word_idx))

    def _chapter_content_total(self, chapter_num: str, cs=None) -> int:
        meta = self.data.chapter_meta(str(chapter_num))
        total = int(meta.total_word_count or 0)
        excluded = self._canonical_ineligible_span_ranges(cs)
        return max(0, total - _range_overlap_len(excluded, 0, total))

    def _chapter_content_start(self, chapter_num: str) -> int:
        total = 0
        for cn in self.data.chapter_order:
            if cn == str(chapter_num):
                break
            total += self._chapter_content_total(cn)
        return total

    def _story_content_total(self) -> int:
        return sum(self._chapter_content_total(cn) for cn in self.data.chapter_order)

    def _chapter_cp_total(self, chapter_num: str, cs=None) -> int:
        cn = str(chapter_num)
        if cs is not None:
            return self._cp_earning_word_offset(len(cs.prose.word_offsets))
        return int(self.data.chapter_meta(cn).cp_earning_word_count or 0)

    def _chapter_cp_start(self, chapter_num: str) -> int:
        total = 0
        for cn in self.data.chapter_order:
            if cn == str(chapter_num):
                break
            total += self._chapter_cp_total(cn)
        return total

    def _story_cp_total(self) -> int:
        return sum(self._chapter_cp_total(cn) for cn in self.data.chapter_order)

    def _chapter_prev_banked_end(self, chapter_num: str) -> int:
        prev: str | None = None
        for cn in self.data.chapter_order:
            if cn == str(chapter_num):
                break
            prev = cn
        if prev is None:
            return 0
        cf = self.data.chapter_derived(prev).chapter_facts or {}
        return int(cf.get("banked_cp_at_end") or 0)

    def _eligibility_at_cursor(self, cs, word_idx: int, sec_idx: int) -> dict:
        sections = cs.meta.sections or []
        section_counts = False
        if 0 <= sec_idx < len(sections):
            section_counts = bool(sections[sec_idx].get("counts_for_cp", True))
        section_eligible = section_counts

        if 0 <= sec_idx < len(sections):
            for span in sections[sec_idx].get("span_overrides") or []:
                try:
                    start = int(span.get("word_offset_start"))
                    end = int(span.get("word_offset_end"))
                except (TypeError, ValueError):
                    continue
                if start <= int(word_idx) < end:
                    span_eligible = bool(span.get("counts_for_cp"))
                    return {
                        "section_eligible": section_eligible,
                        "text_eligible": span_eligible,
                        "reason": str(span.get("reason_code") or "span override"),
                    }
        if not section_eligible:
            return {
                "section_eligible": False,
                "text_eligible": False,
                "reason": "section ineligible",
            }
        return {
            "section_eligible": True,
            "text_eligible": True,
            "reason": "content",
        }

    def _global_cp_from_roll(self, chapter_num: str, roll: dict) -> int | None:
        return self._chapter_scoped_roll_value(
            chapter_num, roll, "cumulative_word_offset"
        )

    def _local_cp_from_roll(self, chapter_num: str, roll: dict) -> int | None:
        return self._chapter_scoped_roll_value(chapter_num, roll, "word_position")

    def _roll_display_raw_word_index(self, chapter_num: str, roll: dict) -> int | None:
        if roll.get("display_position_policy") != "source_marker":
            return None
        if str(roll.get("mention_chapter_num")) != str(chapter_num):
            return None
        raw = roll.get("mention_word_position")
        if raw is None:
            return None
        raw_idx = int(raw)
        cs = self.state.chapter
        if cs is not None and str(cs.meta.chapter_num) == str(chapter_num):
            if self._is_structural_word_index(cs, raw_idx):
                return None
        return raw_idx

    def _chapter_scoped_roll_value(
        self, chapter_num: str, roll: dict, field: str
    ) -> int | None:
        cn = str(chapter_num)
        display_field = f"display_{field}"
        mechanical_field = f"mechanical_{field}"
        if (
            str(roll.get("display_chapter_num")) == cn
            and roll.get(display_field) is not None
        ):
            return int(roll[display_field])
        if (
            str(roll.get("mechanical_chapter_num")) == cn
            and roll.get(mechanical_field) is not None
        ):
            return int(roll[mechanical_field])
        has_explicit_chapters = (
            roll.get("display_chapter_num") is not None
            or roll.get("mechanical_chapter_num") is not None
        )
        if not has_explicit_chapters and roll.get(field) is not None:
            return int(roll[field])
        return None

    def _mention_cp_from_roll(self, chapter_num: str, roll: dict) -> int | None:
        cn = str(chapter_num)
        if (
            str(roll.get("mention_chapter_num")) == cn
            and roll.get("mention_word_position") is not None
        ):
            return int(roll["mention_word_position"])
        return self._local_cp_from_roll(chapter_num, roll)

    def _curated_roll_global_positions(self) -> list[int]:
        positions: list[int] = []
        for roll in self.data.roll_facts.get("rolls", []):
            if roll.get("source_kind") == "trigger":
                continue
            pos = (
                roll.get("display_cumulative_word_offset")
                if roll.get("display_cumulative_word_offset") is not None
                else roll.get("cumulative_word_offset")
            )
            if pos is None:
                pos = roll.get("mechanical_cumulative_word_offset")
            if pos is not None:
                positions.append(int(pos))
        return sorted(set(positions))

    def _predicted_roll_global_positions(self) -> list[int]:
        positions: list[int] = []
        for roll in self.data.predicted.get("predicted", []):
            pos = roll.get("cp_offset")
            if pos is not None:
                positions.append(int(pos))
        return sorted(set(positions))

    def _curated_evidence_global_positions(self) -> list[int]:
        positions: list[int] = []
        for roll in self.data.roll_facts.get("rolls", []):
            if roll.get("source_kind") == "trigger" or not self._roll_evidence_quotes(roll):
                continue
            pos = self._stats_evidence_global_position(roll)
            if pos is not None:
                positions.append(int(pos))
        return sorted(set(positions))

    def _stats_evidence_global_position(self, roll: dict) -> int | None:
        quotes = self._roll_evidence_quotes(roll)
        if not quotes:
            return None
        quote = None
        if roll.get("display_position_policy") == "mention":
            for candidate in quotes:
                if (
                    str(candidate.get("mention_chapter_num")) == str(roll.get("mention_chapter_num"))
                    and candidate.get("mention_word_position") == roll.get("mention_word_position")
                ):
                    quote = candidate
                    break
        if quote is None:
            quote = quotes[0]
        return self._quote_global_position(roll, quote)

    def _quote_global_position(self, roll: dict, quote: dict) -> int | None:
        local = quote.get("mention_word_position")
        if local is None:
            return None
        quote_chapter = str(quote.get("mention_chapter_num") or "")
        bases = [
            (
                roll.get("display_chapter_num"),
                roll.get("display_cumulative_word_offset"),
                roll.get("display_word_position"),
            ),
            (
                roll.get("mechanical_chapter_num"),
                roll.get("mechanical_cumulative_word_offset"),
                roll.get("mechanical_word_position"),
            ),
            (
                roll.get("chapter_num"),
                roll.get("cumulative_word_offset"),
                roll.get("word_position"),
            ),
        ]
        for chapter, cumulative, word in bases:
            if (
                chapter is not None
                and str(chapter) == quote_chapter
                and cumulative is not None
                and word is not None
            ):
                return int(cumulative) - int(word) + int(local)
        return int(local)

    def _distance_stats(
        self, story_cp_cursor: int, positions: list[int]
    ) -> tuple[int, int | None]:
        last = max((p for p in positions if p <= story_cp_cursor), default=0)
        nxt = min((p for p in positions if p > story_cp_cursor), default=None)
        since = max(0, story_cp_cursor - last)
        until = None if nxt is None else max(0, nxt - story_cp_cursor)
        return since, until

    def _predicted_roll_distance_stats(
        self, story_cp_cursor: int
    ) -> tuple[int, int | None]:
        return self._distance_stats(
            story_cp_cursor, self._predicted_roll_global_positions()
        )

    def _curated_roll_distance_stats(
        self, story_cp_cursor: int
    ) -> tuple[int, int | None]:
        return self._distance_stats(
            story_cp_cursor, self._curated_roll_global_positions()
        )

    def _curated_evidence_distance_stats(
        self, story_cp_cursor: int
    ) -> tuple[int, int | None]:
        return self._distance_stats(
            story_cp_cursor, self._curated_evidence_global_positions()
        )

    def _roll_cost(self, roll: dict) -> int:
        if roll.get("outcome") != "hit":
            return 0
        return int(roll.get("purchased_perk_cost_total") or 0)

    def _chapter_spent_total_from_facts(self, chapter_num: str) -> int:
        cf = self.data.chapter_derived(str(chapter_num)).chapter_facts or {}
        return sum(self._roll_cost(r) for r in (cf.get("rolls") or []))

    def _chapter_trigger_after_bank(self, cs) -> int | None:
        for r in cs.derived.roll_facts:
            if r.get("source_kind") == "trigger" and r.get("banked_cp_after_roll") is not None:
                return int(r["banked_cp_after_roll"])
        cf = cs.derived.chapter_facts or {}
        for r in cf.get("rolls") or []:
            if r.get("source_kind") == "trigger" and r.get("banked_cp_after_roll") is not None:
                return int(r["banked_cp_after_roll"])
        return None

    def _cp_stats_at_cursor(self, cs, cp_word_idx: int) -> dict[str, int]:
        cn = cs.meta.chapter_num
        spent_before = 0
        for prev_cn in self.data.chapter_order:
            if prev_cn == cn:
                break
            spent_before += self._chapter_spent_total_from_facts(prev_cn)
        spent_chapter = 0
        cf = cs.derived.chapter_facts or {}
        for r in (cf.get("rolls") or []):
            if r.get("source_kind") == "trigger":
                spent_chapter += self._roll_cost(r)
        for roll in self._unified_rolls(cs):
            if int(roll["word_position"]) > cp_word_idx:
                break
            spent_chapter += self._roll_cost(roll)
        banked = self._cp_at_cursor(cp_word_idx)
        spent_total = spent_before + spent_chapter
        gained_total = spent_total + banked
        gained_before = spent_before + self._chapter_prev_banked_end(cn)
        return {
            "gained_total": gained_total,
            "gained_chapter": max(0, gained_total - gained_before),
            "available": banked,
            "spent_total": spent_total,
            "spent_chapter": spent_chapter,
        }

    def _cp_earning_word_offset(self, raw_word_idx: int) -> int:
        """Map raw cursor word index to its CP-earning offset.

        CP-eligible word = section eligibility plus passage-level span
        overrides. This is the canonical raw→CP function for the TUI;
        ``_raw_word_for_cp_offset`` is its inverse.
        """
        cs = self.state.chapter
        if cs is None or raw_word_idx <= 0:
            return 0
        sections = cs.meta.sections or []
        cp = 0
        raw_running = 0
        for sec in sections:
            wc = int(sec.get("word_count") or 0)
            sec_end = raw_running + wc
            upper = min(sec_end, raw_word_idx)
            if upper > raw_running:
                cp += section_cp_word_count(
                    section_word_start=raw_running,
                    section_word_end=upper,
                    base_counts_for_cp=bool(sec.get("counts_for_cp", True)),
                    span_overrides=section_span_overrides(
                        sec,
                        raw_running,
                        upper,
                    ),
                )
            if sec_end >= raw_word_idx:
                break
            raw_running = sec_end
        return cp

    def _trigger_event_for_chapter(self, cs) -> dict | None:
        """Return the chapter's trigger event (if any).

        Curator entries with ``source_kind == "trigger"`` represent
        perks acquired at chapter start — granted with Joe's power /
        constellation reveal, not as a roll outcome. These get
        surfaced separately and their perks/costs are excluded from
        the inference.
        """
        if cs is None:
            return None
        triggers = [
            r for r in cs.derived.roll_facts
            if r.get("source_kind") == "trigger"
        ]
        if not triggers:
            return None
        # Aggregate (typical case is a single trigger entry per chapter).
        all_purchased: list[dict] = []
        all_free: list[dict] = []
        cost_total = 0
        for t in triggers:
            for p in (t.get("purchased_perks") or []):
                all_purchased.append({
                    "name": p.get("name", "?"),
                    "cost": int(p.get("cost") or 0),
                    "free": bool(p.get("free")),
                })
                if not p.get("free"):
                    cost_total += int(p.get("cost") or 0)
            for fp in (t.get("free_perks") or []):
                all_free.append({
                    "name": fp.get("name", "?"),
                    "cost": 0,
                    "free": True,
                })
        # Names used to filter chapter perks for the rolls inference.
        trigger_names = {p["name"] for p in all_purchased + all_free}
        return {
            "purchased_perks": all_purchased + all_free,
            "purchased_perk_cost_total": cost_total,
            "perk_names": trigger_names,
        }

    def _rolls_header_count(self, cs) -> str:
        predicted = _fmt_int(len(cs.derived.predicted_rolls))
        current = sum(
            1 for roll in self._unified_rolls(cs)
            if roll.get("display_kind") not in {"deferred_in", "source_deferred"}
        )
        source = sum(
            1 for roll in self._unified_rolls(cs)
            if roll.get("display_kind") not in {"deferred_in", "source_deferred"}
            and self._is_source_evidence_roll(roll)
        )
        curated = max(0, current - source)
        source_text = f"{_fmt_int(source)} source"
        if curated:
            source_text = f"{source_text}, {_fmt_int(curated)} curated"
        return f"{predicted} predicted, {source_text}"

    def _predicted_slot_rolls(self, cs) -> list[dict]:
        cn = cs.meta.chapter_num
        chapter_cp_start = self._chapter_cp_start(cn)
        rows: list[dict] = []
        for idx, roll in enumerate(cs.derived.predicted_rolls, start=1):
            if str(roll.get("chapter_num")) != cn:
                continue
            global_cp = roll.get("cp_offset")
            if global_cp is None:
                continue
            local_cp = int(global_cp) - chapter_cp_start
            raw = self._roll_marker_word_index_from_cp(cs, local_cp)
            override = self._roll_override_entry(cn, idx)
            mention_chapter = (
                str(override.get("mention_chapter_num"))
                if override and override.get("mention_chapter_num") is not None
                else cn
            )
            rows.append({
                "index": idx,
                "target_roll_index": idx,
                "target_chapter_num": cn,
                "visible_chapter_num": cn,
                "display_kind": "predicted_slot",
                "source": "prediction",
                "source_kind": "predicted_slot",
                "outcome": "open",
                "roll_number": roll.get("roll_number"),
                "word_position": local_cp,
                "raw_word_position": raw,
                "global_cp_word": int(global_cp),
                "mechanical_chapter_num": cn,
                "mechanical_word_position": local_cp,
                "mechanical_cumulative_word_offset": int(global_cp),
                "display_chapter_num": cn,
                "display_word_position": local_cp,
                "display_cumulative_word_offset": int(global_cp),
                "mention_chapter_num": mention_chapter,
                "mention_word_position": (
                    override.get("mention_word_position") if override else None
                ),
                "display_position_policy": (
                    override.get("display_position_policy") if override else None
                ),
                "evidence_quotes": list(override.get("evidence_quotes") or [])
                if override else [],
                "use_stable_target_identity": True,
                "skipped": self._roll_override_skipped(cn, idx),
                "deferred_to_later_chapter": bool(
                    (override or {}).get("deferred_to_later_chapter")
                ),
            })
        return rows

    def _roll_override_entry(self, chapter_num: str, index: int) -> dict | None:
        entry = (
            self.persistence.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(str(chapter_num), {})
        )
        rolls = entry.get("rolls") or []
        if not (1 <= int(index) <= len(rolls)):
            return None
        roll = rolls[int(index) - 1]
        return roll if isinstance(roll, dict) else None

    def _roll_override_skipped(self, chapter_num: str, index: int) -> bool:
        entry = self._roll_override_entry(chapter_num, index)
        return bool((entry or {}).get("skipped"))

    def _predicted_roll_for_chapter_index(
        self, chapter_num: str, index: int,
    ) -> dict | None:
        rows = [
            roll for roll in self.data.predicted.get("predicted", [])
            if str(roll.get("chapter_num")) == str(chapter_num)
        ]
        rows.sort(key=lambda roll: roll.get("cp_offset") or 0)
        if not (1 <= int(index) <= len(rows)):
            return None
        return rows[int(index) - 1]

    def _deferred_predicted_slot_rolls(
        self, cs, unified: list[dict] | None = None,
    ) -> list[dict]:
        """Open predicted slots from prior chapters deferred into this chapter."""
        cn = cs.meta.chapter_num
        represented = {
            (
                str(roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")),
                int(roll.get("target_roll_index") or 0),
            )
            for roll in (unified if unified is not None else self._unified_rolls(cs))
            if roll.get("display_kind") == "deferred_in"
            and roll.get("target_roll_index") is not None
        }
        rows: list[dict] = []
        overrides = (
            self.persistence.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
        )
        display_cp = self._chapter_cp_start(cn)

        def _unresolved_locationless_deferral(override: dict) -> bool:
            if override.get("skipped"):
                return False
            if override.get("source_roll_number") is not None:
                return False
            if override.get("evidence_quotes"):
                return False
            if override.get("mention_word_position") is not None:
                return False
            return True

        def _later_than_target(target_chapter: str) -> bool:
            return self._chapter_sort_key(str(target_chapter)) < self._chapter_sort_key(cn)

        def _floating_deferral_visible(target_chapter: str, override: dict) -> bool:
            return (
                override.get("deferred_to_later_chapter")
                and override.get("mention_chapter_num") is None
                and _unresolved_locationless_deferral(override)
                and _later_than_target(target_chapter)
            )

        def _concrete_deferral_visible(target_chapter: str, override: dict) -> bool:
            if str(override.get("mention_chapter_num") or "") == cn:
                return True
            return (
                override.get("mention_chapter_num") is not None
                and _unresolved_locationless_deferral(override)
                and _later_than_target(target_chapter)
            )

        for target_chapter, entry in overrides.items():
            if str(target_chapter) == cn:
                continue
            for idx, override in enumerate(entry.get("rolls") or [], start=1):
                if not isinstance(override, dict):
                    continue
                if not (
                    _concrete_deferral_visible(str(target_chapter), override)
                    or _floating_deferral_visible(str(target_chapter), override)
                ):
                    continue
                key = (str(target_chapter), int(idx))
                if key in represented:
                    continue
                predicted = self._predicted_roll_for_chapter_index(target_chapter, idx)
                if predicted is None:
                    continue
                global_cp = int(predicted.get("cp_offset") or 0)
                local_cp = global_cp - self._chapter_cp_start(str(target_chapter))
                row = {
                    "index": None,
                    "target_roll_index": idx,
                    "target_chapter_num": str(target_chapter),
                    "visible_chapter_num": cn,
                    "display_kind": "deferred_in",
                    "source": "prediction",
                    "source_kind": "predicted_slot",
                    "outcome": "open",
                    "roll_number": predicted.get("roll_number"),
                    "word_position": 0,
                    "raw_word_position": 0,
                    "global_cp_word": display_cp,
                    "mechanical_chapter_num": str(target_chapter),
                    "mechanical_word_position": local_cp,
                    "mechanical_cumulative_word_offset": global_cp,
                    "display_chapter_num": cn,
                    "display_word_position": 0,
                    "display_cumulative_word_offset": display_cp,
                    "mention_chapter_num": cn,
                    "mention_word_position": override.get("mention_word_position"),
                    "display_position_policy": override.get("display_position_policy"),
                    "evidence_quotes": list(override.get("evidence_quotes") or []),
                    "use_stable_target_identity": False,
                    "skipped": bool(override.get("skipped")),
                    "deferred_to_later_chapter": bool(
                        override.get("deferred_to_later_chapter")
                    ),
                }
                source_roll_number = override.get("source_roll_number")
                if source_roll_number is not None:
                    row["source_roll_number"] = int(source_roll_number)
                source_fact = self._roll_fact_for_roll_number(source_roll_number)
                if source_fact is not None:
                    for key in (
                        "roll_number",
                        "outcome",
                        "constellation",
                        "available_cp",
                        "banked_cp_after_roll",
                        "purchased_perks",
                        "purchased_perk_cost_total",
                        "rolled_perk_name",
                        "rolled_perk_cost",
                        "miss_cost_estimate",
                        "free_perks",
                        "raw",
                    ):
                        if source_fact.get(key) is not None:
                            row[key] = source_fact.get(key)
                    row["fact_source_kind"] = source_fact.get("source_kind")
                rows.append(row)
        return sorted(
            rows,
            key=lambda roll: (
                self._chapter_sort_key(str(roll["target_chapter_num"])),
                int(roll["target_roll_index"]),
            ),
        )

    def _roll_fact_for_roll_number(self, roll_number) -> dict | None:
        if roll_number is None:
            return None
        for roll in self.data.roll_facts.get("rolls", []):
            if roll.get("roll_number") == roll_number:
                return roll
        return None


    def _predicted_slot_index_for_cp(self, cs, local_cp: int | None) -> int | None:
        if local_cp is None:
            return None
        for slot in self._predicted_slot_rolls(cs):
            if int(slot["word_position"]) == int(local_cp):
                return int(slot["target_roll_index"])
        return None

    def _roll_slot_rows(
        self,
        cs,
        unified: list[dict] | None = None,
    ) -> list[dict]:
        """Return the main stats roll list as predicted slots.

        Roll facts are evidence assigned to slots. Predicted slots remain
        visible even when they are skipped or still open.
        """
        assigned: dict[int, dict] = {}
        for roll in unified if unified is not None else self._unified_rolls(cs):
            if roll.get("display_kind") in {"deferred_in", "source_deferred"}:
                continue
            if str(roll.get("target_chapter_num") or cs.meta.chapter_num) != cs.meta.chapter_num:
                continue
            target = roll.get("target_roll_index")
            if target is None:
                continue
            assigned[int(target)] = roll
        rows: list[dict] = []
        represented: set[tuple[str, int]] = set()
        for slot in self._predicted_slot_rolls(cs):
            idx = int(slot["target_roll_index"])
            if slot.get("skipped") or idx not in assigned:
                rows.append(slot)
                represented.add((str(slot["target_chapter_num"]), idx))
                continue
            source = dict(assigned[idx])
            source["index"] = idx
            source["target_roll_index"] = idx
            rows.append(source)
            represented.add((str(source["target_chapter_num"]), idx))
        for roll in unified if unified is not None else self._unified_rolls(cs):
            if roll.get("display_kind") in {"deferred_in", "source_deferred"}:
                continue
            target = roll.get("target_roll_index")
            target_chapter = str(roll.get("target_chapter_num") or cs.meta.chapter_num)
            if target is not None and (target_chapter, int(target)) in represented:
                continue
            rows.append(roll)
        return rows

    def _roll_evidence_picker_rolls(self, cs) -> list[dict]:
        """Rows normal roll evidence may be attached to.

        Skipped slots are deliberately absent: normal quote evidence belongs
        on emitted roll/source rows or open slots, not on skipped slots.
        """
        unified = self._unified_rolls(cs)
        deferred_rows = [
            roll for roll in unified
            if roll.get("display_kind") in {"deferred_in", "source_deferred"}
        ]
        deferred_rows.extend(self._deferred_predicted_slot_rolls(cs, unified))
        current_rows: list[dict] = []
        seen_targets: set[tuple] = set()
        for roll in [
            *self._roll_slot_rows(cs, unified),
            *[
                roll for roll in unified
                if roll.get("display_kind") not in {"deferred_in", "source_deferred"}
            ],
        ]:
            if (
                roll.get("display_kind") == "predicted_slot"
                and roll.get("skipped")
            ):
                continue
            key = self._roll_target_key(roll)
            if key is not None and key in seen_targets:
                continue
            current_rows.append(roll)
            if key is not None:
                seen_targets.add(key)
        return [*deferred_rows, *current_rows]

    def _open_predicted_slot_rolls(self, cs) -> list[dict]:
        occupied = {
            int(roll["target_roll_index"])
            for roll in self._unified_rolls(cs)
            if (
                roll.get("display_kind") != "deferred_in"
                and str(roll.get("target_chapter_num") or cs.meta.chapter_num)
                == cs.meta.chapter_num
                and roll.get("target_roll_index") is not None
            )
        }
        return [
            roll for roll in self._predicted_slot_rolls(cs)
            if int(roll["target_roll_index"]) not in occupied
        ]

    def _roll_target_key(self, roll: dict | None) -> tuple | None:
        if roll is None:
            return None
        return (
            str(roll.get("target_chapter_num") or roll.get("mechanical_chapter_num") or ""),
            int(roll.get("target_roll_index") or roll.get("index") or 0),
            str(roll.get("display_kind") or ""),
        )

    def _same_roll_target(self, left: dict | None, right: dict | None) -> bool:
        left_key = self._roll_target_key(left)
        right_key = self._roll_target_key(right)
        return left_key is not None and left_key == right_key

    def _select_roll_target(self, roll: dict) -> None:
        self._selected_roll_target = dict(roll)

    def _selected_roll_target_if_visible(self) -> dict | None:
        cs = self.state.chapter
        if cs is None or self._selected_roll_target is None:
            return None
        unified = self._unified_rolls(cs)
        visible = [
            *self._roll_slot_rows(cs, unified),
            *[
                roll for roll in unified
                if roll.get("display_kind") in {"deferred_in", "source_deferred"}
            ],
            *self._deferred_predicted_slot_rolls(cs, unified),
        ]
        for roll in visible:
            if self._same_roll_target(roll, self._selected_roll_target):
                return roll
        self._selected_roll_target = None
        return None

    def _selected_or_default_roll_target(self) -> dict | None:
        return self._selected_roll_target_if_visible() or self._default_roll_target()

    def _mechanical_roll_index(self, roll: dict) -> int | None:
        chapter_num = roll.get("mechanical_chapter_num")
        if chapter_num is None:
            return None
        mechanical_cumulative = roll.get("mechanical_cumulative_word_offset")
        if (
            mechanical_cumulative is not None
            and roll.get("predicted_chapter_num") is not None
            and str(roll.get("predicted_chapter_num")) == str(chapter_num)
        ):
            predicted = [
                r for r in self.data.predicted.get("predicted", [])
                if str(r.get("chapter_num")) == str(chapter_num)
            ]
            predicted.sort(key=lambda r: r.get("cp_offset") or 0)
            for idx, predicted_roll in enumerate(predicted, start=1):
                if int(predicted_roll.get("cp_offset") or -1) == int(mechanical_cumulative):
                    return int(predicted_roll.get("slot_index") or idx)
        rows = [
            r for r in self.data.roll_facts.get("rolls", [])
            if r.get("source_kind") != "trigger"
            and str(r.get("mechanical_chapter_num")) == str(chapter_num)
        ]
        rows.sort(key=lambda r: (
            (
                int(r.get("mechanical_word_position") or r.get("word_position"))
                if (r.get("mechanical_word_position") or r.get("word_position")) is not None
                else 10**12
            ),
            int(r.get("roll_number") or r.get("roll_sequence_in_chapter") or 0),
        ))
        roll_number = roll.get("roll_number")
        for idx, candidate in enumerate(rows, start=1):
            if (
                roll_number is not None
                and candidate.get("roll_number") == roll_number
            ):
                return idx
            if candidate is roll:
                return idx
        return None

    def _unified_rolls(self, cs) -> list[dict]:
        """Format canonical per-chapter roll facts for display/navigation."""
        if cs is None:
            return []
        cn = cs.meta.chapter_num
        canonical_rows = [
            r for r in cs.derived.roll_facts
            if r.get("source_kind") != "trigger"
            and (
                self._local_cp_from_roll(cn, r) is not None
                or str(r.get("chapter_num")) == cn
                or cn in {str(ch) for ch in r.get("visible_chapter_nums") or []}
            )
        ]

        result: list[dict] = []

        def _is_deferred_in(row: dict, local_cp: int | None) -> bool:
            return (
                str(row.get("chapter_num")) == cn
                and str(row.get("mechanical_chapter_num") or cn) != cn
            )

        def _is_unslotted_current_chapter(row: dict, local_cp: int | None) -> bool:
            return (
                local_cp is None
                and str(row.get("mechanical_chapter_num") or row.get("chapter_num")) == cn
            )

        def _is_source_projection(row: dict, local_cp: int | None) -> bool:
            return (
                local_cp is None
                and str(row.get("source_chapter_num")) == cn
                and str(row.get("mechanical_chapter_num") or row.get("chapter_num")) != cn
                and not _is_deferred_in(row, local_cp)
            )

        def _sort_key(row: dict) -> tuple[int, int, int, int]:
            display_raw = self._roll_display_raw_word_index(cn, row)
            if display_raw is not None:
                local_cp = self._cp_earning_word_offset(display_raw)
            else:
                local_cp = self._local_cp_from_roll(cn, row)
            if _is_deferred_in(row, local_cp):
                bucket = 0
            elif _is_source_projection(row, local_cp):
                bucket = 1
                local_cp = row.get("source_word_position")
            elif local_cp is not None:
                bucket = 1
            else:
                bucket = 2
            return (
                bucket,
                local_cp if local_cp is not None else 10**12,
                int(row.get("mechanical_cumulative_word_offset") or 10**12),
                int(row.get("roll_number") or row.get("roll_sequence_in_chapter") or 0),
            )

        rows = sorted(canonical_rows, key=_sort_key)
        has_cross_chapter_visible_rows = any(
            str(row.get("mechanical_chapter_num") or cn) != cn
            for row in rows
        )
        local_index = 0
        for row in rows:
            display_raw = self._roll_display_raw_word_index(cn, row)
            local_cp = (
                self._cp_earning_word_offset(display_raw)
                if display_raw is not None
                else self._local_cp_from_roll(cn, row)
            )
            is_deferred_in = _is_deferred_in(row, local_cp)
            is_unslotted_current = _is_unslotted_current_chapter(row, local_cp)
            is_source_projection = _is_source_projection(row, local_cp)
            if local_cp is None and not (
                is_deferred_in or is_unslotted_current or is_source_projection
            ):
                continue
            if is_deferred_in:
                display_kind = "deferred_in"
                word_position = int(local_cp) if local_cp is not None else 0
                if display_raw is not None:
                    raw_word_position = display_raw
                elif local_cp is not None:
                    raw_word_position = self._roll_marker_word_index_from_cp(
                        cs, int(local_cp)
                    )
                else:
                    raw_word_position = 0
                global_cp = (
                    self._chapter_cp_start(cn) + int(word_position)
                    if local_cp is not None
                    else row.get("mechanical_cumulative_word_offset")
                )
            elif is_source_projection:
                display_kind = "source_deferred"
                word_position = int(row.get("source_word_position") or 0)
                raw_word_position = word_position
                global_cp = (
                    int(row["source_cumulative_word_offset"])
                    if row.get("source_cumulative_word_offset") is not None
                    else self._chapter_cp_start(cn) + int(word_position)
                )
            elif display_raw is not None:
                display_kind = "chapter_roll"
                local_index += 1
                raw_word_position = display_raw
                word_position = int(local_cp or 0)
                global_cp = self._chapter_cp_start(cn) + int(word_position)
            elif is_unslotted_current:
                display_kind = "chapter_roll"
                local_index += 1
                raw_word_position = self._curated_roll_word_index(cs, row)
                if raw_word_position is not None:
                    word_position = self._cp_earning_word_offset(raw_word_position)
                else:
                    word_position = self._chapter_cp_total(cn, cs)
                global_cp = self._chapter_cp_start(cn) + int(word_position)
            else:
                display_kind = "chapter_roll"
                local_index += 1
                word_position = int(local_cp)
                raw_word_position = self._roll_marker_word_index_from_cp(
                    cs, int(local_cp)
                )
                global_cp = self._global_cp_from_roll(cn, row)
            target_chapter_num = str(row.get("mechanical_chapter_num") or cn)
            predicted_target_index = (
                self._predicted_slot_index_for_cp(cs, int(word_position))
                if not is_deferred_in and target_chapter_num == cn else None
            )
            entry = {
                **row,
                "index": local_index if not is_deferred_in else None,
                "display_kind": display_kind,
                "word_position": int(word_position),
                "global_cp_word": global_cp,
                "raw_word_position": raw_word_position,
                "outcome": row.get("outcome") or "unknown",
                "constellation": row.get("constellation"),
                "purchased_perks": list(row.get("purchased_perks") or []),
                "purchased_perk_cost_total": row.get("purchased_perk_cost_total"),
                "source": row.get("fact_source") or row.get("source") or "canonical",
                "evidence_quotes": list(row.get("evidence_quotes") or []),
                "target_chapter_num": target_chapter_num,
                "target_roll_index": (
                    predicted_target_index or self._mechanical_roll_index(row)
                ),
                "visible_chapter_num": cn,
                "use_stable_target_identity": not has_cross_chapter_visible_rows,
            }
            target_index = entry.get("target_roll_index")
            if target_index is not None:
                override = self._roll_override_entry(target_chapter_num, int(target_index))
                if (
                    override is not None
                    and override.get("source_deferred_to_chapter") is not None
                ):
                    entry["source_deferred_to_chapter"] = str(
                        override["source_deferred_to_chapter"]
                    )
                if (
                    override is not None
                    and override.get("source_roll_number") is not None
                ):
                    entry["source_roll_number"] = int(override["source_roll_number"])
            result.append(entry)
        return result

    def _roll_evidence_marker(self, roll: dict) -> str:
        evidence_quotes = self._roll_evidence_quotes(roll)
        source_marker = "S" if self._is_source_evidence_roll(roll) else ""
        if evidence_quotes:
            return source_marker + ("Q" * len(evidence_quotes))
        if source_marker:
            return source_marker
        evidence_kind = str(roll.get("evidence_kind") or "")
        if evidence_kind in {"direct", "general_only", "forward_ref"} and (
            roll.get("anchor_char_offset_in_chapter") is not None
            or roll.get("predicted_char_offset_in_chapter") is not None
        ):
            return "T"
        return "I"

    @staticmethod
    def _is_source_evidence_roll(roll: dict) -> bool:
        if roll.get("curator_added"):
            return False
        if roll.get("source_kind") in {"roll", "miss"}:
            return (
                bool(str(roll.get("raw") or "").strip())
                or roll.get("source") in {"curator_rolls", "curator"}
                or roll.get("fact_source") == "curator_rolls"
            )
        return (
            roll.get("source") in {"curator_rolls", "curator"}
            or roll.get("fact_source") == "curator_rolls"
        )

    @staticmethod
    def _roll_evidence_quotes(roll: dict) -> list[dict]:
        return [
            q for q in (roll.get("evidence_quotes") or [])
            if isinstance(q, dict) and q.get("text")
        ]

    def _model_validation_summary(self, cs) -> str:
        model = (cs.derived.chapter_facts or {}).get("model_validation") or {}
        current = bool(model.get("current_discrepancy"))
        prior = bool(model.get("prior_discrepancy"))
        if current and prior:
            return "discrepancy here + earlier"
        if current:
            return "discrepancy here"
        if prior:
            first = model.get("first_discrepancy_chapter_num")
            return f"earlier discrepancy ch {first}" if first else "earlier discrepancy"
        status = model.get("status")
        return "ok" if status == "ok" else str(status or "unknown")

    def _curation_status_line(self) -> str:
        if self._last_curation_error:
            return self._format_curation_error_status(self._last_curation_error)
        if self._last_curation_message:
            return f"  Curation: [dim]{self._last_curation_message}[/]\n\n"
        return ""

    @staticmethod
    def _format_curation_error_status(error: str) -> str:
        lines = [line.strip() for line in str(error).splitlines() if line.strip()]
        summary = lines[0] if lines else "unknown error"
        if len(summary) > 140:
            summary = summary[:137].rstrip() + "..."
        return (
            f"  Curation failed: [red]{summary}[/]\n"
            "  Details: press F12 for snapshot; run verify/check command in terminal.\n\n"
        )

    def _format_roll_stat_line(self, roll: dict, marker: str) -> str:
        global_num = roll.get("roll_number")
        outcome = roll.get("outcome") or "unknown"
        evidence = self._roll_evidence_marker(roll)
        constel = roll.get("constellation") or "unknown"
        if roll.get("display_kind") == "predicted_slot":
            chapter_idx = self._display_roll_identity(roll)
            word_position = roll.get("word_position")
            mention_chapter = roll.get("mention_chapter_num")
            target_chapter = roll.get("target_chapter_num")
            locationless_future_deferral = False
            if roll.get("skipped"):
                status = "skipped"
            elif roll.get("deferred_to_later_chapter"):
                status = "deferred to future chapter"
                locationless_future_deferral = True
            elif (
                mention_chapter is not None
                and target_chapter is not None
                and str(mention_chapter) != str(target_chapter)
            ):
                if (
                    roll.get("mention_word_position") is None
                    and not self._roll_evidence_quotes(roll)
                ):
                    status = "deferred to future chapter"
                    locationless_future_deferral = True
                else:
                    status = f"deferred to ch {mention_chapter}"
            else:
                status = "predicted"
            if locationless_future_deferral:
                return (
                    f"  {marker} # {chapter_idx} {status} "
                    f"({global_num if global_num is not None else '?'})"
                )
            return (
                f"  {marker} # {chapter_idx} {status} "
                f"({global_num if global_num is not None else '?'}) "
                f"at CP {_fmt_int(word_position)}"
            )
        if outcome == "miss":
            min_cost = roll.get("miss_cost_estimate") or roll.get("rolled_perk_cost")
            possible = self._miss_possible_suffix(roll, min_cost)
            perk_text = (
                f"missed >= {int(min_cost)} CP{possible}"
                if min_cost is not None else "missed"
            )
            detail_lines = [f"    {constel} - {perk_text}"]
        else:
            perks = roll.get("purchased_perks") or []
            if perks:
                detail_lines = []
                for p in perks:
                    name = _perk_display_label(p) or "unknown"
                    cost = "free" if p.get("free") else str(int(p.get("cost") or 0))
                    detail_lines.append(f"    {constel} - {name} ({cost})")
            else:
                detail_lines = [f"    {constel} - perk unknown"]
        available = roll.get("available_cp")
        available_part = (
            f"Avail CP {int(available)}" if available is not None else "Avail CP ?"
        )
        if roll.get("display_kind") == "source_deferred":
            source_idx = roll.get("source_roll_index") or roll.get("target_roll_index") or "?"
            mechanical_chapter = (
                roll.get("mechanical_chapter_num")
                or roll.get("display_chapter_num")
                or "?"
            )
            target_chapter = roll.get("target_chapter_num") or mechanical_chapter
            target_idx = roll.get("target_roll_index") or "?"
            source_chapter = roll.get("source_chapter_num")
            source_detail = (
                f"    source/narrative from ch {source_chapter} #{source_idx}"
                if source_chapter is not None
                else f"    source row #{source_idx}"
            )
            return "\n".join([
                (
                    f"  {marker} deferred from ch {target_chapter} #{target_idx} source "
                    f"({global_num if global_num is not None else '?'}) "
                    f"{available_part} {outcome} {evidence}"
                ),
                source_detail,
                *detail_lines,
            ])
        if roll.get("display_kind") == "deferred_in":
            source_chapter = roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")
            source_idx = roll.get("target_roll_index") or "?"
            if roll.get("source_kind") == "predicted_slot" and outcome == "open":
                return (
                    f"  {marker} deferred from ch {source_chapter} #{source_idx} "
                    f"({global_num if global_num is not None else '?'}) "
                    f"predicted {evidence}"
                )
            return "\n".join([
                (
                    f"  {marker} deferred from ch {source_chapter} #{source_idx} "
                    f"({global_num if global_num is not None else '?'}) "
                    f"{available_part} {outcome} {evidence}"
                ),
                *detail_lines,
            ])
        mechanical_chapter = roll.get("mechanical_chapter_num")
        mention_chapter = roll.get("mention_chapter_num")
        if (
            mechanical_chapter is not None
            and mention_chapter is not None
            and str(mention_chapter) != str(mechanical_chapter)
        ):
            detail_lines.insert(
                0,
                self._cross_chapter_evidence_detail(
                    str(mechanical_chapter), str(mention_chapter)
                ),
            )
        source_chapter = roll.get("source_chapter_num")
        source_index = roll.get("source_roll_index")
        if (
            source_chapter is not None
            and mechanical_chapter is not None
            and str(source_chapter) != str(mechanical_chapter)
        ):
            detail_lines.insert(
                0,
                (
                    f"    source/narrative from ch {source_chapter}"
                    f" #{source_index if source_index is not None else '?'}"
                ),
            )
        source_deferred_to = roll.get("source_deferred_to_chapter")
        if source_deferred_to is not None:
            detail_lines.insert(0, f"    source roll deferred to ch {source_deferred_to}")
        display_line = self._roll_display_policy_detail(roll)
        if display_line:
            detail_lines.insert(0, display_line)
        chapter_idx = self._display_roll_identity(roll)
        return "\n".join([
            (
                f"  {marker} # {chapter_idx} "
                f"({global_num if global_num is not None else '?'}) "
                f"{available_part} {outcome} {evidence}"
            ),
            *detail_lines,
        ])

    @staticmethod
    def _chapter_sort_key(chapter_num: str) -> tuple[int, int]:
        major, _dot, minor = str(chapter_num).partition(".")
        return (
            int(major) if major.isdigit() else 10**9,
            int(minor) if minor.isdigit() else 0,
        )

    @classmethod
    def _cross_chapter_evidence_detail(
        cls, mechanical_chapter: str, mention_chapter: str
    ) -> str:
        if cls._chapter_sort_key(mention_chapter) > cls._chapter_sort_key(
            mechanical_chapter
        ):
            return f"    narrative deferred to ch {mention_chapter}"
        return f"    narrative evidence from ch {mention_chapter}"

    @staticmethod
    def _roll_display_policy_detail(roll: dict) -> str:
        policy = roll.get("display_position_policy")
        if not policy:
            policy = "mechanical" if roll.get("evidence_quotes") else ""
        if not policy:
            return ""
        mention_word = roll.get("mention_word_position")
        default_policy = "mention" if mention_word is not None else "mechanical"
        if policy == default_policy and not roll.get("evidence_quotes"):
            return ""
        if policy == "mechanical":
            return "    display at predicted roll position"
        if policy == "mention":
            return "    display at quoted evidence"
        if policy == "source_marker":
            return "    display at source marker"
        if policy == "section_start":
            return "    display at section start"
        if policy == "section_end":
            return "    display at section end"
        return f"    display policy: {policy}"

    @staticmethod
    def _display_roll_identity(roll: dict) -> int:
        visible_chapter = roll.get("visible_chapter_num") or roll.get("chapter_num")
        target_chapter = roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")
        if (
            roll.get("use_stable_target_identity", True)
            and
            roll.get("target_roll_index") is not None
            and (
                visible_chapter is None
                or target_chapter is None
                or str(visible_chapter) == str(target_chapter)
            )
        ):
            return int(roll["target_roll_index"])
        return int(roll.get("index") or roll.get("roll_sequence_in_chapter") or 0)

    def _miss_possible_suffix(self, roll: dict, min_cost) -> str:
        if min_cost is None:
            return ""
        constellation = roll.get("constellation")
        if not constellation:
            return ""
        chapter_num = str(
            roll.get("mechanical_chapter_num")
            or roll.get("target_chapter_num")
            or roll.get("chapter_num")
            or roll.get("visible_chapter_num")
            or ""
        )
        before = next(
            (
                c.get("before_chapter", {}).get("by_constellation", {})
                for c in self.data.outstanding_perks.get("chapters", [])
                if str(c.get("chapter_num")) == chapter_num
            ),
            {},
        )
        candidates = [
            p for p in before.get(str(constellation), [])
            if p.get("cost") is not None and int(p["cost"]) >= int(min_cost)
        ]
        if not candidates:
            return ""
        if len(candidates) == 1:
            return f" ({candidates[0].get('name') or 'unknown'})"
        return f" ({len(candidates)} possible)"

    def _evidence_block(self, cs) -> str:
        rows: list[str] = []
        selected_quote_keys = self._selected_evidence_quote_keys()
        for roll in self._roll_evidence_picker_rolls(cs):
            if self._is_source_evidence_roll(roll):
                target_chapter = roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")
                target_index = roll.get("target_roll_index") or roll.get("index") or "?"
                global_num = roll.get("roll_number")
                global_part = f"global #{global_num}" if global_num is not None else "global #?"
                raw = str(roll.get("raw") or "").strip()
                rows.append(
                    f"  S against ch {target_chapter} #{target_index} ({global_part})"
                )
                if raw:
                    rows.append(f"    {raw}")
            for quote_idx, quote in enumerate(self._roll_evidence_quotes(roll), start=1):
                text = str(quote.get("text") or "")
                quote_start = cs.prose.text.find(text)
                target_chapter = roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")
                target_index = roll.get("target_roll_index") or roll.get("index") or "?"
                global_num = roll.get("roll_number")
                global_part = f"global #{global_num}" if global_num is not None else "global #?"
                quote_key = (
                    str(roll.get("target_chapter_num") or cs.meta.chapter_num),
                    int(target_index) if target_index != "?" else -1,
                    text,
                    str(quote.get("mention_chapter_num")),
                    str(quote.get("mention_word_position")),
                )
                marker = "▸" if quote_key in selected_quote_keys else " "
                rows.append(
                    f"  {marker} Q{quote_idx} against ch {target_chapter} "
                    f"#{target_index} ({global_part})"
                )
                if quote_start >= 0:
                    quote_word = _word_index_for_char_offset(
                        cs.prose.word_offsets, quote_start
                    )
                    roll_word = self._evidence_reference_word_index(cs, roll)
                    if quote_word is not None and roll_word is not None:
                        quote_cp = self._cp_earning_word_offset(int(quote_word))
                        distance = int(quote_word) - int(roll_word)
                        rows.extend([
                            f"    word distance: {_fmt_signed_int(distance)}",
                            f"    CP at quote start: {self._cp_at_cursor(quote_cp)}",
                        ])
                    continue
                mention_chapter = quote.get("mention_chapter_num")
                mention_word = quote.get("mention_word_position")
                if mention_chapter is not None or mention_word is not None:
                    rows.append(
                        f"    mention: ch {mention_chapter or '?'} word "
                        f"{_fmt_int(mention_word)}"
                    )
        return "\n".join(rows) if rows else "  (no evidence)"

    def _selected_evidence_quote_keys(self) -> set[tuple[str, int, str, str, str]]:
        try:
            targets = self._roll_evidence_quote_targets_at_selection_or_cursor()
        except (NoMatches, ScreenStackError):
            return set()
        return {
            (
                target["target_chapter"],
                int(target["target_index"]),
                str(target["quote"].get("text") or ""),
                str(target["quote"].get("mention_chapter_num")),
                str(target["quote"].get("mention_word_position")),
            )
            for target in targets
        }

    def _perks_this_chapter_block(self, cs) -> str:
        lines: list[str] = []
        for p in cs.derived.perks:
            constel = p.get("constellation") or "unknown"
            name = p.get("perk_name") or p.get("name") or "unknown"
            cost = "free" if p.get("free") else str(int(p.get("cost") or 0))
            lines.append(f"  {constel} - {name} ({cost})")
        return "\n".join(lines) if lines else "  (none)"

    def _raw_word_for_cp_offset(self, target_cp: int) -> int:
        """Inverse of ``_cp_earning_word_offset``: smallest raw word
        index whose CP-earning offset reaches ``target_cp``.

        Implemented as a binary search on the canonical forward
        function so both directions agree exactly.
        """
        cs = self.state.chapter
        if cs is None:
            return 0
        n = len(cs.prose.word_offsets)
        if target_cp <= 0:
            return 0
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            if self._cp_earning_word_offset(mid) < target_cp:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def _cp_at_cursor(self, cp_word_idx: int) -> int:
        """Banked CP at the cursor's CP-earning word offset.

        Walks canonical roll rows. Where curator/fact rows record
        available/banked CP, those values win over synthetic accrual.
        This preserves grants and duplicate-position curator rows.
        """
        cs = self.state.chapter
        if cs is None:
            return 0
        cf = cs.derived.chapter_facts or {}
        regime = int(cf.get("point_calculation_regime") or 1)
        rate_words = int(REGIMES.get(regime, REGIMES[1])["words_per_100_cp"])
        banked = int(cf.get("banked_cp_at_start") or 0)
        trigger_after = self._chapter_trigger_after_bank(cs)
        if trigger_after is not None:
            banked = trigger_after
        last_cp = 0
        for roll in self._unified_rolls(cs):
            ecp = int(roll["word_position"])
            if ecp > cp_word_idx:
                break
            # Earn CP between last event and this roll's position.
            banked += (max(0, ecp - last_cp) * 100) // rate_words
            if roll.get("available_cp") is not None:
                banked = int(roll["available_cp"])
            if roll.get("banked_cp_after_roll") is not None:
                banked = int(roll["banked_cp_after_roll"])
            elif roll["outcome"] == "hit":
                banked = max(0, banked - int(roll["purchased_perk_cost_total"] or 0))
            last_cp = ecp
        banked += (max(0, cp_word_idx - last_cp) * 100) // rate_words
        return max(0, banked)

    # ----- bindings -----

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_undo_last(self) -> None:
        """Restore the file state from before the last curation action."""
        result = self.persistence.undo_last()
        if result is None:
            self._flash("nothing to undo")
            return
        action, chapter = result
        full = action in {"mark_span_eligibility", "remove_annotations_at_word"}
        ch_part = f" (ch {chapter})" if chapter else ""
        self._post_curation_refresh(f"undid: {action}{ch_part}", full=full)

    def action_quit_app(self) -> None:
        self.exit()

    def action_next_chapter(self) -> None:
        nxt = self.state.next_chapter()
        if nxt is not None:
            self._load_chapter(nxt)
            self.refresh_all_panels()

    def action_prev_chapter(self) -> None:
        prv = self.state.prev_chapter()
        if prv is not None:
            self._load_chapter(prv)
            self.refresh_all_panels()

    def action_focus_regex_star(self) -> None:
        self._set_active_regex_slot(3)
        inp = self.query_one("#regex_4", Input)
        inp.focus()

    def action_snapshot(self) -> None:
        """Dump current TUI state to ``data/manual/.forge_curator_snapshot.json``."""
        cs = self.state.chapter
        snap: dict = {
            "snapshot_version": 1,
            "snapshot_kind": "forge_curator_tui",
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "chapter": None,
            "cursor": None,
            "passage_view": None,
            "regex": [],
            "rolls": [],
            "derived": None,
            "prose": None,
            "active_regex_slot": self.active_regex_slot,
            "pending_chord": self._pending_chord,
            "pending_space_chord": self._pending_space_chord,
            "last_curation_error": self._last_curation_error,
            "last_curation_message": self._last_curation_message,
        }
        if cs is not None:
            snap["chapter"] = {
                "chapter_num": cs.meta.chapter_num,
                "full_title": cs.meta.full_title,
                "total_word_count": cs.meta.total_word_count,
                "cp_earning_word_count": cs.meta.cp_earning_word_count,
                "sections": cs.meta.sections,
            }
            snap["cursor"] = {
                "char": cs.cursor_char,
                "word_index": cs.cursor_word_index,
                "total_words": cs.total_words,
                "section_index": cs.section_index_at(cs.cursor_word_index),
            }
            snap["regex"] = [
                {
                    "slot": "*",
                    "pattern": cs.regex_hits[3].pattern,
                    "error": cs.regex_hits[3].error,
                    "word_indices": list(cs.regex_hits[3].word_indices),
                    "char_spans": list(cs.regex_hits[3].char_spans),
                }
            ]
            unified = self._unified_rolls(cs)
            deferred_rolls = [
                roll for roll in unified
                if roll.get("display_kind") in {"deferred_in", "source_deferred"}
            ]
            deferred_rolls.extend(self._deferred_predicted_slot_rolls(cs, unified))
            snap["rolls"] = [
                *deferred_rolls,
                *self._roll_slot_rows(cs, unified),
            ]
            snap["derived"] = {
                "chapter_facts": cs.derived.chapter_facts,
                "roll_facts": cs.derived.roll_facts,
                "predicted_rolls": cs.derived.predicted_rolls,
                "roll_outcomes": cs.derived.roll_outcomes,
                "validation": cs.derived.validation,
                "perks": cs.derived.perks,
                "overrides": cs.derived.overrides,
            }
            snap["prose"] = {
                "text": cs.prose.text,
                "word_offsets": cs.prose.word_offsets,
                "section_break_word_indices": cs.prose.section_break_word_indices,
                "implicit_header_word_ranges": cs.prose.implicit_header_word_ranges,
            }
        try:
            prose_view = self.query_one("#prose", PassageView)
            selection = prose_view.selection
            snap["passage_view"] = {
                "cursor": prose_view.cursor,
                "anchor": prose_view.anchor,
                "visual_mode": prose_view.visual_mode,
                "selection_start": selection[0] if selection else None,
                "selection_end": selection[1] if selection else None,
                "selected_text": prose_view.selected_text,
            }
        except Exception:
            pass
        try:
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT_PATH.write_text(
                json.dumps(snap, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            self.notify(f"Snapshot -> {SNAPSHOT_PATH}")
        except Exception as exc:
            try:
                self.notify(f"Snapshot failed: {exc}", severity="error")
            except Exception:
                pass

    # ----- chord-state hooks called by ``PassageView`` -----

    def _handle_bracket_chord_start(self, ch: str) -> None:
        self._pending_chord = ch

    def _handle_chord_completion(self, prefix: str, ch: str | None) -> bool:
        self._pending_chord = None
        return self._handle_chord(prefix, ch)

    def _set_active_regex_slot(self, slot: int) -> None:
        self.active_regex_slot = 3
        self._refresh_regex_bar()

    def _handle_regex_slot_hotkey(self, ch: str) -> None:
        return

    # ----- space-leader chord (Phase 2 actions) ---------------------------

    def _handle_space_chord(self, ch: str | None) -> None:
        """Dispatch the next-key after Space-leader to a curation action."""
        if not ch:
            return
        cs = self.state.chapter
        if cs is None:
            return
        cn = cs.meta.chapter_num
        if ch == "e":
            self._action_toggle_section_eligibility(cn)
        elif ch == "E":
            self._action_mark_span_eligibility(cn)
        elif ch == "h":
            self._action_set_last_outcome(cn, "hit")
        elif ch == "m":
            self._action_set_last_outcome(cn, "miss")
        elif ch == "c":
            self._action_pick_constellation(cn)
        elif ch == "p":
            self._action_pick_perks(cn)
        elif ch == "q":
            self._action_save_quote(cn)
        elif ch == "Q":
            self._action_save_quote_multi(cn)
        elif ch == "M":
            self._action_reassign_roll_quote(cn)
        elif ch == "v":
            self._action_pick_roll_visualization_position(cn)
        elif ch == "r":
            self._action_resolve_model_discrepancy(cn)
        elif ch == "R":
            self._action_rebuild_derived_data(cn)
        elif ch == "s":
            self._action_mark_predicted_roll_skipped(cn)
        elif ch == "S":
            self._action_assign_source_roll(cn)
        elif ch == "_":
            self._action_anchor_roll_without_quote(cn)
        elif ch == "d":
            self._action_defer_roll_to_next_chapter(cn)
        elif ch == "D":
            self._action_delete_chapter_curation_data(cn)
        elif ch == "i":
            self._action_insert_roll(cn)
        else:
            self._flash(f"<space>{ch}: not bound")

    # ----- Phase 2 action implementations ---------------------------------

    def _flash(self, message: str) -> None:
        """Refresh panels without treating manual edits as display facts."""
        self._last_curation_error = None
        self._last_curation_message = message
        self.refresh_all_panels()
        self._scroll_cursor_into_view()

    def _run_post_curation_derivation(self) -> None:
        for script in (
            "scripts/derive_roll_facts.py",
            "scripts/build_chapter_facts.py",
        ):
            result = subprocess.run(
                [sys.executable, script],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(detail or f"{script} exited {result.returncode}")

    def _run_full_curation_derivation(self) -> None:
        for script in (
            "scripts/extract_chapter_sections.py",
            "scripts/build_section_classifications.py",
            "scripts/predict_rolls.py",
            "scripts/derive_roll_facts.py",
            "scripts/build_chapter_facts.py",
        ):
            result = subprocess.run(
                [sys.executable, script],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise RuntimeError(detail or f"{script} exited {result.returncode}")

    def _post_curation_refresh(self, message: str, *, full: bool = False) -> None:
        """Regenerate derived roll/chapter facts, then reload display data."""
        cs = self.state.chapter
        if cs is None:
            self.refresh_all_panels()
            return
        cn = cs.meta.chapter_num
        saved_cursor = cs.cursor_char
        saved_anchor = None
        saved_visual = False
        saved_visual_line = False
        try:
            prose_view = self.query_one("#prose", PassageView)
            saved_anchor = prose_view.anchor
            saved_visual = prose_view.visual_mode
            saved_visual_line = prose_view.visual_line_mode
        except Exception:
            pass
        try:
            if full:
                self._run_full_curation_derivation()
            else:
                self._run_post_curation_derivation()
        except Exception as exc:
            self._last_curation_error = str(exc)
            self._last_curation_message = None
            self.refresh_all_panels()
            self._scroll_cursor_into_view()
            return
        self._last_curation_error = None
        self.data.reload_from_disk()
        new_cs = self._load_chapter(cn)
        new_cs.cursor_char = saved_cursor
        self._last_curation_message = self._curation_refresh_message(message, cn)
        self.refresh_all_panels()
        try:
            prose_view = self.query_one("#prose", PassageView)
            prose_view.cursor = saved_cursor
            prose_view.anchor = saved_anchor
            prose_view.visual_mode = saved_visual
            prose_view.visual_line_mode = saved_visual_line
            prose_view.refresh()
        except Exception:
            pass
        self._scroll_cursor_into_view()

    def _curation_refresh_message(self, message: str, chapter_num: str) -> str:
        chapters = self.data.chapter_facts.get("chapters") or []
        try:
            current_key = self.data.chapter_sort_key(chapter_num)
        except Exception:
            current_key = None
        stale_later = []
        stale_current = False
        for chapter in chapters:
            model = chapter.get("model_validation") or {}
            has_stale_alignment = any(
                issue.get("code") == "chapter_alignment_stale"
                for issue in model.get("issues") or []
            )
            if not has_stale_alignment:
                continue
            cn = str(chapter.get("chapter_num"))
            if cn == str(chapter_num):
                stale_current = True
                continue
            if current_key is not None:
                try:
                    if self.data.chapter_sort_key(cn) <= current_key:
                        continue
                except Exception:
                    pass
            stale_later.append(cn)
        if stale_later:
            count = len(stale_later)
            noun = "chapter" if count == 1 else "chapters"
            verb = "needs" if count == 1 else "need"
            return f"{message}; alignment warning: {count} later {noun} {verb} review"
        if stale_current:
            return f"{message}; alignment warning: current chapter needs review"
        return message

    def _action_toggle_section_eligibility(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        section_index = cs.section_index_at(cs.cursor_word_index)
        sections = cs.meta.sections or []
        if not (0 <= section_index < len(sections)):
            self._flash("section eligibility: no section at cursor")
            return
        section = sections[section_index]
        now_eligible = self.persistence.toggle_section_eligibility(
            chapter_num,
            int(section_index),
            header=section.get("header"),
            current_counts_for_cp=bool(section.get("counts_for_cp", True)),
        )
        msg = "ENABLED" if now_eligible else "DISABLED"
        self._post_curation_refresh(
            f"ch {chapter_num} sec {section_index} CP eligibility: {msg}",
            full=True,
        )

    def _selected_word_range_for_action(
        self, action_name: str,
    ) -> tuple[int, int, str] | None:
        cs = self.state.chapter
        if cs is None:
            return None
        prose_view = self.query_one("#prose", PassageView)
        sel = prose_view.selection
        if sel is None:
            self._flash(f"{action_name}: no selection - press v or V to select first")
            return None
        lo, hi = sel
        lo, hi = min(lo, hi), max(lo, hi)
        wo = cs.prose.word_offsets
        if not wo:
            self._flash(f"{action_name}: empty chapter")
            return None
        word_start = next((i for i, (_s, e) in enumerate(wo) if e > lo), len(wo))
        word_end = next((i for i, (s, _e) in enumerate(wo) if s >= hi), len(wo))
        if word_end <= word_start:
            self._flash(f"{action_name}: selection covers no whole word")
            return None
        return word_start, word_end, cs.prose.text[lo:hi].strip()

    def _action_mark_span_eligibility(self, chapter_num: str) -> None:
        selected = self._selected_word_range_for_action("eligibility")
        if selected is None:
            return
        word_start, word_end, excerpt = selected

        def on_confirm(
            counts_for_cp: bool,
            reason_code: str,
            note: str | None,
        ) -> None:
            self._save_span_eligibility(
                chapter_num,
                word_start,
                word_end,
                counts_for_cp=counts_for_cp,
                reason_code=reason_code,
                note=note,
                excerpt=excerpt,
            )

        self.push_screen(
            EligibilitySpanModal(
                on_confirm,
                selection_words=word_end - word_start,
            )
        )

    def _save_span_eligibility(
        self,
        chapter_num: str,
        word_start: int,
        word_end: int,
        *,
        counts_for_cp: bool,
        reason_code: str,
        note: str | None = None,
        excerpt: str = "",
    ) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        sections = cs.meta.sections or []
        if not sections:
            self._flash("eligibility: no sections loaded")
            return
        display_excerpt = re.sub(r"\s+", " ", excerpt).strip()
        if len(display_excerpt) > 120:
            display_excerpt = display_excerpt[:117] + "..."
        running = 0
        saved_count = 0
        for section_index, section in enumerate(sections):
            section_start = running
            section_end = running + int(section.get("word_count") or 0)
            running = section_end
            start = max(int(word_start), section_start)
            end = min(int(word_end), section_end)
            if end <= start:
                continue
            self.persistence.mark_span_eligibility(
                chapter_num,
                int(section_index),
                start,
                end,
                counts_for_cp=counts_for_cp,
                reason_code=reason_code,
                note=note,
                excerpt=display_excerpt,
                header=section.get("header"),
                current_counts_for_cp=bool(section.get("counts_for_cp", True)),
            )
            saved_count += 1
        if not saved_count:
            self._flash("eligibility: selection did not overlap a section")
            return
        try:
            prose_view = self.query_one("#prose", PassageView)
            prose_view.anchor = None
            prose_view.visual_mode = False
            prose_view.visual_line_mode = False
            refresh = getattr(prose_view, "refresh", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass
        status = "eligible" if counts_for_cp else "ineligible"
        self._post_curation_refresh(
            (
                f"CP {status} span saved "
                f"({int(word_end) - int(word_start)} words, {reason_code})"
            ),
            full=True,
        )

    def _action_remove_annotations_at_current_word(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        roll_targets = self._roll_evidence_targets_at_selection_or_cursor()
        removed_roll_evidence = 0
        for target_chapter, target_index, quote in roll_targets:
            if self.persistence.remove_roll_evidence_quote_at_index(
                target_chapter,
                target_index,
                quote,
            ):
                removed_roll_evidence += 1
        word_idx = cs.cursor_word_index
        result = self.persistence.remove_annotations_at_word(
            chapter_num,
            word_idx,
        )
        total = (
            result["eligibility_spans"] + removed_roll_evidence
        )
        if not total:
            self._flash("annotation delete: none at current word")
            return
        full = bool(
            result["eligibility_spans"]
        )
        self._post_curation_refresh(
            (
                "annotation delete: "
                f"{result['eligibility_spans']} eligibility, "
                f"{removed_roll_evidence} roll evidence"
            ),
            full=full,
        )

    def _selection_or_cursor_char_range(self) -> tuple[int, int] | None:
        cs = self.state.chapter
        if cs is None:
            return None
        prose_view = self.query_one("#prose", PassageView)
        if prose_view.selection is not None:
            lo, hi = prose_view.selection
            return min(lo, hi), max(lo, hi)
        word_idx = cs.cursor_word_index
        if not (0 <= word_idx < len(cs.prose.word_offsets)):
            return None
        return cs.prose.word_offsets[word_idx]

    def _roll_evidence_targets_at_selection_or_cursor(self) -> list[tuple[str, int, dict]]:
        return [
            (target["target_chapter"], target["target_index"], target["quote"])
            for target in self._roll_evidence_quote_targets_at_selection_or_cursor()
        ]

    def _roll_evidence_quote_targets_at_selection_or_cursor(self) -> list[dict]:
        cs = self.state.chapter
        target_range = self._selection_or_cursor_char_range()
        if cs is None or target_range is None:
            return []
        lo, hi = target_range
        targets: list[dict] = []
        seen: set[tuple[str, int, str, str, str]] = set()
        for roll in self._roll_evidence_picker_rolls(cs):
            target_index = roll.get("target_roll_index")
            if target_index is None:
                continue
            for quote in self._roll_evidence_quotes(roll):
                quote_text = str(quote.get("text") or "")
                start = cs.prose.text.find(quote_text)
                if start >= 0:
                    span = (start, start + len(quote_text))
                else:
                    raw = self._evidence_fallback_word_index(cs, roll)
                    if raw is None or not (0 <= raw < len(cs.prose.word_offsets)):
                        continue
                    span = cs.prose.word_offsets[raw]
                if max(lo, span[0]) >= min(hi, span[1]):
                    continue
                key = (
                    str(roll.get("target_chapter_num") or cs.meta.chapter_num),
                    int(target_index),
                    quote_text,
                    str(quote.get("mention_chapter_num")),
                    str(quote.get("mention_word_position")),
                )
                if key not in seen:
                    seen.add(key)
                    targets.append({
                        "target_chapter": str(
                            roll.get("target_chapter_num") or cs.meta.chapter_num
                        ),
                        "target_index": int(target_index),
                        "quote": quote,
                        "roll": roll,
                    })
        return targets

    def _action_reassign_roll_quote(self, chapter_num: str) -> None:
        sources = self._roll_evidence_quote_targets_at_selection_or_cursor()
        if not sources:
            self._flash("move quote: no saved quote at cursor")
            return

        def choose_target(source: dict) -> None:
            cs = self.state.chapter
            if cs is None:
                return
            rolls: list[dict] = []
            for roll in self._roll_evidence_picker_rolls(cs):
                target_index = roll.get("target_roll_index")
                if target_index is None:
                    continue
                target_chapter = str(
                    roll.get("target_chapter_num") or chapter_num
                )
                if (
                    target_chapter == source["target_chapter"]
                    and int(target_index) == int(source["target_index"])
                ):
                    continue
                rolls.append(roll)
            if not rolls:
                self._flash("move quote: no other roll targets")
                return

            def move_to(target: dict) -> None:
                target_chapter = str(
                    target.get("target_chapter_num") or chapter_num
                )
                target_index = target.get("target_roll_index")
                if target_index is None:
                    self._flash("move quote: invalid target")
                    return
                moved = self.persistence.move_roll_evidence_quote_between_indices(
                    source_chapter_num=source["target_chapter"],
                    source_index=int(source["target_index"]),
                    target_chapter_num=target_chapter,
                    target_index=int(target_index),
                    quote=source["quote"],
                )
                if not moved:
                    self._flash("move quote: saved quote no longer found")
                    return
                self._post_curation_refresh(
                    f"quote moved to ch {target_chapter} #{int(target_index)}"
                )

            self.push_screen(QuoteMoveTargetPicker(rolls=rolls, on_select=move_to))

        if len(sources) == 1:
            choose_target(sources[0])
            return
        self.push_screen(QuoteMoveSourcePicker(
            sources=sources,
            on_select=choose_target,
        ))

    def _actionable_roll_targets(self, cs) -> list[dict]:
        unified = self._unified_rolls(cs)
        return sorted(
            [
                *self._roll_slot_rows(cs, unified),
                *[
                    roll for roll in unified
                    if roll.get("display_kind") == "deferred_in"
                ],
                *self._deferred_predicted_slot_rolls(cs, unified),
            ],
            key=lambda roll: (
                self._roll_action_word_position(cs, roll),
                int(roll.get("target_roll_index") or roll.get("index") or 0),
            ),
        )

    def _roll_action_word_position(self, cs, roll: dict) -> int:
        if roll.get("display_kind") in {"deferred_in", "predicted_slot"}:
            return int(roll.get("word_position") or 0)
        target_chapter = str(roll.get("target_chapter_num") or cs.meta.chapter_num)
        display_chapter = str(roll.get("display_chapter_num") or cs.meta.chapter_num)
        if target_chapter != str(cs.meta.chapter_num) and display_chapter != str(
            cs.meta.chapter_num
        ):
            return int(roll.get("word_position") or 0)
        mechanical_word = (
            roll.get("mechanical_word_position")
            if str(roll.get("mechanical_chapter_num") or target_chapter)
            == str(cs.meta.chapter_num)
            else roll.get("word_position")
        )
        if mechanical_word is None:
            mechanical_word = roll.get("word_position")
        return int(mechanical_word or 0)

    def _default_roll_target(self, *, word_idx: int | None = None) -> dict | None:
        """Action target for the mechanical roll at or before the cursor.

        This is the "target" roll for `<space>h/m/c/p/q` actions. If
        the cursor is before the first predicted roll, returns None.
        """
        cs = self.state.chapter
        if cs is None:
            return None
        cp_word_idx = self._cp_earning_word_offset(
            cs.cursor_word_index if word_idx is None else word_idx
        )
        target: dict | None = None
        for roll in self._actionable_roll_targets(cs):
            if roll.get("display_kind") == "deferred_in":
                if int(roll.get("word_position") or 0) <= cp_word_idx:
                    target = roll
                continue
            if roll.get("display_kind") == "predicted_slot":
                if int(roll.get("word_position") or 0) <= cp_word_idx:
                    target = roll
                else:
                    break
                continue
            target_chapter = str(roll.get("target_chapter_num") or cs.meta.chapter_num)
            display_chapter = str(roll.get("display_chapter_num") or cs.meta.chapter_num)
            if target_chapter != str(cs.meta.chapter_num) and display_chapter != str(
                cs.meta.chapter_num
            ):
                continue
            if self._roll_action_word_position(cs, roll) <= cp_word_idx:
                target = roll
            else:
                break
        return target

    def _current_roll_target(self, *, word_idx: int | None = None) -> dict | None:
        selected = self._selected_roll_target_if_visible()
        if selected is not None:
            return selected
        return self._default_roll_target(word_idx=word_idx)

    def _current_roll_evidence_target(
        self, *, word_idx: int | None = None,
    ) -> dict | None:
        """Normal quote evidence target; skipped slots are not evidence rows."""
        selected = self._selected_roll_target_if_visible()
        if selected is not None and not (
            selected.get("display_kind") == "predicted_slot"
            and selected.get("skipped")
        ):
            return selected
        cs = self.state.chapter
        if cs is None:
            return None
        cp_word_idx = self._cp_earning_word_offset(
            cs.cursor_word_index if word_idx is None else word_idx
        )
        target: dict | None = None
        for roll in self._roll_evidence_picker_rolls(cs):
            if roll.get("display_kind") == "deferred_in":
                if int(roll.get("word_position") or 0) <= cp_word_idx:
                    target = roll
                continue
            if roll.get("display_kind") == "predicted_slot":
                if int(roll.get("word_position") or 0) <= cp_word_idx:
                    target = roll
                else:
                    break
                continue
            target_chapter = str(roll.get("target_chapter_num") or cs.meta.chapter_num)
            display_chapter = str(roll.get("display_chapter_num") or cs.meta.chapter_num)
            if target_chapter != str(cs.meta.chapter_num) and display_chapter != str(
                cs.meta.chapter_num
            ):
                continue
            display_raw = self._roll_display_raw_word_index(cs.meta.chapter_num, roll)
            mechanical_word = (
                self._cp_earning_word_offset(display_raw)
                if display_raw is not None
                else (
                    roll.get("word_position")
                    if display_chapter == str(cs.meta.chapter_num)
                    else roll.get("mechanical_word_position")
                )
            )
            if mechanical_word is None:
                mechanical_word = roll.get("word_position")
            if int(mechanical_word) <= cp_word_idx:
                target = roll
            else:
                break
        return target

    def _current_roll_index(self) -> int | None:
        target = self._current_roll_target()
        if target is None:
            return None
        return target.get("target_roll_index") or target.get("index")

    def _action_set_last_outcome(self, chapter_num: str, outcome: str) -> None:
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash(
                "no predicted roll at/before cursor — move past a roll position first"
            )
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        self.persistence.update_roll_at_index(
            target_chapter, idx, outcome=outcome,
        )
        self._post_curation_refresh(f"roll #{idx} = {outcome}")

    def _action_mark_predicted_roll_skipped(self, chapter_num: str) -> None:
        target = self._current_roll_target()
        if (
            target is None
            or target.get("target_roll_index") is None
        ):
            self._flash("skip roll: select a predicted or assigned roll slot first")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        self.persistence.mark_roll_skipped(target_chapter, idx)
        self._post_curation_refresh(f"roll #{idx} skipped")

    def _action_pick_constellation(self, chapter_num: str) -> None:
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash("no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])

        def on_pick(name: str) -> None:
            self.persistence.update_roll_at_index(
                target_chapter, idx, constellation=name,
            )
            self._post_curation_refresh(f"roll #{idx} constellation = {name}")
        self.push_screen(ConstellationPicker(on_select=on_pick))

    def _action_pick_perks(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash("no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        perks = list(cs.derived.perks)
        if not perks:
            self._flash("no perks recorded for this chapter")
            return

        def on_confirm(names: list[str]) -> None:
            self.persistence.update_roll_at_index(
                target_chapter, idx, perks=names,
            )
            self._post_curation_refresh(
                f"roll #{idx} perks: {', '.join(names) or '(none)'}"
            )
        self.push_screen(PerkPicker(perks=perks, on_confirm=on_confirm))

    def _source_roll_picker_rows(self, chapter_num: str) -> list[dict]:
        rows = [
            roll for roll in self.data.roll_facts.get("rolls", [])
            if str(roll.get("chapter_num")) == str(chapter_num)
            and roll.get("source_kind") != "trigger"
            and roll.get("roll_number") is not None
        ]
        rows.extend(self._deferred_source_roll_rows(chapter_num))
        rows.extend(self._obtained_perk_source_rows(chapter_num, rows))
        rows.sort(key=lambda roll: (
            0 if roll.get("source_deferred_from_chapter") is not None else 1,
            1 if roll.get("source_kind") == "obtained_perk" else 0,
            int(roll.get("roll_number") or 0),
            int(roll.get("source_row_index") or 0),
            str(roll.get("rolled_perk_name") or ""),
        ))
        unique: list[dict] = []
        seen: set[int] = set()
        for roll in rows:
            if roll.get("source_kind") == "obtained_perk":
                unique.append(roll)
                continue
            roll_number = int(roll["roll_number"])
            if roll_number in seen:
                continue
            seen.add(roll_number)
            unique.append(roll)
        return unique

    def _obtained_perk_source_rows(
        self, chapter_num: str, source_rows: list[dict],
    ) -> list[dict]:
        cn = str(chapter_num)
        source_hit_names = {
            str(roll.get("rolled_perk_name") or "").strip().lower()
            for roll in source_rows
            if roll.get("outcome") == "hit"
            and str(roll.get("rolled_perk_name") or "").strip()
        }
        rows: list[dict] = []
        for perk in self.data.obtained_perks.get("perks", []):
            if str(perk.get("chapter_num")) != cn:
                continue
            if perk.get("free"):
                continue
            name = str(perk.get("perk_name") or perk.get("name") or "").strip()
            if not name or name.lower() in source_hit_names:
                continue
            cost = int(perk.get("cost") or 0)
            constellation = perk.get("constellation")
            rows.append({
                "source": "obtained_perks",
                "source_kind": "obtained_perk",
                "outcome": "hit",
                "roll_number": None,
                "chapter_num": cn,
                "rolled_perk_name": name,
                "rolled_perk_cost": cost,
                "constellation": constellation,
                "purchased_perks": [
                    {"name": name, "cost": cost, "free": False}
                ],
                "purchased_perk_cost_total": cost,
                "purchased_perk_jump": perk.get("jump"),
                "raw": (
                    f"Obtained perk: {constellation or 'unknown'} - {name} "
                    f"({perk.get('jump') or 'unknown'})"
                ),
            })
        return rows

    def _deferred_source_roll_rows(self, chapter_num: str) -> list[dict]:
        rows: list[dict] = []
        overrides = (
            self.persistence.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
        )
        for source_chapter, entry in overrides.items():
            if str(source_chapter) == str(chapter_num):
                continue
            for idx, override in enumerate(entry.get("rolls") or [], start=1):
                if not isinstance(override, dict):
                    continue
                if str(override.get("source_deferred_to_chapter") or "") != str(chapter_num):
                    continue
                source = None
                source_roll_number = override.get("source_roll_number")
                if source_roll_number is not None:
                    source = self._roll_fact_for_roll_number(source_roll_number)
                if source is None:
                    source = next(
                        (
                            roll for roll in self.data.roll_facts.get("rolls", [])
                            if str(roll.get("chapter_num")) == str(source_chapter)
                            and int(roll.get("roll_sequence_in_chapter") or 0) == idx
                            and roll.get("roll_number") is not None
                        ),
                        None,
                    )
                if source is None:
                    source = next(
                        (
                            roll for roll in self.data.roll_facts.get("rolls", [])
                            if str(roll.get("source_chapter_num")) == str(source_chapter)
                            and int(roll.get("source_roll_index") or 0) == idx
                            and roll.get("roll_number") is not None
                        ),
                        None,
                    )
                if source is None:
                    continue
                row = dict(source)
                row["source_deferred_from_chapter"] = str(source_chapter)
                row["source_deferred_from_index"] = idx
                rows.append(row)
        return rows

    def _source_assignment_target_rows(self, cs) -> list[dict]:
        unified = self._unified_rolls(cs)
        rows = [
            *[
                roll for roll in unified
                if roll.get("display_kind") in {"deferred_in", "source_deferred"}
            ],
            *self._deferred_predicted_slot_rolls(cs, unified),
            *self._roll_slot_rows(cs, unified),
        ]
        out: list[dict] = []
        seen: set[tuple] = set()
        for roll in rows:
            if roll.get("target_roll_index") is None:
                continue
            key = self._roll_target_key(roll)
            if key is None or key in seen:
                continue
            seen.add(key)
            out.append(roll)
        return sorted(
            out,
            key=lambda roll: (
                0 if roll.get("display_kind") == "deferred_in" else 1,
                self._chapter_sort_key(str(
                    roll.get("target_chapter_num")
                    or roll.get("mechanical_chapter_num")
                    or cs.meta.chapter_num
                )),
                int(roll.get("target_roll_index") or roll.get("index") or 0),
            ),
        )

    def _source_link_rows(self, cs, chapter_num: str) -> list[dict]:
        rows = [
            *self._source_assignment_target_rows(cs),
            *self._deferred_source_roll_rows(chapter_num),
            *self._source_roll_picker_rows(chapter_num),
        ]
        out: list[dict] = []
        seen: set[tuple] = set()
        for roll in rows:
            key = (
                str(roll.get("source_deferred_from_chapter") or ""),
                int(roll.get("source_deferred_from_index") or 0),
                str(
                    roll.get("target_chapter_num")
                    or roll.get("mechanical_chapter_num")
                    or roll.get("chapter_num")
                    or ""
                ),
                int(roll.get("target_roll_index") or roll.get("index") or 0),
                int(roll.get("roll_number") or 0),
                str(roll.get("display_kind") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(roll)
        return out

    @staticmethod
    def _is_source_link_source(roll: dict) -> bool:
        if roll.get("display_kind") == "source_deferred":
            return False
        return (
            roll.get("source_deferred_from_chapter") is not None
            or (
                roll.get("roll_number") is not None
                and (
                    roll.get("source_kind") in {"roll", "miss"}
                    or bool(str(roll.get("raw") or "").strip())
                )
            )
            or roll.get("source_kind") == "obtained_perk"
        )

    @staticmethod
    def _is_source_link_target(roll: dict) -> bool:
        return roll.get("target_roll_index") is not None

    def _normalize_source_link_pair(
        self, left: dict, right: dict,
    ) -> tuple[dict, dict] | None:
        left_source = self._is_source_link_source(left)
        right_source = self._is_source_link_source(right)
        left_target = self._is_source_link_target(left)
        right_target = self._is_source_link_target(right)
        if left.get("source_deferred_from_chapter") is not None and right_target:
            return right, left
        if right.get("source_deferred_from_chapter") is not None and left_target:
            return left, right
        if left_target and right_source and not left_source:
            return left, right
        if right_target and left_source and not right_source:
            return right, left
        if left.get("display_kind") == "deferred_in" and right_source:
            return left, right
        if right.get("display_kind") == "deferred_in" and left_source:
            return right, left
        return None

    def _canonical_source_assignment_target(
        self, target: dict, source_roll: dict, targets: list[dict],
    ) -> dict:
        if (
            target.get("display_kind") != "deferred_in"
            or not target.get("deferred_to_later_chapter")
            or source_roll.get("roll_number") is None
        ):
            return target
        source_roll_number = int(source_roll["roll_number"])
        for candidate in targets:
            if candidate is target:
                continue
            if candidate.get("display_kind") != "deferred_in":
                continue
            if candidate.get("deferred_to_later_chapter"):
                continue
            if int(candidate.get("roll_number") or 0) == source_roll_number:
                return candidate
        return target

    def _action_assign_source_roll(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        targets = self._source_assignment_target_rows(cs)
        if not targets:
            self._flash("assign source: no roll slots in this chapter")
            return
        sources = self._source_roll_picker_rows(chapter_num)
        if not sources:
            self._flash("assign source: no source rolls in this chapter")
            return

        def assign_source_to_target(left: dict, right: dict) -> None:
            pair = self._normalize_source_link_pair(left, right)
            if pair is None:
                self._flash("assign source: choose one target slot and one source roll")
                return
            target, source_roll = pair
            target = self._canonical_source_assignment_target(
                target, source_roll, targets,
            )
            target_chapter = str(target.get("target_chapter_num") or chapter_num)
            idx = int(target["target_roll_index"])
            if source_roll.get("source_kind") == "obtained_perk":
                perk_name = str(source_roll.get("rolled_perk_name") or "")
                self.persistence.assign_obtained_perk_at_index(
                    target_chapter,
                    idx,
                    perk_name=perk_name,
                    constellation=source_roll.get("constellation"),
                )
                self._post_curation_refresh(
                    f"ch {target_chapter} roll #{idx} source = {perk_name}"
                )
                return
            source_roll_number = int(source_roll["roll_number"])
            should_shift_quotes = (
                target.get("display_kind") == "deferred_in"
                and str(target_chapter) != str(chapter_num)
                and str(source_roll.get("chapter_num") or "") == str(chapter_num)
                and source_roll.get("source_roll_index") is not None
            )
            result = self.persistence.assign_source_roll_with_evidence_at_index(
                target_chapter_num=target_chapter,
                target_index=idx,
                source_roll_number=source_roll_number,
                copied_quotes=list(source_roll.get("evidence_quotes") or []),
                mention_chapter_num=(
                    chapter_num
                    if target.get("deferred_to_later_chapter") or should_shift_quotes
                    else None
                ),
                display_position_policy=(
                    "mechanical"
                    if target.get("deferred_to_later_chapter") or should_shift_quotes
                    else None
                ),
                shift_source_chapter_num=(
                    chapter_num if should_shift_quotes else None
                ),
                shift_source_index=(
                    int(source_roll["source_roll_index"])
                    if should_shift_quotes else None
                ),
            )
            if result == "target_has_evidence":
                self._flash("assign source: deferred target already has quote evidence")
            self._post_curation_refresh(
                f"ch {target_chapter} roll #{idx} source = Roll {source_roll_number}"
            )

        self.push_screen(SourceLinkPicker(
            targets,
            sources,
            on_confirm=assign_source_to_target,
        ))

    def _action_save_quote(self, chapter_num: str) -> None:
        quote = self._selected_quote("save quote")
        if quote is None:
            return
        target_word = self._selected_quote_start_word_index()
        target = self._current_roll_evidence_target(word_idx=target_word)
        if target is None or target.get("target_roll_index") is None:
            self._flash("save quote: no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        mention_word = self._cp_earning_word_offset(target_word or 0)
        self.persistence.append_roll_evidence_at_index(
            target_chapter,
            idx,
            text=quote,
            mention_chapter_num=chapter_num,
            mention_word_position=mention_word,
        )
        self._clear_prose_selection()
        self._post_curation_refresh(f"roll #{idx} quote saved ({len(quote)} chars)")

    def _clear_prose_selection(self) -> None:
        try:
            prose_view = self.query_one("#prose", PassageView)
        except Exception:
            return
        prose_view.anchor = None
        prose_view.visual_mode = False
        prose_view.visual_line_mode = False
        refresh = getattr(prose_view, "refresh", None)
        if callable(refresh):
            refresh()

    def _selected_quote_start_word_index(self) -> int | None:
        cs = self.state.chapter
        if cs is None:
            return None
        prose_view = self.query_one("#prose", PassageView)
        sel = prose_view.selection
        if sel is None:
            return cs.cursor_word_index
        lo, _hi = sel
        return _word_index_for_char_offset(cs.prose.word_offsets, lo)

    def _action_save_quote_multi(self, chapter_num: str) -> None:
        quote = self._selected_quote("save quote")
        if quote is None:
            return
        cs = self.state.chapter
        if cs is None:
            return
        target_word = self._selected_quote_start_word_index()
        mention_word = self._cp_earning_word_offset(target_word or 0)
        rolls = self._roll_evidence_picker_rolls(cs)
        if not rolls:
            self._flash("save quote: no rolls in this chapter")
            return
        self._clear_prose_selection()

        def on_confirm(
            indices: list[int],
            display_position_policy: str | None,
        ) -> None:
            if not indices:
                self._flash("save quote: no rolls selected")
                return
            by_chapter: dict[str, list[int]] = {}
            target_labels: list[str] = []
            for index in indices:
                if 1 <= index <= len(rolls):
                    target_roll = rolls[index - 1]
                    target_chapter = str(
                        target_roll.get("target_chapter_num") or chapter_num
                    )
                    target_index = target_roll.get("target_roll_index")
                    if target_index is not None:
                        by_chapter.setdefault(target_chapter, []).append(int(target_index))
                        label = self._roll_target_message_label(target_roll)
                        if label not in target_labels:
                            target_labels.append(label)
            for target_chapter, target_indices in by_chapter.items():
                self.persistence.append_roll_evidence_at_indices(
                    target_chapter,
                    target_indices,
                    text=quote,
                    mention_chapter_num=chapter_num,
                    mention_word_position=mention_word,
                    display_position_policy=display_position_policy,
                )
            self._post_curation_refresh(
                f"quote saved to rolls {', '.join(target_labels)}"
            )

        self.push_screen(RollEvidencePicker(rolls=rolls, on_confirm=on_confirm))

    @staticmethod
    def _roll_target_message_label(roll: dict) -> str:
        target_chapter = (
            roll.get("target_chapter_num")
            or roll.get("mechanical_chapter_num")
            or roll.get("visible_chapter_num")
            or roll.get("chapter_num")
            or "?"
        )
        target_index = roll.get("target_roll_index") or roll.get("index")
        if target_index is not None:
            return f"ch {target_chapter} #{int(target_index)}"
        return f"ch {target_chapter} #?"

    def _source_roll_number_for_chapter_source_index(
        self, chapter_num: str, source_index: int,
    ) -> int | None:
        for roll in self.data.roll_facts.get("rolls", []):
            if (
                str(roll.get("source_chapter_num")) == str(chapter_num)
                and int(roll.get("source_roll_index") or 0) == int(source_index)
                and roll.get("roll_number") is not None
            ):
                return int(roll["roll_number"])
        for roll in self.data.roll_facts.get("rolls", []):
            if (
                str(roll.get("chapter_num")) == str(chapter_num)
                and int(roll.get("roll_sequence_in_chapter") or 0) == int(source_index)
                and roll.get("roll_number") is not None
            ):
                return int(roll["roll_number"])
        return None

    def _chapter_curation_delete_candidates(
        self, chapter_num: str,
    ) -> list[CurationDeleteCandidate]:
        overrides = (
            self.persistence.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
        )
        candidates: list[CurationDeleteCandidate] = []
        seen: set[tuple] = set()
        related_source_rolls: set[int] = set()

        def add(label: str, item: dict) -> None:
            key = tuple(sorted(item.items()))
            if key in seen:
                return
            seen.add(key)
            candidates.append(CurationDeleteCandidate(label=label, item=item))

        def add_roll_candidates(chapter: str, idx: int, roll: dict, *, related: bool) -> None:
            prefix = f"ch {chapter} roll #{idx}"
            rel = "related " if related else ""
            if roll.get("source_deferred_to_chapter") is not None:
                add(
                    f"{rel}{prefix}: source deferred to ch {roll.get('source_deferred_to_chapter')}",
                    {
                        "kind": "source_deferral",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
                source_roll = self._source_roll_number_for_chapter_source_index(
                    str(chapter), idx,
                )
                if source_roll is not None:
                    related_source_rolls.add(source_roll)
            if roll.get("source_roll_number") is not None:
                add(
                    f"{rel}{prefix}: source = Roll {roll.get('source_roll_number')}",
                    {
                        "kind": "source_assignment",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            if roll.get("outcome") is not None:
                add(
                    f"{rel}{prefix}: outcome = {roll.get('outcome')}",
                    {
                        "kind": "outcome",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            if roll.get("constellation") is not None:
                add(
                    f"{rel}{prefix}: constellation = {roll.get('constellation')}",
                    {
                        "kind": "constellation",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            if roll.get("perks"):
                add(
                    f"{rel}{prefix}: perks override ({len(roll.get('perks') or [])})",
                    {
                        "kind": "perks",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            if roll.get("skipped"):
                add(
                    f"{rel}{prefix}: skipped",
                    {
                        "kind": "skipped",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            roll_deferral = (
                roll.get("deferred_to_later_chapter")
                or roll.get("mention_chapter_num") is not None
                or roll.get("mention_word_position") is not None
                or roll.get("display_position_policy") is not None
            )
            if roll_deferral:
                add(
                    f"{rel}{prefix}: roll deferral/display position override",
                    {
                        "kind": "roll_deferral",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                    },
                )
            for quote_index, quote in enumerate(roll.get("evidence_quotes") or []):
                text = str(quote.get("text") or "").strip()
                snippet = text[:54] + ("..." if len(text) > 54 else "")
                add(
                    f"{rel}{prefix}: quote {quote_index + 1} {snippet!r}",
                    {
                        "kind": "evidence_quote",
                        "chapter_num": str(chapter),
                        "roll_index": int(idx),
                        "quote_index": int(quote_index),
                    },
                )

        current_entry = overrides.get(str(chapter_num), {})
        for idx, roll in enumerate(current_entry.get("rolls") or [], start=1):
            if isinstance(roll, dict):
                add_roll_candidates(str(chapter_num), idx, roll, related=False)
        if current_entry.get("model_validation_resolution") is not None:
            add(
                f"ch {chapter_num}: model validation resolution",
                {
                    "kind": "model_validation_resolution",
                    "chapter_num": str(chapter_num),
                },
            )
        classifications = (
            self.persistence.section_classifications
            .get("classifications", {})
        )
        for section_key, entry in sorted(classifications.items()):
            if str(entry.get("chapter_num")) != str(chapter_num):
                continue
            section_index = int(entry.get("section_index") or 0)
            reason = str(entry.get("reason") or "")
            if reason.startswith("curator toggle:"):
                status = "eligible" if bool(entry.get("counts_for_cp", True)) else "ineligible"
                add(
                    f"ch {chapter_num} sec {section_index}: section eligibility = {status}",
                    {
                        "kind": "section_eligibility",
                        "chapter_num": str(chapter_num),
                        "section_key": str(section_key),
                    },
                )
            for span_index, span in enumerate(entry.get("span_overrides") or []):
                if str(span.get("reason_code") or "") == "section_header":
                    continue
                status = "eligible" if bool(span.get("counts_for_cp")) else "ineligible"
                start = int(span.get("word_offset_start") or 0)
                end = int(span.get("word_offset_end") or 0)
                reason_code = str(span.get("reason_code") or "span")
                add(
                    (
                        f"ch {chapter_num} sec {section_index}: eligibility span "
                        f"{start}-{end} {status} ({reason_code})"
                    ),
                    {
                        "kind": "eligibility_span",
                        "chapter_num": str(chapter_num),
                        "section_key": str(section_key),
                        "span_index": int(span_index),
                    },
                )

        for related_chapter, entry in overrides.items():
            if str(related_chapter) == str(chapter_num):
                continue
            for idx, roll in enumerate(entry.get("rolls") or [], start=1):
                if not isinstance(roll, dict):
                    continue
                if (
                    roll.get("source_roll_number") is not None
                    and int(roll["source_roll_number"]) in related_source_rolls
                ):
                    add_roll_candidates(str(related_chapter), idx, roll, related=True)
        return candidates

    def _action_delete_chapter_curation_data(self, chapter_num: str) -> None:
        candidates = self._chapter_curation_delete_candidates(chapter_num)
        if not candidates:
            self._flash("delete curation: no persisted curation data for chapter")
            return

        def on_confirm(items: list[dict]) -> None:
            if not items:
                self._flash("delete curation: nothing selected")
                return
            deleted = self.persistence.delete_chapter_curation_items(items)
            if not deleted:
                self._flash("delete curation: selected records already clear")
                return
            needs_full_refresh = any(
                item.get("kind") in {"section_eligibility", "eligibility_span"}
                for item in items
            )
            self._post_curation_refresh(
                f"deleted {deleted} curation records",
                full=needs_full_refresh,
            )

        self.push_screen(ChapterCurationDeletePicker(candidates, on_confirm=on_confirm))

    def _action_pick_roll_visualization_position(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash("roll position: no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        cursor_word = self._cp_earning_word_offset(cs.cursor_word_index)

        def on_select(payload: dict) -> None:
            self.persistence.set_roll_visualization_anchor(
                target_chapter,
                idx,
                mention_chapter_num=payload["mention_chapter_num"],
                mention_word_position=payload["mention_word_position"],
                display_position_policy=payload["display_position_policy"],
            )
            self._post_curation_refresh(f"roll #{idx} visualization position saved")

        self.push_screen(
            RollVisualizationPicker(
                roll=target,
                cursor_chapter_num=chapter_num,
                cursor_word_position=cursor_word,
                on_select=on_select,
            )
        )

    def _action_anchor_roll_without_quote(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash("anchor roll: no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        mention_word = cs.cursor_word_index
        self.persistence.update_roll_at_index(
            target_chapter,
            idx,
            mention_chapter_num=chapter_num,
            mention_word_position=mention_word,
            display_position_policy="source_marker",
            curator_note="source-only roll anchor",
        )
        self._post_curation_refresh(f"roll #{idx} source anchor saved")

    def _next_chapter_num(self, chapter_num: str) -> str | None:
        order = self.data.chapter_order
        try:
            idx = order.index(str(chapter_num))
        except ValueError:
            return None
        if idx + 1 >= len(order):
            return None
        return order[idx + 1]

    def _action_defer_roll_to_next_chapter(self, chapter_num: str) -> None:
        target = self._current_roll_target()
        if target is None or target.get("target_roll_index") is None:
            self._flash("defer evidence: no predicted roll at/before cursor")
            return
        idx = int(target["target_roll_index"])
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        persisted_rolls = (
            self.persistence.chapter_roll_overrides
            .get("chapter_roll_overrides", {})
            .get(target_chapter, {})
            .get("rolls", [])
        )
        persisted_roll = (
            persisted_rolls[idx - 1]
            if 0 <= idx - 1 < len(persisted_rolls)
            and isinstance(persisted_rolls[idx - 1], dict)
            else {}
        )
        persisted_source_deferred_to = persisted_roll.get("source_deferred_to_chapter")
        persisted_mention_chapter = persisted_roll.get("mention_chapter_num")
        persisted_later_deferral = bool(persisted_roll.get("deferred_to_later_chapter"))
        if (
            target.get("display_kind") == "deferred_in"
            or persisted_later_deferral
            or (
                persisted_mention_chapter is not None
                and str(persisted_mention_chapter) != str(target_chapter)
            )
        ):
            self.persistence.clear_roll_deferral(target_chapter, idx)
            self._post_curation_refresh(f"roll #{idx} evidence deferral cleared")
            return
        if persisted_source_deferred_to is not None:
            self.persistence.clear_source_roll_deferral(target_chapter, idx)
            self._post_curation_refresh(f"roll #{idx} source deferral cleared")
            return
        if (
            target.get("roll_number") is not None
            and target.get("source_kind") in {"roll", "miss"}
        ):
            next_chapter = self._next_chapter_num(chapter_num)
            if next_chapter is None:
                self._flash("defer evidence: no next chapter")
                return
            self.persistence.mark_source_roll_deferred_to_chapter(
                target_chapter,
                idx,
                next_chapter,
            )
            message = (
                f"roll #{idx} source Roll {target.get('roll_number')} "
                f"deferred to ch {next_chapter}"
            )
        else:
            self.persistence.mark_roll_deferred_to_later_chapter(
                target_chapter,
                idx,
                display_position_policy="mechanical",
            )
            message = f"roll #{idx} evidence deferred to later chapter"
        self._post_curation_refresh(message)

    def _action_resolve_model_discrepancy(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        model = (cs.derived.chapter_facts or {}).get("model_validation") or {}
        blocking_codes = {
            "paid_rolls_exceed_predicted_slots",
            "known_attempts_exceed_predicted_slots",
            "cost_schedule_infeasible",
        }
        issues = model.get("issues") or []
        unresolved = [
            str(issue.get("code"))
            for issue in issues
            if (
                str(issue.get("code")) in blocking_codes
                and not issue.get("resolved")
            )
        ]
        if not unresolved:
            self._flash("resolve discrepancy: no unresolved model discrepancy here")
            return
        for code in dict.fromkeys(unresolved):
            self.persistence.resolve_model_validation_issue(
                chapter_num,
                issue_code=code,
                reason_code=self._resolution_reason_code(code),
                note=self._resolution_note(chapter_num, code, model),
            )
        self._post_curation_refresh("model discrepancy resolved")

    def _action_rebuild_derived_data(self, chapter_num: str) -> None:
        self._post_curation_refresh("full curation rebuild complete", full=True)

    @staticmethod
    def _resolution_reason_code(issue_code: str) -> str:
        if issue_code == "known_attempts_exceed_predicted_slots":
            return "curator_confirmed_extra_attempt"
        if issue_code == "paid_rolls_exceed_predicted_slots":
            return "curator_confirmed_extra_paid_roll"
        if issue_code == "cost_schedule_infeasible":
            return "curator_confirmed_schedule_exception"
        return "curator_confirmed_model_exception"

    @staticmethod
    def _resolution_note(chapter_num: str, issue_code: str, model: dict) -> str:
        predicted = model.get("predicted_roll_count")
        known = model.get("known_attempt_count")
        paid = model.get("required_paid_roll_count")
        if issue_code == "known_attempts_exceed_predicted_slots":
            return (
                f"Curator confirmed chapter {chapter_num} has {known} known "
                f"attempts despite {predicted} predicted model slots."
            )
        if issue_code == "paid_rolls_exceed_predicted_slots":
            return (
                f"Curator confirmed chapter {chapter_num} has {paid} paid "
                f"roll units despite {predicted} predicted model slots."
            )
        if issue_code == "cost_schedule_infeasible":
            return (
                f"Curator confirmed chapter {chapter_num} is an intentional "
                "exception to the modeled CP schedule."
            )
        return f"Curator confirmed chapter {chapter_num} model exception."

    def _selected_quote(self, action_name: str) -> str | None:
        prose_view = self.query_one("#prose", PassageView)
        sel = prose_view.selection
        if sel is None:
            self._flash(f"{action_name}: no selection — press v or V to select first")
            return None
        lo, hi = sel
        cs = self.state.chapter
        if cs is None:
            return None
        quote = cs.prose.text[lo:hi].strip()
        if not quote:
            self._flash(f"{action_name}: empty selection")
            return None
        return quote

    def _action_insert_roll(self, chapter_num: str) -> None:
        # Insert/delete are no-ops in the canonical model: roll
        # positions come from the simulator, not the curator. To change
        # what fires, mark prose ineligible (or change regime); the
        # simulator's prediction will adjust.
        self._flash(
            "insert roll: not used — predictions come from simulator. "
            "Mark text ineligible or curate regime to influence positions."
        )

    def _action_delete_last_roll(self, chapter_num: str) -> None:
        self._flash(
            "delete roll: not used — predictions come from simulator. "
            "Mark text ineligible or curate regime to influence positions."
        )

    def _handle_chord(self, prefix: str, key: str | None) -> bool:
        if key is None:
            return False
        cs = self.state.chapter
        if cs is None:
            return False
        # ]] / [[  — next/previous chapter, landing at chapter edge
        if key == prefix:
            self._jump_chapter(forward=(prefix == "]"))
            return True
        # ][ / []  — section
        if (prefix == "]" and key == "[") or (prefix == "[" and key == "]"):
            self._jump_section(forward=(prefix == "]"))
            return True
        if key == "r":
            self._jump_roll_curated(forward=(prefix == "]"))
            return True
        if key == "R":
            self._jump_roll_predicted(forward=(prefix == "]"))
            return True
        if key == "q":
            self._jump_roll_quoted(forward=(prefix == "]"))
            return True
        return False

    def _handle_star_search(self) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        wi = cs.cursor_word_index
        if not (0 <= wi < len(cs.prose.word_offsets)):
            return
        s, e = cs.prose.word_offsets[wi]
        word = cs.prose.text[s:e]
        # Strip surrounding punctuation; build a word-bounded regex.
        m = re.search(r"\w+", word)
        if not m:
            return
        pattern = rf"\b{re.escape(m.group(0))}\b"
        self._set_active_regex_slot(3)
        inp = self.query_one("#regex_4", Input)
        inp.value = pattern
        self.state.set_regex(3, pattern)
        # Jump to the next match after cursor.
        self._jump_regex(3, forward=True)
        self.refresh_all_panels()

    def _handle_n_search(self, *, forward: bool) -> None:
        self._jump_evidence_candidate(forward=forward)

    def _handle_star_regex_search(self, *, forward: bool) -> None:
        self._jump_regex(3, forward=forward)

    def _handle_article_motion(self, *, forward: bool) -> None:
        self._jump_article_word(forward=forward)

    def _handle_constellation_name_motion(self) -> None:
        self._jump_constellation_name_end()

    def _handle_connection_word_motion(self) -> None:
        self._jump_connection_word_end()

    # ----- jump navigation -----

    def _jump_chapter(self, *, forward: bool) -> None:
        next_chapter = (
            self.state.next_chapter() if forward else self.state.prev_chapter()
        )
        if next_chapter is None:
            return
        self._load_chapter(next_chapter)
        cs = self.state.chapter
        if cs is None or not cs.prose.word_offsets:
            self.refresh_all_panels()
            return
        target = 0 if forward else len(cs.prose.word_offsets) - 1
        self._jump_to_word(target)

    def _jump_to_word(self, word_idx: int) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        char = self.state.char_at_word_index(word_idx)
        self._jump_to_char(char)

    def _jump_to_char(self, char: int) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        char = max(0, min(int(char), len(cs.prose.text)))
        cs.cursor_char = char
        prose_view = self.query_one("#prose", PassageView)
        saved_anchor = prose_view.anchor
        saved_visual = prose_view.visual_mode
        saved_visual_line = prose_view.visual_line_mode
        prose_view.cursor = char
        prose_view.focus()
        self.refresh_all_panels()
        if saved_visual or saved_visual_line:
            prose_view = self.query_one("#prose", PassageView)
            prose_view.cursor = char
            prose_view.anchor = saved_anchor
            prose_view.visual_mode = saved_visual
            prose_view.visual_line_mode = saved_visual_line
            prose_view.refresh()
        self._scroll_cursor_into_view()

    def _jump_article_word(self, *, forward: bool) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        cur = cs.cursor_word_index
        article_words: list[int] = []
        for idx, (start, end) in enumerate(cs.prose.word_offsets):
            normalized = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", cs.prose.text[start:end])
            if normalized.lower() in {"a", "the"}:
                article_words.append(idx)
        if not article_words:
            self._flash("no a/the words in this chapter")
            return
        candidates = [
            idx for idx in article_words
            if (idx > cur if forward else idx < cur)
        ]
        if not candidates:
            candidates = article_words
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_constellation_name_end(self) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        cur_char = cs.cursor_char
        matches = [
            end - 1
            for _start, end in self._constellation_name_char_spans(cs)
            if end - 1 > cur_char
        ]
        if not matches:
            self._flash("no next constellation name in this chapter")
            return
        self._jump_to_char(min(matches))

    def _jump_connection_word_end(self) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        cur_char = cs.cursor_char
        matches: list[int] = []
        for start, _end in cs.prose.word_offsets:
            token = cs.prose.text[start:_end]
            for match in re.finditer(r"[A-Za-z]+", token):
                if match.group(0).lower() in {"connection", "constellation"}:
                    target = start + match.end() - 1
                    if target > cur_char:
                        matches.append(target)
                    break
        if not matches:
            self._flash("no next connection/constellation in this chapter")
            return
        self._jump_to_char(min(matches))

    def _jump_section(self, *, forward: bool) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        cur_wi = cs.cursor_word_index
        breaks = cs.prose.section_break_word_indices
        candidates = [b for b in breaks if (b > cur_wi if forward else b < cur_wi)]
        if not candidates:
            return
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_roll_predicted(self, *, forward: bool) -> None:
        """Jump to next/prev predicted roll position."""
        cs = self.state.chapter
        if cs is None:
            return
        cur_wi = cs.cursor_word_index
        positions = self._predicted_roll_word_indices(cs)
        positions.sort()
        candidates = [p for p in positions if (p > cur_wi if forward else p < cur_wi)]
        if not candidates:
            self._flash("no further predicted roll in this chapter")
            return
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_roll_curated(self, *, forward: bool) -> None:
        """Jump to next/prev curated hit/miss display position."""
        cs = self.state.chapter
        if cs is None:
            return
        cur_wi = cs.cursor_word_index
        positions = [
            raw
            for r in self._unified_rolls(cs)
            if r.get("outcome") in ("hit", "miss")
            for raw in [self._curated_roll_word_index(cs, r)]
            if raw is not None
        ]
        positions = sorted(set(positions))
        candidates = [p for p in positions if (p > cur_wi if forward else p < cur_wi)]
        if not candidates:
            self._flash("no further curated hit/miss in this chapter")
            return
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_roll_quoted(self, *, forward: bool) -> None:
        """Jump to next/prev regenerated roll fact with a narrator quote."""
        cs = self.state.chapter
        if cs is None:
            return
        cur_wi = cs.cursor_word_index
        positions = self._roll_evidence_word_indices(cs)
        positions = sorted(set(positions))
        candidates = [p for p in positions if (p > cur_wi if forward else p < cur_wi)]
        if not candidates:
            self._flash("no curated narrator quote in this direction")
            return
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_evidence_candidate(self, *, forward: bool) -> None:
        """Jump to next/prev paragraph selected by the narrative scorer."""
        cs = self.state.chapter
        if cs is None:
            return
        positions = sorted({c.word_index for c in cs.evidence_candidates})
        if not positions:
            self._flash("no narrative evidence candidates in this chapter")
            return
        cur_wi = cs.cursor_word_index
        candidates = [
            p for p in positions
            if (p > cur_wi if forward else p < cur_wi)
        ]
        if not candidates:
            candidates = positions
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _jump_regex(self, slot_idx: int, *, forward: bool) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        if not (0 <= slot_idx < 4):
            return
        hits = cs.regex_hits[slot_idx].word_indices
        if not hits:
            return
        cur_wi = cs.cursor_word_index
        candidates = [h for h in hits if (h > cur_wi if forward else h < cur_wi)]
        if not candidates:
            # Wrap-around (vim convention).
            candidates = list(hits)
        target = min(candidates) if forward else max(candidates)
        self._jump_to_word(target)

    def _scroll_cursor_into_view(self) -> None:
        """Scroll the prose container so the cursor is visible (B12)."""
        try:
            prose_view = self.query_one("#prose", PassageView)
            scroll = self.query_one("#prose_scroll", VerticalScroll)
        except Exception:
            return
        if not prose_view._lines:
            prose_view._recompute_lines()
        line_idx = prose_view._line_index(prose_view.cursor)
        visible_height = max(1, scroll.size.height or 1)
        target_y = max(0, line_idx - (visible_height // 2))
        try:
            scroll.scroll_to(y=target_y, animate=False)
        except Exception:
            pass

    # ----- regex input wiring -----

    @on(Input.Submitted)
    def _on_regex_submit(self, event: Input.Submitted) -> None:
        slot_id = event.input.id or ""
        if slot_id != "regex_4":
            return
        self._set_active_regex_slot(3)
        self.state.set_regex(3, event.input.value)
        self._jump_regex(3, forward=True)
        self.refresh_all_panels()
        prose = self.query_one("#prose", PassageView)
        prose.focus()

    # ----- track cursor moves in the prose view -----

    def _on_cursor_moved(self) -> None:
        """Called by PassageView whenever the cursor moves (B12 + stats)."""
        cs = self.state.chapter
        if cs is None:
            return
        prose_view = self.query_one("#prose", PassageView)
        cs.cursor_char = prose_view.cursor
        try:
            stats = self.query_one("#stats", StatsPanel)
            stats.render_stats(self.state, self)
            gutter = self.query_one("#gutter", GutterPanel)
            gutter_height = max(1, gutter.size.height or 1)
            gutter.render_minimap(
                self._compute_gutter_marks(),
                self._cursor_chapter_proportion(),
                gutter_height,
            )
        except Exception:
            return
        self._scroll_cursor_into_view()

    def on_resize(self, event: events.Resize) -> None:
        """Re-render the minimap when the panel resizes."""
        try:
            self.refresh_all_panels()
        except Exception:
            pass

    def on_idle(self, event: events.Idle | None = None) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        try:
            prose_view = self.query_one("#prose", PassageView)
        except Exception:
            return
        if cs.cursor_char != prose_view.cursor:
            cs.cursor_char = prose_view.cursor
            self._on_cursor_moved()


# ---------- entry point -----------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="forge_curator", description=__doc__)
    p.add_argument("--chapter", default=None, help="chapter to open at (e.g. 1, 35.1)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    compatibility = check_terminal_compatibility()
    if not compatibility.ok:
        _warn_terminal_compatibility(compatibility)
        raise SystemExit(2)
    app = ForgeCuratorApp(start_chapter=args.chapter)
    app.run()


if __name__ == "__main__":
    main()
