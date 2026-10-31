"""Casefold collision detector for DAG keys (IMP-0162)."""
from __future__ import annotations

from typing import Iterable


def would_casefold_collide(keys: Iterable[str]) -> bool:
    items = [str(k) for k in keys]
    folded = {k.casefold() for k in items}
    return len(folded) < len(items)
