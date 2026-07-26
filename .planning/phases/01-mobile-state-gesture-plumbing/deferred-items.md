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
