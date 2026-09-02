#!/usr/bin/env python3
"""Probe 2: non-load-bearing hunks plus refuse-to-revert-tests control.

A protocol that only ever finds load-bearing hunks does not discriminate.
This probe requires at least one examined hunk whose failure does NOT
return on revert, and requires that reversing the test file is refused.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import protocol as P  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0032-hunk-revert-causality.json"
RAW = HERE / "probe2-non-load-bearing.raw.json"


def main() -> int:
    try:
        result = P.run_protocol()
    except P.ProtocolError as exc:
        print(f"FAILED:CNF-0032-probe2 protocol {exc}")
        return 1

    non = [
        r
        for r in result["rows"]
        if r["classification"] in {"non-load-bearing", "confounded-change"}
    ]
    refuse = result["refuse_test_revert"]
    payload = {
        "non_load_bearing": len(non),
        "non_ids": [r["id"] for r in non],
        "test_revert_refused": bool(refuse.get("refused")),
        "refuse_message": refuse.get("message"),
        "pass": False,
    }
    if not non:
        print("FAILED:CNF-0032-probe2 protocol never classified a non-load-bearing hunk")
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    still_green = [r for r in non if not r["revert"]["is_red"] and r["restore"]["is_green"]]
    if len(still_green) != len(non):
        print("FAILED:CNF-0032-probe2 non-load-bearing row was not revert-still-green")
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1
    if not refuse.get("refused"):
        print("FAILED:CNF-0032-probe2 test-file revert was not refused")
        RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        rec = (doc.get("counts") or {}).get("non_load_bearing")
        if rec != len(non):
            print(f"FAILED:CNF-0032-probe2 artifact non_load_bearing={rec} live={len(non)}")
            return 1
        iso = doc.get("scratch_isolation") or {}
        if iso.get("test_file_revert_refused") is not True:
            print("FAILED:CNF-0032-probe2 artifact did not record refuse")
            return 1

    payload["pass"] = True
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"non_load_bearing={len(non)} ids={payload['non_ids']} "
        f"test_revert_refused=True"
    )
    print("SUCCESS:CNF-0032-probe2 non-load-bearing classified; test revert refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
