"""Forge Curator TUI (Phase 1 read-only viewer).

Three-panel layout: stats (left), prose with cursor (centre, with a
gutter column), actions catalog (right, disabled in Phase 1). A regex
strip and status bar live at the bottom.

Vim-style cursor motions are inherited from the shared
``nlp.tui_common.PassageView`` widget.

Run with::

    python -m scripts.forge_curator [--chapter X[.Y]]

F12 writes the current TUI state to data/manual/.forge_curator_snapshot.json.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from nlp.tui_common import PassageView as BasePassageView
from scripts.forge_curator.data_loader import ForgeCuratorData
from scripts.forge_curator.data_loader import MANUAL, ROOT
from scripts.forge_curator.persistence import CurationPersistence
from scripts.forge_curator.state import ForgeCuratorState

STATE_FILE = MANUAL / ".forge_curator_state.json"
# Fixed location for the F12 snapshot. Repeated use overwrites this file so
# "look at the snapshot" can mean one stable artifact.
SNAPSHOT_PATH = MANUAL / ".forge_curator_snapshot.json"

KNOWN_CONSTELLATIONS = [
    "Alchemy", "Capstone", "Clothing", "Crafting", "Knowledge",
    "Magic", "Magitech", "Personal Reality", "Quality",
    "Resources and Durability", "Size", "Time", "Toolkits", "Vehicles",
]

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

    Wraps the shared :class:`nlp.tui_common.PassageView` so the App can
    intercept the ``]`` / ``[`` chord prefixes (used by ``]r``, ``][``,
    ``]2`` etc.) before the base widget's vim-style on_key handler eats
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

        # 3) `z` / `x` / `c` select the active regex slot for n/N.
        if ch in ("z", "x", "c"):
            handler = getattr(app, "_handle_regex_slot_hotkey", None)
            if handler is not None:
                handler(ch)
                event.prevent_default()
                event.stop()
                return

        # 4) `*` — search for word under cursor as the dedicated star regex.
        if ch == "*":
            handler = getattr(app, "_handle_star_search", None)
            if handler is not None:
                handler()
                event.prevent_default()
                event.stop()
                return

        # 5) `n` / `N` — next / prev active regex match.
        if ch in ("n", "N"):
            handler = getattr(app, "_handle_n_search", None)
            if handler is not None:
                handler(forward=(ch == "n"))
                event.prevent_default()
                event.stop()
                return

        # 6) Space alone arms the action leader chord (overrides the base
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


# Glyph colors used by gutter Rich styles, prose highlights, and RegexBar CSS.
GLYPH_COLORS: dict[str, str] = {
    "═": "grey70",
    "R": "red",
    "H": "green",
    "M": "orange1",
    "A": "blue",
    "Q": "medium_purple1",
    "1": "yellow",
    "2": "cyan",
    "3": "magenta",
    "*": "white",
}
GLYPH_STYLES: dict[str, str] = {
    glyph: f"bold {color}" for glyph, color in GLYPH_COLORS.items()
}

ROLL_HIGHLIGHT_STYLE = GLYPH_STYLES["R"]
QUOTE_HIGHLIGHT_STYLE = GLYPH_STYLES["Q"]
REGEX_HIGHLIGHT_STYLES = (
    GLYPH_STYLES["1"],
    GLYPH_STYLES["2"],
    GLYPH_STYLES["3"],
    GLYPH_STYLES["*"],
)

ROLL_EVIDENCE_GUTTER_GLYPH = "Q"

LEGEND = [
    ("═", "section break / header", GLYPH_STYLES["═"]),
    ("R", "predicted roll", GLYPH_STYLES["R"]),
    ("H", "hit (curated/derived)", GLYPH_STYLES["H"]),
    ("M", "miss (curated/derived)", GLYPH_STYLES["M"]),
    ("A", "author note span", GLYPH_STYLES["A"]),
    (
        ROLL_EVIDENCE_GUTTER_GLYPH,
        "saved roll evidence",
        GLYPH_STYLES[ROLL_EVIDENCE_GUTTER_GLYPH],
    ),
    ("1", "regex 1 (z, n/N)", GLYPH_STYLES["1"]),
    ("2", "regex 2", GLYPH_STYLES["2"]),
    ("3", "regex 3", GLYPH_STYLES["3"]),
    ("*", "regex *", GLYPH_STYLES["*"]),
]

ROLL_EVIDENCE_MARKERS = [
    ("Q", "curated quote"),
    ("T", "text evidence"),
    ("S", "spreadsheet/log"),
    ("I", "inferred"),
]

# Lower rank values render first. A row can show up to five indicators
# followed by a blank spacer column.
_GLYPH_PRIORITY = {
    "H": 1,
    "M": 2,
    "R": 3,
    "═": 4,
    "A": 5,
    ROLL_EVIDENCE_GUTTER_GLYPH: 6,
    "*": 7,
    "1": 8,
    "2": 9,
    "3": 10,
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

    _CURSOR_ROW_STYLE = "reverse"

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

    def render_stats(self, state: ForgeCuratorState, app: "ForgeCuratorApp") -> None:
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
        since_last_roll, until_next_roll = app._roll_distance_stats(story_cp_cursor)

        eligibility = app._eligibility_at_cursor(cs, word_idx, sec_idx)
        section_status = (
            "CP eligible" if eligibility["section_eligible"] else "CP ineligible"
        )
        text_status = "CP eligible" if eligibility["text_eligible"] else "CP ineligible"

        cp_stats = app._cp_stats_at_cursor(cs, cp_word_idx)

        unified = app._unified_rolls(cs)
        current_roll: dict | None = None
        for roll in unified:
            if roll["word_position"] <= cp_word_idx:
                current_roll = roll
            else:
                break

        roll_lines: list[str] = []
        if not unified:
            roll_lines.append("  (no rolls)")
        else:
            for roll in unified:
                marker = (
                    "▸"
                    if current_roll is not None and roll["index"] == current_roll["index"]
                    else " "
                )
                line = app._format_roll_stat_line(roll, marker)
                if roll["word_position"] > cp_word_idx:
                    line = f"[dim]{line}[/]"
                roll_lines.append(line)
        rolls_block = "\n".join(roll_lines)
        perks_block = app._perks_this_chapter_block(cs)
        model_status = app._model_validation_summary(cs)
        title_block = "\n".join(
            _wrap_title_for_stats(cs.meta.full_title, STATS_CONTENT_WIDTH)
        )

        body = (
            f"[bold]Chapter[/bold]\n"
            f"{title_block}\n"
            f"  chapter {_fmt_int(chapter_ordinal)} / {_fmt_int(total_chapters)}; "
            f"section {_fmt_int(section_ordinal)} / {_fmt_int(section_total)}\n"
            f"  Model: {model_status}\n\n"
            f"  Section: {section_status}\n"
            f"  Text: {text_status} - {eligibility['reason']}\n\n"
            f"[bold]Words[/bold]\n"
            f"  Total content:\n"
            f"    story {_fmt_int(story_content_cursor)} / {_fmt_int(story_content_total)}\n"
            f"    chapter {_fmt_int(content_word_idx)} / {_fmt_int(chapter_content_total)}\n"
            f"  CP eligible:\n"
            f"    story {_fmt_int(story_cp_cursor)} / {_fmt_int(story_cp_total)}\n"
            f"    chapter {_fmt_int(cp_word_idx)} / {_fmt_int(chapter_cp_total)}\n"
            f"  Since last roll: {_fmt_int(since_last_roll)}\n"
            f"  Until next roll: {_fmt_int(until_next_roll)}\n\n"
            f"[bold]CP at cursor[/bold]\n"
            f"  Gained:\n"
            f"    total {_fmt_int(cp_stats['gained_total'])}\n"
            f"    chapter {_fmt_int(cp_stats['gained_chapter'])}\n"
            f"  Spent:\n"
            f"    total {_fmt_int(cp_stats['spent_total'])}\n"
            f"    chapter {_fmt_int(cp_stats['spent_chapter'])}\n\n"
            f"[bold]Rolls[/bold] [dim]({app._rolls_header_count(cs)})[/]\n"
            f"{rolls_block}\n\n"
            f"[bold]Perks this chapter[/bold]\n{perks_block}\n"
        )
        self.update(body)


def _fmt_int(value: int | None) -> str:
    return "n/a" if value is None else f"{int(value):,}"


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


def _an_word_length(note: dict) -> int:
    """Word count of an author-note entry (best effort).

    The on-disk schema doesn't carry an explicit word count; use the raw
    text length as a proxy.
    """
    text = note.get("an_text") or ""
    return len(text.split())


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
# functions ignored AN / auto-header / manual-header exclusion ranges
# and would land ``]r`` and similar jumps a few words off from the
# actual threshold-crossing. The canonical methods both consult
# ``_excluded_word_ranges`` so they always agree.


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
            "  ⎵e  Toggle chapter eligibility\n\n"
            "[bold]Selection-based[/bold]\n"
            "  v / V    select char / line\n"
            "  ⎵a       AN = selection\n"
            "  ⎵H       header = selection\n"
            "  ⎵q       quote = selection\n"
            "  ⎵Q       quote = selection, multiple rolls\n\n"
            "[bold]Roll metadata[/bold]\n"
            "  ⎵h  Last roll = hit\n"
            "  ⎵m  Last roll = miss\n"
            "  ⎵d  Defer evidence to next chapter\n"
            "  ⎵c  Set constellation\n"
            "  ⎵p  Set perks\n\n"
            "[bold]Annotation cleanup[/bold]\n"
            "  ⎵D  Remove annotation at word\n\n"
            "[bold]Navigation[/bold]\n"
            "  ]] [[  next/prev chapter\n"
            "  ][ []  next/prev section\n"
            "  ]r [r  next/prev predicted roll\n"
            "  ]R [R  next/prev curated quote\n"
            "  z/x/c  active regex 1/2/3\n"
            "  n N    active regex next/prev\n"
            "  *      seed/select regex *\n"
            "  ]2 [2  regex 2\n"
            "  ]3 [3  regex 3\n\n"
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
    RegexBar > Input.regex-slot-1 {{
        color: {GLYPH_COLORS["1"]};
        text-style: bold;
    }}
    RegexBar > Input.regex-slot-2 {{
        color: {GLYPH_COLORS["2"]};
        text-style: bold;
    }}
    RegexBar > Input.regex-slot-3 {{
        color: {GLYPH_COLORS["3"]};
        text-style: bold;
    }}
    RegexBar > Input.regex-slot-4 {{
        color: {GLYPH_COLORS["*"]};
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
    RegexBar Static.label.regex-slot-1 {{
        color: {GLYPH_COLORS["1"]};
        text-style: bold;
    }}
    RegexBar Static.label.regex-slot-2 {{
        color: {GLYPH_COLORS["2"]};
        text-style: bold;
    }}
    RegexBar Static.label.regex-slot-3 {{
        color: {GLYPH_COLORS["3"]};
        text-style: bold;
    }}
    RegexBar Static.label.regex-slot-4 {{
        color: {GLYPH_COLORS["*"]};
        text-style: bold;
    }}
    """

    def compose(self) -> ComposeResult:
        yield Static("regex 1:", id="regex_label_1", classes="label regex-slot-1")
        yield Input(
            id="regex_1", placeholder="(none)", compact=True, classes="regex-slot-1"
        )
        yield Static("regex 2:", id="regex_label_2", classes="label regex-slot-2")
        yield Input(
            id="regex_2", placeholder="(none)", compact=True, classes="regex-slot-2"
        )
        yield Static("regex 3:", id="regex_label_3", classes="label regex-slot-3")
        yield Input(
            id="regex_3", placeholder="(none)", compact=True, classes="regex-slot-3"
        )
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
            "  f<c> F<c> t<c> T<c>  find char\n"
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
            "  ]] [[   next/prev chapter\n"
            "  ][ []   next/prev section\n"
            "  ]r [r   next/prev curated hit/miss\n"
            "  ]R [R   next/prev predicted roll\n"
            "  ]q [q   next/prev curated narrator quote\n"
            "  z/x/c   select regex 1/2/3 for n/N\n"
            "  n / N   next/prev active regex match\n"
            "  *       seed/select regex * with word under cursor\n"
            "  ]2 [2   regex 2 matches\n"
            "  ]3 [3   regex 3 matches\n"
            "  F12     snapshot state to data/manual/.forge_curator_snapshot.json\n"
        )
        body.append("\nRegex bar\n", style="bold")
        body.append(
            "  /     focus regex *\n"
            "  Tab   cycle regex 1 -> 2 -> 3 -> *\n"
            "  Enter apply regex\n"
        )
        body.append(
            "\nAction panel keybinds (disabled in Phase 1)\n", style="bold"
        )
        body.append(
            "  <space>e         toggle chapter eligibility\n"
            "  <space>a         AN = current selection\n"
            "  <space>H         header span = current selection\n"
            "  <space>q         roll quote = current selection\n"
            "  <space>Q         roll quote = current selection, multi-roll\n"
            "  <space>d         defer current roll evidence to next chapter\n"
            "  <space>D         remove annotation at current word\n"
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


class RollEvidencePicker(ModalScreen):
    """Multi-select roll picker for assigning one quote to several rolls."""

    DEFAULT_CSS = """
    RollEvidencePicker {
        align: center middle;
    }
    RollEvidencePicker > Container {
        width: 76;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    RollEvidencePicker Static.title {
        height: 1;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    RollEvidencePicker Button {
        width: 100%;
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
        return f"{marker} #{roll.get('index')} ({global_part})  {outcome}"

    def compose(self) -> ComposeResult:
        with Container():
            yield Static("Save quote to rolls (click to toggle)", classes="title")
            for idx, r in enumerate(self._rolls, start=1):
                yield Button(
                    self._roll_button_label(idx, r),
                    id=f"roll_{idx}",
                    name=str(idx),
                )
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
        if isinstance(self.focused, Button) and self.focused.id != "confirm":
            self._toggle_button(self.focused)

    def action_confirm_selection(self) -> None:
        self.app.pop_screen()
        self._on_confirm(sorted(self._selected))

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
        self.active_regex_slot: int = 0
        self._last_curation_error: str | None = None
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
        for idx, hits in enumerate(cs.regex_hits[:4], start=1):
            try:
                inp = self.query_one(f"#regex_{idx}", Input)
                label = self.query_one(f"#regex_label_{idx}", Static)
            except Exception:
                continue
            if not inp.has_focus:
                inp.value = hits.pattern
            active = idx - 1 == self.active_regex_slot
            inp.set_class(active, "active")
            label.set_class(active, "active")

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
        for slot, hits in enumerate(cs.regex_hits[:4]):
            style = REGEX_HIGHLIGHT_STYLES[slot]
            for start, end in hits.char_spans:
                if 0 <= start < end <= len(cs.prose.text):
                    spans.append({
                        "start": start,
                        "end": end,
                        "style": style,
                        "priority": 30 + slot,
                    })
        return spans

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
        for roll in self._unified_rolls(cs):
            quote = roll.get("narrative_evidence")
            if not quote:
                continue
            start = cs.prose.text.find(str(quote))
            if start >= 0:
                span = (start, start + len(str(quote)))
            else:
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
        cn = cs.meta.chapter_num
        for roll in (cs.derived.chapter_facts or {}).get("rolls", []):
            if str(roll.get("mechanical_chapter_num")) != cn:
                continue
            wp = roll.get("mechanical_word_position")
            if wp is None:
                wp = roll.get("word_position")
            if wp is not None:
                indices.append(self._raw_word_for_cp_offset(int(wp)))
        return indices

    def _curated_roll_word_index(self, cs, roll: dict) -> int | None:
        if roll.get("display_kind") == "deferred_in":
            return None
        raw = roll.get("raw_word_position")
        if raw is not None:
            return int(raw)
        quote = roll.get("narrative_evidence")
        if quote:
            start = cs.prose.text.find(str(quote))
            if start >= 0:
                return _word_index_for_char_offset(cs.prose.word_offsets, start)
        return None

    def _evidence_fallback_word_index(self, cs, roll: dict) -> int | None:
        if roll.get("word_position") is None:
            return None
        return self._raw_word_for_cp_offset(int(roll["word_position"]))

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
        # Derived excluded ranges include ANs and auto/manual header
        # exclusions. Auto headers already have a header glyph above, so
        # don't render their duplicate exclusion range as an AN.
        implicit_headers = set(cs.prose.implicit_header_word_ranges or [])
        for ws, _we in (cs.meta.excluded_word_ranges or []):
            span = (int(ws), int(_we))
            if span in implicit_headers:
                continue
            if 0 <= int(ws) < total:
                _add(int(ws), "A")

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

        # Regex matches.
        for slot, hits in enumerate(cs.regex_hits, start=1):
            for wi in hits.word_indices:
                if 0 <= wi < total:
                    _add(int(wi), "*" if slot == 4 else str(slot))

        return items

    # ----- helpers ---------------------------------------------------------

    def _chapter_author_notes(self, chapter_num: str) -> list[dict]:
        """Manual AN docs are write inputs; display uses derived ranges."""
        return []

    def _an_word_span(self, note: dict, cs) -> tuple[int | None, int | None]:
        """Compute the chapter-local raw word range covered by an AN entry.

        The on-disk schema doesn't carry word offsets, so derive them
        from the AN's section_index plus the actual ``an_text`` length.
        We place the AN at the END of its section (matches the dominant
        convention: ANs trail the section's prose).
        """
        section_index = note.get("section_index")
        if section_index is None:
            return None, None
        sections = cs.meta.sections or []
        if not (0 <= int(section_index) < len(sections)):
            return None, None
        # Cumulative raw word offset to start of section_index+1.
        cum = 0
        for i, sec in enumerate(sections):
            wc = int(sec.get("word_count") or 0)
            if i == int(section_index):
                end = cum + wc
                start = max(cum, end - _an_word_length(note))
                return start, end
            cum += wc
        return None, None

    def _excluded_word_ranges(self, cs) -> list[tuple[int, int]]:
        """Word ranges in the current chapter excluded from CP earning.

        Combines derived excluded ranges and auto-detected section
        header ranges. Manual files are not read directly for display.
        """
        ranges: list[tuple[int, int]] = []
        # Auto-detected section-header spans.
        for ws, we in (cs.prose.implicit_header_word_ranges or []):
            ranges.append((int(ws), int(we)))
        return _merge_ranges(sorted(ranges))

    def _chapter_ordinal(self, chapter_num: str) -> int:
        try:
            return self.data.chapter_order.index(str(chapter_num)) + 1
        except ValueError:
            return 0

    def _canonical_excluded_word_ranges(
        self, chapter_num: str, cs=None
    ) -> list[tuple[int, int]]:
        """Chapter-local content exclusions from derived data plus live edits."""
        cn = str(chapter_num)
        ranges: list[tuple[int, int]] = []
        try:
            meta = self.data.chapter_meta(cn)
            for r in meta.excluded_word_ranges or []:
                if len(r) == 2 and int(r[1]) > int(r[0]):
                    ranges.append((int(r[0]), int(r[1])))
        except Exception:
            pass
        if cs is not None:
            ranges.extend(self._excluded_word_ranges(cs))
        return _merge_ranges(sorted(ranges))

    def _content_word_offset(self, cs, raw_word_idx: int) -> int:
        total = len(cs.prose.word_offsets)
        raw_word_idx = max(0, min(int(raw_word_idx), total))
        excluded = self._canonical_excluded_word_ranges(cs.meta.chapter_num, cs)
        return max(0, raw_word_idx - _range_prefix_len(excluded, raw_word_idx))

    def _chapter_content_total(self, chapter_num: str, cs=None) -> int:
        meta = self.data.chapter_meta(str(chapter_num))
        total = int(meta.total_word_count or 0)
        excluded = self._canonical_excluded_word_ranges(str(chapter_num), cs)
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

        for ws, we in (cs.prose.implicit_header_word_ranges or []):
            if int(ws) <= word_idx < int(we):
                return {
                    "section_eligible": section_eligible,
                    "text_eligible": False,
                    "reason": "header",
                }
        for ws, we in (cs.meta.excluded_word_ranges or []):
            if int(ws) <= word_idx < int(we):
                return {
                    "section_eligible": section_eligible,
                    "text_eligible": False,
                    "reason": "excluded",
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

    def _all_roll_global_positions(self) -> list[int]:
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

    def _roll_distance_stats(self, story_cp_cursor: int) -> tuple[int, int | None]:
        positions = self._all_roll_global_positions()
        last = max((p for p in positions if p <= story_cp_cursor), default=0)
        nxt = min((p for p in positions if p > story_cp_cursor), default=None)
        since = max(0, story_cp_cursor - last)
        until = None if nxt is None else max(0, nxt - story_cp_cursor)
        return since, until

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
            "spent_total": spent_total,
            "spent_chapter": spent_chapter,
        }

    def _cp_earning_word_offset(self, raw_word_idx: int) -> int:
        """Map raw cursor word index to its CP-earning offset.

        CP-eligible word = (section is CP-eligible) AND (word not within
        any AN / header / auto-header span). Walks the chapter's
        sections, intersecting CP-eligible section ranges with the
        excluded-range list, so excluded words that already lie in an
        ineligible section don't get double-subtracted. This is the
        canonical raw→CP function for the TUI; ``_raw_word_for_cp_offset``
        is its inverse.
        """
        cs = self.state.chapter
        if cs is None or raw_word_idx <= 0:
            return 0
        excluded = self._canonical_excluded_word_ranges(cs.meta.chapter_num, cs)
        sections = cs.meta.sections or []
        cp = 0
        raw_running = 0
        for sec in sections:
            wc = int(sec.get("word_count") or 0)
            sec_end = raw_running + wc
            if bool(sec.get("counts_for_cp", True)):
                upper = min(sec_end, raw_word_idx)
                if upper > raw_running:
                    eligible_words = upper - raw_running
                    excluded_words = sum(
                        max(0, min(we, upper) - max(ws, raw_running))
                        for ws, we in excluded
                    )
                    cp += max(0, eligible_words - excluded_words)
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
        deferred = sum(
            1 for roll in self._unified_rolls(cs)
            if roll.get("display_kind") == "deferred_in"
        )
        if deferred:
            return f"{predicted} predicted +{_fmt_int(deferred)} deferred"
        return f"{predicted} predicted"

    def _mechanical_roll_index(self, roll: dict) -> int | None:
        chapter_num = roll.get("mechanical_chapter_num")
        if chapter_num is None:
            return None
        rows = [
            r for r in self.data.roll_facts.get("rolls", [])
            if r.get("source_kind") != "trigger"
            and str(r.get("mechanical_chapter_num")) == str(chapter_num)
        ]
        rows.sort(key=lambda r: (
            int(r.get("mechanical_word_position") or r.get("word_position") or 0),
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
            )
        ]

        result: list[dict] = []
        rows = sorted(
            canonical_rows,
            key=lambda r: (
                0 if self._local_cp_from_roll(cn, r) is None else 1,
                self._local_cp_from_roll(cn, r) or 0,
                int(r.get("mechanical_cumulative_word_offset") or 0),
                int(r.get("roll_number") or r.get("roll_sequence_in_chapter") or 0),
            ),
        )
        local_index = 0
        for row in rows:
            local_cp = self._local_cp_from_roll(cn, row)
            is_deferred_in = local_cp is None and str(row.get("chapter_num")) == cn
            if local_cp is None and not is_deferred_in:
                continue
            if is_deferred_in:
                display_kind = "deferred_in"
                word_position = 0
                raw_word_position = 0
                global_cp = row.get("mechanical_cumulative_word_offset")
            else:
                display_kind = "chapter_roll"
                local_index += 1
                word_position = int(local_cp)
                raw_word_position = self._raw_word_for_cp_offset(int(local_cp))
                global_cp = self._global_cp_from_roll(cn, row)
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
                "narrative_evidence": row.get("narrative_evidence"),
                "target_chapter_num": str(
                    row.get("mechanical_chapter_num") or cn
                ),
                "target_roll_index": self._mechanical_roll_index(row),
                "visible_chapter_num": cn,
            }
            result.append(entry)
        return result

    def _roll_evidence_marker(self, roll: dict) -> str:
        if roll.get("narrative_evidence"):
            return "Q"
        evidence_kind = str(roll.get("evidence_kind") or "")
        if evidence_kind in {"direct", "general_only", "forward_ref"} and (
            roll.get("anchor_char_offset_in_chapter") is not None
            or roll.get("predicted_char_offset_in_chapter") is not None
        ):
            return "T"
        if (
            roll.get("source") in {"curator_rolls", "curator"}
            or roll.get("fact_source") == "curator_rolls"
            or roll.get("source_kind") in {"roll", "miss"}
        ):
            return "S"
        return "I"

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

    def _format_roll_stat_line(self, roll: dict, marker: str) -> str:
        global_num = roll.get("roll_number")
        global_part = f"global #{global_num}" if global_num is not None else "global #?"
        outcome = roll.get("outcome") or "unknown"
        evidence = self._roll_evidence_marker(roll)
        constel = roll.get("constellation") or "unknown"
        if outcome == "miss":
            min_cost = roll.get("miss_cost_estimate") or roll.get("rolled_perk_cost")
            perk_text = (
                f"missed >= {int(min_cost)} CP"
                if min_cost is not None else "missed"
            )
            detail_lines = [f"    {constel} - {perk_text}"]
        else:
            perks = roll.get("purchased_perks") or []
            if perks:
                detail_lines = []
                for p in perks:
                    name = p.get("name") or p.get("perk_name") or "unknown"
                    cost = "free" if p.get("free") else str(int(p.get("cost") or 0))
                    detail_lines.append(f"    {constel} - {name} ({cost})")
            else:
                detail_lines = [f"    {constel} - perk unknown"]
        if roll.get("display_kind") == "deferred_in":
            source_chapter = roll.get("target_chapter_num") or roll.get("mechanical_chapter_num")
            source_idx = roll.get("target_roll_index") or "?"
            available = roll.get("available_cp")
            if available is not None:
                detail_lines.append(f"    available CP at slot: {int(available)}")
            return "\n".join([
                (
                    f"  {marker} deferred from ch {source_chapter} #{source_idx} "
                    f"({global_part}) {outcome} {evidence}"
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
            detail_lines.insert(0, f"    narrative deferred to ch {mention_chapter}")
        chapter_idx = int(roll.get("index") or roll.get("roll_sequence_in_chapter") or 0)
        return "\n".join([
            f"  {marker} #{chapter_idx} ({global_part}) {outcome} {evidence}",
            *detail_lines,
        ])

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
        full = action in {
            "mark_an_span",
            "mark_header_span",
            "remove_annotations_at_word",
        }
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
        }
        if cs is not None:
            snap["chapter"] = {
                "chapter_num": cs.meta.chapter_num,
                "full_title": cs.meta.full_title,
                "total_word_count": cs.meta.total_word_count,
                "cp_earning_word_count": cs.meta.cp_earning_word_count,
                "sections": cs.meta.sections,
                "excluded_word_ranges": cs.meta.excluded_word_ranges,
            }
            snap["cursor"] = {
                "char": cs.cursor_char,
                "word_index": cs.cursor_word_index,
                "total_words": cs.total_words,
                "section_index": cs.section_index_at(cs.cursor_word_index),
            }
            snap["regex"] = [
                {
                    "slot": idx + 1,
                    "pattern": hits.pattern,
                    "error": hits.error,
                    "word_indices": list(hits.word_indices),
                    "char_spans": list(hits.char_spans),
                }
                for idx, hits in enumerate(cs.regex_hits[:4])
            ]
            snap["rolls"] = self._unified_rolls(cs)
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
        if not (0 <= slot < 4):
            return
        self.active_regex_slot = slot
        self._refresh_regex_bar()

    def _handle_regex_slot_hotkey(self, ch: str) -> None:
        slots = {"z": 0, "x": 1, "c": 2}
        slot = slots.get(ch)
        if slot is not None:
            self._set_active_regex_slot(slot)

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
            self._action_toggle_chapter_eligibility(cn)
        elif ch == "a":
            self._action_mark_an_from_selection(cn)
        elif ch == "H":
            self._action_mark_header_from_selection(cn)
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
        elif ch == "d":
            self._action_defer_roll_to_next_chapter(cn)
        elif ch == "D":
            self._action_remove_annotations_at_current_word(cn)
        elif ch == "i":
            self._action_insert_roll(cn)
        else:
            self._flash(f"<space>{ch}: not bound")

    # ----- Phase 2 action implementations ---------------------------------

    def _flash(self, message: str) -> None:
        """Refresh panels without treating manual edits as display facts."""
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
            self.refresh_all_panels()
            self._scroll_cursor_into_view()
            return
        self._last_curation_error = None
        self.data.reload_from_disk()
        new_cs = self._load_chapter(cn)
        new_cs.cursor_char = saved_cursor
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

    def _refresh_live_manual_inputs(self) -> None:
        """Deprecated compatibility path for non-roll actions."""
        cs = self.state.chapter
        if cs is not None:
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
            self.data._derived_cache.pop(cn, None)
            new_cs = self._load_chapter(cn)
            new_cs.cursor_char = saved_cursor
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
        else:
            self.refresh_all_panels()

    def _action_toggle_chapter_eligibility(self, chapter_num: str) -> None:
        now_disabled = self.persistence.toggle_chapter_eligibility(chapter_num)
        msg = "DISABLED" if now_disabled else "ENABLED"
        self._flash(f"ch {chapter_num} CP eligibility: {msg}")

    def _action_mark_an_from_selection(self, chapter_num: str) -> None:
        """Save the current visual selection as an Author Note span.

        Use ``v`` (char) or ``V`` (line) to select the AN text, then
        ``<space>a``. Section index is taken from where the selection
        starts.
        """
        cs = self.state.chapter
        if cs is None:
            return
        prose_view = self.query_one("#prose", PassageView)
        sel = prose_view.selection
        if sel is None:
            self._flash("AN: no selection — press v or V to select first")
            return
        lo, hi = sel
        an_text = cs.prose.text[lo:hi].strip()
        if not an_text:
            self._flash("AN: empty selection")
            return
        wo = cs.prose.word_offsets
        word_at_lo = next((i for i, (s, e) in enumerate(wo) if e > lo), 0) if wo else 0
        section_index = cs.section_index_at(word_at_lo)
        self.persistence.mark_an_span(
            chapter_num, int(section_index), an_text,
            reason="marked via curator TUI",
        )
        prose_view.anchor = None
        prose_view.visual_mode = False
        prose_view.visual_line_mode = False
        refresh = getattr(prose_view, "refresh", None)
        if callable(refresh):
            refresh()
        self._post_curation_refresh(
            f"AN saved ({len(an_text.split())} words, sec {section_index})",
            full=True,
        )

    def _action_mark_header_from_selection(self, chapter_num: str) -> None:
        """Save the current visual selection as a header-span correction.

        Marked words are excluded from CP-earning word counts. Use ``V``
        to grab the whole header line, then ``<space>H``.
        """
        cs = self.state.chapter
        if cs is None:
            return
        prose_view = self.query_one("#prose", PassageView)
        sel = prose_view.selection
        if sel is None:
            self._flash("header: no selection — press V to select the header line")
            return
        lo, hi = sel
        wo = cs.prose.word_offsets
        if not wo:
            self._flash("header: empty chapter")
            return
        word_start = next((i for i, (s, e) in enumerate(wo) if e > lo), len(wo))
        word_end = next((i for i, (s, e) in enumerate(wo) if s >= hi), len(wo))
        if word_end <= word_start:
            self._flash("header: selection covers no whole word")
            return
        excerpt = cs.prose.text[lo:hi].strip()
        if len(excerpt) > 80:
            excerpt = excerpt[:77] + "..."
        section_index = cs.section_index_at(word_start)
        self.persistence.mark_header_span(
            chapter_num, int(section_index),
            int(word_start), int(word_end),
            excerpt=excerpt,
        )
        prose_view.anchor = None
        prose_view.visual_mode = False
        prose_view.visual_line_mode = False
        refresh = getattr(prose_view, "refresh", None)
        if callable(refresh):
            refresh()
        self._post_curation_refresh(
            f"header marked ({word_end - word_start} words, sec {section_index})",
            full=True,
        )

    def _manual_author_note_keys_at_word(
        self, chapter_num: str, word_idx: int,
    ) -> list[tuple[int, str]]:
        """Resolve manual author-note entries that cover ``word_idx``."""
        cs = self.state.chapter
        if cs is None:
            return []
        notes = self.persistence.author_notes.get("author_notes") or []
        word_offsets = cs.prose.word_offsets
        if not word_offsets:
            return []

        section_starts: list[int] = []
        running = 0
        for section in cs.meta.sections or []:
            section_starts.append(running)
            running += int(section.get("word_count") or 0)

        matches: list[tuple[int, str]] = []
        for note in notes:
            if str(note.get("chapter_num")) != str(chapter_num):
                continue
            try:
                section_index = int(note.get("section_index"))
            except Exception:
                continue
            an_text = str(note.get("an_text") or "")
            if not an_text or not (0 <= section_index < len(section_starts)):
                continue

            section_start_word = section_starts[section_index]
            section_end_word = (
                section_starts[section_index + 1]
                if section_index + 1 < len(section_starts)
                else len(word_offsets)
            )
            if section_start_word >= len(word_offsets):
                continue
            section_start_char = word_offsets[section_start_word][0]
            section_end_char = (
                word_offsets[min(section_end_word, len(word_offsets)) - 1][1]
                if section_end_word > section_start_word
                else section_start_char
            )
            section_text = cs.prose.text[section_start_char:section_end_char]
            offset = section_text.find(an_text)
            if offset < 0:
                note_words = an_text.split()
                section_words = [
                    cs.prose.text[s:e]
                    for s, e in word_offsets[section_start_word:section_end_word]
                ]
                for rel_start in range(0, len(section_words) - len(note_words) + 1):
                    rel_end = rel_start + len(note_words)
                    if section_words[rel_start:rel_end] == note_words:
                        start_word = section_start_word + rel_start
                        end_word = section_start_word + rel_end
                        if start_word <= int(word_idx) < end_word:
                            matches.append((section_index, an_text))
                        break
                continue

            start_char = section_start_char + offset
            end_char = start_char + len(an_text)
            start_word = next(
                (i for i, (_s, e) in enumerate(word_offsets) if e > start_char),
                len(word_offsets),
            )
            end_word = next(
                (i for i, (s, _e) in enumerate(word_offsets) if s >= end_char),
                len(word_offsets),
            )
            if start_word <= int(word_idx) < end_word:
                matches.append((section_index, an_text))
        return matches

    def _action_remove_annotations_at_current_word(self, chapter_num: str) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        roll_targets = self._roll_evidence_targets_at_selection_or_cursor()
        removed_roll_evidence = 0
        for target_chapter, target_index in roll_targets:
            if self.persistence.clear_roll_evidence_at_index(
                target_chapter,
                target_index,
            ):
                removed_roll_evidence += 1
        word_idx = cs.cursor_word_index
        result = self.persistence.remove_annotations_at_word(
            chapter_num,
            word_idx,
            author_note_keys=self._manual_author_note_keys_at_word(chapter_num, word_idx),
        )
        total = (
            result["author_notes"]
            + result["header_corrections"]
            + removed_roll_evidence
        )
        if not total:
            self._flash("annotation delete: none at current word")
            return
        full = bool(result["author_notes"] or result["header_corrections"])
        self._post_curation_refresh(
            (
                "annotation delete: "
                f"{result['author_notes']} AN, "
                f"{result['header_corrections']} header, "
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

    def _roll_evidence_targets_at_selection_or_cursor(self) -> list[tuple[str, int]]:
        cs = self.state.chapter
        target_range = self._selection_or_cursor_char_range()
        if cs is None or target_range is None:
            return []
        lo, hi = target_range
        targets: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for roll in self._unified_rolls(cs):
            quote = roll.get("narrative_evidence")
            target_index = roll.get("target_roll_index")
            if not quote or target_index is None:
                continue
            quote_text = str(quote)
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
            key = (str(roll.get("target_chapter_num") or cs.meta.chapter_num), int(target_index))
            if key not in seen:
                seen.add(key)
                targets.append(key)
        return targets

    def _current_roll_target(self, *, word_idx: int | None = None) -> dict | None:
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
        for roll in self._unified_rolls(cs):
            if roll.get("display_kind") == "deferred_in":
                if int(roll.get("word_position") or 0) <= cp_word_idx:
                    target = roll
                continue
            target_chapter = str(roll.get("target_chapter_num") or cs.meta.chapter_num)
            display_chapter = str(roll.get("display_chapter_num") or cs.meta.chapter_num)
            if target_chapter != str(cs.meta.chapter_num) and display_chapter != str(
                cs.meta.chapter_num
            ):
                continue
            mechanical_word = (
                roll.get("word_position")
                if display_chapter == str(cs.meta.chapter_num)
                else roll.get("mechanical_word_position")
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

    def _action_save_quote(self, chapter_num: str) -> None:
        quote = self._selected_quote("save quote")
        if quote is None:
            return
        target_word = self._selected_quote_start_word_index()
        target = self._current_roll_target(word_idx=target_word)
        if target is None or target.get("target_roll_index") is None:
            self._flash("save quote: no predicted roll at/before cursor")
            return
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        idx = int(target["target_roll_index"])
        mention_word = self._cp_earning_word_offset(target_word or 0)
        self.persistence.update_roll_at_index(
            target_chapter,
            idx,
            narrative_evidence=quote,
            mention_chapter_num=chapter_num,
            mention_word_position=mention_word,
            display_position_policy="mention",
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
        rolls = self._unified_rolls(cs)
        if not rolls:
            self._flash("save quote: no rolls in this chapter")
            return
        self._clear_prose_selection()

        def on_confirm(indices: list[int]) -> None:
            if not indices:
                self._flash("save quote: no rolls selected")
                return
            by_chapter: dict[str, list[int]] = {}
            for index in indices:
                if 1 <= index <= len(rolls):
                    target_roll = rolls[index - 1]
                    target_chapter = str(
                        target_roll.get("target_chapter_num") or chapter_num
                    )
                    target_index = target_roll.get("target_roll_index")
                    if target_index is not None:
                        by_chapter.setdefault(target_chapter, []).append(int(target_index))
            for target_chapter, target_indices in by_chapter.items():
                self.persistence.update_rolls_at_indices(
                    target_chapter,
                    target_indices,
                    narrative_evidence=quote,
                    mention_chapter_num=chapter_num,
                    mention_word_position=mention_word,
                    display_position_policy="mention",
                )
            self._post_curation_refresh(
                f"quote saved to rolls {', '.join(map(str, indices))}"
            )

        self.push_screen(RollEvidencePicker(rolls=rolls, on_confirm=on_confirm))

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
        if target.get("display_kind") == "deferred_in":
            self._flash("defer evidence: roll is already deferred into this chapter")
            return
        idx = int(target["target_roll_index"])
        target_chapter = str(target.get("target_chapter_num") or chapter_num)
        next_chapter = self._next_chapter_num(chapter_num)
        if next_chapter is None:
            self._flash("defer evidence: no next chapter")
            return
        self.persistence.mark_roll_deferred_to_chapter(
            target_chapter,
            idx,
            next_chapter,
            mention_word_position=None,
            display_position_policy="mechanical",
        )
        self._post_curation_refresh(
            f"roll #{idx} evidence deferred to ch {next_chapter}"
        )

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
        # ]] / [[  — chapter
        if key == prefix:
            (self.action_next_chapter if prefix == "]" else self.action_prev_chapter)()
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
        if key in ("2", "3"):
            self._jump_regex(int(key) - 1, forward=(prefix == "]"))
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
        self._jump_regex(self.active_regex_slot, forward=forward)

    # ----- jump navigation -----

    def _jump_to_word(self, word_idx: int) -> None:
        cs = self.state.chapter
        if cs is None:
            return
        char = self.state.char_at_word_index(word_idx)
        cs.cursor_char = char
        prose_view = self.query_one("#prose", PassageView)
        prose_view.cursor = char
        self.refresh_all_panels()
        self._scroll_cursor_into_view()

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
        m = re.match(r"regex_([1234])", slot_id)
        if not m:
            return
        slot = int(m.group(1)) - 1
        self._set_active_regex_slot(slot)
        self.state.set_regex(slot, event.input.value)
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
    app = ForgeCuratorApp(start_chapter=args.chapter)
    app.run()


if __name__ == "__main__":
    main()
