#!/usr/bin/env python3
"""Probe 2: schema-parity by path, plus unrun cells stay NOT-CHECKED.

Both local vendors' artifacts must validate against the identical schema file
(command-center/schema/work-result.schema.json). A copied schema path must
turn the differential red. An unrun live cell must stay NOT-CHECKED and must
not inherit the other vendor's PASS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import conformance as C  # noqa: E402

RUN = HERE / "runs" / "probe2"
PLAN = REPO / "command-center/phase3/A6/TEST-PLAN.json"


def main() -> int:
    parity = C.schema_parity_assertion(RUN)
    unrun = C.unrun_cells_not_inferred(RUN)
    gap = C.mutation_suite_would_not_catch(RUN)
    print(
        f"schema_path={parity['schema_path']} sha256={parity['schema_sha256']} "
        f"same_path={parity['same_path']} same_sha={parity['same_sha']} "
        f"both_schema_ok={parity['both_schema_ok']} "
        f"path_mutant_caught={parity['path_mutant_caught']}"
    )
    print(
        f"unrun verdict={unrun['live_cell'].get('verdict')} "
        f"inferred={unrun['live_cell'].get('inferred')} "
        f"copied={unrun['copied']} diff={unrun['differential']['verdict']}"
    )
    print(
        f"gap name={gap['name']} payloads_differ={gap['payloads_differ']} "
        f"diff={gap['differential']['verdict']}"
    )
    if not (parity["ok"] and unrun["ok"] and gap["ok"]):
        print("FAILED:ARC-0043-probe2 schema-parity or unrun-inference control")
        return 1

    if PLAN.is_file():
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        recorded = plan.get("schema_path")
        if recorded != C.SCHEMA_REL:
            print(f"FAILED:ARC-0043-probe2 plan schema_path drift {recorded}")
            return 1
        if plan.get("schema_sha256") != parity["schema_sha256"]:
            print("FAILED:ARC-0043-probe2 plan schema_sha256 drift")
            return 1
        overclaim = []
        for cell in plan.get("matrix", {}).get("cells") or []:
            if cell.get("inferred") is True:
                overclaim.append(f"{cell.get('row_id')}/{cell.get('column_id')}:inferred")
            if cell.get("ran") is False and cell.get("verdict") not in {
                "NOT-CHECKED",
            }:
                overclaim.append(
                    f"{cell.get('row_id')}/{cell.get('column_id')}:"
                    f"{cell.get('verdict')}"
                )
        if overclaim:
            print("FAILED:ARC-0043-probe2 overclaimed unrun cells", overclaim[:8])
            return 1
        print("plan_schema_path_matches=True unrun_cells_honest=True")
    print("SUCCESS:ARC-0043-probe2 schema-parity by path; unrun stays NOT-CHECKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
