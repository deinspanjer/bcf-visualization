"""BCF Annotation TUI — main Textual App.

Run with::

    python -m nlp.tui.app [--jsonl PATH] [--strategy STRATEGY] [--annotator NAME]

Or via uv::

    uv run python -m nlp.tui.app

The TUI requires only ``textual``, ``pydantic``, and ``httpx`` — no torch.

Keybindings implemented
-----------------------
s       Save current passage and advance to next candidate
S       Save without advancing
PgDn    Skip (no labels saved)
PgUp    Go back to previous candidate (read-only review mode)
a       Add span (modal; prefilled from selection if any)
e       Edit selected span
d       Delete selected span
x       Toggle focused section label flag
Tab     Cycle focus: passage -> spans table -> section labels
r       Re-propose with bootstrap (background worker)
f       Flag for follow-up
N       Edit per-passage note (free-form text; rides on the saved record)
F12     Snapshot full TUI state to data/labeled/.tui_snapshot.json
?       Help overlay
q       Quit (warns if unsaved edits)

Passage panel (focus required)
------------------------------
h/j/k/l, Arrows  Move cursor
w / b            Word forward / back
W / B            WORD forward / back (whitespace-delimited)
e / E            End of word / WORD
0 / $            Line start / end
g g / G          Document start / end
f<c> / F<c>      Find char forward / back on current visual line
t<c> / T<c>      Until char forward / back on current visual line
<N>motion        Repeat motion N times (e.g. 3w, 12l)
v / Space        Toggle visual selection mode
Escape           Clear visual selection
Mouse drag       Select character range
"""

from __future__ import annotations

import argparse
import json
import os
import datetime
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Input,
    Label,
    Select,
    Static,
)

from nlp.bootstrap import _resolve_offsets
from nlp.schema import (
    LAYER_A_LABELS,
    LAYER_B_LABELS,
    SCHEMA_VERSION,
    SECTION_LABELS,
    SectionRecord,
    SpanAnnotation,
    SpanRecord,
)
from nlp.tui.candidates import Candidate, QueueState
from nlp.tui.passage_view import PassageView
from nlp.tui.persist import JsonlAnnotationStore, TuiWal
from nlp.tui.proposals import ProposalResult, propose_async

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_JSONL = Path("data/labeled/spans/pilot.jsonl")
DEFAULT_WAL = Path("data/labeled/.tui_wal.jsonl")
# Fixed location for the F12 snapshot. The user (or someone reviewing the
# session) can dump full TUI state to this file with one keypress and
# point Claude at it via "look at the snapshot" — no path needed.
SNAPSHOT_PATH = Path("data/labeled/.tui_snapshot.json")

# ---------------------------------------------------------------------------
# Helper: build Rich markup for passage with span highlights
# ---------------------------------------------------------------------------

_LAYER_A_COLOR = "bold green"
_LAYER_B_COLOR = "bold cyan"


def _render_passage(text: str, spans: list[dict[str, Any]]) -> str:
    """Return Rich markup string for *text* with span brackets.

    Layer-A spans rendered with ``⟦ ⟧``, layer-B with ``⟪ ⟫``.
    Overlapping brackets from different layers are handled by inserting
    bracket markers at all span start/end positions, sorted by offset.
    """
    if not spans:
        return text

    # Build sorted list of (offset, kind) events
    # kind: "A_open", "A_close", "B_open", "B_close"
    events: list[tuple[int, str]] = []
    for sp in spans:
        layer = sp.get("layer", "A")
        start = sp.get("start", 0)
        end = sp.get("end", 0)
        events.append((start, f"{layer}_open"))
        events.append((end, f"{layer}_close"))

    # Sort: closes before opens at same offset so brackets don't cross weirdly
    events.sort(key=lambda e: (e[0], 0 if "close" in e[1] else 1))

    parts: list[str] = []
    prev = 0
    for offset, kind in events:
        if offset > prev:
            # Escape Rich markup characters in plain text
            chunk = text[prev:offset]
            chunk = chunk.replace("[", r"\[")
            parts.append(chunk)
        if kind == "A_open":
            parts.append(f"[{_LAYER_A_COLOR}]⟦[/{_LAYER_A_COLOR}]")
        elif kind == "A_close":
            parts.append(f"[{_LAYER_A_COLOR}]⟧[/{_LAYER_A_COLOR}]")
        elif kind == "B_open":
            parts.append(f"[{_LAYER_B_COLOR}]⟪[/{_LAYER_B_COLOR}]")
        elif kind == "B_close":
            parts.append(f"[{_LAYER_B_COLOR}]⟫[/{_LAYER_B_COLOR}]")
        prev = offset

    # Trailing text
    if prev < len(text):
        chunk = text[prev:]
        chunk = chunk.replace("[", r"\[")
        parts.append(chunk)

    return "".join(parts)


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


def _diff_counts(
    original_spans: list[dict[str, Any]],
    current_spans: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Return (added, removed, edited) counts vs the original proposal."""

    def _key(sp: dict[str, Any]) -> tuple:
        return (sp.get("layer"), sp.get("label"), sp.get("start"), sp.get("end"))

    orig_keys = {_key(s) for s in original_spans}
    curr_keys = {_key(s) for s in current_spans}
    added = len(curr_keys - orig_keys)
    removed = len(orig_keys - curr_keys)
    # "edited" is hard to track without IDs; we report 0 for now
    return added, removed, 0


# ---------------------------------------------------------------------------
# Modal screens
# ---------------------------------------------------------------------------


class HelpScreen(ModalScreen):
    """Help overlay — lists all keybindings and label definitions."""

    BINDINGS = [Binding("q,escape,?", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "[bold]BCF Annotation TUI — Help[/bold]\n\n"
                "[bold]Global keybindings[/bold]\n"
                "  s       Save & advance\n"
                "  S       Save without advancing\n"
                "  PgDn    Skip (no labels saved)\n"
                "  PgUp    Go back (read-only review)\n"
                "  a       Add span (uses passage selection if any)\n"
                "  e       Edit selected span\n"
                "  d       Delete selected span\n"
                "  x       Toggle focused section flag\n"
                "  Tab     Cycle focus areas\n"
                "  r       Re-propose (background)\n"
                "  f       Flag for follow-up\n"
                "  N       Edit per-passage note\n"
                "  F12     Snapshot state to .tui_snapshot.json\n"
                "  ?       This help screen\n"
                "  q       Quit\n\n"
                "[bold]Passage panel (when focused)[/bold]\n"
                "  h/l, Left/Right  Move cursor by 1 char\n"
                "  j/k, Down/Up     Move cursor by 1 line\n"
                "  w / b            Word forward / back\n"
                "  W / B            WORD forward / back (whitespace-delimited)\n"
                "  e / E            End of word / WORD\n"
                "  0 / $            Line start / end\n"
                "  g g / G          Document start / end\n"
                "  f<c> / F<c>      Find char forward / back on line\n"
                "  t<c> / T<c>      Until char forward / back on line\n"
                "  N (digits)       Count prefix: e.g. 3w, 5j, 12l\n"
                "  v / Space        Toggle visual selection mode\n"
                "  Escape           Clear visual selection\n"
                "  Mouse drag       Select character range\n"
                "  Note: while passage is focused, the App's e (edit-span)\n"
                "  and f (flag) are unavailable — Tab to the spans table\n"
                "  or section flags first, then press them.\n\n"
                "[bold]TODO phase 2[/bold]\n"
                "  l/L     Cycle layer label on selected span\n"
                "  R       Re-propose with custom addendum\n\n"
                "[bold]Layer A labels (events)[/bold]\n"
                + "".join(f"  {l}\n" for l in LAYER_A_LABELS)
                + "\n[bold]Layer B labels (entities)[/bold]\n"
                + "".join(f"  {l}\n" for l in LAYER_B_LABELS),
                markup=True,
            ),
            Button("Close", id="close_help"),
            id="help_dialog",
        )

    @on(Button.Pressed, "#close_help")
    def _close(self) -> None:
        self.dismiss()


class SpanModal(ModalScreen):
    """Modal for adding or editing a span.

    The user supplies the verbatim substring of the passage to label;
    start/end offsets are resolved automatically. Returns a dict with
    keys: layer, label, start, end — or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        # Enter always submits the modal regardless of which child has
        # focus. Using priority=True intercepts before Select/Input can
        # consume Enter (Select would otherwise open its dropdown).
        # To open a Select dropdown the user clicks it or arrows down.
        Binding("enter", "submit", "OK", priority=True),
    ]

    def __init__(
        self,
        *,
        layer: str = "A",
        label: str = "",
        start: int = 0,
        end: int = 0,
        title: str = "Add Span",
        passage_text: str = "",
        selected_text: str = "",
    ) -> None:
        super().__init__()
        self._init_layer = layer
        self._init_label = label
        self._init_start = start
        self._init_end = end
        self._title = title
        self._passage_text = passage_text
        self._selected_text = selected_text

    def compose(self) -> ComposeResult:
        layer_opts = [("A — event", "A"), ("B — entity", "B")]
        label_opts_a = [(l, l) for l in LAYER_A_LABELS]
        label_opts_b = [(l, l) for l in LAYER_B_LABELS]
        all_label_opts = label_opts_a + label_opts_b

        # Prefill priority:
        #   1. Live PassageView selection (if non-empty) — overrides everything.
        #   2. Existing span substring when editing.
        #   3. Empty for a fresh add.
        prefill = ""
        if self._selected_text:
            prefill = self._selected_text
        elif (
            self._passage_text
            and 0 <= self._init_start < self._init_end <= len(self._passage_text)
        ):
            prefill = self._passage_text[self._init_start:self._init_end]

        yield Container(
            Static(f"[bold]{self._title}[/bold]", markup=True),
            Static(
                "Mnemonics (any time focus is NOT on the Text input):  "
                "[bold]A[/bold]/[bold]B[/bold] = Layer  •  "
                "[bold]h[/bold]=HIT  [bold]m[/bold]=MISS  "
                "[bold]p[/bold]=Perk  [bold]c[/bold]=Constellation  "
                "[bold]s[/bold]=preSence  [bold]d[/bold]=Date  "
                "[bold]t[/bold]=Time  [bold]u[/bold]=dUration  "
                "[bold]f[/bold]=Flashback  [bold]l[/bold]=diLation  "
                "[bold]n[/bold]=Note",
                id="span_mnemonics",
                markup=True,
            ),
            Label("Layer:"),
            Select(
                layer_opts,
                value=self._init_layer,
                id="span_layer",
            ),
            Label("Label:"),
            Select(
                all_label_opts,
                value=self._init_label if self._init_label else LAYER_A_LABELS[0],
                id="span_label",
            ),
            Label("Text (paste/type the verbatim substring from the passage):"),
            Input(value=prefill, id="span_text"),
            Static("", id="span_error", markup=True),
            Horizontal(
                Button("OK", id="span_ok", variant="primary"),
                Button("Cancel", id="span_cancel"),
                id="span_buttons",
            ),
            id="span_dialog",
        )

    # Mnemonic shortcuts for the Layer/Label Select widgets. Implemented as
    # a key event handler (rather than BINDINGS) so that when focus is on
    # the Text input, character keys flow to typing instead of being
    # consumed by mnemonics.
    _LAYER_MNEMONICS = {"a": "A", "b": "B"}
    _LABEL_MNEMONICS = {
        "h": "ROLL_HIT",
        "m": "ROLL_MISS",
        "p": "PERK_REFERENCE",
        "c": "CONSTELLATION_REFERENCE",
        "s": "PRESENCE_ACTION",
        "d": "DATE_REF",
        "t": "TIME_OF_DAY",
        "u": "DURATION",
        "f": "FLASHBACK_CUE",
        "l": "DILATION_CUE",
        "n": "AUTHOR_NOTE",
    }

    def on_key(self, event: events.Key) -> None:
        # If focus is on the Text input, let the key flow through to typing.
        focused = self.focused
        if isinstance(focused, Input):
            return

        key = (event.key or "").lower()
        if key in self._LAYER_MNEMONICS:
            try:
                self.query_one("#span_layer", Select).value = self._LAYER_MNEMONICS[key]
            except NoMatches:
                pass
            event.stop()
        elif key in self._LABEL_MNEMONICS:
            try:
                self.query_one("#span_label", Select).value = self._LABEL_MNEMONICS[key]
            except NoMatches:
                pass
            event.stop()

    def _show_error(self, msg: str) -> None:
        try:
            self.query_one("#span_error", Static).update(f"[red]{msg}[/red]")
        except NoMatches:
            pass

    @on(Button.Pressed, "#span_ok")
    def _ok(self) -> None:
        try:
            layer = str(self.query_one("#span_layer", Select).value)
            label = str(self.query_one("#span_label", Select).value)
            declared_text = self.query_one("#span_text", Input).value or ""
        except NoMatches:
            return

        declared_text = declared_text.strip("\n")
        if not declared_text:
            self._show_error("Text is empty — paste/type the passage substring to label.")
            return

        # Use the prefilled span's start as the disambiguation hint when
        # multiple matches exist; otherwise fall back to None.
        hint_start: int | None
        if (
            self._passage_text
            and 0 <= self._init_start < self._init_end <= len(self._passage_text)
        ):
            hint_start = self._init_start
        else:
            hint_start = None

        resolved = _resolve_offsets(self._passage_text, declared_text, hint_start)
        if resolved is None:
            self._show_error(
                "Text not found in passage. Check capitalization, punctuation, and whitespace."
            )
            return
        start, end = resolved
        self.dismiss({"layer": layer, "label": label, "start": start, "end": end})

    @on(Button.Pressed, "#span_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        """Enter-key submit — equivalent to clicking OK."""
        self._ok()


class NotesModal(ModalScreen):
    """Modal for editing the per-passage free-form note.

    A single-line input prefilled with the current note. OK saves;
    Escape cancels. Returns the new note string on save, or None on
    cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "OK", priority=True),
    ]

    def __init__(self, *, passage_id: str, current_note: str = "") -> None:
        super().__init__()
        self._passage_id = passage_id
        self._current_note = current_note

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                f"[bold]Note for {self._passage_id}[/bold]",
                id="notes_title",
                markup=True,
            ),
            Label("Note (free-form; OK to save, Esc to cancel):"),
            Input(value=self._current_note, id="notes_input"),
            Horizontal(
                Button("OK", id="notes_ok", variant="primary"),
                Button("Cancel", id="notes_cancel"),
                id="notes_buttons",
            ),
            id="notes_dialog",
        )

    def on_mount(self) -> None:
        try:
            self.query_one("#notes_input", Input).focus()
        except NoMatches:
            pass

    @on(Button.Pressed, "#notes_ok")
    def _ok(self) -> None:
        try:
            value = self.query_one("#notes_input", Input).value or ""
        except NoMatches:
            value = self._current_note
        self.dismiss(value)

    @on(Input.Submitted, "#notes_input")
    def _submit(self, event: Input.Submitted) -> None:
        self.dismiss(event.value or "")

    @on(Button.Pressed, "#notes_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        """Enter-key submit — equivalent to clicking OK."""
        self._ok()


class QuitConfirmScreen(ModalScreen):
    """Quit confirmation when there are unsaved changes."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "[bold yellow]Unsaved changes![/bold yellow]\n\n"
                "The current passage has unsaved edits.\n"
                "Are you sure you want to quit?",
                markup=True,
            ),
            Horizontal(
                Button("Quit anyway", id="quit_yes", variant="error"),
                Button("Cancel", id="quit_no"),
                id="quit_buttons",
            ),
            id="quit_dialog",
        )

    @on(Button.Pressed, "#quit_yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#quit_no")
    def _no(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class WalRestoreScreen(ModalScreen):
    """Offer to restore WAL state after a crash."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Container(
            Static(
                "[bold yellow]Crash recovery[/bold yellow]\n\n"
                "An unfinished annotation session was found.\n"
                "Would you like to restore the in-progress work?",
                markup=True,
            ),
            Horizontal(
                Button("Restore", id="wal_yes", variant="primary"),
                Button("Discard", id="wal_no", variant="error"),
                id="wal_buttons",
            ),
            id="wal_dialog",
        )

    @on(Button.Pressed, "#wal_yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#wal_no")
    def _no(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------


class BcfAnnotationApp(App):
    """BCF Annotation TUI — single-screen Textual app for span labeling."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #header_bar {
        height: 4;
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
    }

    #header_line1, #header_line2 {
        height: 1;
    }

    #passage_container {
        height: 12;
        border: solid $primary;
        padding: 0 1;
        overflow-y: scroll;
    }

    #passage_view {
        height: auto;
    }

    #spans_container {
        height: 8;
        border: solid $primary;
    }

    #spans_label {
        height: 1;
        background: $primary-darken-1;
        padding: 0 1;
    }

    #spans_table {
        height: 7;
    }

    #section_container {
        height: 6;
        border: solid $primary;
        padding: 0 1;
    }

    #section_label_header {
        height: 1;
        background: $primary-darken-1;
    }

    #section_checkboxes {
        height: 5;
        layout: grid;
        grid-size: 4;
        grid-gutter: 0;
    }

    #section_checkboxes Checkbox {
        background: transparent;
        color: $text;
        border: none;
        height: 1;
        padding: 0 1;
    }

    #section_checkboxes Checkbox:focus {
        background: $accent 30%;
        color: $text;
        text-style: bold;
    }

    #section_checkboxes Checkbox.-on {
        color: $success;
        text-style: bold;
    }

    #status_container {
        height: 4;
        border: solid $accent;
        padding: 0 1;
    }

    #status_line1, #status_line2 {
        height: 1;
    }

    HelpScreen, SpanModal, NotesModal, QuitConfirmScreen, WalRestoreScreen {
        align: center middle;
    }

    #help_dialog, #span_dialog, #notes_dialog, #quit_dialog, #wal_dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }

    #span_buttons, #notes_buttons, #quit_buttons, #wal_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("s", "save_and_advance", "save&next", show=True),
        Binding("S", "save_only", "save", show=True),
        # K/B reclaimed for vim (lowercase k/j = cursor up/down already; the
        # capital B is now used by PassageView as "WORD back" — whitespace-
        # delimited word motion). Queue navigation moves to PageDown/PageUp.
        Binding("pagedown", "skip", "skip", show=True),
        Binding("pageup", "go_back", "back", show=True),
        Binding("a", "add_span", "add span", show=True),
        Binding("e", "edit_span", "edit span", show=True),
        Binding("d", "delete_span", "del span", show=True),
        Binding("x", "toggle_section_flag", "toggle flag", show=True),
        Binding("r", "re_propose", "re-propose", show=True),
        Binding("f", "flag", "flag", show=False),
        Binding("N", "edit_note", "note", show=True),
        Binding("f12", "snapshot", "snapshot", show=True),
        Binding("question_mark", "help", "help", show=True),
        Binding("q", "quit_safe", "quit", show=True),
    ]

    # Reactive state
    _status_msg: reactive[str] = reactive("")
    _proposal_pending: reactive[bool] = reactive(False)
    _dirty: reactive[bool] = reactive(False)
    _last_save_ts: reactive[float] = reactive(0.0)

    def __init__(
        self,
        jsonl_path: Path = DEFAULT_JSONL,
        wal_path: Path = DEFAULT_WAL,
        annotator: str = "annotator",
        strategy: str = "balanced",
        default_model: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._jsonl_path = jsonl_path
        self._wal_path = wal_path
        self._annotator = annotator
        self._default_model = default_model

        # Persistence objects
        self._store = JsonlAnnotationStore(jsonl_path)
        self._wal = TuiWal(wal_path)

        # Queue
        self._queue = QueueState(
            strategy=strategy,
            jsonl_path=jsonl_path,
        )
        self._queue.load_state()
        # Seed the queue's last-used model so the first `r` press has one.
        if default_model and not getattr(self._queue, "_last_model", ""):
            self._queue._last_model = default_model

        # Per-passage working state
        self._current: Candidate | None = None
        self._working_spans: list[dict[str, Any]] = []
        self._proposal_spans: list[dict[str, Any]] = []  # original from LLM
        self._section_flags: dict[str, bool] = {k: False for k in SECTION_LABELS}

        # Section data
        self._section_header: str = ""
        self._section_first_chars: str = ""
        self._section_word_count: int = 0

        # Proposal metadata
        self._proposal_model: str = ""
        self._proposal_score: float | None = None

        # Per-passage free-form note (rides on the saved SpanRecord).
        # Hydrated from any existing record on candidate load; cleared
        # to "" when there is no prior record.
        self._current_note: str = ""

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        # Header
        yield Container(
            Static("", id="header_line1"),
            Static("", id="header_line2"),
            id="header_bar",
        )

        # Passage view — interactive widget with cursor + selection.
        yield ScrollableContainer(
            PassageView("", id="passage_view"),
            id="passage_container",
        )

        # Spans table
        yield Container(
            Static(" Spans", id="spans_label"),
            DataTable(id="spans_table"),
            id="spans_container",
        )

        # Section labels (checkboxes)
        yield Container(
            Static(" Section labels", id="section_label_header"),
            Container(
                *[Checkbox(label, False, id=f"sec_{label}") for label in SECTION_LABELS],
                id="section_checkboxes",
            ),
            id="section_container",
        )

        # Status bar
        yield Container(
            Static("", id="status_line1"),
            Static("", id="status_line2"),
            id="status_container",
        )

        yield Footer()

    # ------------------------------------------------------------------
    # App lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        # Configure spans table columns
        table = self.query_one("#spans_table", DataTable)
        table.add_columns("#", "L", "Label", "start", "end", "text")
        table.cursor_type = "row"

        # Always fill the queue first. Previously this was inside the
        # else-branch of the WAL check, so accepting a WAL restore left
        # the queue empty (total=0), and any subsequent K/skip dropped
        # _current to None — leaving the user stuck at "[0/0] No candidate
        # loaded" with no way out short of relaunch.
        self._init_queue()

        # Check WAL for crash recovery
        if self._wal.has_unflushed():
            self.push_screen(WalRestoreScreen(), self._handle_wal_restore)

        # Initial focus: passage panel — so vim motions work without Tab.
        try:
            self.query_one("#passage_view", PassageView).focus()
        except NoMatches:
            pass

    def _handle_wal_restore(self, restore: bool) -> None:
        # Queue is already filled by on_mount; we only need to handle the
        # WAL snapshot itself here. If the user accepts restore, layer the
        # snapshot's in-progress edits on top of the queue's current
        # candidate. If they decline, just clear the WAL — the queue's
        # default candidate (set by _init_queue) is fine.
        if restore:
            snapshot = self._wal.restore()
            if snapshot:
                self._restore_from_snapshot(snapshot)
                self._update_all_widgets()
                self._set_status("Restored from crash WAL.")
                return
        self._wal.clear()

    def _restore_from_snapshot(self, snapshot: dict[str, Any]) -> None:
        """Restore in-progress work from a WAL snapshot."""
        passage_id = snapshot.get("passage_id", "")
        # Find the candidate in the queue or create a stub
        # The snapshot stores all we need to rebuild
        chapter_num = snapshot.get("chapter_num", "")
        section_index = snapshot.get("section_index", 0)
        text = snapshot.get("text", "")
        source = snapshot.get("source", "manual")

        self._current = Candidate(
            passage_id=passage_id,
            chapter_num=chapter_num,
            section_index=section_index,
            epub_char_start=snapshot.get("epub_char_start", 0),
            epub_char_end=snapshot.get("epub_char_end", 0),
            text=text,
            source=source,
        )
        self._working_spans = snapshot.get("spans", [])
        self._proposal_spans = snapshot.get("proposal_spans", [])
        self._section_flags = snapshot.get("section_flags", {k: False for k in SECTION_LABELS})
        self._proposal_model = snapshot.get("proposal_model", "")
        self._current_note = snapshot.get("note", "") or ""
        self._dirty = True

    def _init_queue(self) -> None:
        """Fill queue from candidates and load first item.

        Note: previously-saved passages are NOT filtered out of the queue.
        That filter caused two problems: (1) ``B`` (go back) couldn't reach
        already-saved candidates, since they were excluded from the queue
        entirely; (2) if proposals were dropped at save time (e.g. by an
        upstream bug), the user couldn't revisit the affected records to
        re-propose. Keeping all candidates in the queue lets ``B`` revisit
        any prior save; ``_load_candidate`` already pulls saved spans from
        the JSONL store via ``by_passage_id`` so revisits show what's on
        disk.
        """
        added = self._queue.fill_queue()

        # Preload synthetic candidates if queue is still empty (no real data)
        if self._queue.total == 0:
            self._set_status(
                f"Queue empty (filled {added} candidates). "
                "Add real candidates or use smoke script."
            )
        else:
            self._load_candidate(self._queue.current)

    # ------------------------------------------------------------------
    # Candidate loading
    # ------------------------------------------------------------------

    @staticmethod
    def _default_section_flags(cand: Candidate) -> dict[str, bool]:
        """Return smart defaults for section flags based on the candidate.

        Rules (initial values only — the labeler is free to flip any flag):
          * pov_joe defaults True unless the section header signals a
            non-Joe POV. Headers like "Interlude X", "Addendum X",
            "Side Story X" name the POV character; if X is "Joe" (or
            absent), it's still Joe POV. So "Interlude Weld" → non-Joe
            but "Addendum Joe" → Joe POV.
          * joe_on_screen defaults to pov_joe (Joe narrating implies he's
            present).
          * time_real defaults True (current-narrative-present is the most
            common time mode).
          * counts_for_cp defaults True when pov_joe is True (legacy
            CP-eligibility rule).
          * All other flags default False.
        """
        flags = {k: False for k in SECTION_LABELS}
        header = (getattr(cand, "section_header", "") or "").strip().lower()

        # Strip the marker prefix to inspect the named character (if any).
        # E.g. "Addendum Joe" → "joe", "Interlude Weld" → "weld",
        # "Side Story Apeiron" → "apeiron", "Interlude" alone → "".
        named: str | None = None
        for marker in ("interlude", "addendum", "side story"):
            if header.startswith(marker):
                named = header[len(marker):].strip().strip("—-:").strip()
                break

        if named is None:
            # No marker → default Joe-POV section.
            is_joe_pov = True
        else:
            # Marker present. If the named character is Joe (or unnamed),
            # it's still Joe POV. Anything else is non-Joe POV.
            is_joe_pov = named in ("", "joe")

        flags["pov_joe"] = is_joe_pov
        flags["joe_on_screen"] = is_joe_pov
        flags["time_real"] = True
        flags["counts_for_cp"] = is_joe_pov
        return flags

    def _load_candidate(self, cand: Candidate | None) -> None:
        if cand is None:
            self._current = None
            self._working_spans = []
            self._proposal_spans = []
            self._section_flags = {k: False for k in SECTION_LABELS}
            self._current_note = ""
            self._update_all_widgets()
            self._set_status("No more candidates in queue.")
            return

        self._current = cand
        self._dirty = False

        # Check if already labeled — load existing spans + note
        existing = self._store.by_passage_id(cand.passage_id)
        if existing:
            self._working_spans = [s.model_dump() for s in existing.spans]
            self._proposal_spans = list(self._working_spans)
            self._current_note = getattr(existing, "notes", "") or ""
        else:
            self._working_spans = []
            self._proposal_spans = []
            self._current_note = ""

        # Section flags: apply smart defaults from the candidate's section
        # header. Saved-section-flag readback isn't implemented — the
        # SectionRecord is persisted to a separate file and not joined
        # back here on reload. This is acceptable for pilot phase since
        # revisits are rare; pulling the flags back from disk is a TODO.
        self._section_flags = self._default_section_flags(cand)

        self._proposal_model = ""
        self._proposal_score = None

        self._update_all_widgets()
        self._set_status(
            f"Loaded {cand.passage_id}. "
            f"Press 'r' to request proposals, 's' to save."
        )

    # ------------------------------------------------------------------
    # Widget update helpers
    # ------------------------------------------------------------------

    def _update_all_widgets(self) -> None:
        self._update_header()
        self._update_passage_view()
        self._update_spans_table()
        self._update_section_checkboxes()
        self._update_status()

    def _update_header(self) -> None:
        cand = self._current
        q = self._queue
        fname = self._jsonl_path.name

        if cand:
            chapter_title = getattr(cand, "chapter_title", "") or ""
            section_header = getattr(cand, "section_header", "") or ""
            # Build a "POV hint" tag from the section header. Headers like
            # "Addendum Joe" or "Interlude Joe" still mark Joe POV (the
            # marker names the focal character, not necessarily a non-Joe
            # speaker). Only flag NON-Joe markers as yellow.
            header_lower = section_header.strip().lower()
            named: str | None = None
            for marker in ("interlude", "addendum", "side story"):
                if header_lower.startswith(marker):
                    named = header_lower[len(marker):].strip().strip("—-:").strip()
                    break

            if named is None:
                # No special marker → presumed Joe POV.
                pov_tag = "[green]Joe POV (presumed)[/green]"
            elif named in ("", "joe"):
                # "Addendum Joe" / "Interlude" with no name → Joe POV.
                pov_tag = "[green]Joe POV (presumed)[/green]"
            elif "interlude" in header_lower:
                pov_tag = f"[yellow]INTERLUDE ({named.title()})[/yellow]"
            elif "addendum" in header_lower:
                pov_tag = f"[yellow]ADDENDUM ({named.title()})[/yellow]"
            elif "side story" in header_lower:
                pov_tag = f"[yellow]SIDE STORY ({named.title()})[/yellow]"
            elif section_header:
                pov_tag = "[green]Joe POV (presumed)[/green]"
            else:
                # No section header — typically the chapter's primary section,
                # which is Joe POV.
                pov_tag = "[green]Joe POV (presumed)[/green]"

            title_str = f' "{chapter_title}"' if chapter_title else ""
            section_str = f' / "{section_header}"' if section_header else ""
            line1 = (
                f"[bold] BCF Annotation TUI — {fname}[/bold]"
                f"  [{q.position}/{q.total}]"
                f"{title_str}{section_str}  {pov_tag}"
            )
            line2 = (
                f" ch{cand.chapter_num} sec {cand.section_index}"
                f"  passage_id {cand.passage_id}"
                f"  strategy: {q.strategy}"
                f"  source: {cand.source}"
            )
            if self._proposal_score is not None:
                line2 += f"  confidence: {self._proposal_score:.2f}"
            if self._current_note:
                # Use a plain bracketed token; emoji rendering varies by terminal.
                line2 += "  [bold yellow][note][/bold yellow]"
        else:
            line1 = f"[bold] BCF Annotation TUI — {fname}[/bold]  [0/0]"
            line2 = " No candidate loaded"

        try:
            self.query_one("#header_line1", Static).update(line1)
            self.query_one("#header_line2", Static).update(line2)
        except NoMatches:
            pass

    def _update_passage_view(self) -> None:
        try:
            view = self.query_one("#passage_view", PassageView)
        except NoMatches:
            return
        cand = self._current
        if cand is None:
            view.set_text("", spans=[])
            return
        # Only reset cursor / selection when the underlying text changed.
        if view.text != cand.text:
            view.set_text(cand.text, spans=self._working_spans)
        else:
            view.set_spans(self._working_spans)

    def _update_spans_table(self) -> None:
        try:
            table = self.query_one("#spans_table", DataTable)
        except NoMatches:
            return
        table.clear()
        for i, sp in enumerate(self._working_spans, 1):
            layer = sp.get("layer", "?")
            label = sp.get("label", "?")
            start = sp.get("start", 0)
            end = sp.get("end", 0)
            text = sp.get("text", "")
            if not text and self._current:
                text = self._current.text[start:end]
            # Truncate display text
            display_text = text[:30] + "…" if len(text) > 30 else text
            table.add_row(str(i), layer, label, str(start), str(end), display_text)

    def _update_section_checkboxes(self) -> None:
        for label in SECTION_LABELS:
            try:
                cb = self.query_one(f"#sec_{label}", Checkbox)
                cb.value = self._section_flags.get(label, False)
            except NoMatches:
                pass

    def _update_status(self) -> None:
        # Diff vs proposal
        added, removed, edited = _diff_counts(self._proposal_spans, self._working_spans)
        diff_str = f"diff vs proposal: +{added} span{'s' if added != 1 else ''} -{removed}"
        if edited:
            diff_str += f" Δ{edited}"

        # Last save age
        if self._last_save_ts:
            age = time.time() - self._last_save_ts
            if age < 60:
                save_str = f"Last save {age:.1f}s ago."
            else:
                save_str = f"Last save {age/60:.0f}m ago."
        else:
            save_str = "Not saved yet."

        # Proposal source
        if self._proposal_pending:
            proposal_str = "proposal source: [pending…]"
        elif self._proposal_model:
            proposal_str = f"proposal source: {self._proposal_model}"
        else:
            proposal_str = "proposals: not requested"

        dirty_flag = " [yellow][UNSAVED][/yellow]" if self._dirty else ""

        status1 = f" {proposal_str}   {diff_str}{dirty_flag}"
        status2 = f" {save_str}  {self._status_msg}"

        try:
            self.query_one("#status_line1", Static).update(status1)
            self.query_one("#status_line2", Static).update(status2)
        except NoMatches:
            pass

    def _set_status(self, msg: str) -> None:
        self._status_msg = msg
        self._update_status()

    # ------------------------------------------------------------------
    # WAL snapshot
    # ------------------------------------------------------------------

    def _write_wal(self) -> None:
        if self._current is None:
            return
        snapshot: dict[str, Any] = {
            "passage_id": self._current.passage_id,
            "chapter_num": self._current.chapter_num,
            "section_index": self._current.section_index,
            "epub_char_start": self._current.epub_char_start,
            "epub_char_end": self._current.epub_char_end,
            "text": self._current.text,
            "source": self._current.source,
            "spans": self._working_spans,
            "proposal_spans": self._proposal_spans,
            "section_flags": self._section_flags,
            "proposal_model": self._proposal_model,
            "note": self._current_note,
        }
        self._wal.record_state(snapshot)

    # ------------------------------------------------------------------
    # Save logic
    # ------------------------------------------------------------------

    def _build_records(self) -> tuple[SpanRecord, SectionRecord | None]:
        cand = self._current
        assert cand is not None

        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Determine source kind
        if self._proposal_model:
            source = "llm_proposal_reviewed"
        elif self._proposal_spans:
            source = "corrected"
        else:
            source = "manual"

        spans = [
            SpanAnnotation(
                layer=sp["layer"],
                label=sp["label"],
                start=sp["start"],
                end=sp["end"],
            )
            for sp in self._working_spans
        ]

        span_record = SpanRecord(
            passage_id=cand.passage_id,
            chapter_num=cand.chapter_num,
            section_index=cand.section_index,
            epub_char_start=cand.epub_char_start,
            epub_char_end=cand.epub_char_end,
            text=cand.text,
            spans=spans,
            source=source,  # type: ignore[arg-type]
            model_proposal_score=self._proposal_score,
            annotator=self._annotator,
            annotated_at=now,
            notes=self._current_note,
            schema_version=SCHEMA_VERSION,
        )

        # Build section record only if we have header info
        section_record: SectionRecord | None = None
        if self._section_header:
            section_record = SectionRecord(
                chapter_num=cand.chapter_num,
                section_index=cand.section_index,
                header=self._section_header,
                first_chars=self._section_first_chars or cand.text[:3000],
                word_count=self._section_word_count or len(cand.text.split()),
                labels=self._section_flags,
                annotator=self._annotator,
                annotated_at=now,
                schema_version=SCHEMA_VERSION,
            )

        return span_record, section_record

    def _do_save(self) -> bool:
        """Save current record. Returns True on success."""
        if self._current is None:
            self._set_status("Nothing to save.")
            return False
        try:
            span_rec, sec_rec = self._build_records()
            self._store.append(span_rec, sec_rec)
            self._wal.clear()
            self._last_save_ts = time.time()
            self._dirty = False
            self._update_status()
            self._set_status(f"Saved {self._current.passage_id}.")
            return True
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Save error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Keybinding actions
    # ------------------------------------------------------------------

    def action_save_and_advance(self) -> None:
        if self._do_save():
            next_cand = self._queue.advance()
            self._load_candidate(next_cand)

    def action_save_only(self) -> None:
        self._do_save()

    def action_skip(self) -> None:
        next_cand = self._queue.skip()
        self._load_candidate(next_cand)
        self._set_status("Skipped.")

    def action_go_back(self) -> None:
        prev = self._queue.go_back()
        if prev is None:
            self._set_status("Already at first candidate.")
            return
        self._load_candidate(prev)
        self._set_status(f"Reviewing {prev.passage_id} (read-only).")

    def _passage_selection(self) -> str:
        """Return the live PassageView selection, or ``""``."""
        try:
            view = self.query_one("#passage_view", PassageView)
        except NoMatches:
            return ""
        return view.selected_text

    def _clear_passage_selection(self) -> None:
        try:
            self.query_one("#passage_view", PassageView).clear_selection()
        except NoMatches:
            pass

    def action_add_span(self) -> None:
        passage_text = self._current.text if self._current else ""
        selected = self._passage_selection()
        self.push_screen(
            SpanModal(
                title="Add Span",
                passage_text=passage_text,
                selected_text=selected,
            ),
            self._handle_add_span,
        )

    def _handle_add_span(self, result: dict[str, Any] | None) -> None:
        self._clear_passage_selection()
        if result is None:
            return
        self._working_spans.append(result)
        self._dirty = True
        self._write_wal()
        self._update_passage_view()
        self._update_spans_table()
        self._update_status()

    def action_edit_span(self) -> None:
        try:
            table = self.query_one("#spans_table", DataTable)
        except NoMatches:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._working_spans):
            self._set_status("No span selected.")
            return
        sp = self._working_spans[row_idx]
        passage_text = self._current.text if self._current else ""
        selected = self._passage_selection()
        self.push_screen(
            SpanModal(
                layer=sp.get("layer", "A"),
                label=sp.get("label", LAYER_A_LABELS[0]),
                start=sp.get("start", 0),
                end=sp.get("end", 0),
                title="Edit Span",
                passage_text=passage_text,
                selected_text=selected,
            ),
            lambda result: self._handle_edit_span(row_idx, result),
        )

    def _handle_edit_span(self, idx: int, result: dict[str, Any] | None) -> None:
        self._clear_passage_selection()
        if result is None or idx >= len(self._working_spans):
            return
        self._working_spans[idx] = result
        self._dirty = True
        self._write_wal()
        self._update_passage_view()
        self._update_spans_table()
        self._update_status()

    def action_delete_span(self) -> None:
        try:
            table = self.query_one("#spans_table", DataTable)
        except NoMatches:
            return
        row_idx = table.cursor_row
        if row_idx < 0 or row_idx >= len(self._working_spans):
            self._set_status("No span selected.")
            return
        del self._working_spans[row_idx]
        self._dirty = True
        self._write_wal()
        self._update_passage_view()
        self._update_spans_table()
        self._update_status()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_snapshot(self) -> None:
        """Dump current TUI state to ``data/labeled/.tui_snapshot.json``.

        Bound to F12. The fixed-path JSON snapshot lets the user point
        Claude at "the snapshot" without specifying a filename. Includes
        passage text, working/proposal spans, section flags, the per-
        passage note, queue position, and (where available) the passage
        view's cursor + selection. Designed for read-by-Claude, not pixel
        fidelity — it's text, not an image.
        """
        cand = self._current
        snap: dict[str, Any] = {
            "snapshot_version": 1,
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "queue": {
                "position": self._queue.position,
                "total": self._queue.total,
                "strategy": self._queue.strategy,
            },
            "candidate": None,
            "spans_working": list(self._working_spans),
            "spans_proposal": list(self._proposal_spans),
            "section_flags": dict(self._section_flags),
            "note": self._current_note,
            "proposal": {
                "model": self._proposal_model,
                "score": self._proposal_score,
                "pending": bool(self._proposal_pending),
            },
            "dirty": bool(self._dirty),
            "status_msg": self._status_msg,
        }

        if cand is not None:
            snap["candidate"] = {
                "passage_id": cand.passage_id,
                "chapter_num": cand.chapter_num,
                "section_index": cand.section_index,
                "chapter_title": getattr(cand, "chapter_title", "") or "",
                "section_header": getattr(cand, "section_header", "") or "",
                "source": cand.source,
                "epub_char_start": cand.epub_char_start,
                "epub_char_end": cand.epub_char_end,
                "text": cand.text,
                "roll_context": cand.roll_context,
            }

        # Passage view cursor / selection (best effort — widget may not be
        # mounted yet during certain modal states).
        try:
            view = self.query_one("#passage_view", PassageView)
            sel = view.selection
            snap["passage_view"] = {
                "cursor": int(view.cursor),
                "anchor": int(view.anchor) if view.anchor is not None else None,
                "visual_mode": bool(view.visual_mode),
                "selection_start": sel[0] if sel else None,
                "selection_end": sel[1] if sel else None,
                "selected_text": view.selected_text,
            }
        except (NoMatches, AttributeError):
            snap["passage_view"] = None

        try:
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT_PATH.write_text(
                json.dumps(snap, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self._set_status(f"Snapshot → {SNAPSHOT_PATH}")
        except OSError as exc:
            self._set_status(f"[red]Snapshot failed:[/red] {exc}")

    def action_toggle_section_flag(self) -> None:
        """Toggle the focused section-label checkbox.

        Bound to ``x`` (formerly ``Space``) so that ``Space`` is free for the
        passage panel's visual-mode alias.
        """
        focused = self.focused
        if isinstance(focused, Checkbox) and (focused.id or "").startswith("sec_"):
            focused.toggle()
        else:
            self._set_status("Focus a section flag (Tab) before pressing 'x'.")

    def action_flag(self) -> None:
        self._queue.flag_current()
        if self._current:
            self._set_status(f"Flagged {self._current.passage_id} for follow-up.")

    def action_edit_note(self) -> None:
        """Open the NotesModal to edit the per-passage note."""
        if self._current is None:
            self._set_status("No candidate loaded — nothing to annotate.")
            return
        self.push_screen(
            NotesModal(
                passage_id=self._current.passage_id,
                current_note=self._current_note,
            ),
            self._handle_edit_note,
        )

    def _handle_edit_note(self, result: str | None) -> None:
        if result is None:
            return
        if result == self._current_note:
            return
        self._current_note = result
        self._dirty = True
        self._write_wal()
        self._update_header()
        self._update_status()
        if result:
            self._set_status("Note updated (will save with the record).")
        else:
            self._set_status("Note cleared.")

    def action_quit_safe(self) -> None:
        if self._dirty:
            self.push_screen(QuitConfirmScreen(), self._handle_quit_confirm)
        else:
            self._perform_exit()

    def _handle_quit_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._perform_exit()

    def _perform_exit(self) -> None:
        """Best-effort cleanup before exiting the app.

        Renamed from ``_shutdown`` because Textual's :class:`App` defines an
        async ``_shutdown`` coroutine that is awaited during the exit path —
        a sync override here would shadow it and raise ``TypeError`` from the
        framework, masking any real traceback.
        """
        try:
            self._queue.save_state()
        except Exception as exc:  # noqa: BLE001
            print(f"warning: queue.save_state failed: {exc}", file=sys.stderr)
        self.exit()

    # ------------------------------------------------------------------
    # Section label toggles (Space handled via Checkbox widget directly)
    # ------------------------------------------------------------------

    @on(Checkbox.Changed)
    def _on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cb_id = event.checkbox.id or ""
        if cb_id.startswith("sec_"):
            label = cb_id[4:]
            if label in self._section_flags:
                self._section_flags[label] = event.value
                self._dirty = True
                self._write_wal()
                self._update_status()

    # ------------------------------------------------------------------
    # Re-propose (background worker)
    # ------------------------------------------------------------------

    def action_re_propose(self) -> None:
        if self._current is None:
            self._set_status("No candidate loaded.")
            return
        if self._proposal_pending:
            self._set_status("Proposal already in progress…")
            return
        self._proposal_pending = True
        self._update_status()
        self._run_proposal(self._current.text, self._current.passage_id)

    @work(exclusive=True, thread=True)
    def _run_proposal(self, text: str, passage_id: str) -> None:
        """Run propose_async in a thread worker (Textual work decorator)."""
        import asyncio

        result = asyncio.run(
            propose_async(text, passage_id=passage_id, model_name=self._queue._last_model)
        )
        self.call_from_thread(self._handle_proposal_result, result)

    def _handle_proposal_result(self, result: ProposalResult) -> None:
        self._proposal_pending = False
        if result.ok:
            self._proposal_spans = list(result.spans)
            # Only protect working_spans from overwrite when the user has
            # already edited spans — i.e. there's something to clobber.
            # The previous condition `if not self._dirty` was too coarse:
            # toggling a section flag or editing a note marks _dirty=True
            # without touching spans, which silently blocked the proposal
            # from populating an empty span list.
            if not self._working_spans:
                self._working_spans = list(result.spans)
            self._proposal_model = result.model_name or "unknown"
            self._proposal_score = result.avg_confidence
            if result.model_name:
                self._queue._last_model = result.model_name
            self._update_passage_view()
            self._update_spans_table()
            self._set_status(
                f"Proposals received from {result.model_name} "
                f"({len(result.spans)} spans, {result.elapsed_s:.1f}s)."
            )
        else:
            self._set_status(f"[yellow]Proposal warning:[/yellow] {result.error}")
        self._update_status()

    # ------------------------------------------------------------------
    # Span table navigation helpers
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Just update status to confirm selection
        self._set_status(f"Selected span row {event.cursor_row + 1}.")


# ---------------------------------------------------------------------------
# __main__ entry
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m nlp.tui.app",
        description="BCF Annotation TUI — keyboard-driven span labeling for fanfic NLP.",
    )
    parser.add_argument(
        "--jsonl",
        default=str(DEFAULT_JSONL),
        help=f"Path to output JSONL file (default: {DEFAULT_JSONL})",
    )
    parser.add_argument(
        "--wal",
        default=str(DEFAULT_WAL),
        help=f"Path to WAL file (default: {DEFAULT_WAL})",
    )
    parser.add_argument(
        "--annotator",
        default="annotator",
        help="Annotator name written into records (default: annotator)",
    )
    parser.add_argument(
        "--strategy",
        choices=["balanced", "event_focused", "low_confidence", "coverage_gap"],
        default="balanced",
        help="Candidate selection strategy (default: balanced)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("BCF_LLAMACPP_MODEL", ""),
        help="llama.cpp model name to request (e.g. 'bartowski/Qwen_Qwen3-32B-GGUF:Q4_K_M'). "
        "Falls back to BCF_LLAMACPP_MODEL env var, then to the router's default.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    app = BcfAnnotationApp(
        jsonl_path=Path(args.jsonl),
        wal_path=Path(args.wal),
        annotator=args.annotator,
        strategy=args.strategy,
        default_model=args.model,
    )
    app.run()


if __name__ == "__main__":
    main()
