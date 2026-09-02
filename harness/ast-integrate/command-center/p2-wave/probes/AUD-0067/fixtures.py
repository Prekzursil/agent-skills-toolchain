"""Control estate: two trees whose UNION is 29 but neither tree holds 29.

tree-a: first 17 contracted names.
tree-b: last 20 contracted names (index 9..28).
overlap: 8 names (index 9..16). One overlap is byte-divergent.
A union-only counter reports 29 for each tree; a per-tree counter cannot.
"""
from __future__ import annotations

from pathlib import Path

from common import CONTRACT_29, HERE, UNIT

ESTATE = HERE / "fixtures" / "estate"
TREE_A = ESTATE / "tree-a"
TREE_B = ESTATE / "tree-b"
TREE_A_COUNT = 17
TREE_B_START = 9
DIVERGENT_INDEX = 9


def materialize() -> dict:
    if len(CONTRACT_29) != 29:
        raise SystemExit(f"{UNIT} contract length {len(CONTRACT_29)} != 29")
    TREE_A.mkdir(parents=True, exist_ok=True)
    TREE_B.mkdir(parents=True, exist_ok=True)
    names_a = list(CONTRACT_29[:TREE_A_COUNT])
    names_b = list(CONTRACT_29[TREE_B_START:])
    overlap = [n for n in names_a if n in names_b]
    divergent_name = CONTRACT_29[DIVERGENT_INDEX]
    if divergent_name not in overlap:
        raise SystemExit(f"{UNIT} divergent name not in overlap")
    overlap_set = set(overlap)
    for name in names_a:
        if name == divergent_name:
            payload = f"{UNIT}-control DIVERGENT-A name={name}\n"
        elif name in overlap_set:
            payload = f"{UNIT}-control IDENTICAL-OVERLAP name={name}\n"
        else:
            payload = f"{UNIT}-control tree=a name={name}\n"
        (TREE_A / name).write_text(payload, encoding="utf-8")
    for name in names_b:
        if name == divergent_name:
            payload = f"{UNIT}-control DIVERGENT-B name={name}\n"
        elif name in overlap_set:
            payload = f"{UNIT}-control IDENTICAL-OVERLAP name={name}\n"
        else:
            payload = f"{UNIT}-control tree=b name={name}\n"
        (TREE_B / name).write_text(payload, encoding="utf-8")
    union = sorted(set(names_a) | set(names_b))
    if len(names_a) != 17 or len(names_b) != 20 or len(union) != 29:
        raise SystemExit(
            f"{UNIT} fixture cardinality a={len(names_a)} b={len(names_b)} "
            f"union={len(union)}"
        )
    identical_overlap = [n for n in overlap if n != divergent_name]
    return {
        "tree_a": str(TREE_A),
        "tree_b": str(TREE_B),
        "count_a": len(names_a),
        "count_b": len(names_b),
        "union_count": len(union),
        "overlap_count": len(overlap),
        "divergent_name": divergent_name,
        "identical_overlap_count": len(identical_overlap),
        "names_a": names_a,
        "names_b": names_b,
    }
