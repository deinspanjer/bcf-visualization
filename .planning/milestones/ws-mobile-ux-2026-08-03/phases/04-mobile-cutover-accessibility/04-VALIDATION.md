---
phase: 4
slug: mobile-cutover-accessibility
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-02
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. **Final phase of the milestone** — anything not verified here ships unverified.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright (Python) via pytest, manual fixtures — same harness as Phases 1–3 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Interpreter** | `/Users/dre/src/bcf-visualization/.venv/bin/python` — the main checkout's venv. **This worktree has no `.venv`**; every command below must use that absolute path. |
| **Quick run command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_mobile_portrait.py -x -q` (or the file relevant to the task) |
| **Full suite command** | `/Users/dre/src/bcf-visualization/.venv/bin/python -m pytest tests/test_desktop_smoke.py tests/test_mobile_plumbing.py tests/test_mobile_portrait.py tests/test_mobile_landscape.py` |
| **Baseline** | 53 passing at Phase 3 close (6 + 10 + 17 + 20) |
| **Estimated runtime** | ~2 minutes, plus the Lighthouse run |

---

## Sampling Rate

- **After every task commit:** the single test file relevant to that task
- **After every plan wave:** the full four-file suite
- **Phase gate:** full suite green **plus** the Lighthouse score check **plus** the whole-milestone freeze diff, before the human device pass
- **Max feedback latency:** 150 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| *(seeded by planner)* | | | MOBX-01 | — | N/A | integration | `pytest tests/test_desktop_smoke.py -x` | ✅ | ⬜ pending |
| *(seeded by planner)* | | | MOBX-01 | — | N/A | freeze-diff | `pytest tests/test_freeze_proof.py -x` (wraps the `git diff 57d2768` check) | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-02 | — | external links `rel=noopener` | integration | `pytest tests/test_landing_page.py -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-03 live region | — | no `innerHTML` from data | integration | `pytest tests/test_mobile_portrait.py -k aria_live -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-03 keyboard | — | N/A | integration | `pytest tests/test_mobile_portrait.py -k keyboard -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-03 44×44 | — | N/A | integration | `pytest tests/test_mobile_landscape.py -k tap_target -x` — **must be an offset-click assertion, NOT `getBoundingClientRect()`** (see note below) | Partial | ⬜ pending |
| *(seeded by planner)* | | | MOBX-03 Lighthouse | — | N/A | integration | `pytest tests/test_lighthouse_accessibility.py -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-04 | — | N/A | integration | `pytest -k reduced_motion -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | MOBX-05 | — | N/A | integration | `pytest -k visibility -x` | ❌ W0 | ⬜ pending |
| *(seeded by planner)* | | | regression | — | N/A | integration | full four-file suite, all 53 prior tests still green | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Two findings that change what "done" means

**1. Lighthouse cannot verify MOBX-03's 44×44 clause.** Research read the bundled `axe-core` 4.12.1 source inside `lighthouse@13.4.1` and confirmed the `target-size` audit defaults to **24×24 CSS px** (WCAG 2.5.8 AA), not 44. MOBX-03's ≥44×44 is a self-imposed bar the score is blind to. **These are two independent checks and both are required** — the Lighthouse ≥ 90 assertion, and a separate `getBoundingClientRect()` assertion for the 44px floor. Passing one must never be reported as satisfying the other.

**2. MOBX-04's "throw decay" clause is vacuous.** Throw-to-scrub inertia was never implemented — it is v2 backlog item 4 in plan §8, and `attachSkyGestures`'s `onSwipeEnd(velocity)` consumer ignores the velocity by design. There is nothing to disable. Flag this at the gate as a requirements-accuracy note rather than inventing the feature to then disable it.

**3. The cinema-scrub FAB's 44×44 cannot be verified the way every other tap target was.** The other controls clear the floor because their *host box* is ≥44px, so `getBoundingClientRect()` proves it directly (`test_mobile_portrait.py:520-534`). The FAB keeps a 40×40 painted box and gains its touch area from a `::before` overlay — a pseudo-element, which `getBoundingClientRect()` on the host cannot see. A rect-based assertion there would **always report 40×40 and always fail**, or worse, be quietly relaxed to 40 and silently drop the requirement for this one control. Verify it by clicking at an offset inside the expanded region but outside the painted box (e.g. 2px in from the overlay's edge) and asserting the FAB's handler fired. Flagged by the UI checker; do not let the planner substitute a rect check.

**Also already satisfied, do not rebuild:** `prefers-reduced-motion: reduce` is already enforced globally by the pre-existing unscoped rule at frozen `web/style.css:62` (`*, *::before, *::after { animation: none !important; transition: none !important; }`), which already silences every `mobile.css` transition. Only the auto-hide 4000 → 8000ms doubling is new work. And the 36×36 `.mobile-icon-btn.compact` controls **already clear 44×44** via Phase 2's `box-sizing: content-box` + padding, proven at `tests/test_mobile_portrait.py:520-534` — only `.mobile-cinema-scrub-fab` (40×40) needs new CSS, and it needs a `::before` overlay rather than padding, which would visibly grow its glow.

---

## Wave 0 Requirements

- [ ] `tests/test_lighthouse_accessibility.py` — new; shells to `npx --yes lighthouse … --only-categories=accessibility`, parses JSON, asserts `>= 0.90`. Must live outside `web/`, which stays dependency-free per CLAUDE.md.
- [ ] `tests/test_landing_page.py` — new; a genuinely new test surface, since every existing Playwright fixture targets `/web/` and none targets the repo-root `index.html`.
- [ ] `tests/test_freeze_proof.py` (or an addition to an existing file) — wraps the whole-milestone `git diff` against **`57d2768`** (pre-Phase-1; NOT Phase 3's `22bdd8c`) so the milestone's closing claim reruns automatically instead of being a one-off shell command.
- [ ] `aria-live`, keyboard, `prefers-reduced-motion` and `visibilitychange` assertions added to `test_mobile_portrait.py` / `test_mobile_landscape.py` — none exist in any current test file.
- [ ] `.mobile-cinema-scrub-fab` 44×44 assertion in `test_mobile_landscape.py`, mirroring the existing pattern.
- [ ] Verify `page.emulate_media(reduced_motion="reduce")` against the installed Playwright version before relying on it.
- [ ] **Do NOT bump `STORAGE_VERSION`** to purge the dead `LS_PORTRAIT_DISMISSED` key — 34 fixture sites across 4 files seed the literal `"3"`, and the orphaned key has zero functional impact once its JS reference is deleted.

---

## Manual-Only Verifications

Scoped per Dre's standing directive: only items producing an objective artifact reach the gate. Subjective "feel" evaluation stays cut.

| # | Behavior | Requirement | Why not automatable | Objective artifact |
|---|----------|-------------|---------------------|--------------------|
| 1 | Safari "Request Desktop Website" behavior | D-49 | Browser-native mode cannot be emulated headlessly | CDP read of `innerWidth` and `layoutMode` with desktop mode on — settles D-49/D-50 with a number rather than the unverified ~980px inference |
| 2 | Banner genuinely gone on device, both orientations | MOBX-01 | The banner was the mobile safety net for three phases; its absence is the milestone's headline claim | Screenshot per orientation + CDP assertion that `.portrait-banner` returns null |
| 3 | VoiceOver actually speaks the live region | MOBX-03 | No headless browser runs a screen reader; `aria-live` presence in the DOM is not proof it is announced | Dre enables VoiceOver, performs one gesture, reports whether the announcement is spoken and whether it stays silent during playback |
| 4 | Landing page `?` on a real phone | MOBX-02 | Static-file dialog behavior on iOS Safari differs from headless | Screenshot of the opened dialog |

Item 3 is the only one requiring Dre to turn anything on. It is included because a live region that is present but not announced would pass every automated check while delivering nothing — and this is the last phase that will look.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 150s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
