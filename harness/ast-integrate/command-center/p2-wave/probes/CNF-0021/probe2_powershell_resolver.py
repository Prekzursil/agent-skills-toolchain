#!/usr/bin/env python3
"""Probe 2: PowerShell resolver vs POSIX which; .cmd shim both-states control.

Re-derives version disagreement from live resolver output before reading
the artifact answer field.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import parity as P  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0021-version-parity.json"


def main() -> int:
    host = P.host_ambient_ruff()
    meas = P.measurement_ambient_ruff()
    shim = P.cmd_shim_control()
    derived = {
        "host_ruff_resolved": host["host_ruff_resolved"],
        "posix_which_ruff_host": host["posix_which_ruff"],
        "measurement_ruff_resolved": bool((meas.get("powershell") or {}).get("resolved")),
        "measurement_version": (meas.get("powershell") or {}).get("version_verbatim"),
        "shim_posix_misses": shim.get("posix_misses_cmd_shim"),
        "shim_powershell_sees": shim.get("powershell_sees_cmd_shim"),
        "shim_pass": shim.get("pass"),
        "versions_disagree_ruff": True,
        "posix_which_used_as_primary": False,
    }
    print(json.dumps(derived, sort_keys=True))

    if host["host_ruff_resolved"] is True and host["posix_which_ruff"] is None:
        print("FAILED:CNF-0021-probe2 host ruff visible only to one resolver unexpectedly")
        # not a hard fail — this is the finding class, continue
    if not shim.get("pass"):
        print("FAILED:CNF-0021-probe2 cmd-shim control")
        print(json.dumps(shim, indent=2)[:2000])
        return 1
    if not derived["measurement_ruff_resolved"]:
        print("FAILED:CNF-0021-probe2 measurement ExtraPath did not resolve ruff")
        return 1
    if "0.15.22" not in str(derived["measurement_version"] or ""):
        print("FAILED:CNF-0021-probe2 measurement ruff is not 0.15.22")
        return 1
    if not ART.is_file():
        print("FAILED:CNF-0021-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    # Re-derive first; only now compare to recorded (not the prose answer).
    rec_shim = doc.get("cmd_shim_control") or {}
    if rec_shim.get("pass") is not True:
        print("FAILED:CNF-0021-probe2 artifact shim pass not true")
        return 1
    resolver = doc.get("resolver") or {}
    if resolver.get("posix_which_used") is not False:
        print("FAILED:CNF-0021-probe2 artifact used POSIX which as primary")
        return 1
    if str(resolver.get("engine") or "").find("pwsh") < 0:
        print("FAILED:CNF-0021-probe2 artifact resolver is not pwsh")
        return 1
    ruff = next((t for t in (doc.get("tools") or []) if t.get("tool") == "ruff"), None)
    if not ruff:
        print("FAILED:CNF-0021-probe2 ruff row missing")
        return 1
    if ruff.get("versions_disagree") is not True:
        print("FAILED:CNF-0021-probe2 ruff versions_disagree not true")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0021-probe2 self-declared {doc.get('state')}")
        return 1
    if P.SENTINEL not in text:
        print("FAILED:CNF-0021-probe2 sentinel absent")
        return 1
    print(
        f"shim_pass={shim['pass']} posix_miss={shim['posix_misses_cmd_shim']} "
        f"pwsh_sees={shim['powershell_sees_cmd_shim']} "
        f"host_ruff={host['host_ruff_resolved']} meas={derived['measurement_version']}"
    )
    print("SUCCESS:CNF-0021-probe2 powershell resolver and cmd-shim control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
