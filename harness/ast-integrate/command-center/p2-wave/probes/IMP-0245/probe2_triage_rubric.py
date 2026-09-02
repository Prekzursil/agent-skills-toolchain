#!/usr/bin/env python3
"""Named probe 2: triage severity comes from the declared rubric.

A report labelled CRITICAL with low-axis inputs must score LOW. A report
labelled low with high-axis inputs must score CRITICAL. Swapping the
adjective must not change the ordinal. Premortem halt and committee REJECT
on unmet least-privilege are live on the same run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "blueprints" / "security"
sys.path.insert(0, str(LIB))

from risk_premortem import premortem  # noqa: E402
from standards_committee import review  # noqa: E402
from vulnerability_triage import triage  # noqa: E402

LOW_AXES = {
    "exploitability": "local",
    "blast_radius": "process",
    "evidence_class": "reporter-claim",
}
HIGH_AXES = {
    "exploitability": "unauth-network",
    "blast_radius": "supply-chain",
    "evidence_class": "reproduced",
}


def main() -> int:
    a = triage({**LOW_AXES, "reporter_severity": "CRITICAL"})
    a_swap = triage({**LOW_AXES, "reporter_severity": "low"})
    b = triage({**HIGH_AXES, "reporter_severity": "low"})
    b_swap = triage({**HIGH_AXES, "reporter_severity": "CRITICAL"})

    if a["severity"] != "LOW":
        print("FAILED:IMP-0245-probe2 expected LOW got", a)
        return 1
    if a["severity_source"] != "rubric" or a["adjective_used_in_score"]:
        print("FAILED:IMP-0245-probe2 adjective leaked into score", a)
        return 1
    if a["reporter_severity"] != "CRITICAL":
        print("FAILED:IMP-0245-probe2 adjective not recorded", a)
        return 1
    if a["severity"] == a["reporter_severity"]:
        print("FAILED:IMP-0245-probe2 ordinal copied the adjective", a)
        return 1
    if a["score_total"] != a_swap["score_total"] or a["severity"] != a_swap["severity"]:
        print("FAILED:IMP-0245-probe2 adjective swap changed low-axes score", a, a_swap)
        return 1
    if b["severity"] != "CRITICAL":
        print("FAILED:IMP-0245-probe2 expected CRITICAL got", b)
        return 1
    if b["severity"] == b["reporter_severity"]:
        print("FAILED:IMP-0245-probe2 high-axes copied adjective", b)
        return 1
    if b["score_total"] != b_swap["score_total"] or b["severity"] != b_swap["severity"]:
        print("FAILED:IMP-0245-probe2 adjective swap changed high-axes score", b, b_swap)
        return 1

    pre = premortem(
        {
            "plan_id": "probe2",
            "observed_triggers": ["auto-loading agent config present"],
            "owner_accepted_risks": [],
        }
    )
    pre_ok = premortem({"plan_id": "probe2-control", "observed_triggers": [], "owner_accepted_risks": []})
    if not pre["halt"] or pre_ok["halt"]:
        print("FAILED:IMP-0245-probe2 premortem both-states", pre, pre_ok)
        return 1

    rejected = review(
        {
            "proposal_id": "probe2-unmet",
            "cited_standards": ["least-privilege"],
            "claims": {"permissions_subset": False},
        }
    )
    accepted = review(
        {
            "proposal_id": "probe2-met",
            "cited_standards": ["least-privilege"],
            "claims": {"permissions_subset": True},
        }
    )
    if rejected["verdict"] != "REJECT" or accepted["verdict"] != "ACCEPT":
        print("FAILED:IMP-0245-probe2 committee", rejected, accepted)
        return 1

    out = {
        "adjective_swap_invariant": True,
        "committee_accept": accepted["verdict"],
        "committee_reject": rejected["verdict"],
        "high_axes_severity": b["severity"],
        "low_axes_severity": a["severity"],
        "pass": True,
        "premortem_halt_on_autoload": pre["halt"],
        "premortem_silent_when_clean": (not pre_ok["halt"]),
        "probe": "probe2-triage-rubric",
        "reporter_adjective_low_axes": a["reporter_severity"],
        "severity_source": a["severity_source"],
        "unit_id": "IMP-0245",
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"low-axes adjective=CRITICAL severity={a['severity']} "
        f"high-axes adjective=low severity={b['severity']}"
    )
    print("SUCCESS:IMP-0245-probe2 rubric-derived severity not reporter adjective")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
