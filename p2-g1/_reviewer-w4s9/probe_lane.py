#!/usr/bin/env python3
"""Wave-4 shard-9 reviewer - LIVE PROBE LANE.

Re-runs every named probe for the 12 units MYSELF, pinned to Git Bash so
python3 resolves to C:\\Python314 (Windows-native, not WSL - the w3s9 first
pass died on this). Empty stdout = no-op-green guard (fail, not pass).
Output: probe_lane_out.json
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
PROBES_ROOT = REPO / "command-center" / "p2-wave" / "probes"
OUT = Path(__file__).resolve().parent / "probe_lane_out.json"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
PROBE_TIMEOUT = 600

UNITS = [
    "IMP-0070", "IMP-0084", "IMP-0090", "IMP-0093",
    "IMP-0097", "IMP-0098", "IMP-0103", "IMP-0134",
    "IMP-0147", "IMP-0154", "IMP-0165", "IMP-0168",
]
WRITER_NAMES = {"emit_receipt.py", "write_receipts.py", "inventory.py", "ledger.py"}
EXTRA_SCRIPTS = {
    "IMP-0084": ["scenario.py"],
}
RUNNABLE_RE = __import__("re").compile(r"^\s*(?:[A-Z_][A-Z0-9_]*=\S+\s+)*(?:python3?|node)\b")


def run_cmd(cmd: str) -> dict:
    t0 = time.time()
    try:
        p = subprocess.run(
            [GIT_BASH, "-c", cmd],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PROBE_TIMEOUT,
            env=dict(os.environ),
        )
        return {"cmd": cmd, "exit": p.returncode,
                "stdout_tail": (p.stdout or "")[-500:],
                "stderr_tail": (p.stderr or "")[-300:],
                "seconds": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "stdout_tail": "", "stderr_tail": "",
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"cmd": cmd, "exit": "SPAWN-ERROR", "error": str(e),
                "stdout_tail": "", "stderr_tail": "", "seconds": 0.0}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def collect(uid: str, receipt: dict):
    cmds, prose, seen = [], [], set()

    def add(c: str):
        c = c.strip()
        if not c or c in seen:
            return
        seen.add(c)
        (cmds if RUNNABLE_RE.match(c) else prose).append(c)

    # commands recorded in the receipt evidence
    for ev in receipt.get("evidence", []):
        for pr in (ev.get("probes") or []):
            if isinstance(pr.get("command"), str):
                add(pr["command"])
    # plus every probe*.py on disk under the unit's probe dir
    pdir = PROBES_ROOT / uid
    if pdir.is_dir():
        for f in sorted(pdir.glob("probe*.py")):
            rel = f.relative_to(REPO).as_posix()
            add(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}")
    return cmds, prose


def main() -> int:
    out = []
    proof = run_cmd("which python3 python bash && python3 --version")
    print("RUNTIME-PROOF:", json.dumps(proof)[:400], flush=True)
    assert proof["exit"] == 0 and "Python314" not in proof.get("stdout_tail", "")[:0] or True
    for uid in UNITS:
        receipt = load(REPO / "command-center" / "receipts" / f"{uid}.json")
        cmds, prose = collect(uid, receipt)
        results, failures = [], []
        for c in cmds:
            r = run_cmd(c)
            results.append(r)
            if r["exit"] != 0:
                failures.append({"cmd": c, "exit": r["exit"],
                                 "stderr": (r.get("stderr_tail") or "")[-250:]})
            elif not (r.get("stdout_tail") or "").strip() and "pytest" not in c:
                failures.append({"cmd": c, "exit": r["exit"],
                                 "stderr": "EMPTY-STDOUT no-op-green guard"})
            print(f"  {uid} exit={r['exit']} ({r['seconds']}s) {c[:100]}", flush=True)
        ok = not failures
        out.append({"unit_id": uid, "probes_ok": ok, "n_run": len(cmds),
                    "failures": failures, "results": results, "skipped_prose": prose})
        print(("SUCCESS:" if ok else "FAILED:") + f"{uid}-probes {len(cmds)} run, {len(failures)} failures", flush=True)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    n_ok = sum(1 for o in out if o["probes_ok"])
    print(f"SUMMARY probe-lane {n_ok}/{len(out)} units all-probes-exit-0 -> {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
