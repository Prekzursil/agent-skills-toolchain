#!/usr/bin/env python3
"""Measure every class-mod ID. Writes jsonl + summary. No bash $id."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(os.environ.get("AST_INTEGRATE_ROOT") or Path.home() / "p2-g1")
IDS = REPO / "command-center" / "p2-wave" / "seed-stage" / "_class_mod_ids.txt"
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
OUT = Path("/tmp/g1-class-mod.measure.jsonl")


def main() -> int:
    ids = [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ok = fail = 0
    OUT.write_text("", encoding="utf-8")
    for i, uid in enumerate(ids, 1):
        print(f"===== MEASURE {uid} ({i}/{len(ids)}) =====", flush=True)
        p = subprocess.run(
            [sys.executable, "-B", str(MEASURE), uid],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env={**os.environ, "AST_INTEGRATE_ROOT": str(REPO), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        last = text.splitlines()[-1] if text.splitlines() else f"FAILED:delivered {uid} no-output"
        delivered = last.startswith("SUCCESS:delivered ")
        if delivered:
            ok += 1
        else:
            fail += 1
            for line in text.splitlines()[-12:]:
                print(line, flush=True)
        print(last, flush=True)
        rec = {"id": uid, "ok": delivered, "line": last, "rc": p.returncode}
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    print(f"===== SUMMARY n={len(ids)} ok={ok} fail={fail} =====", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
