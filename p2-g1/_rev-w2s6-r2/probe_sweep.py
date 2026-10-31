#!/usr/bin/env python3
"""Run the canonical _measure_one_delivered.py for each shard-6 w2 unit.
Captures rc + final SUCCESS/FAILED line per unit -> probe_sweep_out.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = [
    "BLD-0016", "BLD-0023", "BLD-0024", "BLD-0027", "BLD-0028",
    "BLD-0031", "BLD-0032", "BLD-0033", "BLD-0035", "BLD-0037",
    "BLD-0040", "BLD-0042",
]

def main() -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    out = {}
    for uid in UNITS:
        r = subprocess.run(
            [sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid],
            cwd=str(REPO), capture_output=True, text=True,
            timeout=2700, env=env,
        )
        text = ((r.stdout or "") + (r.stderr or "")).strip()
        lines = text.splitlines()
        last = lines[-1] if lines else ""
        probe_lines = [l for l in lines if l.startswith("probe[")]
        out[uid] = {
            "rc": r.returncode,
            "last": last[:200],
            "probes": probe_lines[:6],
            "tail": text[-800:] if r.returncode != 0 else "",
        }
        print(uid, "rc=%d" % r.returncode, last[:120], flush=True)
    Path(__file__).with_name("probe_sweep_out.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print("SWEEP-DONE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
