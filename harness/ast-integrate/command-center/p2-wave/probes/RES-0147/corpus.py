"""Load fetched snapshots, verify lineage hashes, build a lexical index."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAP = HERE / "fixtures" / "snapshots"
LINEAGE_PATH = HERE / "fixtures" / "lineage.json"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def load_lineage() -> dict:
    return json.loads(LINEAGE_PATH.read_text(encoding="utf-8"))


class Corpus:
    def __init__(self) -> None:
        lineage = load_lineage()
        self.lineage = lineage
        self.docs: dict[str, str] = {}
        self.meta: dict[str, dict] = {}
        self.doc_tokens: dict[str, list[str]] = {}
        self.doc_tf: dict[str, Counter] = {}
        self.df: Counter = Counter()
        for row in lineage["fetched"]:
            doc_id = str(row["id"])
            path = REPO / str(row["path"])
            raw = path.read_bytes()
            live_sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
            if live_sha != row["sha256"]:
                raise RuntimeError(f"lineage sha mismatch for {doc_id}")
            text = raw.decode("utf-8", errors="replace")
            self.docs[doc_id] = text
            self.meta[doc_id] = row
            toks = tokenize(text)
            self.doc_tokens[doc_id] = toks
            tf = Counter(toks)
            self.doc_tf[doc_id] = tf
            self.df.update(set(tf))
        self.n_docs = len(self.docs)
        self.avgdl = (
            sum(len(v) for v in self.doc_tokens.values()) / self.n_docs
            if self.n_docs
            else 1.0
        )

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log((self.n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def bm25(self, terms: list[str], doc_id: str, k1: float = 1.5, b: float = 0.75) -> float:
        tf = self.doc_tf[doc_id]
        dl = len(self.doc_tokens[doc_id])
        score = 0.0
        hits = 0
        for term in terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            hits += 1
            denom = freq + k1 * (1 - b + b * dl / self.avgdl)
            score += self.idf(term) * (freq * (k1 + 1)) / denom
        if hits < min(2, len(set(terms)) or 1):
            return 0.0
        return score

    def coverage(self, terms: list[str], doc_id: str) -> float:
        if not terms:
            return 0.0
        uniq = list(dict.fromkeys(terms))
        have = sum(1 for t in uniq if t in self.doc_tf[doc_id])
        return have / len(uniq)

    def search_bm25(self, terms: list[str], k: int = 10) -> list[tuple[str, float]]:
        scored = []
        for doc_id in self.docs:
            s = self.bm25(terms, doc_id)
            if s > 0:
                scored.append((doc_id, s))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]

    def search_boolean(self, terms: list[str], k: int = 10) -> list[tuple[str, float]]:
        """Independent ranker: subject coverage, then cue overlap."""
        scored = []
        uniq = [t for t in dict.fromkeys(terms) if t]
        if not uniq:
            return []
        for doc_id in self.docs:
            cov = self.coverage(uniq, doc_id)
            if cov < 0.5:
                continue
            scored.append((doc_id, cov))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]


_CORPUS: Corpus | None = None


def get_corpus() -> Corpus:
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = Corpus()
    return _CORPUS
