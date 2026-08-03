# Phase 3: Landscape Layout - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-01
**Phase:** 3-Landscape Layout
**Mode:** default (interactive)
**Areas discussed:** Rotation hand-off, Field log call-or-duplicate, Auto-hide semantics, Landscape shell mechanics

Dre selected all four offered gray areas. Prior decisions honored without re-asking: D-01..D-19, plan §1 locked constants (auto-hide 4000ms landscape-only, swipe right = forward), §7 prohibitions.

---

## Rotation hand-off

| Question | Options | Selected |
|---|---|---|
| What must "no visible remount" mean? | Accept the rebuild / Cross-fade over ROTATION_ANIM 220ms / Re-parent live nodes | **Accept the rebuild** (D-20) |
| Open surface during rotation? | Stays open / Closes on rotate / Help stays, flyouts close | **Stays open** (D-21) |
| Rotation mid-gesture? | Abort drag, keep cinematic / Block rotation mid-gesture / You decide | **Abort drag, keep cinematic** (D-22) |
| How to prove the gate? | Playwright plus device / Device only / Playwright only | **Playwright plus device** (D-23) |

**Notes:** State preservation was never actually at risk — every MOBL-03 field lives on `app.*`. The discussion reframed the requirement around what is visually acceptable rather than what is technically preserved.

## Field log: call or duplicate

| Question | Options | Selected |
|---|---|---|
| Where is the seam? | Share recentRolls only / Call the frozen renderers / Extract a shared partial | **Share recentRolls only** (D-24) |
| What content? | Prototype FieldLog / Mirror desktop content / You decide | **Prototype FieldLog** (D-25) |
| Scroll behavior? | Auto-follows playhead / Scrolls with auto-follow / Scrolls, no follow | **Auto-follows playhead** (D-26) |
| Evidence quote in the rail? | Keep the quote / Drop the quote / Show on tap | **Keep the quote** (D-27) |

**Notes:** The apparent §7-vs-§5 conflict dissolved on re-reading — both documents say share the model and duplicate the view. The useful question turned out to be *where* the seam sits, not *whether* to share.

## Auto-hide semantics

| Question | Options | Selected |
|---|---|---|
| Auto-hide while paused? | Only while playing / Always after idle / You decide | **Only while playing** (D-28) |
| What hides? | Cinema-scrub only / Scrub and top chips / Scrub, chips and rail | **Cinema-scrub only** (D-29) |
| Second tap when tap-to-pause is off? | Reveal works, pause no-ops / Both taps no-op / You decide | **Reveal works, pause no-ops** (D-30) |
| Chrome state on rotating into landscape? | Visible, timer starts / Visible, timer waits / Hidden immediately | **Visible, timer starts** (D-31) |

**Notes:** Every choice matched the prototype's existing behavior, so this area confirmed rather than changed direction. D-30 closes a real trap: with tap-to-pause off and both taps inert, hidden chrome would only be recoverable via the rail.

## Landscape shell mechanics

| Question | Options | Selected |
|---|---|---|
| Portrait-scoped body scroll-lock? | Drop the orientation nesting / Add a landscape twin / Leave portrait-only | **Drop the orientation nesting** (D-32) |
| Where do landscape panels mount? | In the sky, D-19 style / Over the right rail / Anchored to the rail dock | **In the sky, D-19 style** (D-33) |
| How does landscape get gestures? | Generalize to one function / Add a landscape sibling / You decide | **Generalize to one function** (D-34) |
| How is the shared sky handled? | Shared mobile sky helper / Duplicate per layout / You decide | **Shared mobile sky helper** (D-35) |

**Notes:** The scroll-lock question was pre-flagged by the Phase 2 code comment, which literally said the portrait scoping held "until Phase 3 replaces it."

## Follow-up question from Dre (not a gray area)

> *"Is there anything in the decisions and plan that would prohibit or hinder using the gestures in a non-phone but touch-enabled device such as a tablet or chromebook?"*

Investigated against live code rather than answered from memory. Findings recorded as **D-36** plus a deferred idea:

- Nothing prohibits touch anywhere. The mobile gesture module accepts mouse as well as touch (`mobile-gestures.js:45,159` reject only non-primary buttons), and the frozen desktop path is itself pointer-based (`app.js:1186 onPointerDown` plus a native `type="range"` control) — so touch devices routed to desktop stay usable, they just don't get the mobile gesture vocabulary.
- Routing per `MOBILE_LAYOUT_QUERY` (`app.js:73`): iPad-portrait → mobile portrait; iPad-landscape and typical Chromebooks → desktop; a Chromebook window ≤900px → mobile landscape. This is §7's stated intent, not an accident.
- The genuine gap is ergonomic: gesture constants and dock heights are absolute pixels tuned for a phone thumb, so an iPad in portrait gets a functional but untuned experience. Captured as a deferred idea; nothing in Phase 3 forecloses fixing it.

## Claude's Discretion

- Landscape DOM structure and class names (prototype `LandscapeF` as reference)
- CSS expression of the ~75/25 sky-rail split and the rail's 2/3–1/3 division
- Whether the cinema-scrub wraps or directly reuses the portrait scrub helpers
- Auto-hide timer implementation details, provided D-28..D-31 semantics hold
- Playwright structure for rotation and auto-hide tests

## Deferred Ideas

- Large-tablet-portrait ergonomics (scaling gesture constants, or a tablet tier — a §7 deviation)
- Desktop-view escape hatch from mobile → Phase 4
- Persistent idle sky — considered and dropped at the Phase 2 gate after the 88%-populated measurement
- Plan §8 v2 backlog items
