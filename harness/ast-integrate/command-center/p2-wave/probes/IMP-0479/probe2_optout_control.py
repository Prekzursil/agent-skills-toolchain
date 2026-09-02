#!/usr/bin/env python3
"""Named probe 2: opt-out emits nothing; unredacted control fires; no egress.

Mechanically different from probe 1 (which plants canaries into a live sink):
this probe disables the bus, asserts zero bytes, then feeds an UNREDACTED
blob to the same detector to prove the sweep is not inert. Also rejects
stdout as a sink and AST-scans the package for network imports.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from telemetry.netaudit import audit_no_network  # noqa: E402
from telemetry.sweep import (  # noqa: E402
    refuse_ephemeral_sink,
    run_opt_out_proof,
    run_unredacted_control,
)

ART = REPO / "command-center/receipts/IMP-0479.json"
SENTINEL = "SENTINEL:IMP-0479:TELEMETRY-REDACTION-PROVEN"
PKG = REPO / "command-center" / "telemetry"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0479-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0479-probe2 sentinel absent")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0479-p2-") as tmp:
        opt = run_opt_out_proof(Path(tmp) / "store")
    ctrl = run_unredacted_control()
    eph = refuse_ephemeral_sink()
    net = audit_no_network(PKG)

    if not opt.get("pass") or opt.get("file_created") or opt.get("bytes") != 0:
        print("FAILED:IMP-0479-probe2 opt-out still emitted")
        return 1
    if not ctrl.get("pass") or not ctrl.get("fired_on_bad_state"):
        print("FAILED:IMP-0479-probe2 unredacted control did not fire")
        return 1
    if not ctrl.get("silent_on_good_state"):
        print("FAILED:IMP-0479-probe2 detector not silent on redacted good state")
        return 1
    if not eph.get("pass"):
        print("FAILED:IMP-0479-probe2 ephemeral sink was accepted")
        return 1
    if not net.get("pass"):
        print("FAILED:IMP-0479-probe2 network import", net.get("hits"))
        return 1

    summary = {
        "probe": "probe2-optout-control",
        "unit_id": "IMP-0479",
        "opt_out_emits_nothing": True,
        "unredacted_control_fired": True,
        "unredacted_control_silent_on_good": True,
        "ephemeral_sink_refused": True,
        "network_imports": 0,
        "canary_values_printed": False,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0479-probe2 opt-out silence and unredacted-control fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
