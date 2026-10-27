#!/usr/bin/env python3
"""RES-0160 probe1_backtest.

tests row: "Python source-ledger back-test resolves 30 mechanisms and applies
the missing-metric rule". Recomputes the gate verdict for every back-test row
from the row's own recorded metric status (missing metric => WOULD-NOT-HAVE-
PASSED, the honest reading), recounts the counts block, and requires the
bless-all negative control to have gone red. Defaults to FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/gem-hunt/RES-0160-gem-adoption-gate-with-measured-improvement.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    rep = doc.get("report") or {}
    bt = rep.get("back_test") or {}
    rows = bt.get("rows") or []
    ck("thirty-backtest-rows", len(rows) == 30, f"n={len(rows)}")
    ck("rows-have-mechanism-and-lineage",
       all(r.get("mechanism") and r.get("signal_pair") and r.get("source_lineage") for r in rows),
       str([r.get("mechanism") for r in rows[:4]]))

    # missing-metric rule: no verifiable adoption metric in mounted lineage
    # => WOULD-NOT-HAVE-PASSED. Recompute per row.
    recompute = [
        "WOULD-NOT-HAVE-PASSED" if (r.get("metric") or {}).get("status") == "NO_VERIFIABLE_ADOPTION_METRIC_IN_MOUNTED_LINEAGE"
        else "REVIEW" for r in rows
    ]
    recorded = [r.get("verdict") for r in rows]
    ck("missing-metric-rule-applied-every-row", recompute == recorded,
       f"agree={sum(a == b for a, b in zip(recompute, recorded))}/30")
    ck("zero-would-have-passed", recorded.count("WOULD-HAVE-PASSED") == 0,
       f"n={recorded.count('WOULD-HAVE-PASSED')}")
    ck("all-thirty-would-not-have-passed", recorded.count("WOULD-NOT-HAVE-PASSED") == 30,
       f"n={recorded.count('WOULD-NOT-HAVE-PASSED')}")

    counts = bt.get("counts") or {}
    ck("counts-match-recompute",
       counts.get("WOULD-HAVE-PASSED") == 0 and counts.get("WOULD-NOT-HAVE-PASSED") == 30,
       str(counts))

    in_use = [r for r in rows if r.get("current_use_status") == "CONFIRMED_STILL_IN_USE"]
    ck("one-still-in-use-would-not-have-passed",
       len(in_use) == 1 and counts.get("CONFIRMED-STILL-IN-USE-AND-WOULD-NOT-HAVE-PASSED") == 1
       and in_use[0].get("verdict") == "WOULD-NOT-HAVE-PASSED",
       str([(r.get("mechanism"), r.get("current_use_status")) for r in in_use]))

    nc = (doc.get("negative_controls") or [{}])[0]
    ck("bless-all-mutant-went-red",
       nc.get("fired_on_bad_state") is True and "NEGATIVE_CONTROL_WENT_RED=true" in str(nc.get("bad_state_output")),
       str(nc.get("id")))

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and "SUCCESS:RES-0160" in txt, f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe1-backtest", "unit_id": "RES-0160", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0160-probe1 30-row back-test recomputed, bless-all red" if not red
          else f"FAILED:RES-0160-probe1 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
