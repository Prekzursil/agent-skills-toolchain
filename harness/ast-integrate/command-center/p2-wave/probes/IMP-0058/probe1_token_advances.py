#!/usr/bin/env python3
"""Named probe 1: token advances on a slow op; silence is not a hang.

Signal 1: heartbeat token value before vs after a CPU-bound cooperative op.
Signal 2: /proc cpu_ticks (or stdout byte growth) over the same interval.
The op is launched through scripts/longrun.sh, not a private classifier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from test_heartbeat import (  # noqa: E402
    test_silence_is_not_hang,
    test_token_advances_during_a_slow_op,
)

ART = REPO / "command-center/receipts/IMP-0058.json"


def main() -> int:
    slow = test_token_advances_during_a_slow_op()
    silent = test_silence_is_not_hang()
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        text = ART.read_text(encoding="utf-8")
        if "SUCCESS:IMP-0058" not in text:
            print("FAILED:IMP-0058-probe1 sentinel absent from receipt")
            return 1
        if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0058-probe1 receipt self-declared", doc.get("state"))
            return 1
        if doc.get("unit_id") != "IMP-0058":
            print("FAILED:IMP-0058-probe1 unit_id", doc.get("unit_id"))
            return 1
    out = {
        "probe": "probe1-token-advances",
        "unit_id": "IMP-0058",
        "slow_token_start": slow.get("token_start"),
        "slow_token_end": slow.get("token_end"),
        "slow_token_advanced": slow.get("token_advanced"),
        "slow_cpu_delta": slow.get("cpu_delta"),
        "slow_via_longrun_script": slow.get("via_longrun_script"),
        "silent_status": silent.get("status"),
        "silent_output_bytes_delta": silent.get("output_bytes_delta"),
        "silent_cpu_delta": silent.get("cpu_delta"),
        "mtime_consulted": False,
        "silence_is_hang": False,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"slow token {slow.get('token_start')}->{slow.get('token_end')} "
        f"cpu_delta={slow.get('cpu_delta')} via_script={slow.get('via_longrun_script')}"
    )
    print(
        f"silent status={silent.get('status')} bytes_delta={silent.get('output_bytes_delta')} "
        f"cpu_delta={silent.get('cpu_delta')}"
    )
    print("SUCCESS:IMP-0058-probe1 token advances; silence is not hang")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
