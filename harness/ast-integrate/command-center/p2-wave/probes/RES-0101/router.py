"""Two mechanically different top-1 routers: TF-IDF cosine vs Jaccard tokens."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Callable, Iterable

from common import tokenize

Router = Callable[[str, list[dict[str, Any]]], str]


def _doc_text(tool: dict[str, Any], fields: Iterable[str]) -> str:
    parts = [str(tool.get(f) or "") for f in fields]
    return " ".join(parts)


def tfidf_select(query: str, catalog: list[dict[str, Any]]) -> str:
    """Signal A: sublinear TF-IDF cosine over name+description (name tokens boosted)."""
    q_tokens = tokenize(query)
    docs: list[list[str]] = []
    names: list[str] = []
    for tool in catalog:
        name = str(tool["name"])
        names.append(name)
        toks = tokenize(_doc_text(tool, ("name", "description")))
        toks.extend(tokenize(name) * 3)
        docs.append(toks)

    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))
    n_docs = len(docs)
    idf = {t: math.log((n_docs + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def vec(tokens: list[str]) -> dict[str, float]:
        tf = Counter(tokens)
        return {t: (1.0 + math.log(c)) * idf.get(t, 0.0) for t, c in tf.items()}

    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        keys = set(a) & set(b)
        dot = sum(a[k] * b[k] for k in keys)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    qv = vec(q_tokens)
    scored = [(cosine(qv, vec(doc)), name) for name, doc in zip(names, docs)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


def jaccard_select(query: str, catalog: list[dict[str, Any]]) -> str:
    """Signal B: Jaccard overlap on token sets (name+description, no TF and no name boost)."""
    q = set(tokenize(query))
    scored: list[tuple[float, str]] = []
    for tool in catalog:
        d = set(tokenize(_doc_text(tool, ("name", "description"))))
        union = q | d
        score = (len(q & d) / len(union)) if union else 0.0
        scored.append((score, str(tool["name"])))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1]


ROUTERS: dict[str, Router] = {
    "tfidf-cosine-nameboost": tfidf_select,
    "jaccard-description": jaccard_select,
}
