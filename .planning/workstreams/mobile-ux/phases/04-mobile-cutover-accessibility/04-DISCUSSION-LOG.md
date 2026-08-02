# Phase 4: Mobile Cutover & Accessibility - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-02
**Phase:** 4-Mobile Cutover & Accessibility (final phase of the workstream)
**Mode:** default (interactive)
**Areas discussed:** Desktop-view escape hatch, Lighthouse ≥ 90 vs 44px targets, aria-live cadence, Keyboard equivalents

Dre selected all four offered gray areas. Two areas were reframed mid-discussion by Dre's own questions — both are recorded below because the reframing changed the outcome.

Pre-empted by the scout, so never offered as gray areas: **MOBX-05 is already implemented** (Phase 1's D-02 `visibilitychange` → `stopPlayback` at `app.js:4592`) and needs verifying, not building; and `aria-live` appears **zero** times in the codebase, so it is entirely new work.

---

## Desktop-view escape hatch

Opened with four questions (location / mechanism / return path / conditional fallback). Dre answered the first with a question of his own:

> *"Can we just drive it purely based on whether the user takes advantage of the browser's built in 'desktop view' mode instead of adding actual configuration to the app?"*

Questions 2 and 3 were explicitly held pending that answer. Question 4 was answered: **Drop it, log to v2** if it compromises the mobile design.

**Investigation.** Safari's "Request Desktop Website" overrides the viewport meta and imposes a ~980px layout viewport, scaling down to the physical screen. Against our query, `(orientation: portrait) and (max-width: 1100px)` still matches at 980 — so desktop mode would render the *mobile* layout at 980px scaled onto a 440pt screen, not the desktop view. Making it work would require lowering the portrait ceiling below 980 (breaking §7's iPad-portrait-is-mobile rule) or adding a second layout signal (`navigator.maxTouchPoints`, or `innerWidth` vs `screen.width`), violating D-06.

**Caveat surfaced rather than buried:** the 980px figure is documentation-derived, not measured. The phone was disconnected at the time, so no empirical check was possible.

| Option | Selected |
|---|---|
| Test at the Phase 4 device pass — measure `innerWidth`/`layoutMode` with desktop mode on | ✓ (D-49) |
| Drop to v2 now on the analysis alone | |
| Build the in-app Settings toggle | |

**Notes:** Dre chose to replace inference with a measurement. One extra tap during a device pass that is happening anyway. D-50 records the fallback: if it does not work natively, drop to v2 rather than building the toggle without a further ruling.

## Lighthouse ≥ 90 vs 44px targets

| Question | Options | Selected |
|---|---|---|
| Sub-44px locked controls (36×36 compact, 40×40 cinema-scrub FAB) | Expand hit area keep visuals / Enlarge to 44 / Keep as-is and accept risk | **Expand hit area, keep visuals** (D-39) |
| How Lighthouse is run and evidenced | Scripted committed repeatable / One-off manual / You decide | **Scripted, committed, repeatable** (D-40) |
| If the score lands under 90 | Fix what it flags then re-run / Escalate / Accept and document | **Fix what it flags, then re-run** (D-41) |

**Notes:** The hit-area technique resolves what looked like a direct conflict between MOBX-03's own 44px floor and the locked prototype visuals — Lighthouse measures the touch target, not the painted box. D-40's constraint is that the runner must live outside `web/`, which CLAUDE.md keeps dependency-free.

## aria-live cadence

**Offered twice, dismissed twice.** Dre's first dismissal came with a question:

> *"What is 'aria-live'? Is that text to speech? Or like toast notifications?"*

Explained: a W3C ARIA attribute marking a DOM element as a live region; assistive technology watches it and speaks content changes without the user navigating there. Not TTS, not toasts — closer to a pub/sub topic the screen reader subscribes to. The element is visually hidden; users without a screen reader are unaffected entirely. Relevant here because the visualization is *purely visual* — a roll firing produces nothing perceivable otherwise.

The re-offered question was dismissed again, this time with an architectural objection:

> *"There is a big difference between maybe providing some form of assistive hints when the user might be partially sighted and able to see the visualization but maybe not the fine text, but for a user who was not able to see the app at all, there is almost no value in this app at all because it is a *visualization*. For those users … the better output would actually be … export of the data into a spreadsheet."*

**Assessment.** Substantially correct, and it reframed the area. Three things were added before ruling: (1) dropping `aria-live` would NOT endanger the Lighthouse gate — its audits cover accessible names, contrast, valid ARIA, `lang`, viewport and tap targets, none of which require a live region, so the two halves of MOBX-03 are independent; (2) the partially-sighted case Dre describes is *already* served by D-03, which deliberately preserved page zoom by rejecting `user-scalable=no`, plus contrast, hit areas and reduced-motion; (3) dropping it entirely would be a REQUIREMENTS.md amendment, not a silent omission, since MOBX-03 names `aria-live="polite"` explicitly.

Counter-position offered rather than simply agreeing: users with residual vision who also run VoiceOver are a real population, and an announcement on *deliberate navigation only* helps them at ~15 lines and zero playback cost.

| Option | Selected |
|---|---|
| Drop entirely, amend MOBX-03, cross-reference the spreadsheet workstream | |
| **Minimal — discrete navigation only** | ✓ (D-42, D-44, D-45) |
| Keep full scope as originally specified | |

**Notes:** The chosen middle path satisfies MOBX-03 as written (no amendment needed) while avoiding the flooding behaviour. Explicitly recorded in D-45 that this is *not* a claim the app is usable unsighted, and that the spreadsheet export is the real answer for that audience. A throttle was rejected on its merits: it silently drops announcements, misrepresenting the count in the one channel whose job is to be truthful. D-43 (outcome-aware phrasing) was raised by Claude rather than asked — roughly half the rolls are misses, which under the locked string would speak as "Roll 61 of 670. dash, dash CP."

## Keyboard equivalents

| Question | Options | Selected |
|---|---|---|
| Arrow semantics on mobile | ±1 roll matching the gesture / Inherit word-stepping / You decide | **±1 roll** (D-46) |
| How to add without breaking the frozen desktop path | Early mobile branch in the existing handler / Separate mobile listener / You decide | **Early mobile branch** (D-47) |
| What `?` does, and whether keyboard matters on a phone | Toggle Help, yes it matters / Open only / Skip `?` | **Toggle Help** (D-48) |

**Notes:** The mobile layout is not phones-only — an iPad with a keyboard lands in it (§7), as does any sufficiently narrow or short desktop window, so keyboard support is not theoretical. The separate-listener option was rejected as the double-binding class of bug D-07's attach discipline exists to prevent.

## Claude's Discretion

- Landing-page markup for the title chip, credit and `?` (Survey letter text stays verbatim)
- Whether the landing page reuses or duplicates the Help markup (plan §3.4 permits either)
- What `prefers-reduced-motion` disables beyond MOBX-04's named items — notably whether the roll cinematic itself should be reduced
- Live-region DOM placement and visually-hidden technique
- Lighthouse runner implementation and output location

## Deferred Ideas

- Spreadsheet export of curated data — Dre's own separate planned workstream, and the right artifact for non-sighted users
- In-app desktop-view toggle — only if D-49's measurement fails AND Dre rules to build it anyway
- Large-tablet-portrait ergonomics (D-36)
- Plan §8 v2 backlog
