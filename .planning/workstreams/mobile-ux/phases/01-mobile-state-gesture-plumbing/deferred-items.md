# Deferred Items — Phase 01 (out-of-scope discoveries)

## 2026-07-26 — plan 01-01 executor

- `scripts/verify.py` fails at `data_release.py check-derived` on pre-existing
  local derived-data staleness, unrelated to this plan's web/mobile changes:
  - `manifest entry perk_directory has stale sha256; run scripts/data_release.py manifest`
  - `could not validate predicted_rolls.json freshness: multi_grab override for
    ch 95.5 roll #0 references 'Minor Blessing Zeus – Lightning' but no obtained
    perk in the mechanical or mention chapter has that name (mechanical paid:
    ['arena', 'central control', 'gym', 'your robots']; mention_chapter_num: 95.5)`
  - Belongs to the Track B curation/data pipeline (recent curation through ch 96).
    Not fixed here per executor scope boundary. Verification run instead:
    `node --check web/app.js web/mobile-gestures.js` plus
    `.venv/bin/python -m pytest tests/test_web_app_integration.py tests/test_mobile_plumbing.py -q`
    (all green).

## 2026-07-26 — plan 01-04 executor (phase gate)

- Full `.venv/bin/python -m pytest` (no path filter) surfaces 24 additional
  failures, all in Track B data-consistency modules that read the same stale
  `data/derived/*.json` state `data_release.py check-derived` already flags
  above (recent curation through ch 96/ch 95.5 not yet fully regenerated):
  `test_chapter_alignment_fingerprints.py` (1), `test_data_package_contract.py`
  (1), `test_forge_curator.py` (4), `test_model_validation.py` (5),
  `test_roll_ordinal_contract.py` (9), `test_roll_position_invariants.py` (2),
  `test_web_data_contract.py` (1). A one-line non-fatal warning also appears
  during `check-derived` for a second chapter (`ch 95 override drops paid
  perk(s) ['Minor Blessing Zeus – Lightning', 'Unnatural Skill: Curses']`) —
  this is printed by `scripts/multi_grab.py`'s intentional drop-warning path,
  not part of the raised `RuntimeError`'s detail list, and is the same
  underlying staleness as the already-documented ch 95.5 failure above.
  None of these 24 failures touch `web/`, `tests/test_desktop_smoke.py`,
  `tests/test_mobile_plumbing.py`, or `tests/test_web_app_integration.py` —
  those three Phase 1 suites are fully green inside this same full run (zero
  entries for them in the failure list). Not fixed here per executor scope
  boundary (Track B data pipeline, out of scope for Track A Phase 1). Belongs
  to the same Track B epub/pipeline refresh (Phase 5) that will resolve the
  `check-derived` staleness above.
