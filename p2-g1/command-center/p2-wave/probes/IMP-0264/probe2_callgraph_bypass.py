"""IMP-0264 probe 2: call-graph audit - no topology bypasses the kernel.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0264/probe2_callgraph_bypass.py
Exit 0 iff the live source audit (tools/council/kernel.audit_topology_callgraph)
is SILENT over the real topology modules and FIRES on the planted bypass
fixture (direct-write-output and direct-write-events): a both-states proof
that the no-direct-write check is load-bearing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "council"))
from kernel import audit_topology_callgraph, topology_module_paths  # noqa: E402

bypass_path = Path(__file__).resolve().parent / "fixtures" / "bypass_topology.py"

good = audit_topology_callgraph(topology_module_paths(W))
bad = audit_topology_callgraph([bypass_path])

checks = {
    "good_topology_silent": good["finding_count"] == 0,
    "bypass_fires": bad["finding_count"] >= 2,
    "fires_direct_write_output": any(f["id"] == "direct-write-output" for f in bad["findings"]),
    "fires_direct_write_events": any(f["id"] == "direct-write-events" for f in bad["findings"]),
    "bypass_fixture_exists": bypass_path.is_file(),
}
both_states = {"bad_fires": bool(checks["bypass_fires"]), "good_silent": checks["good_topology_silent"]}
ok = all(checks.values())
out = {"probe": "probe2-callgraph-bypass", "unit_id": "IMP-0264",
       "good_topology_files": len(topology_module_paths(W)),
       "bypass_finding_count": bad["finding_count"],
       "bypass_ids": sorted({f["id"] for f in bad["findings"]}),
       "bypass_path": bypass_path.relative_to(W).as_posix(),
       "both_states": both_states,
       "checks": checks, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-callgraph.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0264-probe2 %s" % [k for k, v in checks.items() if not v])
    raise SystemExit(1)
print("SUCCESS:IMP-0264-probe2 real topology silent; planted direct-write bypass FIRES")
