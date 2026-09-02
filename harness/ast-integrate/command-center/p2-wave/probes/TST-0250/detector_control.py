#!/usr/bin/env python3
"""Detector control: deliberate planted print vs redacted good state."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402


def main() -> int:
    def inner(root):
        return {"detector": C.run_detector_control(root)}

    result = C.with_isolation(inner)
    det = result["detector"]
    print(C.dump_json({"probe": "detector-control", "unit_id": C.UNIT, **det, "egress_attempts": result.get("egress_attempts")}))
    if not det.get("pass"):
        print("FAILED:ADV-0037-detector-control sweep did not discriminate")
        return 1
    print("SUCCESS:ADV-0037-detector-control fired on bad, silent on good")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
