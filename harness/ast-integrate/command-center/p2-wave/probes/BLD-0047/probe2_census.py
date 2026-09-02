#!/usr/bin/env python3
"""Probe 2: armed-not-reported, NOT-INVOKED control, independent flag executor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0047.json"


def main() -> int:
    armed = E.control_armed_not_reported()
    missing = E.control_not_invoked()
    reviewer = E.reviewer_execute()
    print(json.dumps({"armed": armed, "not_invoked": missing, "reviewer_pass": reviewer["pass"]}, sort_keys=True))
    if not armed["pass"]:
        print("FAILED:BLD-0047-probe2 armed-with-flag was reported or not ARMED", armed)
        return 1
    if not missing["pass"]:
        print("FAILED:BLD-0047-probe2 present-not-in-CI was not NOT-INVOKED", missing)
        return 1
    if not reviewer["pass"] or reviewer.get("verdict") != "PASS":
        print("FAILED:BLD-0047-probe2 reviewer flag execution", reviewer)
        return 1
    if not ART.is_file():
        print("FAILED:BLD-0047-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    findings = doc.get("findings") or []
    if any(f.get("path") == E.ARMED_REL for f in findings):
        print("FAILED:BLD-0047-probe2 receipt reported the planted armed gate")
        return 1
    census_findings = [f.get("path") for f in findings]
    # Live validate.py must appear as a hole on this worktree (NOT-INVOKED).
    if "tools/command-center/validate.py" not in census_findings:
        print("FAILED:BLD-0047-probe2 validate.py missing from findings")
        return 1
    val_row = next(
        (f for f in findings if f.get("path") == "tools/command-center/validate.py"),
        None,
    )
    if not val_row or val_row.get("classification") not in {"NOT-INVOKED", "DISARMED"}:
        print("FAILED:BLD-0047-probe2 validate.py classification", val_row)
        return 1
    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        print("FAILED:BLD-0047-probe2 reviewer field", rev)
        return 1
    if "SUCCESS:BLD-0047" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0047-probe2 sentinel")
        return 1
    print(
        "reviewer_gates="
        + ",".join(g["path"] for g in reviewer["gates"])
        + f" not_invoked={missing['classification']} armed={armed['classification']}"
    )
    print("SUCCESS:BLD-0047-probe2 census-controls reviewer-execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
