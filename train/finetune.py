"""Fine-tune GLiNER on Bosch synthetic PII data.

Usage:
  # local CPU/MPS smoke (small)
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
    p.add_argument("--max-types", type=int, default=25)
    p.add_argument("--warmup-ratio", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    # Deferred imports — heavy deps only loaded when actually training.
    import gliner as _gliner
    import torch
    from gliner import GLiNER
    from gliner.training import Trainer, TrainingArguments

    print(f"[gliner] version={getattr(_gliner, '__version__', '?')}")

    # Collator: name + signature differ across versions
    try:
        from gliner.data_processing.collator import DataCollator as _DC
    except ImportError:
        from gliner.data_processing.collator import DataCollatorWithPadding as _DC

    # Dataset wrapper exists in some versions only; Trainer can also accept raw list
    GLiNERDataset = None
    for modpath in (
        "gliner.data_processing",
        "gliner.data_processing.dataset",
        "gliner.dataset",
    ):
        try:
            mod = __import__(modpath, fromlist=["GLiNERDataset"])
            GLiNERDataset = getattr(mod, "GLiNERDataset", None)
            if GLiNERDataset is not None:
                print(f"[gliner] using {modpath}.GLiNERDataset")
                break
        except ImportError:
            continue

    device = _pick_device()
    print(f"[device] {device}")

    train_data = _load_jsonl(Path(args.train))
    val_data = _load_jsonl(Path(args.val))
    print(f"[data] train={len(train_data)} val={len(val_data)}")

    print(f"[model] loading base: {args.base_model}")
    model = GLiNER.from_pretrained(args.base_model)
    model = model.to(device)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Wrap if available; else pass raw lists (Trainer handles it).
    if GLiNERDataset is not None:
        train_dataset = GLiNERDataset(train_data, model.config, data_processor=model.data_processor)
        val_dataset = GLiNERDataset(val_data, model.config, data_processor=model.data_processor)
    else:
        train_dataset = train_data
        val_dataset = val_data

    training_args = TrainingArguments(
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
        max_steps=args.max_steps if args.max_steps > 0 else -1,
        eval_strategy="epoch",
        save_strategy="steps",
        save_steps=args.save_steps,
        save_total_limit=2,
        dataloader_num_workers=0,
        use_cpu=(device == "cpu"),
        bf16=(device == "cuda"),
        report_to="none",
        seed=args.seed,
    )

    # Collator constructor signature varies — try modern kwargs first, fall back to legacy
    try:
        data_collator = _DC(model.config, data_processor=model.data_processor, prepare_labels=True)
    except TypeError:
        data_collator = _DC(model.config)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=model.data_processor.transformer_tokenizer,
        data_collator=data_collator,
    )

    print(f"[train] starting — epochs={args.epochs} batch={args.batch_size}")
    trainer.train()

    print(f"[save] {out_dir}")
    trainer.save_model(str(out_dir))

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
