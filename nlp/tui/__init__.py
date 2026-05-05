"""Textual review TUI for the BCF local NLP labeling pipeline.

Sub-modules:
  app       -- Textual App subclass; run with ``python -m nlp.tui.app``
  persist   -- Append-only JSONL store + WAL
  candidates -- QueueState wrapper around nlp.candidates.iter_candidates
  proposals  -- Async wrapper around nlp.bootstrap.propose
"""
