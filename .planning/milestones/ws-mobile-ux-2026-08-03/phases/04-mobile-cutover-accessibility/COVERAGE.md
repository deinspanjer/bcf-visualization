# Phase 4 — API Coverage Declaration

**Phase:** 04-mobile-cutover-accessibility
**Declared:** 2026-08-02 (planning); re-asserted at the Phase D+E gate by plan 04-05.

No external API integration: cutover and accessibility work touches only local DOM, localStorage, static outbound links, and a local Lighthouse CLI invocation.

## Rationale

This phase deletes a render function and a CSS block, adds a visually-hidden ARIA live region, a keyboard
branch inside the app's one existing global `keydown` listener, a CSS hit-area overlay, a reduced-motion
timer branch, and static markup on the repo-root landing page. It introduces no SDK, no HTTP client, no
authentication, and no network call of any kind — `web/` still has no `package.json`, no lockfile and no
bundler, and the only data the phase reads is the already-loaded in-memory `app.data` bundle
(`visualization_facts.json`), fetched once by pre-existing Phase-1 code this phase does not modify.

The one external tool this phase invokes is the `lighthouse` npm CLI, run ephemerally via `npx` from a
committed pytest module against a locally served copy of the app. It is test tooling, never a runtime
dependency of the shipped site, and it is never added to any `package.json` in this repo. It is therefore
not an external API integration; it is a local audit binary. Its supply-chain exposure is modelled
explicitly as `T-04-SC` in plan 04-05's `<threat_model>` and gated by a blocking human legitimacy
checkpoint before its first invocation.

No capability matrix is provided because there is no external capability surface to enumerate. Plan 04-05's
dependency scan is the standing proof that this remains true at phase close.
