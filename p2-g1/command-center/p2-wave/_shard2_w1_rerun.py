#!/usr/bin/env python3
"""Re-run failed shard2 units after fixes; then run the G-1 measure on each."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
spec = importlib.util.spec_from_file_location(
    "resume", P2 / "command-center/p2-wave/_shard2_w1_resume.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

UNITS = sys.argv[1:] or ["AUD-0033", "AUD-0043", "AUD-0066", "AUD-0084", "AUD-0096"]
cat = m.catalog()
fails = 0
for uid in UNITS:
    t0 = time.time()
    try:
        st, detail = m.do_closed(uid, cat[uid])
    except Exception as exc:
        st, detail = "FAILED", "%s: %s" % (type(exc).__name__, exc)
    print("%s :: %s :: %s :: %.1fs" % (uid, st, detail, time.time() - t0), flush=True)
    meas = subprocess.run(
        [sys.executable, "-B", str(P2 / "command-center/p2-wave/_measure_one_delivered.py"), uid],
        cwd=str(P2), capture_output=True, text=True, timeout=900)
    tail = (meas.stdout + meas.stderr).strip().splitlines()
    verdict = tail[-1] if tail else "no-output"
    print("%s :: MEASURE rc=%s :: %s" % (uid, meas.returncode, verdict), flush=True)
    if meas.returncode != 0:
        fails += 1
print("RERUN-SUMMARY fails=%d" % fails)
raise SystemExit(1 if fails else 0)
