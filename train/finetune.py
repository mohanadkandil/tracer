"""Fine-tune GLiNER on Bosch synthetic PII data.

Uses the high-level `model.train_model(...)` API which is stable across gliner versions
and abstracts away DataCollator / Dataset wiring.

Usage:
  # local CPU/MPS smoke
  uv run --group train python -m train.finetune \
      --train data/gliner/train.jsonl --val data/gliner/val.jsonl \
      --out models/gliner-bosch --epochs 1 --batch-size 4 --max-steps 50

  # Colab GPU full run
  python -m train.finetune \
      --train data/gliner/train.jsonl --val data/gliner/val.jsonl \
      --out models/gliner-bosch --epochs 3 --batch-size 16

Requires the `train` dependency group:
  uv sync --group train
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ENTITY_LABELS = [
    "PERSON",
    "EMPLOYEE_ID",
    "EMAIL",
    "PHONE",
    "ADDRESS",
    "TAX_ID",
    "IBAN",
    "DEPARTMENT",
    "COMPANY",
    "DATE",
    "ID_NUMBER",
    "SIGNATURE",
    "USERNAME",
]


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="data/gliner/train.jsonl")
    p.add_argument("--val", default="data/gliner/val.jsonl")
    p.add_argument("--out", default="models/gliner-bosch")
    p.add_argument("--base-model", default="urchade/gliner_multi_pii-v1")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=5e-6)
    p.add_argument("--lr-others", type=float, default=1e-5)
    p.add_argument("--max-steps", type=int, default=0, help="0 = no cap (run full epochs)")
    p.add_argument("--save-steps", type=int, default=500)
    p.add_argument("--warmup-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "true")

    # Deferred imports — heavy deps only loaded when actually training.
    import gliner as _gliner
    import torch
    from gliner import GLiNER

    print(f"[gliner] version={getattr(_gliner, '__version__', '?')}")

    device = _pick_device()
    print(f"[device] {device}")

    train_data = _load_jsonl(Path(args.train))
    val_data = _load_jsonl(Path(args.val))
    print(f"[data] train={len(train_data)} val={len(val_data)}")

    print(f"[model] loading base: {args.base_model}")
    model = GLiNER.from_pretrained(args.base_model)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # train_model API kwargs are stable across versions. We pass extras only when supported.
    train_kwargs = dict(
        train_dataset=train_data,
        eval_dataset=val_data,
        output_dir=str(out_dir),
        learning_rate=args.lr,
        weight_decay=0.01,
        others_lr=args.lr_others,
        others_weight_decay=0.01,
        lr_scheduler_type="linear",
        warmup_ratio=args.warmup_ratio,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        save_steps=args.save_steps,
        save_total_limit=2,
        dataloader_num_workers=0,
        use_cpu=(device == "cpu"),
        report_to="none",
        seed=args.seed,
    )
    if args.max_steps > 0:
        train_kwargs["max_steps"] = args.max_steps
    if device == "cuda":
        train_kwargs["bf16"] = True

    print(f"[train] starting — epochs={args.epochs} batch={args.batch_size}")
    try:
        model.train_model(**train_kwargs)
    except TypeError as e:
        # Older gliner versions may reject some kwargs — strip and retry.
        print(f"[warn] train_model rejected some kwargs: {e}\n[warn] retrying with minimal set")
        minimal = dict(
            train_dataset=train_data,
            eval_dataset=val_data,
            output_dir=str(out_dir),
            learning_rate=args.lr,
            per_device_train_batch_size=args.batch_size,
            per_device_eval_batch_size=args.batch_size,
            num_train_epochs=args.epochs,
            save_steps=args.save_steps,
            save_total_limit=2,
            use_cpu=(device == "cpu"),
            report_to="none",
        )
        model.train_model(**minimal)

    # `train_model` saves automatically, but save again to be safe.
    print(f"[save] {out_dir}")
    model.save_pretrained(str(out_dir))

    meta = {
        "base_model": args.base_model,
        "entity_labels": ENTITY_LABELS,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "device": device,
        "train_size": len(train_data),
        "val_size": len(val_data),
    }
    (out_dir / "training_meta.json").write_text(json.dumps(meta, indent=2))
    print("[done]")


if __name__ == "__main__":
    main()
