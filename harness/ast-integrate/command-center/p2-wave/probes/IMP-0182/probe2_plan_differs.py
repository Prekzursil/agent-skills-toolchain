#!/usr/bin/env python3
"""Probe 2: valid splice runs on the fake rail; plan differs from BOTH parents.

Guards a no-op fusion that silently returns one parent. Also: zero spawn, zero
network; untouched host stages byte-identical; AST of fake_rail.py has no
subprocess/socket/urllib import.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fake_rail import FakeRail, RailRefusal  # noqa: E402
from scenario import (  # noqa: E402
    DONOR_INDEX,
    HOST_INDEX,
    host_workflow,
    initial_env,
    matching_donor,
)
from stage_splice import stage_splice  # noqa: E402
from workflow_ir import untouched_byte_identical  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0182.json"
FORBIDDEN_IMPORTS = frozenset(
    {"subprocess", "socket", "urllib", "http.client", "requests", "httpx"}
)


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0182-probe2 {msg}")
    return 1


def fake_rail_imports() -> set[str]:
    tree = ast.parse((HERE / "fake_rail.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.name or "").split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
            names.add(node.module)
    return names


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return _fail(f"receipt self-declared {doc.get('state')}")
    if "SUCCESS:IMP-0182" not in text:
        return _fail("sentinel absent")

    imported = fake_rail_imports()
    hit = sorted(n for n in imported if n in FORBIDDEN_IMPORTS or n.split(".")[0] in FORBIDDEN_IMPORTS)
    if hit:
        return _fail(f"fake_rail imports live I/O {hit}")

    host = host_workflow()
    donor = matching_donor()
    result = stage_splice(host, donor, HOST_INDEX, DONOR_INDEX)
    if result.get("status") != "emitted" or not result.get("fusion"):
        return _fail(f"valid splice refused: {result.get('reason')}")
    fusion = result["fusion"]

    rail = FakeRail()
    env = initial_env()
    try:
        host_run = FakeRail().run(host, env)
        donor_run = FakeRail().run(donor, env)
        fused_run = rail.run(fusion, env)
    except RailRefusal as exc:
        return _fail(f"rail refused a valid workflow: {exc.reason} {exc.detail}")

    for run, label in ((host_run, "host"), (donor_run, "donor"), (fused_run, "fusion")):
        if not run.get("ok"):
            return _fail(f"{label} run not ok")
        if run.get("spawn_count") != 0 or run.get("network_count") != 0:
            return _fail(f"{label} spawn/network non-zero")

    hp, dp, fp = host_run["plan_fingerprint"], donor_run["plan_fingerprint"], fused_run["plan_fingerprint"]
    if fp == hp:
        return _fail("fusion plan equals host plan (no-op parent)")
    if fp == dp:
        return _fail("fusion plan equals donor plan (no-op parent)")
    if host_run["plan"] == fused_run["plan"]:
        return _fail("fusion executed plan equals host executed plan")
    if donor_run["plan"] == fused_run["plan"]:
        return _fail("fusion executed plan equals donor executed plan")

    rows = untouched_byte_identical(host, fusion, HOST_INDEX)
    if not rows or any(not r["identical"] for r in rows):
        return _fail(f"untouched host stages not byte-identical {rows}")
    if len(rows) != len(host["stages"]) - 1:
        return _fail(f"untouched count {len(rows)}")

    if fused_run["env"].get("verdict") is None:
        return _fail("fusion did not produce an exit verdict")

    summary = {
        "probe": "probe2-plan-differs",
        "unit_id": "IMP-0182",
        "pass": True,
        "host_plan_fingerprint": hp,
        "donor_plan_fingerprint": dp,
        "fusion_plan_fingerprint": fp,
        "differs_from_host": fp != hp,
        "differs_from_donor": fp != dp,
        "spawn_count": fused_run["spawn_count"],
        "network_count": fused_run["network_count"],
        "untouched_identical": all(r["identical"] for r in rows),
        "fusion_verdict": fused_run["env"].get("verdict"),
        "fusion_score": fused_run["env"].get("score"),
        "fake_rail_imports": sorted(imported),
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    print("SUCCESS:IMP-0182-probe2 fake-rail splice plan differs from both parents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
