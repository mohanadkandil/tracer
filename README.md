# Bosch GDPR PII — Synthetic Dataset Pipeline

Generates labeled NER training data for fine-tuning a PII detector on Bosch-style
corporate documents. Three sources combined:

| Source        | Cost   | Role                                                      |
|---------------|--------|-----------------------------------------------------------|
| Faker + Jinja | $0     | Deterministic templated fills, perfect span labels        |
| LLM paraphrase| ~$0.50 | Prose diversity (preserve entities verbatim)              |
| Hard negatives| ~$0.40 | Non-PII business docs (teach model to NOT over-flag)      |

Default sweet-spot run produces ~5K labeled examples, split 80/10/10 train/val/test.

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # paste OPENROUTER_API_KEY
```

Offline smoke (no API calls, ~3s):
```bash
python -m data_gen.pipeline --no-llm --filled 50 --blanks 10 --negatives-local 10 \
  --paraphrase 0 --negatives-llm 0 --out data/smoke
```

Full sweet-spot run (~5K examples, ~$5 on OpenRouter, ~15min):
```bash
python -m data_gen.pipeline --out data/out \
  --filled 2500 --blanks 500 \
  --paraphrase 1500 \
  --negatives-local 300 --negatives-llm 700 \
  --concurrency 8
```

## Output format (JSONL)

```json
{
  "id": "exp-1a2b3c4d",
  "doc_type": "expense",
  "lang": "de",
  "is_template": false,
  "is_filled": true,
  "source": "faker",
  "text": "Spesenabrechnung (ausgefüllt)\nMitarbeiter: Hans Müller (E-12345)\n...",
  "entities": [
    {"start": 42, "end": 53, "label": "PERSON", "value": "Hans Müller"},
    {"start": 55, "end": 62, "label": "EMPLOYEE_ID", "value": "E-12345"}
  ]
}
```

## Entity labels

`PERSON · EMPLOYEE_ID · EMAIL · PHONE · ADDRESS · TAX_ID · IBAN · DEPARTMENT · COMPANY · DATE · ID_NUMBER · SIGNATURE · USERNAME`

## Doc types

`expense · it_access · incident · supplier · training · policy · meeting · blank_template`

## Design choices

- **Spans by construction**: `TextBuilder` records `(start, end)` as it appends — never
  post-locates entities, so labels are perfect for Faker examples.
- **Paraphrase preserves entities**: prompt forbids altering listed values; after
  rewrite we re-locate by exact substring. If any entity is missing or appears
  twice (ambiguous), the example is dropped — favours precision over volume.
- **Hard negatives**: rule-based local + LLM-generated, both run through a PII
  regex sweep. Anything resembling email/IBAN/tax-id/phone is rejected.
- **Reproducibility**: every step takes `--seed`. Deterministic Faker, deterministic
  shuffle. LLM steps are inherently non-deterministic (temperature 0.7) but the
  list of inputs and the dropping logic is reproducible.

## Files

- `data_gen/schemas.py` — Pydantic `Example`, `Entity`, plus `TextBuilder` span helper
- `data_gen/generators.py` — Faker generators for 5 Bosch doc types (DE + EN) + blank templates
- `data_gen/paraphrase.py` — OpenRouter async paraphrase with entity-preserving prompt
- `data_gen/hard_negatives.py` — rule-based + LLM-generated negatives with regex filter
- `data_gen/pipeline.py` — CLI orchestrator, train/val/test split, stats
