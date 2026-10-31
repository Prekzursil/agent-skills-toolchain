#!/usr/bin/env python3
"""Re-measure the 281 prior log-success IDs that this box has in completed.json."""
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
PRIOR = WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json"
OUT = Path("/opt/p2/remeasure-281.json")
LOG = Path("/opt/p2/remeasure-281.out")
TIMEOUT = 90


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    prior = set()
    if PRIOR.exists():
        try:
            prior = set(str(x) for x in (json.loads(PRIOR.read_text()).get("remaining_ids") or []))
        except Exception:
            prior = set()
    done = []
    if DONE.exists():
        try:
            done = [str(x) for x in (json.loads(DONE.read_text()).get("ids") or [])]
        except Exception:
            done = []
    ids = [u for u in done if u in prior]
    prev = {}
    if OUT.exists():
        try:
            for r in (json.loads(OUT.read_text()).get("results") or []):
                if r.get("id"):
                    prev[str(r["id"])] = r
        except Exception:
            prev = {}
    results = []
    ok_n = fail_n = 0
    for i, uid in enumerate(ids, 1):
        old = prev.get(uid)
        if old and old.get("ok"):
            results.append(old)
            ok_n += 1
            continue
        rec = {"id": uid, "i": i, "n": len(ids)}
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
        if i % 5 == 0 or i == len(ids):
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(f"{utc()} {i}/{len(ids)} ok={ok_n} fail={fail_n}\n")
    payload = {
        "ts": utc(),
        "prior_n": len(prior),
        "n": len(ids),
        "ok": ok_n,
        "fail": fail_n,
        "results": results,
        "fail_ids": [r["id"] for r in results if not r.get("ok")],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"REMEASURE-281 n={len(ids)} ok={ok_n} fail={fail_n}", flush=True)
    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
