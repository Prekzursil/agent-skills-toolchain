"""IMP-0167 probe 2 (verifier, adversarial): reconciliation is required-subset-of-
allowed as a SET DIFFERENCE, never a substring match on prose.

Trap: required tool "Read" is a substring of the unit's declared "ReadWrite".
A substring matcher reconciles it (IMPORTED); the set method must BLOCK with
missing=['Read']. The honest twin (declared ["Read"]) imports clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "workflow_foundry"))
import tool_requirements as TR  # noqa: E402

RAW = HERE / "probe2-subset-not-substring.raw.txt"

trap = {"candidate_id": "cand-read-substring-trap",
        "stages": [{"name": "inspect", "tools": ["Read"]}]}
res_trap = TR.import_candidate(trap, unit_permissions=["ReadWrite"])
twin = {"candidate_id": "cand-read-honest",
        "stages": [{"name": "inspect", "tools": ["Read"]}]}
res_twin = TR.import_candidate(twin, unit_permissions=["Read"])

# The banned detector, implemented independently: substring reconciliation.
def substring_reconcile(required, declared):
    blob = " ".join(declared)
    return [r for r in required if r not in blob]

prose_missing = substring_reconcile(["Read"], ["ReadWrite"])
lines = [
    f"prose.status={'IMPORTED' if not prose_missing else 'BLOCKED'} "
    f"silent.status={res_trap.status} Read/ReadWrite missing={res_trap.missing_capabilities}",
    f"twin.status={res_twin.status} twin.missing={res_twin.missing_capabilities}",
]
assert res_trap.status == "BLOCKED", "substring trap imported: reconciliation is prose"
assert res_trap.missing_capabilities == ["Read"], res_trap.missing_capabilities
assert prose_missing == [], "trap precondition broke: substring matcher no longer fooled"
assert res_twin.status == "IMPORTED", "honest twin blocked: over-firing"
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"trap_status": res_trap.status,
                              "trap_missing": res_trap.missing_capabilities,
                              "substring_matcher_would_import": True,
                              "twin_status": res_twin.status,
                              "method": res_trap.method}))
print("SUCCESS:IMP-0167-probe2 reconciliation is set-subset, not substring")
