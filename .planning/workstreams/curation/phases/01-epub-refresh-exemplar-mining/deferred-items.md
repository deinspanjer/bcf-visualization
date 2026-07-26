# Deferred Items — Phase 01 (curation workstream, out-of-scope discoveries)

## 2026-07-26 — plan 01-01 executor

- **`build_chapter_facts.py` refreshes the runtime manifest before
  `visualization_facts.json` is rebuilt for the same run — a DAG ordering gap
  that only surfaces when the epub's chapter count actually changes.**

  During Task 3's `scripts/pipeline.py --target data --force` (after the epub
  refresh grew the story from 195 to 198 chapters, last `120.2` → `121.1`),
  the `build_chapter_facts` step failed:
  ```
  File ".../scripts/data_release.py", line 235, in _validate_source_epub_story
      raise ValueError(...)
  ValueError: source EPUB chapter_count 198 does not match package story_chapter_ordinal 195
  ```

  Root cause: `scripts/build_chapter_facts.py` writes a fresh
  `data/derived/chapter_facts.json` and then unconditionally calls
  `refresh_current_runtime_manifest(source_dir=DERIVED, allow_missing_required=True)`.
  That function's story-freshness check
  (`scripts/data_release.py::_story_freshness`) reads
  `data/derived/visualization_facts.json` — but that file is only rebuilt by
  the *later* `build_visualization_facts` step in `pipeline.py`'s DAG (it
  depends on `chapter_facts.json`), so mid-run it is still the pre-refresh
  artifact (confirmed: `data/derived/data_package.json` was stamped
  `ch195-120.2`, `generated_at: 2026-05-21T21:57:55Z`, well before this
  phase's work).

  The `allow_missing_required=True` flag's bootstrap fallback
  (`_bootstrap_story_freshness`, which reads `chapter_facts.json` instead)
  only activates when `visualization_facts.json` **does not exist at all**
  (`data_release.py` line 529: `if allow_missing_required and not
  (source_dir / "visualization_facts.json").exists(): ...`) — it does not
  activate when the file merely exists-but-is-stale, which is exactly this
  case. This has presumably never surfaced before because every prior
  `--force` run either left the epub chapter count unchanged (no mismatch
  possible) or never regenerated a chapter-count-changed `chapter_facts.json`
  and a stale `visualization_facts.json` in the same invocation.

  **Workaround used this session (orchestrator-approved, no code change):**
  ran `.venv/bin/python scripts/build_visualization_facts.py` once, manually,
  ahead of the `build_chapter_facts` step that needed it — its declared
  inputs (`chapter_facts.json`, `constellation_wireframes.json`,
  `predicted_rolls.json`) were already fresh on disk from the same regen run.
  This refreshed `visualization_facts.json`/`data_package.json` to
  198/`121.1`, breaking the circularity; the subsequent
  `pipeline.py --target data --force` retry then completed cleanly through
  its `--target data` closure (final step `build_visualization_facts`).

  **Not fixed here** — this is pipeline/`data_release.py` code, not a
  hand-curated or mechanically-regenerable data file, and touching it is a
  process/code decision outside this data-curation plan's scope. A proper
  fix belongs to a follow-up: either make `_bootstrap_story_freshness`'s
  fallback trigger on *staleness* (chapter-count/last-chapter mismatch), not
  just *absence*, of `visualization_facts.json`, or move
  `refresh_current_runtime_manifest`'s invocation out of
  `build_chapter_facts.py` entirely so it only runs after
  `build_visualization_facts` in the same invocation. Anyone hitting this
  again after a future epub chapter-count change should apply the same
  workaround: run `build_visualization_facts.py` once manually before
  retrying the full `--force` regen.
