#!/usr/bin/env python3
"""Live probe leg - reviewer w4s10. Re-runs every named probe myself (fresh transport:
direct sys.executable -B <script>, cwd=REPO, PYTHONDONTWRITEBYTECODE=1, program PYTHONPATH).
Requires exit 0; also records whether the unit's own SUCCESS marker appears in output."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUT = REPO / "_reviewer-w4s10" / "probe_results.json"
UNITS = [
    "IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198", "IMP-0202", "IMP-0204",
    "IMP-0207", "IMP-0219", "IMP-0223", "IMP-0224", "IMP-0228", "IMP-0229",
]


def probe_cmds(uid: str) -> list[str]:
    ret = json.loads((REPO / "command-center/p2-wave/probes" / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    cmds = []
    for item in ret.get("named_probes") or []:
        if isinstance(item, dict):
            cmd = item.get("command")
            if isinstance(cmd, str) and cmd.strip():
                cmds.append(cmd.strip())
    if len(cmds) >= 2:
        return cmds[:2]
    # fallback: probe scripts on disk
    pdir = REPO / "command-center/p2-wave/probes" / uid
    p1 = sorted(pdir.glob("probe1*.py"))
    p2 = sorted(pdir.glob("probe2*.py"))
    out = []
    for lst in (p1, p2):
        named = [p for p in lst if p.name not in {"probe1.py", "probe2.py"}]
        out.append(str((named or lst)[0].relative_to(REPO)).replace("\\", "/"))
    return out


def run_one(uid: str, cmd: str) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    py_path = os.pathsep.join([
        hook_dir, str(REPO), str(REPO / "tools"),
        str(REPO / "tools" / "measure-guard"), str(REPO / "platform" / "lib"),
        str(REPO / "tools" / "agentspec"), env.get("PYTHONPATH", ""),
    ])
    env["PYTHONPATH"] = py_path
    # strip POSIX env-prefixes; substitute python3 -> this interpreter + g1 wrapper (as the
    # program's measure script does) so the recorded commands run verbatim on Windows
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = sys.executable.replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                           text=True, timeout=2700, env=env)
        rc, out = p.returncode, ((p.stdout or "") + (p.stderr or ""))
    except subprocess.TimeoutExpired:
        rc, out = 124, "TIMEOUT"
    dt = time.time() - t0
    marker = f"SUCCESS:{uid}" in out
    fail_marker = f"FAILED:{uid}" in out
    return {"cmd": cmd[:160], "rc": rc, "seconds": round(dt, 1),
            "success_marker": marker, "fail_marker": fail_marker,
            "tail": out.strip().splitlines()[-4:]}


def main() -> int:
    results = {}
    all_ok = True
    for uid in UNITS:
        cmds = probe_cmds(uid)
        runs = [run_one(uid, c) for c in cmds]
        ok = len(runs) > 0 and all(r["rc"] == 0 for r in runs)
        all_ok &= ok
        results[uid] = {"probes_ok": ok, "runs": runs}
        print(f"{'OK ' if ok else 'FAIL'} {uid}: " +
              " | ".join(f"rc={r['rc']} {r['seconds']}s marker={'Y' if r['success_marker'] else ('FAILMARK' if r['fail_marker'] else 'N')} :: {(r['tail'] or [''])[-1][:80]}"
                          for r in runs))
    OUT.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8", newline="\n")
    n = sum(1 for u in UNITS if results[u]["probes_ok"])
    print(f"{'SUCCESS' if all_ok else 'FAILED'}:reviewer-w4s10 live probes {n}/{len(UNITS)} units all-probes-exit-0")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
