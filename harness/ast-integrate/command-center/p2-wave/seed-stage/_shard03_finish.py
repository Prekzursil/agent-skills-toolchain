#!/usr/bin/env python3
"""Finish remaining shard-03 IDs + remesure easy fixes. Run in $HOME/p2-g1."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
WAVE = REPO / "command-center" / "p2-wave"
OUT = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/_shard03_finish.json")
REMAINING = [
    "TST-0062","TST-0129","TST-0157","TST-0191","TST-0222","TST-0249",
    "TST-0284","TST-0311","WFA-0004","WFA-0065","WFA-0110","WFA-0156",
]
REMEASURE = ["ADV-0027","ADV-0115","IMP-0261","IMP-0306","IMP-0475","ADV-0089","AUD-0014"]
EMIT = {
    "ADV-0027": "write_receipts.py",
    "ADV-0115": "write_receipts.py",
    "IMP-0261": "write_receipts.py",
    "IMP-0306": "emit.py",
    "IMP-0475": "write_receipts.py",
    "ADV-0089": "write_receipts.py",
    "AUD-0014": "write_receipts.py",
}


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, env=env, timeout=timeout)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def measure(uid: str) -> dict:
    try:
        rc, out = run([sys.executable, "-B", str(WAVE / "_measure_one_delivered.py"), uid], 180)
    except subprocess.TimeoutExpired:
        rc, out = 124, "TIMEOUT"
    last = out.splitlines()[-1] if out else ""
    ok = last == f"SUCCESS:delivered {uid}"
    print(("OK:" if ok else "FAIL:") + uid, last, flush=True)
    if not ok:
        print("\n".join(out.splitlines()[-8:]), flush=True)
    return {"id": uid, "rc": rc, "ok": ok, "line": last, "tail": out[-1500:]}


def main() -> int:
    rows = []
    for uid in REMEASURE:
        script = EMIT.get(uid)
        if script:
            path = WAVE / "probes" / uid / script
            if path.is_file():
                try:
                    erc, eout = run([sys.executable, "-B", str(path)], 180)
                except subprocess.TimeoutExpired:
                    erc, eout = 124, "TIMEOUT"
                print(f"EMIT {uid} {script} rc={erc}", flush=True)
                if erc != 0:
                    print(eout[-800:], flush=True)
        if uid == "ADV-0115":
            run([sys.executable, "-B", str(WAVE / "seed-stage" / "_g1_sync_manifest.py"), uid], 30)
        rows.append(measure(uid))
        OUT.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
    for uid in REMAINING:
        rows.append(measure(uid))
        OUT.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
    ok = sum(1 for r in rows if r["ok"])
    print(f"FINISH attempted={len(rows)} ok={ok} fail={len(rows)-ok}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
