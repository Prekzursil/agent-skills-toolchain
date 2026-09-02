#!/usr/bin/env python3
"""Probe 2: isolation + independent reviewer re-applies two survivors.

Every mutation is a tempfile copy. Shared gate sources must be byte-identical
after the reviewer run. Two reported survivors stay green; one killed
mutation stays red.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402
import code_mutants as C  # noqa: E402
from isolate import (  # noqa: E402
    REPO,
    find_item,
    fingerprint_shared,
    materialise_clean,
    run_validate_cli,
    write_json,
)

ART = REPO / "command-center/receipts/BLD-0039.json"
SENTINEL = "SUCCESS:BLD-0039"


def _view(doc: dict) -> dict:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    view = dict(report)
    view.update({k: v for k, v in doc.items() if k != "report"})
    return view


def _run_m01(tmp: Path, base: dict) -> dict:
    catalog = __import__("copy").deepcopy(base["catalog"])
    find_item(catalog, "R-M01")["dependencies"] = ["R-DOES-NOT-EXIST"]
    cat_path = tmp / "m01-catalog.json"
    graph_path = tmp / "m01-graph.json"
    write_json(cat_path, catalog)
    write_json(graph_path, B._derive_graph(catalog))
    cli = run_validate_cli(cat_path, graph_path, base["register_path"])
    return {"exit_code": cli["exit_code"], "output": (cli["output"] or "")[-500:]}


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0039-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in json.dumps(doc):
        print("FAILED:BLD-0039-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0039-probe2 self-declared", doc.get("state"))
        return 1

    before = fingerprint_shared()
    with tempfile.TemporaryDirectory(prefix="bld0039-p2-") as raw:
        tmp = Path(raw)
        base = materialise_clean(tmp / "clean")
        r1 = C.reapply_survivor_defaults(tmp / "rev", base)
        r2 = C.reapply_survivor_min_bytes()
        killed = _run_m01(tmp / "killed", base)
        code = C.run_code_mutants(base["catalog"], base["register_path"])
    after = fingerprint_shared()
    unchanged = before["aggregate_sha256"] == after["aggregate_sha256"]

    print(
        json.dumps(
            {
                "shared_tree_unchanged": unchanged,
                "m16_bare_exit": r1["bare_exit"],
                "m16_armed_exit": r1["armed_exit"],
                "m16_stayed_green": r1["stayed_green_bare"],
                "m16_armed_red": r1["goes_red_with_flag"],
                "c3_stayed_green": r2["stayed_green"],
                "m01_exit": killed["exit_code"],
                "code_killed": code["killed"],
                "code_survived": code["survived"],
                "before": before["aggregate_sha256"],
                "after": after["aggregate_sha256"],
            },
            sort_keys=True,
        )
    )
    if not unchanged:
        print("FAILED:BLD-0039-probe2 shared gate sources changed")
        return 1
    if not r1["stayed_green_bare"]:
        print("FAILED:BLD-0039-probe2 M16 did not stay green on bare CLI")
        return 1
    if not r1["goes_red_with_flag"]:
        print("FAILED:BLD-0039-probe2 M16 did not go red with --require-complete")
        return 1
    if not r2["stayed_green"]:
        print("FAILED:BLD-0039-probe2 C3 min_bytes default did not stay green")
        return 1
    if killed["exit_code"] == 0:
        print("FAILED:BLD-0039-probe2 M01 dangling mutation was not killed")
        return 1
    if code["killed"] < 1 or code["survived"] < 1:
        print(
            "FAILED:BLD-0039-probe2 code census is not a rate "
            f"killed={code['killed']} survived={code['survived']}"
        )
        return 1
    view = _view(doc)
    iso = view.get("isolation") or {}
    if iso.get("shared_tree_unchanged") is not True:
        print("FAILED:BLD-0039-probe2 receipt isolation not proven")
        return 1
    rev = view.get("reviewer") or {}
    reapplied = int(
        rev.get("reapplied_survivors")
        or view.get("reapplied_survivors")
        or 0
    )
    if rev.get("independent") is not True or reapplied < 2:
        print("FAILED:BLD-0039-probe2 reviewer requirement unmet in receipt")
        return 1
    print(
        f"unchanged=True m16_bare={r1['bare_exit']} m16_armed={r1['armed_exit']} "
        f"c3_green={r2['stayed_green']} m01_exit={killed['exit_code']}"
    )
    print("SUCCESS:BLD-0039-probe2 isolation and reviewer re-apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
