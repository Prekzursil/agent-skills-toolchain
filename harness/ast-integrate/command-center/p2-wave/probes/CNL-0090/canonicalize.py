"""Claim-text identity helpers for CNL-0090.

CNL-0051 is not delivered on this tree. This module is the local stand-in
the circling detector actually runs: two mechanically different text
signals plus structured claim_id identity in detector.py.

Scoped claim (NOT-CHECKED beyond this): a full rewrite that shares no
tokens and no character 4-grams. Lexical near-copies, hyphenation, and
compound splits are in scope.
"""
from __future__ import annotations

import re

STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "be",
        "by",
        "for",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "with",
        "when",
    }
)
TOKEN_DUP = 0.85
CHAR4_DUP = 0.35
CHAR_N = 4


def alnum_space(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def tokens(text: str) -> tuple[str, ...]:
    return tuple(t for t in alnum_space(text).split() if t and t not in STOP)


def token_set(text: str) -> set[str]:
    return set(tokens(text))


def char_ngrams(text: str, n: int = CHAR_N) -> set[str]:
    s = re.sub(r"[^a-z0-9]+", "", (text or "").lower())
    if not s:
        return set()
    if len(s) < n:
        return {s}
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def token_jaccard(left: str, right: str) -> float:
    return jaccard(token_set(left), token_set(right))


def char4_jaccard(left: str, right: str) -> float:
    return jaccard(char_ngrams(left), char_ngrams(right))


def is_duplicate_text(text: str, prior_texts: list[str]) -> dict:
    """True if token-Jaccard or char-4gram Jaccard hits a prior claim."""
    best_token = 0.0
    best_char4 = 0.0
    matched = None
    for prior in prior_texts:
        tj = token_jaccard(text, prior)
        cj = char4_jaccard(text, prior)
        if tj > best_token:
            best_token = tj
        if cj > best_char4:
            best_char4 = cj
        if tj >= TOKEN_DUP or cj >= CHAR4_DUP:
            matched = prior
            best_token = max(best_token, tj)
            best_char4 = max(best_char4, cj)
            break
    duplicate = matched is not None or (
        best_token >= TOKEN_DUP or best_char4 >= CHAR4_DUP
    )
    return {
        "duplicate": bool(duplicate),
        "token_jaccard": round(best_token, 4),
        "char4_jaccard": round(best_char4, 4),
        "token_threshold": TOKEN_DUP,
        "char4_threshold": CHAR4_DUP,
        "matched_prior": matched,
    }
