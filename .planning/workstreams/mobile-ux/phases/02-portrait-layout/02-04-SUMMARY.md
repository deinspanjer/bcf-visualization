---
phase: 02-portrait-layout
plan: 04
subsystem: ui
tags: [vanilla-js, css-flexbox, playwright, focus-trap, history-api]

requires:
  - phase: 02-portrait-layout
    plan: 03
    provides: "Portrait gesture callbacks, cluster-binned mini-rail, app.mobileSurface guard wired defensively (falsy until this plan sets it for real)"
provides:
  - "One exclusive surface stack (openMobileSurface/closeMobileSurface): Settings, About and Help open and close, mutually exclusive, with a history sentinel consumed exactly once per close route (backdrop tap, close button, or the phone's own back gesture)"
  - "trapMobileSurfaceFocus(): Tab/Shift+Tab wrapped inside the open surface; focus restored to the button that opened it on close, re-resolved by its data-action selector post-render (a raw node reference would already be detached — render() rebuilds the whole portrait DOM tree every time)"
  - "renderMobileSettingsFlyout(): View mode / On roll / Speed / Timeline zoom / Comfort groups in locked order, every control routed through an existing shared setter or the set-on-roll-behavior delegation; setMode gets a write-side allow-list guard (T-02-12)"
  - "renderMobileInfoFlyout()/renderMobileHelpOverlay(): live STORY_LINKS source links, live dataset counts, seven locked gesture rows; Help overlay scoped to .mobile-sky only (D-19) so the dock stays operable while it's open"
  - "maybeAutoOpenHelp(): first-run welcome opens once per session with zero extra structural renders"
  - "Dock gear/info buttons and the top-cluster help button, all riding the existing data-action click delegation"
affects: [02-portrait-layout-phase-B-gate]

tech-stack:
  added: []
  patterns:
    - "Surface-stack identity survives a full DOM rebuild by storing the opener's data-action STRING (not a node reference) and re-querying a live element by that selector after render() — matches this app's no-diffing, full-rebuild render model"
    - "A surface's own backdrop (position:absolute inset:0 inside .mobile-app, explicit z-index) naturally covers the ENTIRE app including the dock — any interactive element that must stay reachable while a surface is open (the dock-transport row, for switching between Settings/About directly) needs its own higher z-index, not an assumption that DOM order alone keeps it on top"

key-files:
  created: []
  modified:
    - web/app.js
    - web/mobile.css
    - tests/test_mobile_portrait.py

key-decisions:
  - "D-19 (Help overlay scoping, carried from the plan's flagged assumption F-07): the Help overlay mounts inside .mobile-sky with position:absolute; inset:0, never as a full-portrait overlay. The prototype's own .help-overlay is full-bleed (inset:0 on the whole app), but tests/test_mobile_plumbing.py::test_visibilitychange_pauses_playback_on_mobile_only loads portrait with EMPTY storage — exactly the first-run condition that auto-opens Help — then clicks the dock's Play button, and that file must stay green UNMODIFIED. Scoping Help to the sky region keeps the dock (including Play) reachable throughout. Trade-off: Help scrolls internally on short viewports rather than being a true full-screen takeover. STILL ON THE PHASE B GATE AGENDA per the plan's flagged_assumptions — Dre confirms or redirects the scoping choice at that review."
  - "Rule 1 fix: .mobile-dock switched from top-aligned block children to a bottom-aligned flex column (display:flex; flex-direction:column; justify-content:flex-end). Plan 02-01 gave the dock flex:1 0 auto so it absorbs whatever's left after the sky's locked 60% basis — at a real 390x844 viewport the dock's grown height (~338px) is nearly double its content's natural height (~178px transport+rail+hint), and with top-aligned block children that leftover ~160px collected BELOW the transport row. The Settings/About flyout's UI-SPEC-locked anchor (bottom:152px) sits inside that same 338px-tall dock box (152 < 338), so its own rendered height reached down far enough to overlap the dock-transport row (measured directly: flyout box y:430-692 vs transport box y:521-575 before the fix) — silently making the gear/info buttons unclickable behind the flyout whenever it was open. Bottom-aligning the dock's content collapses the leftover space above the transport row instead of below it, which mostly (but not entirely, at every possible content length) clears the collision. THIS TENSION — the UI-SPEC's locked flyout bottom:152px anchor vs. the dock's real (content-driven, taller-than-assumed) height — belongs on the Phase B gate agenda alongside D-19; the two fixes in this plan (bottom-aligned dock content, and the z-index fix below) are a pragmatic resolution, not a re-litigation of either locked value."
  - "Companion fix to the above: .mobile-dock-transport gets position:relative and a z-index (10) higher than the flyout (9) and its backdrop (8). This is deliberate, not just defensive — it is what lets a reader tap directly from About to Settings (or vice versa) via the dock's own icon buttons without dismissing the open surface first, which the plan's acceptance criteria require ('opening Settings while About is open leaves exactly one surface mounted'). A residual few pixels of geometric overlap between the flyout and the transport row can still exist depending on content height; the z-index guarantees the transport row's own buttons stay tappable regardless."
  - "openMobileSurface stores the opener as its data-action STRING, not the DOM node passed in. render() unconditionally clears and rebuilds the entire portrait DOM tree (no per-node diffing anywhere in this app) — a raw node reference captured at open time is already detached by the time a later closeMobileSurface() would try to focus it. closeMobileSurface() re-resolves a live element by that selector after its own render() call instead."
  - "window.__bcfMobile gets a new setMode export (alongside the existing pure-function/setter exposures) purely for test assertions of the write-side allow-list guard — the guard itself is otherwise only reachable through the Settings UI's own already-allow-listed buttons."

requirements-completed: [MOBP-05]

coverage:
  - id: D1
    description: "Settings, About and Help all open and close in portrait; opening one closes any other; a backdrop tap and the phone's back gesture both close the open surface and leave the current history entry back where it was before opening"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_surface_stack_focus_trap_and_back_gesture"
        status: pass
    human_judgment: false
  - id: D2
    description: "Focus is trapped inside the open surface (Tab/Shift+Tab wraps at the first/last focusable control) and returns to the button that opened it on close; sky gestures are inert while a surface is open"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_surface_stack_focus_trap_and_back_gesture"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every Settings control (view mode, on-roll behavior, speed, timeline zoom, tap-to-pause, haptics) writes through an existing shared setter/delegated action and survives a real page reload with an allow-listed value; setMode rejects an out-of-allow-list value; Settings groups render in the locked order"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_settings_about_help_persist_across_reload"
        status: pass
    human_judgment: false
  - id: D4
    description: "The About flyout shows the story title/credit, three live STORY_LINKS anchors (target=_blank, rel=noopener noreferrer), live dataset counts, and its Gestures & help button opens the Help overlay; opening Settings while About is open leaves exactly one surface mounted"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_settings_about_help_persist_across_reload"
        status: pass
    human_judgment: false
  - id: D5
    description: "The Help overlay contains exactly seven verbatim gesture rows and the 'Got it — read on' CTA"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_settings_about_help_persist_across_reload"
        status: pass
    human_judgment: false
  - id: D6
    description: "On a first visit with empty storage every preference reads its default and the Help overlay opens by itself with zero extra structural renders; dismissing it records help-seen so a reload doesn't reopen it; a dismiss action with nothing open is a harmless no-op; the dock (including Play) stays fully operable while the auto-opened overlay is present"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_first_run_help_auto_opens_once"
        status: pass
    human_judgment: false
  - id: D7
    description: "At a 320x568 viewport every Settings control stays reachable — the flyout scrolls internally rather than clipping content off-screen"
    requirement: "MOBP-05"
    verification:
      - kind: e2e
        ref: "tests/test_mobile_portrait.py#test_settings_about_help_persist_across_reload"
        status: pass
    human_judgment: false
  - id: D8
    description: "The first-run Help auto-open reads as a welcome rather than an obstacle on a real device: appears once, dismissible with one thumb, never blocks the dock transport"
    verification: []
    human_judgment: true
    rationale: "Backstop truth in the plan's must_haves explicitly requires real-device confirmation — emulation proves the mechanics (auto-open-once, dock stays clickable) but not the felt experience of the overlay on an actual phone. Carried to the Phase B gate alongside D-19 and the flyout/dock overlap tension."

duration: ~66min (includes a 1Password SSH-signing agent stall between staging and landing the implementation commit — see Issues Encountered)
completed: 2026-07-26
status: complete
---

# Phase 2 Plan 4: Settings/About/Help Surface Stack Summary

**One exclusive Settings/About/Help surface stack with a focus trap, back-gesture dismissal, and a first-run auto-opening Help overlay — every preference round-trips through an existing shared setter and survives a real reload.**

## Performance

- **Duration:** ~66 min (implementation + verification), spanning a mid-session pause for a wedged 1Password SSH-signing agent between staging the implementation and landing it as `e3d2015`
- **Started:** 2026-07-26T20:22:00-04:00 (following 02-03's completion)
- **Completed:** 2026-07-26T21:28:15-04:00
- **Tasks:** 2 (implemented and verified together — see Deviations)
- **Files modified:** 3

## Accomplishments

- `openMobileSurface`/`closeMobileSurface` implement the one exclusive surface stack: opening Settings, About or Help closes whatever else is open, pushes exactly one `history.pushState` sentinel, and every close route (backdrop tap, close button, phone back gesture) consumes it exactly once.
- `trapMobileSurfaceFocus()` wraps Tab/Shift+Tab inside the open surface and restores focus to the button that opened it on close — re-resolved by a stable `data-action` selector after `render()`'s full DOM rebuild, since a raw node reference would already be detached.
- `renderMobileSettingsFlyout()`: View mode / On roll / Speed / Timeline zoom / Comfort groups in the UI-SPEC's locked order; every control commits through `setMode`/`set-on-roll-behavior`/`setMobileSpeedMultiplier`/`setMobileTimelineZoom`/`setTapToPause`/`setHaptics` — never a second persistence path. `setMode` gained a write-side allow-list guard (T-02-12) mirroring `setRollLocation`'s, closing the "details" vs "detail" pitfall RESEARCH.md flagged.
- `renderMobileInfoFlyout()`/`renderMobileHelpOverlay()`: live `STORY_LINKS` source anchors (`target=_blank rel="noopener noreferrer"`), live `app.data.story` dataset counts, and the seven locked "How to play" gesture rows — Help scoped to `.mobile-sky` only (D-19) so the dock stays operable while it's open.
- `maybeAutoOpenHelp()` opens the Help overlay once per session on a first visit with empty storage, mutating state synchronously inside the current render pass so it costs zero extra structural renders and never blocks the dock's Play button.
- Dock gear/info buttons (`mobileGearIcon`/`mobileInfoIcon`, ported verbatim from the prototype) and the top-cluster help button (`mobileHelpIcon`, filling Plan 02-01's reserved 44x44 slot) all ride the existing `data-action` click delegation.
- Fixed a real geometric collision the flyout's locked position exposed: `.mobile-dock` now bottom-aligns its content and `.mobile-dock-transport` sits above the flyout/backdrop stack in z-index, so the gear/info buttons stay reachable and switchable even when a surface is open.

## Task Commits

1. **Tasks 1+2 combined: surface stack, focus trap, back gesture, Settings flyout, About flyout, Help overlay, first-run auto-open** - `e3d2015` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified

- `web/app.js` - `MODE_CHOICES`/`DEFAULT_MODE`/`MOBILE_SURFACES` constants; `app.mobileSurface`/`mobileSurfaceOpener`/`mobileSurfaceFocusTrapTeardown`/`mobileHelpAutoOpened` state fields; `setMode`'s allow-list guard; `openMobileSurface`/`closeMobileSurface`/`trapMobileSurfaceFocus`/`teardownMobileSurfaceFocusTrap`, the module-level `popstate` listener; `mobileGearIcon`/`mobileInfoIcon`/`mobileHelpIcon`; `mobileSeg`/`mobileSettingsGroup`/`mobileComfortRow`; `renderMobileSurface`/`renderMobileSettingsFlyout`/`renderMobileInfoFlyout`/`renderMobileHelpOverlay`/`maybeAutoOpenHelp`; the `mobile-open-settings`/`mobile-open-info`/`mobile-open-help`/`mobile-close-surface` click-delegation branches; `renderMobilePortrait()`'s gear/info buttons and Help-overlay mount; `renderMobileTopCluster()`'s help button (replacing the Plan 02-01 spacer); `render()`'s focus-trap wiring; `window.__bcfMobile.setMode` test exposure.
- `web/mobile.css` - `.mobile-flyout-backdrop`/`.mobile-flyout`/`.mobile-flyout-divider`/`.mobile-group`/`.mobile-group-label`/`.mobile-seg`/`.mobile-row`/`.mobile-row-val`/`.mobile-source-row`/`.mobile-flyout-dataset`/`.mobile-full-btn`; `.mobile-help-overlay` and its header/credit-block/gestures/got-it children; `.mobile-icon-btn.is-active`; the `:focus-visible` ring for trapped-surface controls; `.mobile-dock`'s bottom-aligned flex-column layout and `.mobile-dock-transport`'s z-index fix; removed the now-dead `.mobile-help-spacer` rule.
- `tests/test_mobile_portrait.py` - `test_surface_stack_focus_trap_and_back_gesture`, `test_settings_about_help_persist_across_reload`, `test_first_run_help_auto_opens_once`, `_total_rolls`/`_format_words` helpers; added `bcf:help-seen: "true"` to `DEFAULT_STORAGE` and every ad-hoc storage dict in the file that didn't already carry it, so the new first-run auto-open doesn't silently disable sky/rail gesture attachment (`attachMobilePortraitGestures` guards on `app.mobileSurface`) in tests written before this surface existed.

## Decisions Made

See `key-decisions` in frontmatter for full detail. Short form:
- D-19: Help overlay scoped to `.mobile-sky`, not full-portrait (protects `test_visibilitychange_pauses_playback_on_mobile_only`'s empty-storage + Play-click path). **Phase B gate agenda item.**
- `.mobile-dock` bottom-aligned flex column + `.mobile-dock-transport` z-index fix: a Rule 1 correctness fix forced by the Settings/About flyout's UI-SPEC-locked `bottom: 152px` anchor overlapping the dock's real (taller-than-content) rendered height. **Phase B gate agenda item** — the underlying tension between the locked flyout position and the dock's flex-grown height should be reviewed with Dre rather than silently patched over again if a future plan hits the same class of overlap.
- `openMobileSurface`/`closeMobileSurface` track the opener by its `data-action` string, not a DOM node — required by this app's full-DOM-rebuild render model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `.mobile-dock`'s top-aligned content let the Settings/About flyout's locked position overlap the dock-transport row, hiding the gear/info buttons behind it**
- **Found during:** writing `test_settings_about_help_persist_across_reload`'s "opening Settings while About is open" assertion — the gear button click timed out with Playwright reporting `.mobile-source-row` (inside the About flyout) intercepting the click.
- **Issue:** Plan 02-01 gave `.mobile-dock` `flex: 1 0 auto` so it absorbs the sky's leftover ~40% of the viewport; at 390x844 that grows the dock to ~338px while its actual content (transport+rail+hint) is only ~178px tall. With top-aligned block children, the ~160px of leftover space collected BELOW the transport row — leaving the transport row near the dock's TOP edge, right where the flyout's locked `bottom:152px` anchor (which sits inside that same 338px-tall dock region) geometrically reached.
- **Fix:** `.mobile-dock` switched to `display:flex; flex-direction:column; justify-content:flex-end` (bottom-aligns its children without changing the outer 60/40 sky/dock split), plus `.mobile-dock-transport` got `position:relative; z-index:10` so it stays clickable above the flyout/backdrop stack regardless of any residual overlap.
- **Files modified:** `web/mobile.css`
- **Verification:** `test_settings_about_help_persist_across_reload`'s surface-switch assertion passes; `test_portrait_layout_proportions_and_chip_overlap` (Plan 02-01's sky/dock ratio test) still passes at both 390x844 and 320x568.
- **Committed in:** `e3d2015`

**2. [Rule 1 - Bug] `openMobileSurface` storing a raw DOM node as the "opener" would silently break focus restoration**
- **Found during:** implementing `closeMobileSurface`'s focus-restore step, before any test ran — recognized that `render()` unconditionally clears and rebuilds the entire portrait DOM tree (no per-node diffing anywhere in this app), so a node captured at open time is already detached by the time a later close tries to `.focus()` it.
- **Issue:** The plan's action text describes storing "the element" as the opener; taken literally, `document.contains(opener)` would always be `false` after the structural render `closeMobileSurface` itself triggers, silently no-oping the focus restore and failing the acceptance bar ("after closing, `document.activeElement` is the gear button").
- **Fix:** Store the opener's `data-action` attribute value (a stable identifier) instead of the node; `closeMobileSurface` re-resolves a live element by that selector after its own `render()` call.
- **Files modified:** `web/app.js`
- **Verification:** `test_surface_stack_focus_trap_and_back_gesture`'s focus-trap assertion passes (`document.activeElement` is the gear button after backdrop-close).
- **Committed in:** `e3d2015`

**3. [Rule 1 - Bug/Test] `.mobile-group-label` and `.mobile-got-it`'s CSS `text-transform: uppercase` made `inner_text()` assertions fail**
- **Found during:** writing the Settings group-order and Help CTA assertions.
- **Issue:** Playwright's `inner_text()` reflects CSS text-transform (same pitfall already documented in 02-02-SUMMARY for `.mobile-hint-row`); asserting literal-case copy against it fails even though the DOM text content is correct.
- **Fix:** Used `all_text_contents()`/`text_content()` (untransformed DOM text) instead of `inner_text()`/`all_inner_texts()` for those two assertions.
- **Files modified:** `tests/test_mobile_portrait.py`
- **Verification:** Both assertions pass.
- **Committed in:** `e3d2015`

**4. [Rule 1 - Test] Every pre-existing test in `tests/test_mobile_portrait.py` needed `bcf:help-seen: "true"` seeded**
- **Found during:** first full run of the new surface-stack tests — several pre-existing Plan 02-01/02/03 tests (rail scrub, cluster binning, sky gestures) started failing because the new first-run Help auto-open (which fires whenever `bcf:help-seen` is unset) also disables sky/rail gesture attachment (`attachMobilePortraitGestures` returns early while `app.mobileSurface` is truthy).
- **Issue:** This plan's own acceptance bar requires `tests/test_mobile_plumbing.py`/`tests/test_desktop_smoke.py` to stay green (verified — they do, since the Play button and structural-render-count assertions there are unaffected by D-19's sky-scoped overlay), but the sibling suite `tests/test_mobile_portrait.py` (which this plan is explicitly allowed to modify) needed updating so its own prior tests kept exercising gesture behavior rather than the new auto-open.
- **Fix:** Added `"bcf:help-seen": "true"` to `DEFAULT_STORAGE` and to every other ad-hoc storage dict in the file that omitted it.
- **Files modified:** `tests/test_mobile_portrait.py`
- **Verification:** All 17 tests in the file pass; `tests/test_mobile_plumbing.py`/`tests/test_desktop_smoke.py` pass unmodified.
- **Committed in:** `e3d2015`

---

**Total deviations:** 4 auto-fixed (3 Rule 1 bugs, 1 Rule 1 test-infrastructure fix)
**Impact on plan:** All four were necessary for correctness or for the plan's own verification bar to hold; no scope creep beyond the plan's stated files (`web/app.js`, `web/mobile.css`, `tests/test_mobile_portrait.py`).

**Note on task granularity:** Task 1 (surface stack + Settings) and Task 2 (About/Help/auto-open) were implemented and verified together in a single commit (`e3d2015`) rather than as two separate atomic commits. The two tasks are tightly coupled — Task 2 extends the exact same functions (`renderMobilePortrait`, `renderMobileSurface`, the click delegation, `render()`'s focus-trap wiring) Task 1 introduces — and splitting the diff after the fact would have required risky manual hunk surgery with no functional benefit. Both tasks' full acceptance criteria are verified by the tests in this single commit.

## Known Stubs

None — every acceptance criterion in both tasks is wired and tested; no placeholder data paths remain in the surface stack.

## Threat Flags

None — this plan's own `<threat_model>` register (T-02-11..T-02-15, T-02-SC) already covers every new surface this plan introduces (outbound story links, `setMode`'s write path, the surface renderers' markup construction, the history-sentinel lifecycle, and the focus-trap listener lifecycle). No additional surface was found during implementation.

## Issues Encountered

**The local 1Password SSH-signing agent wedged again between staging the implementation and committing it** (same class of issue 02-03-SUMMARY.md documented — confirmed unresponsive via a 10s-timeout `op whoami` before pausing to report it as a checkpoint rather than bypassing signing). The coordinator confirmed the agent recovered independently and the staged commit landed as `e3d2015` with the exact message supplied; this session verified `git log`/`git status`/`git diff --exit-code` afterward before proceeding to plan-closure steps. No signing bypass occurred at any point.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MOBP-05 is now the last functional gap the phase's `<success_criteria>` named — Phase 2 (Portrait Layout) is functionally complete pending the Phase B gate review with Dre.
- **Phase B gate agenda additions from this plan:** (1) D-19's Help-overlay-scoped-to-sky decision (trade-off: internal scroll on short viewports vs. a true full-screen takeover); (2) the tension between the UI-SPEC's locked flyout `bottom:152px` anchor and the dock's real flex-grown height, resolved here with a bottom-aligned dock + z-index fix rather than revisiting either locked value — worth Dre's eyes if a later plan hits the same overlap class again; (3) D8's real-device confirmation that the auto-opening Help overlay reads as a welcome, not an obstacle.
- Every artifact this phase's `<output>` inventory promised (`MOBILE_SURFACES`, `openMobileSurface`, `closeMobileSurface`, `renderMobileSurface`, `renderMobileSettingsFlyout`, `renderMobileInfoFlyout`, `renderMobileHelpOverlay`, `trapMobileSurfaceFocus`, `maybeAutoOpenHelp`, `mobileSeg`, `mobileInfoIcon`, `mobileHelpIcon`, `mobileGearIcon`, the `setMode` allow-list guard, and the `.mobile-flyout`/`.mobile-flyout-backdrop`/`.mobile-seg`/`.mobile-help-overlay`/`.mobile-got-it`/`.mobile-source-row` CSS) is present and tested.

---
*Phase: 02-portrait-layout*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created/modified files verified present on disk; commit `e3d2015` verified present in `git log --oneline --all` (confirmed independently by the coordinator and re-checked in this session before writing this summary).
