"""Multi-label section classifier training entry point.

Usage:
    uv run python nlp/train_section.py \\
        --train data/labeled/sections/train.jsonl \\
        --eval  data/labeled/sections/eval.jsonl \\
        --version v1 \\
        [--backbone answerdotai/ModernBERT-base] \\
        [--epochs 4] [--lr 2e-5] [--batch-size 8] \\
        [--seed 1337] [--bf16/--no-bf16]

Fails fast with a clear error message if torch/transformers are not installed
(except for --help which always works).
"""

from __future__ import annotations

import argparse
import os
import sys


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Train the multi-label section classifier.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--train", required=True, help="Path to train.jsonl")
    p.add_argument("--eval", required=True, help="Path to eval.jsonl")
    p.add_argument("--version", required=True, help="Run version tag, e.g. v1")
    p.add_argument(
        "--backbone",
        default=os.environ.get("BCF_BACKBONE", "answerdotai/ModernBERT-base"),
        help="HuggingFace model id for the backbone encoder",
    )
    p.add_argument("--epochs", type=int, default=4)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--batch-size", type=int, default=8, dest="batch_size")
    p.add_argument("--seed", type=int, default=1337)
    p.add_argument("--bf16", action=argparse.BooleanOptionalAction, default=True)
    return p


def _require_gpu_stack() -> None:
    try:
        import numpy  # noqa: F401
        import torch  # noqa: F401
        from transformers import AutoModelForSequenceClassification  # noqa: F401
    except ImportError as e:
        print(
            f"ERROR: {e}\n"
            "torch and transformers must be installed to run training.\n"
            "On the GPU box: pip install -e '.[gpu]'",
            file=sys.stderr,
        )
        sys.exit(1)


def train(args: argparse.Namespace) -> None:
    import atexit
    import hashlib
    import json
    import random
    import subprocess
    from collections import Counter
    from pathlib import Path

    import numpy as np
    import torch
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )

    try:
        from sklearn.metrics import (
            f1_score as sk_f1,
            precision_score as sk_precision,
            recall_score as sk_recall,
        )
        has_sklearn = True
    except ImportError:
        has_sklearn = False

    from .schema import SCHEMA_VERSION, SECTION_LABELS, SectionRecord

    ID2LABEL: dict[int, str] = {i: lbl for i, lbl in enumerate(SECTION_LABELS)}
    LABEL2ID: dict[str, int] = {lbl: i for i, lbl in ID2LABEL.items()}
    NUM_LABELS = len(SECTION_LABELS)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def load_jsonl(path: Path) -> list[SectionRecord]:
        records = []
        with path.open() as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rec = SectionRecord.model_validate(obj)
                if rec.schema_version != SCHEMA_VERSION:
                    raise ValueError(
                        f"{path}:{lineno} schema_version={rec.schema_version}, "
                        f"expected {SCHEMA_VERSION}"
                    )
                records.append(rec)
        return records

    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def records_to_dataset(records: list[SectionRecord], tokenizer, max_length: int):
        import datasets as _datasets
        rows = []
        for rec in records:
            enc = tokenizer(
                rec.first_chars,
                max_length=max_length,
                truncation=True,
                padding="max_length",
            )
            label_vec = [float(rec.labels.get(lbl, False)) for lbl in SECTION_LABELS]
            rows.append({
                "input_ids": enc["input_ids"],
                "attention_mask": enc["attention_mask"],
                "labels": label_vec,
            })
        return _datasets.Dataset.from_list(rows)

    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    def compute_section_metrics(eval_pred):
        logits, labels = eval_pred
        probs = _sigmoid(np.array(logits))
        preds = (probs >= 0.5).astype(int)
        labels = np.array(labels).astype(int)

        metrics: dict = {}
        if has_sklearn:
            for i, lbl in enumerate(SECTION_LABELS):
                try:
                    metrics[f"f1_{lbl}"] = float(sk_f1(labels[:, i], preds[:, i], zero_division=0))
                    metrics[f"precision_{lbl}"] = float(sk_precision(labels[:, i], preds[:, i], zero_division=0))
                    metrics[f"recall_{lbl}"] = float(sk_recall(labels[:, i], preds[:, i], zero_division=0))
                except Exception:
                    metrics.setdefault(f"f1_{lbl}", 0.0)
            try:
                metrics["f1_macro"] = float(sk_f1(labels, preds, average="macro", zero_division=0))
                metrics["precision_macro"] = float(sk_precision(labels, preds, average="macro", zero_division=0))
                metrics["recall_macro"] = float(sk_recall(labels, preds, average="macro", zero_division=0))
                metrics["f1_micro"] = float(sk_f1(labels, preds, average="micro", zero_division=0))
                metrics["precision_micro"] = float(sk_precision(labels, preds, average="micro", zero_division=0))
                metrics["recall_micro"] = float(sk_recall(labels, preds, average="micro", zero_division=0))
            except Exception:
                for k in ["f1_macro", "precision_macro", "recall_macro",
                          "f1_micro", "precision_micro", "recall_micro"]:
                    metrics.setdefault(k, 0.0)
        else:
            tp = np.sum((preds == 1) & (labels == 1), axis=0).astype(float)
            fp = np.sum((preds == 1) & (labels == 0), axis=0).astype(float)
            fn = np.sum((preds == 0) & (labels == 1), axis=0).astype(float)
            per_f1 = 2 * tp / (2 * tp + fp + fn + 1e-9)
            for i, lbl in enumerate(SECTION_LABELS):
                metrics[f"f1_{lbl}"] = float(per_f1[i])
            metrics["f1_macro"] = float(per_f1.mean())
            tp_s, fp_s, fn_s = tp.sum(), fp.sum(), fn.sum()
            metrics["f1_micro"] = float(2 * tp_s / (2 * tp_s + fp_s + fn_s + 1e-9))
            metrics["precision_micro"] = float(tp_s / (tp_s + fp_s + 1e-9))
            metrics["recall_micro"] = float(tp_s / (tp_s + fn_s + 1e-9))

        return metrics

    def _git_state() -> dict:
        try:
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
            dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
            return {"commit": commit, "dirty": dirty, "branch": branch}
        except Exception as exc:
            return {"error": str(exc)}

    def _env_info() -> dict:
        import platform
        info: dict = {"python": sys.version, "platform": platform.platform()}
        try:
            info["torch"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            info["cuda_version"] = torch.version.cuda
        except Exception:
            pass
        try:
            import transformers as _tr
            info["transformers"] = _tr.__version__
        except Exception:
            pass
        return info

    class EpochMetricsCallback(TrainerCallback):
        def __init__(self, out_dir: Path):
            self.out_dir = out_dir

        def on_evaluate(self, args, state, control, metrics=None, **kwargs):
            epoch = int(state.epoch) if state.epoch is not None else state.global_step
            out = self.out_dir / f"epoch{epoch:02d}.json"
            with out.open("w") as f:
                json.dump(metrics or {}, f, indent=2)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    out_dir = Path("checkpoints") / "section" / args.version
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_final_path = out_dir / "metrics_final.json"
    metrics_so_far: dict = {"status": "started"}

    def _write_metrics_final():
        with metrics_final_path.open("w") as f:
            json.dump(metrics_so_far, f, indent=2)

    atexit.register(_write_metrics_final)

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    backbone = os.environ.get("BCF_BACKBONE", args.backbone)
    print(f"Backbone: {backbone}")

    train_path = Path(args.train)
    eval_path = Path(args.eval)
    train_records = load_jsonl(train_path)
    eval_records = load_jsonl(eval_path)
    print(f"Train records: {len(train_records)}, Eval records: {len(eval_records)}")

    label_counts = Counter(
        lbl for r in train_records for lbl, val in r.labels.items() if val
    )
    print(f"Label counts (positive): {dict(label_counts)}")

    tokenizer = AutoTokenizer.from_pretrained(backbone)
    max_length = min(4096, tokenizer.model_max_length)

    print("Encoding training set...")
    train_ds = records_to_dataset(train_records, tokenizer, max_length=max_length)
    print("Encoding eval set...")
    eval_ds = records_to_dataset(eval_records, tokenizer, max_length=max_length)

    train_ds.set_format("torch")
    eval_ds.set_format("torch")

    model = AutoModelForSequenceClassification.from_pretrained(
        backbone,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,
    )

    best_dir = out_dir / "best"
    bf16 = args.bf16 and torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False
    fp16 = (not bf16) and torch.cuda.is_available()

    training_args = TrainingArguments(
        output_dir=str(out_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=max(args.batch_size, 16),
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_ratio=0.1,
        max_grad_norm=1.0,
        lr_scheduler_type="cosine",
        bf16=bf16,
        fp16=fp16,
        seed=args.seed,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=10,
        report_to=[],
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=compute_section_metrics,
        callbacks=[EpochMetricsCallback(out_dir)],
    )

    metrics_so_far["status"] = "training"
    _write_metrics_final()

    result = trainer.train()
    eval_metrics = trainer.evaluate()
    metrics_so_far.update(result.metrics)
    metrics_so_far.update(eval_metrics)
    metrics_so_far["status"] = "done"

    best_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_dir))
    tokenizer.save_pretrained(str(best_dir))

    with (best_dir / "id2label.json").open("w") as f:
        json.dump(ID2LABEL, f, indent=2)

    with (best_dir / "train_args.json").open("w") as f:
        json.dump({
            "backbone": backbone, "epochs": args.epochs, "lr": args.lr,
            "batch_size": args.batch_size, "seed": args.seed,
            "bf16": bf16, "fp16": fp16, "version": args.version,
            "train": str(train_path), "eval": str(eval_path),
            "num_labels": NUM_LABELS, "labels": SECTION_LABELS,
        }, f, indent=2)

    manifest = {
        "train": {"path": str(train_path.resolve()), "sha256": sha256_file(train_path), "records": len(train_records)},
        "eval": {"path": str(eval_path.resolve()), "sha256": sha256_file(eval_path), "records": len(eval_records)},
    }
    with (out_dir / "dataset_manifest.json").open("w") as f:
        json.dump(manifest, f, indent=2)

    with (out_dir / "git_state.json").open("w") as f:
        json.dump(_git_state(), f, indent=2)

    with (out_dir / "env.json").open("w") as f:
        json.dump(_env_info(), f, indent=2)

    _write_metrics_final()

    print(f"\nTraining complete. Best model saved to {best_dir}")
    print(f"f1_macro: {eval_metrics.get('eval_f1_macro', 'N/A')}")


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    _require_gpu_stack()
    train(args)
