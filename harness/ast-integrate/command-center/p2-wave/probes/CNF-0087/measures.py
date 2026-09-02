#!/usr/bin/env python3
"""Two mechanically different uniqueness measures for CNF-0087.

Council-own (reconstructed): normalized string identity. A missing
tools/council/quota/unique_ideas.py that counted distinct strings would
treat trivial wording variants as unique. Family: lexical-identity.

Independent recount: canonical mechanism-key = sorted unique stemmed
content tokens after stopword removal. Family: canonical-mechanism-key.

These are not the same instrument re-run: identity vs extracted key.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "for",
        "in",
        "on",
        "at",
        "by",
        "from",
        "with",
        "plus",
        "is",
        "are",
        "be",
        "been",
        "being",
        "was",
        "were",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "as",
        "each",
        "every",
        "get",
        "gets",
        "got",
        "into",
        "via",
        "using",
        "use",
        "used",
        "so",
        "its",
        "own",
        "may",
        "any",
        "not",
        "than",
        "rather",
    }
)

COUNCIL_MEASURE = {
    "id": "council-normalized-string-identity",
    "name": "council string-identity unique count",
    "method": (
        "Unicode NFKC, casefold, collapse whitespace, then count distinct "
        "normalized strings. No stemming, no stopword drop, no key extract."
    ),
    "mechanical_family": "lexical-identity",
    "threshold": "exact-after-whitespace-casefold",
    "role": "council-own",
}

RECOUNT_MEASURE = {
    "id": "independent-canonical-mechanism-key",
    "name": "independent mechanism-key recount",
    "method": (
        "Tokenize on non-letters, drop stopwords, apply suffix stemming, "
        "sort unique remaining tokens into a canonical mechanism key, "
        "cluster by exact key equality."
    ),
    "mechanical_family": "canonical-mechanism-key",
    "threshold": "exact-key-equality",
    "role": "independent-recount",
}


def _stem(word: str) -> str:
    for suf in ("ing", "ers", "ies", "ied", "ed", "es", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            if suf == "ies":
                return word[:-3] + "y"
            return word[: -len(suf)]
    return word


def council_normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", folded).strip()


def content_tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z]+", unicodedata.normalize("NFKC", text).casefold())
    out: list[str] = []
    for tok in raw:
        if tok in STOP or len(tok) < 3:
            continue
        out.append(_stem(tok))
    return out


def mechanism_key(text: str) -> str:
    return " ".join(sorted(set(content_tokens(text))))


def council_unique(texts: list[str]) -> int:
    return len({council_normalize(t) for t in texts})


def cluster_by_mechanism(ideas: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for idea in ideas:
        buckets[mechanism_key(idea["text"])].append(idea)
    return dict(buckets)


def recount_unique(ideas: list[dict]) -> int:
    return len(cluster_by_mechanism(ideas))


def report_payload(doc: dict) -> dict:
    """Domain fields live under report (receipt additionalProperties is false)."""
    r = doc.get("report")
    if isinstance(r, dict) and (
        "planted_control" in r or "measures" in r or "target_verdict" in r
    ):
        return r
    return doc
