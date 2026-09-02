#!/usr/bin/env python3
"""Probe 1: token share, surviving-idea share, synthesis attribution."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402


def payload() -> dict:
    fx = C.fixture_runs()
    fails = C.share_invariants(fx)
    off, on, rest, bal = (
        fx["flood_off"],
        fx["flood_on"],
        fx["restate_off"],
        fx["balanced"],
    )
    summary = {
        "probe": "probe1-shares",
        "unit_id": C.UNIT_ID,
        "flood_off": {
            "token_share": off["token_share"],
            "idea_share": off["idea_share"],
            "attribution_share": off["attribution_share"],
            "first_speaker": off["first_speaker"],
            "recommendation": off["recommendation"],
            "token_weighted_recommendation": off["token_weighted_recommendation"],
            "throttles": off["throttles"],
            "quiet_census": (off.get("census") or {}).get("quiet"),
        },
        "flood_on": {
            "token_share": on["token_share"],
            "idea_share": on["idea_share"],
            "attribution_share": on["attribution_share"],
            "first_speaker": on["first_speaker"],
            "recommendation": on["recommendation"],
            "throttles": on["throttles"],
        },
        "restate_off": {
            "token_share": rest["token_share"],
            "idea_share": rest["idea_share"],
            "recommendation": rest["recommendation"],
            "token_weighted_recommendation": rest["token_weighted_recommendation"],
        },
        "balanced": {
            "token_share": bal["token_share"],
            "idea_share": bal["idea_share"],
            "recommendation": bal["recommendation"],
        },
        "scheduler": off["scheduler"],
        "engagement": off["engagement"],
        "fails": fails,
        "pass": not fails,
    }
    return summary


def main() -> int:
    summary = payload()
    print(json.dumps(summary, sort_keys=True, default=str))
    off = summary["flood_off"]
    on = summary["flood_on"]
    print(
        "flood_off loud token={:.3f} idea={:.3f} rec={} first={} | "
        "flood_on loud token={:.3f} idea={:.3f} rec={} throttles={}".format(
            off["token_share"].get("loud", 0),
            off["idea_share"].get("loud", 0),
            off["recommendation"].get("idea_id"),
            off["first_speaker"],
            on["token_share"].get("loud", 0),
            on["idea_share"].get("loud", 0),
            on["recommendation"].get("idea_id"),
            on["throttles"].get("loud"),
        )
    )
    if summary["fails"]:
        print("FAILED:ADV-0094-probe1 " + "; ".join(summary["fails"]))
        return 1
    print(
        "SUCCESS:ADV-0094-probe1 shares: uncapped volume capture; "
        "quota redistributes tokens and unique ideas; first speaker unchanged"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
