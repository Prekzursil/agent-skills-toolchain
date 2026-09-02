"""Closed severity vocabulary. Unknown tokens fail; they never default low."""
from __future__ import annotations

from typing import Iterable

VOCAB = ("P0", "P1", "P2", "P3")
# Higher rank = more severe. Author engine uses a dict, not a list scan.
RANK = {"P0": 3, "P1": 2, "P2": 1, "P3": 0}
TOKEN_FOR_RANK = {3: "P0", 2: "P1", 1: "P2", 0: "P3"}


class UnknownSeverityError(ValueError):
    """Raised when a token is outside the closed P0..P3 vocabulary."""


def parse_severity(token: object) -> str:
    if not isinstance(token, str):
        raise UnknownSeverityError(
            f"unknown severity token {token!r} (type {type(token).__name__}); "
            f"closed vocabulary is {VOCAB} and never defaults to low"
        )
    stripped = token.strip()
    if not stripped:
        raise UnknownSeverityError(
            "unknown severity token ''; closed vocabulary is "
            f"{VOCAB} and never defaults to low"
        )
    key = stripped.upper()
    if key not in RANK:
        raise UnknownSeverityError(
            f"unknown severity token {token!r}; closed vocabulary is {VOCAB} "
            "and never defaults to low"
        )
    return key


def more_severe(a: str, b: str) -> str:
    return a if RANK[parse_severity(a)] >= RANK[parse_severity(b)] else b


def max_token(tokens: Iterable[str]) -> str | None:
    best: str | None = None
    for raw in tokens:
        tok = parse_severity(raw)
        best = tok if best is None else more_severe(best, tok)
    return best


def nearest_mean_token(tokens: Iterable[str]) -> str | None:
    parsed = [parse_severity(t) for t in tokens]
    if not parsed:
        return None
    avg = sum(RANK[t] for t in parsed) / len(parsed)
    # Tie-break toward the more severe token so averaging cannot hide a P0.
    return min(VOCAB, key=lambda tok: (abs(RANK[tok] - avg), -RANK[tok]))
