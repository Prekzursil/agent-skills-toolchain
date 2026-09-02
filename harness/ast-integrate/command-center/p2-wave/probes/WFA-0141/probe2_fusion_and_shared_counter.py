#!/usr/bin/env python3
"""Probe 2: fusion both-states + runtime-vs-guard + shared-counter AST."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

OUT = HERE / "probe2-fusion-and-shared-counter.raw.json"
SRC = HERE / "census.py"


def calls_count_planes(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "count_planes":
                return True
    return False


def main() -> int:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    errors: list[str] = []
    acq_calls = "acquire" in fns and calls_count_planes(fns["acquire"])
    fuse_calls = "fuse" in fns and calls_count_planes(fns["fuse"])
    if not acq_calls:
        errors.append("acquire() does not call count_planes")
    if not fuse_calls:
        errors.append("fuse() does not call count_planes")

    planted = C.planted_bundle()
    catalog = C.candidate_catalog(planted["candidates"])
    fusions = {row["id"]: row for row in planted["fusions"]}
    dup = C.fuse(fusions["plant-fusion-dup-planes"], catalog)
    single = C.fuse(fusions["plant-fusion-single-plane"], catalog)
    two_f = C.fuse(fusions["plant-fusion-two-foreign"], catalog)
    lying = C.acquire(catalog["plant-home-string-foreign-import"])

    if dup["gate"] != "FIRE" or not dup["over_one"]:
        errors.append(f"duplicate-plane fusion did not fire: {dup}")
    if "langgraph" not in dup["planes"]:
        errors.append(f"dup fusion missing langgraph: {dup['planes']}")
    if single["gate"] != "PASS" or single["over_one"]:
        errors.append(f"single-plane fusion did not pass: {single}")
    if two_f["gate"] != "FIRE":
        errors.append(f"two-foreign fusion did not fire: {two_f}")
    if lying["gate"] != "FIRE":
        errors.append(f"home-string + crewai import did not fire: {lying}")
    if "crewai" not in lying["guard_planes"]:
        errors.append(f"guard missed crewai import: {lying}")
    if C.HOME_PLANE not in lying["runtime_field_planes"]:
        errors.append("runtime-field reading dropped the home string")
    if "langgraph" not in dup.get("source_runtime_field_planes", []):
        errors.append("source reading did not see langgraph")
    if C.HOME_PLANE not in dup.get("fused_definition_runtime_planes", []):
        errors.append("fused-definition reading left the home plane")
    if set(dup.get("source_runtime_field_planes", [])) == set(
        dup.get("fused_definition_runtime_planes", [])
    ):
        errors.append("source and fused-definition readings collapsed")

    live = C.live_bundle()
    report = {
        "probe": "probe2-fusion-and-shared-counter",
        "unit_id": "WFA-0141",
        "shared_counter": {
            "acquire_calls_count_planes": acq_calls,
            "fuse_calls_count_planes": fuse_calls,
        },
        "fusion_dup": dup,
        "fusion_single": single,
        "fusion_two_foreign": two_f,
        "lying_runtime_string": lying,
        "live_registry_available": live["live_available"],
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        print("FAILED:WFA-0141-probe2 " + "; ".join(errors))
        return 1
    print(
        json.dumps(
            {
                "dup_gate": dup["gate"],
                "single_gate": single["gate"],
                "lying_gate": lying["gate"],
                "shared_counter": True,
                "pass": True,
            }
        )
    )
    print(
        "SUCCESS:WFA-0141-probe2 fusion both-states; runtime-vs-guard split; "
        "acquire and fuse share count_planes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
