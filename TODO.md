# Future work

## Data and extraction

- Keep the data-release workflow's private source repo path as the
  preferred EPUB input and treat FicHub download as an explicit fallback,
  not the normal release path.
- Enhance the private-source scripts with clear bidirectional commands:
  one to publish/copy a local EPUB into the private source repo, and one
  to hydrate `data/raw/Brocktons_Celestial_Forge.epub` from the latest
  private source ref or an explicitly selected source tag.
- Locate and document any later author clarification about which
  non-Joe-POV sections count for CP earning.
- Reclassify sections under the suspected "Joe on screen" rule while
  preserving the current classification for traceability.
- Re-run `predict_rolls.py`, roll-location extraction, validation, and
  `build_chapter_facts.py` after any section-classification change.
- Revisit `roll_locations_validation.json` findings after the
  reclassification pass; current "curator divergence" conclusions may
  be artifacts of an overly strict simulator rule.
- Resolve the unbound source rolls in chapters 56 and 67 — both chapters
  have predicted slots and curated source rolls but zero bindings between
  them (22 unbound rolls corpus-wide). Needs a curator-TUI judgment on the
  7-vs-6 and 5-vs-4 mismatches, same shape as the chapter 104 item. Details
  and the full unbound list: `docs/unbound_source_rolls_ch56_ch67.md`.
- Re-anchor the four `tests/test_forge_curator.py` stats-click tests on
  (chapter, within-chapter ordinal) instead of literal curator roll labels
  like `R520/P548`; curator roll numbers renumber on every curation pass,
  so the current fixtures go stale repeatedly. Same doc.
- Extract in-world dates per chapter into a structured manual or
  derived file so the scrubber can add an in-world date track.
- Research the public Google Sheet layout for perk descriptions and add
  stable per-perk or per-tab links where possible.

## Visualization

- Complete the real-device Mobile UX acceptance pass before treating mobile
  as fully validated: confirm VoiceOver speaks roll-change announcements and
  stays silent during playback; exercise the landing-page `?` dialog on iOS
  Safari; measure `innerWidth` and the selected layout with Safari's
  "Request Desktop Website" enabled; and check the cinema-scrub play button's
  edge tap for a dead zone. Use the desktop-mode result to decide whether an
  in-app desktop-view toggle belongs in the backlog.
- Add an in-world time/date track once chapter-level in-world dates are
  available.
- Prominently display Survey designation codes for hit rolls in the web
  visualization now that designation data flows through derived perk
  records.
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
