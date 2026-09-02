#!/usr/bin/env python3
"""Probe 1: blocking vs advisory both-states, and no metaswarm runtime import.

PASS state: a metaswarm blocking gate classifies BLOCKING and the IR keeps it
BLOCKING. FAIL state: an advisory-only mutant classifies ADVISORY, and forcing
that kind onto a blocking source is a translation defect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adapter as A  # noqa: E402

MUTANT = HERE / "fixtures" / "mutant_advisory.md"


def main() -> int:
    texts = A.load_corpus()
    ir = A.build_ir()
    audit = A.runtime_import_audit()
    mutant = MUTANT.read_text(encoding="utf-8")

    blocking_src = A.classify_gate_kind(texts["plan_review"])
    orch_src = A.classify_gate_kind(texts["orchestrated"])
    design_src = A.classify_gate_kind(texts["design_review"])
    mutant_src = A.classify_gate_kind(mutant)

    gates = {g["id"]: g for g in ir["gates"]}
    pr = gates["plan-review-gate"]
    defect_real = A.translation_defect(blocking_src, pr["gate_kind"])
    defect_forced = A.translation_defect("BLOCKING", "ADVISORY")
    defect_ok = A.translation_defect("BLOCKING", "BLOCKING")

    advisory_in_ir = [
        g["id"]
        for g in ir["gates"]
        if g.get("gate_kind") == "ADVISORY"
    ]

    report = {
        "probe": "probe1-blocking-gate",
        "plan_review_source": blocking_src,
        "design_review_source": design_src,
        "orchestrated_source": orch_src,
        "mutant_source": mutant_src,
        "ir_plan_review_kind": pr["gate_kind"],
        "downgrade_defect_on_live_ir": defect_real,
        "forced_advisory_is_defect": defect_forced,
        "same_kind_not_defect": defect_ok,
        "advisory_gates_in_ir": advisory_in_ir,
        "runtime_import_audit": audit,
    }
    print(json.dumps(report, indent=2, sort_keys=True))

    ok = (
        blocking_src == "BLOCKING"
        and design_src == "BLOCKING"
        and orch_src == "BLOCKING"
        and mutant_src == "ADVISORY"
        and pr["gate_kind"] == "BLOCKING"
        and gates["design-review-gate"]["gate_kind"] == "BLOCKING"
        and gates["pre-pr-knowledge-capture"]["gate_kind"] == "BLOCKING"
        and gates["coverage-enforcement"]["gate_kind"] == "BLOCKING"
        and defect_real is False
        and defect_forced is True
        and defect_ok is False
        and not advisory_in_ir
        and audit["clean"] is True
    )
    if not ok:
        print("FAILED:WFA-0046-probe1 blocking/advisory both-states")
        return 1
    print(
        "blocking_source=True mutant_advisory=True no_downgrade=True "
        "forced_downgrade_is_defect=True no_metaswarm_import=True"
    )
    print("SUCCESS:WFA-0046-probe1 blocking gate both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
