#!/usr/bin/env python3
"""Probe 2: independent severed-monitor review via network-partition kill."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import scenarios as S  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "BLD-0027.json"


def main() -> int:
    scratch = Path(tempfile.mkdtemp(prefix="bld0027-rev-"))
    part = S.executed_severed(scratch / "partition", mechanism="partition")
    kill = S.executed_severed(scratch / "sigkill", mechanism="sigkill")
    print(json.dumps({"partition": part, "sigkill": kill}, sort_keys=True, default=str))
    if not part.get("pass") or part.get("honest") != C.SEVERED:
        print("FAILED:BLD-0027-probe2 partition kill did not yield SEVERED")
        return 1
    if not kill.get("pass") or kill.get("honest") != C.SEVERED:
        print("FAILED:BLD-0027-probe2 process kill did not yield SEVERED")
        return 1
    if part.get("mechanism") == kill.get("mechanism"):
        print("FAILED:BLD-0027-probe2 kill mechanisms are not independent")
        return 1
    if RECEIPT.is_file():
        doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
        if "SUCCESS:BLD-0027" not in RECEIPT.read_text(encoding="utf-8"):
            print("FAILED:BLD-0027-probe2 receipt sentinel absent")
            return 1
        sampled = (doc.get("reviewer") or {}).get("sampled") or []
        if len(sampled) < 1:
            print("FAILED:BLD-0027-probe2 reviewer sampled empty")
            return 1
        ids = {str(s.get("finding_id")) for s in sampled if isinstance(s, dict)}
        if "F-SEVERED-PARTITION" not in ids and "F-INSTRUMENT-SEVERED-PARTITION" not in ids:
            print(f"FAILED:BLD-0027-probe2 reviewer did not sample partition finding {ids}")
            return 1
        print(f"receipt_ok=True sampled={len(sampled)}")
    print(
        "reviewer_ok=True partition={0} sigkill={1} independent=True".format(
            part.get("honest"), kill.get("honest")
        )
    )
    print("SUCCESS:BLD-0027-probe2 independent partition vs process-kill SEVERED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
