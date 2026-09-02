#!/usr/bin/env python3
"""Named probe 1: floors enforced per risk class."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.risk import (  # noqa: E402
    FLOORS,
    RISK_CLASSES,
    at_floor,
    evaluate_config,
    floor_enforcement_matrix,
    map_risk_class,
    matrix_is_sound,
)

ART = REPO / "command-center/receipts/IMP-0358.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0358-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0358":
        print("FAILED:IMP-0358-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:IMP-0358" not in text:
        print("FAILED:IMP-0358-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0358-probe1 self-declared", doc.get("state"))
        return 1

    mapped = {cls: map_risk_class(cls) for cls in RISK_CLASSES}
    for cls, row in mapped.items():
        floor = FLOORS[cls]
        if row["protocol_strength"] != floor["protocol_strength"]:
            print(f"FAILED:IMP-0358-probe1 map protocol {cls}")
            return 1
        if int(row["quorum"]) != int(floor["quorum"]):
            print(f"FAILED:IMP-0358-probe1 map quorum {cls}")
            return 1
        if row["evidence_standard"] != floor["evidence_standard"]:
            print(f"FAILED:IMP-0358-probe1 map evidence {cls}")
            return 1
        if int(row["reviewer_count"]) != int(floor["reviewer_count"]):
            print(f"FAILED:IMP-0358-probe1 map reviewers {cls}")
            return 1
        if row["immutable_after_start"] is not True:
            print("FAILED:IMP-0358-probe1 mapping does not declare immutability")
            return 1

    # HIGH cannot run on LOW floors.
    sneak = evaluate_config("HIGH", at_floor("LOW"))
    if sneak["accepted"] is not False:
        print("FAILED:IMP-0358-probe1 HIGH accepted LOW config")
        return 1
    dims = {v["dimension"] for v in sneak["violations"]}
    if not {"protocol_strength", "quorum", "evidence_standard", "reviewer_count"} <= dims:
        print("FAILED:IMP-0358-probe1 HIGH-vs-LOW violations incomplete", sneak)
        return 1

    rows = floor_enforcement_matrix()
    errors = matrix_is_sound(rows)
    if errors:
        print("FAILED:IMP-0358-probe1 matrix", errors)
        return 1

    payload = {
        "adjudicated": True,
        "pass": True,
        "probe": "probe1-floors",
        "unit_id": "IMP-0358",
        "classes": list(RISK_CLASSES),
        "mapping": mapped,
        "high_rejected_on_low_config": True,
        "high_vs_low_violations": sneak["violations"],
        "matrix_rows": len(rows),
        "matrix": rows,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0358-probe1 floors enforced per risk class")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
