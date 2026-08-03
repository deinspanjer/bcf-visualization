# Phase 4: Mobile Cutover & Accessibility - Context

**Gathered:** 2026-08-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Mobile becomes the real experience: the "rotate to landscape" banner is deleted, the landing page gains the story-title chip and a `?` help button, and the app meets its accessibility bar — keyboard equivalents, a minimal live region, reduced-motion support, 44×44 tap targets, and Lighthouse Accessibility ≥ 90 on the mobile preset. Covers MOBX-01..MOBX-05, merging `INTEGRATION_PLAN.md` §5 phases D and E. **This is the final phase of the mobile-ux workstream** — anything not landed here becomes v2. Desktop stays frozen per plan §0, with one sanctioned exception (see D-37). Phase ends with the §5 Phase D+E gate review with Dre plus a passing `tests/test_desktop_smoke.py` run and a real-device pass.

</domain>

<decisions>
## Implementation Decisions

Numbering continues from Phases 1–3 (D-01..D-11, D-12..D-19, D-20..D-36 in the prior phase CONTEXT files). **All prior decisions remain binding**, in particular D-03 (page zoom stays enabled — never `user-scalable=no`), D-06 (one breakpoint query, CSS and JS in lockstep), D-07 (per-render attach lifecycle), D-17 (single scrub input path), D-18 (single rAF update tier), and D-19/D-33 (surfaces scoped to `.mobile-sky`).

### Banner deletion and the frozen-CSS exception

- **D-37 Deleting `.portrait-banner` from `web/style.css` is the one sanctioned edit to frozen CSS:** §0.4 otherwise permits only *adding* rules to `style.css`, but MOBX-01 and plan §3.2 explicitly require deleting `.portrait-banner` (`style.css:326`) and its media-query block (`:360`). This is the plan's own instruction, not a freeze violation — but it must be surgical: the deletion may touch only those two blocks, and `tests/test_desktop_smoke.py` must still pass byte-identical desktop rendering at ≥ 1100px afterwards. `renderPortraitBanner()` (`app.js:1228`) and its call site (`:1098`) go with it.
- **D-38 This deletion also resolves the Phase 3 breakpoint divergence:** `style.css:360` still carries the OLD `(max-width: 900px), …` query, deliberately left diverged when Phase 3 moved `MOBILE_LAYOUT_QUERY` and `mobile.css` to the height-based clause (see the comment at `app.js:73`). Deleting the block removes the stale copy entirely rather than leaving two queries in the repo forever. After this phase there must be exactly ONE breakpoint definition pair (`app.js` + `mobile.css`), restoring D-06's single-source intent.

### Tap targets and the Lighthouse gate (MOBX-03)

- **D-39 Expand hit areas to 44×44 without changing visual size:** the 36×36 compact icon buttons (`mobile.css:307`) and the 40×40 cinema-scrub FAB (`:702`) are locked prototype visuals. Use padding or a transparent `::before` overlay to extend the *touchable* region to 44×44 while the painted box stays as designed. This satisfies MOBX-03's floor and the approved design simultaneously — Lighthouse measures the hit target, not the paint. Do NOT enlarge them visually (that thickens chrome Phase 3 deliberately kept slim), and do NOT ship them under-sized.
- **D-40 Lighthouse runs from a committed, repeatable script:** not a one-off manual run. A gate that cannot be re-run silently rots, and this is the last phase that will look at it. The script targets the mobile preset and emits the score. Constraint: `web/` must stay dependency-free and build-step-free per CLAUDE.md — the runner lives outside `web/` (with the other tooling/tests), never as an npm dependency of the app.
- **D-41 A sub-90 score is a work list, not a checkpoint:** treat the report's findings as the tasks, fix them, re-run, iterate until it clears. Lighthouse a11y findings are concrete and mostly mechanical (accessible names, contrast, roles, viewport). Only escalate to Dre if a finding would force a genuine design change — a missing `aria-label` must never become a blocking checkpoint.

### Live region (MOBX-03) — deliberately minimal

- **D-42 The live region fires ONLY on user-caused position changes:** tap, double-tap, swipe-step, rail-scrub release, and keyboard navigation — plus when a roll cinematic fires. It stays **silent during free playback**. At 25000 words/sec a roll lands every few seconds; screen readers speak serially, so announcing every roll produces continuous interruption that a VoiceOver user would simply switch off, leaving them worse served than a well-chosen subset. Do NOT implement a throttle: a throttle silently *drops* announcements, so "Roll 61" followed by "Roll 68" would misrepresent the count in the one channel whose only job is to be truthful.
- **D-43 Announcement phrasing must be outcome-aware:** the plan's locked string (`"Roll {n} of {total}. {perkName}, {cp} CP."`) speaks as "Roll 61 of 670. dash, dash CP." for a miss — and misses are roughly half the rolls in this story, so that is the common case, not an edge case. Research must check what the roll model actually carries for misses and multi-grab rolls and propose phrasing covering every outcome the real data produces.
- **D-44 Rolls only, mobile only:** one visually-hidden `aria-live="polite"` region in the mobile shell. It must NOT mount on the desktop path (frozen). Do not also announce surface open/close (the surfaces already carry `role="dialog"` with focus trapping, which screen readers announce natively — it would double-speak) and do not announce play/pause (the FAB's own `aria-label` already flips between Play and Pause).
- **D-45 Scope rationale, recorded deliberately:** Dre's ruling — a screen reader reciting roll facts does not convey what this app *is* (the spatial density of the rail, the sky, the cinematic), so serialising a visualization into speech is strictly worse than a table the user could navigate at their own pace. The real answer for non-sighted users is the **planned spreadsheet-export workstream**, not this live region. The minimal version is kept because it satisfies MOBX-03 as written at negligible cost and genuinely helps users with residual vision who navigate by gesture and want confirmation of where they landed. It is explicitly NOT a claim that the app is usable unsighted. **Note for a future reader:** MOBX-03's `aria-live` clause is satisfied, not waived — no REQUIREMENTS.md amendment is needed.

### Keyboard equivalents (MOBX-03)

- **D-46 Arrows step ±1 ROLL in the mobile layouts, not ±10000 words:** MOBX-03 asks for keyboard *equivalents*, and on mobile the thing being equivalated is the swipe gesture, which moves one roll. Reuse the existing `rollStepFrom()` that the swipe callback already calls (D-17's single-path discipline) rather than adding a second stepping model. Desktop keeps its word-stepping (10000, or 2000 with shift) unchanged.
- **D-47 Add mobile keys as an early branch in the existing global handler:** `app.js:4564`'s window-level `keydown` listener gains a `layoutMode` check at the top that handles the mobile cases and returns before any desktop code path executes — the same shape D-18 used for `updatePlaybackFrame`'s mobile branch, proven across two phases. Do NOT add a second window-level `keydown` listener: two listeners competing for the same keys is exactly the double-binding class of bug D-07's attach discipline exists to prevent. Desktop behaviour at ≥ 1100px must remain byte-identical (§0.1).
- **D-48 `?` toggles the Help overlay:** pressing it again closes it, matching the toggle behaviour every surface control gained in Phase 2 (`openMobileSurface` closes on re-request). The keyboard matters despite this being a phone-first layout: an iPad with a keyboard lands in the mobile envelope (§7: iPads-in-portrait are mobile), and so does any desktop browser window narrow or short enough to cross the breakpoint.

### Desktop-view escape hatch — deferred to a measurement

- **D-49 Test browser-native desktop mode at the device pass before deciding:** Dre asked whether Safari's built-in "Request Desktop Website" could serve as the escape hatch with no app configuration at all. Analysis says probably not — Safari's desktop mode imposes a ~980px layout viewport, and our portrait clause (`max-width: 1100px`, set so iPad-portrait gets mobile) still matches at 980, so the app would render the *mobile* layout at 980px scaled down to a 440pt screen rather than switching to desktop. **This is unverified** — the 980px figure is from documentation, not measured on the device. The Phase 4 device pass measures `innerWidth` and `layoutMode` with desktop mode on; one extra tap replaces the inference with a number.
- **D-50 If it does not work natively, drop the escape hatch to v2:** per Dre's own conditional framing. Making it work would require either lowering the portrait ceiling below 980 (breaking §7's iPad-portrait-is-mobile rule) or adding a second layout signal such as `navigator.maxTouchPoints` or an `innerWidth`-vs-`screen.width` comparison — both violating D-06's single-source-of-layout-truth discipline that has held for three phases. Do NOT build the in-app toggle without a further ruling from Dre. Record it as a v2 item with this rationale.

### Already satisfied — verify, do not rebuild

- **D-51 MOBX-05 is already implemented:** Phase 1's D-02 wired `document.visibilitychange` → `stopPlayback()` for non-desktop layouts (`web/app.js:4592`). This phase VERIFIES it (a test asserting playback pauses when the page is hidden, and that the desktop path is unaffected) and must not re-implement it. Confirm the landscape layout added in Phase 3 is covered by the same guard, since it keys on `layoutMode !== "desktop"`.

### Claude's Discretion

- Exact landing-page markup for the title chip, author credit and `?` button (the Survey letter text stays verbatim per MOBX-02)
- Whether the landing page's `?` reuses the in-app Help markup or duplicates it — plan §3.4 explicitly permits either for v1; the landing page is a separate static file outside the app shell
- Precisely what `prefers-reduced-motion: reduce` disables beyond MOBX-04's named items (transitions, throw decay, auto-hide → 8000ms); whether the roll cinematic itself should be reduced is a judgment call for research to propose
- Live-region DOM placement and the visually-hidden technique
- Lighthouse runner implementation and where its output is recorded

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Plan & contract
- `design/mobile-ux/INTEGRATION_PLAN.md` — §0 freeze rules (esp. §0.4's "add rules only" and the D-37 exception), §0.5 smoke checklist, §3.2 (delete `.portrait-banner` rules), §3.4 (landing page), §5 phases D and E (this phase merges them), §6 acceptance checklist (Accessibility + Help/credits sections), §7 prohibitions. Its `redesign/mobile-ux/…` prefix is stale — everything lives under `design/mobile-ux/…`.
- `design/mobile-ux/gesture-contract.html` — locked constants; `CHROME_AUTOHIDE` 4000ms doubles to 8000ms under reduced motion (MOBX-04).

### Live code
- `web/app.js:1098` and `:1228` — `renderPortraitBanner()` call site and definition, both deleted (D-37).
- `web/style.css:326` and `:360` — `.portrait-banner` rules and the stale-breakpoint media block, both deleted (D-37, D-38).
- `web/app.js:73` — `MOBILE_LAYOUT_QUERY`, whose comment documents the divergence D-38 resolves.
- `web/app.js:4564` — the global `keydown` handler that gains the D-47 early mobile branch. `rollStepFrom()` is the D-46 stepping function the swipe callback already uses.
- `web/app.js:4592` — the D-02 `visibilitychange` pause that already satisfies MOBX-05 (D-51).
- `web/mobile.css:307` (36×36 compact buttons) and `:702` (40×40 cinema-scrub FAB) — the D-39 hit-area targets.
- `index.html` (repo root) — the Survey landing page; currently contains zero help markup (MOBX-02 is entirely new).
- `web/mobile-gestures.js` — byte-identical since Phase 1, must stay so (D-17).

### Prior phases
- `../03-landscape-layout/03-CONTEXT.md` — D-20..D-36.
- `../03-landscape-layout/03-04-SUMMARY.md` — the Phase C gate record, the two hardware-found defects, and the "hardware finds what green suites miss" pattern now true three phases running.
- `../02-portrait-layout/02-05-SUMMARY.md` — the Phase B gate record and the four device-found defects.
- `../01-mobile-state-gesture-plumbing/01-CONTEXT.md` — D-01..D-11, esp. D-03 (page zoom preserved for a11y) and D-02 (the MOBX-05 implementation).
- `.planning/workstreams/mobile-ux/ROADMAP.md`, `REQUIREMENTS.md` — Phase 4 success criteria and MOBX-01..05 wording.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `openMobileSurface`/`closeMobileSurface` with the Phase 2 toggle + single-sentinel behaviour — `?` (D-48) routes straight through it.
- `rollStepFrom()` — the D-46 stepping function, already the swipe callback's path.
- `updatePlaybackFrame()`'s mobile early-branch — the structural precedent D-47 copies for the keyboard handler.
- The Phase 2/3 Playwright harness (`staged_web_runtime_site`, `_page_with_console_capture`, `PHONE_PORTRAIT`/`PHONE_LANDSCAPE` and the large-phone viewports added in Phase 3).
- `tests/test_desktop_smoke.py` — untouched across all of Phase 3; the D-37 deletion is the first thing in the milestone that could plausibly break it, so it is the primary guard.

### Established Patterns
- Full-teardown `render()` with per-render listener attach; teardown handles on `app`.
- Desktop freeze: §0.2 read-only functions; all new CSS in `web/mobile.css`.
- Device passes find what green suites miss — three phases running, six defects total, two of them structural.

### Integration Points
- `renderAppShell()` loses the banner call (D-37) — the only edit to a §0.2 function this milestone, and it is a deletion the plan mandates.
- Global `keydown` handler gains a mobile branch (D-47).
- New: hidden live region in the mobile shell (D-42..D-44), landing-page chip and `?` (MOBX-02), reduced-motion CSS (MOBX-04), Lighthouse runner (D-40).

</code_context>

<specifics>
## Specific Ideas

- Phase ends with the §5 Phase D+E gate review **with Dre**, a passing `tests/test_desktop_smoke.py`, and a real-device pass. Per D-49 the device pass carries one extra measurement: turn on Safari's "Request Desktop Website" and record `innerWidth` + `layoutMode`.
- Run the device pass on **iOS** specifically. Three phases running, hardware has found defects a green suite missed every time — and Phase 3's two were structural (a breakpoint that excluded the device entirely, and a control inside the home-indicator zone).
- MOBX-01's "desktop UI byte-identical above the breakpoint" is the milestone's closing proof. The freeze has held perfectly through Phase 3; D-37's deletion is the one change that could break it, so verify against the pre-milestone base, not just the working tree.

</specifics>

<deferred>
## Deferred Ideas

- **Spreadsheet export of the curated data** — Dre's own planned separate workstream, and the *right* artifact for non-sighted users who want the curation work (D-45). Not this milestone.
- **In-app desktop-view toggle** — only if D-49's measurement shows browser-native desktop mode does not work AND Dre rules to build it anyway; otherwise v2 (D-50).
- **Large-tablet-portrait ergonomics** — gesture constants are phone-thumb pixel values; an iPad in portrait gets a functional but untuned experience (D-36).
- Plan §8 v2 backlog: pinch zoom, long-press preview, edge swipe-down peel, throw-to-scrub inertia, real constellation outlines, richer cinematic content, Screen Wake Lock.

</deferred>

---

*Phase: 4-Mobile Cutover & Accessibility*
*Context gathered: 2026-08-02*
