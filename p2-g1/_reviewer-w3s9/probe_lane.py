#!/usr/bin/env python3
"""Wave-3 shard-9 reviewer - probe lane RE-RUN under the correct runtime.

The first battery's subprocess resolved WSL bash/python3 (evidence:
/usr/lib/python3.12 tracebacks, /home/prekzursil/... paths, `python: command
not found`) - a wrong-runtime artifact that invalidates those probe results.
This lane pins bash to Git Bash explicitly so `python3`/`python` resolve to
C:\Python314, the runtime the tree's probes are built and measured under.

Read-only over receipts; runs probe commands only. Output: probe_lane_out.json
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CC = REPO / "command-center"
PROBES_ROOT = CC / "p2-wave" / "probes"
OUT = Path(__file__).resolve().parent / "probe_lane_out.json"
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
PROBE_TIMEOUT = 600

UNITS = [
    "IMP-0022", "IMP-0031", "IMP-0035", "IMP-0036", "IMP-0037", "IMP-0038",
    "IMP-0041", "IMP-0044", "IMP-0051", "IMP-0068", "IMP-0070", "IMP-0084",
]
WRITER_NAMES = {"emit_receipt.py", "write_receipts.py"}
EXTRA_SCRIPTS = {
    "IMP-0038": ["scenario.py"],
    "IMP-0051": ["negative_control.py", "run_required_tests.py"],
}
RUNNABLE_RE = re.compile(r"^\s*(?:[A-Z_][A-Z0-9_]*=\S+\s+)*(?:python3?|node)\b")


def run_cmd(cmd: str) -> dict:
    import os  # noqa: PLC0415
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
                "stdout_tail": (p.stdout or "")[-400:],
                "stderr_tail": (p.stderr or "")[-250:],
                "seconds": round(time.time() - t0, 1)}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": "TIMEOUT", "stdout_tail": "", "stderr_tail": "",
                "seconds": round(time.time() - t0, 1)}
    except Exception as e:  # noqa: BLE001
        return {"cmd": cmd, "exit": "SPAWN-ERROR", "error": str(e),
                "stdout_tail": "", "stderr_tail": "", "seconds": 0.0}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def collect(uid: str, receipt: dict, unit: dict):
    cmds, prose, seen = [], [], set()

    def add(c: str):
        c = c.strip()
        if not c or c in seen:
            return
        seen.add(c)
        if RUNNABLE_RE.match(c):
            cmds.append(c)
        else:
            prose.append(c)

    for ev in receipt.get("evidence", []):
        for pr in (ev.get("probes") or []):
            if isinstance(pr.get("command"), str):
                add(pr["command"])
    pdir = PROBES_ROOT / uid
    if pdir.is_dir():
        for f in sorted(pdir.iterdir()):
            n = f.name
            if n in WRITER_NAMES or not n.endswith(".py"):
                continue
            rel = f.relative_to(REPO).as_posix()
            if n.startswith("probe") or n in EXTRA_SCRIPTS.get(uid, []):
                add(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel}")
    for t in unit.get("tests_required") or []:
        if isinstance(t, str) and ".py" in t:
            path = t.split("::")[0].strip()
            if (REPO / path).is_file():
                add(f"python3 -m pytest -q {path}")
            else:
                prose.append(f"tests_required file absent on tree: {t}")
    return cmds, prose


def main() -> int:
    cat = load_json(CC / "WORK-UNIT-CATALOG.json")
    byid = {u["id"]: u for u in cat["work_units"]}
    out = []
    # runtime identity proof first
    probe = run_cmd("which python3 python bash && python3 --version")
    print("RUNTIME-PROOF:", json.dumps(probe)[:400], flush=True)
    for uid in UNITS:
        receipt = load_json(CC / "receipts" / (uid + ".json"))
        unit = byid[uid]
        cmds, prose = collect(uid, receipt, unit)
        results = []
        failures = []
        for c in cmds:
            r = run_cmd(c)
            results.append(r)
            if r["exit"] != 0:
                failures.append({"cmd": c, "exit": r["exit"],
                                 "stderr": (r.get("stderr_tail") or "")[-200:]})
            elif (r.get("stdout_tail") or "").strip() == "" and "pytest" not in c:
                failures.append({"cmd": c, "exit": r["exit"], "stderr": "EMPTY-STDOUT no-op-green guard"})
            print(f"  {uid} probe exit={r['exit']} ({r['seconds']}s) {c[:90]}", flush=True)
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
