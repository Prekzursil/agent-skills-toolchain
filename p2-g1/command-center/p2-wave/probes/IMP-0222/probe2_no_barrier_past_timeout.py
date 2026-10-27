"""IMP-0222 probe 2 (verifier): no barrier waits past a declared timeout - asserted
from timestamps in the ledger, with the barrier-coupled counterfactual as control.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0222/probe2_no_barrier_past_timeout.py
Exit 0 iff every completed unit's measured elapsed <= its declared timeout (timestamp
audit), the cohort wall does not include the hang, and the COUPLED-BARRIER
counterfactual on the same cohort stalls ALL siblings (both-states control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))  # agentspec pkg home
sys.path.insert(0, str(W / "tools" / "agentrail"))  # LAST -> wins; tools/agentspec carries a shadow agentrail/
from agentrail.runner import (  # noqa: E402
    TIMEOUT,
    CoupledBarrierRunner,
    IsolatedPipelineRunner,
    make_cohort,
    run_cohort_isolated,
)

report = run_cohort_isolated(
    {("U-%04d" % i): ((lambda: __import__("time").sleep(8.0)) if i == 7 else (lambda: __import__("time").sleep(0.001))) for i in range(50)},
    timeout_s=0.5, max_workers=10,
)
completed = [r for r in report["ledger"] if r["status"] == "completed"]
audit_ok = all(r["elapsed_s"] <= 0.5 for r in completed)
audit_ok = audit_ok and report["no_completed_unit_past_timeout"] is True
# barrier excess: cohort wall may exceed timeout only by scheduling slop, never by the hang
barrier_ok = report["barrier_excess_s"] < 0.5 and report["wall_s"] < 1.5

cohort = make_cohort(n=50, hang_at=7)
coupled_summary = CoupledBarrierRunner().run(cohort)
isolated_summary = IsolatedPipelineRunner().run(cohort)
control_ok = (
    coupled_summary["terminal"] == TIMEOUT
    and coupled_summary["completed"] == []
    and isolated_summary["terminal"] == "completed"
    and len(isolated_summary["completed"]) == 49
)

ok = audit_ok and barrier_ok and control_ok
out = {"probe": "probe2-no-barrier-past-timeout", "unit_id": "IMP-0222",
       "timestamp_audit_ok": audit_ok,
       "barrier_excess_s": report["barrier_excess_s"], "wall_s": report["wall_s"],
       "barrier_ok": barrier_ok,
       "coupled_terminal": coupled_summary["terminal"],
       "coupled_completed": len(coupled_summary["completed"]),
       "isolated_completed": len(isolated_summary["completed"]),
       "control_ok": control_ok, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-barrier.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0222-probe2 barrier waited past timeout or control failed")
    raise SystemExit(1)
print("SUCCESS:IMP-0222-probe2 timestamp audit clean; barrier bounded; coupled counterfactual stalls")
