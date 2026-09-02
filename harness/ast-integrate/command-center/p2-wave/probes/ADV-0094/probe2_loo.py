#!/usr/bin/env python3
"""Probe 2: leave-one-out outcome delta (influence, not token share)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402


def payload() -> dict:
    loo = C.loo_runs()
    fails = C.loo_invariants(loo)
    fx = loo["fixtures"]
    independent = C.pick_recommendation(
        fx["flood_off"]["unique_by_author"],
        fx["flood_off"]["first_idea_by_author"],
    )
    summary = {
        "probe": "probe2-loo",
        "unit_id": C.UNIT_ID,
        "flood_off": loo["flood_off"],
        "flood_on": loo["flood_on"],
        "balanced": loo["balanced"],
        "independent_rederive": independent,
        "independent_matches_base": independent["idea_id"]
        == fx["flood_off"]["recommendation"]["idea_id"],
        "fails": fails,
        "pass": not fails,
    }
    return summary


def main() -> int:
    summary = payload()
    print(json.dumps(summary, sort_keys=True, default=str))
    off, on = summary["flood_off"], summary["flood_on"]
    print(
        "loo_off rec {} -> {} changed={} delta={:.3f} | "
        "loo_on rec {} -> {} changed={} delta={:.3f}".format(
            off["base_rec"],
            off["loo_rec"],
            off["rec_changed"],
            off["outcome_delta"],
            on["base_rec"],
            on["loo_rec"],
            on["rec_changed"],
            on["outcome_delta"],
        )
    )
    if not summary["independent_matches_base"]:
        print("FAILED:ADV-0094-probe2 independent rederive mismatch")
        return 1
    if summary["fails"]:
        print("FAILED:ADV-0094-probe2 " + "; ".join(summary["fails"]))
        return 1
    print(
        "SUCCESS:ADV-0094-probe2 leave-one-out: uncapped outcome moves; "
        "quota pins recommendation; balanced control is stable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
