"""PassageView — interactive passage display with cursor + selection.

A custom Textual widget used by the BCF Annotation TUI that replaces the
plain ``Static`` previously used to display the passage. It supports:

* A visible character cursor (rendered as inverse-video).
* A character-wise selection range, highlighted with the accent style.
* Mouse click-and-drag to select a range.
* Vim-style keyboard motions when the widget has focus:
    h/j/k/l, Left/Down/Up/Right
    w / W  (word / WORD forward)
    b      (word back)
    e / E  (end of word / WORD)
    0 / $  (line start / end)
    g g (top), G (bottom)
    f<c>/F<c>  find char forward/back on current visual line
    t<c>/T<c>  until char forward/back on current visual line
    <count><motion>  repeat motion (e.g. ``3w`` = three words forward)
    v / Space (toggle visual mode), Escape (clear visual mode + selection)

The host App reads the current selection via :pyattr:`selection` /
:pyattr:`selected_text` and feeds it into ``SpanModal``.

The widget renders by *wrapping* the passage text to its content width.
Wrapping is recomputed when ``text`` changes or the widget resizes.
Mouse coordinates map back to character offsets through the cached wrap
geometry.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.geometry import Size
from textual.reactive import reactive
from textual.widget import Widget


# Regex for word boundaries — vim-ish: a word is a run of word chars.
_WORD = re.compile(r"\w+")
_WORD_CHAR = re.compile(r"\w")
# A WORD (vim-uppercase) is a run of non-whitespace characters.
_BIGWORD = re.compile(r"\S+")

# Layer styles applied to existing-span text (background colors so the
# character offsets remain stable — no bracket characters are inserted).
_LAYER_A_STYLE = "bold green"
_LAYER_B_STYLE = "bold cyan"


class PassageView(Widget, can_focus=True):
    """Interactive passage display with cursor, selection, and vim motions."""

    DEFAULT_CSS = """
    PassageView {
        height: auto;
        min-height: 1;
        padding: 0 0;
    }
    PassageView:focus {
        /* No outline change — host container already has a border. */
    }
    """

    # Keyboard bindings only fire when the widget has focus.
    #
    # NOTE: digits, ``f``/``F``/``t``/``T``, ``g`` and ``0`` (when a count is
    # pending) are handled in :meth:`on_key` rather than via bindings, because
    # they participate in stateful key sequences that bindings can't express.
    # The arrow / vim-letter motions remain as bindings so the test suite can
    # exercise the underlying ``action_*`` methods directly without going
    # through the Textual key dispatcher.
    BINDINGS = [
        # Movement
        Binding("h", "move_left", "left", show=False),
        Binding("left", "move_left", "left", show=False),
        Binding("l", "move_right", "right", show=False),
        Binding("right", "move_right", "right", show=False),
        Binding("j", "move_down", "down", show=False),
        Binding("down", "move_down", "down", show=False),
        Binding("k", "move_up", "up", show=False),
        Binding("up", "move_up", "up", show=False),
        Binding("w", "word_forward", "word forward", show=False),
        Binding("W", "WORD_forward", "WORD forward", show=False),
        Binding("b", "word_back", "word back", show=False),
        Binding("B", "WORD_back", "WORD back", show=False),
        Binding("e", "end_of_word", "end of word", show=False),
        Binding("E", "end_of_WORD", "end of WORD", show=False),
        Binding("dollar_sign", "line_end", "line end", show=False),
        Binding("G", "doc_end", "doc end", show=False),
        # Visual mode
        Binding("v", "toggle_visual", "visual", show=False),
        Binding("space", "toggle_visual", "visual", show=False),
        Binding("escape", "clear_visual", "clear", show=False),
    ]

    # Reactive state — re-render on change.
    text: reactive[str] = reactive("", layout=True)
    cursor: reactive[int] = reactive(0)
    anchor: reactive[Optional[int]] = reactive(None)
    visual_mode: reactive[bool] = reactive(False)

    # Rich style strings (not Textual CSS — `$accent` won't resolve in Rich).
    cursor_style: reactive[str] = reactive("reverse")
    # ANSI color 24 = a steel-blue background that reads well on most terminals.
    selection_style: reactive[str] = reactive("on color(24)")

    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.text = text
        # Existing labeled spans (for inline coloring).
        self._spans: list[dict[str, Any]] = []
        # Wrap geometry: list of (start_offset, end_offset) per visual line.
        self._lines: list[tuple[int, int]] = []
        self._wrap_width: int = 0
        # g-chord state for "gg".
        self._pending_g: bool = False
        # Mouse drag state.
        self._dragging: bool = False
        # Vim-style count prefix accumulator (e.g. "3" then "w" → 3 words).
        # Stored as a string so the leading-zero rule is easy: ``0`` is only
        # treated as a digit when ``_pending_count`` is non-empty.
        self._pending_count: str = ""
        # Pending two-key operator: ``"f"``, ``"F"``, ``"t"``, ``"T"`` waits
        # for the next character. ``None`` when no operator is pending.
        self._pending_op: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_text(self, text: str, spans: Optional[list[dict[str, Any]]] = None) -> None:
        """Replace the passage text and reset cursor / selection.

        ``spans`` is the list of currently labeled spans to render as
        coloured backgrounds. Pass ``None`` to keep the previous list.
        """
        self.text = text
        if spans is not None:
            self._spans = list(spans)
        self.cursor = 0
        self.anchor = None
        self.visual_mode = False
        self._pending_g = False
        self._pending_count = ""
        self._pending_op = None
        self._dragging = False
        self._recompute_lines()
        self.refresh()

    def set_spans(self, spans: list[dict[str, Any]]) -> None:
        """Update the highlighted span list without resetting the cursor."""
        self._spans = list(spans)
        self.refresh()

    def clear_selection(self) -> None:
        """Clear any active selection (mouse or visual mode)."""
        self.anchor = None
        self.visual_mode = False
        self.refresh()

    @property
    def selection(self) -> Optional[tuple[int, int]]:
        """Current selection ``(start, end)`` (end-exclusive) or ``None``.

        Vim's character-wise visual mode is inclusive of the cursor's cell:
        with anchor at offset 0 and cursor on offset 10, the selection
        covers ``[0..10]`` (11 chars). Python slices are end-exclusive, so
        we extend by one beyond the rightmost endpoint. When anchor is at
        or past the end of the text, we still produce a single-cell range.
        """
        if self.anchor is None:
            return None
        n = len(self.text)
        # When anchor == cursor, vim still highlights one cell. Make a
        # single-char selection — useful for click-no-drag and Space-then-a.
        lo = min(self.anchor, self.cursor)
        hi = max(self.anchor, self.cursor) + 1
        if hi > n:
            hi = n
        if lo >= hi:
            return None
        return (lo, hi)

    @property
    def selected_text(self) -> str:
        """Verbatim substring within the current selection, or ``""``."""
        sel = self.selection
        if sel is None:
            return ""
        lo, hi = sel
        return self.text[lo:hi]

    # ------------------------------------------------------------------
    # Wrap geometry
    # ------------------------------------------------------------------

    def _content_width(self) -> int:
        # Use the most recent rendered size if known; otherwise a sane default.
        w = self.size.width if self.size.width else 80
        return max(1, w)

    @staticmethod
    def _wrap_text(text: str, width: int) -> list[tuple[int, int]]:
        """Return wrap geometry as ``[(start, end), ...]`` for *text* at *width*.

        Hard newlines split lines and are *consumed* by the break (not part of
        any line's range). Long lines soft-wrap at *width*. An empty input
        produces a single empty range so the cursor is always renderable.
        """
        width = max(1, width)
        n = len(text)
        if n == 0:
            return [(0, 0)]
        lines: list[tuple[int, int]] = []
        i = 0
        while i <= n:
            # Find next hard newline; if i == n we're past the text.
            nl = text.find("\n", i) if i < n else -1
            hard_end = nl if nl != -1 else n
            if i == hard_end:
                # Empty line (or trailing newline produced empty terminal line).
                lines.append((i, i))
            else:
                j = i
                while j < hard_end:
                    k = min(j + width, hard_end)
                    lines.append((j, k))
                    j = k
            if nl == -1:
                break
            i = nl + 1
            if i == n:
                # Trailing newline → empty terminal line.
                lines.append((i, i))
                break
        return lines or [(0, 0)]

    def _recompute_lines(self) -> None:
        """Recompute :pyattr:`_lines` for the widget's current width."""
        width = self._content_width()
        self._wrap_width = width
        self._lines = self._wrap_text(self.text, width)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def on_resize(self, event: events.Resize) -> None:  # noqa: D401
        """Recompute wrap when the widget resizes."""
        if event.size.width != self._wrap_width:
            self._recompute_lines()
            self.refresh()

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        """Tell Textual how tall to make the widget for *width*."""
        self._lines = self._wrap_text(self.text, width)
        self._wrap_width = max(1, width)
        return max(1, len(self._lines))

    def _span_style_at(self, offset: int) -> Optional[str]:
        """Return the layer style covering *offset*, or None.

        Layer-A and layer-B spans may overlap; layer A wins as a tie-breaker
        because it is the dominant event-tagging layer.
        """
        a_hit = False
        b_hit = False
        for sp in self._spans:
            try:
                start = int(sp.get("start", 0))
                end = int(sp.get("end", 0))
            except (TypeError, ValueError):
                continue
            if start <= offset < end:
                if sp.get("layer", "A") == "A":
                    a_hit = True
                else:
                    b_hit = True
        if a_hit:
            return _LAYER_A_STYLE
        if b_hit:
            return _LAYER_B_STYLE
        return None

    def render(self) -> Text:
        """Render the passage with cursor + selection overlays."""
        if not self._lines:
            self._recompute_lines()

        text = self.text
        rich_text = Text()
        sel = self.selection
        sel_lo, sel_hi = (sel if sel is not None else (-1, -1))

        for li, (start, end) in enumerate(self._lines):
            i = start
            while i < end:
                ch = text[i]
                styles: list[str] = []
                span_style = self._span_style_at(i)
                if span_style is not None:
                    styles.append(span_style)
                if sel_lo <= i < sel_hi:
                    styles.append(self.selection_style)
                if i == self.cursor:
                    styles.append(self.cursor_style)
                if styles:
                    rich_text.append(ch, style=" ".join(styles))
                else:
                    rich_text.append(ch)
                i += 1
            # If cursor is at end of text, render a synthetic block so it's
            # still visible even when there's no character to invert.
            if li == len(self._lines) - 1 and self.cursor == len(text):
                rich_text.append(" ", style=self.cursor_style)
            if li < len(self._lines) - 1:
                rich_text.append("\n")
        return rich_text

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def _xy_to_offset(self, x: int, y: int) -> int:
        """Convert widget-local (x, y) to a character offset."""
        if not self._lines:
            return 0
        line_idx = max(0, min(y, len(self._lines) - 1))
        start, end = self._lines[line_idx]
        col = max(0, x)
        offset = start + col
        if offset > end:
            offset = end
        return max(0, min(offset, len(self.text)))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        self.focus()
        offset = self._xy_to_offset(event.x, event.y)
        self.cursor = offset
        self.anchor = offset
        self.visual_mode = False
        self._dragging = True
        self.capture_mouse()
        self.refresh()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        offset = self._xy_to_offset(event.x, event.y)
        if offset != self.cursor:
            self.cursor = offset
            self.refresh()
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.release_mouse()
        offset = self._xy_to_offset(event.x, event.y)
        self.cursor = offset
        # Click without drag — clear selection.
        if self.anchor == self.cursor:
            self.anchor = None
        self.refresh()
        event.stop()

    # ------------------------------------------------------------------
    # Cursor / selection helpers
    # ------------------------------------------------------------------

    def _maybe_extend(self, new_cursor: int) -> None:
        """Move the cursor and, if not in visual mode, drop the anchor.

        In visual mode the anchor is preserved so the selection grows /
        shrinks. Outside visual mode any prior selection is cleared by a
        plain motion.
        """
        new_cursor = max(0, min(new_cursor, len(self.text)))
        if not self.visual_mode:
            # Plain motion clears any pre-existing (e.g. mouse) selection.
            self.anchor = None
        self.cursor = new_cursor
        self.refresh()

    def _line_index(self, offset: int) -> int:
        """Return the visual-line index containing *offset*."""
        if not self._lines:
            return 0
        for i, (start, end) in enumerate(self._lines):
            if start <= offset <= end:
                # If exactly at end and a next line starts here, prefer this one
                # for cursor-at-end semantics.
                if offset == end and i + 1 < len(self._lines):
                    if self._lines[i + 1][0] == end:
                        # Wrapped: still belongs to current line.
                        return i
                return i
        return len(self._lines) - 1

    def _column(self, offset: int) -> int:
        li = self._line_index(offset)
        start, _ = self._lines[li]
        return offset - start

    # ------------------------------------------------------------------
    # Key event interception (counts, f/F/t/T, gg)
    # ------------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """Intercept keys that participate in vim-style key sequences.

        This runs before Textual dispatches BINDINGS for the same event.
        When we claim a key, ``event.prevent_default()`` and ``event.stop()``
        are called so the binding-based action handlers don't also fire.
        Otherwise the event bubbles through normally.
        """
        # If a two-key operator is pending (f / F / t / T), consume the next
        # printable character as the target. Anything non-printable (Escape,
        # arrows, etc.) clears the pending state without movement.
        if self._pending_op in ("f", "F", "t", "T"):
            op = self._pending_op
            self._pending_op = None
            ch = event.character
            count = self._consume_count()
            if ch is None or not ch.isprintable() or len(ch) != 1:
                # Cancelled — also clear pending count via _consume_count.
                event.prevent_default()
                event.stop()
                return
            forward = op in ("f", "t")
            until = op in ("t", "T")
            for _ in range(count):
                target = self._step_find_char(ch, forward=forward, until=until)
                if target is None:
                    break
                self._set_cursor(target)
            self.refresh()
            event.prevent_default()
            event.stop()
            return

        key = event.key
        ch = event.character

        # Count prefix: digits 1-9 always start/extend a count; 0 is a digit
        # only if a count is already in progress (otherwise it's line-start).
        if ch is not None and ch.isdigit():
            if ch == "0" and not self._pending_count:
                # Treat as line-start motion.
                self.action_line_start()
                event.prevent_default()
                event.stop()
                return
            self._pending_count += ch
            self._pending_g = False
            event.prevent_default()
            event.stop()
            return

        # Operator triggers (f / F / t / T) — store and wait for the next key.
        if key in ("f", "F", "t", "T"):
            self._pending_op = key
            self._pending_g = False
            event.prevent_default()
            event.stop()
            return

        # gg chord. The first 'g' arms _pending_g; the second jumps to top.
        if key == "g":
            self.action_g_chord()
            event.prevent_default()
            event.stop()
            return

        # The key is going to fall through to the BINDINGS dispatcher (or to
        # nothing). Motion actions call ``_consume_count`` to absorb the
        # count; any *other* key should leave the count behaviour predictable
        # by clearing it here. Listing the motion keys explicitly avoids
        # leaking a stale count into a later motion the user didn't intend.
        _MOTION_KEYS = {
            "h", "l", "j", "k", "w", "W", "b", "e", "E", "G",
            "left", "right", "up", "down",
            "dollar_sign",  # $
        }
        if key not in _MOTION_KEYS:
            self._pending_count = ""
        # Clear chord-state for any key other than 'g'.
        if key != "g":
            self._pending_g = False

    # ------------------------------------------------------------------
    # Pending-count helpers
    # ------------------------------------------------------------------

    def _consume_count(self) -> int:
        """Pop the pending count, returning at least 1.

        After every motion the count is reset; the next non-digit key starts
        fresh. Non-numeric counts (shouldn't happen) fall back to 1.
        """
        try:
            n = int(self._pending_count) if self._pending_count else 1
        except ValueError:
            n = 1
        self._pending_count = ""
        if n < 1:
            n = 1
        return n

    # ------------------------------------------------------------------
    # Single-step motion helpers (used by both actions and on_key)
    # ------------------------------------------------------------------

    def _step_word_forward(self, *, big: bool = False) -> int:
        """Compute the offset of the next word/WORD start from the cursor.

        ``big`` selects vim WORD semantics (``\\S+`` runs) instead of word
        semantics (``\\w+`` runs). The cursor itself is not moved here — the
        result is fed through :meth:`_maybe_extend` by the caller.
        """
        text = self.text
        n = len(text)
        i = self.cursor
        if big:
            # Skip current run of non-whitespace.
            while i < n and not text[i].isspace():
                i += 1
            # Then skip whitespace to land on next non-whitespace.
            while i < n and text[i].isspace():
                i += 1
            return i if i <= n else n
        # word semantics — runs of \w+.
        while i < n and _WORD_CHAR.match(text, i):
            i += 1
        if i == self.cursor and i < n:
            # Non-word char; nudge forward at least one position.
            i += 1
        regex = _WORD
        m = regex.search(text, i)
        return n if m is None else m.start()

    def _step_word_back(self, *, big: bool = False) -> int:
        """Compute the offset of the previous word start.

        ``big=False`` uses vim ``b`` semantics (alphanumeric word
        boundaries); ``big=True`` uses vim ``B`` semantics
        (whitespace-delimited WORD).
        """
        text = self.text
        target = 0
        regex = _BIGWORD if big else _WORD
        for m in regex.finditer(text):
            if m.start() < self.cursor:
                target = m.start()
            else:
                break
        return target

    def _step_end_of_word(self, *, big: bool = False) -> int:
        """Compute the end-of-word position (vim ``e`` / ``E``).

        Lands on the *last* character of the current word; if already there
        (or on whitespace), advances to the end of the next word.
        ``big=True`` uses whitespace boundaries (WORD).
        """
        text = self.text
        n = len(text)
        if n == 0:
            return 0
        regex = _BIGWORD if big else _WORD
        cursor = self.cursor
        for m in regex.finditer(text):
            end_pos = m.end() - 1
            if end_pos > cursor:
                return end_pos
        # No further word — clamp to last char.
        return max(0, n - 1)

    def _step_find_char(self, ch: str, *, forward: bool, until: bool) -> Optional[int]:
        """Compute the offset for ``f``/``F``/``t``/``T`` motions.

        Search is *line-scoped*: it never crosses a visual-line boundary. Only
        a single occurrence is consumed per call — counts loop the caller.
        Returns ``None`` if the character is not found on the current line in
        the requested direction (no movement should occur).
        """
        if not ch or not self._lines:
            return None
        text = self.text
        li = self._line_index(self.cursor)
        line_start, line_end = self._lines[li]
        if forward:
            # Search strictly after the cursor on this line.
            search_from = self.cursor + 1
            for i in range(search_from, line_end):
                if text[i] == ch:
                    return i - 1 if until else i
            return None
        # Backward search — strictly before the cursor on this line.
        for i in range(self.cursor - 1, line_start - 1, -1):
            if text[i] == ch:
                return i + 1 if until else i
        return None

    # ------------------------------------------------------------------
    # Action handlers (keyboard)
    # ------------------------------------------------------------------

    def action_move_left(self) -> None:
        """Move cursor left one character (h / Left). Honors count prefix."""
        self._pending_g = False
        count = self._consume_count()
        self._maybe_extend(self.cursor - count)

    def action_move_right(self) -> None:
        """Move cursor right one character (l / Right). Honors count prefix."""
        self._pending_g = False
        count = self._consume_count()
        self._maybe_extend(self.cursor + count)

    def action_move_down(self) -> None:
        """Move cursor down one visual line (j / Down). Honors count prefix."""
        self._pending_g = False
        if not self._lines:
            self._consume_count()
            return
        count = self._consume_count()
        col = self._column(self.cursor)
        target_li = self._line_index(self.cursor) + count
        if target_li >= len(self._lines):
            self._maybe_extend(len(self.text))
            return
        nstart, nend = self._lines[target_li]
        self._maybe_extend(min(nstart + col, nend))

    def action_move_up(self) -> None:
        """Move cursor up one visual line (k / Up). Honors count prefix."""
        self._pending_g = False
        if not self._lines:
            self._consume_count()
            return
        count = self._consume_count()
        col = self._column(self.cursor)
        target_li = self._line_index(self.cursor) - count
        if target_li <= 0:
            pstart, pend = self._lines[0]
            self._maybe_extend(min(pstart + col, pend))
            return
        pstart, pend = self._lines[target_li]
        self._maybe_extend(min(pstart + col, pend))

    def action_word_forward(self) -> None:
        """Move to the start of the next word (``w``). Honors count prefix.

        A word is a run of ``\\w+`` characters. ``count`` repetitions land on
        the start of the *count-th* next word.
        """
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_word_forward(big=False))
        self.refresh()

    def action_WORD_forward(self) -> None:
        """Move to the start of the next WORD (``W``) — whitespace-delimited."""
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_word_forward(big=True))
        self.refresh()

    def action_word_back(self) -> None:
        """Move to the start of the previous word (``b``). Honors count prefix."""
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_word_back(big=False))
        self.refresh()

    def action_WORD_back(self) -> None:
        """Move to the start of the previous WORD (``B``) — whitespace-delimited."""
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_word_back(big=True))
        self.refresh()

    def action_end_of_word(self) -> None:
        """Move to the last character of the current/next word (``e``)."""
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_end_of_word(big=False))
        self.refresh()

    def action_end_of_WORD(self) -> None:
        """Move to the last character of the current/next WORD (``E``)."""
        self._pending_g = False
        count = self._consume_count()
        for _ in range(count):
            self._set_cursor(self._step_end_of_word(big=True))
        self.refresh()

    def action_line_start(self) -> None:
        """Move to the start of the current visual line (``0``)."""
        self._pending_g = False
        self._pending_count = ""
        if not self._lines:
            return
        li = self._line_index(self.cursor)
        self._maybe_extend(self._lines[li][0])

    def action_line_end(self) -> None:
        """Move to the end of the current visual line (``$``)."""
        self._pending_g = False
        self._pending_count = ""
        if not self._lines:
            return
        li = self._line_index(self.cursor)
        self._maybe_extend(self._lines[li][1])

    def action_g_chord(self) -> None:
        """Handle 'g' — second 'g' jumps to top of document."""
        if self._pending_g:
            self._pending_g = False
            self._pending_count = ""
            self._maybe_extend(0)
        else:
            self._pending_g = True

    def action_doc_end(self) -> None:
        """Move to end of document (``G``)."""
        self._pending_g = False
        self._pending_count = ""
        self._maybe_extend(len(self.text))

    def action_toggle_visual(self) -> None:
        """Toggle visual selection mode (``v`` or Space)."""
        self._pending_g = False
        self._pending_count = ""
        if self.visual_mode:
            self.visual_mode = False
            self.anchor = None
        else:
            self.visual_mode = True
            self.anchor = self.cursor
        self.refresh()

    def action_clear_visual(self) -> None:
        """Clear any active selection / visual mode (Escape)."""
        self._pending_g = False
        self._pending_count = ""
        self._pending_op = None
        self.visual_mode = False
        self.anchor = None
        self.refresh()

    def _set_cursor(self, new_cursor: int) -> None:
        """Move the cursor without calling refresh (caller refreshes once).

        Loop-friendly variant of :meth:`_maybe_extend` used by count motions
        so the widget doesn't repaint mid-loop.
        """
        new_cursor = max(0, min(new_cursor, len(self.text)))
        if not self.visual_mode:
            self.anchor = None
        self.cursor = new_cursor
