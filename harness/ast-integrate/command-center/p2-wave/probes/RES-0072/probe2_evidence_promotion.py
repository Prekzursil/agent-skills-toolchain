#!/usr/bin/env python3
"""Probe 2: evidence rails, E3 promotion ban, partitioned sources, mutants.

Mechanically different from probe 1 (which re-derives the replication column):
this probe checks DOI/arXiv + locus + effect + baseline on every non-unknown
row, refuses E3 promotion, checks disjoint intended partitions, and fires two
mutants (strip baseline; promote E3).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    OUTPUT_REL,
    UNIT_ID,
    mutant_promote_e3,
    mutant_strip_baseline,
    validate_artifact,
)

ART = REPO / OUTPUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0072-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = validate_artifact(doc)
    if errs:
        print("FAILED:RES-0072-probe2 live " + "; ".join(errs))
        return 1
    col = doc.get("replication_column") or []
    cited = [r for r in col if r.get("replication_status") != "unknown"]
    for row in cited:
        if not (row.get("arxiv") or row.get("doi")):
            print(f"FAILED:RES-0072-probe2 {row.get('router_id')} missing arxiv/doi")
            return 1
        if not str(row.get("figure_locus") or "").strip():
            print(f"FAILED:RES-0072-probe2 {row.get('router_id')} missing locus")
            return 1
        if not str(row.get("effect_size") or "").strip():
            print(f"FAILED:RES-0072-probe2 {row.get('router_id')} missing effect")
            return 1
        if not str(row.get("baseline") or "").strip():
            print(f"FAILED:RES-0072-probe2 {row.get('router_id')} missing baseline")
            return 1
        if row.get("evidence_tier") == "E3" and row.get("may_promote") is True:
            print(f"FAILED:RES-0072-probe2 {row.get('router_id')} E3 promoted")
            return 1
    if any(r.get("may_promote") for r in col) or (doc.get("promoted_mechanisms") or []):
        print("FAILED:RES-0072-probe2 unexpected promotion of a non-replicated saving")
        return 1
    parts = doc.get("intended_partitions") or []
    if len(parts) < 2:
        print("FAILED:RES-0072-probe2 intended partitions missing")
        return 1
    a = set(parts[0].get("source_ids") or [])
    b = set(parts[1].get("source_ids") or [])
    if not a or not b or (a & b):
        print("FAILED:RES-0072-probe2 partitions not disjoint nonempty")
        return 1
    req = doc.get("reviewer_requirement") or {}
    if req.get("met") is True:
        print("FAILED:RES-0072-probe2 reviewer_requirement.met claimed without two vendors")
        return 1
    strip_errs = validate_artifact(mutant_strip_baseline(doc))
    prom_errs = validate_artifact(mutant_promote_e3(doc))
    if not strip_errs:
        print("FAILED:RES-0072-probe2 strip-baseline mutant silent")
        return 1
    if not prom_errs:
        print("FAILED:RES-0072-probe2 promote-E3 mutant silent")
        return 1
    payload = {
        "probe": "probe2-evidence-promotion",
        "unit_id": UNIT_ID,
        "cited_rows": len(cited),
        "promoted": doc.get("promoted_mechanisms") or [],
        "partition_a": sorted(a),
        "partition_b": sorted(b),
        "reviewer_requirement_met": req.get("met"),
        "strip_baseline_errors": strip_errs[:8],
        "promote_e3_errors": prom_errs[:8],
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:RES-0072-probe2 evidence rails and E3 promotion ban")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
