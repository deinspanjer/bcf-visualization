"""CLI driver for the BCF annotation bootstrap lane.

Generates span proposals from llama.cpp for candidate passages and writes
them as JSONL.  Designed to run on Windows (or the iMac) without the TUI.

Usage::

    python3 scripts/bootstrap_proposals.py \\
        --strategy event_focused \\
        --limit 5 \\
        --epub data/raw/bcf.epub \\
        --out data/labeled/spans/_proposals_dryrun.jsonl \\
        [--llama-url http://192.168.x.x:11434] \\
        [--model unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF]

On HTTP error from llama.cpp this script exits with code 1 and prints
a clear message including which URL was tried.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure the repo root is on sys.path so `nlp` is importable regardless
# of the working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import httpx  # noqa: E402  (after sys.path setup)

from nlp.bootstrap import propose  # noqa: E402
from nlp.candidates import iter_candidates  # noqa: E402
from nlp.schema import SCHEMA_VERSION  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOURCE_UNREVIEWED = "llm_proposal_unreviewed"
_ANNOTATOR_PLACEHOLDER = "bootstrap_dryrun"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_span_record(candidate, proposal) -> dict:
    """Assemble a SpanRecord-shaped dict from a Candidate + Proposal."""
    spans_out = []
    for sp in proposal.spans:
        entry: dict = {
            "layer": sp.layer,
            "start": sp.start,
            "end": sp.end,
            "label": sp.label,
        }
        spans_out.append(entry)

    return {
        "passage_id": candidate.passage_id,
        "chapter_num": candidate.chapter_num,
        "section_index": candidate.section_index,
        "epub_char_start": candidate.epub_char_start,
        "epub_char_end": candidate.epub_char_end,
        "text": candidate.text,
        "spans": spans_out,
        "source": _SOURCE_UNREVIEWED,
        "model_proposal_score": proposal.mean_confidence,
        "annotator": _ANNOTATOR_PLACEHOLDER,
        "annotated_at": _now_iso(),
        "schema_version": SCHEMA_VERSION,
    }


def _print_passage_summary(candidate, proposal) -> None:
    n_spans = len(proposal.spans)
    model_tag = proposal.model_name or "(router)"
    conf_tag = (
        f"{proposal.mean_confidence:.2f}" if proposal.mean_confidence is not None else "n/a"
    )
    span_labels = ", ".join(f"{s.label}[{s.layer}]" for s in proposal.spans[:6])
    if len(proposal.spans) > 6:
        span_labels += f" … (+{len(proposal.spans)-6} more)"
    print(
        f"  {candidate.passage_id:<20} src={candidate.source:<22} "
        f"spans={n_spans:>2}  conf={conf_tag}  model={model_tag}"
    )
    if span_labels:
        print(f"    labels: {span_labels}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Bootstrap LLM span proposals for BCF annotation passages.\n"
            "Writes one JSONL line per passage to --out."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/bootstrap_proposals.py \\
      --strategy event_focused --limit 5 \\
      --epub data/raw/bcf.epub \\
      --out data/labeled/spans/_proposals_dryrun.jsonl

  # With explicit llama.cpp endpoint:
  python3 scripts/bootstrap_proposals.py \\
      --strategy event_focused --limit 10 \\
      --llama-url http://192.168.1.100:11434 \\
      --model unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF \\
      --out data/labeled/spans/batch1.jsonl
""",
    )
    p.add_argument(
        "--strategy",
        default="event_focused",
        choices=["event_focused", "balanced", "low_confidence", "coverage_gap"],
        help="Candidate selection strategy (default: event_focused).",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N passages (default: all).",
    )
    p.add_argument(
        "--epub",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the EPUB file for full-prose passage extraction. "
            "If omitted, falls back to section first_chars."
        ),
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="PATH",
        help="Output JSONL file path.",
    )
    p.add_argument(
        "--llama-url",
        default=None,
        metavar="URL",
        help=(
            "Base URL of the llama.cpp server "
            "(default: BCF_LLAMACPP_URL env or http://localhost:11434)."
        ),
    )
    p.add_argument(
        "--model",
        default=None,
        metavar="MODEL",
        help=(
            "Model name to request from llama.cpp "
            "(default: let the router decide)."
        ),
    )
    p.add_argument(
        "--derived-dir",
        type=Path,
        default=Path("data/derived"),
        metavar="DIR",
        help="Directory containing chapter_sections.json etc. (default: data/derived).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=1337,
        help="RNG seed for candidate ordering (default: 1337).",
    )
    p.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/labeled/.proposals_raw"),
        metavar="DIR",
        help="Directory for raw LLM output persistence.",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # Resolve derived_dir relative to repo root if it's a relative path
    derived_dir = args.derived_dir
    if not derived_dir.is_absolute():
        derived_dir = _REPO_ROOT / derived_dir
    if not derived_dir.exists():
        print(
            f"ERROR: derived data directory not found: {derived_dir}\n"
            "       Make sure you are running from the repo root or use --derived-dir.",
            file=sys.stderr,
        )
        return 1

    # Resolve epub path
    epub_path: Path | None = args.epub
    if epub_path is not None and not epub_path.is_absolute():
        epub_path = _REPO_ROOT / epub_path

    # Prepare output directory
    out_path: Path = args.out
    if not out_path.is_absolute():
        out_path = _REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve raw dir
    raw_dir: Path = args.raw_dir
    if not raw_dir.is_absolute():
        raw_dir = _REPO_ROOT / raw_dir

    # Determine effective llama URL for error messages
    import os
    llama_url: str = args.llama_url or os.environ.get(
        "BCF_LLAMACPP_URL", "http://localhost:11434"
    )

    print(f"BCF Bootstrap Proposals")
    print(f"  strategy   : {args.strategy}")
    print(f"  limit      : {args.limit or 'unlimited'}")
    print(f"  epub       : {epub_path or '(not provided — using first_chars fallback)'}")
    print(f"  llama URL  : {llama_url}")
    print(f"  model      : {args.model or '(router decides)'}")
    print(f"  output     : {out_path}")
    print()

    # Build candidates
    try:
        candidates = list(
            iter_candidates(
                strategy=args.strategy,
                epub_path=epub_path,
                derived_dir=derived_dir,
                seed=args.seed,
                limit=args.limit,
            )
        )
    except NotImplementedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR building candidates: {exc}", file=sys.stderr)
        return 1

    if not candidates:
        print("No candidates found. Check derived data files and strategy.")
        return 1

    print(f"Proposing spans for {len(candidates)} candidate(s)...")
    print()

    n_ok = 0
    n_err = 0
    n_spans_total = 0

    with open(out_path, "w", encoding="utf-8") as out_fh:
        for candidate in candidates:
            try:
                proposal = propose(
                    candidate.text,
                    passage_id=candidate.passage_id,
                    llama_url=args.llama_url,
                    model=args.model,
                    persist_raw_dir=raw_dir,
                )
            except httpx.ConnectError as exc:
                print(
                    f"\nERROR: Could not connect to llama.cpp at {llama_url}\n"
                    f"  Detail: {exc}\n"
                    f"\n  Troubleshooting:\n"
                    f"    - Check that llama.cpp is running: curl {llama_url}/health\n"
                    f"    - Use --llama-url to specify a different endpoint\n"
                    f"    - On Windows: verify Windows Firewall allows port 11434\n",
                    file=sys.stderr,
                )
                return 1
            except httpx.HTTPStatusError as exc:
                print(
                    f"\nERROR: llama.cpp returned HTTP {exc.response.status_code}\n"
                    f"  URL  : {llama_url}\n"
                    f"  Model: {args.model or '(router decides)'}\n"
                    f"  Body : {exc.response.text[:300]}\n"
                    f"\n  Troubleshooting:\n"
                    f"    - Verify the model is loaded: check llama.cpp logs\n"
                    f"    - Use --model to specify a model name explicitly\n"
                    f"    - Use --llama-url to point at the correct endpoint\n",
                    file=sys.stderr,
                )
                return 1
            except httpx.TimeoutException as exc:
                print(
                    f"\nERROR: Request to llama.cpp timed out.\n"
                    f"  URL: {llama_url}\n"
                    f"  Detail: {exc}\n"
                    f"\n  The model may be loading or the passage may be too long.\n"
                    f"  Try again in a moment, or use a smaller --limit.\n",
                    file=sys.stderr,
                )
                return 1
            except httpx.HTTPError as exc:
                print(
                    f"\nERROR: HTTP error from llama.cpp at {llama_url}: {exc}\n"
                    f"  Use --llama-url to specify a different endpoint.\n",
                    file=sys.stderr,
                )
                return 1
            except Exception as exc:
                print(f"  WARN: unexpected error for {candidate.passage_id}: {exc}")
                n_err += 1
                continue

            record = _build_span_record(candidate, proposal)
            out_fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_fh.flush()

            _print_passage_summary(candidate, proposal)
            n_ok += 1
            n_spans_total += len(proposal.spans)

    print()
    print("── Summary ──────────────────────────────────────")
    print(f"  Passages processed : {n_ok + n_err}")
    print(f"  Successful         : {n_ok}")
    print(f"  Errors             : {n_err}")
    print(f"  Total spans emitted: {n_spans_total}")
    print(f"  Output file        : {out_path}")
    if n_ok > 0:
        print(f"  Avg spans/passage  : {n_spans_total/n_ok:.1f}")
    print()
    print("Next step: open the TUI to review proposals:")
    print("  uv run python -m nlp.tui.app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
