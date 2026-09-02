#!/usr/bin/env python3
"""Probe 2: declared writes are a SUPERSET of observed writes; ledger invariants.

Independent of probe 1's MAE table. Both-states: under-declaring one observed
write must go red; the unmodified registry must stay green. Duplicate node_id
must raise DoubleCountError.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.registry import (  # noqa: E402
    evaluate_registry,
    ledger_invariants_hold,
    writes_declared_superset,
)

ART = REPO / "command-center/receipts/IMP-0143.json"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0143-probe2 {msg}")
    return 1


def main() -> int:
    inv = ledger_invariants_hold()
    print(json.dumps({"ledger_invariants": inv}, sort_keys=True))
    if not inv["duplicate_append_raised"]:
        return _fail("duplicate node_id did not raise DoubleCountError")
    if not inv["monotonic"] or not inv["no_double_count_asserted"]:
        return _fail("ledger invariant flags false")
    if inv["n_entries"] != 3:
        return _fail(f"invariant ledger entry count {inv['n_entries']}")

    with tempfile.TemporaryDirectory(prefix="imp0143-p2-") as tmp:
        report = evaluate_registry(Path(tmp))

    if not report["all_writes_superset"]:
        bad = [r["case_id"] for r in report["rows"] if not r["writes_superset"]]
        return _fail(f"estimate writes not a superset: {bad}")

    # Need at least one case where actual writes are a proper subset (conservative).
    proper = [
        r
        for r in report["rows"]
        if set(r["act_writes"]) < set(r["est_writes"]) and r["act_writes"]
    ]
    print(f"proper_subset_cases={[r['case_id'] for r in proper]}")
    if not proper:
        return _fail("no fixture where estimate is a proper superset (vacuous)")

    victim = next(r for r in report["rows"] if r["act_writes"])
    dropped = victim["act_writes"][0]
    mutant_est = [p for p in victim["est_writes"] if p != dropped]
    fired = not writes_declared_superset(set(mutant_est), set(victim["act_writes"]))
    silent = writes_declared_superset(
        set(victim["est_writes"]), set(victim["act_writes"])
    )
    extra_act = set(victim["act_writes"]) | {"undeclared/escape.txt"}
    extra_fired = not writes_declared_superset(set(victim["est_writes"]), extra_act)
    print(
        json.dumps(
            {
                "victim": victim["case_id"],
                "dropped": dropped,
                "mutant_underdeclare_fired": fired,
                "good_state_silent": silent,
                "undeclared_write_fired": extra_fired,
                "all_writes_superset": report["all_writes_superset"],
            },
            sort_keys=True,
        )
    )
    if not silent:
        return _fail("good-state superset check fired")
    if not fired:
        return _fail("under-declare mutant was accepted (both-states fail)")
    if not extra_fired:
        return _fail("undeclared observed write was accepted")

    nested = next(
        (r for r in report["rows"] if r["case_id"] == "nested-subworkflow"), None
    )
    if nested is None:
        return _fail("nested-subworkflow case missing")
    # Wrapper is 0-cost; two units at 1000 each => estimate 2000, not 4000.
    if nested["est_micro_cost"] != 2000:
        return _fail(
            f"nested estimate micro_cost={nested['est_micro_cost']} (double-count?)"
        )

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        table = doc.get("estimate_vs_actual") or []
        if len(table) != report["n_cases"]:
            return _fail("receipt table length drifted from live registry")
        if doc.get("all_writes_superset") is not True:
            return _fail("receipt all_writes_superset is not true")
        if "SUCCESS:IMP-0143" not in ART.read_text(encoding="utf-8"):
            return _fail("sentinel absent")

    print("SUCCESS:IMP-0143-probe2 writes superset and ledger no-double-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
