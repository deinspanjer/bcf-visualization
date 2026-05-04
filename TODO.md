# Future work

## Data and extraction

- Locate and document any later author clarification about which
  non-Joe-POV sections count for CP earning.
- Reclassify sections under the suspected "Joe on screen" rule while
  preserving the current classification for traceability.
- Re-run `predict_rolls.py`, roll-location extraction, validation, and
  `build_chapter_facts.py` after any section-classification change.
- Revisit `roll_locations_validation.json` findings after the
  reclassification pass; current "curator divergence" conclusions may
  be artifacts of an overly strict simulator rule.
- Extract in-world dates per chapter into a structured manual or
  derived file so the scrubber can add an in-world date track.
- Research the public Google Sheet layout for perk descriptions and add
  stable per-perk or per-tab links where possible.

## Visualization

- Add an in-world time/date track once chapter-level in-world dates are
  available.
- Link perk names in tooltips, selected-chapter details, and recent
  acquisitions to source descriptions once `description_url` exists.
- Continue refining dense roll clusters at high zoom, especially where
  multiple untracked acquisitions fall in the same chapter.
- Consider a richer interaction for non-clickable date/POV/recovery
  ticks if hover-only metadata remains too subtle.

## Documentation and maintenance

- Decide whether the long mechanics and analytics sections in
  `README.md` should move into focused docs under `docs/` after the
  next milestone.
- Keep `plans/daw_scrubber_v2.md` as historical milestone context; do
  not use it as the canonical TODO list.
- Confirm final public credit wording with the author/source display
  names before publishing broadly.

## Research

- Evaluate whether a local NLP model trained or tuned on the primary
  EPUB could reliably extract power-acquisition facts from prose without
  using a subscription LLM. Key questions: annotation volume, hardware
  requirements, expected precision/recall, and whether a smaller local
  model plus deterministic validators would be enough.
