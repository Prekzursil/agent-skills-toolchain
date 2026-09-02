#!/usr/bin/env python3
"""Probe 1: unanimous-wrong is visible via postcondition; ties stay UNRESOLVED.

Both-states for the postcondition: genuine cross-vendor consensus PASSES the
probe; an ensemble whose members all agree on PLANTED-WRONG FAILS it. Cluster
mass ties (same-vendor collapse, and equal cross-vendor mass) must not be
broken by member count or by an arbitrary pick.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ensemble_operator as E  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0105-fusion-ensemble.json"


def _check_artifact(report: dict) -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0105" not in text:
        return "sentinel absent from artifact"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"self-declared {doc.get('state')}"
    by_id = {row["ensemble_id"]: row for row in doc.get("ensembles") or []}
    want = {
        "cross-vendor-consensus": report["cross_vendor"]["result"]["verdict"],
        "unanimous-wrong": report["unanimous_wrong"]["result"]["verdict"],
        "same-vendor-tie": report["same_vendor_tie"]["result"]["verdict"],
        "equal-mass-tie": report["equal_mass_tie"]["result"]["verdict"],
    }
    for eid, verdict in want.items():
        row = by_id.get(eid)
        if not row:
            return f"artifact missing ensemble {eid}"
        if row.get("result", {}).get("verdict") != verdict:
            return f"artifact {eid} verdict drift {row.get('result')}"
    tests = {t["id"]: t for t in doc.get("tests") or []}
    for tid in (
        "unanimous-wrong-postcondition",
        "cluster-mass-tie-unresolved",
        "both-states-postcondition",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            return f"artifact test {tid} not PASS"
    return None


def main() -> int:
    report = E.evaluate_contracts()
    xv = report["cross_vendor"]
    uw = report["unanimous_wrong"]
    sv = report["same_vendor_tie"]
    tm = report["equal_mass_tie"]
    payload = {
        "probe": "probe1-unanimous-wrong-and-tie",
        "unit_id": "WFA-0105",
        "genuine_consensus_resolved": report["genuine_consensus_resolved"],
        "genuine_consensus_postcondition_passed": report[
            "genuine_consensus_postcondition_passed"
        ],
        "unanimous_wrong_verdict": uw["result"]["verdict"],
        "unanimous_cluster_count": report["unanimous_cluster_count"],
        "same_vendor_tie_verdict": sv["result"]["verdict"],
        "equal_mass_tie_verdict": tm["result"]["verdict"],
        "naive_member_count_breaks_same_vendor_tie": report[
            "naive_member_count_breaks_same_vendor_tie"
        ],
        "both_states_postcondition": report["both_states_postcondition"],
        "agree_on_already_sorted": report["agree_on_already_sorted"],
        "disagree_on_mixed_dup": report["disagree_on_mixed_dup"],
        "split_despite_sorted_agreement": report["split_despite_sorted_agreement"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"genuine={xv['result']['verdict']}/{xv['postcondition']['passed']} "
        f"unanimous={uw['result']['verdict']} "
        f"sv_tie={sv['result']['verdict']} eq_tie={tm['result']['verdict']} "
        f"naive_breaks={report['naive_member_count_breaks_same_vendor_tie']} "
        f"split={report['split_despite_sorted_agreement']}"
    )
    if not report["both_states_postcondition"]:
        print("FAILED:WFA-0105-probe1 both-states postcondition")
        return 1
    if report["unanimous_cluster_count"] != 1:
        print("FAILED:WFA-0105-probe1 unanimous-wrong must be one cluster")
        return 1
    if uw["result"]["verdict"] != "POSTCONDITION-FAILED":
        print("FAILED:WFA-0105-probe1 unanimous wrong hidden by consensus")
        return 1
    if sv["result"]["verdict"] != "UNRESOLVED":
        print("FAILED:WFA-0105-probe1 same-vendor tie was broken")
        return 1
    if tm["result"]["verdict"] != "UNRESOLVED":
        print("FAILED:WFA-0105-probe1 equal-mass tie was broken")
        return 1
    if not report["naive_member_count_breaks_same_vendor_tie"]:
        print("FAILED:WFA-0105-probe1 naive member-count control did not fire")
        return 1
    if not report["split_despite_sorted_agreement"]:
        print("FAILED:WFA-0105-probe1 distinguishing inputs did not split clusters")
        return 1
    art_err = _check_artifact(report)
    if art_err:
        print(f"FAILED:WFA-0105-probe1 artifact {art_err}")
        return 1
    print(
        "SUCCESS:WFA-0105-probe1 postcondition exposes unanimous-wrong; "
        "ties stay UNRESOLVED; distinguishing inputs split clusters"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
