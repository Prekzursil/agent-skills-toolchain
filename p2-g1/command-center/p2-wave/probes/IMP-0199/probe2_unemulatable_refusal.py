"""IMP-0199 probe 2 (source, both-states): unemulatable capability REFUSED by name.

The unemulatable fixture demands live-model-infer and network-egress. The
simulator must REFUSE it with status REFUSED naming BOTH capabilities
BEFORE any node runs - a silently faked capability is worse than a
refusal. The emulatable twin (same shape, hermetic capabilities) runs
clean: the refusal is capability-specific, not shape-specific. Defense in
depth is also checked: a rail whose can_honestly_emulate is overridden to
lie STILL refuses a NEVER_EMULATABLE capability at execute_node.

Exit 0 iff refusal names the capability and the twin runs.
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

from agentspec.evals.fake_rail import (  # noqa: E402
    NEVER_EMULATABLE,
    UnemulatableCapability,
    FakeRail,
)
from agentspec.evals.instrumented_ports import InstrumentedPorts  # noqa: E402
from agentspec.evals.simulator import simulate  # noqa: E402

live = json.loads((HERE / "fixtures" / "unemulatable.json").read_text(encoding="utf-8"))["workflow"]
twin = json.loads((HERE / "fixtures" / "emulatable.json").read_text(encoding="utf-8"))["workflow"]

with InstrumentedPorts() as ports:
    refused = simulate(live)
    snap = ports.snapshot()

d = refused.as_dict()
twin_res = simulate(twin).as_dict()

class LyingRail(FakeRail):
    def can_honestly_emulate(self, capability: str) -> bool:
        return True

lying_rail = LyingRail()
depth_node = {"id": "n1", "kind": "unit", "capabilities": ["live-model-infer"]}
depth_fired = False
try:
    lying_rail.execute_node(depth_node)
except UnemulatableCapability:
    depth_fired = True

checks = {
    "refused_status": d["status"] == "REFUSED",
    "names_live_model_infer": "live-model-infer" in d["refused_capabilities"],
    "names_network_egress": "network-egress" in d["refused_capabilities"],
    "refusal_message_names_both": (
        "live-model-infer" in d["refusal_message"]
        and "network-egress" in d["refusal_message"]
    ),
    "nothing_ran_before_refusal": d["steps"] == 0 and d["visited"] == [],
    "zero_egress_on_refused_run": snap["egress_attempts"] == 0 and snap["real_spawns"] == 0,
    "emulatable_twin_runs": twin_res["status"] == "RAN" and twin_res["steps"] >= 5,
    "never_emulatable_registry_nonempty": len(NEVER_EMULATABLE) >= 4,
    "lying_rail_still_refuses_never_set": depth_fired,
    "both_states": d["status"] == "REFUSED" and twin_res["status"] == "RAN",
}

result = {
    "probe": "probe2-unemulatable-refusal",
    "unit_id": "IMP-0199",
    "checks": checks,
    "refused": d,
    "twin": {"status": twin_res["status"], "steps": twin_res["steps"]},
    "never_emulatable": sorted(NEVER_EMULATABLE),
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0199-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0199-probe2 unemulatable refused by name; twin runs clean")
