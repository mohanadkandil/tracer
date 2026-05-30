"""End-to-end synthetic dataset pipeline.

Usage:
  python -m data_gen.pipeline --out data/out --filled 2500 --paraphrase 1500 --negatives 1000

Writes JSONL splits: train.jsonl, val.jsonl, test.jsonl plus stats.json.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import orjson
from dotenv import load_dotenv

from .generators import generate_blanks, generate_filled
from .hard_negatives import generate_llm_negatives, generate_local_negatives
from .paraphrase import paraphrase_batch
from .schemas import Example


@dataclass
class Stats:
    filled: int
    blanks: int
    paraphrased: int
    negatives_local: int
    negatives_llm: int
    total: int
    train: int
    val: int
    test: int
    seed: int
    by_doc_type: dict[str, int]
    by_lang: dict[str, int]
    by_entity_label: dict[str, int]


def _write_jsonl(path: Path, examples: list[Example]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        for ex in examples:
            f.write(orjson.dumps(ex.model_dump()))
            f.write(b"\n")


def _split(examples: list[Example], ratios: tuple[float, float, float], seed: int) -> tuple[list, list, list]:
    rng = random.Random(seed)
    rng.shuffle(examples)
    n = len(examples)
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    train = examples[:n_train]
    val = examples[n_train : n_train + n_val]
    test = examples[n_train + n_val :]
    return train, val, test


def _compute_stats(buckets: dict[str, list[Example]], train: list, val: list, test: list, seed: int) -> Stats:
    all_ex = train + val + test
    by_doc: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    by_label: dict[str, int] = {}
    for ex in all_ex:
        by_doc[ex.doc_type] = by_doc.get(ex.doc_type, 0) + 1
        by_lang[ex.lang] = by_lang.get(ex.lang, 0) + 1
        for e in ex.entities:
            by_label[e.label] = by_label.get(e.label, 0) + 1
    return Stats(
        filled=len(buckets["filled"]),
        blanks=len(buckets["blanks"]),
        paraphrased=len(buckets["paraphrased"]),
        negatives_local=len(buckets["neg_local"]),
        negatives_llm=len(buckets["neg_llm"]),
        total=len(all_ex),
        train=len(train),
        val=len(val),
        test=len(test),
        seed=seed,
        by_doc_type=by_doc,
        by_lang=by_lang,
        by_entity_label=by_label,
    )


async def _run_async(args: argparse.Namespace) -> None:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Faker filled: {args.filled}")
    filled = generate_filled(args.filled, lang_ratio_de=args.de_ratio, seed=args.seed)

    print(f"[2/5] Blank templates: {args.blanks}")
    blanks = generate_blanks(args.blanks, lang_ratio_de=args.de_ratio, seed=args.seed + 1) if args.blanks > 0 else []

    paraphrased: list[Example] = []
    if args.paraphrase > 0 and not args.no_llm:
        print(f"[3/5] Paraphrasing {args.paraphrase} via OpenRouter")
        source_for_pp = random.Random(args.seed + 2).sample(filled, min(args.paraphrase, len(filled)))
        paraphrased = await paraphrase_batch(source_for_pp, concurrency=args.concurrency)
        print(f"       kept {len(paraphrased)} / {args.paraphrase} (failures + ambiguous spans dropped)")
    else:
        print("[3/5] Paraphrase skipped")

    neg_local = generate_local_negatives(args.negatives_local, lang_ratio_de=args.de_ratio, seed=args.seed + 3) if args.negatives_local > 0 else []
    print(f"[4/5] Local hard negatives: {len(neg_local)}")

    neg_llm: list[Example] = []
    if args.negatives_llm > 0 and not args.no_llm:
        print(f"       LLM hard negatives: {args.negatives_llm}")
        neg_llm = await generate_llm_negatives(args.negatives_llm, lang_ratio_de=args.de_ratio, concurrency=args.concurrency, seed=args.seed + 4)
        print(f"       kept {len(neg_llm)} / {args.negatives_llm}")
    else:
        print("       LLM negatives skipped")

    all_ex = filled + blanks + paraphrased + neg_local + neg_llm
    print(f"[5/5] Total examples: {len(all_ex)}")

    train, val, test = _split(all_ex, ratios=(0.8, 0.1, 0.1), seed=args.seed)
    _write_jsonl(out_dir / "train.jsonl", train)
    _write_jsonl(out_dir / "val.jsonl", val)
    _write_jsonl(out_dir / "test.jsonl", test)

    buckets = {
        "filled": filled,
        "blanks": blanks,
        "paraphrased": paraphrased,
        "neg_local": neg_local,
        "neg_llm": neg_llm,
    }
    stats = _compute_stats(buckets, train, val, test, seed=args.seed)
    (out_dir / "stats.json").write_bytes(orjson.dumps(asdict(stats), option=orjson.OPT_INDENT_2))

    print(f"\nWrote → {out_dir}/")
    print(f"  train.jsonl  {len(train)}")
    print(f"  val.jsonl    {len(val)}")
    print(f"  test.jsonl   {len(test)}")
    print(f"  stats.json")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/out")
    p.add_argument("--filled", type=int, default=2500)
    p.add_argument("--blanks", type=int, default=500)
    p.add_argument("--paraphrase", type=int, default=1500)
    p.add_argument("--negatives-local", type=int, default=300)
    p.add_argument("--negatives-llm", type=int, default=700)
    p.add_argument("--de-ratio", type=float, default=0.5)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-llm", action="store_true", help="Skip OpenRouter calls (offline smoke test)")
    args = p.parse_args()

    asyncio.run(_run_async(args))


if __name__ == "__main__":
    main()
