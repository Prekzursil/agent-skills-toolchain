#!/usr/bin/env python3
"""Mimics _measure_one_delivered.py steps AFTER the state check: sentinel present,
SUBAGENT-RETURN ok, named probes re-run exit 0, manifest sha matches live bytes."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CAT = {u["id"]: u for u in json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))["work_units"]}
UNITS = ["IMP-0010", "IMP-0011", "IMP-0012", "IMP-0025", "IMP-0039", "IMP-0055",
         "IMP-0062", "IMP-0072", "IMP-0114", "IMP-0116", "IMP-0158"]
UNITS = ["IMP-0010", "IMP-0011", "IMP-0012", "IMP-0025", "IMP-0039", "IMP-0055",
         "IMP-0056", "IMP-0062", "IMP-0072", "IMP-0114", "IMP-0116", "IMP-0158"]


def digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run(cmd: str):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    import re as _re
    while True:
        m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]
    exe = str(sys.executable).replace(chr(92), "/")
    cmd = cmd.replace("python3", exe + " -B", 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=900, env=env)
    return p.returncode


ok_all = True
for u in UNITS:
    unit = CAT[u]
    out = REPO / unit["output_path"]
    text = out.read_text(encoding="utf-8")
    checks = {}
    checks["sentinel"] = unit["completion_sentinel"] in text
    pdir = REPO / "command-center" / "p2-wave" / "probes" / u
    ret = json.loads((pdir / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    st = str(ret.get("status") or ret.get("state") or "").upper()
    checks["return-status"] = st not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
    cmds = [np["command"] for np in ret.get("named_probes", [])]
    rcs = [run(c) for c in cmds]
    checks["probes-exit0"] = all(r == 0 for r in rcs)
    man = json.loads((pdir / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == u]
    live = digest(out)
    checks["manifest-row"] = any(a.get("path") == unit["output_path"] and a.get("present") is True and a.get("sha256") == live for a in rows)
    ok = all(checks.values())
    ok_all = ok_all and ok
    print(u, "OK" if ok else "GAP", checks if not ok else "", "probe-rcs:", rcs)
print("ALL-STACK-GREEN" if ok_all else "STACK-GAPS-PRESENT")
