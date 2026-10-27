"""IMP-0167 probe 1 (source, both-states): a candidate requiring an absent tool
(WebFetch) is BLOCKED at import with the capability named; the grantable twin
imports clean.

Exit 0 iff both states hold.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "workflow_foundry"))
from tool_requirements import import_candidate  # noqa: E402

RAW = HERE / "probe1-absent-tool.raw.txt"

UNIT_PERMISSIONS = ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]
HOST_GRANTABLE = ["Bash", "Edit", "Glob", "Grep", "Read", "Write"]

absent = json.loads((HERE / "fixtures" / "candidate_absent_webfetch.json").read_text(encoding="utf-8"))
twin = json.loads((HERE / "fixtures" / "candidate_grantable_twin.json").read_text(encoding="utf-8"))

res_bad = import_candidate(absent, unit_permissions=UNIT_PERMISSIONS, host_grantable=HOST_GRANTABLE)
res_good = import_candidate(twin, unit_permissions=UNIT_PERMISSIONS, host_grantable=HOST_GRANTABLE)

lines = [
    json.dumps({
        "candidate_id": absent["candidate_id"], "status": res_bad.status,
        "required": sorted(__import__("tool_requirements").extract_tool_requirements(absent)),
        "missing_capabilities": res_bad.missing_capabilities,
        "missing_from_host": res_bad.missing_from_host,
        "missing_from_unit": res_bad.missing_from_unit,
        "unit_declared": UNIT_PERMISSIONS, "host_grantable": HOST_GRANTABLE,
        "method": res_bad.method, "allowed": sorted(set(UNIT_PERMISSIONS) | set(HOST_GRANTABLE)),
    }),
    f"status={res_bad.status} missing={res_bad.missing_capabilities}",
    f"twin.status={res_good.status} twin.missing={res_good.missing_capabilities}",
]
assert res_bad.status == "BLOCKED", "absent-tool candidate was not blocked"
assert res_bad.missing_capabilities == ["WebFetch"], res_bad.missing_capabilities
assert res_good.status == "IMPORTED", "grantable twin did not import clean"
assert res_good.missing_capabilities == []
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"absent_status": res_bad.status,
                              "missing": res_bad.missing_capabilities,
                              "twin_status": res_good.status}))
print("SUCCESS:IMP-0167-probe1 absent tool BLOCKED with capability named, twin imports")
