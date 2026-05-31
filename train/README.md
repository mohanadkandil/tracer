# Fine-tune GLiNER on Bosch PII

Two paths: **Colab** (recommended, fast, free GPU) or **local** (slow on CPU, OK for smoke).

## Path A — Colab (recommended)

1. Push this repo somewhere accessible (GitHub private OK).
2. Open `train/colab_finetune.ipynb` in Google Colab.
3. Edit cell 2 → set `REPO_URL` to your repo.
4. Runtime → Change runtime type → **T4 GPU**.
5. Run all cells. Trained model lands in your Google Drive at `MyDrive/gliner-bosch/`.

Expected runtime on T4: **~30-60 min** for 3 epochs over 3.7K examples.
Cost: **$0** (free Colab tier).

## Path B — Local

Install the heavy training deps (PyTorch, GLiNER, transformers):
```bash
uv sync --group train
```

Convert data:
```bash
uv run python -m train.convert --in-dir data/out --out-dir data/gliner
```

Smoke train (CPU, ~5 min, no accuracy gain — just verifies the loop runs):
```bash
uv run --group train python -m train.finetune \
    --train data/gliner/train.jsonl --val data/gliner/val.jsonl \
    --out models/gliner-bosch --epochs 1 --batch-size 4 --max-steps 20
```

Full local run (Apple Silicon with MPS, ~3-4hr):
```bash
uv run --group train python -m train.finetune \
    --train data/gliner/train.jsonl --val data/gliner/val.jsonl \
    --out models/gliner-bosch --epochs 3 --batch-size 8
```

## Sanity test after training

```python
from gliner import GLiNER
m = GLiNER.from_pretrained("models/gliner-bosch", local_files_only=True)
labels = ["PERSON","EMPLOYEE_ID","EMAIL","PHONE","ADDRESS","TAX_ID","IBAN",
          "DEPARTMENT","COMPANY","DATE","SIGNATURE","USERNAME"]
print(m.predict_entities("Mitarbeiter: Hans Müller (E-43217)", labels, threshold=0.4))
```

## Files

- `train/convert.py` — JSONL char-span → GLiNER token-span converter
- `train/finetune.py` — training script (works locally or in Colab)
- `train/colab_finetune.ipynb` — Colab notebook
- `train/README.md` — this file
