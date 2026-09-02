"""Mechanical set operations over vendor feature lists."""
from __future__ import annotations

from typing import Iterable


def as_sets(feature_lists: dict[str, Iterable[str]]) -> dict[str, set[str]]:
    return {k: set(v) for k, v in feature_lists.items()}


def intersection(feature_lists: dict[str, Iterable[str]]) -> list[str]:
    sets = as_sets(feature_lists)
    if not sets:
        return []
    acc: set[str] | None = None
    for s in sets.values():
        acc = s if acc is None else (acc & s)
    return sorted(acc or [])


def unique_sets(feature_lists: dict[str, Iterable[str]]) -> dict[str, list[str]]:
    sets = as_sets(feature_lists)
    out: dict[str, list[str]] = {}
    for name, s in sets.items():
        others: set[str] = set()
        for other, os_ in sets.items():
            if other != name:
                others |= os_
        out[name] = sorted(s - others)
    return out


def mutate_plant_into_all(
    feature_lists: dict[str, Iterable[str]], planted: str
) -> dict[str, list[str]]:
    """RED-state mutant: force a vendor-unique primitive into every list."""
    return {k: sorted(set(v) | {planted}) for k, v in feature_lists.items()}
