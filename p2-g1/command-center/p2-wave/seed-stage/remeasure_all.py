#!/usr/bin/env python3
"""Re-measure every completed.json id on this box. Writes /opt/p2/remeasure.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/p2/ast-integrate")
WAVE = ROOT / "command-center" / "p2-wave"
SCRIPT = WAVE / "_measure_one_delivered.py"
DONE = Path("/opt/p2/completed.json")
OUT = Path("/opt/p2/remeasure.json")
LOG = Path("/opt/p2/remeasure.out")
TIMEOUT = 60


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ids = []
    if DONE.exists():
        try:
            ids = [str(x) for x in (json.loads(DONE.read_text()).get("ids") or [])]
        except Exception:
            ids = []
    results = []
    ok_n = fail_n = err_n = 0
    for i, uid in enumerate(ids, 1):
        rec = {"id": uid, "i": i, "n": len(ids)}
        if not SCRIPT.is_file():
            rec.update({"ok": False, "rc": 2, "line": "FAILED:measure-missing"})
            err_n += 1
            results.append(rec)
            continue
        try:
            p = subprocess.run(
                [sys.executable, str(SCRIPT), uid],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
            lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
            last = lines[-1] if lines else f"exit={p.returncode}"
            rec["rc"] = p.returncode
            rec["line"] = last[:400]
            rec["ok"] = last.startswith("SUCCESS:delivered")
        except subprocess.TimeoutExpired:
            rec.update({"ok": False, "rc": 124, "line": "FAILED:timeout"})
        except Exception as exc:
            rec.update({"ok": False, "rc": 99, "line": f"FAILED:exc {exc}"[:400]})
        if rec.get("ok"):
            ok_n += 1
        else:
            fail_n += 1
        results.append(rec)
        if i % 10 == 0 or i == len(ids):
            msg = f"{utc()} {i}/{len(ids)} ok={ok_n} fail={fail_n}\n"
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(msg)
    payload = {
        "ts": utc(),
        "n": len(ids),
        "ok": ok_n,
        "fail": fail_n,
        "results": results,
        "fail_ids": [r["id"] for r in results if not r.get("ok")],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"REMEASURE n={len(ids)} ok={ok_n} fail={fail_n}", flush=True)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
