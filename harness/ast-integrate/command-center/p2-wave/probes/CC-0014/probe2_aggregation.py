#!/usr/bin/env python3
"""Probe 2: aggregation control + independent reviewer mutation.

A coverage summary over all-UNPROVEN entries must report 0 protected claims,
not 100 percent. An independent mutation the implementer did not write must
be classified the same way (kill → PROTECTING, survive → HOLE). Bindings
test_id / claim_id / unit_id are required on every entry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
sys.path.insert(0, str(HERE))

import test_registry_bind as bind  # noqa: E402
import mutate as M  # noqa: E402

ART = REPO / "command-center/receipts/CC-0014.json"
T_PROT = HERE / "fixtures" / "test_protecting.py"
T_EXPL = HERE / "fixtures" / "test_explicit.py"


def fail(msg: str) -> int:
    print(f"FAILED:CC-0014-probe2 {msg}")
    return 1


def receipt_payload(doc: dict) -> tuple[list, dict, dict, str]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    entries = doc.get("entries") or report.get("entries") or []
    coverage = doc.get("coverage") or report.get("coverage") or {}
    reviewer = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    mutation_id = str(
        reviewer.get("mutation_id") or report.get("reviewer_mutation_id") or ""
    )
    return (
        [e for e in entries if isinstance(e, dict)],
        coverage if isinstance(coverage, dict) else {},
        reviewer,
        mutation_id,
    )


def main() -> int:
    all_unproven = [
        bind.bind_row(
            test_id="test_empty_list_rejected_at_explicit_one",
            claim_id="CL-CC-0014-UNPROVEN-NOT-COVERAGE",
            unit_id="CC-0014",
        ),
        bind.bind_row(
            test_id="test_default_floor_accepts_exact_minimum",
            claim_id="CL-CC-0014-DEFAULT-FLOOR-ENFORCED",
            unit_id="CC-0014",
        ),
        bind.bind_row(
            test_id="test_explicit_minimum_ignores_module_default",
            claim_id="CL-CC-0014-EXPLICIT-ONLY-IS-HOLE",
            unit_id="CC-0014",
        ),
    ]
    cov = bind.coverage_summary(all_unproven)
    if cov["protected_claims"] != 0:
        return fail(f"all-UNPROVEN protected_claims={cov['protected_claims']}")
    if cov["protected_percent"] != 0.0:
        return fail(f"all-UNPROVEN reported {cov['protected_percent']} percent")
    if cov["claims_total"] != 3:
        return fail(f"claims_total={cov['claims_total']}")
    if cov["unproven_counted_as_coverage"] is not False:
        return fail("UNPROVEN counted as coverage")
    if cov["all_unproven_reports_zero_not_hundred"] is not True:
        return fail("zero-not-hundred flag")

    # Independent reviewer mutation: REQUIRED_MIN = 99 (implementer used 0).
    if M.MUT_REV_NINETY_NINE == M.MUT_IMPL_ZERO:
        return fail("reviewer mutation is not independent of implementer mutation")
    rev_kill = M.mutate_and_run(
        M.MUT_REV_NINETY_NINE, T_PROT, "test_default_floor_accepts_exact_minimum"
    )
    if rev_kill["outcome"] != "KILLED":
        return fail(f"reviewer mutation did not kill protecting test: {rev_kill}")
    if "REQUIRED_MIN = 99" not in rev_kill["diff"]:
        return fail("reviewer diff missing REQUIRED_MIN = 99")
    rev_prot = bind.bind_row(
        test_id="test_default_floor_accepts_exact_minimum",
        claim_id="CL-CC-0014-DEFAULT-FLOOR-ENFORCED",
        unit_id="CC-0014",
        mutation={
            "outcome": rev_kill["outcome"],
            "diff": rev_kill["diff"],
            "failing_output": rev_kill["failing_output"],
            "id": "M-REV-DEFAULT-NINETY-NINE",
            "author": "independent-reviewer",
        },
    )
    if rev_prot["status"] != "PROTECTING":
        return fail(f"reviewer kill classified {rev_prot['status']}")

    rev_live = M.mutate_and_run(
        M.MUT_REV_NINETY_NINE, T_EXPL, "test_explicit_minimum_ignores_module_default"
    )
    if rev_live["outcome"] != "SURVIVED":
        return fail(f"reviewer mutation should survive explicit test: {rev_live}")
    rev_hole = bind.bind_row(
        test_id="test_explicit_minimum_ignores_module_default",
        claim_id="CL-CC-0014-EXPLICIT-ONLY-IS-HOLE",
        unit_id="CC-0014",
        mutation={
            "outcome": rev_live["outcome"],
            "diff": rev_live["diff"],
            "failing_output": rev_live["failing_output"],
            "id": "M-REV-DEFAULT-NINETY-NINE",
            "author": "independent-reviewer",
        },
    )
    if rev_hole["status"] != "HOLE":
        return fail(f"reviewer survive classified {rev_hole['status']}")

    mixed = bind.coverage_summary([all_unproven[0], rev_prot, rev_hole])
    if mixed["protected_claims"] != 1:
        return fail(f"mixed protected_claims={mixed['protected_claims']}")
    if mixed["protected_percent"] <= 0:
        return fail("mixed percent not positive")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CC-0014" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    entries, rec_cov, reviewer, mutation_id = receipt_payload(doc)
    for entry in entries:
        for key in ("test_id", "claim_id", "unit_id"):
            if not entry.get(key):
                return fail(f"entry missing {key}: {entry}")
        if entry.get("unit_id") != "CC-0014":
            return fail(f"unbound unit {entry.get('unit_id')}")
    live_cov = bind.coverage_summary(entries)
    if int(rec_cov.get("protected_claims") or -1) != live_cov["protected_claims"]:
        return fail("receipt coverage.protected_claims != live recompute")
    if rec_cov.get("unproven_counted_as_coverage") is not False:
        return fail("receipt counts UNPROVEN as coverage")
    if mutation_id != "M-REV-DEFAULT-NINETY-NINE":
        return fail("receipt missing independent reviewer mutation")
    if reviewer.get("verdict") != "PASS":
        return fail(f"reviewer verdict={reviewer.get('verdict')}")

    print(
        json.dumps(
            {
                "all_unproven_protected_claims": cov["protected_claims"],
                "all_unproven_percent": cov["protected_percent"],
                "reviewer_kill": rev_prot["status"],
                "reviewer_survive": rev_hole["status"],
                "mixed_protected_claims": mixed["protected_claims"],
                "receipt_protected_claims": rec_cov.get("protected_claims"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CC-0014-probe2 aggregation zero-not-hundred and reviewer mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
