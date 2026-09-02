"""Independent reviewer rank: list index, not the author RANK dict."""
from __future__ import annotations

from typing import Iterable

# Index is severity rank. Mechanically different from severity.RANK.
ORDER = ("P3", "P2", "P1", "P0")


class ReviewerUnknownSeverity(ValueError):
    pass


def reviewer_rank(token: object) -> int:
    if not isinstance(token, str):
        raise ReviewerUnknownSeverity(f"reviewer unknown token {token!r}")
    key = token.strip().upper()
    try:
        return ORDER.index(key)
    except ValueError as exc:
        raise ReviewerUnknownSeverity(
            f"reviewer unknown token {token!r}; not in {ORDER}"
        ) from exc


def reviewer_max(tokens: Iterable[str]) -> str | None:
    best_rank = -1
    best: str | None = None
    for raw in tokens:
        rank = reviewer_rank(raw)
        if rank > best_rank:
            best_rank = rank
            best = ORDER[rank]
    return best


def reviewer_delta(recorded: str, max_child: str | None) -> int:
    if max_child is None:
        return 0
    rec = reviewer_rank(recorded)
    child = reviewer_rank(max_child)
    return max(0, child - rec)
