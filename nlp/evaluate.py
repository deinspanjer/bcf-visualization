"""Offline evaluation harness for the span and section models.

Usage:
    uv run python nlp/evaluate.py \\
        --span-checkpoint checkpoints/span/v1/best \\
        --section-checkpoint checkpoints/section/v1/best \\
        --span-eval data/labeled/spans/eval.jsonl \\
        --span-heldout data/labeled/spans/heldout.jsonl \\
        --section-eval data/labeled/sections/eval.jsonl \\
        --report-out checkpoints/eval_v1_report.md

Fails fast with a clear error message if torch/transformers are not installed
(except for --help which always works).
"""

from __future__ import annotations

import argparse
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Offline evaluation harness for the BCF NLP models.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--span-checkpoint", default=None, help="Path to span model best/ dir")
    p.add_argument("--section-checkpoint", default=None, help="Path to section model best/ dir")
    p.add_argument("--span-eval", default=None, help="Span eval JSONL")
    p.add_argument("--span-heldout", default=None, help="Span heldout JSONL (blind eval only)")
    p.add_argument("--section-eval", default=None, help="Section eval JSONL")
    p.add_argument(
        "--report-out",
        default="eval_report.md",
        help="Output markdown report path",
    )
    return p


def _require_gpu_stack() -> None:
    try:
        import numpy  # noqa: F401
        import torch  # noqa: F401
        from transformers import AutoTokenizer  # noqa: F401
    except ImportError as e:
        print(
            f"ERROR: {e}\n"
            "torch and transformers must be installed to run evaluation.\n"
            "On the GPU box: pip install -e '.[gpu]'",
            file=sys.stderr,
        )
        sys.exit(1)


def main(args: argparse.Namespace) -> None:
    import json
    from collections import defaultdict
    from pathlib import Path

    import numpy as np

    try:
        from seqeval.metrics import (
            classification_report as seq_report,
            f1_score as seq_f1,
            precision_score as seq_prec,
            recall_score as seq_rec,
        )
    except ImportError as e:
        print(f"ERROR: seqeval not installed: {e}", file=sys.stderr)
        sys.exit(1)

    from .schema import (
        LAYER_A_BIO,
        LAYER_B_BIO,
        SCHEMA_VERSION,
        SECTION_LABELS,
        ClassifySectionRequest,
        ExtractRequest,
        PassageInput,
        SectionInput,
        SpanRecord,
        SectionRecord,
    )
    from .runners_impl import SpanRunner, SectionRunner

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def load_span_jsonl(path: Path) -> list[SpanRecord]:
        records = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(SpanRecord.model_validate(json.loads(line)))
        return records

    def load_section_jsonl(path: Path) -> list[SectionRecord]:
        records = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(SectionRecord.model_validate(json.loads(line)))
        return records

    # ------------------------------------------------------------------
    # Span eval
    # ------------------------------------------------------------------

    def run_span_eval(runner, records):
        all_preds_a, all_refs_a = [], []
        all_preds_b, all_refs_b = [], []
        detail_rows = []

        for rec in records:
            req = ExtractRequest(
                passages=[PassageInput(passage_id=rec.passage_id, text=rec.text)]
            )
            resp = runner.run(req)
            pred_spans_a = [s for r in resp.results for s in r.spans if s.layer == "A"]
            pred_spans_b = [s for r in resp.results for s in r.spans if s.layer == "B"]
            ref_spans_a = [s for s in rec.spans if s.layer == "A"]
            ref_spans_b = [s for s in rec.spans if s.layer == "B"]

            tok = runner.tokenizer
            encoding = tok(
                rec.text,
                return_offsets_mapping=True,
                truncation=True,
                max_length=4096,
            )
            offsets = encoding["offset_mapping"]
            n = len(offsets)

            def spans_to_bio(spans):
                tags = ["O"] * n
                for i, (ts, te) in enumerate(offsets):
                    if ts == 0 and te == 0:
                        tags[i] = "__SPECIAL__"
                for sp in spans:
                    first = True
                    for i, (ts, te) in enumerate(offsets):
                        if tags[i] == "__SPECIAL__":
                            continue
                        if ts < sp.end and te > sp.start:
                            tags[i] = f"B-{sp.label}" if first else f"I-{sp.label}"
                            first = False
                return [t for t in tags if t != "__SPECIAL__"]

            all_preds_a.append(spans_to_bio(pred_spans_a))
            all_refs_a.append(spans_to_bio(ref_spans_a))
            all_preds_b.append(spans_to_bio(pred_spans_b))
            all_refs_b.append(spans_to_bio(ref_spans_b))

            detail_rows.append({
                "passage_id": rec.passage_id,
                "text": rec.text[:120],
                "ref_a": [f"{s.label}[{s.start}:{s.end}]" for s in ref_spans_a],
                "pred_a": [f"{s.label}[{s.start}:{s.end}]" for s in pred_spans_a],
                "ref_b": [f"{s.label}[{s.start}:{s.end}]" for s in ref_spans_b],
                "pred_b": [f"{s.label}[{s.start}:{s.end}]" for s in pred_spans_b],
            })

        metrics_a = {
            "f1_micro": seq_f1(all_refs_a, all_preds_a, average="micro"),
            "precision_micro": seq_prec(all_refs_a, all_preds_a, average="micro"),
            "recall_micro": seq_rec(all_refs_a, all_preds_a, average="micro"),
            "report": seq_report(all_refs_a, all_preds_a),
        }
        metrics_b = {
            "f1_micro": seq_f1(all_refs_b, all_preds_b, average="micro"),
            "precision_micro": seq_prec(all_refs_b, all_preds_b, average="micro"),
            "recall_micro": seq_rec(all_refs_b, all_preds_b, average="micro"),
            "report": seq_report(all_refs_b, all_preds_b),
        }
        return metrics_a, metrics_b, detail_rows

    # ------------------------------------------------------------------
    # Section eval
    # ------------------------------------------------------------------

    def _sigmoid(x):
        return 1.0 / (1.0 + np.exp(-x))

    def run_section_eval(runner, records):
        try:
            from sklearn.metrics import (
                f1_score as sk_f1,
                precision_score as sk_precision,
                recall_score as sk_recall,
            )
            has_sklearn = True
        except ImportError:
            has_sklearn = False

        preds_mat, refs_mat = [], []
        for rec in records:
            req = ClassifySectionRequest(
                sections=[SectionInput(
                    chapter_num=rec.chapter_num,
                    section_index=rec.section_index,
                    header=rec.header,
                    text=rec.first_chars,
                )]
            )
            resp = runner.run(req)
            result = resp.results[0]
            preds_mat.append([
                int(result.labels[lbl].value) if lbl in result.labels else 0
                for lbl in SECTION_LABELS
            ])
            refs_mat.append([int(rec.labels.get(lbl, False)) for lbl in SECTION_LABELS])

        preds = np.array(preds_mat)
        refs = np.array(refs_mat)
        metrics: dict = {}

        if has_sklearn:
            metrics["f1_macro"] = float(sk_f1(refs, preds, average="macro", zero_division=0))
            metrics["f1_micro"] = float(sk_f1(refs, preds, average="micro", zero_division=0))
            metrics["per_label"] = {
                lbl: {
                    "f1": float(sk_f1(refs[:, i], preds[:, i], zero_division=0)),
                    "precision": float(sk_precision(refs[:, i], preds[:, i], zero_division=0)),
                    "recall": float(sk_recall(refs[:, i], preds[:, i], zero_division=0)),
                }
                for i, lbl in enumerate(SECTION_LABELS)
            }
        else:
            tp = ((preds == 1) & (refs == 1)).sum(axis=0).astype(float)
            fp = ((preds == 1) & (refs == 0)).sum(axis=0).astype(float)
            fn = ((preds == 0) & (refs == 1)).sum(axis=0).astype(float)
            per_f1 = 2 * tp / (2 * tp + fp + fn + 1e-9)
            metrics["f1_macro"] = float(per_f1.mean())
            tp_s, fp_s, fn_s = tp.sum(), fp.sum(), fn.sum()
            metrics["f1_micro"] = float(2 * tp_s / (2 * tp_s + fp_s + fn_s + 1e-9))
            metrics["per_label"] = {
                lbl: {"f1": float(per_f1[i])} for i, lbl in enumerate(SECTION_LABELS)
            }
        return metrics

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _md_table(headers, rows):
        sep = " | ".join("---" for _ in headers)
        lines = [f"| {' | '.join(headers)} |", f"| {sep} |"]
        for row in rows:
            lines.append("| " + " | ".join(str(c) for c in row) + " |")
        return "\n".join(lines)

    def write_report(out_path, span_ma, span_mb, span_detail, sec_m,
                     heldout_a, heldout_b):
        lines = ["# BCF NLP Evaluation Report\n"]

        lines.append("## Span Model — Layer A (Events)\n")
        if span_ma:
            lines.append(
                f"- Micro F1: {span_ma['f1_micro']:.4f}  "
                f"Precision: {span_ma['precision_micro']:.4f}  "
                f"Recall: {span_ma['recall_micro']:.4f}\n"
            )
            lines.append("### Per-label report\n```\n" + span_ma.get("report", "") + "\n```\n")
        else:
            lines.append("_No span checkpoint provided._\n")

        lines.append("## Span Model — Layer B (Entities)\n")
        if span_mb:
            lines.append(
                f"- Micro F1: {span_mb['f1_micro']:.4f}  "
                f"Precision: {span_mb['precision_micro']:.4f}  "
                f"Recall: {span_mb['recall_micro']:.4f}\n"
            )
            lines.append("### Per-label report\n```\n" + span_mb.get("report", "") + "\n```\n")
        else:
            lines.append("_No span checkpoint provided._\n")

        lines.append("## Layer-A Label Confusion Analysis\n")
        if span_detail:
            fp_examples: dict = defaultdict(list)
            fn_examples: dict = defaultdict(list)
            for row in span_detail:
                ref_set = {s.split("[")[0] for s in row["ref_a"]}
                pred_set = {s.split("[")[0] for s in row["pred_a"]}
                for lbl in pred_set - ref_set:
                    fp_examples[lbl].append(row["text"][:80])
                for lbl in ref_set - pred_set:
                    fn_examples[lbl].append(row["text"][:80])
            lines.append("### Top false positives per label (layer A)\n")
            for lbl, exs in sorted(fp_examples.items()):
                lines.append(f"**{lbl}** ({len(exs)} FP):\n")
                for ex in exs[:20]:
                    lines.append(f"- `{ex}`\n")
            lines.append("\n### Top false negatives per label (layer A)\n")
            for lbl, exs in sorted(fn_examples.items()):
                lines.append(f"**{lbl}** ({len(exs)} FN):\n")
                for ex in exs[:20]:
                    lines.append(f"- `{ex}`\n")
        else:
            lines.append("_No span data available._\n")

        lines.append("## Section Classifier\n")
        if sec_m:
            lines.append(
                f"- Macro F1: {sec_m.get('f1_macro', 0.0):.4f}  "
                f"Micro F1: {sec_m.get('f1_micro', 0.0):.4f}\n"
            )
            per = sec_m.get("per_label", {})
            if per:
                rows = [
                    [lbl, f"{v.get('f1', 0):.4f}", f"{v.get('precision', 0):.4f}",
                     f"{v.get('recall', 0):.4f}"]
                    for lbl, v in per.items()
                ]
                lines.append(_md_table(["Label", "F1", "Precision", "Recall"], rows) + "\n")
        else:
            lines.append("_No section checkpoint provided._\n")

        lines.append("## Span Model — Heldout Set\n")
        if heldout_a and heldout_b:
            lines.append(
                f"Layer A micro F1: {heldout_a['f1_micro']:.4f}  "
                f"Layer B micro F1: {heldout_b['f1_micro']:.4f}\n"
            )
        else:
            lines.append("_No heldout data provided._\n")

        lines.append("## End-to-End Pipeline Replay\n")
        lines.append(
            "> **Not yet implemented.** See roadmap.\n\n"
            "end-to-end replay: not yet implemented; see roadmap\n\n"
            # TODO(phase 2): feed every chapter section text through span model,
            # run the deterministic PERK_NAME linker (build_perk_directory + rapidfuzz),
            # compare per-chapter paid-acquisition counts against
            # data/derived/obtained_perks.json for chapters 1-75, surface a
            # per-chapter agreement table.
            "_This section will show per-chapter agreement once phase 2 is implemented._\n"
        )

        lines.append("## Validator Rejection Rate\n")
        lines.append(
            # TODO(phase 2): run validate_roll_locations.py-style rules over predicted
            # spans and report the rejection rate here.
            "_Validator rejection rate: not yet implemented; see roadmap._\n"
        )

        lines.append("## Acceptance Criteria Scoreboard\n")
        span_f1_a = span_ma["f1_micro"] if span_ma else None
        span_f1_b = span_mb["f1_micro"] if span_mb else None
        sec_f1 = sec_m.get("f1_macro") if sec_m else None

        def _status(value, threshold):
            if value is None:
                return "N/A"
            return "PASS" if value >= threshold else "FAIL"

        rows = [
            ["Span micro F1 (L-A) >= 0.85",
             f"{span_f1_a:.4f}" if span_f1_a is not None else "N/A",
             _status(span_f1_a, 0.85)],
            ["Span micro F1 (L-B) >= 0.85",
             f"{span_f1_b:.4f}" if span_f1_b is not None else "N/A",
             _status(span_f1_b, 0.85)],
            ["Section macro F1 >= 0.90",
             f"{sec_f1:.4f}" if sec_f1 is not None else "N/A",
             _status(sec_f1, 0.90)],
            ["E2E replay >= 95%", "not yet measured", "N/A"],
        ]
        lines.append(_md_table(["Criterion", "Value", "Status"], rows) + "\n")

        out_path.write_text("\n".join(lines))
        print(f"Report written to {out_path}")

    # ------------------------------------------------------------------
    # Orchestrate
    # ------------------------------------------------------------------

    span_metrics_a = span_metrics_b = span_detail = None
    span_heldout_a = span_heldout_b = None
    section_metrics = None

    span_runner = None
    if args.span_checkpoint:
        span_runner = SpanRunner(Path(args.span_checkpoint))

    if span_runner and args.span_eval:
        records = load_span_jsonl(Path(args.span_eval))
        print(f"Evaluating span model on {len(records)} records...")
        span_metrics_a, span_metrics_b, span_detail = run_span_eval(span_runner, records)

    if span_runner and args.span_heldout:
        heldout = load_span_jsonl(Path(args.span_heldout))
        print(f"Evaluating span model on {len(heldout)} heldout records...")
        span_heldout_a, span_heldout_b, _ = run_span_eval(span_runner, heldout)

    section_runner = None
    if args.section_checkpoint:
        section_runner = SectionRunner(Path(args.section_checkpoint))

    if section_runner and args.section_eval:
        sec_records = load_section_jsonl(Path(args.section_eval))
        print(f"Evaluating section model on {len(sec_records)} records...")
        section_metrics = run_section_eval(section_runner, sec_records)

    write_report(
        Path(args.report_out),
        span_metrics_a, span_metrics_b, span_detail,
        section_metrics,
        span_heldout_a, span_heldout_b,
    )


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    _require_gpu_stack()
    main(args)
