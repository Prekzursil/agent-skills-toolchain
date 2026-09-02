#!/usr/bin/env python3
"""Named probe 2: same reducer identity + tally vs distinct-source count."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from experiment import run_experiment  # noqa: E402
from topology import FLAT_FANIN, NESTED_FANIN  # noqa: E402
from reducer import FANIN, reduce_many  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0095-council-of-councils-fanin.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0095-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    trace = doc.get("reducer_invocation_trace") or []
    fps = {t.get("predicate_fingerprint") for t in trace if t.get("predicate_fingerprint")}
    if len(fps) != 1:
        print(f"FAILED:CNF-0095-probe2 artifact trace fingerprints {fps}")
        return 1
    tally = doc.get("parent_tally_arithmetic") or {}
    if tally.get("tally_sum") != tally.get("distinct_source_count"):
        print(f"FAILED:CNF-0095-probe2 artifact tally arithmetic {tally}")
        return 1

    live = run_experiment()
    if not (FLAT_FANIN is NESTED_FANIN is FANIN is reduce_many):
        print("FAILED:CNF-0095-probe2 fan-in object identity broken")
        return 1
    if not live["same_fanin_object"]:
        print("FAILED:CNF-0095-probe2 same_fanin_object false")
        return 1
    if not live["same_fingerprint_both_levels"]:
        print(f"FAILED:CNF-0095-probe2 fingerprint mismatch {live['fingerprints']}")
        return 1
    if not live["same_predicate_id_both_levels"]:
        print(f"FAILED:CNF-0095-probe2 predicate id mismatch {live['predicate_ids']}")
        return 1
    if not live["topology_imports_shared_reducer"]:
        print("FAILED:CNF-0095-probe2 topology does not import shared reducer")
        return 1
    if not live["production_topology_has_no_private_predicate"]:
        print("FAILED:CNF-0095-probe2 topology defines a private predicate")
        return 1
    if not live["planted_private_predicate_detected"]:
        print("FAILED:CNF-0095-probe2 planted private-predicate control silent")
        return 1
    if not live["tally_ok"]:
        print(f"FAILED:CNF-0095-probe2 honest tally {live['disagree']['tally']}")
        return 1
    if not live["double_count_detected"]:
        print(f"FAILED:CNF-0095-probe2 double-count control {live['doubled']['tally']}")
        return 1
    if fps != set(live["fingerprints"]["nested"]):
        print(f"FAILED:CNF-0095-probe2 artifact fingerprint != live {fps} {live['fingerprints']}")
        return 1

    print(
        json.dumps(
            {
                "same_fanin_object": True,
                "fingerprint": live["predicate_fingerprint"],
                "tally_sum": live["disagree"]["tally"]["tally_sum"],
                "distinct_source_count": live["disagree"]["tally"]["distinct_source_count"],
                "double_count_control_fired": True,
                "planted_private_predicate_detected": True,
                "computed_not_asserted": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"identity ok fingerprint={live['predicate_fingerprint'][:12]} "
        f"tally={live['disagree']['tally']['tally_sum']}/"
        f"{live['disagree']['tally']['distinct_source_count']} "
        f"double_count_control=True"
    )
    print("SUCCESS:CNF-0095-probe2 shared reducer identity and tally arithmetic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
