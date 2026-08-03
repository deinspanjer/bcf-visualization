"""Run Stage 2 inference over one or more chapters and report what it found.

One warm MCP server serves the whole run, so the prose loader, directory
match index, obtained-perks index and exemplar index are built **once**
rather than once per chapter. The server is shut down in a ``finally`` on
every exit path.

There is no dollar cap here and no cost estimator, because inference rides
an existing subscription and has no per-token price to cap. Run size is
bounded by chapter count and by concurrency instead, and the harness's own
``usage`` envelope is logged so run size is measured rather than guessed.

**This script has no corpus write path.** Everything it produces goes to
the proposals sidecar.

Usage::

    PYTHONPATH=scripts .venv/bin/python scripts/run_stage2_chapter.py 92 104 \\
        --model opus --concurrency 2
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

try:  # bare import when scripts/ is on sys.path, package-qualified otherwise
    from cp_word_index import EPUB
    from data_paths import DERIVED, MANUAL
    from mechanical_verifier import _build_prose_loader, build_obtained_perks_index
    from perk_name_resolver import build_directory_match_index, load_perk_aliases
    from stage2_mcp_server import build_stage2_server, serve_stage2_http
    from stage2_prompt import (
        STAGE2_RETRIEVAL_THRESHOLD,
        build_candidate_snippets,
        build_system_prefix,
        build_user_message,
    )
    from stage2_proposals_io import DEFAULT_PROPOSALS_PATH
    from stage2_response import Stage2RunContext
    from stage2_transport import DEFAULT_MODEL, ClaudeCliTransport
except ImportError:  # pragma: no cover - import-path shim
    from scripts.cp_word_index import EPUB  # type: ignore[no-redef]
    from scripts.data_paths import DERIVED, MANUAL  # type: ignore[no-redef]
    from scripts.mechanical_verifier import (  # type: ignore[no-redef]
        _build_prose_loader,
        build_obtained_perks_index,
    )
    from scripts.perk_name_resolver import (  # type: ignore[no-redef]
        build_directory_match_index,
        load_perk_aliases,
    )
    from scripts.stage2_mcp_server import (  # type: ignore[no-redef]
        build_stage2_server,
        serve_stage2_http,
    )
    from scripts.stage2_prompt import (  # type: ignore[no-redef]
        STAGE2_RETRIEVAL_THRESHOLD,
        build_candidate_snippets,
        build_system_prefix,
        build_user_message,
    )
    from scripts.stage2_proposals_io import (  # type: ignore[no-redef]
        DEFAULT_PROPOSALS_PATH,
    )
    from scripts.stage2_response import Stage2RunContext  # type: ignore[no-redef]
    from scripts.stage2_transport import (  # type: ignore[no-redef]
        DEFAULT_MODEL,
        ClaudeCliTransport,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "chapters",
        nargs="+",
        help="One or more chapter numbers, e.g. 92 104 121.1",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "Harness model flag. Calibrate on 'opus'; step down to 'sonnet' "
            "only once evidence shows it clears the same bar. Never haiku -- "
            "exact-quote fidelity matters more than latency here. "
            "(default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=2,
        help=(
            "Concurrent harness invocations against the one warm server. "
            "Start at 2 and raise only on evidence; the binding constraint "
            "is the subscription usage window. (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=STAGE2_RETRIEVAL_THRESHOLD,
        help="Retrieval threshold parameter (default: %(default)s)",
    )
    parser.add_argument(
        "--proposals",
        type=Path,
        default=DEFAULT_PROPOSALS_PATH,
        help="Proposals sidecar path (default: %(default)s)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional path to write the run report as JSON",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Per-chapter wall-clock budget in seconds (default: %(default)s)",
    )
    return parser.parse_args(argv)


def _load_inputs() -> dict:
    chapters_doc = json.loads((DERIVED / "chapters.json").read_text())
    classifications_doc = json.loads(
        (MANUAL / "section_classifications.json").read_text()
    )
    perk_directory = json.loads((DERIVED / "perk_directory.json").read_text())
    obtained = json.loads((DERIVED / "obtained_perks.json").read_text())
    candidate_doc = json.loads((DERIVED / "candidate_rolls.json").read_text())
    evidence_doc = json.loads((DERIVED / "roll_text_evidence.json").read_text())

    exemplar_path = DERIVED / "exemplar_index.json"
    exemplar_index = (
        json.loads(exemplar_path.read_text()) if exemplar_path.exists() else None
    )
    chapter_facts_path = DERIVED / "chapter_facts.json"
    chapter_facts = (
        json.loads(chapter_facts_path.read_text())
        if chapter_facts_path.exists()
        else None
    )

    return {
        "chapters_doc": chapters_doc,
        "classifications_doc": classifications_doc,
        "perk_directory": perk_directory,
        "obtained": obtained,
        "candidate_doc": candidate_doc,
        "evidence_doc": evidence_doc,
        "exemplar_index": exemplar_index,
        "chapter_facts": chapter_facts,
    }


def _regime_for_chapter(chapter_facts: dict | None, chapter_num: str) -> int | None:
    if not chapter_facts:
        return None
    for row in chapter_facts.get("chapters") or []:
        if str(row.get("chapter_num")) == str(chapter_num):
            return row.get("point_calculation_regime")
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = _load_inputs()

    classifications = inputs["classifications_doc"]["classifications"]
    prose_loader = _build_prose_loader(
        EPUB, inputs["chapters_doc"], inputs["classifications_doc"]
    )

    candidates_by_chapter: dict[str, dict[int, dict]] = {}
    for cand in inputs["candidate_doc"]["candidates"]:
        chapter = str(cand["chapter_num"])
        candidates_by_chapter.setdefault(chapter, {})[int(cand["slot_index"])] = cand

    evidence_by_chapter: dict[str, list[dict]] = {}
    for row in inputs["evidence_doc"]["rolls"]:
        evidence_by_chapter.setdefault(str(row["chapter_num"]), []).append(row)

    perks_by_chapter: dict[str, list[dict]] = {}
    for row in inputs["obtained"]["perks"]:
        perks_by_chapter.setdefault(str(row["chapter_num"]), []).append(row)

    run_id = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}-{uuid.uuid4().hex[:8]}"

    ctx = Stage2RunContext(
        prose_loader=prose_loader,
        directory_index=build_directory_match_index(
            inputs["perk_directory"]["perks"],
            load_perk_aliases(MANUAL / "perk_aliases.json"),
        ),
        obtained_perks_index=build_obtained_perks_index(inputs["obtained"]),
        candidates_by_chapter=candidates_by_chapter,
        run_id=run_id,
        model=args.model,
        proposals_path=args.proposals,
    )

    server = build_stage2_server(ctx)
    results: dict[str, dict] = {}

    with serve_stage2_http(server) as running:
        print(f"warm MCP server on {running.url}", flush=True)
        transport = ClaudeCliTransport(
            running=running,
            take_submission=ctx.take_submission,
            timeout=args.timeout,
        )

        def run_one(chapter_num: str) -> tuple[str, dict]:
            chapter_num = str(chapter_num)
            chapter_html, word_starts = prose_loader(chapter_num)
            candidates = sorted(
                candidates_by_chapter.get(chapter_num, {}).values(),
                key=lambda c: int(c["slot_index"]),
            )
            perk_rows = perks_by_chapter.get(chapter_num, [])
            snippets = build_candidate_snippets(
                chapter_num,
                chapter_html=chapter_html,
                word_starts=word_starts,
                section_classifications=classifications,
                candidates=candidates,
                perk_names=[r["perk_name"] for r in perk_rows],
                evidence_rows=evidence_by_chapter.get(chapter_num, []),
                threshold=args.threshold,
            )
            system_prompt = build_system_prefix(
                exemplar_index=inputs["exemplar_index"],
                target_regime=_regime_for_chapter(
                    inputs["chapter_facts"], chapter_num
                ),
                target_chapter=chapter_num,
            )
            user_message = build_user_message(
                chapter_num,
                candidates=candidates,
                snippets=snippets,
                perk_rows=perk_rows,
            )
            print(
                f"[{chapter_num}] {len(candidates)} slot(s), "
                f"{len(snippets)} retrieved passage(s), "
                f"{len(user_message)} prompt chars",
                flush=True,
            )
            harness = transport.run_chapter(
                chapter_num, system_prompt, user_message, model=args.model
            )
            outcome = ctx.outcomes.get(chapter_num)
            return chapter_num, {
                "submitted": harness.submitted,
                "state": harness.state,
                "turns": harness.turns,
                "duration_ms": harness.duration_ms,
                "usage": harness.usage,
                "total_cost_usd": harness.total_cost_usd,
                "permission_denials": harness.permission_denials,
                "error_detail": harness.error_detail,
                "retrieved_passages": len(snippets),
                "prompt_chars": len(user_message),
                "stats": outcome.stats if outcome else None,
            }

        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            for chapter_num, payload in pool.map(run_one, args.chapters):
                results[chapter_num] = payload

    report = _build_report(run_id, args, results, ctx)
    _print_report(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"\nwrote report to {args.report}")
    print(f"proposals: {args.proposals}")

    return 0 if all(r["submitted"] for r in results.values()) else 1


def _build_report(run_id, args, results: dict, ctx: Stage2RunContext) -> dict:
    usage_total: dict[str, int] = {}
    for payload in results.values():
        for key, value in (payload.get("usage") or {}).items():
            if isinstance(value, int):
                usage_total[key] = usage_total.get(key, 0) + value
    return {
        "run_id": run_id,
        "model": args.model,
        "concurrency": args.concurrency,
        "retrieval_threshold": args.threshold,
        "chapters": results,
        "usage_total": usage_total,
        "read_tool_instrumentation": dict(ctx.instrumentation),
        "read_set_size": len(ctx.read_set),
    }


def _print_report(report: dict) -> None:
    print("\n" + "=" * 74)
    print(f"STAGE 2 RUN REPORT  run_id={report['run_id']}  model={report['model']}")
    print("=" * 74)
    header = (
        f"{'ch':>7} {'sub':>4} {'rolls':>5} {'ans':>4} {'T1':>3} {'T2':>3} "
        f"{'lost':>4} {'noev':>4} {'fill':>5} {'turns':>5} {'sec':>6}"
    )
    print(header)
    print("-" * len(header))
    for chapter_num, payload in sorted(report["chapters"].items()):
        stats = payload.get("stats") or {}
        print(
            f"{chapter_num:>7} "
            f"{('yes' if payload['submitted'] else 'NO'):>4} "
            f"{stats.get('rolls', 0):5} "
            f"{stats.get('answered_by_model', 0):4} "
            f"{stats.get('tier1', 0):3} "
            f"{stats.get('tier2', 0):3} "
            f"{stats.get('quotes_unlocated', 0):4} "
            f"{stats.get('rolls_evidence_not_found', 0):4} "
            f"{stats.get('fields_prefilled', 0):5} "
            f"{payload.get('turns', 0):5} "
            f"{payload.get('duration_ms', 0) / 1000:6.1f}"
        )
    print("-" * len(header))
    print(
        "  T1/T2 = quotes located at verifier tier 1 / tier 2; "
        "lost = proposed quotes not found in prose"
    )
    print(
        "  noev = rolls left with no evidence; fill = fields pre-filled "
        "(perks/outcome/constellation/quotes)"
    )

    inst = report["read_tool_instrumentation"]
    print("\nREAD-TOOL INSTRUMENTATION (drives the keep-or-drop decision):")
    print(
        f"  get_prose_span: {inst['prose_span_calls']} call(s), "
        f"{inst['prose_span_quotes_verified']} produced a quote that verified"
    )
    print(
        f"  check_quote:    {inst['check_quote_calls']} call(s), "
        f"{inst['check_quote_quotes_verified']} produced a quote that verified"
    )

    print("\nHARNESS USAGE TOTALS (run size, measured not guessed):")
    for key, value in sorted(report["usage_total"].items()):
        print(f"  {key}: {value:,}")


if __name__ == "__main__":
    sys.exit(main())
