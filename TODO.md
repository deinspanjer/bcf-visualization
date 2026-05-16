# Future work

## Data and extraction

- Keep the data-release workflow's private source repo path as the
  preferred EPUB input and treat FicHub download as an explicit fallback,
  not the normal release path.
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

- Execute the test-surface cleanup roadmap in
  [docs/test_surface_cleanup_plan.md](docs/test_surface_cleanup_plan.md):
  replace current-story-shape assertions with stable fixtures, add
  fixture-backed web UI integration tests, split large TUI tests by
  capability, and map every major feature to an owning test layer.
- Top-level `data/derived/*.json` is ignored and release-backed Pages
  deploy plus local maintainer bootstrap were validated with
  `bcf-visualization-data-v20260509.3-ch194-120.1`; keep monitoring the
  bootstrap workflow before considering history rewrite.
- Keep data release tags and asset names aligned with the visible app
  data-version label: build date/ordinal plus latest BCF chapter ordinal
  and descriptive chapter number.
- Treat any future `git-filter-repo` cleanup as a coordinated migration
  with a write freeze, branch guidance, and reclone instructions.
- Decide whether the long mechanics and analytics sections in
  `README.md` should move into focused docs under `docs/` after the
  next milestone.
- Keep `plans/daw_scrubber_v2.md` as historical milestone context; do
  not use it as the canonical TODO list.
- Confirm final public credit wording with the author/source display
  names before publishing broadly.
- Rename the final runtime payload from `chapter_facts.json` to a
  broader name such as `bcf-visualization-data.json`, with compatibility
  updates across schemas, web loading, tests, and release packaging.
- Move committed schema contracts out of `data/derived/_schemas/` into
  a non-derived schema/contract path, preserving compatibility for the
  validators during the transition.
