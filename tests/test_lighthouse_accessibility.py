"""Committed, re-runnable Lighthouse Accessibility gate — MOBX-03's score
clause, D-40's "not a one-off manual run" requirement.

Browser-free at the pytest level (no Playwright import here): this module
shells out to the pinned Lighthouse CLI via ``npx`` and parses its JSON
report, in the shape of ``tests/test_freeze_proof.py`` (subprocess-driven)
rather than the Playwright suite. Lighthouse itself launches its own
headless Chrome instance.

Version pin — read this before touching ``LIGHTHOUSE_VERSION``:
    Plan 04-05's Task 1 (a blocking human-verify checkpoint) was ruled on
    by Dre on 2026-08-02, ahead of this module's execution: **approve,
    pinned to lighthouse@13.4.1** — the exact version 04-RESEARCH.md
    fetched, ran, and read source from (``target-size.js``, ``axe.js``)
    this cycle. The pin exists so the artifact reviewed at the checkpoint
    and the artifact this gate executes are provably the same one; do not
    change it without a fresh legitimacy ruling for the new version.

Independence note (must not be forgotten by a future editor): this gate
closes ONLY MOBX-03's "Lighthouse Accessibility >= 90" clause. Lighthouse's
own bundled ``target-size`` audit (axe-core, WCAG 2.5.8 AA) defaults to a
24x24 CSS px minimum — a lower, different threshold than MOBX-03's
separate 44x44 tap-target clause, which plan 04-04 closed with direct
``getBoundingClientRect()``/offset-click assertions in
``tests/test_mobile_portrait.py`` and ``tests/test_mobile_landscape.py``.
A passing score here is never evidence for that other clause.

This module intentionally contains no conditional bypass of any kind for a
missing tool or browser: an unavailable ``npx``, ``node``, or Chrome must
surface as a failing assertion with the real subprocess error, never as a
quietly-passing or omitted test. A gate that can go green by doing nothing
reads as a pass while proving nothing.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Iterator

import pytest

from tests.helpers.web_runtime_site import staged_web_runtime_site

REPO_ROOT = Path(__file__).resolve().parents[1]

# The exact artifact Task 1's package-legitimacy checkpoint reviewed and
# Dre approved (2026-08-02) — see the module docstring. Pinning ties the
# executed code to the reviewed code; floating to "latest" would run
# whatever npm most recently published, unreviewed.
LIGHTHOUSE_VERSION = "13.4.1"

# MOBX-03: "Lighthouse Accessibility >= 90" on the mobile preset.
ACCESSIBILITY_SCORE_THRESHOLD = 0.90

# Generous: a cold `npx` fetch of a ~13.4.1-sized package plus a full
# headless Chrome accessibility pass on this app's fixture page.
LIGHTHOUSE_SUBPROCESS_TIMEOUT_SECONDS = 180

FORBIDDEN_WEB_ARTIFACTS = (
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "vite.config.js",
    "webpack.config.js",
    "rollup.config.js",
)


def _run_lighthouse(url: str, output_path: Path) -> subprocess.CompletedProcess:
    """Invoke the pinned Lighthouse CLI against a real http URL.

    No form-factor flag is passed deliberately: Lighthouse's own default
    form factor is mobile, which is what MOBX-03 asks for. Passing a
    desktop preset here would be exactly the prohibited shortcut; the
    absence of any preset flag, combined with Test 2 below reading the
    form factor back out of the report, is what proves the mobile preset
    ran rather than merely assuming it.

    `check=False` and an explicit generous timeout: the return code is
    asserted on directly below with captured stderr in the message, so a
    tool crash or a network failure produces a loud, diagnosable pytest
    failure rather than an uncaught subprocess exception.
    """
    cmd = [
        "npx",
        "--yes",
        f"lighthouse@{LIGHTHOUSE_VERSION}",
        url,
        "--only-categories=accessibility",
        "--output=json",
        f"--output-path={output_path}",
        "--chrome-flags=--headless=new --no-sandbox --disable-gpu",
        "--quiet",
    ]
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=LIGHTHOUSE_SUBPROCESS_TIMEOUT_SECONDS,
    )


@pytest.fixture(scope="module")
def lighthouse_report(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict]:
    """Run the pinned Lighthouse CLI exactly once per module and hand every
    test in this file the same parsed JSON report, so the (slow) real
    subprocess invocation happens a single time rather than once per
    assertion."""
    tmp_path = tmp_path_factory.mktemp("lighthouse-site")
    output_path = tmp_path / "lighthouse-report.json"
    with staged_web_runtime_site(tmp_path) as site:
        url = site.url_for("/web/")
        result = _run_lighthouse(url, output_path)
        assert result.returncode == 0, (
            "The pinned Lighthouse CLI invocation failed (exit code "
            f"{result.returncode}). This gate must fail loudly here, never "
            "silently pass or omit itself, when the tool or a browser is "
            f"unavailable.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert output_path.exists(), (
            f"Lighthouse exited 0 but wrote no report to {output_path} — "
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        report = json.loads(output_path.read_text(encoding="utf-8"))
    yield report


def _accessibility_category(report: dict) -> dict:
    category = report.get("categories", {}).get("accessibility")
    assert category is not None, (
        "Lighthouse report has no 'accessibility' category — the "
        "--only-categories=accessibility invocation should always produce "
        "one. Report keys were: " + ", ".join(report.get("categories", {}))
    )
    return category


def _non_perfect_accessibility_audits(report: dict) -> list[str]:
    """Every audit in the accessibility category whose score is neither
    perfect (1) nor inapplicable (None) — the work list a red run should
    read as, per D-41."""
    category = _accessibility_category(report)
    audits = report.get("audits", {})
    findings: list[str] = []
    for ref in category.get("auditRefs", []):
        audit_id = ref.get("id")
        audit = audits.get(audit_id, {})
        score = audit.get("score")
        if score is None:
            continue  # not applicable to this page, or a manual-only audit
        if score < 1:
            title = audit.get("title", "(no title)")
            findings.append(f"{audit_id}: {title}")
    return findings


def test_accessibility_score_at_or_above_threshold(lighthouse_report: dict) -> None:
    """MOBX-03: the accessibility category score, run at the mobile form
    factor, is 0.90 or greater. On failure, the message IS the work list —
    every non-perfect audit's id and title — so a red run tells a human
    what to fix, not just that the number fell short (D-41)."""
    category = _accessibility_category(lighthouse_report)
    score = category.get("score")
    assert score is not None, "Lighthouse accessibility category has no score."
    findings = _non_perfect_accessibility_audits(lighthouse_report)
    work_list = (
        "\n".join(f"  - {item}" for item in findings) if findings else "  (none found in the report)"
    )
    assert score >= ACCESSIBILITY_SCORE_THRESHOLD, (
        f"Lighthouse Accessibility score {score!r} is below the "
        f"{ACCESSIBILITY_SCORE_THRESHOLD} threshold required by MOBX-03. "
        f"Non-perfect accessibility audits (the work list):\n{work_list}"
    )


def test_report_form_factor_is_mobile(lighthouse_report: dict) -> None:
    """MOBX-03 asks for the mobile preset specifically. The form factor is
    asserted from the report itself, never assumed from the invocation —
    a silent fallback to the desktop preset would score a layout this
    milestone did not build."""
    form_factor = lighthouse_report.get("configSettings", {}).get("formFactor")
    assert form_factor == "mobile", (
        f"Lighthouse report's recorded formFactor is {form_factor!r}, not "
        "'mobile'. MOBX-03 requires the mobile preset; this test proves it "
        "from the report rather than trusting the tool's default."
    )


def test_report_tool_version_matches_pinned_version(lighthouse_report: dict) -> None:
    """The reviewed artifact and the executed artifact must be the same
    one: the report's own recorded tool version must equal the pinned
    constant tied to Task 1's legitimacy ruling."""
    reported_version = lighthouse_report.get("lighthouseVersion")
    assert reported_version == LIGHTHOUSE_VERSION, (
        f"Lighthouse report records tool version {reported_version!r}, but "
        f"this gate is pinned to {LIGHTHOUSE_VERSION!r} — the version "
        "reviewed at Task 1's package-legitimacy checkpoint. An unpinned "
        "or drifted invocation would execute code nobody reviewed."
    )


def test_web_gains_no_dependency_surface(lighthouse_report: dict) -> None:
    """The ephemeral `npx` invocation must leave no footprint: no package
    manifest, lockfile, or bundler config anywhere under web/ or the repo
    root after the run. `lighthouse_report` is requested (and otherwise
    unused) purely to force this check to run after the real invocation
    above, not before it."""
    del lighthouse_report
    web_dir = REPO_ROOT / "web"
    found_in_web = [p for p in web_dir.rglob("*") if p.name in FORBIDDEN_WEB_ARTIFACTS]
    found_at_root = [p for p in REPO_ROOT.iterdir() if p.name in FORBIDDEN_WEB_ARTIFACTS]
    assert not found_in_web and not found_at_root, (
        "A package-manager or bundler artifact appeared after the Lighthouse "
        f"run: web/={found_in_web} repo-root={found_at_root}. web/ must stay "
        "dependency-free and build-step-free per CLAUDE.md; the ephemeral "
        "npx invocation must never leave one behind."
    )


def test_viewport_meta_permits_zoom() -> None:
    """D-03, re-verified here: the app's viewport meta must never disable
    page zoom. Checked directly against the served HTML, independent of
    the Lighthouse report itself — see the paired report-based check
    below for the audit-level confirmation."""
    index_html = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<meta\s+name="viewport"\s+content="([^"]*)"', index_html)
    assert match, 'web/index.html has no <meta name="viewport"> tag to verify.'
    content = match.group(1)
    normalized = content.replace(" ", "")
    assert "user-scalable=no" not in normalized, (
        f"web/index.html's viewport meta disables user scaling ({content!r}). "
        "D-03 requires page zoom to stay enabled for readers with low "
        "vision — MUST NOT trade it away to influence the Lighthouse score."
    )
    assert "maximum-scale=1" not in normalized, (
        f"web/index.html's viewport meta pins maximum-scale=1 ({content!r}), "
        "which also defeats pinch-zoom even without user-scalable=no."
    )


def test_report_meta_viewport_audit_does_not_flag_zoom_disabled(lighthouse_report: dict) -> None:
    """D-03, re-verified against the real audit rather than the static HTML
    alone: Lighthouse's own 'meta-viewport' audit (WCAG 1.4.4, "Zooming and
    scaling should not be disabled") must not report a failure. This is
    the ROADMAP's Phase 4 note closed with a number instead of an
    inference — the Phase 1 interview weighed zoom against the score and
    chose zoom, and this confirms that choice did not cost anything."""
    audits = lighthouse_report.get("audits", {})
    viewport_audit = audits.get("meta-viewport")
    assert viewport_audit is not None, (
        "Lighthouse report has no 'meta-viewport' audit — expected as part "
        "of the default accessibility category; cannot re-verify D-03 "
        "against this real run without it."
    )
    score = viewport_audit.get("score")
    assert score is None or score == 1, (
        f"Lighthouse's meta-viewport audit did not pass (score={score!r}): "
        f"{viewport_audit.get('title')} — {viewport_audit.get('description')}. "
        "D-03 requires zoom to stay enabled; a real finding here must be "
        "recorded as a tension for Dre, never resolved by disabling zoom."
    )
