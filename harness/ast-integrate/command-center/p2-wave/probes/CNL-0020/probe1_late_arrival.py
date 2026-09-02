#!/usr/bin/env python3
"""Probe 1: late-arrival fixture — first position is not majority-copying."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catchup as C  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0020-elastic-scaling-mid-council-recruitment-and-catch-up-brief.md"
)


def main() -> int:
    live = C.run_late_arrival()
    print(json.dumps({k: live[k] for k in sorted(live) if k != "leak_on_good"}, sort_keys=True))
    print(
        "invariance={inv} copy={copy} match={m}/{n} prior_eq_maj={p} "
        "opposing_copied={oc}/{on}".format(
            inv=live["invariance_violations"],
            copy=live["copy_hypothesis"],
            m=live["match_majority"],
            n=live["n_trials"],
            p=live["prior_equals_majority"],
            oc=live["opposing_prior_copied_majority"],
            on=live["opposing_n"],
        )
    )
    if not live.get("ok"):
        print("FAILED:CNL-0020-probe1 late-arrival fixture did not hold")
        return 1
    if live["invariance_violations"] != 0:
        print("FAILED:CNL-0020-probe1 majority flip moved first position")
        return 1
    if live["opposing_prior_copied_majority"] != 0:
        print("FAILED:CNL-0020-probe1 newcomer copied majority against prior")
        return 1
    if live["match_majority"] == live["n_trials"]:
        print("FAILED:CNL-0020-probe1 every trial matched majority (copying)")
        return 1
    if live["match_majority"] != live["prior_equals_majority"]:
        print("FAILED:CNL-0020-probe1 match_majority != prior_equals_majority")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0020-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0020-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0020" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0020-probe1 sentinel absent")
        return 1
    rpt = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rec = (
        (doc.get("measurements") or rpt.get("measurements") or {}).get("late_arrival")
        or {}
    )
    for k in (
        "n_trials",
        "match_majority",
        "prior_equals_majority",
        "invariance_violations",
        "opposing_prior_copied_majority",
        "copy_hypothesis",
    ):
        if rec.get(k) != live.get(k):
            print(f"FAILED:CNL-0020-probe1 artifact mismatch {k} rec={rec.get(k)} live={live.get(k)}")
            return 1
    print("SUCCESS:CNL-0020-probe1 late-arrival independence held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
