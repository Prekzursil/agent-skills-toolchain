"""Semantic differ over two WorkflowIRs, plus the duplicate score it implies.

Dimensions are stages, roles, gates, tools and stop_rules. Comparison is
set-valued (order-insensitive). ABSENT is distinct from PRESENT-BUT-DIFFERENT.
Prose fields are ignored, so a reworded paraphrase of name/description is
structurally identical.

Duplicate score is Jaccard over the tagged union of all five dimension
item sets. Declared threshold is versioned; probes re-run this module live
whenever the file bytes or the threshold constant change.
"""
from __future__ import annotations

import copy
import hashlib
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from ir import DIMENSIONS  # noqa: E402

THRESHOLD = 0.72
THRESHOLD_VERSION = "wfa-0096-threshold-v1"
DIFFER_ID = "wfa-0096-structural-jaccard-v1"
INDEPENDENT_EXCLUSIVE_MAX = 2


def dim_items(ir: dict[str, Any], dim: str) -> frozenset[str]:
    rows = ir.get(dim) or []
    items: set[str] = set()
    if not isinstance(rows, list):
        return frozenset()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if dim == "roles":
            token = str(row.get("token") or "").strip()
            vendor = str(row.get("vendor") or "").strip()
            if token:
                items.add(f"{dim}:role:{token}")
            if vendor:
                items.add(f"{dim}:vendor:{vendor}")
            continue
        token = str(row.get("token") or "").strip()
        if token:
            items.add(f"{dim}:{token}")
    return frozenset(items)


def all_items(ir: dict[str, Any]) -> frozenset[str]:
    out: set[str] = set()
    for dim in DIMENSIONS:
        out |= set(dim_items(ir, dim))
    return frozenset(out)


def classify_sets(left: frozenset[str], right: frozenset[str]) -> str:
    if left == right:
        return "IDENTICAL"
    if not left and right:
        return "ABSENT-LEFT"
    if left and not right:
        return "ABSENT-RIGHT"
    return "PRESENT-BUT-DIFFERENT"


def semantic_diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    dims: dict[str, Any] = {}
    for dim in DIMENSIONS:
        a = dim_items(left, dim)
        b = dim_items(right, dim)
        only_a = sorted(a - b)
        only_b = sorted(b - a)
        dims[dim] = {
            "kind": classify_sets(a, b),
            "left_only": only_a,
            "right_only": only_b,
            "shared_count": len(a & b),
            "left_count": len(a),
            "right_count": len(b),
        }
    return {
        "left_id": left.get("id"),
        "right_id": right.get("id"),
        "dimensions": dims,
        "self_diff_empty": all(row["kind"] == "IDENTICAL" for row in dims.values()),
    }


def jaccard(left: dict[str, Any], right: dict[str, Any]) -> float:
    a = all_items(left)
    b = all_items(right)
    if not a and not b:
        return 1.0
    union = len(a | b)
    if union == 0:
        return 1.0
    return len(a & b) / union


def exclusive_total(left: dict[str, Any], right: dict[str, Any]) -> int:
    """Independent of Jaccard: raw exclusive-item cardinality across five dims."""
    n = 0
    for dim in DIMENSIONS:
        a = dim_items(left, dim)
        b = dim_items(right, dim)
        n += len(a - b) + len(b - a)
    return n


def is_duplicate(score: float, threshold: float = THRESHOLD) -> bool:
    return score >= threshold


def independent_is_duplicate(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """Mechanically independent of Jaccard: exclusive cardinality <= fork budget."""
    return exclusive_total(left, right) <= INDEPENDENT_EXCLUSIVE_MAX


def nearest_neighbors(
    plant: dict[str, Any],
    corpus: list[dict[str, Any]],
    *,
    score_fn=jaccard,
) -> list[tuple[str, float]]:
    ranked: list[tuple[str, float]] = []
    pid = plant.get("id")
    for other in corpus:
        oid = other.get("id")
        if oid == pid:
            continue
        ranked.append((str(oid), float(score_fn(plant, other))))
    ranked.sort(key=lambda row: (-row[1], row[0]))
    return ranked


def self_diff_failures(corpus: list[dict[str, Any]]) -> list[str]:
    bad: list[str] = []
    for ir in corpus:
        diff = semantic_diff(ir, ir)
        if not diff["self_diff_empty"]:
            bad.append(str(ir.get("id")))
    return bad


def absent_versus_different_fixture() -> dict[str, Any]:
    """Both-states fixture: missing tools vs rewritten tools must not collapse."""
    base = {
        "id": "fixture-left",
        "stages": [{"id": "s", "token": "shared-stage"}],
        "roles": [{"id": "r", "token": "shared-role", "vendor": "v"}],
        "gates": [{"id": "g", "token": "shared-gate"}],
        "tools": [{"id": "t", "token": "read"}],
        "stop_rules": [{"id": "st", "token": "timeout:1"}],
    }
    absent = copy.deepcopy(base)
    absent["id"] = "fixture-absent-tools"
    absent["tools"] = []
    different = copy.deepcopy(base)
    different["id"] = "fixture-different-tools"
    different["tools"] = [{"id": "t", "token": "write"}]
    k_abs = semantic_diff(base, absent)["dimensions"]["tools"]["kind"]
    k_diff = semantic_diff(base, different)["dimensions"]["tools"]["kind"]
    return {
        "absent_kind": k_abs,
        "different_kind": k_diff,
        "distinguished": k_abs != k_diff
        and k_abs.startswith("ABSENT")
        and k_diff == "PRESENT-BUT-DIFFERENT",
    }


def module_fingerprint(path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()
