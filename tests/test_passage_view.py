"""Unit tests for nlp.tui.passage_view.PassageView.

These tests exercise the widget's pure-Python state machine — cursor
movement, selection extension, mouse-coordinate-to-offset mapping — without
spinning up a Textual `App`. The widget's reactive attributes can be set
directly because no parent app is observing them.
"""

from __future__ import annotations

import pytest

from nlp.tui.passage_view import PassageView


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(text: str, width: int = 40) -> PassageView:
    """Construct a PassageView and pre-wrap it to *width*."""
    pv = PassageView(text)
    pv._lines = PassageView._wrap_text(text, width)
    pv._wrap_width = width
    return pv


# ---------------------------------------------------------------------------
# Wrap geometry
# ---------------------------------------------------------------------------


def test_wrap_single_short_line() -> None:
    lines = PassageView._wrap_text("hello", width=80)
    assert lines == [(0, 5)]


def test_wrap_soft_wrap() -> None:
    # 12 chars at width 5 → 5/5/2.
    lines = PassageView._wrap_text("abcdefghijkl", width=5)
    assert lines == [(0, 5), (5, 10), (10, 12)]


def test_wrap_hard_newline() -> None:
    lines = PassageView._wrap_text("ab\ncd", width=80)
    # Newline at 2 is consumed; second line starts at 3.
    assert lines == [(0, 2), (3, 5)]


def test_wrap_empty_text() -> None:
    assert PassageView._wrap_text("", width=80) == [(0, 0)]


# ---------------------------------------------------------------------------
# Cursor motion
# ---------------------------------------------------------------------------


def test_cursor_move_right_and_left() -> None:
    pv = _make("hello world")
    pv.action_move_right()
    assert pv.cursor == 1
    pv.action_move_right()
    assert pv.cursor == 2
    pv.action_move_left()
    assert pv.cursor == 1


def test_cursor_clamped_at_bounds() -> None:
    pv = _make("ab")
    pv.action_move_left()  # already at 0
    assert pv.cursor == 0
    pv.cursor = 2
    pv.action_move_right()  # already at len
    assert pv.cursor == 2


def test_word_forward_jumps_to_next_word_start() -> None:
    pv = _make("Joe gained Perfect Pitch.")
    # Cursor at 0 ("J"). w → start of next word "gained" at offset 4.
    pv.action_word_forward()
    assert pv.cursor == 4
    # Next w → "Perfect" at offset 11.
    pv.action_word_forward()
    assert pv.cursor == 11
    # Next w → "Pitch" at offset 19.
    pv.action_word_forward()
    assert pv.cursor == 19


def test_word_back_walks_back_to_prior_word_start() -> None:
    pv = _make("Joe gained Perfect Pitch.")
    pv.cursor = 19  # at "P" of "Pitch"
    pv.action_word_back()
    assert pv.cursor == 11  # start of "Perfect"
    pv.action_word_back()
    assert pv.cursor == 4  # start of "gained"


def test_doc_end_and_gg() -> None:
    pv = _make("hello")
    pv.action_doc_end()
    assert pv.cursor == 5
    # gg from end → 0
    pv.action_g_chord()
    pv.action_g_chord()
    assert pv.cursor == 0


def test_line_start_and_line_end() -> None:
    text = "hello\nworld\nfoo"
    pv = _make(text, width=80)
    pv.cursor = 8  # inside "world"
    pv.action_line_start()
    assert pv.cursor == 6
    pv.action_line_end()
    assert pv.cursor == 11


# ---------------------------------------------------------------------------
# Selection (visual mode + plain motion semantics)
# ---------------------------------------------------------------------------


def test_visual_mode_toggle_anchors_cursor() -> None:
    pv = _make("Joe gained Perfect Pitch.")
    pv.cursor = 11
    pv.action_toggle_visual()
    assert pv.visual_mode is True
    assert pv.anchor == 11
    # Move cursor — selection should grow inclusively (vim default).
    pv.action_word_forward()
    assert pv.cursor == 19
    # Inclusive of cursor cell: covers offsets 11..19 → text[11:20].
    assert pv.selection == (11, 20)
    assert pv.selected_text == "Perfect P"


def test_visual_mode_extending_selection_word_by_word() -> None:
    pv = _make("Joe gained Perfect Pitch.")
    pv.cursor = 11
    pv.action_toggle_visual()
    # The user presses w 3 times — selection grows to end-of-text.
    pv.action_word_forward()  # 19
    pv.action_word_forward()  # 25 (past the period — len)
    pv.action_word_forward()  # already len
    sel = pv.selection
    assert sel is not None
    lo, hi = sel
    assert lo == 11
    assert hi == len("Joe gained Perfect Pitch.")
    assert pv.selected_text == "Perfect Pitch."


def test_clear_visual_drops_selection() -> None:
    pv = _make("hello")
    pv.cursor = 1
    pv.action_toggle_visual()
    pv.action_move_right()
    # Inclusive of cursor cell: covers offsets 1..2 → text[1:3].
    assert pv.selection == (1, 3)
    pv.action_clear_visual()
    assert pv.selection is None
    assert pv.visual_mode is False


def test_plain_motion_clears_prior_selection() -> None:
    """Plain motion (no visual mode) must drop any prior anchor."""
    pv = _make("hello")
    pv.cursor = 1
    pv.anchor = 4  # simulate residual mouse selection
    # Inclusive of cursor cell: covers offsets 1..4 → text[1:5].
    assert pv.selection == (1, 5)
    pv.action_move_right()
    # anchor cleared, selection gone, cursor advanced.
    assert pv.anchor is None
    assert pv.selection is None
    assert pv.cursor == 2


# ---------------------------------------------------------------------------
# Mouse-coordinate → offset mapping
# ---------------------------------------------------------------------------


def test_xy_to_offset_single_line() -> None:
    pv = _make("Joe gained Perfect Pitch.", width=80)
    # Column 11 on line 0 → offset 11 ("P" of Perfect).
    assert pv._xy_to_offset(11, 0) == 11
    assert pv._xy_to_offset(24, 0) == 24


def test_xy_to_offset_clamps_overflow() -> None:
    pv = _make("hello", width=80)
    # Click past end of line clamps to end-of-line.
    assert pv._xy_to_offset(99, 0) == 5
    # Click below content clamps to last line.
    assert pv._xy_to_offset(0, 99) == 0


def test_xy_to_offset_wrapped_line() -> None:
    # 12 chars, width 5 → lines (0,5)/(5,10)/(10,12).
    pv = _make("abcdefghijkl", width=5)
    assert pv._xy_to_offset(0, 0) == 0
    assert pv._xy_to_offset(4, 0) == 4
    assert pv._xy_to_offset(0, 1) == 5
    assert pv._xy_to_offset(2, 2) == 12  # 10+2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_set_text_resets_state() -> None:
    pv = _make("hello world")
    pv.cursor = 5
    pv.anchor = 0
    pv.visual_mode = True
    pv.set_text("new")
    assert pv.text == "new"
    assert pv.cursor == 0
    assert pv.anchor is None
    assert pv.visual_mode is False
    assert pv.selection is None


def test_clear_selection_idempotent() -> None:
    pv = _make("hello")
    assert pv.selection is None
    pv.clear_selection()  # no-op
    assert pv.selection is None
    pv.cursor = 2
    pv.anchor = 0
    pv.clear_selection()
    assert pv.selection is None
    # Cursor preserved.
    assert pv.cursor == 2


def test_selected_text_matches_substring() -> None:
    text = "Joe gained Perfect Pitch."
    pv = _make(text)
    # Selection from 11 to 24 with inclusive cursor cell → "Perfect Pitch."
    pv.cursor = 11
    pv.anchor = 11
    pv.cursor = 24
    assert pv.selected_text == "Perfect Pitch."


# ---------------------------------------------------------------------------
# Mouse drag flow (synthetic)
# ---------------------------------------------------------------------------


class _FakeEvent:
    """Minimal stand-in for textual events.MouseDown/Move/Up."""

    def __init__(self, x: int, y: int, button: int = 1) -> None:
        self.x = x
        self.y = y
        self.button = button

    def stop(self) -> None:
        pass


def test_mouse_drag_selects_range(monkeypatch) -> None:
    pv = _make("Joe gained Perfect Pitch.", width=80)

    # Stub out methods the real Textual runtime would provide.
    monkeypatch.setattr(pv, "focus", lambda: None)
    monkeypatch.setattr(pv, "capture_mouse", lambda: None)
    monkeypatch.setattr(pv, "release_mouse", lambda: None)
    monkeypatch.setattr(pv, "refresh", lambda *a, **kw: None)

    pv.on_mouse_down(_FakeEvent(11, 0))
    assert pv.cursor == 11
    assert pv.anchor == 11

    pv.on_mouse_move(_FakeEvent(24, 0))
    assert pv.cursor == 24
    # Inclusive of cursor cell — drag-to-x=24 includes the period.
    assert pv.selection == (11, 25)
    assert pv.selected_text == "Perfect Pitch."

    pv.on_mouse_up(_FakeEvent(24, 0))
    # Selection preserved (drag != click).
    assert pv.selection == (11, 25)


def test_mouse_click_without_drag_clears_selection(monkeypatch) -> None:
    pv = _make("hello world", width=80)

    monkeypatch.setattr(pv, "focus", lambda: None)
    monkeypatch.setattr(pv, "capture_mouse", lambda: None)
    monkeypatch.setattr(pv, "release_mouse", lambda: None)
    monkeypatch.setattr(pv, "refresh", lambda *a, **kw: None)

    pv.on_mouse_down(_FakeEvent(3, 0))
    pv.on_mouse_up(_FakeEvent(3, 0))
    # No drag — anchor cleared.
    assert pv.anchor is None
    assert pv.selection is None
    assert pv.cursor == 3


# ---------------------------------------------------------------------------
# Vim count prefix and extended motions (W/e/E/f/F/t/T)
# ---------------------------------------------------------------------------


class _FakeKeyEvent:
    """Stand-in for textual.events.Key with the same shape the widget reads."""

    def __init__(self, key: str, character: str | None = None) -> None:
        self.key = key
        # Textual's Key event auto-fills character from a single-char key name.
        if character is None and len(key) == 1:
            character = key
        self.character = character
        self._stopped = False
        self._prevented = False

    def stop(self) -> None:
        self._stopped = True

    def prevent_default(self) -> None:
        self._prevented = True


def _send(pv: PassageView, *keys: str) -> None:
    """Drive on_key with a sequence of single-char keys.

    Only printable single-character keys are supported here — that's all the
    new tests exercise (digits, letters, punctuation).
    """
    for k in keys:
        pv.on_key(_FakeKeyEvent(k))


def test_count_prefix_motion() -> None:
    pv = _make("abc def ghi jkl")
    # "3w" — three words forward from offset 0 → start of "jkl" at 12.
    _send(pv, "3")
    assert pv._pending_count == "3"
    _send(pv, "w")
    # on_key falls through for "w" (it's not an operator); but the binding
    # dispatcher isn't running here, so we invoke the action directly to
    # consume the count the same way Textual would.
    # (on_key cleared _pending_count? No — it only sets pending state for
    # digits/operators; the action consumes the count.)
    pv.action_word_forward()  # consumes the count
    assert pv.cursor == 12


def test_count_prefix_resets_after_motion() -> None:
    pv = _make("abc def ghi jkl mno")
    _send(pv, "3")
    pv.action_word_forward()
    assert pv.cursor == 12
    # Now plain w — should advance one word, not three.
    pv.action_word_forward()
    assert pv.cursor == 16  # start of "mno"


def test_W_word_forward_treats_punctuation_as_part_of_word() -> None:
    pv = _make("foo.bar baz")
    pv.action_WORD_forward()
    assert pv.cursor == 8  # "baz"
    # Compare to lowercase w which would land on "bar" at offset 4.
    pv2 = _make("foo.bar baz")
    pv2.action_word_forward()
    assert pv2.cursor == 4


def test_e_end_of_word() -> None:
    pv = _make("abc def")
    pv.action_end_of_word()
    assert pv.cursor == 2  # last char of "abc"
    pv.action_end_of_word()
    assert pv.cursor == 6  # last char of "def"


def test_E_end_of_WORD() -> None:
    pv = _make("foo.bar baz")
    pv.action_end_of_WORD()
    # End of "foo.bar" = offset 6.
    assert pv.cursor == 6
    pv.action_end_of_WORD()
    # End of "baz" = offset 10.
    assert pv.cursor == 10


def test_f_find_char_forward() -> None:
    pv = _make("the quick brown fox")
    _send(pv, "f", "b")
    assert pv.cursor == 10  # "b" of "brown"


def test_F_find_char_back() -> None:
    pv = _make("the quick brown fox")
    pv.cursor = 18
    _send(pv, "F", "b")
    assert pv.cursor == 10


def test_t_until_char() -> None:
    pv = _make("the quick brown fox")
    _send(pv, "t", "b")
    assert pv.cursor == 9  # one before "b"


def test_T_until_char_back() -> None:
    pv = _make("the quick brown fox")
    pv.cursor = 18
    _send(pv, "T", "b")
    assert pv.cursor == 11  # one after the "b" we found


def test_3fx_count_with_find() -> None:
    pv = _make("a-b-c-d-e")
    # "3f-" — jump to the 3rd hyphen forward. Hyphens are at offsets 1, 3, 5, 7.
    _send(pv, "3", "f", "-")
    assert pv.cursor == 5


def test_pending_op_clears_on_unrelated_key() -> None:
    pv = _make("hello world")
    _send(pv, "f")
    assert pv._pending_op == "f"
    # Send a non-character key (e.g. an arrow). Textual sets character=None.
    pv.on_key(_FakeKeyEvent("left", character=None))
    # No crash; pending op cleared; no movement.
    assert pv._pending_op is None
    assert pv.cursor == 0


def test_zero_is_line_start_when_no_count_pending() -> None:
    pv = _make("hello world\nfoo bar", width=80)
    pv.cursor = 5
    _send(pv, "0")
    assert pv.cursor == 0


def test_zero_is_a_digit_when_count_pending() -> None:
    pv = _make("a b c d e f g h i j k l m n", width=80)
    # "10l" — move 10 chars right.
    _send(pv, "1", "0")
    assert pv._pending_count == "10"
    pv.action_move_right()
    assert pv.cursor == 10


def test_count_with_move_right() -> None:
    pv = _make("0123456789abcdef")
    _send(pv, "5")
    pv.action_move_right()
    assert pv.cursor == 5


def test_dollar_still_works_with_new_state() -> None:
    pv = _make("hello world")
    pv.action_line_end()
    assert pv.cursor == 11


def test_f_not_found_does_not_move() -> None:
    pv = _make("the quick brown fox")
    pv.cursor = 4
    _send(pv, "f", "z")  # 'z' not on this line
    assert pv.cursor == 4


def test_f_is_line_scoped() -> None:
    # Hard newline splits visual lines. f should not cross.
    pv = _make("foo bar\nbaz qux", width=80)
    pv.cursor = 0
    _send(pv, "f", "q")  # 'q' is on the second line, not first
    assert pv.cursor == 0
    # Move to the second line and try again.
    pv.cursor = 8  # "b" of "baz"
    _send(pv, "f", "q")
    assert pv.cursor == 12


def test_gg_chord_via_on_key() -> None:
    pv = _make("hello world")
    pv.cursor = 8
    _send(pv, "g")
    assert pv._pending_g is True
    _send(pv, "g")
    assert pv.cursor == 0
    assert pv._pending_g is False
