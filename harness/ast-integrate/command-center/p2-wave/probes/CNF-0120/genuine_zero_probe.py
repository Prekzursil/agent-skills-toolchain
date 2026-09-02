#!/usr/bin/env python3
"""Completed probe over three clean subjects that yields finding_count=0.

This is the GENUINE_ZERO control: a probe that actually ran, not an empty
unread container and not a missing directory.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUBJECTS = HERE / "fixtures" / "genuine-zero" / "subjects"
RECEIPT = HERE / "fixtures" / "genuine-zero" / "receipt.json"


def main() -> int:
    SUBJECTS.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in SUBJECTS.glob("*.json") if p.is_file())
    findings: list[str] = []
    checked: list[str] = []
    for path in files:
        checked.append(path.name)
        doc = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            findings.append(path.name + ":not-object")
            continue
        if doc.get("defect") is True or doc.get("broken") is True:
            findings.append(path.name)
    receipt = {
        "id": "FIXTURE-GENUINE-ZERO",
        "probe_ran": True,
        "finding_count": len(findings),
        "findings": findings,
        "subjects_checked": checked,
        "subject_count": len(files),
        "probe": {
            "ran": True,
            "exit_code": 0,
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/CNF-0120/genuine_zero_probe.py"
            ),
            "finding_count": len(findings),
        },
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    if len(files) < 3:
        print("FAILED:CNF-0120-genuine-zero need 3 subjects")
        return 1
    if findings:
        print("FAILED:CNF-0120-genuine-zero expected 0 findings")
        return 1
    print("SUCCESS:CNF-0120-genuine-zero finding_count=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
