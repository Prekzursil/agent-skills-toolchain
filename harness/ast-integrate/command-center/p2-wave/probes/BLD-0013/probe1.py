#!/usr/bin/env python3
"""Probe 1: four catalog controls, including a planted unrelated binding.

Re-runs the auditor on fixtures (not merely reading the receipt's claims)
and checks the live receipt recorded the same verdicts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from auditor import audit_binding  # noqa: E402
from catalog_units import unit_view  # noqa: E402
from register import reconstructed_register  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0013.json"


def row(reg, rid, uid):
    for r in reg:
        if r["requirement_id"] == rid and r["bound_unit_id"] == uid:
            return r
    raise KeyError((rid, uid))


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0013-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0013-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:BLD-0013" not in ART.read_text(encoding="utf-8"):
        print("FAILED:BLD-0013-probe1 sentinel absent")
        return 1

    reg = reconstructed_register(REPO)

    # Control 1: plant unrelated binding (synthetic unit target, not in register)
    builder = row(reg, "REQ-DISJUNCT-BUILDER", "IMP-0327")
    planted = audit_binding(
        builder["demanded_mechanism"],
        "cp1252 console encoding and DST fall-back ordering of ledger entries",
        builder["disjuncts"],
        builder["domain_tokens"],
        bound_unit_id="SYN-UNRELATED-DST",
    )
    print(f"planted_synthetic={planted['verdict']}")
    if planted["verdict"] != "MIS-BOUND":
        print("FAILED:BLD-0013-probe1 planted unrelated binding was not MIS-BOUND")
        return 1

    planted_live = audit_binding(
        builder["demanded_mechanism"],
        unit_view(REPO, "BLD-0014")["target"],
        builder["disjuncts"],
        builder["domain_tokens"],
        bound_unit_id="BLD-0014",
    )
    print(f"planted_BLD-0014={planted_live['verdict']}")
    if planted_live["verdict"] != "MIS-BOUND":
        print("FAILED:BLD-0013-probe1 BLD-0014 plant was not MIS-BOUND")
        return 1

    # Control 2: disjunction
    disj = audit_binding(
        builder["demanded_mechanism"],
        unit_view(REPO, "IMP-0327")["target"],
        builder["disjuncts"],
        builder["domain_tokens"],
        bound_unit_id="IMP-0327",
    )
    print(f"disjunction_IMP-0327={disj['verdict']}")
    if disj["verdict"] != "SATISFIES":
        print("FAILED:BLD-0013-probe1 disjunction did not SATISFIES")
        return 1
    if disj["verdict"] == "SUBSTITUTES":
        print("FAILED:BLD-0013-probe1 disjunction misclassified SUBSTITUTES")
        return 1

    # Control 3: correctly bound requirement is not flagged
    true_row = row(reg, "REQ-MISBIND-AUDIT", "BLD-0013")
    trueb = audit_binding(
        true_row["demanded_mechanism"],
        unit_view(REPO, "BLD-0013")["target"],
        true_row["disjuncts"],
        true_row["domain_tokens"],
        bound_unit_id="BLD-0013",
    )
    print(f"true_bind_BLD-0013={trueb['verdict']}")
    if trueb["verdict"] != "SATISFIES":
        print("FAILED:BLD-0013-probe1 true bind flagged")
        return 1

    # Control 4: unbound is out of scope (CC-0024), not MIS-BOUND
    orphan = [r for r in reg if r["bound_unit_id"] is None]
    if not orphan:
        print("FAILED:BLD-0013-probe1 no unbound fixture")
        return 1
    scoped = audit_binding(
        orphan[0]["demanded_mechanism"],
        "",
        orphan[0]["disjuncts"],
        orphan[0]["domain_tokens"],
        bound_unit_id=None,
    )
    print(f"unbound_verdict={scoped['verdict']}")
    if scoped["verdict"] != "OUT-OF-SCOPE-CC-0024":
        print("FAILED:BLD-0013-probe1 unbound not scoped to CC-0024")
        return 1
    if not doc.get("scope", {}).get("unbound_requirements_out_of_scope"):
        print("FAILED:BLD-0013-probe1 receipt scope flag missing")
        return 1
    if doc.get("scope", {}).get("unbound_owner") != "CC-0024":
        print("FAILED:BLD-0013-probe1 unbound owner is not CC-0024")
        return 1

    # Receipt must match live auditor for the four named cases
    want = {
        ("REQ-DISJUNCT-BUILDER", "BLD-0014"): "MIS-BOUND",
        ("REQ-DISJUNCT-BUILDER", "IMP-0327"): "SATISFIES",
        ("REQ-MISBIND-AUDIT", "BLD-0013"): "SATISFIES",
    }
    seen = {
        (c["requirement_id"], c["bound_unit_id"]): c["verdict"]
        for c in doc.get("classifications") or []
    }
    for k, v in want.items():
        print(f"receipt {k[0]}->{k[1]}={seen.get(k)}")
        if seen.get(k) != v:
            print(f"FAILED:BLD-0013-probe1 receipt mismatch {k}")
            return 1

    tests = {t["id"]: t for t in doc.get("tests") or []}
    for tid in (
        "T-PLANTED-MISBIND",
        "T-DISJUNCTION",
        "T-NO-FALSE-POSITIVE",
        "T-UNBOUND-OUT-OF-SCOPE",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            print(f"FAILED:BLD-0013-probe1 receipt test {tid}")
            return 1

    print("SUCCESS:BLD-0013-probe1 planted-misbind disjunction true-bind unbound-scope")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
