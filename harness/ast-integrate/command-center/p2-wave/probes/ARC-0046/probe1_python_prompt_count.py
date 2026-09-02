#!/usr/bin/env python3
"""Probe 1: Python shell, data field prompt_count_after on replay.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import replay as R  # noqa: E402

COST = REPO / "command-center/phase3/A7/COST.json"


def cost_body(doc: dict) -> dict:
    report = doc.get("report")
    if isinstance(report, dict) and "task_shapes" in report:
        return report
    return doc


def main() -> int:
    rc = R.main()
    if rc != 0:
        print("FAILED:ARC-0046-probe1 replay rc", rc)
        return 1
    doc = json.loads(R.REPLAY_JSON.read_text(encoding="utf-8"))
    py = {t["id"]: t["prompt_count_after"] for t in doc["tasks"]}
    if len(py) < 2:
        print("FAILED:ARC-0046-probe1 need two task shapes")
        return 1
    if not COST.is_file():
        print("FAILED:ARC-0046-probe1 COST.json missing")
        return 1
    cost = json.loads(COST.read_text(encoding="utf-8"))
    body = cost_body(cost)
    if "SUCCESS:ARC-0046" not in COST.read_text(encoding="utf-8"):
        print("FAILED:ARC-0046-probe1 sentinel absent")
        return 1
    recorded = {t["id"]: t["prompt_count_after"] for t in body["task_shapes"]}
    if recorded != py:
        print("FAILED:ARC-0046-probe1 prompt_count_after mismatch")
        print("live", py, "artifact", recorded)
        return 1
    unjust = [c for c in body["controls"] if c["attribution"] == "UNJUSTIFIED"]
    ids = {c["id"] for c in unjust}
    if "approve.every_read" not in ids or "sign.artifact_provenance" not in ids:
        print("FAILED:ARC-0046-probe1 UNJUSTIFIED controls missing", sorted(ids))
        return 1
    planted = next(c for c in body["controls"] if c["id"] == "approve.every_read")
    if planted.get("failure_class") is not None:
        print("FAILED:ARC-0046-probe1 theater must have null failure_class")
        return 1
    if rc == 2 or str(cost.get("state") or "").upper() == "BLOCKED":
        print("FAILED:ARC-0046-probe1 self-declared BLOCKED")
        return 1
    print(
        "python_field=prompt_count_after "
        + " ".join(f"{k}={v}" for k, v in sorted(py.items()))
    )
    print("SUCCESS:ARC-0046-probe1 python prompt_count_after")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
