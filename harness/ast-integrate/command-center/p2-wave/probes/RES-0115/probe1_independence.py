#!/usr/bin/env python3
"""Probe 1: independence check recorded and recomputed for every multi-reporter row."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import independence as I  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/research/RES-0115.json"
SENTINEL = (
    "SUCCESS:RES-0115 in the receipt AND a failure register with an "
    "independent-reporter count and at least one documented collapse to one"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0115-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    view = SL.artifact_view(doc)
    if str(view.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:RES-0115-probe1 self-declared {view.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0115-probe1 sentinel absent")
        return 1
    register = view.get("failure_register") or view.get("register") or []
    if not isinstance(register, list) or len(register) < 1:
        print("FAILED:RES-0115-probe1 failure_register empty")
        return 1
    multi = 0
    for row in register:
        if not isinstance(row, dict):
            print("FAILED:RES-0115-probe1 non-object row")
            return 1
        reporters = row.get("reporters") or []
        check = I.collapse_reporters(reporters)
        raw = int(row.get("raw_reporter_count") or 0)
        indep = int(row.get("independent_reporter_count") or -1)
        recorded = row.get("independence_check") or {}
        if raw != check["raw_reporter_count"] or indep != check["independent_reporter_count"]:
            print(
                f"FAILED:RES-0115-probe1 count mismatch {row.get('id')} "
                f"artifact raw={raw} indep={indep} "
                f"recomputed raw={check['raw_reporter_count']} "
                f"indep={check['independent_reporter_count']}"
            )
            return 1
        if raw > 1:
            multi += 1
            if recorded.get("performed") is not True:
                print(
                    f"FAILED:RES-0115-probe1 independence check not recorded "
                    f"for {row.get('id')}"
                )
                return 1
            if "verdict" not in recorded:
                print(f"FAILED:RES-0115-probe1 verdict missing on {row.get('id')}")
                return 1
            print(
                f"multi[{row.get('id')}] raw={raw} independent={indep} "
                f"verdict={recorded.get('verdict')}"
            )
    if multi < 1:
        print("FAILED:RES-0115-probe1 no multi-reporter row to check")
        return 1
    print(f"independence_checks={multi} rows_checked={len(register)}")
    print("SUCCESS:RES-0115-probe1 independence checks recorded and recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
