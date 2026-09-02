"""Dispatch surface for product blueprints 1-4."""
from __future__ import annotations

from typing import Any, Mapping

from product_blueprints.discovery import discover
from product_blueprints.prioritize import RankingRefusal, rank
from product_blueprints.registry import BLUEPRINT_IDS, list_blueprints
from product_blueprints.requirements import reconcile
from product_blueprints.synthesis import synthesise


def run_blueprint(blueprint_id: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(payload or {})
    if blueprint_id == "requirements-mining-reconciliation":
        result = reconcile(
            str(payload.get("baseline_text") or ""),
            str(payload.get("revision_text") or ""),
        )
        result["id"] = blueprint_id
        return result
    if blueprint_id == "roadmap-prioritization":
        result = rank(payload)
        result["id"] = blueprint_id
        return result
    if blueprint_id == "product-discovery":
        result = discover(payload)
        result["id"] = blueprint_id
        return result
    if blueprint_id == "user-research-synthesis":
        result = synthesise(payload)
        result["id"] = blueprint_id
        return result
    raise KeyError(blueprint_id)


def smoke_all() -> dict[str, Any]:
    rows = []
    ok = True
    for rec in list_blueprints():
        if rec.id == "requirements-mining-reconciliation":
            out = run_blueprint(
                rec.id,
                {
                    "baseline_text": "REQ-A-01: keep\n",
                    "revision_text": "REQ-A-01: keep\n",
                },
            )
        elif rec.id == "roadmap-prioritization":
            out = run_blueprint(
                rec.id,
                {
                    "weights": {
                        "reach": 1,
                        "impact": 1,
                        "confidence": 1,
                        "effort": 1,
                    },
                    "items": [
                        {
                            "id": "a",
                            "reach": 1,
                            "impact": 1,
                            "confidence": 50,
                            "effort": 1,
                        }
                    ],
                },
            )
        else:
            out = run_blueprint(rec.id, {})
        passed = bool(out)
        rows.append({"id": rec.id, "pass": passed, "workflow_id": rec.workflow["id"]})
        ok = ok and passed
    return {
        "pass": ok and [r["id"] for r in rows] == list(BLUEPRINT_IDS),
        "rows": rows,
    }
