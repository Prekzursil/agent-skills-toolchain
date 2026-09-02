#!/usr/bin/env python3
"""Named probe 1: independent remesure of every retained improvement.

A fresh agent_id re-runs the harness and must match the artifact's verdict
and (for ops) the exact op-count median. Wall-clock noise claims must stay
classified noise-dominated. All raw repetitions stay recorded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402
import harness as H  # noqa: E402
from checks import domain  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0127-retention-remeasure.json"
PROBE_AGENT = "cnf-0127-probe1-fresh"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0127-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0127":
        print("FAILED:CNF-0127-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNF-0127 emitted only when the artifact" not in text:
        print("FAILED:CNF-0127-probe1 sentinel absent")
        return 1

    payload = domain(doc)
    base_m = H.measure_variant("baseline", agent_id=PROBE_AGENT)
    rows = []
    fail = False
    for case in payload.get("cases") or []:
        variant = None
        for planted in (
            json.loads((HERE / "fixtures/ledger.json").read_text(encoding="utf-8"))[
                "retained_improvements"
            ]
        ):
            if planted["id"] == case["id"]:
                variant = planted["variant"]
                planted_row = planted
                break
        else:
            print(f"FAILED:CNF-0127-probe1 unknown case {case.get('id')}")
            return 1
        imp_m = H.measure_variant(variant, agent_id=PROBE_AGENT)
        fresh = E.decide(planted_row, base_m, imp_m)
        match_verdict = fresh["verdict"] == case["verdict"]
        if case["claimed_metric"] == "ops":
            match_median = fresh["improved_median"] == case["improved_median"]
        else:
            match_median = fresh["verdict"] == case["verdict"]
        raw_n = len((case.get("remeasurements") or {}).get("raw") or [])
        if raw_n < H.REPETITIONS:
            print(f"FAILED:CNF-0127-probe1 under-sampling {case['id']} n={raw_n}")
            return 1
        reported = str(case["remeasurements"]["reported_as"])
        print(
            f"case {case['id']} artifact={case['verdict']} fresh={fresh['verdict']} "
            f"gain={fresh['measured_gain']} median_match={match_median} "
            f"reported_as={reported} remesurer={PROBE_AGENT}"
        )
        if not match_verdict or not match_median:
            fail = True
        if case.get("independence", {}).get("independent") is not True:
            print(f"FAILED:CNF-0127-probe1 not independent {case['id']}")
            return 1
        if PROBE_AGENT == case.get("author_agent_id"):
            print("FAILED:CNF-0127-probe1 probe agent authored the change")
            return 1
        rows.append(case["id"])

    flake = payload.get("flake_measurement_demo") or {}
    if flake.get("reported_as") != "1/7":
        print("FAILED:CNF-0127-probe1 flake overwrite", flake)
        return 1
    if fail:
        print("FAILED:CNF-0127-probe1 remesure disagreement")
        return 1
    if len(rows) < 4:
        print("FAILED:CNF-0127-probe1 too few cases", len(rows))
        return 1
    print(f"remeasured={len(rows)} probe_agent={PROBE_AGENT}")
    print("SUCCESS:CNF-0127-probe1 independent remesure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
