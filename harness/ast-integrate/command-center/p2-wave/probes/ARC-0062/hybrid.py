"""A9 hybrid entry paths: every borrowed surface crosses ONE evaluator.

Plane-local checks (signature, budget, never-forward, typed validate) are
non-granting. Only permission_evaluator may emit a grant. Borrowing A3/A4/A6
arrival must not substitute those checks for the A7 choke.
"""
from __future__ import annotations

from typing import Any

from sources import live_interface_paths, source_dossier_paths

# The single permission choke. Every capability entry path must include this hop.
SINGLE_EVALUATOR_NODE = "permission_evaluator"

ARRIVAL_NODE = {
    "marketplace": "arrival_marketplace",
    "gateway": "arrival_gateway",
    "adapter": "arrival_adapter",
    "a7": "arrival_a7",
    "a1_config": "arrival_a1_config",
    "a2_generate": "arrival_a2_generate",
    "a5_ledger": "arrival_a5_ledger",
}

# Hops that would be a second grant authority if they appeared.
FORBIDDEN_GRANT_NODES = frozenset(
    {
        "marketplace_acl",
        "gateway_grant",
        "adapter_permission_grant",
        "local_acl",
        "signature_grant",
        "config_wildcard_grant",
    }
)


def gated_hops(spec: dict[str, Any]) -> list[str]:
    arrival = ARRIVAL_NODE[str(spec["arrival"])]
    checks = [str(c) for c in (spec.get("plane_checks") or [])]
    effect = str(spec["effect"])
    return [arrival, *checks, SINGLE_EVALUATOR_NODE, effect]


def _compose_row(spec: dict[str, Any]) -> dict[str, Any]:
    hops = gated_hops(spec)
    return {
        "id": spec["id"],
        "source_architecture": spec["source_architecture"],
        "source_unit": spec["source_unit"],
        "epoch": spec["epoch"],
        "arrival": spec["arrival"],
        "effect": spec["effect"],
        "plane_checks": list(spec.get("plane_checks") or []),
        "hops": hops,
        "crosses_single_evaluator": SINGLE_EVALUATOR_NODE in hops,
        "binding": spec.get("binding"),
    }


def hybrid_paths() -> list[dict[str, Any]]:
    """Union of catalog-bound source paths and live A1/A2/A5 interfaces."""
    rows = [_compose_row(s) for s in source_dossier_paths()]
    seen = {r["id"] for r in rows}
    for spec in live_interface_paths():
        if spec["id"] in seen:
            continue
        rows.append(_compose_row(spec))
        seen.add(spec["id"])
    rows.sort(key=lambda r: r["id"])
    return rows


def hybrid_ids() -> list[str]:
    return [r["id"] for r in hybrid_paths()]


def drop_path(paths: list[dict[str, Any]], path_id: str) -> list[dict[str, Any]]:
    out = [dict(r) for r in paths if r["id"] != path_id]
    if len(out) == len(paths):
        raise RuntimeError(f"drop-missing:{path_id}")
    return out
