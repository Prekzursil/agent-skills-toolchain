#!/usr/bin/env python3
"""Drive a real downstream unit using ONLY the WFA-0126 handoff contract."""
from __future__ import annotations

import json
from typing import Any


class ConsumerError(ValueError):
    """Contract is not consumable by the named downstream unit."""


def _rows_by_id(contract: dict) -> dict[str, dict]:
    rows = contract.get("declared_artifacts")
    if not isinstance(rows, list) or not rows:
        raise ConsumerError("declared_artifacts missing or empty")
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("unit_id"):
            raise ConsumerError("declared_artifacts row missing unit_id")
        out[str(row["unit_id"])] = row
    return out


def _binding(contract: dict, unit_id: str) -> dict:
    bindings = contract.get("consumer_bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ConsumerError("consumer_bindings missing or empty")
    for item in bindings:
        if isinstance(item, dict) and item.get("unit_id") == unit_id:
            return item
    raise ConsumerError(f"no consumer binding for {unit_id}")


def _unknowns(contract: dict) -> dict[str, dict]:
    items = contract.get("residual_unknowns")
    if not isinstance(items, list) or not items:
        raise ConsumerError("residual_unknowns missing or empty")
    out: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise ConsumerError("residual unknown missing id")
        for key in ("settling_experiment", "owner_visible_impact"):
            if not str(item.get(key) or "").strip():
                raise ConsumerError(f"residual {item.get('id')} missing {key}")
        out[str(item["id"])] = item
    return out


def _did_not(contract: dict) -> list[dict]:
    items = contract.get("bucket_did_not")
    if not isinstance(items, list) or not items:
        raise ConsumerError("bucket_did_not missing or empty")
    return [x for x in items if isinstance(x, dict)]


def consume(contract: dict, unit_id: str = "IMP-0209") -> dict[str, Any]:
    """Produce the downstream unit's first output from the contract alone.

    Does not read WORK-UNIT-CATALOG.json or any WFA artifact path. Absence of
    consumed artifacts is reported as a typed gap, which is a valid first
    output: the scout's first step is to name its sources.
    """
    if not isinstance(contract, dict):
        raise ConsumerError("contract is not an object")
    if contract.get("unit_id") != "WFA-0126":
        raise ConsumerError("contract unit_id is not WFA-0126")
    if "SUCCESS:WFA-0126" not in json.dumps(contract):
        raise ConsumerError("sentinel absent")
    binding = _binding(contract, unit_id)
    rows = _rows_by_id(contract)
    unknowns = _unknowns(contract)
    did_not = _did_not(contract)
    consumed = []
    missing = []
    for cid in binding.get("consumes_unit_ids") or []:
        row = rows.get(str(cid))
        if row is None:
            raise ConsumerError(f"{unit_id} consumes unknown id {cid}")
        consumed.append(
            {
                "unit_id": row["unit_id"],
                "path": row["path"],
                "schema": row["schema"],
                "schema_def": row["schema_def"],
                "schema_version": row["schema_version"],
                "present": row["present"],
                "consumers": list(row.get("consumers") or []),
            }
        )
        if not row.get("present"):
            missing.append(str(cid))
    inherited = []
    for uid in binding.get("inherits_unknown_ids") or []:
        ru = unknowns.get(str(uid))
        if ru is None:
            raise ConsumerError(f"{unit_id} inherits unknown id {uid}")
        inherited.append(
            {
                "id": ru["id"],
                "settling_experiment": ru["settling_experiment"],
                "owner_visible_impact": ru["owner_visible_impact"],
            }
        )
    kind = str(binding.get("first_output_kind") or "")
    if unit_id == "IMP-0209":
        query = next((c for c in consumed if c["unit_id"] == "WFA-0084"), None)
        registry = next((c for c in consumed if c["unit_id"] == "WFA-0078"), None)
        first = {
            "kind": kind,
            "goal": (
                "search the archaeology surface for ranked adopt/adapt "
                "candidates given a goal and constraints"
            ),
            "query_interface": query,
            "registry": registry,
            "ranked_candidate_slots": [],
            "anti_rebuild_gate": (
                "BUILD is refused until WFA-0120/WFA-0084 are present; a "
                "missing query interface is not a licence to rebuild"
            ),
            "gap": (
                "consumed artifacts absent: " + ",".join(missing)
                if missing
                else "all consumed artifacts present"
            ),
            "bucket_did_not_inherited": [
                x.get("id") for x in did_not if x.get("id") in {
                    "DN-QUERY",
                    "DN-REGISTRY-V2",
                    "DN-SCOUT-FORGE",
                }
            ],
        }
    elif unit_id == "TST-0001":
        first = {
            "kind": kind,
            "goal": "bind the 12-condition completion predicate to WFA artifacts",
            "consumed": consumed,
            "gap": (
                "consumed artifacts absent: " + ",".join(missing)
                if missing
                else "all consumed artifacts present"
            ),
        }
    else:
        first = {
            "kind": kind or "generic-intake",
            "consumed": consumed,
            "gap": (
                "consumed artifacts absent: " + ",".join(missing)
                if missing
                else "all consumed artifacts present"
            ),
        }
    return {
        "unit_id": unit_id,
        "bucket": binding.get("bucket"),
        "driven_purely_from": (
            "command-center/wfa/WFA-0126-bucket-handoff-contract.json"
        ),
        "catalog_not_consulted": True,
        "consumed_rows": consumed,
        "inherited_unknowns": inherited,
        "first_output": first,
        "usable": not missing,
    }
