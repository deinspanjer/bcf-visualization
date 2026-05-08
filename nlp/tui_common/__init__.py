"""Shared TUI primitives reused by ``nlp/tui/`` and ``scripts/forge_curator/``.

The original interactive widgets (vim-style cursor motions, prose
rendering, selection, mouse handling) live in ``nlp/tui/passage_view.py``
and grew up serving the labelling TUI. The Forge Curator wants the same
foundation. Rather than duplicate the implementation, this module is
the canonical re-export point: both apps import the shared widget from
here so future improvements stay in one place.

Wider Phase 0 scope: only the ``PassageView`` widget is exported so far.
Other reusable bits (panel-layout helpers, regex bar, status bar) live in
this package's submodules and are added as Phase 1 and Phase 2 develop.
"""

from nlp.tui.passage_view import PassageView

__all__ = ["PassageView"]
