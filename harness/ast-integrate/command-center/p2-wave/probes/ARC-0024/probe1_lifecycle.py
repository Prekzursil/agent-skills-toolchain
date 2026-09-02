#!/usr/bin/env python3
"""Probe 1: lifecycle totality for every capability class.

Independent of DESIGN prose: walks the live index, activates and
deactivates one record per kind, and asserts the session returns to the
measured resident floor. A mutated index that drops a deactivation path
must fail the same checker (both-states).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gateway as G  # noqa: E402

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT", str(HERE.parents[3])))
DESIGN = REPO / "command-center/phase3/A4/DESIGN.json"


def main() -> int:
    result = G.check_lifecycle_totality()
    print(json.dumps({k: v for k, v in result.items() if k != "floor"}, indent=2, sort_keys=True))
    floor = result["floor"]
    print(
        f"floor processes={floor['processes']} bytes={floor['bytes']} "
        f"activated={floor['activated_ids']}"
    )
    if DESIGN.is_file():
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        recorded = ((design.get("resident_set") or {}).get("floor") or {})
        if recorded:
            if int(recorded.get("processes", -1)) != int(floor["processes"]):
                print(
                    f"FAILED:ARC-0024-probe1 design floor processes "
                    f"{recorded.get('processes')} != live {floor['processes']}"
                )
                return 1
            if int(recorded.get("bytes", -1)) != int(floor["bytes"]):
                print(
                    f"FAILED:ARC-0024-probe1 design floor bytes "
                    f"{recorded.get('bytes')} != live {floor['bytes']}"
                )
                return 1
            print("design floor matches live resident()")
    if not result.get("ok"):
        print("FAILED:ARC-0024-probe1 lifecycle totality")
        return 1
    kinds = [row["kind"] for row in result["per_kind"] if row.get("ok")]
    print(f"kinds_ok={kinds}")
    print("SUCCESS:ARC-0024-probe1 lifecycle totality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
