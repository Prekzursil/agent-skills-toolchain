#!/usr/bin/env python
"""Both-states probe on the ONE authorization control Wave 1 actually shipped:
DSL-SEM-011 (deny-by-default tool policy), platform/lib/wfdsl/semantics.py:479-506.

The security-first architecture's central claim is that this control is correct
but its SCOPE is one plane out of three. To claim that honestly I must first
prove the control works. Four states:

  S1 absent tool_policy  + a tool request     -> EXPECT violation (fail CLOSED)
  S2 allow-listed tool                        -> EXPECT clean    (no false positive)
  S3 explicitly denied tool                   -> EXPECT violation
  S4 default:allow + unlisted tool            -> EXPECT clean    (policy honoured)

A probe that fires in all four states, or is silent in all four, measures
nothing (rules/common/single-signal-verification.md 3b).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform" / "lib"))

from wfdsl import semantics  # noqa: E402

BASE: dict = {
    "dsl_version": "1.0.0",
    "id": "probe-denydefault",
    "name": "deny-default probe",
    "version": "1.0.0",
    "stages": [
        {
            "id": "s1",
            "kind": "agent",
            "tool_permissions": ["Read", "mcp__cloud-hub__modal_sandbox_exec"],
        }
    ],
}


def run(name: str, doc: dict) -> dict:
    res = semantics.check_workflow(doc)
    hit = next((r for r in res if r.rule == "DSL-SEM-011"), None)
    if hit is None:
        return {
            "state": name,
            "rule_found": False,
            "rules_present": [r.rule for r in res][:40],
        }
    return {
        "state": name,
        "rule_found": True,
        "checked": hit.checked,
        "severity": hit.severity,
        "n_violations": len(hit.violations),
        "violations": [list(map(str, v)) for v in hit.violations][:4],
    }


import copy  # noqa: E402

s1 = copy.deepcopy(BASE)  # no tool_policy at all
s2 = copy.deepcopy(BASE)
s2["tool_policy"] = {
    "default": "deny",
    "allow": ["Read", "mcp__cloud-hub__modal_sandbox_exec"],
}
s3 = copy.deepcopy(BASE)
s3["tool_policy"] = {
    "default": "deny",
    "allow": ["Read", "mcp__cloud-hub__modal_sandbox_exec"],
    "deny": ["mcp__cloud-hub__modal_sandbox_exec"],
}
s4 = copy.deepcopy(BASE)
s4["tool_policy"] = {"default": "allow"}

out = {
    "probe": "secfirst_denydefault_bothstates",
    "S1_absent_policy": run("S1_absent_policy", s1),
    "S2_allowlisted": run("S2_allowlisted", s2),
    "S3_explicit_deny": run("S3_explicit_deny", s3),
    "S4_default_allow": run("S4_default_allow", s4),
}

exp = {
    "S1_absent_policy": True,
    "S2_allowlisted": False,
    "S3_explicit_deny": True,
    "S4_default_allow": False,
}
verdict = {}
for k, want_fire in exp.items():
    got = out[k].get("n_violations")
    verdict[k] = {
        "expected_fire": want_fire,
        "n_violations": got,
        "ok": (got is not None) and ((got > 0) == want_fire),
    }
out["verdict"] = verdict
out["all_four_as_expected"] = all(v["ok"] for v in verdict.values())
out["discriminating"] = (
    len({(v["n_violations"] or 0) > 0 for v in verdict.values()}) == 2
)

# ---- the ASYMMETRY claim: which rules exist per plane, and does the WORK-UNIT
# plane carry any tool-authorization rule at all?
wf_rules = [(r.rule, r.description, r.severity) for r in semantics.check_workflow(s2)]
cat = json.loads(
    (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
wu_rules = [
    (r.rule, r.description, r.severity)
    for r in semantics.check_work_units(cat["work_units"][:200])
]
import re as _re  # noqa: E402

AUTHZ = _re.compile(
    r"tool|permission|policy|deny|allow|approval|privileg|substrate", _re.I
)
out["plane_asymmetry"] = {
    "workflow_dsl_rules_n": len(wf_rules),
    "workflow_dsl_authz_rules": [
        r for r in wf_rules if AUTHZ.search(r[0] + " " + r[1])
    ],
    "work_unit_rules_n": len(wu_rules),
    "work_unit_rules": [r[0] for r in wu_rules],
    "work_unit_authz_rules": [r for r in wu_rules if AUTHZ.search(r[0] + " " + r[1])],
}

Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=1, default=str), encoding="utf-8"
)
for k in ("S1_absent_policy", "S2_allowlisted", "S3_explicit_deny", "S4_default_allow"):
    print(
        f"{k:20s} viol={out[k].get('n_violations')} checked={out[k].get('checked')} ok={verdict[k]['ok']}"
    )
print(
    "all_four_as_expected:",
    out["all_four_as_expected"],
    "| discriminating:",
    out["discriminating"],
)
print(
    "SUCCESS:secfirst-denydefault"
    if out["all_four_as_expected"]
    else "FAILED:secfirst-denydefault not-all-expected"
)
