"""IMP-0222 probe 1 (source): planted hang in a 50-unit cohort delays only itself.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0222/probe1_planted_hang_49_of_50.py
Exit 0 iff 49/50 complete, the hung unit carries a TIMEOUT-TYPED terminal record
(not absent), and the cohort wall stays bounded by the declared timeout instead of
the hang duration.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))  # agentspec pkg home
sys.path.insert(0, str(W / "tools" / "agentrail"))  # LAST -> wins; tools/agentspec carries a shadow agentrail/
from agentrail.runner import run_cohort_isolated  # noqa: E402

jobs = {}
for i in range(50):
    if i == 7:
        jobs["U-0007"] = (lambda: time.sleep(8.0) or "done")  # the planted hang
    else:
        jobs["U-%04d" % i] = (lambda: time.sleep(0.001) or "done")

report = run_cohort_isolated(jobs, timeout_s=0.5, max_workers=10)
by_id = {r["unit_id"]: r for r in report["ledger"]}
hung = by_id["U-0007"]
ok = (
    report["submitted"] == 50
    and report["completed_count"] == 49
    and report["timed_out_count"] == 1
    and report["timed_out_units"] == ["U-0007"]
    and hung["status"] == "timeout-typed"
    and hung.get("declared_timeout_s") == 0.5
    and report["wall_s"] < 1.5
    and report["wall_s"] < 8.0  # the hang duration itself is NOT the cohort wall
)
out = {"probe": "probe1-planted-hang-49of50", "unit_id": "IMP-0222",
       "completed": report["completed_count"], "timed_out": report["timed_out_units"],
       "hung_record": hung, "wall_s": report["wall_s"],
       "abandoned_workers": report["abandoned_workers"], "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-hang.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0222-probe1 cohort deadlocked or hang untyped")
    raise SystemExit(1)
print("SUCCESS:IMP-0222-probe1 planted hang: 49/50 complete, 1 timeout-typed, wall bounded")
