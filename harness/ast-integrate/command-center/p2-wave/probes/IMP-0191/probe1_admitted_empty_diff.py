#!/usr/bin/env python3
"""Probe 1: set-difference is empty for every admitted fusion.

Independent of the detector's `fired` boolean: this probe recomputes
union(source vectors) - fusion vector with the public `capability_vector`
API and requires that result to be empty AND to match `lost_capabilities`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from fusion.capability_loss import (  # noqa: E402
    FAILURE_CLASS,
    capability_vector,
    detect_capability_loss,
    evaluate_admitted,
    index_workflows,
    load_library,
    lost_capabilities,
    resolve_sources,
)

LIB = HERE / "fixtures" / "library.json"


def main() -> int:
    library = load_library(LIB)
    catalog = index_workflows(library)
    report = evaluate_admitted(library)
    print(json.dumps({
        "probe": "probe1-admitted-empty-diff",
        "unit_id": "IMP-0191",
        "admitted_count": report["admitted_count"],
        "set_difference_empty_for_all": report["set_difference_empty_for_all"],
        "fusion_ids": [r["fusion_id"] for r in report["results"]],
    }, sort_keys=True))

    if report["admitted_count"] < 2:
        print("FAILED:IMP-0191-probe1 admitted set too small to discriminate")
        return 1
    if not report["set_difference_empty_for_all"]:
        print("FAILED:IMP-0191-probe1 admitted fusion has nonempty set difference")
        for rec in report["results"]:
            if rec["fired"]:
                print(f"  {rec['fusion_id']} lost={rec['lost']}")
        return 1

    for rec in report["results"]:
        fusion = catalog[str(rec["fusion_id"])]
        sources = resolve_sources(fusion, catalog)
        independent = set()
        for src in sources:
            independent |= set(capability_vector(src))
        independent -= set(capability_vector(fusion))
        via_api = set(lost_capabilities(fusion, sources))
        det = detect_capability_loss(fusion, sources)
        if independent != via_api or independent != set(det["lost"]):
            print(
                f"FAILED:IMP-0191-probe1 set-difference mismatch on {rec['fusion_id']}: "
                f"independent={sorted(independent)} api={sorted(via_api)} det={det['lost']}"
            )
            return 1
        if independent:
            print(f"FAILED:IMP-0191-probe1 {rec['fusion_id']} independent diff nonempty")
            return 1
        if det["fired"] or det["failure_class"] == FAILURE_CLASS:
            print(f"FAILED:IMP-0191-probe1 {rec['fusion_id']} detector fired on admitted fusion")
            return 1
        print(
            f"admitted {rec['fusion_id']} empty_diff=True "
            f"fusion_n={len(rec['fusion_vector'])} source_union_n={len(rec['source_union'])}"
        )

    print("SUCCESS:IMP-0191-probe1 capability set difference empty for all admitted fusions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
