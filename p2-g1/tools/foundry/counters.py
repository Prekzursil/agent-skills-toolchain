"""Process-local engine counters (IMP-0254)."""
from __future__ import annotations

_COUNTS: dict[str, int] = {}


def reset() -> None:
    _COUNTS.clear()


def inc(name: str, n: int = 1) -> int:
    _COUNTS[name] = int(_COUNTS.get(name) or 0) + n
    return _COUNTS[name]


def get(name: str) -> int:
    return int(_COUNTS.get(name) or 0)


def snapshot() -> dict[str, int]:
    return dict(_COUNTS)
