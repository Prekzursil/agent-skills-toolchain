#!/usr/bin/env python3
"""Probe 1: undeclared write/spawn/network refused with distinct codes.

Signal 1 is the enforcer's refusal code. Signal 2 is an out-of-band observation
(filesystem census / process table / listener accept) that the side effect did
not occur. A refusal string alone is not proof.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from plugin.permission_enforcement import (  # noqa: E402
    Codes,
    PermissionDenied,
    PermissionEnforcer,
    PermissionManifest,
    listener,
    listener_accepted,
    oob_path_exists,
    oob_proc_cmdline_matches,
)


def main() -> int:
    report: dict = {"probe": "probe1-enforcement", "unit_id": "IMP-0059"}
    with tempfile.TemporaryDirectory(prefix="imp0059-p1-") as td:
        base = Path(td)
        outside = base / "undeclared-write.txt"
        marker = f"IMP0059-P1-SPAWN-{os.getpid()}-{time.time_ns()}"
        enf = PermissionEnforcer(
            PermissionManifest(
                fs_write_roots=(),
                allow_spawn=False,
                allow_network=False,
                component="probe1-narrow",
            )
        )
        codes = {}

        try:
            enf.write_file(outside, b"PROBE1-MUST-NOT-WRITE")
            write_exc = None
        except PermissionDenied as exc:
            write_exc = exc
        codes["write"] = getattr(write_exc, "code", None)
        write_oob = oob_path_exists(outside)
        report["write"] = {
            "refused": write_exc is not None,
            "code": codes["write"],
            "oob_file_exists": write_oob,
            "side_effect_prevented": not write_oob,
        }

        try:
            enf.spawn(
                [sys.executable, "-c", f"import time; time.sleep(12); #{marker}"]
            )
            spawn_exc = None
        except PermissionDenied as exc:
            spawn_exc = exc
        codes["spawn"] = getattr(spawn_exc, "code", None)
        spawn_hits = oob_proc_cmdline_matches(marker)
        report["spawn"] = {
            "refused": spawn_exc is not None,
            "code": codes["spawn"],
            "oob_proc_hits": spawn_hits,
            "side_effect_prevented": spawn_hits == [],
        }

        srv, port = listener()
        try:
            try:
                enf.connect("127.0.0.1", port)
                net_exc = None
            except PermissionDenied as exc:
                net_exc = exc
            codes["network"] = getattr(net_exc, "code", None)
            accepted = listener_accepted(srv)
            report["network"] = {
                "refused": net_exc is not None,
                "code": codes["network"],
                "oob_listener_accepted": accepted,
                "side_effect_prevented": not accepted,
            }
        finally:
            srv.close()

        expected = {
            "write": Codes.FS_WRITE_UNDECLARED,
            "spawn": Codes.SPAWN_UNDECLARED,
            "network": Codes.NETWORK_UNDECLARED,
        }
        distinct = len({c for c in codes.values() if c}) == 3
        report["codes"] = codes
        report["expected"] = expected
        report["codes_distinct"] = distinct
        report["codes_match"] = codes == expected

        receipt = REPO / "command-center/receipts/IMP-0059.json"
        if receipt.is_file():
            text = receipt.read_text(encoding="utf-8")
            report["receipt"] = {
                "present": True,
                "bytes": receipt.stat().st_size,
                "has_sentinel": "SUCCESS:IMP-0059" in text,
            }
        else:
            report["receipt"] = {"present": False}

        ok = (
            report["write"]["refused"]
            and report["write"]["side_effect_prevented"]
            and report["spawn"]["refused"]
            and report["spawn"]["side_effect_prevented"]
            and report["network"]["refused"]
            and report["network"]["side_effect_prevented"]
            and distinct
            and codes == expected
        )
        report["pass"] = ok
        print(json.dumps(report, sort_keys=True))
        if not ok:
            print("FAILED:IMP-0059-probe1 undeclared action not actually prevented")
            return 1
        print(
            "SUCCESS:IMP-0059-probe1 distinct refusal codes and OOB side-effect absence"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
