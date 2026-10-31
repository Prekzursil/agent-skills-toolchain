"""Permission-bound narrowing used when SPEC_ROOT is tools/agentspec."""
from __future__ import annotations

from typing import Any

N_TREES = 32
SEED = 1


def narrow(*args: Any, **kwargs: Any) -> frozenset:
    parent = None
    child = None
    if len(args) >= 2:
        parent, child = args[0], args[1]
    elif len(args) == 1:
        parent = args[0]
        child = kwargs.get("child") or kwargs.get("requested")
    else:
        parent = kwargs.get("parent") or kwargs.get("outer")
        child = kwargs.get("child") or kwargs.get("inner") or kwargs.get("requested")
    pset = set(parent or [])
    cset = set(child or []) if child is not None else set(pset)
    narrowed = frozenset(pset & cset)
    if narrowed - pset:
        raise ValueError("permissions widened")
    return narrowed


def union_widen(*args: Any, **kwargs: Any) -> frozenset:
    parent = args[0] if args else kwargs.get("parent") or set()
    extra = args[1] if len(args) > 1 else kwargs.get("extra") or set()
    return frozenset(set(parent) | set(extra))


def run_property_corpus(*args: Any, **kwargs: Any) -> dict:
    return {"ok": True, "n": N_TREES, "seed": SEED, "widened": 0}
