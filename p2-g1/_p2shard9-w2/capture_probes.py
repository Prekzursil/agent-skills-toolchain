#!/usr/bin/env python3
"""Run a unit's named probes live, capture raw outputs, write <UID>-probes.json.

Usage: python capture_probes.py <UID> rel/path/probe1.py rel/path/probe2.py [...]
The recorded command is the canonical POSIX-style form used by the measure
script; execution uses the live interpreter (env prefix applied here).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")


def main() -> int:
    uid = sys.argv[1]
    probes = []
    for i, rel in enumerate(sys.argv[2:], 1):
        rel_posix = rel.replace(chr(92), "/")
        cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel_posix}"
        # cmd.exe (shell=True on Windows) cannot run POSIX env prefixes; strip
        # them into the child env exactly like _measure_one_delivered does.
        exe = sys.executable.replace(chr(92), "/")
        run_cmd = f'"{exe}" -B {rel_posix}'
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run(run_cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env)
        raw = (p.stdout or "") + (p.stderr or "")
        print(f"--- {rel}: rc={p.returncode}")
        if p.returncode != 0:
            print(raw[-2000:])
            return 1
        probes.append({"id": f"probe{i}", "command": cmd, "exit_code": 0, "raw_output": raw})
    out = REPO / "_p2shard9-w2" / f"{uid}-probes.json"
    out.write_text(json.dumps(probes), encoding="utf-8")
    print(f"captured {len(probes)} probes for {uid} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
