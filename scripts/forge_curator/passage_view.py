"""PassageView — interactive passage display with cursor + selection.

A custom Textual widget used by the BCF Annotation TUI that replaces the
plain ``Static`` previously used to display the passage. It supports:

* A visible character cursor (rendered as inverse-video).
* A character-wise selection range, highlighted with the accent style.
* Mouse click-and-drag to select a range.
* Vim-style keyboard motions when the widget has focus:
    h/j/k/l, Left/Down/Up/Right
    Ctrl-B / Ctrl-F (page back / forward)
    w / W  (word / WORD forward)
    b      (word back)
    e / E  (end of word / WORD)
    0 / $  (line start / end)
    g g (top), G (bottom)
    f<c>/F<c>  find char forward/back until the next paragraph break
    t<c>/T<c>  until char forward/back until the next paragraph break
    ; / ,      repeat last find-char motion / repeat in opposite direction
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
# Paragraphs are separated by a blank line. Spaces or tabs on the blank
# separator line still count as a paragraph break.
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")

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
        Binding("ctrl+b", "cursor_page_up", "page up", show=False),
        Binding("ctrl+f", "cursor_page_down", "page down", show=False),
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
        Binding("V", "toggle_visual_line", "visual line", show=False),
        Binding("space", "toggle_visual", "visual", show=False),
        Binding("escape", "clear_visual", "clear", show=False),
    ]

    # Reactive state — re-render on change.
    text: reactive[str] = reactive("", layout=True)
    cursor: reactive[int] = reactive(0)
    anchor: reactive[Optional[int]] = reactive(None)
    visual_mode: reactive[bool] = reactive(False)
    visual_line_mode: reactive[bool] = reactive(False)

    # Rich style strings (not Textual CSS — `$accent` won't resolve in Rich).
    # Keep the cursor foreground light: if a terminal drops or mishandles the
    # background escape, the cursor cell still remains visible on dark themes.
    cursor_style: reactive[str] = reactive("bold white on #005f87")
    selection_style: reactive[str] = reactive("on #303030")
    selection_plain_style: reactive[str] = reactive("white on #303030")

    def __init__(self, text: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.text = text
        # Existing labeled spans (for inline coloring).
        self._spans: list[dict[str, Any]] = []
        self._span_style_cache: list[Optional[str]] | None = None
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
        # Last completed find-char motion for Vim-style ; / , repeats.
        self._last_find_op: Optional[str] = None
        self._last_find_char: Optional[str] = None
        # Pending text-object scope ``"a"`` (around) or ``"i"`` (inner).
        # Only armed inside visual / visual-line mode; cleared when a
        # following ``w/W/s/p`` completes the selection.
        self._pending_text_object: Optional[str] = None

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
            self._span_style_cache = None
        self.cursor = 0
        self.anchor = None
        self.visual_mode = False
        self._pending_g = False
        self._pending_count = ""
        self._pending_op = None
        self._last_find_op = None
        self._last_find_char = None
        self._dragging = False
        self._recompute_lines()
        self.refresh()

    def set_spans(self, spans: list[dict[str, Any]]) -> None:
        """Update the highlighted span list without resetting the cursor."""
        self._spans = list(spans)
        self._span_style_cache = None
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
        we extend by one beyond the rightmost endpoint. Visual-line mode
        (``V``) extends both endpoints to whole-line boundaries. When
        anchor is at or past the end of the text, we still produce a
        single-cell range.
        """
        if self.anchor is None:
            return None
        n = len(self.text)
        lo = min(self.anchor, self.cursor)
        hi = max(self.anchor, self.cursor) + 1
        if self.visual_line_mode and self._lines:
            # Expand to whole visual lines: lo → start of anchor's line,
            # hi → end of cursor's line (exclusive of trailing newline,
            # inclusive of the last char so the range is non-empty even
            # for a single-line case).
            lo_line = self._line_index(lo)
            hi_line = self._line_index(max(0, hi - 1))
            lo = self._lines[lo_line][0]
            hi = self._lines[hi_line][1]
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

        Hard newlines split lines and are *consumed* by the break.
        Soft wraps prefer **word boundaries**: within a long line, the
        wrap point is the last whitespace at or before ``width`` chars
        from the segment start. The whitespace itself is consumed by
        the break (not in either neighbouring line's range), keeping
        the visual flow clean. If no whitespace is available within the
        segment, falls back to a hard char-wrap so over-long single
        words still don't overflow.
        """
        width = max(1, width)
        n = len(text)
        if n == 0:
            return [(0, 0)]
        lines: list[tuple[int, int]] = []
        i = 0
        while i <= n:
            nl = text.find("\n", i) if i < n else -1
            hard_end = nl if nl != -1 else n
            if i == hard_end:
                lines.append((i, i))
            else:
                j = i
                while j < hard_end:
                    ideal_end = min(j + width, hard_end)
                    if ideal_end == hard_end:
                        lines.append((j, hard_end))
                        j = hard_end
                        break
                    # Search backward from ideal_end-1 for the last
                    # whitespace position. We want to break at that
                    # space so the previous word stays whole.
                    space_at = -1
                    for ki in range(ideal_end - 1, j - 1, -1):
                        if text[ki].isspace():
                            space_at = ki
                            break
                    if space_at > j:
                        lines.append((j, space_at))
                        j = space_at + 1
                    else:
                        # No whitespace in segment — single word longer
                        # than width. Hard char-wrap as fallback.
                        lines.append((j, ideal_end))
                        j = ideal_end
            if nl == -1:
                break
            i = nl + 1
            if i == n:
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

    @staticmethod
    def _span_style_and_priority(sp: dict[str, Any]) -> tuple[Optional[str], int]:
        style = sp.get("style")
        if style:
            try:
                priority = int(sp.get("priority", 30))
            except (TypeError, ValueError):
                priority = 30
            return str(style), priority
        if sp.get("layer", "A") == "A":
            return _LAYER_A_STYLE, 20
        return _LAYER_B_STYLE, 10

    def _span_styles(self) -> list[Optional[str]]:
        """Return cached per-character base span styles.

        Rendering large chapters is sensitive to inner-loop work. The
        highlighted spans change only when the host calls ``set_text`` or
        ``set_spans``, while cursor/selection changes can trigger many
        renders. Cache the resolved span style per character so each render
        can do O(1) lookups instead of scanning every span for every cell.
        """
        if self._span_style_cache is not None and len(self._span_style_cache) == len(self.text):
            return self._span_style_cache
        styles: list[Optional[str]] = [None] * len(self.text)
        priorities = [-1] * len(self.text)
        for sp in self._spans:
            try:
                start = int(sp.get("start", 0))
                end = int(sp.get("end", 0))
            except (TypeError, ValueError):
                continue
            start = max(0, start)
            end = min(len(self.text), end)
            if end <= start:
                continue
            style, priority = self._span_style_and_priority(sp)
            if style is None:
                continue
            for i in range(start, end):
                if priority > priorities[i]:
                    styles[i] = style
                    priorities[i] = priority
        self._span_style_cache = styles
        return styles

    def _span_style_at(self, offset: int) -> Optional[str]:
        """Return the layer style covering *offset*, or None."""
        if not (0 <= offset < len(self.text)):
            return None
        return self._span_styles()[offset]

    def _cell_style(
        self,
        *,
        span_style: Optional[str],
        selected: bool,
        cursor: bool,
    ) -> Optional[str]:
        """Compose the visible style for one character cell.

        Cursor wins outright with an explicit contrast pair. Selection keeps a
        semantic foreground when one exists, but supplies a stable background.
        """
        if cursor:
            return self.cursor_style
        if selected:
            if span_style is not None:
                return f"{span_style} {self.selection_style}"
            return self.selection_plain_style
        return span_style

    def _cursor_primary_line(self) -> int:
        """Index of the visual line where the cursor should render.

        - A cursor strictly inside a line range ``(start <= cursor < end)``
          renders inline in that line.
        - A cursor at exactly ``len(text)`` renders as a synthetic trailing
          block on the last line.
        - A cursor sitting on an empty line ``(start == end)`` or on a hard
          newline position ``(cursor == end)`` of a non-final line renders
          as a synthetic block on that line.
        - When two adjacent lines share the same offset (soft wrap), the
          *next* line's inner loop wins so the cursor renders on the
          continuation line, not as a phantom at the end of the prior line.
        """
        cursor = self.cursor
        n = len(self.text)
        if not self._lines:
            return 0
        if cursor >= n:
            return len(self._lines) - 1
        for i, (start, end) in enumerate(self._lines):
            if start <= cursor < end:
                return i
        # Boundary case: cursor == end for some line, but no inner loop
        # rendered it (hard newline or empty line). Find the line whose end
        # equals cursor; prefer the empty-line owner if start==end==cursor.
        for i, (start, end) in enumerate(self._lines):
            if start == end == cursor:
                return i
        for i, (start, end) in enumerate(self._lines):
            if cursor == end:
                return i
        return len(self._lines) - 1

    def render(self) -> Text:
        """Render the passage with cursor + selection overlays."""
        if not self._lines:
            self._recompute_lines()

        text = self.text
        rich_text = Text()
        sel = self.selection
        sel_lo, sel_hi = (sel if sel is not None else (-1, -1))
        primary_line = self._cursor_primary_line()
        span_styles = self._span_styles()

        for li, (start, end) in enumerate(self._lines):
            i = start
            cursor_drawn_inline = False
            while i < end:
                is_cursor = i == self.cursor and li == primary_line
                if is_cursor:
                    cursor_drawn_inline = True
                    rich_text.append(text[i], style=self.cursor_style)
                    i += 1
                    continue
                span_style = span_styles[i]
                selected = sel_lo <= i < sel_hi
                style = self._cell_style(
                    span_style=span_style,
                    selected=selected,
                    cursor=False,
                )
                j = i + 1
                while j < end:
                    if j == self.cursor and li == primary_line:
                        break
                    if (sel_lo <= j < sel_hi) != selected:
                        break
                    if span_styles[j] != span_style:
                        break
                    j += 1
                if style is not None:
                    rich_text.append(text[i:j], style=style)
                else:
                    rich_text.append(text[i:j])
                i = j
            # Render synthetic cursor block on the primary line when the
            # inner loop didn't draw it (empty line, hard newline boundary,
            # or cursor at end-of-document on the last line).
            if li == primary_line and not cursor_drawn_inline:
                rich_text.append(" ", style=self.cursor_style)
            if li < len(self._lines) - 1:
                rich_text.append("\n")
        return rich_text

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------

    def _xy_to_offset(self, x: int, y: int) -> int:
        """Convert widget-local (x, y) to a character offset.

        Subtracts the widget's CSS padding so a click on the leftmost
        visible character maps to the start of that line, not the
        padding column.
        """
        if not self._lines:
            return 0
        try:
            pad = self.styles.padding
            x -= pad.left
            y -= pad.top
        except Exception:
            pass
        line_idx = max(0, min(y, len(self._lines) - 1))
        start, end = self._lines[line_idx]
        col = max(0, x)
        offset = start + col
        if offset > end:
            offset = end
        return max(0, min(offset, len(self.text)))

    # Drag selection requires the cursor to move a meaningful distance
    # away from the click point before an anchor is committed. Tiny
    # sub-pixel drift during a plain click should never create a
    # selection.
    _DRAG_THRESHOLD_CHARS = 4

    def on_mouse_down(self, event: events.MouseDown) -> None:
        if event.button != 1:
            return
        self.focus()
        offset = self._xy_to_offset(event.x, event.y)
        self.cursor = offset
        # IMPORTANT: do NOT set anchor here. We commit it only on
        # actual drag movement past the threshold. This avoids the
        # "click triggers a 1-char selection" bug.
        self.anchor = None
        self.visual_mode = False
        self.visual_line_mode = False
        self._dragging = True
        self._drag_start_offset = offset
        self.capture_mouse()
        self.refresh()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        offset = self._xy_to_offset(event.x, event.y)
        start = getattr(self, "_drag_start_offset", offset)
        if offset == self.cursor:
            event.stop()
            return
        # Only commit anchor once the user has dragged past threshold;
        # treat shorter drags as a still-pending click.
        if self.anchor is None and abs(offset - start) >= self._DRAG_THRESHOLD_CHARS:
            self.anchor = start
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
        start = getattr(self, "_drag_start_offset", offset)
        # If the drag never crossed the threshold, treat as a click.
        if self.anchor is not None and abs(offset - start) < self._DRAG_THRESHOLD_CHARS:
            self.anchor = None
        self.refresh()
        event.stop()

    # ------------------------------------------------------------------
    # Cursor / selection helpers
    # ------------------------------------------------------------------

    def _maybe_extend(self, new_cursor: int) -> None:
        """Move the cursor and, if not in visual mode, drop the anchor.

        In visual mode (char-wise ``v`` or line-wise ``V``) the anchor
        is preserved so the selection grows / shrinks. Outside visual
        mode any prior selection is cleared by a plain motion.
        """
        new_cursor = max(0, min(new_cursor, len(self.text)))
        if not (self.visual_mode or self.visual_line_mode):
            # Plain motion clears any pre-existing (e.g. mouse) selection.
            self.anchor = None
        self.cursor = new_cursor
        self.refresh()

    def _line_index(self, offset: int) -> int:
        """Return the visual-line index containing *offset*.

        Matches the rendering convention so motion math (j/k/$/^/etc.)
        agrees with where the cursor is actually drawn:

        - A position strictly inside a line (``start <= offset < end``)
          belongs to that line — the inner render loop draws the cursor
          there. For a soft-wrap boundary offset that is both the ``end``
          of line N and the ``start`` of line N+1, this rule selects
          line N+1, the continuation line, where the cursor renders.
        - Otherwise the offset is at a true boundary (empty line range
          ``(i, i)`` or a hard-newline position with no continuation
          starting at the same offset). Pick the *last* line whose
          ``end == offset`` — that's the line whose synthetic cursor
          cell is drawn.
        """
        if not self._lines:
            return 0
        for i, (start, end) in enumerate(self._lines):
            if start <= offset < end:
                return i
        # Boundary positions: empty line, hard-newline char, or end-of-text.
        last_match = -1
        for i, (start, end) in enumerate(self._lines):
            if end == offset:
                last_match = i
        if last_match >= 0:
            return last_match
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
        ch_for_pending = event.character
        key_for_pending = event.key

        # Pending text-object completion: ``aw / iw / aW / iW / as / is /
        # ap / ip``. Only armed inside visual / visual-line mode.
        if self._pending_text_object in ("a", "i"):
            scope = self._pending_text_object
            self._pending_text_object = None
            if ch_for_pending in ("w", "W", "s", "p") and (
                self.visual_mode or self.visual_line_mode
            ):
                count = self._consume_count()
                self._select_text_object(
                    scope=scope,
                    kind=ch_for_pending,
                    count=count,
                )
                event.prevent_default()
                event.stop()
                return
            # Cancel without movement on any other key.
            self._pending_count = ""
            event.prevent_default()
            event.stop()
            return

        # Arm text-object pending state when ``a`` / ``i`` is pressed in
        # visual mode. Outside visual mode they fall through (we don't
        # use them as motions/operators).
        if (self.visual_mode or self.visual_line_mode) and ch_for_pending in ("a", "i"):
            self._pending_text_object = ch_for_pending
            event.prevent_default()
            event.stop()
            return

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
            self._last_find_op = op
            self._last_find_char = ch
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

        if ch in (";", ","):
            self._repeat_find_char(reverse=(ch == ","))
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
            "ctrl+b", "ctrl+f",
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

        Search is paragraph-scoped: it crosses visual wraps and single hard
        newlines, but never crosses a blank-line paragraph break. Only a single
        occurrence is consumed per call — counts loop the caller. Returns
        ``None`` if the character is not found in the requested direction (no
        movement should occur).
        """
        if not ch or not self._lines:
            return None
        return self._step_find_char_from_cursor(
            ch, forward=forward, until=until, repeated_until=False
        )

    def _step_find_char_from_cursor(
        self,
        ch: str,
        *,
        forward: bool,
        until: bool,
        repeated_until: bool,
    ) -> Optional[int]:
        """Compute a find-char target from the current cursor position."""
        text = self.text
        paragraph_start, paragraph_end = self._paragraph_bounds(self.cursor)
        if forward:
            # Search strictly after the cursor within the current paragraph.
            search_from = self.cursor + (2 if repeated_until and until else 1)
            for i in range(search_from, paragraph_end):
                if text[i] == ch:
                    return i - 1 if until else i
            return None
        # Backward search — strictly before the cursor within the current paragraph.
        search_from = self.cursor - (2 if repeated_until and until else 1)
        for i in range(search_from, paragraph_start - 1, -1):
            if text[i] == ch:
                return i + 1 if until else i
        return None

    def _repeat_find_char(self, *, reverse: bool) -> None:
        """Repeat the last ``f/F/t/T`` search; comma reverses direction."""
        self._pending_g = False
        op = self._last_find_op
        ch = self._last_find_char
        count = self._consume_count()
        if op is None or ch is None:
            return
        forward = op in ("f", "t")
        if reverse:
            forward = not forward
        until = op in ("t", "T")
        for _ in range(count):
            target = self._step_find_char_from_cursor(
                ch,
                forward=forward,
                until=until,
                repeated_until=True,
            )
            if target is None:
                break
            self._set_cursor(target)
        self.refresh()

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

    def _page_line_count(self) -> int:
        """Return the number of visual lines in the visible passage page."""
        parent_height = getattr(getattr(self, "parent", None), "size", None)
        height = getattr(parent_height, "height", 0) or self.size.height or 0
        return max(1, int(height))

    def action_cursor_page_down(self) -> None:
        """Move cursor down one visible page (Ctrl-F). Honors count prefix."""
        self._pending_g = False
        if not self._lines:
            self._consume_count()
            return
        count = self._consume_count()
        col = self._column(self.cursor)
        target_li = self._line_index(self.cursor) + (self._page_line_count() * count)
        if target_li >= len(self._lines):
            self._maybe_extend(len(self.text))
            return
        nstart, nend = self._lines[target_li]
        self._maybe_extend(min(nstart + col, nend))

    def action_cursor_page_up(self) -> None:
        """Move cursor up one visible page (Ctrl-B). Honors count prefix."""
        self._pending_g = False
        if not self._lines:
            self._consume_count()
            return
        count = self._consume_count()
        col = self._column(self.cursor)
        target_li = self._line_index(self.cursor) - (self._page_line_count() * count)
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
        # Switching modes: drop line-mode if active.
        self.visual_line_mode = False
        if self.visual_mode:
            self.visual_mode = False
            self.anchor = None
        else:
            self.visual_mode = True
            self.anchor = self.cursor
        self.refresh()

    def action_toggle_visual_line(self) -> None:
        """Toggle line-wise visual selection mode (``V``)."""
        self._pending_g = False
        self._pending_count = ""
        if self.visual_line_mode:
            self.visual_line_mode = False
            self.visual_mode = False
            self.anchor = None
        else:
            self.visual_line_mode = True
            self.visual_mode = False
            self.anchor = self.cursor
        self.refresh()

    # ------------------------------------------------------------------
    # Text objects (vim ``aw / iw / aW / iW / as / is / ap / ip``)
    # ------------------------------------------------------------------

    def _word_bounds(self, cursor: int, *, big: bool) -> Optional[tuple[int, int]]:
        """Return ``(start, end_exclusive)`` of the word containing cursor.

        ``big=True`` uses vim WORD semantics (whitespace-delimited);
        ``big=False`` uses ``\\w+``. Returns ``None`` when ``cursor``
        sits on a non-word character (or whitespace, for big=False).
        """
        text = self.text
        n = len(text)
        if not (0 <= cursor < n):
            return None
        if big:
            if text[cursor].isspace():
                return None
            s = cursor
            while s > 0 and not text[s - 1].isspace():
                s -= 1
            e = cursor
            while e < n and not text[e].isspace():
                e += 1
            return s, e
        if not _WORD_CHAR.match(text, cursor):
            return None
        s = cursor
        while s > 0 and _WORD_CHAR.match(text, s - 1):
            s -= 1
        e = cursor
        while e < n and _WORD_CHAR.match(text, e):
            e += 1
        return s, e

    def _next_word_at_or_after(self, cursor: int, *, big: bool) -> int:
        """Skip whitespace forward to the next word/WORD start at or after cursor."""
        text = self.text
        n = len(text)
        i = cursor
        if big:
            while i < n and text[i].isspace():
                i += 1
        else:
            while i < n and not _WORD_CHAR.match(text, i):
                i += 1
        return i

    def _sentence_bounds(self, cursor: int, *, count: int = 1) -> tuple[int, int]:
        """Return ``(start, end_exclusive)`` for the sentence containing cursor.

        Sentences are runs of text terminated by ``.``, ``!``, or ``?``.
        Blank lines act as paragraph boundaries; single hard newlines are
        treated as whitespace because prose may be hard-wrapped in source.
        """
        text = self.text
        n = len(text)
        # Walk back to find sentence start.
        s = cursor
        while s > 0:
            prev = text[s - 1]
            if prev in ".!?":
                break
            if prev == "\n" and s >= 2 and text[s - 2] == "\n":
                break
            s -= 1
        while s < n and text[s].isspace():
            s += 1
        # Walk forward to sentence end (inclusive of terminating punctuation).
        e = max(s, cursor)
        remaining = max(1, count)
        while remaining > 0 and e < n:
            while e < n:
                c = text[e]
                if c in ".!?":
                    e += 1
                    remaining -= 1
                    break
                if c == "\n" and e + 1 < n and text[e + 1] == "\n":
                    remaining = 0
                    break
                e += 1
            if remaining <= 0:
                break
            while e < n and text[e].isspace():
                e += 1
        return s, e

    def _paragraph_bounds(self, cursor: int) -> tuple[int, int]:
        """Return ``(start, end_exclusive)`` for the paragraph containing cursor.

        Paragraphs are runs separated by a blank line. Spaces or tabs on the
        separator line still count as a paragraph break.
        """
        text = self.text
        n = len(text)
        cursor = max(0, min(cursor, n))
        s = 0
        e = n
        for match in _PARAGRAPH_BREAK.finditer(text):
            if match.end() <= cursor:
                s = match.end()
                continue
            if match.start() >= cursor:
                e = match.start()
                break
            # Cursor is inside the paragraph separator itself. Treat the
            # separator as its own bounded region so find motions and paragraph
            # text objects do not jump across it in either direction.
            s = match.start()
            e = match.end()
            break
        return s, e

    def _select_text_object(self, *, scope: str, kind: str, count: int = 1) -> None:
        """Compute and apply a text-object selection.

        ``scope`` is ``"a"`` (around) or ``"i"`` (inner). ``kind`` is one
        of ``w / W / s / p``.
        """
        text = self.text
        n = len(text)
        if n == 0:
            return
        cursor = self.cursor

        if kind in ("w", "W"):
            big = kind == "W"
            bounds = self._word_bounds(cursor, big=big)
            if bounds is None:
                # On whitespace — find next word.
                start = self._next_word_at_or_after(cursor, big=big)
                if start >= n:
                    return
                bounds = self._word_bounds(start, big=big)
                if bounds is None:
                    return
            s, e = bounds
            if scope == "a":
                while e < n and text[e] in " \t":
                    e += 1
        elif kind == "s":
            s, e = self._sentence_bounds(cursor, count=count)
            if scope == "a":
                while e < n and text[e] in " \t":
                    e += 1
        elif kind == "p":
            s, e = self._paragraph_bounds(cursor)
            if scope == "a":
                while e < n and text[e] == "\n":
                    e += 1
        else:
            return

        if e <= s:
            return
        # Vim selection: anchor at start, cursor on last char of range.
        if not (self.visual_mode or self.visual_line_mode):
            self.visual_mode = True
        self.anchor = s
        self.cursor = max(s, e - 1)
        self.refresh()

    def action_clear_visual(self) -> None:
        """Clear any active selection / visual mode (Escape)."""
        self._pending_g = False
        self._pending_count = ""
        self._pending_op = None
        self._pending_text_object = None
        self.visual_mode = False
        self.visual_line_mode = False
        self.anchor = None
        self.refresh()

    def _set_cursor(self, new_cursor: int) -> None:
        """Move the cursor without calling refresh (caller refreshes once).

        Loop-friendly variant of :meth:`_maybe_extend` used by count motions
        so the widget doesn't repaint mid-loop.
        """
        new_cursor = max(0, min(new_cursor, len(self.text)))
        if not (self.visual_mode or self.visual_line_mode):
            self.anchor = None
        self.cursor = new_cursor
