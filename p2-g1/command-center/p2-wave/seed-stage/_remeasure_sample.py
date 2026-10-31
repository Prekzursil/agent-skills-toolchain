#!/usr/bin/env python3
"""Stratified local G-1 remesure. Run under WSL so probe env prefixes work."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
REPO = WAVE.parents[1]
IDS = json.loads((WAVE / "ovh-monitor" / "local-sample-ids.json").read_text(encoding="utf-8"))["ids"]
OUT = WAVE / "ovh-monitor" / "local-sample-remeasure.jsonl"
SUMMARY = WAVE / "ovh-monitor" / "local-sample-remeasure.json"
SCRIPT = WAVE / "_measure_one_delivered.py"


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    ok = fail = 0
    fails = []
    for i, uid in enumerate(IDS, 1):
        p = subprocess.run(
            [sys.executable, str(SCRIPT), uid],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=180,
        )
        lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
        last = lines[-1] if lines else f"exit={p.returncode}"
        rec = {"id": uid, "ok": last.startswith("SUCCESS:delivered"), "line": last[:300]}
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        if rec["ok"]:
            ok += 1
            mark = "OK"
        else:
            fail += 1
            fails.append(uid)
            mark = "NO"
        print(f"{i}/{len(IDS)} {mark} {uid} {last[:140]}", flush=True)
    payload = {"n": len(IDS), "ok": ok, "fail": fail, "fail_ids": fails}
    SUMMARY.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"SAMPLE ok={ok} fail={fail} n={len(IDS)}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
