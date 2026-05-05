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
k       Skip (no labels saved)
b       Go back to previous candidate (read-only review mode)
a       Add span (number-entry modal for start/end + label dropdown)
e       Edit selected span
d       Delete selected span
Space   Toggle focused section label
Tab     Cycle focus: passage -> spans table -> section labels
r       Re-propose with bootstrap (background worker)
f       Flag for follow-up
?       Help overlay
q       Quit (warns if unsaved edits)

Deferred (TODO phase 2)
-----------------------
l / L   Cycle layer-A/B label on highlighted span (keyboard shortcut)
R       Re-propose with custom prompt addendum
Mouse text selection for span offset entry
Arrow key text cursor in passage view
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from textual import on, work
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
from nlp.tui.persist import JsonlAnnotationStore, TuiWal
from nlp.tui.proposals import ProposalResult, propose_async

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_JSONL = Path("data/labeled/spans/pilot.jsonl")
DEFAULT_WAL = Path("data/labeled/.tui_wal.jsonl")

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
                "[bold]Keybindings[/bold]\n"
                "  s       Save & advance\n"
                "  S       Save without advancing\n"
                "  k       Skip (no labels saved)\n"
                "  b       Go back (read-only review)\n"
                "  a       Add span (offset modal)\n"
                "  e       Edit selected span\n"
                "  d       Delete selected span\n"
                "  Space   Toggle focused section flag\n"
                "  Tab     Cycle focus areas\n"
                "  r       Re-propose (background)\n"
                "  f       Flag for follow-up\n"
                "  ?       This help screen\n"
                "  q       Quit\n\n"
                "[bold]TODO phase 2[/bold]\n"
                "  l/L     Cycle layer label on selected span\n"
                "  R       Re-propose with custom addendum\n"
                "  Mouse text selection for span offsets\n\n"
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

    Returns a dict with keys: layer, label, start, end — or None on cancel.
    """

    def __init__(
        self,
        *,
        layer: str = "A",
        label: str = "",
        start: int = 0,
        end: int = 0,
        title: str = "Add Span",
    ) -> None:
        super().__init__()
        self._init_layer = layer
        self._init_label = label
        self._init_start = start
        self._init_end = end
        self._title = title

    def compose(self) -> ComposeResult:
        layer_opts = [("A — event", "A"), ("B — entity", "B")]
        label_opts_a = [(l, l) for l in LAYER_A_LABELS]
        label_opts_b = [(l, l) for l in LAYER_B_LABELS]
        all_label_opts = label_opts_a + label_opts_b

        yield Container(
            Static(f"[bold]{self._title}[/bold]", markup=True),
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
            Label("Start offset:"),
            Input(value=str(self._init_start), id="span_start", type="integer"),
            Label("End offset:"),
            Input(value=str(self._init_end), id="span_end", type="integer"),
            Horizontal(
                Button("OK", id="span_ok", variant="primary"),
                Button("Cancel", id="span_cancel"),
                id="span_buttons",
            ),
            id="span_dialog",
        )

    @on(Button.Pressed, "#span_ok")
    def _ok(self) -> None:
        try:
            layer = str(self.query_one("#span_layer", Select).value)
            label = str(self.query_one("#span_label", Select).value)
            start = int(self.query_one("#span_start", Input).value or "0")
            end = int(self.query_one("#span_end", Input).value or "0")
        except (ValueError, NoMatches):
            return
        self.dismiss({"layer": layer, "label": label, "start": start, "end": end})

    @on(Button.Pressed, "#span_cancel")
    def _cancel(self) -> None:
        self.dismiss(None)


class QuitConfirmScreen(ModalScreen):
    """Quit confirmation when there are unsaved changes."""

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


class WalRestoreScreen(ModalScreen):
    """Offer to restore WAL state after a crash."""

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

    #status_container {
        height: 4;
        border: solid $accent;
        padding: 0 1;
    }

    #status_line1, #status_line2 {
        height: 1;
    }

    HelpScreen, SpanModal, QuitConfirmScreen, WalRestoreScreen {
        align: center middle;
    }

    #help_dialog, #span_dialog, #quit_dialog, #wal_dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }

    #span_buttons, #quit_buttons, #wal_buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("s", "save_and_advance", "save&next", show=True),
        Binding("S", "save_only", "save", show=True),
        Binding("k", "skip", "skip", show=True),
        Binding("b", "go_back", "back", show=True),
        Binding("a", "add_span", "add span", show=True),
        Binding("e", "edit_span", "edit span", show=True),
        Binding("d", "delete_span", "del span", show=True),
        Binding("r", "re_propose", "re-propose", show=True),
        Binding("f", "flag", "flag", show=False),
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
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._jsonl_path = jsonl_path
        self._wal_path = wal_path
        self._annotator = annotator

        # Persistence objects
        self._store = JsonlAnnotationStore(jsonl_path)
        self._wal = TuiWal(wal_path)

        # Queue
        self._queue = QueueState(
            strategy=strategy,
            jsonl_path=jsonl_path,
        )
        self._queue.load_state()

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

        # Passage view
        yield ScrollableContainer(
            Static("", id="passage_view", markup=True),
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

        # Check WAL for crash recovery
        if self._wal.has_unflushed():
            self.push_screen(WalRestoreScreen(), self._handle_wal_restore)
        else:
            self._init_queue()

    def _handle_wal_restore(self, restore: bool) -> None:
        if restore:
            snapshot = self._wal.restore()
            if snapshot:
                self._restore_from_snapshot(snapshot)
                self._update_all_widgets()
                self._set_status("Restored from crash WAL.")
                return
        self._wal.clear()
        self._init_queue()

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
        self._dirty = True

    def _init_queue(self) -> None:
        """Fill queue from candidates and load first item."""
        labeled = set(self._store.all_passage_ids())
        added = self._queue.fill_queue(already_labeled=labeled)

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

    def _load_candidate(self, cand: Candidate | None) -> None:
        if cand is None:
            self._current = None
            self._working_spans = []
            self._proposal_spans = []
            self._section_flags = {k: False for k in SECTION_LABELS}
            self._update_all_widgets()
            self._set_status("No more candidates in queue.")
            return

        self._current = cand
        self._dirty = False

        # Check if already labeled — load existing spans
        existing = self._store.by_passage_id(cand.passage_id)
        if existing:
            self._working_spans = [s.model_dump() for s in existing.spans]
            self._proposal_spans = list(self._working_spans)
        else:
            self._working_spans = []
            self._proposal_spans = []

        # Reset section flags
        self._section_flags = {k: False for k in SECTION_LABELS}

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
            line1 = (
                f"[bold] BCF Annotation TUI — {fname}[/bold]"
                f"  [{q.position}/{q.total}]"
            )
            line2 = (
                f" ch{cand.chapter_num} sec {cand.section_index}"
                f"  passage_id {cand.passage_id}"
                f"  strategy: {q.strategy}"
                f"  source: {cand.source}"
            )
            if self._proposal_score is not None:
                line2 += f"  confidence: {self._proposal_score:.2f}"
        else:
            line1 = f"[bold] BCF Annotation TUI — {fname}[/bold]  [0/0]"
            line2 = " No candidate loaded"

        try:
            self.query_one("#header_line1", Static).update(line1)
            self.query_one("#header_line2", Static).update(line2)
        except NoMatches:
            pass

    def _update_passage_view(self) -> None:
        cand = self._current
        if cand is None:
            text = "[dim]No passage loaded.[/dim]"
        else:
            text = _render_passage(cand.text, self._working_spans)
            text += "\n\n[dim]⟦ ⟧ = layer A (event)   ⟪ ⟫ = layer B (entity)[/dim]"
        try:
            self.query_one("#passage_view", Static).update(text)
        except NoMatches:
            pass

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

    def action_add_span(self) -> None:
        self.push_screen(
            SpanModal(title="Add Span"),
            self._handle_add_span,
        )

    def _handle_add_span(self, result: dict[str, Any] | None) -> None:
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
        self.push_screen(
            SpanModal(
                layer=sp.get("layer", "A"),
                label=sp.get("label", LAYER_A_LABELS[0]),
                start=sp.get("start", 0),
                end=sp.get("end", 0),
                title="Edit Span",
            ),
            lambda result: self._handle_edit_span(row_idx, result),
        )

    def _handle_edit_span(self, idx: int, result: dict[str, Any] | None) -> None:
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

    def action_flag(self) -> None:
        self._queue.flag_current()
        if self._current:
            self._set_status(f"Flagged {self._current.passage_id} for follow-up.")

    def action_quit_safe(self) -> None:
        if self._dirty:
            self.push_screen(QuitConfirmScreen(), self._handle_quit_confirm)
        else:
            self._shutdown()

    def _handle_quit_confirm(self, confirmed: bool) -> None:
        if confirmed:
            self._shutdown()

    def _shutdown(self) -> None:
        self._queue.save_state()
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
            # Only replace working spans if they haven't been edited
            if not self._dirty:
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    app = BcfAnnotationApp(
        jsonl_path=Path(args.jsonl),
        wal_path=Path(args.wal),
        annotator=args.annotator,
        strategy=args.strategy,
    )
    app.run()


if __name__ == "__main__":
    main()
