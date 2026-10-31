"""IMP-0199 probe 1 (source, measured): zero egress and zero real spawns.

A full hermetic simulation of the emulatable fixture runs under
InstrumentedPorts. The counters are MEASURED by instrumented ports, not
asserted: socket connect/create_connection, subprocess.Popen and os.system
are all monkeypatched to count and block. The rail ledger (spawn_count /
egress_count) must AGREE with the ports snapshot - disagreement between
the two independent signals is a failure, not a picked winner.

Exit 0 iff both signals read zero and the run completed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE
for _ in range(6):
    if (REPO / "command-center" / "p2-wave").is_dir():
        break
    REPO = REPO.parent
for _p in (str(REPO), str(REPO / "tools" / "agentspec")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from agentspec.evals.fake_rail import FakeRail  # noqa: E402
from agentspec.evals.instrumented_ports import InstrumentedPorts  # noqa: E402
from agentspec.evals.simulator import simulate  # noqa: E402

workflow = json.loads((HERE / "fixtures" / "emulatable.json").read_text(encoding="utf-8"))["workflow"]

rail = FakeRail()
with InstrumentedPorts() as ports:
    result = simulate(workflow, rail=rail, ports=ports)
    snap = ports.snapshot()

d = result.as_dict()
checks = {
    "ran_to_completion": d["status"] == "RAN",
    "zero_egress_measured": snap["egress_attempts"] == 0,
    "zero_real_spawn_measured": snap["real_spawns"] == 0,
    "rail_ledger_agrees": rail.spawn_count == 0 and rail.egress_count == 0,
    "signals_agree": (snap["egress_attempts"] == rail.egress_count
                      and snap["real_spawns"] == rail.spawn_count),
    "gates_and_stopping_evaluated": d["gates_evaluated"] >= 1
        and d["stopping_rules_evaluated"] >= 1,
    "loop_body_executed": "body" in d["visited"] and d["steps"] >= 5,
    "no_refusal": d["refused_capabilities"] == [],
}

result_doc = {
    "probe": "probe1-zero-egress-spawn",
    "unit_id": "IMP-0199",
    "checks": checks,
    "ports_snapshot": snap,
    "rail_counters": {"spawn_count": rail.spawn_count, "egress_count": rail.egress_count},
    "simulation": d,
    "pass": all(checks.values()),
}
print(json.dumps(result_doc, sort_keys=True))
if not result_doc["pass"]:
    print("FAILED:IMP-0199-probe1 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0199-probe1 zero egress and zero real spawns (measured by instrumented ports)")
