"""Queue / state management for annotation candidates.

Wraps ``nlp.candidates.iter_candidates`` (when available) with a small
state object that remembers position, supports go-back, and persists to
``data/labeled/.tui_state.json``.

If ``nlp.candidates`` is not yet implemented (the bootstrap agent hasn't
landed yet) we fall back to a simple stub so the TUI is still importable
and testable.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

__all__ = ["Candidate", "QueueState", "next_candidate"]

# ---------------------------------------------------------------------------
# Candidate dataclass (mirrors nlp.candidates.Candidate)
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """A passage candidate for annotation."""

    passage_id: str
    chapter_num: str
    section_index: int
    epub_char_start: int
    epub_char_end: int
    text: str
    source: str = "manual"


# ---------------------------------------------------------------------------
# QueueState
# ---------------------------------------------------------------------------

STRATEGY_CHOICES = ("balanced", "event_focused", "low_confidence", "coverage_gap")


@dataclass
class QueueState:
    """Mutable queue state shared by the TUI.

    Parameters
    ----------
    strategy:
        Candidate selection strategy (persisted to state file).
    jsonl_path:
        The active output JSONL path; used to derive the state file path.
    epub_path:
        Optional path to the EPUB (forwarded to iter_candidates).
    limit:
        Maximum candidates to load per fill.
    """

    strategy: str = "balanced"
    jsonl_path: Path = Path("data/labeled/spans/pilot.jsonl")
    epub_path: Path | None = None
    limit: int = 250

    _queue: list[Candidate] = field(default_factory=list, repr=False)
    _cursor: int = field(default=0, repr=False)
    _history: list[Candidate] = field(default_factory=list, repr=False)
    _flagged: set[str] = field(default_factory=set, repr=False)
    _last_model: str = field(default="", repr=False)
    _save_count: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # State file
    # ------------------------------------------------------------------

    @property
    def state_file(self) -> Path:
        return self.jsonl_path.parent / ".tui_state.json"

    def load_state(self) -> None:
        """Restore persisted state from the state file."""
        if not self.state_file.exists():
            return
        try:
            data = json.loads(self.state_file.read_text())
            self.strategy = data.get("strategy", self.strategy)
            self._last_model = data.get("last_model", "")
            self._cursor = data.get("cursor", 0)
            self._flagged = set(data.get("flagged", []))
        except (json.JSONDecodeError, OSError):
            pass

    def save_state(self) -> None:
        """Persist queue state to the state file."""
        data: dict[str, Any] = {
            "strategy": self.strategy,
            "last_model": self._last_model,
            "cursor": self._cursor,
            "flagged": sorted(self._flagged),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(data, indent=2))
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def fill_queue(self, already_labeled: set[str] | None = None) -> int:
        """Fill ``_queue`` from iter_candidates.  Returns number added."""
        already_labeled = already_labeled or set()
        added = 0
        try:
            # Try to import the real implementation
            from nlp.candidates import iter_candidates  # type: ignore[import]

            for cand in iter_candidates(
                strategy=self.strategy,
                limit=self.limit,
                epub_path=self.epub_path,
            ):
                if cand.passage_id not in already_labeled:
                    self._queue.append(
                        Candidate(
                            passage_id=cand.passage_id,
                            chapter_num=cand.chapter_num,
                            section_index=cand.section_index,
                            epub_char_start=cand.epub_char_start,
                            epub_char_end=cand.epub_char_end,
                            text=cand.text,
                            source=cand.source,
                        )
                    )
                    added += 1
        except ImportError:
            # bootstrap agent hasn't landed yet — stub empty queue
            pass
        return added

    @property
    def current(self) -> Candidate | None:
        if 0 <= self._cursor < len(self._queue):
            return self._queue[self._cursor]
        return None

    @property
    def position(self) -> int:
        """1-based position in the queue (0 if empty)."""
        return self._cursor + 1 if self._queue else 0

    @property
    def total(self) -> int:
        return len(self._queue)

    def advance(self) -> Candidate | None:
        """Move to the next candidate; returns the new current or None."""
        if self._cursor < len(self._queue) - 1:
            self._cursor += 1
            self._save_count += 1
            if self._save_count % 10 == 0:
                self.save_state()
            return self._queue[self._cursor]
        return None

    def go_back(self) -> Candidate | None:
        """Move to the previous candidate; returns it or None."""
        if self._cursor > 0:
            self._cursor -= 1
            return self._queue[self._cursor]
        return None

    def skip(self) -> Candidate | None:
        """Skip current candidate (same as advance)."""
        return self.advance()

    def flag_current(self) -> None:
        """Flag the current passage for follow-up."""
        if (c := self.current) is not None:
            self._flagged.add(c.passage_id)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def flagged(self) -> frozenset[str]:
        return frozenset(self._flagged)


def next_candidate(queue_state: QueueState, *, strategy: str = "balanced") -> Candidate | None:
    """Return the next Candidate from *queue_state*, applying *strategy*.

    This is the function signature called out in the playbook.
    It is a thin shim over ``queue_state.advance()`` that also updates
    the strategy when it changes.
    """
    if strategy != queue_state.strategy:
        queue_state.strategy = strategy
    return queue_state.advance()
