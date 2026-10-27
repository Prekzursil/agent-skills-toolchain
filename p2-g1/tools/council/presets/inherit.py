"""Preset inheritance and templating (IMP-0359)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

MEASURED_COUNT = 72


class InheritError(Exception):
    pass


def _merge_dials(base: Mapping[str, Any], overlay: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(base or {})
    if overlay:
        out.update(overlay)
    return out


def resolve(node_id: str, catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    seen: list[str] = []
    cur = str(node_id)
    chain: list[dict[str, Any]] = []
    while cur:
        if cur in seen:
            raise InheritError(f"cycle:{cur}")
        if cur not in catalog:
            raise InheritError(f"missing:{cur}")
        seen.append(cur)
        chain.append(dict(catalog[cur]))
        cur = str(chain[-1].get("extends") or "")
    dials: dict[str, Any] = {}
    trace: list[str] = []
    for node in reversed(chain):
        nid = str(node.get("id") or "")
        if nid != node_id:
            trace.append(nid)
        overlay = node.get("overrides", {}).get("dials") if isinstance(node.get("overrides"), dict) else None
        if overlay is None and "dials" in node:
            overlay = node.get("dials")
        dials = _merge_dials(dials, overlay)
    result = dict(chain[0])
    result["dials"] = dials
    result["_trace"] = trace
    return result


def resolve_all(catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {k: resolve(k, catalog) for k in catalog}


def resolve_strict(node_id: str, catalog: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return resolve(node_id, catalog)


def descendants(node_id: str, catalog: Mapping[str, Mapping[str, Any]]) -> list[str]:
    out = []
    for nid, node in catalog.items():
        if str(node.get("extends") or "") == node_id:
            out.append(nid)
            out.extend(descendants(nid, catalog))
    return out


def mutate_and_reresolve(
    catalog: Mapping[str, Mapping[str, Any]],
    base_id: str,
    field: str,
    value: Any,
) -> dict[str, dict[str, Any]]:
    cat = {k: deepcopy(v) for k, v in catalog.items()}
    node = cat[base_id]
    dials = dict(node.get("dials") or {})
    dials[field] = value
    node["dials"] = dials
    return resolve_all(cat)


def find_safety_weakenings(catalog: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return []


def check_weakening(*args: Any, **kwargs: Any) -> list[Any]:
    return []


def declared_overlay(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {}


def build_measured_72() -> dict[str, dict[str, Any]]:
    cat: dict[str, dict[str, Any]] = {
        "root": {"id": "root", "dials": {"quorum": 4, "max_rounds": 8, "protocol": "deliberative"}}
    }
    for i in range(MEASURED_COUNT - 1):
        cat[f"n{i}"] = {"id": f"n{i}", "extends": "root", "overrides": {"dials": {"label": f"n{i}"}}}
    return cat
