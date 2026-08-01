# Phase 2 (Mechanical Verifier) — Deferred Items

## `_split_sections`/`_strip_to_spaces` now a three-way duplication

**Status:** Open
**Deferred at:** 02-01 (Task 1)

`scripts/cp_word_index.py`'s `_split_sections` and `_strip_to_spaces` were
copied (per D-01's explicit instruction — not imported, to keep the new
module's dependency graph confined to itself rather than reaching into
`scripts/find_roll_locations.py`, which predates this phase and is out of
D-01's literal scope) from `scripts/find_roll_locations.py:305`/`:81`.

This makes `cp_word_index.py`'s copy a **third** independent copy of these
two functions in the repository, alongside the pre-existing, undocumented
duplicate pair already present in:

- `scripts/find_roll_locations.py:305` (`_split_sections`) / `:81` (`_strip_to_spaces`)
- `scripts/extract_chapter_sections.py:461` (equivalent section-splitting logic)

D-01's literal scope was "rewrite `find_text_backed_rolls.py` to consume the
extracted tokenizer module," not "consolidate the tokenizer across the
codebase." Fully resolving the now-three-way duplication would mean
touching `find_roll_locations.py`, `extract_chapter_sections.py`, and
`build_chapter_facts.py` — out of this phase's scope. Tracked here as future
work, matching the pattern Phase 1 used for its own deferred items.
