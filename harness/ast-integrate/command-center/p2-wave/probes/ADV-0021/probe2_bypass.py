#!/usr/bin/env python3
"""Probe 2: execute each claimed mitigation; downgrade cells with no check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import UNIT, probe2_payload  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    payload = probe2_payload()
    attempts = []
    demos = []
    for cell in payload.get("stride_cells") or []:
        for hit in cell.get("bypass_attempts") or []:
            row = {
                "cell_id": cell.get("id"),
                "kind": hit.get("kind"),
                "bypass_succeeded": hit.get("bypass_succeeded"),
                "control_held": hit.get("control_held"),
            }
            attempts.append(row)
            if hit.get("kind") == "demonstration" and hit.get("bypass_succeeded"):
                demos.append(cell.get("id"))
    crypto = payload.get("crypto_negative_control") or {}
    compact = {
        "probe": "probe2-bypass",
        "unit_id": UNIT,
        "pass": payload.get("pass"),
        "reason": payload.get("reason"),
        "mitigated": payload.get("mitigated"),
        "partial": payload.get("partial"),
        "unmitigated": payload.get("unmitigated"),
        "downgraded": payload.get("downgraded"),
        "missing_executable_checks": payload.get("missing_executable_checks"),
        "closure_ok": payload.get("closure_ok"),
        "closure_reason": payload.get("closure_reason"),
        "benign_ok": (payload.get("bypass") or {}).get("benign_ok"),
        "attempt_count": (payload.get("bypass") or {}).get("attempt_count"),
        "attempts": attempts,
        "demonstrations_confirmed": sorted(set(demos)),
        "disposition_count": len(payload.get("dispositions") or []),
        "crypto_negative_control": {
            "control_held": crypto.get("control_held"),
            "unsigned": (crypto.get("detail") or {}).get("unsigned"),
            "bad_record": (crypto.get("detail") or {}).get("bad_record"),
        },
    }
    print(json.dumps(compact, sort_keys=True, default=str))
    if payload.get("traceback"):
        print(str(payload.get("traceback"))[-1500:])
    if not payload.get("pass"):
        return fail(str(payload.get("reason") or "bypass harness failed"))
    if payload.get("missing_executable_checks"):
        return fail(f"mitigated cells without check: {payload['missing_executable_checks']}")
    if not payload.get("closure_ok"):
        return fail(str(payload.get("closure_reason") or "disposition gap"))
    if not crypto.get("control_held"):
        return fail("crypto negative control did not fire")
    if int(payload.get("mitigated") or 0) < 1:
        return fail("no mitigated cell survived executable bypass")
    print(
        f"mitigated={payload['mitigated']} unmitigated={payload['unmitigated']} "
        f"downgraded={payload.get('downgraded')} "
        f"demos={sorted(set(demos))}"
    )
    print("SUCCESS:ADV-0021-probe2 executable bypass of claimed mitigations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
