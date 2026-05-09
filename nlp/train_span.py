"""Two-head span model training entry point.

Usage:
    uv run python nlp/train_span.py \\
        --train data/labeled/spans/train.jsonl \\
        --eval  data/labeled/spans/eval.jsonl \\
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
        description="Train the two-head span model (layer-A events + layer-B entities).",
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
    """Import torch/transformers at the call site; exit with a clear message if missing."""
    try:
        import numpy  # noqa: F401
        import torch  # noqa: F401
        from transformers import AutoModel  # noqa: F401
    except ImportError as e:
        print(
            f"ERROR: {e}\n"
            "torch and transformers must be installed to run training.\n"
            "On the GPU box: pip install -e '.[gpu]'",
            file=sys.stderr,
        )
        sys.exit(1)


def train(args: argparse.Namespace) -> None:
    """Full training loop — only called when torch/transformers are present."""
    import atexit
    import hashlib
    import inspect
    import json
    import random
    import subprocess
    from collections import Counter
    from pathlib import Path

    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from transformers import (
        AutoModel,
        AutoTokenizer,
        PretrainedConfig,
        PreTrainedModel,
        Trainer,
        TrainerCallback,
        TrainingArguments,
    )
    from transformers.modeling_outputs import TokenClassifierOutput

    try:
        from seqeval.metrics import (
            f1_score,
            precision_score,
            recall_score,
        )
    except ImportError as e:
        print(f"ERROR: seqeval not installed: {e}", file=sys.stderr)
        sys.exit(1)

    import datasets as _datasets  # noqa: F401

    from .encode import ID2LABEL_A, ID2LABEL_B, encode_dataset
    from .schema import LAYER_A_BIO, LAYER_B_BIO, SCHEMA_VERSION, SpanRecord

    # ------------------------------------------------------------------
    # Two-head model (defined here to avoid module-level base class deps)
    # ------------------------------------------------------------------

    class TwoHeadConfig(PretrainedConfig):
        model_type = "two_head_token_classifier"

        def __init__(
            self,
            backbone_name: str = "answerdotai/ModernBERT-base",
            num_labels_a: int = len(LAYER_A_BIO),
            num_labels_b: int = len(LAYER_B_BIO),
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.backbone_name = backbone_name
            self.num_labels_a = num_labels_a
            self.num_labels_b = num_labels_b

    class TwoHeadTokenClassifier(PreTrainedModel):
        config_class = TwoHeadConfig

        def __init__(self, config: TwoHeadConfig):
            super().__init__(config)
            self.backbone = AutoModel.from_pretrained(config.backbone_name)
            d = self.backbone.config.hidden_size
            self.head_a = nn.Linear(d, config.num_labels_a)
            self.head_b = nn.Linear(d, config.num_labels_b)

        def forward(
            self,
            input_ids=None,
            attention_mask=None,
            labels_layer_a=None,
            labels_layer_b=None,
            **kwargs,
        ):
            h = self.backbone(
                input_ids, attention_mask=attention_mask
            ).last_hidden_state
            logits_a = self.head_a(h)
            logits_b = self.head_b(h)

            loss = None
            if labels_layer_a is not None and labels_layer_b is not None:
                num_a = self.config.num_labels_a
                num_b = self.config.num_labels_b
                loss = F.cross_entropy(
                    logits_a.view(-1, num_a),
                    labels_layer_a.view(-1),
                    ignore_index=-100,
                ) + F.cross_entropy(
                    logits_b.view(-1, num_b),
                    labels_layer_b.view(-1),
                    ignore_index=-100,
                )
            return TokenClassifierOutput(loss=loss, logits=(logits_a, logits_b))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def load_jsonl(path: Path) -> list[SpanRecord]:
        records = []
        with path.open() as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                rec = SpanRecord.model_validate(obj)
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

    def _ids_to_bio_tags(pred_ids, id2label, ref_ids):
        preds_out, refs_out = [], []
        for seq, ref_seq in zip(pred_ids, ref_ids):
            p_seq, r_seq = [], []
            for pid, rid in zip(seq, ref_seq):
                if rid == -100:
                    continue
                p_seq.append(id2label.get(pid, "O"))
                r_seq.append(id2label.get(rid, "O"))
            preds_out.append(p_seq)
            refs_out.append(r_seq)
        return preds_out, refs_out

    def make_compute_metrics(id2label_a, id2label_b):
        def compute_metrics(eval_pred):
            raw_preds, raw_labels = eval_pred
            if isinstance(raw_preds, (list, tuple)):
                logits_a, logits_b = raw_preds
            else:
                raise ValueError(f"Unexpected predictions type: {type(raw_preds)}")
            if isinstance(raw_labels, (list, tuple)):
                labels_a, labels_b = raw_labels
            else:
                raise ValueError(f"Unexpected labels type: {type(raw_labels)}")

            pred_ids_a = np.argmax(logits_a, axis=-1).tolist()
            pred_ids_b = np.argmax(logits_b, axis=-1).tolist()
            labels_a = labels_a.tolist() if hasattr(labels_a, "tolist") else list(labels_a)
            labels_b = labels_b.tolist() if hasattr(labels_b, "tolist") else list(labels_b)

            p_a, r_a = _ids_to_bio_tags(pred_ids_a, id2label_a, labels_a)
            p_b, r_b = _ids_to_bio_tags(pred_ids_b, id2label_b, labels_b)

            metrics = {}
            for prefix, preds, refs in [("a", p_a, r_a), ("b", p_b, r_b)]:
                try:
                    metrics[f"f1_{prefix}_micro"] = f1_score(refs, preds, average="micro")
                    metrics[f"precision_{prefix}_micro"] = precision_score(refs, preds, average="micro")
                    metrics[f"recall_{prefix}_micro"] = recall_score(refs, preds, average="micro")
                    metrics[f"f1_{prefix}_macro"] = f1_score(refs, preds, average="macro")
                    metrics[f"precision_{prefix}_macro"] = precision_score(refs, preds, average="macro")
                    metrics[f"recall_{prefix}_macro"] = recall_score(refs, preds, average="macro")
                except Exception:
                    for key in [
                        f"f1_{prefix}_micro", f"precision_{prefix}_micro", f"recall_{prefix}_micro",
                        f"f1_{prefix}_macro", f"precision_{prefix}_macro", f"recall_{prefix}_macro",
                    ]:
                        metrics.setdefault(key, 0.0)

            metrics["f1_overall"] = (
                metrics.get("f1_a_micro", 0.0) + metrics.get("f1_b_micro", 0.0)
            ) / 2.0
            return metrics

        return compute_metrics

    def collate_span_features(features):
        max_len = max(len(feature["input_ids"]) for feature in features)
        pad_token_id = tokenizer.pad_token_id
        if pad_token_id is None:
            pad_token_id = 0

        def padded_tensor(feature, key: str, pad_value: int):
            value = feature[key]
            tensor = value if torch.is_tensor(value) else torch.tensor(value)
            pad_width = max_len - tensor.shape[0]
            if pad_width:
                tensor = F.pad(tensor, (0, pad_width), value=pad_value)
            return tensor

        return {
            "input_ids": torch.stack(
                [padded_tensor(feature, "input_ids", pad_token_id) for feature in features]
            ),
            "attention_mask": torch.stack(
                [padded_tensor(feature, "attention_mask", 0) for feature in features]
            ),
            "labels_layer_a": torch.stack(
                [padded_tensor(feature, "labels_layer_a", -100) for feature in features]
            ),
            "labels_layer_b": torch.stack(
                [padded_tensor(feature, "labels_layer_b", -100) for feature in features]
            ),
        }

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

    out_dir = Path("checkpoints") / "span" / args.version
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

    train_a = Counter(sp.label for r in train_records for sp in r.spans if sp.layer == "A")
    train_b = Counter(sp.label for r in train_records for sp in r.spans if sp.layer == "B")
    print(f"Layer-A label counts: {dict(train_a)}")
    print(f"Layer-B label counts: {dict(train_b)}")

    tokenizer = AutoTokenizer.from_pretrained(backbone)

    print("Encoding training set...")
    train_ds = encode_dataset(train_records, tokenizer)
    print("Encoding eval set...")
    eval_ds = encode_dataset(eval_records, tokenizer)

    keep_cols = {"input_ids", "attention_mask", "labels_layer_a", "labels_layer_b"}
    train_ds = train_ds.remove_columns(
        [c for c in train_ds.column_names if c not in keep_cols]
    )
    eval_ds = eval_ds.remove_columns(
        [c for c in eval_ds.column_names if c not in keep_cols]
    )
    train_ds.set_format("torch")
    eval_ds.set_format("torch")

    config = TwoHeadConfig(
        backbone_name=backbone,
        num_labels_a=len(LAYER_A_BIO),
        num_labels_b=len(LAYER_B_BIO),
    )
    model = TwoHeadTokenClassifier(config)

    best_dir = out_dir / "best"
    bf16 = args.bf16 and torch.cuda.is_bf16_supported() if torch.cuda.is_available() else False
    fp16 = (not bf16) and torch.cuda.is_available()

    eval_strategy_arg = (
        {"eval_strategy": "epoch"}
        if "eval_strategy" in inspect.signature(TrainingArguments.__init__).parameters
        else {"evaluation_strategy": "epoch"}
    )

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
        **eval_strategy_arg,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_overall",
        greater_is_better=True,
        logging_steps=10,
        report_to=[],
        remove_unused_columns=False,
        dataloader_pin_memory=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collate_span_features,
        compute_metrics=make_compute_metrics(ID2LABEL_A, ID2LABEL_B),
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

    with (best_dir / "id2label_a.json").open("w") as f:
        json.dump(ID2LABEL_A, f, indent=2)
    with (best_dir / "id2label_b.json").open("w") as f:
        json.dump(ID2LABEL_B, f, indent=2)

    with (best_dir / "train_args.json").open("w") as f:
        json.dump({
            "backbone": backbone, "epochs": args.epochs, "lr": args.lr,
            "batch_size": args.batch_size, "seed": args.seed,
            "bf16": bf16, "fp16": fp16, "version": args.version,
            "train": str(train_path), "eval": str(eval_path),
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
    print(f"f1_overall: {eval_metrics.get('eval_f1_overall', 'N/A')}")


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    _require_gpu_stack()
    train(args)
