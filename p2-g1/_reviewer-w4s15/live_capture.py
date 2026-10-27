#!/usr/bin/env python3
"""Full live probe capture for the 6 BLOCKED units (reviewer w4s15).

Re-runs every named probe of the 6 closable units MYSELF, capturing FULL
stdout/stderr to _reviewer-w4s15/live_runs/<uid>__<probe>.txt. These captures
are the reviewer's OWN live evidence from which closure blocks (tests,
negative_controls, downstream_consumers) are authored. Exit codes verified.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["RES-0112", "RES-0114", "RES-0128", "RES-0144", "RES-0151", "RES-0157"]
OUTDIR = REPO / "_reviewer-w4s15" / "live_runs"
OUTDIR.mkdir(parents=True, exist_ok=True)


def run_one(cmd: str) -> tuple:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([
        hook_dir, str(REPO), str(REPO / "tools"), str(REPO / "tools" / "measure-guard"),
        str(REPO / "platform" / "lib"), str(REPO / "tools" / "agentspec"),
        env.get("PYTHONPATH", ""),
    ])
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", exe + " " + wrapper.as_posix(), 1)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=2700, env=env, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or ""), round(time.time() - t0, 2)


def main() -> int:
    summary = {}
    for uid in UNITS:
        ret = json.loads((REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
        cmds = []
        for item in ret.get("named_probes") or []:
            if isinstance(item, dict) and isinstance(item.get("command"), str) and item["command"].strip():
                cmds.append(item["command"].strip())
        if len(cmds) < 2:
            pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
            for lst in (sorted(pdir.glob("probe1*.py")), sorted(pdir.glob("probe2*.py"))):
                if lst:
                    cmds.append("PYTHONDONTWRITEBYTECODE=1 python3 -B " + lst[0].relative_to(REPO).as_posix())
        urows = {}
        for cmd in cmds:
            pname = Path(cmd.split()[-1]).name
            rc, out, secs = run_one(cmd)
            cap = OUTDIR / (uid + "__" + pname + ".txt")
            cap.write_text(out, encoding="utf-8", newline="\n")
            urows[pname] = {"rc": rc, "seconds": secs, "capture": str(cap.relative_to(REPO)).replace("\\", "/"),
                            "bytes": len(out), "cmd": cmd}
            print(uid, pname, "rc=" + str(rc), str(len(out)) + "B", str(secs) + "s", flush=True)
        summary[uid] = urows
    (REPO / "_reviewer-w4s15" / "live_runs" / "index.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    bad = {u: {p: r["rc"] for p, r in rows.items() if r["rc"] != 0} for u, rows in summary.items()}
    bad = {u: b for u, b in bad.items() if b}
    print("FAILED:w4s15 live capture nonzero exits: " + json.dumps(bad) if bad else "SUCCESS:w4s15 live capture all probes exit 0")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
