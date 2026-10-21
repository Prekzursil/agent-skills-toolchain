#!/usr/bin/env python3
"""ADV-0037 Probe 2 (error branches): force each REAL credential path's
unset / malformed / expired-shaped branches and repeat the exact-byte sweep --
the leak usually lives in the exception formatter rather than the happy path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402
import probe_targets_real as R  # noqa: E402


def main() -> int:
    report = R.campaign("error")
    det = report["detector"]
    executed = sum(1 for t in report["targets"] if t["executed"])
    leaking = [t["id"] for t in report["targets"] if t["hit"]]
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    print("=== ADV-0037 probe2_error summary ===")
    print(f"targets={len(report['targets'])} executed={executed} leaking={leaking}")
    print(f"detector fired_on_bad={det['fired_on_bad_state']} silent_on_good={det['silent_on_good_state']}")
    ok = executed == len(R.TARGET_IDS) and det["fired_on_bad_state"] and det["silent_on_good_state"]
    print("PROBE2_STATUS=" + ("OK" if ok else "DEGRADED"))
    print("planted_meta=" + json.dumps(C.planted_meta()))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
