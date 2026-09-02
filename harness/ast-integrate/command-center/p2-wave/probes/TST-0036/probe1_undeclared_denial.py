#!/usr/bin/env python3
"""Named probe 1: live undeclared-permission call with denial record.

Evidence: an attempted undeclared-permission call with the denial record.
A silent grant is a P0. Out-of-band census confirms denied write/spawn
did not occur; a declared scratch write does occur.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from permission_model import (  # noqa: E402
    ALLOW,
    DENY,
    PermissionGate,
    census_path,
    narrow_plugin_policy,
)


def main() -> int:
    policy = narrow_plugin_policy("narrow-plugin")
    gate = PermissionGate(policy)
    with tempfile.TemporaryDirectory(prefix="tst0036-p1-") as tmp:
        root = Path(tmp)
        outside = root / "outside" / "p0-silent-grant.txt"
        marker = root / "spawned-marker.txt"
        scratch = root / "scratch" / "allowed.txt"

        declared = gate.attempt_tool("Read")
        undeclared = gate.attempt_tool("Write")
        write_dec = gate.attempt_write(outside, b"P0-if-this-lands")
        spawn_dec = gate.attempt_spawn(
            ["python3", "-c", f"open({str(marker)!r}, 'w').write('spawned')"]
        )
        net_dec = gate.attempt_connect("203.0.113.1", 9)
        cred_dec = gate.attempt_credential_read("OPENAI_API_KEY")
        ok_write = gate.attempt_write(scratch, b"allowed")

        write_denial = next(
            (
                r.as_dict()
                for r in gate.audit_log
                if r.name == "Write" and r.decision == DENY
            ),
            None,
        )
        denials = [
            r.as_dict()
            for r in gate.audit_log
            if r.decision == DENY
            and r.name
            in {
                "Write",
                str(outside),
                "python3",
                "203.0.113.1:9",
                "OPENAI_API_KEY",
            }
        ]
        ok = (
            declared.decision == ALLOW
            and undeclared.decision == DENY
            and undeclared.reason == "undeclared-permission"
            and undeclared.logged
            and write_denial is not None
            and write_denial["reason"] == "undeclared-permission"
            and write_dec.decision == DENY
            and spawn_dec.decision == DENY
            and net_dec.decision == DENY
            and cred_dec.decision == DENY
            and not outside.exists()
            and not marker.exists()
            and "203.0.113.1:9" not in gate.trace.connects
            and "OPENAI_API_KEY" not in gate.trace.credential_reads
            and ok_write.decision == ALLOW
            and scratch.exists()
            and scratch.read_bytes() == b"allowed"
            and len(denials) >= 4
        )
        payload = {
            "pass": bool(ok),
            "probe": "probe1-undeclared-denial",
            "unit_id": "TST-0036",
            "declared_read": declared.decision,
            "undeclared_write_tool": {
                "decision": undeclared.decision,
                "reason": undeclared.reason,
                "logged": undeclared.logged,
            },
            "denial_record": write_denial,
            "denials": denials,
            "side_effects": {
                "outside": census_path(outside),
                "spawn_marker": census_path(marker),
                "scratch": census_path(scratch),
                "connects": gate.trace.connects,
                "credential_reads": gate.trace.credential_reads,
            },
            "control_declared_write_ok": scratch.exists(),
        }
        print(json.dumps(payload, sort_keys=True))
        if not ok:
            print(
                "FAILED:TST-0036-probe1 undeclared request was not "
                "denied+logged or a denied action leaked"
            )
            return 1
        print(
            "SUCCESS:TST-0036-probe1 undeclared Write denied and logged; "
            "outside file absent; declared scratch write executed"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
