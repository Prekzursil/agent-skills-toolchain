#!/usr/bin/env python3
"""Probe 2: over-normalization control + borderline triple-run.

Mechanically different from probe 1: does not re-run the ISO-timestamp pair.
Plants a CLAIM-BODY word change against every named normalizer, and forces the
second-resolution clock through the third-run protocol.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import audit_one, needs_third_run  # noqa: E402
from normalizers import PLANTED_A, PLANTED_B, apply_one, over_normalization_report  # noqa: E402
from reproductions import REPRODUCTIONS  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0184.json"


def main() -> int:
    over = over_normalization_report()
    absorbed = [r["class"] for r in over if r["absorbed"]]
    if absorbed:
        print("FAILED:CNF-0184-probe2 over-normalization absorbed", absorbed)
        return 1
    for row in over:
        na = apply_one(row["class"], PLANTED_A)
        nb = apply_one(row["class"], PLANTED_B)
        if na == nb:
            print("FAILED:CNF-0184-probe2 live planted change equalized", row["class"])
            return 1

    spec = REPRODUCTIONS["fam3.clock-seconds"]
    identical_ts = "cmd=clock-seconds\nnow_s=1700000000\npayload=x\nstatus=0\n"
    if not needs_third_run(identical_ts, identical_ts, spec):
        print("FAILED:CNF-0184-probe2 identical timestamped pair skipped third run")
        return 1

    border = audit_one("fam3.clock-seconds")
    if border["run_count"] < 3 or not border["third_run"]:
        print(
            "FAILED:CNF-0184-probe2 borderline clock did not take a third run "
            f"run_count={border['run_count']}"
        )
        return 1
    if border["classification"] == "BYTE-DETERMINISTIC" and border["run_count"] < 3:
        print("FAILED:CNF-0184-probe2 classified deterministic from two timestamped runs")
        return 1

    if ART.is_file() and ART.stat().st_size > 200:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:CNF-0184" not in text:
            print("FAILED:CNF-0184-probe2 sentinel absent")
            return 1
        tests = doc.get("tests") or {}
        if tests.get("over_normalization_control", {}).get("pass") is not True:
            print("FAILED:CNF-0184-probe2 receipt over-normalization not PASS")
            return 1
        tr = tests.get("triple_run") or {}
        if tr.get("pass") is not True or int(tr.get("run_count") or 0) < 3:
            print("FAILED:CNF-0184-probe2 receipt triple_run not PASS")
            return 1

    print(
        f"over_absorbed=0 n_normalizers={len(over)} "
        f"border_runs={border['run_count']} third={border['third_run']} "
        f"border_class={border['classification']}"
    )
    print("SUCCESS:CNF-0184-probe2 over-normalization and triple-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
