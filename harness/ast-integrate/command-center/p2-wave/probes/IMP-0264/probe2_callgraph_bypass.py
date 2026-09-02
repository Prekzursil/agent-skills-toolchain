#!/usr/bin/env python3
"""IMP-0264 probe 2: call-graph check; planted direct-write bypass must FIRE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))

from council.kernel import (  # noqa: E402
    audit_source,
    audit_topology_callgraph,
    topology_module_paths,
)

PLANTED = """
class BypassMutant:
    def plan_round(self, round_index, roster, **kw):
        for pid in roster:
            participant = type("P", (), {})()
            participant.output = "planted-bypass"
        events = []
        events.append({"kind": "TURN", "bypass": True})
        outputs = {}
        outputs["x"] = "direct"
        return None
"""

HONEST = """
class HonestPlanner:
    def plan_round(self, round_index, roster, *, timeout_ms, max_chars, obligations):
        turns = tuple((pid, tuple(obligations), timeout_ms, max_chars) for pid in roster)
        return (round_index, turns)
"""


def main() -> int:
    topo_paths = topology_module_paths(REPO)
    honest_disk = audit_topology_callgraph(topo_paths)
    bypass_path = HERE / "fixtures" / "bypass_topology.py"
    bypass_disk = audit_topology_callgraph([bypass_path])

    planted = audit_source(PLANTED, label="in-memory-mutant")
    honest_mem = audit_source(HONEST, label="in-memory-honest")

    honest_silent = honest_disk["finding_count"] == 0 and honest_mem == []
    bypass_ids = {f["id"] for f in bypass_disk["findings"]}
    planted_ids = {f["id"] for f in planted}
    bypass_fires = "direct-write-output" in bypass_ids and "direct-write-events" in bypass_ids
    planted_fires = "direct-write-output" in planted_ids and "direct-write-events" in planted_ids
    both_states = honest_silent and bypass_fires and planted_fires

    report = {
        "probe": "probe2-callgraph-bypass",
        "unit_id": "IMP-0264",
        "honest_modules": [str(p.relative_to(REPO)) for p in topo_paths],
        "honest_finding_count": honest_disk["finding_count"],
        "honest_memory_findings": honest_mem,
        "honest_silent": honest_silent,
        "bypass_path": str(bypass_path.relative_to(REPO)),
        "bypass_finding_count": bypass_disk["finding_count"],
        "bypass_ids": sorted(bypass_ids),
        "bypass_fires": bypass_fires,
        "planted_ids": sorted(planted_ids),
        "planted_fires": planted_fires,
        "both_states": {
            "good_silent": honest_silent,
            "bad_fires": bypass_fires and planted_fires,
        },
        "pass": both_states,
        "findings_bypass": bypass_disk["findings"],
        "findings_planted": planted,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["pass"]:
        print("FAILED:IMP-0264-probe2 call-graph bypass")
        return 1
    print("SUCCESS:IMP-0264-probe2 call-graph check fires on direct-write bypass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
