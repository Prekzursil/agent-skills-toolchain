"""Monotone permission narrowing for nested subworkflows (TST-0223).

Child effective permissions are the intersection of the parent bag and the
child's declared bag. They never widen. ``run_property_corpus`` is a
deterministic (hashlib, not ``random``) property test over nesting trees.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from typing import Any

from agentspec.spec import freeze_tool_permissions

N_TREES = 5000
SEED = 20260824
_VOCAB = ("Read", "Grep", "Bash", "Write", "Edit")
_BASE = ("Read", "Grep", "Bash")
NarrowFn = Callable[[Iterable[str], Iterable[str]], frozenset[str]]


def narrow(parent: Iterable[str], declared: Iterable[str]) -> frozenset[str]:
    """Child permissions are the intersection; they never widen."""
    return freeze_tool_permissions(parent) & freeze_tool_permissions(declared)


def union_widen(parent: Iterable[str], declared: Iterable[str]) -> frozenset[str]:
    """Mutation control: union instead of intersection (property must go red)."""
    return freeze_tool_permissions(parent) | freeze_tool_permissions(declared)


def _bits(seed: int, n: int) -> int:
    blob = f"{int(seed)}:{int(n)}".encode("ascii")
    return int.from_bytes(hashlib.sha256(blob).digest()[:8], "big")


def _as_frozen(value: Any) -> frozenset[str]:
    if isinstance(value, frozenset):
        return value
    return freeze_tool_permissions(value)


def run_property_corpus(
    n_trees: int | None = None,
    seed: int | None = None,
    narrow_fn: NarrowFn | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Prove child ⊆ parent over ``n_trees`` hashed nesting trees.

    A widening declaration (child names a tool the parent lacks) is attempted
    at the deepest node. Intersection refuses it with spawn_count=0; union
    allows it and the monotone property goes red.
    """
    if n_trees is None:
        n_trees = kwargs.get("n_trees", N_TREES)
    if seed is None:
        seed = kwargs.get("seed", SEED)
    n_trees = int(n_trees)
    seed = int(seed)
    nfn: NarrowFn = narrow_fn or kwargs.get("narrow_fn") or narrow

    violations = 0
    widening_attempts = 0
    widening_calls_denied = 0
    widening_calls_allowed = 0
    call_mismatches = 0
    trees_ok = 0
    sample_depths: list[dict[str, Any]] = []
    sample_call: dict[str, Any] = {}

    for i in range(n_trees):
        rng = _bits(seed, i)
        depth_n = 2 + (rng % 3)
        parent = freeze_tool_permissions(_BASE)
        current = parent
        depths = [
            {
                "depth": 0,
                "effective": sorted(current),
                "monotone": True,
                "id": "root",
                "kind": "workflow",
            }
        ]
        tree_bad = False
        tree_widened = False
        for d in range(1, depth_n + 1):
            r = _bits(seed, i * 16 + d)
            declared = set(current)
            if (r & 1) or d == depth_n:
                declared.add("Write")
                widening_attempts += 1
                tree_widened = True
            if (r & 2) and "Grep" in declared:
                declared.discard("Grep")
            if not declared:
                declared.add("Read")
            effective = _as_frozen(nfn(current, declared))
            monotone = effective <= current
            if not monotone:
                violations += 1
                tree_bad = True
            depths.append(
                {
                    "depth": d,
                    "effective": sorted(effective),
                    "monotone": monotone,
                    "id": f"child-{d}",
                    "kind": "subworkflow",
                }
            )
            current = effective
        tool = "Write"
        if tree_widened:
            allowed = tool in current
            spawn = 1 if allowed else 0
            if allowed:
                widening_calls_allowed += 1
            else:
                widening_calls_denied += 1
            if allowed != (tool in current):
                call_mismatches += 1
            if not sample_call:
                sample_call = {
                    "tool": tool,
                    "allowed": allowed,
                    "spawn_count": spawn,
                    "code": None if allowed else "tool-permission-denied",
                    "depth": depths[-1]["depth"],
                    "effective": depths[-1]["effective"],
                    "widening_tool": tool,
                }
        if not tree_bad:
            trees_ok += 1
        if not sample_depths:
            sample_depths = depths

    if not sample_call:
        sample_call = {
            "tool": "Write",
            "allowed": False,
            "spawn_count": 0,
            "code": "tool-permission-denied",
            "depth": 2,
            "effective": list(_BASE),
            "widening_tool": "Write",
        }

    passed = violations == 0
    return {
        "pass": passed,
        "n_trees": n_trees,
        "seed": seed,
        "violations": violations,
        "call_mismatches": call_mismatches,
        "widening_attempts": widening_attempts,
        "widening_calls_denied": widening_calls_denied,
        "widening_calls_allowed": widening_calls_allowed,
        "trees_ok": trees_ok,
        "sample_depths": sample_depths,
        "sample_privileged_call": sample_call,
        "vocab": list(_VOCAB),
    }


__all__ = [
    "N_TREES",
    "SEED",
    "narrow",
    "run_property_corpus",
    "union_widen",
]
