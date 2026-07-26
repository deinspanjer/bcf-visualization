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

## 2026-07-26 — plan 01-02 executor

- **Chapter 104's alignment anchor was deliberately left stale — needs a TUI
  edit before it can be safely re-stamped.**

  `scripts/chapter_alignment.py check` flagged 5 chapters (100, 104, 109,
  112, 114) with stored `_fingerprint` values that disagreed with the
  freshly-regenerated predicted-roll shape. A read-only, isolated
  investigation (reconstructing the pre-refresh 195-chapter epub state from
  `data/private-source`'s own git history via `git show`, run entirely
  against a scratch `BCF_DATA_DIR`, never touching the real repo) confirmed
  the drift for **all 5 chapters** traces to a single cause: the
  Dre-approved ch 95.5 `multi_grab` `mention_chapter_num` fix (01-01, commit
  `1a2c9da`), not the epub content refresh. The 195-chapter epub + that fix
  reproduces byte-identical fingerprints to the 198-chapter epub + that fix;
  epub growth alone changes nothing for these chapters. The ch 95.5 override
  that trips this was itself added 2026-06-01 (`f3478f7`), a week *after*
  these 5 fingerprints were stamped 2026-05-23 (`b6c30383`) — this is
  pre-existing curation-data drift the epub refresh happened to surface
  (first full `--force` regen in ~2 months), not something it introduced.

  Dre reviewed each chapter's diff interactively (`scripts/realign_chapters.py`,
  never `--yes`) and accepted 100, 109, 112, 114 (re-stamped, commit
  `cc84f84`). **Chapter 104 was deliberately skipped**:

  - `data/derived/roll_validation.json` reports
    `paid_rolls_exceed_predicted_slots` for ch 104: 2 curated hit rolls
    (Toolkits: "Entrance Hall" cluster; Resources and Durability: "Firestorm")
    require more slots than the 1 predicted roll the current model computes
    for that chapter — a real capacity mismatch, not just a stale hash.
  - Per `realign_chapters.py`'s own warning, a plain fingerprint re-stamp
    would silence the alignment guard **without** fixing the underlying
    mismatch — the override's `rolls` array needs to be edited in the
    curator TUI first (re-mapping which predicted slot each curated hit
    corresponds to, or resolving why the model only computes 1 slot where 2
    are needed) before re-stamping ch 104's `_fingerprint`.
  - **Status:** stale anchor left in place by choice. `chapter_alignment.py
    check` / `scripts/verify.py` will continue to fail on ch 104 until Dre
    completes this TUI review. This is a known-accepted gap, not a
    regression — see Task 3 verification results in
    `01-02-SUMMARY.md` for the exact failure this produces.

- **Latent risk: 7 uncurated chapters may carry the same ch95.5-fix ripple
  invisibly, with no anchor to catch it.**

  Chapters 98, 99.1, 110, 110.3, 113, 115, 116.3 all appear in
  `roll_validation.json`'s INFEASIBLE list but have **no** override entry in
  `data/manual/chapter_roll_overrides.json` at all (they're among the 77
  chapters not yet hand-curated) — so `chapter_alignment.py` has nothing to
  compare against for them and cannot flag drift. They may be experiencing
  the same regime-3 boundary shift from the ch 95.5 fix as ch 100/104/109/
  112/114 did. Whoever curates these chapters in Phases 3-4 (exemplar
  mining / agent curation) should re-check their predicted-roll shape
  against `roll_validation.json` at that time rather than assuming a clean
  slate.

- **`scripts/realign_chapters.py` writes JSON with `ensure_ascii=True`,
  causing whole-file unicode-escaping churn in a hand-curated file every
  time it runs.**

  Running the tool to re-stamp ch 100/109/112/114 rewrote the *entire*
  `data/manual/chapter_roll_overrides.json` via
  `OVERRIDES_PATH.write_text(json.dumps(doc, indent=2) + "\n")` (see
  `_restamp()`), which defaults to `ensure_ascii=True` and escaped ~14
  unrelated lines of literal unicode (en-dash `–`, ellipsis `…`, etc.) into
  `\uXXXX` sequences across hand-curated evidence quotes/perk names,
  diverging from the rest of the codebase's established
  `ensure_ascii=False` convention (e.g. `_common.write_validated_json`).
  This was caught and manually reverted before committing this session
  (diff reduced back to exactly the 4 intended fingerprint lines) but would
  silently corrupt the diff for any future re-stamp session that didn't
  catch it. **Not fixed here** (out of this data-curation plan's scope) —
  a one-line fix (`json.dumps(doc, indent=2, ensure_ascii=False)`) in
  `scripts/realign_chapters.py::_restamp()` would prevent recurrence.

- **Task 3 (`scripts/verify.py`) result: 5 pre-existing test failures remain,
  none caused by the ch 104 skip — known-accepted gap, not a regression.**

  `scripts/verify.py` (git diff --check, then `data_release.py
  check-derived`, then full unfiltered pytest) exits non-zero:
  `git diff --check` passed silently; `check-derived` printed only the
  known, unrelated `multi_grab: ch 95 override drops paid perk(s)` info
  line and reported "local derived data ok"; the full pytest run reports
  **5 failed, 573 passed**:

  ```
  FAILED tests/test_forge_curator.py::test_stats_click_selects_actual_visible_roll_line
  FAILED tests/test_forge_curator.py::test_stats_click_refocuses_prose_for_motion_and_space_chords
  FAILED tests/test_forge_curator.py::test_stats_click_jumps_prose_to_selected_roll_location
  FAILED tests/test_forge_curator.py::test_click_roll_then_space_p_opens_perk_picker_for_selected_roll
  FAILED tests/test_roll_ordinal_contract.py::test_chapter_55_1_source_roll_six_borrows_first_56_prediction
  ```

  The first 4 assert against chapter 79's TUI stats-panel rendering
  (expect `"# 2 (R520/P548)"` to appear; it doesn't — `StopIteration`). The
  5th asserts `roll_facts.json`'s source-ordinal 387 maps to
  `source_chapter_num == "55.1"`; it now resolves to `"57"`.

  **Verified none of these are caused by the deliberately-skipped ch 104
  alignment anchor:** `chapter_alignment.py`'s guard is wired into
  `build_chapter_facts.py` only as a soft, chapter-scoped
  `model_issues_by_chapter()` annotation (see that module's own docstring:
  "surface stale chapter-local override alignment on the affected chapters
  rather than aborting unrelated curation work") — it is never a hard
  `SystemExit`/pytest assertion, and `data_release.py check-derived` does
  not call `chapter_alignment.fail_if_misaligned()` at all (confirmed via
  `grep`). Re-ran `scripts/chapter_alignment.py check` standalone after the
  re-stamp commit: it now reports **only ch 104** (1 mismatch, down from
  5) — exactly the expected post-re-stamp state, and unrelated to any of
  the 5 pytest failures above (none reference chapters 100, 104, 109, 112,
  or 114).

  **These 5 failures are pre-existing Track B staleness, unrelated to this
  phase's epub-refresh work**, per cross-reference with
  `.planning/workstreams/mobile-ux/phases/01-mobile-state-gesture-plumbing/deferred-items.md`'s
  previously-documented 24-failure baseline (`test_forge_curator.py`: 4,
  `test_roll_ordinal_contract.py`: 9, plus 5 other files now fully
  resolved by the 01-01/01-02 pipeline regen and re-stamping):
  - `test_forge_curator.py`'s failure count is **unchanged at 4** — same
    file, same count, chapter-79 TUI fixture data untouched by anything in
    this phase (epub refresh, ch 95.5, ch 121.1, or the ch 100-114
    alignment work).
  - `test_roll_ordinal_contract.py` dropped from 9 failures to 1 — 8 of 9
    were resolved by this phase's regen. The one that remains concerns
    chapters 55.1/56/57, which are unrelated to anything touched by this
    plan; the pipeline's own logs already surface a matching,
    long-standing warning every run (`derive_roll_facts: ch 55.1 override
    does not cover curator hit row #0` / `#4`), consistent with this being
    pre-existing curation-data staleness in a different part of the
    corpus, not something introduced here.
  - `test_chapter_alignment_fingerprints.py`, `test_data_package_contract.py`,
    `test_model_validation.py`, `test_roll_position_invariants.py`, and
    `test_web_data_contract.py` are now **fully green** (0 failures) — the
    epub-refresh regen (01-01) and the manifest re-stamp / fingerprint
    re-stamp (01-02) resolved all previously-documented failures in those
    5 files.

  **Not fixed here** — per the same Rule-3 exclusion this phase has
  observed throughout (curation-authority: agents/executors never
  hand-patch trust-critical data to force a green run), these 5 remaining
  failures are known-accepted gaps: ch 104's TUI re-mapping is Dre's
  planned follow-up (see above); chapters 79 and 55.1/56/57 are pre-existing
  curation-data issues outside this plan's scope (epub refresh /
  exemplar-mining hard gate), tracked here for whoever next works Track B
  curation debt.
