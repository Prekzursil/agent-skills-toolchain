#!/usr/bin/env python3
"""Probe 1: zero claim-id (and objection/dissent id) loss across compaction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from tools.council.artifacts import compact as C  # noqa: E402
from scenario import build_long_transcript  # noqa: E402


def main() -> int:
    transcript = build_long_transcript()
    measured = C.measure_compaction(transcript)
    report = measured["reachability"]
    compacted = measured["compacted"]
    full_ids = C.collect_ids(transcript)

    print(
        json.dumps(
            {
                "probe": "probe1-zero-claim-id-loss",
                "unit_id": "IMP-0348",
                "full_bytes": measured["full_bytes"],
                "compact_bytes": measured["compact_bytes"],
                "shrank": measured["shrank"],
                "full_counts": report["full_counts"],
                "reachable_counts": report["reachable_counts"],
                "unreachable_counts": report["unreachable_counts"],
                "claim_id_loss": report["claim_id_loss"],
                "zero_claim_loss": report["zero_claim_loss"],
                "zero_loss": report["zero_loss"],
            },
            sort_keys=True,
        )
    )
    print(
        f"claim_ids full={report['full_counts']['claim']} "
        f"reachable={report['reachable_counts']['claim']} "
        f"loss={report['claim_id_loss']}"
    )
    print(
        f"objection_loss={report['unreachable_counts']['objection']} "
        f"dissent_loss={report['unreachable_counts']['dissent']} "
        f"shrank={measured['shrank']}"
    )

    if not measured["shrank"]:
        print("FAILED:IMP-0348-probe1 compacted form did not shrink")
        return 1
    if report["claim_id_loss"] != 0 or not report["zero_claim_loss"]:
        print("FAILED:IMP-0348-probe1 claim-id loss is not zero")
        print(json.dumps(report["unreachable"], sort_keys=True))
        return 1
    if not report["zero_loss"]:
        print("FAILED:IMP-0348-probe1 objection or dissent id loss")
        print(json.dumps(report["unreachable"], sort_keys=True))
        return 1
    if any(report["invented"][k] for k in C.KINDS):
        print("FAILED:IMP-0348-probe1 compacted form invented ids")
        print(json.dumps(report["invented"], sort_keys=True))
        return 1
    if full_ids["claim"] != set(compacted["order"]["claim"]):
        print("FAILED:IMP-0348-probe1 claim order set != full claim ids")
        return 1

    # Round-trip: serialize compacted JSON and re-measure reachability.
    roundtrip = json.loads(json.dumps(compacted))
    again = C.reachability(transcript, roundtrip)
    if again["claim_id_loss"] != 0 or not again["zero_loss"]:
        print("FAILED:IMP-0348-probe1 round-tripped compact lost ids")
        return 1

    print("SUCCESS:IMP-0348-probe1 zero claim-id loss across compaction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
