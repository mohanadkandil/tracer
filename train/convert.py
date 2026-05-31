"""Convert our JSONL (char-offset spans) to GLiNER training format (token-offset spans).

GLiNER expects:
  {"tokenized_text": ["Hello", ",", "World"], "ner": [[start_tok, end_tok_inclusive, "label"]]}

Tokenization here is whitespace + simple punctuation split (matches GLiNER conventions).
Any entity whose char span doesn't align cleanly to token boundaries is dropped with a counter.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import orjson

# Simple tokenizer: keep words and standalone punctuation. Mirrors GLiNER's expectations.
_TOKEN_RE = re.compile(r"\w+(?:[-_.]\w+)*|[^\s\w]", re.UNICODE)


def tokenize_with_offsets(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for m in _TOKEN_RE.finditer(text):
        out.append((m.group(), m.start(), m.end()))
    return out


def char_to_token_span(
    tokens: list[tuple[str, int, int]], char_start: int, char_end: int
) -> tuple[int, int] | None:
    """Return (start_tok_idx, end_tok_idx_inclusive) covering [char_start, char_end), or None if no clean alignment."""
    start_tok: int | None = None
    end_tok: int | None = None
    for i, (_, s, e) in enumerate(tokens):
        if e <= char_start:
            continue
        if s >= char_end:
            break
        if start_tok is None:
            start_tok = i
        end_tok = i
    if start_tok is None or end_tok is None:
        return None
    # Sanity: spanned tokens should fully cover the entity char range (allow leading/trailing whitespace).
    span_start_char = tokens[start_tok][1]
    span_end_char = tokens[end_tok][2]
    if span_start_char > char_start or span_end_char < char_end:
        return None
    return start_tok, end_tok


def convert_example(text: str, entities: list[dict]) -> dict | None:
    toks = tokenize_with_offsets(text)
    if not toks:
        return None
    tok_strs = [t[0] for t in toks]
    ner: list[list] = []
    dropped = 0
    for ent in entities:
        rng = char_to_token_span(toks, ent["start"], ent["end"])
        if rng is None:
            dropped += 1
            continue
        ner.append([rng[0], rng[1], ent["label"]])
    return {"tokenized_text": tok_strs, "ner": ner, "_dropped": dropped}


def convert_file(in_path: Path, out_path: Path) -> dict:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_in = 0
    n_out = 0
    total_entities = 0
    dropped_entities = 0
    with in_path.open("rb") as fi, out_path.open("wb") as fo:
        for line in fi:
            if not line.strip():
                continue
            n_in += 1
            ex = orjson.loads(line)
            ents = ex.get("entities", [])
            total_entities += len(ents)
            conv = convert_example(ex["text"], ents)
            if conv is None:
                continue
            dropped_entities += conv.pop("_dropped")
            # Negatives are valid: empty ner allowed for hard-neg docs.
            fo.write(orjson.dumps({"tokenized_text": conv["tokenized_text"], "ner": conv["ner"]}))
            fo.write(b"\n")
            n_out += 1
    return {
        "examples_in": n_in,
        "examples_out": n_out,
        "entities_total": total_entities,
        "entities_dropped": dropped_entities,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in-dir", default="data/out", help="Directory containing train.jsonl / val.jsonl / test.jsonl")
    p.add_argument("--out-dir", default="data/gliner")
    args = p.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)

    for split in ["train", "val", "test"]:
        src = in_dir / f"{split}.jsonl"
        if not src.exists():
            print(f"skip {split}: {src} not found")
            continue
        dst = out_dir / f"{split}.jsonl"
        stats = convert_file(src, dst)
        print(f"{split}: in={stats['examples_in']} out={stats['examples_out']} "
              f"entities={stats['entities_total']} dropped={stats['entities_dropped']}")


if __name__ == "__main__":
    main()
