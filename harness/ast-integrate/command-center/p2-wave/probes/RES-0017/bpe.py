"""Pinned byte-pair tokenizer trained on tokenizer_seed.txt, never the session."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

N_MERGES = 0
HERE = Path(__file__).resolve().parent
SEED = HERE / "tokenizer_seed.txt"
RANKS = HERE / "bpe_ranks.json"

TOKENIZER_ID = "res0017.bpe.utf8-bytes.identity"
TOKENIZER_VERSION = "1"


class BPE:
    def __init__(self, pair_to_id: dict[tuple[int, int], int], ranks: dict[tuple[int, int], int]):
        self.pair_to_id = pair_to_id
        self.ranks = ranks

    def encode(self, text: str) -> list[int]:
        tokens = list(text.encode("utf-8"))
        if not self.ranks:
            return tokens
        while True:
            best_i = None
            best_rank = 10**9
            for i in range(len(tokens) - 1):
                pair = (tokens[i], tokens[i + 1])
                rank = self.ranks.get(pair)
                if rank is not None and rank < best_rank:
                    best_rank = rank
                    best_i = i
            if best_i is None:
                break
            pair = (tokens[best_i], tokens[best_i + 1])
            new_id = self.pair_to_id[pair]
            tokens[best_i : best_i + 2] = [new_id]
        return tokens

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def to_json(self) -> dict:
        merges = []
        for pair, rank in sorted(self.ranks.items(), key=lambda kv: kv[1]):
            merges.append(
                {
                    "a": pair[0],
                    "b": pair[1],
                    "rank": rank,
                    "id": self.pair_to_id[pair],
                }
            )
        return {
            "tokenizer_id": TOKENIZER_ID,
            "tokenizer_version": TOKENIZER_VERSION,
            "n_merges": len(merges),
            "merges": merges,
        }

    @classmethod
    def from_json(cls, doc: dict) -> "BPE":
        pair_to_id: dict[tuple[int, int], int] = {}
        ranks: dict[tuple[int, int], int] = {}
        for row in doc.get("merges") or []:
            pair = (int(row["a"]), int(row["b"]))
            ranks[pair] = int(row["rank"])
            pair_to_id[pair] = int(row["id"])
        return cls(pair_to_id, ranks)


def train(text: str, n_merges: int = N_MERGES) -> BPE:
    tokens = list(text.encode("utf-8"))
    pair_to_id: dict[tuple[int, int], int] = {}
    ranks: dict[tuple[int, int], int] = {}
    next_id = 256
    for rank in range(n_merges):
        counts = Counter(zip(tokens, tokens[1:]))
        if not counts:
            break
        pair, freq = counts.most_common(1)[0]
        if freq < 2:
            break
        ranks[pair] = rank
        pair_to_id[pair] = next_id
        rebuilt: list[int] = []
        i = 0
        n = len(tokens)
        while i < n:
            if i < n - 1 and (tokens[i], tokens[i + 1]) == pair:
                rebuilt.append(next_id)
                i += 2
            else:
                rebuilt.append(tokens[i])
                i += 1
        tokens = rebuilt
        next_id += 1
    return BPE(pair_to_id, ranks)


def load_pinned() -> BPE:
    import json

    if not RANKS.is_file():
        raise FileNotFoundError(f"pinned ranks missing: {RANKS}")
    doc = json.loads(RANKS.read_text(encoding="utf-8"))
    return BPE.from_json(doc)


def train_from_seed() -> BPE:
    text = SEED.read_text(encoding="utf-8")
    return train(text, N_MERGES)
