#!/usr/bin/env python3
"""Probe 2: cross-vendor mass, same-vendor collapse, no LLM ranking.

Mechanically different from probe 1 (postcondition / tie). This probe checks
independence accounting and that the reconciler never imports an LLM client or
calls a quality-rank helper.
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
    llm = doc.get("llm_ranking") or {}
    if llm.get("invocations") != 0 or llm.get("absent") is not True:
        return f"artifact llm_ranking {llm}"
    xv = next(
        (
            row
            for row in doc.get("ensembles") or []
            if row.get("ensemble_id") == "cross-vendor-consensus"
        ),
        None,
    )
    if not xv:
        return "artifact missing cross-vendor-consensus"
    winner_id = xv.get("result", {}).get("winner_cluster_id")
    winner = next(
        (c for c in xv.get("clusters") or [] if c.get("cluster_id") == winner_id),
        None,
    )
    if not winner:
        return "artifact missing winner cluster"
    if winner.get("vendor_mass") != 2 or winner.get("member_count") != 3:
        return f"artifact winner mass {winner}"
    if not all(s.get("cluster_id") for s in xv.get("sources") or []):
        return "artifact missing per-source cluster assignment"
    return None


def main() -> int:
    report = E.evaluate_contracts()
    scan = report["llm_scan"]
    xv = report["cross_vendor"]
    payload = {
        "probe": "probe2-cross-vendor-and-no-llm",
        "unit_id": "WFA-0105",
        "winner_is_unique_sorted": report["winner_is_unique_sorted"],
        "cross_vendor_mass_two_not_three": report["cross_vendor_mass_two_not_three"],
        "same_vendor_pair_collapsed": report["same_vendor_pair_collapsed"],
        "cross_vendor_pair_independent": report["cross_vendor_pair_independent"],
        "llm_ranking_absent": report["llm_ranking_absent"],
        "llm_ranking_invocations": report["llm_ranking_invocations"],
        "forbidden_imports": scan["forbidden_imports"],
        "forbidden_name_hits": scan["forbidden_name_hits"],
        "cluster_assignment": {
            s["id"]: s["cluster_id"] for s in xv["sources"]
        },
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"unique_sorted={report['winner_is_unique_sorted']} "
        f"mass_2_not_3={report['cross_vendor_mass_two_not_three']} "
        f"same_vendor_collapsed={report['same_vendor_pair_collapsed']} "
        f"cross_vendor={report['cross_vendor_pair_independent']} "
        f"llm_absent={report['llm_ranking_absent']}"
    )
    if not report["winner_is_unique_sorted"]:
        print("FAILED:WFA-0105-probe2 winner is not the unique-sorted cluster")
        return 1
    if not report["cross_vendor_mass_two_not_three"]:
        print("FAILED:WFA-0105-probe2 same-vendor members were counted as extra mass")
        return 1
    if not report["same_vendor_pair_collapsed"]:
        print("FAILED:WFA-0105-probe2 same-vendor agreement not recorded as one signal")
        return 1
    if not report["cross_vendor_pair_independent"]:
        print("FAILED:WFA-0105-probe2 cross-vendor agreement not recorded")
        return 1
    if not report["llm_ranking_absent"] or report["llm_ranking_invocations"] != 0:
        print("FAILED:WFA-0105-probe2 reconciler ranks by LLM/quality")
        print(json.dumps(scan, sort_keys=True))
        return 1
    assigned = [s.get("cluster_id") for s in xv["sources"]]
    if not all(assigned) or len(assigned) != 4:
        print("FAILED:WFA-0105-probe2 cluster assignment missing per source")
        return 1
    art_err = _check_artifact(report)
    if art_err:
        print(f"FAILED:WFA-0105-probe2 artifact {art_err}")
        return 1
    print(
        "SUCCESS:WFA-0105-probe2 cross-vendor mass=2; same-vendor collapsed; "
        "no LLM ranking"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
