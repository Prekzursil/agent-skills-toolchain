"""IMP-0182 probe 2 (verifier): a valid splice runs end to end on the fake rail
and its executed plan differs from BOTH parents - computed, guarding against a
no-op fusion that silently returns one parent.

Exit 0 iff all three plans run clean and pairwise differ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_splice as SS  # noqa: E402
from fake_rail import FakeRail  # noqa: E402

RAW = HERE / "probe2-plan-differs.raw.txt"

host = SS.host_workflow()
res = SS.splice(host, SS.donor_matching())
assert res["status"] == "emitted"
donor_wf = {"id": "wf.donor.extract-v2", "stages": [SS.donor_matching()], "edges": []}

rail = FakeRail()
run_host, run_donor, run_fusion = rail.run_many([host, donor_wf, res["fusion"]])
lines = [json.dumps({"host": run_host["plan_sha256"],
                     "donor": run_donor["plan_sha256"],
                     "fusion": run_fusion["plan_sha256"],
                     "network_count": rail.network_count,
                     "spawn_count": rail.spawn_count})]
assert run_fusion["plan_sha256"] != run_host["plan_sha256"], "fusion silently IS the host"
assert run_fusion["plan_sha256"] != run_donor["plan_sha256"], "fusion silently IS the donor"
assert run_host["plan_sha256"] != run_donor["plan_sha256"], "parents identical: fixture broken"
assert rail.network_count == 0 and rail.spawn_count == 0, "fake rail left the box"
# The fused plan is a superset: every parent stage name appears in it.
fused_names = {s["name"] for s in res["fusion"]["stages"]}
assert {s["name"] for s in host["stages"]} <= fused_names
assert SS.donor_matching()["name"] in fused_names
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"host": run_host["plan_sha256"][:16],
                              "donor": run_donor["plan_sha256"][:16],
                              "fusion": run_fusion["plan_sha256"][:16],
                              "fusion_differs_from_both": True,
                              "network_count": 0, "spawn_count": 0}))
print("SUCCESS:IMP-0182-probe2 spliced plan differs from both parents")
