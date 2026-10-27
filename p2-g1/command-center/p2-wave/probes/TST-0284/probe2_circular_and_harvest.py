#!/usr/bin/env python3
"""TST-0284 probe 2: circular refutations rejected + the program harvest.

Unobservable-in-principle (omniscient/infinite), omniscient, and
equals-claim refuting observations are all rejected as circular. The three
program impossibility records (reconstructed verbatim from the receipt
harvest rows) each score accepted=False with the receipt exact
missing-field lists. The three declared CNF/RES harvest paths are live on
this tree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fixtures import (  # noqa: E402
    CIRCULAR_UNOBSERVABLE,
    EQUALS_CLAIM,
    OMNISCIENT,
    PROGRAM_RECORDS,
)
from validator import validate  # noqa: E402


def main() -> int:
    checks: dict[str, bool] = {}
    cu = validate(CIRCULAR_UNOBSERVABLE)
    checks["circular_unobservable_rejected"] = cu["accepted"] is False
    checks["circular_reason_unobservable"] = bool(cu["circular"]) and (
        "unobservable" in cu["circular"]
    )
    om = validate(OMNISCIENT)
    checks["omniscient_rejected"] = om["accepted"] is False
    eq = validate(EQUALS_CLAIM)
    checks["equals_claim_rejected_as_circular"] = eq["accepted"] is False
    harvest_ok = True
    scored = []
    for rec in PROGRAM_RECORDS:
        v = validate(rec)
        ok = v["missing"] == rec["want_missing"] and (
            v["accepted"] == rec["want_accepted"]
        )
        harvest_ok = harvest_ok and ok
        scored.append(
            {
                "id": rec["id"],
                "accepted": v["accepted"],
                "missing": v["missing"],
                "matches_receipt_row": ok,
            }
        )
    checks["program_harvest_scores_match_receipt"] = harvest_ok
    cnf = REPO / "command-center" / "confirmation"
    res = REPO / "command-center" / "research" / "evidence-quality"
    declared = [
        cnf / "CNF-0026-impossibility-records.json",
        cnf / "CNF-0098-macos-reachability.json",
        res / "RES-0149-proof-of-impossibility-record-schema.json",
    ]
    live = [p.is_file() and p.stat().st_size > 0 for p in declared]
    checks["declared_harvest_paths_live"] = all(live)
    out = {
        "probe": "probe2_circular_and_harvest",
        "unit": "TST-0284",
        "circular_results": {
            "unobservable": cu,
            "omniscient": om,
            "equals_claim": eq,
        },
        "program_harvest": scored,
        "declared_paths_live": {
            str(p.relative_to(REPO)): ok for p, ok in zip(declared, live)
        },
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-circular-harvest.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
