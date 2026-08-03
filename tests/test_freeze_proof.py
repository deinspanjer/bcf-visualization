"""Whole-milestone freeze proof (MOBX-01, D-37/D-38, T-04-01, T-04-02,
T-04-04) — turns Phase 3's one-off shell commands into a repeatable,
non-skippable pytest gate that reruns automatically at every future phase
gate instead of rotting the moment Phase 4 closes.

Two base commits are used deliberately — this is NOT a single-constant
freeze proof, and that is intentional:

- ``WHOLE_MILESTONE_BASE`` (``57d2768``, "docs(01): create phase plan") is
  the commit immediately BEFORE any mobile-ux code landed. It is the
  correct diff target for ``web/style.css``, which existed as the frozen
  desktop stylesheet before this milestone started. MOBX-01's claim is
  that desktop is byte-identical to that pre-milestone state — a
  phase-local base from any later phase would silently certify only that
  phase's slice of the freeze, not the whole-milestone claim MOBX-01
  actually makes.

- ``PHASE_1_ESTABLISHED_BASE`` (``1351450``, "docs(02): create phase
  plan" — the commit immediately after Phase 1 closed) is the correct
  diff target for ``web/mobile-gestures.js`` and the mobile
  ``<script>``/``<link>`` tags Phase 1 added to ``web/index.html``.
  These artifacts did not exist at ``WHOLE_MILESTONE_BASE`` — creating
  them WAS Phase 1's job — so diffing them against the pre-Phase-1
  commit would report the entire file as newly added rather than testing
  what D-17 actually claims: byte-identical from the moment Phase 1
  created them onward. Every prior phase's own freeze-proof record
  (``02-05-SUMMARY.md``, ``03-04-SUMMARY.md``) diffed this same file
  against the phase-appropriate base for this exact reason before this
  module formalised the practice as a standing gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Pre-Phase-1 commit ("docs(01): create phase plan") — the whole-milestone
# diff target for artifacts that predate this milestone (web/style.css).
WHOLE_MILESTONE_BASE = "57d2768"

# Commit immediately after Phase 1 closed ("docs(02): create phase plan")
# — the diff target for artifacts Phase 1 itself created and which must
# have stayed byte-identical ever since (D-17).
PHASE_1_ESTABLISHED_BASE = "1351450"

# Kept in exactly one place so the two call sites below cannot drift.
DELETED_BANNER_SELECTOR = "portrait-banner"

FORBIDDEN_WEB_ARTIFACTS = (
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "vite.config.js",
    "webpack.config.js",
    "rollup.config.js",
)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_commit_resolves(sha: str) -> None:
    result = _git("rev-parse", "--verify", sha)
    assert result.returncode == 0, (
        f"Base commit {sha!r} does not resolve in this repository — the "
        f"freeze proof cannot run without it. git stderr: {result.stderr}"
    )


def test_mobile_gestures_byte_identical_since_phase_1():
    """D-17 / T-04-02: web/mobile-gestures.js must never change once Phase
    1 creates it. Diffed against the commit immediately after Phase 1
    closed, not the pre-milestone base — the file did not exist before
    then, so that diff would report it as newly added, not modified."""
    _assert_commit_resolves(PHASE_1_ESTABLISHED_BASE)
    result = _git(
        "diff", "--exit-code", PHASE_1_ESTABLISHED_BASE, "HEAD",
        "--", "web/mobile-gestures.js",
    )
    assert result.returncode == 0, (
        "web/mobile-gestures.js has changed since Phase 1 closed — this is "
        f"a D-17 violation. git diff output:\n{result.stdout}\n{result.stderr}"
    )


def test_style_css_diff_against_whole_milestone_base_is_deletion_only():
    """MOBX-01 / T-04-01: the ONLY sanctioned edit to frozen web/style.css
    this milestone is the Phase 4 banner deletion (D-37). The added-lines
    column must be exactly 0; the deleted-lines column must be > 0 so an
    unmodified file cannot masquerade as a passing deletion-only diff."""
    _assert_commit_resolves(WHOLE_MILESTONE_BASE)
    result = _git(
        "diff", "--numstat", WHOLE_MILESTONE_BASE, "HEAD", "--", "web/style.css",
    )
    assert result.returncode == 0, f"git diff --numstat failed: {result.stderr}"
    line = result.stdout.strip()
    assert line, (
        "web/style.css shows NO diff at all against the whole-milestone base "
        f"{WHOLE_MILESTONE_BASE!r} — MOBX-01 requires the D-37 banner "
        "deletion to have happened, so 'no diff' is a FAILURE here, not a pass."
    )
    added, deleted, _path = line.split("\t", 2)
    assert int(added) == 0, (
        f"web/style.css has {added} added line(s) against "
        f"{WHOLE_MILESTONE_BASE!r} — the frozen-CSS gate is deletion-only; "
        "any added line, including a comment, fails it."
    )
    assert int(deleted) > 0, (
        f"web/style.css shows 0 deleted lines against {WHOLE_MILESTONE_BASE!r} "
        "— the sanctioned D-37 deletion has not actually happened."
    )


def test_deleted_banner_selector_absent_from_served_stylesheets():
    """T-04-01: the deleted .portrait-banner selector must not reappear in
    either served stylesheet — catches a re-add in web/style.css OR a
    reintroduction via web/mobile.css."""
    for relative_path in ("web/style.css", "web/mobile.css"):
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert DELETED_BANNER_SELECTOR not in text, (
            f"{relative_path} still contains {DELETED_BANNER_SELECTOR!r} — "
            "the Phase 4 banner deletion (D-37) has regressed."
        )


def test_web_stays_dependency_free_and_build_step_free():
    """T-04-SC: web/ carries no package-manager or bundler artifacts, and
    the mobile <script>/<link> tags Phase 1 added to web/index.html
    (mobile.css, mobile-gestures.js) have not drifted since Phase 1 closed."""
    web_dir = REPO_ROOT / "web"
    found = [p for p in web_dir.rglob("*") if p.name in FORBIDDEN_WEB_ARTIFACTS]
    assert not found, (
        f"web/ has grown a package-manager/bundler artifact: {found} — "
        "CLAUDE.md's 'no framework, no build step' rule for web/ has regressed."
    )

    _assert_commit_resolves(PHASE_1_ESTABLISHED_BASE)
    result = _git(
        "diff", "--exit-code", PHASE_1_ESTABLISHED_BASE, "HEAD",
        "--", "web/index.html",
    )
    assert result.returncode == 0, (
        "web/index.html has changed since Phase 1 closed — its mobile "
        "<script>/<link> tag set (mobile.css, mobile-gestures.js) must stay "
        f"byte-identical from that point forward. git diff:\n{result.stdout}"
    )
