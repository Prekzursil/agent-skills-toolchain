#!/usr/bin/env python3
"""Probe 1: AST import graph + SCC. Planted 2-cycle control must discriminate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from graph_core import UNIT, catalog_unit, repo_root, run_control, scan_tools  # noqa: E402

OUT_JSON = HERE / "probe1-ast-graph.json"


def check_artifact(scan: dict) -> str | None:
    unit = catalog_unit()
    rel = str(unit.get("output_path") or "")
    art = repo_root() / rel
    if not art.is_file() or art.stat().st_size <= 0:
        return None
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"unparseable:{exc}"
    if not isinstance(doc, dict):
        return "artifact-not-object"
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{st}"
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel and sentinel not in text:
        return "sentinel-absent"
    claimed = doc.get("cycle_count")
    if claimed is None and isinstance(doc.get("report"), dict):
        claimed = doc["report"].get("cycle_count")
    if claimed is not None and int(claimed) != int(scan["cycle_count"]):
        return f"cycle-count-mismatch claimed={claimed} live={scan['cycle_count']}"
    claimed_n = doc.get("module_count")
    if claimed_n is None and isinstance(doc.get("report"), dict):
        claimed_n = doc["report"].get("module_count")
    if claimed_n is not None and int(claimed_n) != int(scan["module_count"]):
        return f"module-count-mismatch claimed={claimed_n} live={scan['module_count']}"
    return None


def main() -> int:
    ctl = run_control()
    if not ctl.get("pass"):
        print(json.dumps({"probe": "probe1-ast-graph", "control": ctl}, indent=1, sort_keys=True))
        print("FAILED:AUD-0030-probe1 SCC control does not discriminate")
        return 1
    scan = scan_tools()
    payload = {
        "probe": "probe1-ast-graph",
        "unit_id": UNIT,
        "instrument": "ast.parse Import/ImportFrom + iterative Tarjan SCC; sibling-script resolution",
        "control": {
            "pass": ctl["pass"],
            "fires_on_planted_cycle": ctl["fires_on_planted_cycle"],
            "silent_on_acyclic_twin": ctl["silent_on_acyclic_twin"],
            "cycles_found": ctl["cycles_found"],
            "cycles_found_acyclic": ctl["cycles_found_acyclic"],
        },
        "files_scanned": scan["files_scanned"],
        "module_count": scan["module_count"],
        "edge_count": scan["edge_count"],
        "cycle_count": scan["cycle_count"],
        "cycles": scan["cycles"],
        "top_fan_in": scan["top_fan_in"],
        "tools_lib_exists": scan["tools_lib_exists"],
        "tools_lib_py_count": scan["tools_lib_py_count"],
        "tools_lib_modules": scan["tools_lib_modules"],
        "pass": True,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    err = check_artifact(scan)
    if err:
        print(json.dumps(payload, indent=1, sort_keys=True))
        print(f"FAILED:AUD-0030-probe1 {err}")
        return 1
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"control planted_cycle={ctl['cycles_found']} acyclic={ctl['cycles_found_acyclic']} "
        f"live modules={scan['module_count']} edges={scan['edge_count']} cycles={scan['cycle_count']}"
    )
    print(
        "SUCCESS:AUD-0030-probe1 AST graph + Tarjan SCC; planted 2-cycle control is both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
