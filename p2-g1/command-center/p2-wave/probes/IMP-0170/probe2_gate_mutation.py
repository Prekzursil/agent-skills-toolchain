"""IMP-0170 probe 2 (source, mutant set + mutation control): 20/20.

Changing ONE gate predicate changes the fingerprint for 20/20 mutants.
Mutation control (receipt T3): a topology-only mutation (an edge rewired,
predicates untouched) is detected WITH topology in the hash and MISSED
without it - proving topology is load-bearing, not decorative. A
predicate-equality control proves each mutation actually changed the gate.

Exit 0 iff 20/20 and both controls hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fingerprint  # noqa: E402
import workflows_lib as WL  # noqa: E402

base = WL.base_workflow()
base_fp = fingerprint.fingerprint(base)
base_fp_nt = fingerprint.fingerprint(base, include_topology=False)

rows = []
all_changed = True
preds_all_differ = True
for name, idx, new_gate in WL.MUTATIONS:
    mutant = WL.gate_mutant(base, name, idx, new_gate)
    pred_differ = mutant["stages"][idx].get("gate") != base["stages"][idx].get("gate")
    fp = fingerprint.fingerprint(mutant)
    changed = fp != base_fp
    all_changed = all_changed and changed
    preds_all_differ = preds_all_differ and pred_differ
    rows.append({"name": name, "changed": changed, "pred_differ": pred_differ, "sha256": fp})

# topology-only mutation: rewire refine_claims -> act_publish to a skip edge
topo_mutant = WL.base_workflow()
topo_mutant["edges"][2] = ["plan_batches", "act_publish"]
topo_detected_with = fingerprint.fingerprint(topo_mutant) != base_fp
topo_detected_without = (
    fingerprint.fingerprint(topo_mutant, include_topology=False) != base_fp_nt
)

checks = {
    "count_20": len(rows) == 20,
    "gate_mutation_changes_fingerprint_20_over_20": all_changed,
    "mutations_real": preds_all_differ,
    "topology_load_bearing_with": topo_detected_with,
    "topology_free_misses_topology_mutation": topo_detected_without is False,
    "topology_free_still_sees_gate_change": (
        fingerprint.fingerprint(WL.gate_mutant(base, "ingest_all_to_any", 0, WL.MUTATIONS[0][2]),
                                include_topology=False)
        != base_fp_nt
    ),
}

result = {
    "probe": "probe2-gate-mutation",
    "unit_id": "IMP-0170",
    "base_sha256": base_fp,
    "count": str(sum(1 for r in rows if r["changed"])) + "/20",
    "checks": checks,
    "rows": [{"name": r["name"], "changed": r["changed"], "sha256": r["sha256"]} for r in rows],
    "topology_control": {
        "mutation": "edge[2] plan_batches->act_publish rewire",
        "detected_with_topology": topo_detected_with,
        "detected_without_topology": topo_detected_without,
    },
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0170-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0170-probe2 gate mutation 20/20, topology load-bearing")
