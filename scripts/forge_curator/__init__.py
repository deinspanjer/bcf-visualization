"""Forge Curator TUI — interactive read/curate browser for the BCF data.

Phase 1 implementation: read-only viewer (three-panel layout, prose with
vim-style cursor, stats panel, gutter indicators, regex bar, navigation).
Phase 2+ will add curation actions, auto-save with session journal, and
per-chapter in-memory recompute.

Entry point::

    python -m scripts.forge_curator [--chapter X[.Y]]
"""

__all__ = []
