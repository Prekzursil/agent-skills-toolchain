"""Structure fingerprint independent of identifiers/prose."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canon(blueprint: dict[str, Any]) -> dict[str, Any]:
    wf = dict(blueprint.get("workflow") or {})
    stages = []
    for s in wf.get("stages") or []:
        stages.append(
            {
                "kind": s.get("kind") or s.get("type") or "",
                "params": s.get("params") or s.get("declared") or {},
            }
        )
    edges = []
    for e in wf.get("edges") or []:
        if isinstance(e, (list, tuple)) and len(e) == 2:
            edges.append(["SRC", "DST"])
        elif isinstance(e, dict):
            edges.append(["SRC", "DST"])
    return {
        "declared_parameters": dict(blueprint.get("declared_parameters") or {}),
        "n_stages": len(stages),
        "stage_kinds": [s["kind"] for s in stages],
        "n_edges": len(edges),
        "stopping_mechanism": (blueprint.get("stopping_rules") or {}).get("mechanism")
        or (blueprint.get("stopping_rules") or {}).get("kind")
        or "documented",
        "tier": blueprint.get("tier"),
    }


def fingerprint(blueprint: dict[str, Any]) -> str:
    blob = json.dumps(_canon(blueprint), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def parameter_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    pa = dict(a.get("declared_parameters") or {})
    pb = dict(b.get("declared_parameters") or {})
    keys = sorted(set(pa) | set(pb))
    changed = {k: {"a": pa.get(k), "b": pb.get(k)} for k in keys if pa.get(k) != pb.get(k)}
    return {"changed": changed, "n": len(changed), "nonempty": bool(changed)}
