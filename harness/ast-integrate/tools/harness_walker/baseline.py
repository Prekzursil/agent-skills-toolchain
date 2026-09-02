"""Naive walkers used as both-states twins (TST-0335)."""
from __future__ import annotations

import os


def naive_walk_raise(root: str | os.PathLike[str]) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        for name in filenames + dirnames:
            path = os.path.join(dirpath, name)
            stem = os.path.splitext(name)[0].upper()
            if stem == "NUL" or name.upper() == "NUL":
                raise ValueError(rf"reserved device name \\.\NUL at {path}")
            found.append(path)
    return found


def naive_walk_crash_as_zero(root: str | os.PathLike[str]) -> dict:
    try:
        found = naive_walk_raise(root)
        return {"raised": False, "count": len(found), "paths": found}
    except Exception:
        return {"raised": True, "count": 0, "paths": []}


def naive_walk_silent_skip(root: str | os.PathLike[str]) -> list[str]:
    found = []
    try:
        for dirpath, dirnames, filenames in os.walk(str(root)):
            for name in filenames:
                stem = os.path.splitext(name)[0].upper()
                if stem in {"NUL", "CON", "AUX", "PRN"}:
                    continue
                found.append(os.path.join(dirpath, name))
    except Exception:
        return found
    return found


def naive_walk_follow_unlimited(root: str | os.PathLike[str], limit: int = 10000) -> list[str]:
    found = []
    n = 0
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=True):
        for name in filenames:
            found.append(os.path.join(dirpath, name))
            n += 1
            if n >= limit:
                return found
    return found
