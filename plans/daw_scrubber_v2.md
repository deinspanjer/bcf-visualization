# DAW scrubber v2 — implementation plan

Status: **milestone executed; retained for historical context.**
Trigger: feedback on the v1 DAW scrubber (commit/branch in flight) — see conversation 2026-05-04.

The v1 scrubber landed a five-track DAW-style timeline against `chapter_facts.json` with k-words/sec playback and a 100k-word pre-roll. The executed milestone covers the copy/visual polish, real-world dates, POV bands, zoomed horizontal scroll, constellation/cost dots, free-perk child clusters, right-side legend, compact readout/cumulative strip, chapter-click details, and current documentation cleanup. Deferred work is tracked in `TODO.md`.

## Risk map

The rule-clarification reclassification (Phase C2) has the largest blast radius — it ripples through `predict_rolls.json`, `roll_text_evidence.json`, and `chapter_facts.json`. Do it last among the data changes; finish all the cosmetic polish first so the visual work isn't redone after the data shifts.

Two items are research-then-derive, not pure code, and require a prose pass before implementation:
- C1: locate the rule-clarification author note(s)
- C4: discover the Google Doc URL pattern for perk descriptions

The cheapest items have the biggest perceived improvement — Phase A first protects the deliverable if work is interrupted.

## Phase A — Quick polish (no data changes, ~30 min, low risk)

### A1. Pre-roll: 100k → 5k words
- File: `web/app.js`
- Change `const PRE_ROLL_WORDS = 100_000;` → `5_000`.
- Bump `LS_VERSION` to `"3"` so any saved bookmark beyond -5k resets cleanly on next load.

### A2. Header title + cross-site badges
- File: `web/index.html` (`<header>`)
- Replace the current `<h1>` and subtitle with:
  - Title text: "Brockton's Celestial Forge [Jumpchain]" wrapping a link to the SV threadmarks page.
  - Byline: "by LordRoustabout (Lord_Roustabout)".
  - Three small badges after the byline linking to:
    - SV: <https://forums.sufficientvelocity.com/threads/brocktons-celestial-forge-worm-jumpchain.70036/threadmarks>
    - FF: <https://www.fanfiction.net/s/13574944/44/Brockton-s-Celestial-Forge>
    - AO3: <https://archiveofourown.org/works/23949661/navigate>
- File: `web/style.css`
- Add `.site-badge` style: pill, monospace, subtle border. Tone: unobtrusive — not a CTA.

### A3. Survey-voice subtitle (in-character)
- File: `web/index.html`
- Replace v1 "Word-driven gacha scrubber..." text with in-character voice from Survey, written for Aisha.
- Voice notes:
  - Survey is one of Joe's tinker-built constructs (multi-perspective awareness aid).
  - Aisha is Joe's friend (Imp from Worm canon).
  - Survey's tone in-prose is helpful, slightly clinical, oriented toward making Joe's experience legible to humans.
  - Acknowledge 4th wall blindness for visualization-specific elements (counters, axes, labels) — frame them as Survey's "scaffolding" that Aisha should ignore.
- Working draft (refine before committing):
  > "Survey, here. Joe doesn't always make the Celestial Forge easy to follow, even for me — he babbles about constellations and motes and connections like everyone has the same view he does. So I built you this. The bar at the top is the story by his words; each dot is a roll, each band is when his power's resting. Hover anything to see what he was actually doing at that moment. The bits that don't quite fit the in-universe view — labels and counters and such — are just my scaffolding; ignore them like a cape ignores their costume's seams."

### A4. De-emphasize the regime band
- The full-width colored band is too prominent for what is essentially accounting metadata.
- File: `web/style.css` — drop `.regime-segment` / `.track-regime` blocks; add `.regime-change-marker` style (single 1–2px vertical line).
- File: `web/app.js` — `renderRegimeTrack` becomes `renderRegimeChangeMarkers`. Two markers at ch 91 and ch 97 (and a third after Phase C1 if a third clarification chapter exists). Hover shows tooltip in plain language; do not use the word "regime".
- Suggested ch 91 tooltip:
  > "After this chapter, every other roll attempt is skipped. Joe still earns power at the same rate; the Forge just only checks for a connection at every other 100-point milestone."
- Suggested ch 97 tooltip:
  > "Power accrues more slowly now (3,000 words per 100 points instead of 2,000), and after Joe acquires anything expensive, the Forge needs time to recover before he can earn anything new."
- Keep `point_calculation_regime` field internally where it gates color decisions; just don't surface a dedicated track.

## Phase B — New visualization layers (medium, ~1–2 hr, isolated to web/)

### B1. Constellation-colored dots + cost-sized dots
- New constant `CONSTELLATION_COLORS` (14 colors) in `web/app.js`. Hand-tuned palette over generated; 14 distinct hues that read clearly against the existing background. Draft palette and request user approval before committing.
- Cost → size map (px diameter):
  | cost | px |
  |---:|---:|
  | 0 (free) | 4 |
  | 100 | 6 |
  | 200 | 8 |
  | 300 | 9 |
  | 400 | 10 |
  | 600 | 12 |
  | 800 | 14 |
- Outcome semantics:
  - **Hits**: dot color = constellation color (we know it).
  - **Misses / unknowns**: gray (we don't know the constellation; coloring would fabricate).
  - **Untracked acquisitions**: constellation color + dashed border (narrated-but-not-simulator-fired).

### B2. Legend panel
- New panel above or beside the data panels, collapsible.
- Sections:
  - **Dot color** = constellation (14-swatch grid).
  - **Dot border** = solid (regime hit) / dashed (untracked acquisition).
  - **Dot row** = top row hits / bottom row misses / unknowns.
  - **Dot size** = perk cost (4 example sizes labeled 100/300/600/800).
  - **Shadow band** = recovery cooldown after expensive perks.
  - **Whisker** = mechanic clarification points (ch 91, ch 97, +TBD).

### B3. Real-world date track
- New track. Year-boundary ticks (2020-01-01, 2021-01-01, ...) at the position of the first chapter published in or after that year.
- Tooltip on a chapter shows `published_at` and `last_edited_at` from `chapter_facts.json`.
- Estimate: ~30 LOC in `web/app.js` (`renderRealWorldDateTrack`).

### B4. POV sections track
- New track. Per chapter, render each section as a horizontal bar colored by `pov_character`. Bar length ∝ section.word_count proportion of chapter's total_word_count.
- Color map: Joe = stable accent; others = derived palette (probably reuse constellation palette or a separate "characters" palette).
- Tooltip: section header, POV character, word count, marker_kind, classification, classification_confidence.
- Estimate: ~50 LOC.

### B5. Track stack reorganization
- Adjust `--track-*` heights and `top:` values. New target stack from top:
  1. Year ticks (real-world dates) — 16px
  2. Chapter ticks + labels — 22px
  3. POV sections track — 12px
  4. Shadow bars — 14px
  5. Roll dots (hits + misses lanes) — 56px
  6. Word axis — 16px
- Total ~136px (vs current 122px). Marginal vertical growth.

## Phase C — Data enrichments (bigger, blocking, requires research)

### C1. Locate the rule-clarification chapter
- Approach:
  1. Check the existing 14 sections with `marker_kind: "author_note"` from `chapter_sections.json` first — most likely candidates.
  2. If not found, search EPUB prose for phrasings like "on screen", "in scene", "actively present", "doing something", "modify the rule", "clarify the rule".
- Update README's "Mechanic regimes" table with the third clarification (date + chapter) once located.
- Document the new rule precisely. **Confirm wording with user before applying anywhere downstream.**

### C2. Reclassify non-MC sections under "Joe on screen" rule
- Scope: 288 currently non-MC sections (or just the post-clarification subset, depending on C1's finding). For each non-Joe-POV preamble/addendum/interlude, decide whether Joe is *physically present and acting*.
- Implementation: **LLM pass** preferred over manual review.
  - For each candidate section's first ~2000 words, ask: "Is Joe physically present in this scene and doing things, or is he merely being thought about / referenced?"
  - Output: strict yes/no + a short prose justification quote.
- Output file: extend `data/manual/section_classifications.json` with:
  - `counts_for_cp_v2: bool` (keep v1 alongside for traceability)
  - `reclassification_evidence: string` (LLM's quote/justification)
- Validation cases (calibration sanity checks):
  - **Ch 35.1 "Addendum Margaret"** — should now count (Dragon converses with Joe per user). False under new rule = calibration bug.
  - **Ch 6.1 "Interlude Taylor"** — should not count (Taylor's POV without Joe present). True = calibration bug.
- Ask user to spot-check 5 borderline calls before regenerating downstream.

### C3. In-world dates per chapter (deferred from chapter_facts spec)
- LLM pass over each chapter's first ~2000 words extracting:
  - `start_date` (YYYY-MM-DD)
  - `start_time_of_day` (morning/afternoon/evening/night)
  - `end_date`, `end_time_of_day`
  - `evidence` (one quote)
- Output: new `data/manual/chapter_in_world_dates.json` consumed by `build_chapter_facts.py`.
- Reference: `timeline.json` already has 26 dated events; many will appear in prose and serve as anchors.
- Mostly orthogonal to C2 — can run in parallel.

### C4. Google Sheets URL pattern for perks
- Resource is a **Google Sheet** (not a Doc): <https://docs.google.com/spreadsheets/d/1ZSh8kfVxsuSpZyclWWVjJ-m5Jv7JBTo3H7KMVpz9wQM/edit>
- Sheets use anchor format `#gid=<SHEET_ID>&range=<A1>` per tab/cell — heading-slug links don't apply.
- **C4a. Discover the sheet structure** (read-only research, do first):
  - Fetch the sheet (publicly readable) and enumerate tabs (gids) and column layout.
  - Common patterns: one tab per constellation; one master tab with constellation as a column; or one tab with named ranges per perk.
- **C4b. Construct linkage strategy** depending on what C4a finds:
  - **Best case**: per-perk row-anchor links — `#gid=<constellation_gid>&range=A<row>` mapping each `(constellation, jump, name)` triple to its row.
  - **Acceptable v1 fallback**: link perk name to the spreadsheet root (`#gid=<constellation_gid>`) and let the user scroll within the right tab.
  - **Worst case**: just link to the spreadsheet root for every perk (no tab targeting).
- **C4c. Wire into data**:
  - Add `description_url` field to `perk_directory.json`.
  - Builder script constructs the URL deterministically from `(constellation, jump, name)` based on the C4a structure mapping.
- **C4d. Wire into UI**:
  - Tooltip: perk name in `roll-tooltip` becomes `<a target="_blank">` if `description_url` is set.
  - Same for the per-chapter perk list and recent-acquisitions list.

## Curator-rolls revalidation hypothesis (testable after C2)

The `roll_locations_validation.json` `_findings` block documents three discrepancies between curator-logged rolls and simulator predictions, attributed to "curator was bookkeeping-divergent". That finding was made under the **strict-POV rule** — and may be wrong.

**Hypothesis**: under the corrected "Joe on screen" rule, the curator's counts may have been right all along. Specifically:
- The curator was applying the *actual author rule* (Joe on screen counts).
- The simulator was applying a *too-strict* version (Joe POV only) and undercounting CP-earning sections.
- Once C2 reclassifies the non-Joe-POV sections where Joe is physically present, the simulator should fire roughly as many rolls as the curator logged.

**Specific predictions to verify after D1**:

| chapter | v1 finding | predicted v2 outcome under "Joe on screen" rule |
|---|---|---|
| ch 5 | curator extras attributed to bookkeeping | likely a Preamble or section with Joe present that should now count, producing extra simulator rolls |
| ch 58 | "1 roll narrated, curator logged 6" → "buildup compression" theory | Preamble Survey is Joe-on-screen → should now CP-earn → simulator fires ~5–6 rolls, matching curator |
| ch 6.1 / 8.1 / 43.1 / 46.1 / 55.1 / 74.2 (interludes the curator tagged with rolls) | "structural zero — curator divergence" | If Joe is on-screen in any of these (Dragon-converses-with-Joe pattern, debriefs, etc.), they reclassify to MC and the curator's tags become correct |

**Action**: after D1 runs, re-run `validate_roll_locations.py` and compare:
- Total `chapter_coverage_pct` should *increase* (closer to 100%, possibly above v1's 90.9%).
- `chapters_undercollected_list` should *shrink*.
- `_findings` v1 entries should be retracted in the validation JSON (replace with v2 findings backed by post-reclassification prose evidence).

If the hypothesis holds, the v1 narrative ("curator over-counted via bookkeeping ticks") was wrong, and we should update README + the validation `_findings` to credit the curator with applying the rule correctly while the simulator was strict.

## Phase D — Pipeline regeneration (after C2 lands)

| step | command | output | expected impact |
|---|---|---|---|
| D1 | `python scripts/predict_rolls.py` | `data/derived/predicted_rolls.json` | Different CP-earning word totals (~+30k–80k from reclassified Joe-on-screen sections); roll positions shift slightly |
| D2 | `python scripts/find_roll_locations.py` then `find_text_backed_rolls.py` | `data/derived/roll_text_evidence.json` | New windows around new predicted positions |
| D3 | `python scripts/build_chapter_facts.py` | `data/derived/chapter_facts.json` | `untracked_acquisition` count drops as ch 35.1's surplus acquisitions get paired with newly-fired regime-simulator rolls |
| D4 | `python scripts/validate_roll_locations.py` | `data/derived/roll_locations_validation.json` | Chapter coverage % should stay in 90–95% band |

### D5. Cross-validation
- Spot-check ch 35.1: should now have 2 hits (instead of 2 untracked_acquisitions).
- Spot-check ch 58.2 (previously a "structural zero" curator-quirk finding): if it has Joe on screen per user's recollection, should reclassify to MC.
- Compare totals before/after for sanity.
- **Test the curator-rolls revalidation hypothesis** (see callout above Phase D). Specifically:
  - Run `validate_roll_locations.py` and compare `chapter_coverage_pct` and `chapters_undercollected_list` against v1.
  - If hypothesis holds: retract the v1 `_findings` entries; rewrite as "curator was applying the corrected rule; simulator was too strict in v1; both agree under the new rule".
  - If hypothesis partially holds: identify which chapters still diverge and document the residual divergence honestly.
- README update should acknowledge the rule clarification was likely already in the curator's bookkeeping all along.

## Phase E — Final web integration (after Phase D)

### E1. Reload chapter_facts.json
- No code changes needed if schema is stable.

### E2. In-world time track
- New track between chapter ticks and POV sections.
- Hashes at known in-world day boundaries (April 8, 9, 10, ..., 25, 2011).
- Each hash labeled with day-of-month; tooltip shows full date.
- Future: sub-hashes for time-of-day transitions if `chapter_in_world_dates.json` carries that.

### E3. Perk-link tooltips
- If `description_url` is populated, wrap perk name in `roll-tooltip` as `<a target="_blank">`.
- Same for the per-chapter perk list and recent-acquisitions list.

### E4. README update
- Document the new eligibility rule (post-clarification).
- Document the in-world dates derivation.
- Document the v2 scrubber's tracks for future maintainers.

## Open questions

### Resolved
1. ~~**Google Doc URL**~~ — resolved: spreadsheet at <https://docs.google.com/spreadsheets/d/1ZSh8kfVxsuSpZyclWWVjJ-m5Jv7JBTo3H7KMVpz9wQM/edit>. Sheet structure discovery moved into C4a.
2. ~~**Survey-voice subtitle**~~ — resolved: working draft is fine for v1; user will edit later.

### Still open
3. ~~**Constellation palette**~~ — resolved for current UI; future palette refinements belong in `TODO.md`.
4. **Rule-clarification chapter** — rough chapter range to narrow the C1 search? Best guess from "after interludes/preambles/addendums started showing up" is ch ~4 onward, with the actual clarification probably falling in an author note in the early-to-mid story.
5. **C2 LLM pass cost** — ~288 sections × ~2k words × ~$0.003/section ≈ $1. Acceptable, or prefer manual review?

## Suggested resume order if cut off

The plan is structured so each phase is independently executable.

- **Phase A is fully self-contained** — finish A1–A4 first; entire-app polish lift even if nothing else lands.
- **Phase B doesn't require any data changes** — runs against current `chapter_facts.json`. B1–B5 can be done in any order.
- **Phase C is the dependency wall** — C1 must precede C2; C2 must precede D; C3 and C4 are independent.
- **Phase D is mechanical** — once C2 lands, D1–D4 is one pipeline run.
- **Phase E lands incremental wiring** as Phase C completions arrive.

## Affected files at a glance

| change area | files |
|---|---|
| A1, A4, B1–B5, E1–E3 | `web/app.js`, `web/style.css`, `web/index.html` |
| A2, A3 | `web/index.html` |
| C1 | `README.md` (mechanic regimes table) |
| C2 | `data/manual/section_classifications.json` (new fields) |
| C3 | `data/manual/chapter_in_world_dates.json` (new file), `scripts/build_chapter_facts.py` (consumer) |
| C4 | `data/derived/perk_directory.json` (new field), schema, builder script update |
| D1–D4 | regenerates `data/derived/predicted_rolls.json`, `roll_locations_regex.json`, `roll_text_evidence.json`, `chapter_facts.json`, `roll_locations_validation.json` |
| E4 | `README.md` |
