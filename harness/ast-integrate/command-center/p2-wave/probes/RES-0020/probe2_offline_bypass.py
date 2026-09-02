#!/usr/bin/env python3
"""Probe 2: offline zero-endpoint control + mitigation bypass reviewer."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import evaluate  # noqa: E402

ART = REPO / "command-center/research/RES-0020.json"
SENTINEL = (
    "SUCCESS:RES-0020 in the receipt AND an endpoint list with a "
    "with/without-telemetry diff and an explicit statement of which fields "
    "were observed versus merely documented"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0020-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:RES-0020-probe2 self-declared", doc.get("state"))
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0020-probe2 sentinel-absent")
        return 1

    live = evaluate()
    if not live["pass"]:
        print("FAILED:RES-0020-probe2 live harness checks failed")
        return 1

    offline = live["scenarios"]["offline"]
    online = live["scenarios"]["on"]
    print(
        f"offline_connects={offline['connect_count']} "
        f"offline_hits={offline['hit_count']} "
        f"online_connects={online['connect_count']}"
    )
    if offline["connect_count"] != 0 or offline["hit_count"] != 0:
        print("FAILED:RES-0020-probe2 offline produced endpoints")
        return 1
    if online["connect_count"] == 0:
        print("FAILED:RES-0020-probe2 offline control is vacuous (online also zero)")
        return 1

    rec_off = (doc.get("endpoints") or {}).get("offline_control") or {}
    if rec_off.get("connect_count") != 0:
        print(
            "FAILED:RES-0020-probe2 artifact offline connect_count drift",
            rec_off.get("connect_count"),
        )
        return 1

    rec_bypasses = doc.get("bypass_attempts") or []
    live_bypasses = live["bypass_attempts"]
    if len(rec_bypasses) != len(live_bypasses):
        print("FAILED:RES-0020-probe2 bypass attempt count drift")
        return 1
    for rec, live_row in zip(rec_bypasses, live_bypasses):
        if rec.get("mitigation") != live_row.get("mitigation"):
            print("FAILED:RES-0020-probe2 bypass mitigation drift", rec, live_row)
            return 1
        if bool(rec.get("bypassed")) != bool(live_row.get("bypassed")):
            print("FAILED:RES-0020-probe2 bypass result drift", rec)
            return 1
        if rec.get("bypassed") and rec.get("recorded_as_effective"):
            print("FAILED:RES-0020-probe2 effective mitigation had a successful bypass")
            return 1

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        print("FAILED:RES-0020-probe2 reviewer not independent")
        return 1
    effective = reviewer.get("mitigations_recorded_as_effective") or []
    if len(effective) < 1:
        print("FAILED:RES-0020-probe2 no effective mitigation recorded")
        return 1

    mcp_off = live["scenarios"]["mcp_off"]
    if "mcp_vendor" not in mcp_off["roles_hits"]:
        print("FAILED:RES-0020-probe2 MCP vendor egress missing under telemetry-off")
        return 1
    if "telemetry" in mcp_off["roles_hits"]:
        print("FAILED:RES-0020-probe2 telemetry still present under TELEMETRY_DISABLED")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-offline-bypass",
                "unit_id": "RES-0020",
                "offline_zero": True,
                "online_nonzero": True,
                "bypass_attempts": len(live_bypasses),
                "effective_mitigations": len(effective),
                "mcp_vendor_under_telemetry_off": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0020-probe2 offline zero-endpoint control and bypass reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
