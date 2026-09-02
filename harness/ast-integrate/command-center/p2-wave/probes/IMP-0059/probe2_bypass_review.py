#!/usr/bin/env python3
"""Probe 2: reviewer bypasses (symlink hop, traversal, TOCTOU) plus negative control.

The negative control is the SAME three action classes with the capabilities
declared, in the same run, proving the gate is not a blanket deny.
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
    oob_pid_alive,
    oob_proc_cmdline_matches,
)


def main() -> int:
    report: dict = {
        "probe": "probe2-bypass-review",
        "unit_id": "IMP-0059",
        "reviewer_id": "IMP-0059-probe2-bypass-review",
    }
    with tempfile.TemporaryDirectory(prefix="imp0059-p2-") as td:
        base = Path(td)
        root = base / "root"
        mid = base / "mid"
        outside = base / "outside"
        root.mkdir()
        mid.mkdir()
        outside.mkdir()

        # Reviewer bypass A: two-hop symlink (root/hop -> mid/hop2 -> outside).
        hop2 = mid / "hop2"
        os.symlink(outside, hop2)
        hop = root / "hop"
        os.symlink(hop2, hop)
        wide = PermissionEnforcer(
            PermissionManifest(
                fs_write_roots=(str(root),),
                allow_spawn=True,
                allow_network=True,
                component="probe2-wide",
            )
        )
        leaked_a = outside / "via-twohop.txt"
        try:
            wide.write_file(hop / "via-twohop.txt", b"reviewer-twohop")
            a_exc = None
        except PermissionDenied as exc:
            a_exc = exc
        report["bypass_symlink_twohop"] = {
            "refused": a_exc is not None,
            "code": getattr(a_exc, "code", None),
            "oob_leaked": oob_path_exists(leaked_a),
        }

        # Reviewer bypass B: relative traversal out of the declared root.
        trav = root / "sub" / ".." / ".." / "outside" / "via-trav.txt"
        leaked_b = outside / "via-trav.txt"
        try:
            wide.write_file(trav, b"reviewer-trav")
            b_exc = None
        except PermissionDenied as exc:
            b_exc = exc
        report["bypass_relative_traversal"] = {
            "refused": b_exc is not None,
            "code": getattr(b_exc, "code", None),
            "oob_leaked": oob_path_exists(leaked_b),
        }

        # Reviewer bypass C: TOCTOU parent swap after authorize, before open.
        sub = root / "cell"
        sub.mkdir()
        target = sub / "race.txt"
        target.write_bytes(b"before")

        def swap() -> None:
            os.rename(sub, root / "cell.bak")
            os.symlink(outside, sub)

        wide._after_authorize_hook = swap
        try:
            wide.write_file(target, b"reviewer-toctou-payload")
            c_exc = None
        except PermissionDenied as exc:
            c_exc = exc
        finally:
            wide._after_authorize_hook = None
        leaked_c = outside / "race.txt"
        payload_leaked = False
        if oob_path_exists(leaked_c):
            payload_leaked = b"reviewer-toctou-payload" in leaked_c.read_bytes()
        report["bypass_toctou_parent_swap"] = {
            "refused": c_exc is not None,
            "code": getattr(c_exc, "code", None),
            "oob_payload_leaked": payload_leaked,
        }

        # Negative control: declared write/spawn/network succeed in THIS run.
        allowed = root / "ok.txt"
        wide.write_file(allowed, b"declared-ok")
        write_ok = oob_path_exists(allowed) and allowed.read_bytes() == b"declared-ok"

        marker = f"IMP0059-P2-OK-{os.getpid()}-{time.time_ns()}"
        proc = wide.spawn(
            [sys.executable, "-c", f"import time; time.sleep(3); #{marker}"]
        )
        try:
            time.sleep(0.15)
            spawn_ok = oob_pid_alive(proc.pid) and bool(
                oob_proc_cmdline_matches(marker)
            )
        finally:
            proc.kill()
            proc.wait(timeout=2)

        srv, port = listener()
        srv.settimeout(2.0)
        try:
            sock = wide.connect("127.0.0.1", port, timeout=2.0)
            try:
                net_ok = listener_accepted(srv)
            finally:
                sock.close()
        finally:
            srv.close()

        report["negative_control_declared_succeed"] = {
            "write_ok": write_ok,
            "spawn_ok": spawn_ok,
            "network_ok": net_ok,
        }

        expected_symlink = Codes.FS_SYMLINK_ESCAPE
        expected_trav = Codes.FS_TRAVERSAL
        expected_toctou = Codes.FS_TOCTOU
        a_ok = (
            a_exc is not None
            and a_exc.code == expected_symlink
            and not oob_path_exists(leaked_a)
        )
        b_ok = (
            b_exc is not None
            and b_exc.code == expected_trav
            and not oob_path_exists(leaked_b)
        )
        c_ok = c_exc is not None and c_exc.code == expected_toctou and not payload_leaked
        nc_ok = write_ok and spawn_ok and net_ok
        report["expected_codes"] = {
            "symlink": expected_symlink,
            "traversal": expected_trav,
            "toctou": expected_toctou,
        }
        report["pass"] = a_ok and b_ok and c_ok and nc_ok
        print(json.dumps(report, sort_keys=True))
        if not report["pass"]:
            print("FAILED:IMP-0059-probe2 bypass or negative control")
            return 1
        print(
            "SUCCESS:IMP-0059-probe2 reviewer bypasses refused; declared actions succeed"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
