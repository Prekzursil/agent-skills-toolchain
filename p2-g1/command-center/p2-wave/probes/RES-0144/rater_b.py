"""Rater B: content n-gram. Body markers + pairwise 5-gram Jaccard.

URL, host, and gold labels are sealed. Vendor-role analog:
anthropic-mechanical-content-ngram.
"""
from __future__ import annotations

import re
from typing import Any

from rubric import AUTHORITY_LEVELS, INDEPENDENCE_LEVELS, LOW_INDEPENDENCE

TOKEN_RE = re.compile(r"[a-z0-9]+")
MEASURE_RE = re.compile(
    r"\b(i|we) (measured|reproduced|observed|timed|ran|added|changed|shipped)\b",
    re.I,
)
CITE_RE = re.compile(
    r"\b(according to|as reported by|sources say|as explained in)\b",
    re.I,
)
TOPIC_WORDS = (
    "gil",
    "hashlib",
    "sha256",
    "json",
    "rfc2119",
    "rfc8259",
    "pep8",
    "pep",
    "spdx",
    "mit",
    "iana",
    "requests",
    "urllib",
    "numpy",
    "pip",
)


def tokens(body: str) -> list[str]:
    return TOKEN_RE.findall(body.lower())


def ngrams(body: str, n: int = 5) -> set[tuple[str, ...]]:
    toks = tokens(body)
    if len(toks) < n:
        return set((t,) for t in toks)
    return set(tuple(toks[i : i + n]) for i in range(len(toks) - n + 1))


def jaccard5(a: str, b: str) -> float:
    sa, sb = ngrams(a, 5), ngrams(b, 5)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def topics(body: str) -> set[str]:
    toks = set(tokens(body))
    hit = {w for w in TOPIC_WORDS if w in toks}
    if "rfc" in toks and "2119" in toks:
        hit.add("rfc2119")
    if "rfc" in toks and "8259" in toks:
        hit.add("rfc8259")
    if "pep" in toks and "8" in toks:
        hit.add("pep8")
    return hit


def authority_from_body(body: str) -> tuple[str, str]:
    if (
        "Status of This Memo" in body
        or "Request for Comments:" in body
        or "This memo provides information" in body
    ):
        return "PRIMARY", "rfc-boilerplate"
    if re.search(r"^PEP:\s*\d+", body, re.M) or "PEP-Counter" in body:
        return "PRIMARY", "pep-header"
    if "Permission is hereby granted, free of charge" in body and "THE SOFTWARE IS PROVIDED" in body:
        return "PRIMARY", "license-text"
    if "$schema" in body and "json-schema.org" in body:
        return "PRIMARY", "json-schema-spec"
    if "IANA" in body and "media type" in body.lower():
        return "PRIMARY", "iana-media-type"
    if "CPython Lib/" in body or re.search(r"^#.*CPython", body, re.M):
        return "PRIMARY", "implementing-source"
    if MEASURE_RE.search(body):
        return "PRACTITIONER", "first-person-engineering-voice"
    if (
        "This document is part of the official" in body
        or "Contributing to" in body
        or "official Python documentation" in body
        or "user guide" in body.lower()
        or "library reference" in body.lower()
    ):
        return "MAINTAINER", "official-docs-voice"
    if CITE_RE.search(body):
        return "RETELLER", "citation-voice"
    return "RETELLER", "fail-closed"


def score_one(src: dict[str, Any], corpus: list[dict[str, Any]]) -> dict[str, Any]:
    body = str(src.get("body") or "")
    leaked = [k for k in src.keys() if k in {"gold_authority", "gold_independence", "expected", "label"}]
    # URL is present on the row but must not be consulted.
    authority, a_why = authority_from_body(body)
    pairs: list[tuple[str, float]] = []
    for other in corpus:
        if other.get("id") == src.get("id"):
            continue
        pairs.append((str(other.get("id")), jaccard5(body, str(other.get("body") or ""))))
    pairs.sort(key=lambda x: x[1], reverse=True)
    best_id, best = pairs[0] if pairs else ("", 0.0)
    own_topics = topics(body)
    measure = bool(MEASURE_RE.search(body))
    if best >= 0.90:
        independence = "SYNDICATED"
        why = f"jaccard5={best:.4f} twin={best_id} threshold=0.90"
    elif best >= 0.22:
        independence = "DERIVED"
        why = f"jaccard5={best:.4f} twin={best_id} paraphrase-or-quote"
    elif measure:
        peers = []
        for other in corpus:
            if other.get("id") == src.get("id"):
                continue
            ob = str(other.get("body") or "")
            if not MEASURE_RE.search(ob):
                continue
            shared = own_topics & topics(ob)
            jac = jaccard5(body, ob)
            if len(shared) >= 1 and 0.02 <= jac < 0.22:
                peers.append(other["id"])
        if peers:
            independence = "PARALLEL"
            why = f"measurement-voice shared-topic peers={peers}"
        else:
            independence = "ORIGINATING"
            why = "measurement-voice unique-ngrams"
    elif CITE_RE.search(body):
        independence = "DERIVED"
        why = "citation-voice without high n-gram overlap"
    else:
        independence = "ORIGINATING"
        why = "unique-ngrams no-citation"
    return {
        "id": src.get("id"),
        "rater": "B",
        "vendor_role": "anthropic-mechanical-content-ngram",
        "authority": authority,
        "authority_why": a_why,
        "independence": independence,
        "low_independence": independence in LOW_INDEPENDENCE,
        "why": why,
        "best_twin": best_id,
        "best_jaccard5": round(best, 6),
        "topics": sorted(own_topics),
        "forbidden_keys_seen": leaked,
        "features_used": ["body"],
        "url_consulted": False,
        "axis_vocab": {"authority": list(AUTHORITY_LEVELS), "independence": list(INDEPENDENCE_LEVELS)},
    }


def score_all(corpus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [score_one(src, corpus) for src in corpus]
