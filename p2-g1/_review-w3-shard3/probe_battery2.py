#!/usr/bin/env python3
"""Clean C09/C10 probe re-run: explicit Git Bash launcher (never System32/WSL bash stub).

Background: subprocess.run(["bash", ...]) resolved to C:\\Windows\\System32\\bash.exe
(the WSL relay). WSL Ubuntu on this box is wedged (0x8007274c; /mnt/c traversal times
out), which polluted the first battery's probe results. This pass pins the executable
to Git Bash, whose python3 is C:\\Python314\\python3 (CPython 3.14.6, same as `python`).
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
GITBASH = r"C:\Program Files\Git\bin\bash.exe"
OUTDIR = REPO / "_review-w3-shard3"
UNITS = [
    "ARC-0055", "ARC-0056", "ARC-0076",
    "AUD-0003", "AUD-0005", "AUD-0008", "AUD-0010", "AUD-0026",
    "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043",
]


def probe_commands(uid: str, receipt: dict) -> list[str]:
    cmds: list[str] = []
    for np in receipt.get("named_probes") or []:
        c = (np or {}).get("command")
        if isinstance(c, str) and c.strip():
            cmds.append(c.strip())
    for ev in receipt.get("evidence") or []:
        for pr in (ev or {}).get("probes") or []:
            c = (pr or {}).get("command")
            if isinstance(c, str) and c.strip() and c.strip() not in cmds:
                cmds.append(c.strip())
    cmds = [c for c in cmds if c.startswith(("PYTHONDONTWRITEBYTECODE", "python"))]
    if not cmds:
        # ARC-0055 lane: receipt records no command rows; the unit's named probes
        # live on disk as probe1.py/probe2.py - run those directly.
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        cands = sorted(pdir.glob("probe1*.py")) + sorted(pdir.glob("probe2*.py"))
        cmds = [f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p.name}" for p in cands]
    return cmds


def run(cmd: str, timeout: int) -> dict:
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            executable=GITBASH,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        tail = [ln for ln in out.strip().splitlines() if ln.strip()][-4:]
        return {"cmd": cmd, "exit": proc.returncode, "seconds": round(time.time() - t0, 1), "tail": tail}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "seconds": round(time.time() - t0, 1), "tail": ["TIMEOUT"]}
    except Exception as exc:  # noqa: BLE001
        return {"cmd": cmd, "exit": "SPAWN-ERROR", "seconds": round(time.time() - t0, 1), "tail": [repr(exc)]}


def main() -> int:
    results = {}
    for uid in UNITS:
        rec = json.loads((REPO / "command-center" / "receipts" / f"{uid}.json").read_text(encoding="utf-8"))
        cmds = probe_commands(uid, rec)
        runs = [run(c, 900) for c in cmds]
        # C10 cross-check with explicit Git Bash
        m = run(f"python command-center/p2-wave/_measure_one_delivered.py {uid}", 900)
        ok = all(r["exit"] == 0 for r in runs) and (
            m["exit"] == 0 and any("SUCCESS:delivered" in ln for ln in m["tail"])
        )
        results[uid] = {"probes": runs, "measure": m, "c09c10_ok": ok}
        print(f"[{uid}] c09c10_ok={ok}", flush=True)
        for r0 in runs + [m]:
            flag = "OK " if r0["exit"] == 0 else "BAD"
            print(f"   {flag} exit={r0['exit']} {r0['seconds']}s {r0['cmd'][:90]}", flush=True)
            if r0["exit"] != 0:
                for ln in r0["tail"][:3]:
                    print(f"      | {ln[:160]}", flush=True)
        (OUTDIR / "probe_results_clean.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
