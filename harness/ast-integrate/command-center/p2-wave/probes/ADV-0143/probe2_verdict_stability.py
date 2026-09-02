#!/usr/bin/env python3
"""Probe 2: two-reviewer verdict stability with a pre-stated threshold.

Prints the frozen threshold BEFORE any rater pair is computed.
Different field from probe 1 (not completeness/extent).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reviewers import adjudicate  # noqa: E402
import schema_check as SC  # noqa: E402
from threshold import (  # noqa: E402
    AGREEMENT_METRIC,
    AGREEMENT_THRESHOLD,
    CHOSEN_BEFORE_RUN,
    KAPPA_THRESHOLD,
    RATIONALE,
    STABILITY_N,
)

ART = REPO / "command-center/adversarial/ADV-0143-content-redistribution.json"
SENTINEL = "SUCCESS:ADV-0143"


def main() -> int:
    print(f"pre_stated_agreement_threshold={AGREEMENT_THRESHOLD}")
    print(f"agreement_metric={AGREEMENT_METRIC}")
    print(f"pre_stated_kappa_threshold={KAPPA_THRESHOLD}")
    print(f"threshold_stated_before_run={CHOSEN_BEFORE_RUN}")
    print(f"threshold_rationale={RATIONALE}")
    if not CHOSEN_BEFORE_RUN or AGREEMENT_THRESHOLD != 0.8:
        print("FAILED:ADV-0143-probe2 threshold was not the frozen pre-stated value")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:ADV-0143-probe2 artifact missing")
        return 1
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:ADV-0143-probe2 sentinel absent")
        return 1

    live = adjudicate(REPO)
    if live["n"] != STABILITY_N:
        print("FAILED:ADV-0143-probe2 row count", live["n"])
        return 1
    if live["source_probe"] == live["verifier_probe"]:
        print("FAILED:ADV-0143-probe2 same-probe-rerun")
        return 1
    if live["agreement_rate"] < AGREEMENT_THRESHOLD:
        print(
            "FAILED:ADV-0143-probe2 agreement "
            f"{live['agreement_rate']} < {AGREEMENT_THRESHOLD}"
        )
        return 1
    if live["kappa_live"]["kappa"] < KAPPA_THRESHOLD:
        print(
            "FAILED:ADV-0143-probe2 kappa "
            f"{live['kappa_live']['kappa']} < {KAPPA_THRESHOLD}"
        )
        return 1
    if live["naive_agreement_rate"] >= AGREEMENT_THRESHOLD:
        print(
            "FAILED:ADV-0143-probe2 silent_in_both_states "
            f"naive_rate={live['naive_agreement_rate']}"
        )
        return 1

    doc = json.loads(ART.read_text(encoding="utf-8"))
    rec = SC.domain(doc)["verdict_stability"]
    if rec.get("met") is not True:
        print("FAILED:ADV-0143-probe2 artifact met is not true")
        return 1
    if abs(float(rec.get("agreement_rate")) - live["agreement_rate"]) > 1e-12:
        print("FAILED:ADV-0143-probe2 artifact agreement mismatch")
        return 1
    if rec.get("source_probe") != "classify_path":
        print("FAILED:ADV-0143-probe2 source_probe drift")
        return 1
    if rec.get("verifier_probe") != "classify_body":
        print("FAILED:ADV-0143-probe2 verifier_probe drift")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-verdict-stability",
                "agreement_rate": live["agreement_rate"],
                "kappa": live["kappa_live"]["kappa"],
                "naive_agreement_rate": live["naive_agreement_rate"],
                "n": live["n"],
                "source_probe": live["source_probe"],
                "verifier_probe": live["verifier_probe"],
                "silent_in_both_states": False,
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:ADV-0143-probe2 agreement="
        f"{live['agreement_rate']} kappa={live['kappa_live']['kappa']} "
        f"naive_rate={live['naive_agreement_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
