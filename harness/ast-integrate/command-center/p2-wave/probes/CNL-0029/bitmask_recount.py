"""Independent recount of the same-seat matrix via capability bitmasks.

This is a different mechanism from solver.py set-overlap: each
(capability, kind) pair is a bit, two roles are OR-merged, then the
author-kind bits are AND-ed against the OR of judge/vote/veto kind bits.
A disagreement in the resulting count blocks CNL-0029.
"""
from __future__ import annotations

from typing import Any

CAP_ORDER = ("author", "judge", "vote", "veto", "chair")
ADJUDICATE = ("judge", "vote", "veto")


def kind_index(library: dict[str, Any]) -> list[str]:
    kinds = library.get("artifact_kinds") or []
    if not isinstance(kinds, list) or not kinds:
        raise ValueError("artifact_kinds missing")
    return [str(k) for k in kinds]


def role_mask(role: dict[str, Any], kinds: list[str]) -> int:
    n = len(kinds)
    mask = 0
    kind_pos = {k: i for i, k in enumerate(kinds)}
    for ci, cap in enumerate(CAP_ORDER):
        for kind in role.get(cap) or []:
            if kind not in kind_pos:
                raise ValueError(f"unknown kind {kind!r}")
            mask |= 1 << (ci * n + kind_pos[kind])
    return mask


def author_kinds(mask: int, n: int) -> int:
    return mask & ((1 << n) - 1)


def adjudicate_kinds(mask: int, n: int) -> int:
    bits = 0
    for cap in ADJUDICATE:
        ci = CAP_ORDER.index(cap)
        bits |= (mask >> (ci * n)) & ((1 << n) - 1)
    return bits


def pair_incompatible(mask_a: int, mask_b: int, n: int) -> bool:
    merged = mask_a | mask_b
    return (author_kinds(merged, n) & adjudicate_kinds(merged, n)) != 0


def recount(library: dict[str, Any]) -> dict[str, Any]:
    kinds = kind_index(library)
    n = len(kinds)
    templates = library.get("templates") or {}
    names = sorted(templates)
    masks = {name: role_mask(templates[name], kinds) for name in names}
    rows = []
    unordered: dict[tuple[str, str], bool] = {}
    for a in names:
        for b in names:
            inc = pair_incompatible(masks[a], masks[b], n)
            rows.append({"a": a, "b": b, "incompatible": inc})
            key = tuple(sorted([a, b]))
            unordered[key] = unordered.get(key, False) or inc
    unordered_inc = sorted(["+".join(k) for k, v in unordered.items() if v])
    inc_ordered = sum(1 for r in rows if r["incompatible"])
    return {
        "mechanism": "bitmask-OR-then-AND",
        "template_count": len(names),
        "ordered_pair_count": len(rows),
        "incompatible_ordered": inc_ordered,
        "compatible_ordered": len(rows) - inc_ordered,
        "incompatible_unordered": unordered_inc,
        "incompatible_unordered_count": len(unordered_inc),
        "rows": rows,
        "names": names,
        "kind_width": n,
    }
