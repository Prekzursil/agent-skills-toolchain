#!/usr/bin/env python3
"""Detached, session-independent re-run of BLD-0037's two probes at the
unit-contract 3600s per-probe budget. Survives the reviewer session that
launched it; logs land next to this script. Started by the wave-3 shard-6
independent reviewer on 2026-10-26 because the 600s re-run budget timed out
three times (reviewer run2, run3, canonical gate) while the unit verdict
(FAIL on receipt_core 41 / output_schema 42 / manifest-row sha mismatch)
does not depend on this outcome."""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PROBES = [
    "command-center/p2-wave/probes/BLD-0037/probe1_recall_controls.py",
    "command-center/p2-wave/probes/BLD-0037/probe2_contradiction_anchors.py",
]

for rel in PROBES:
    t0 = time.time()
    try:
        cp = subprocess.run(
            [sys.executable, "-B", str(REPO / rel)],
            cwd=str(REPO), capture_output=True, text=True,
            timeout=3600, encoding="utf-8", errors="replace",
        )
        rc, tail = cp.returncode, (cp.stdout or "") + (cp.stderr or "")
    except subprocess.TimeoutExpired:
        rc, tail = 124, "TIMEOUT after 3600s"
    dt = time.time() - t0
    marker = "SUCCESS:" if (rc == 0 and "SUCCESS:" in tail and "FAILED:" not in tail) else "NOT-CLEAN:"
    print(f"{marker}{Path(rel).name} rc={rc} seconds={dt:.0f}", flush=True)
    log = HERE / ("re0037_detached_" + Path(rel).name + ".log")
    log.write_text(tail, encoding="utf-8", errors="replace")
print("re0037-detached-finished", flush=True)
