#!/usr/bin/env python3
"""Probe 1: case-distinct keys survive; true duplicates are rejected (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.import_generic_dag import GenericDeclarativeDagAdapter  # noqa: E402
from agentspec.strict_parse import would_casefold_collide  # noqa: E402

FX = HERE / "fixtures"
ADAPTER = GenericDeclarativeDagAdapter()


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0162-probe1 {msg}")
    return 1


def _load(name: str):
    return ADAPTER.import_path(FX / name)


def main() -> int:
    good_json = _load("case_distinct.json")
    good_yaml = _load("case_distinct.yaml")
    if not good_json.ok or good_json.workflow is None:
        return _fail(f"case_distinct.json rejected {good_json.to_dict()}")
    if not good_yaml.ok or good_yaml.workflow is None:
        return _fail(f"case_distinct.yaml rejected {good_yaml.to_dict()}")

    for label, result in (("json", good_json), ("yaml", good_yaml)):
        wf = result.workflow
        unit_ids = list(wf.unit_ids())
        if unit_ids != ["Build", "build"]:
            return _fail(f"{label} node ids {unit_ids} (expected Build, build)")
        build = next(u for u in wf.units if u.id == "Build")
        param_keys = list(build.param_keys())
        if param_keys != ["Name", "name"]:
            return _fail(f"{label} param keys {param_keys} (expected Name, name)")
        if len(param_keys) != 2 or len(unit_ids) != 2:
            return _fail(f"{label} two-in-two-out failed")
        if not would_casefold_collide(param_keys):
            return _fail(f"{label} control: Name/name would not collide under casefold")
        if not would_casefold_collide(unit_ids):
            return _fail(f"{label} control: Build/build would not collide under casefold")
        folded_params = {k.casefold() for k in param_keys}
        if len(folded_params) != 1:
            return _fail(f"{label} casefold param cardinality {folded_params}")
        print(
            f"{label} nodes_in=2 nodes_out={len(unit_ids)} "
            f"params_in=2 params_out={len(param_keys)} "
            f"casefold_would_drop=True preserved={param_keys}"
        )

    dup_key = _load("duplicate_keys.json")
    dup_ids = [v.id for v in dup_key.violations]
    if dup_key.ok or "AS-DAG-DUPLICATE-KEY" not in dup_ids:
        return _fail(f"true duplicate keys not rejected: {dup_key.to_dict()}")
    print(f"duplicate_keys rejected id=AS-DAG-DUPLICATE-KEY ids={dup_ids}")

    dup_node = _load("duplicate_node_id.json")
    node_ids = [v.id for v in dup_node.violations]
    if dup_node.ok or "AS-DAG-DUPLICATE-NODE-ID" not in node_ids:
        return _fail(f"duplicate node id not named: {dup_node.to_dict()}")
    print(f"duplicate_node_id rejected id=AS-DAG-DUPLICATE-NODE-ID ids={node_ids}")

    twin = _load("valid_minimal.json")
    if not twin.ok:
        return _fail(f"valid twin rejected {twin.to_dict()}")
    print("valid_minimal imported ok=True (both-states good twin)")

    payload = {
        "probe": "probe1-case-distinct",
        "unit_id": "IMP-0162",
        "pass": True,
        "json_node_ids": list(good_json.workflow.unit_ids()),
        "json_param_keys": list(good_json.workflow.units[0].param_keys()),
        "yaml_node_ids": list(good_yaml.workflow.unit_ids()),
        "duplicate_key_id": "AS-DAG-DUPLICATE-KEY",
        "duplicate_node_id": "AS-DAG-DUPLICATE-NODE-ID",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0162-probe1 case-distinct keys preserved; true duplicates rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
