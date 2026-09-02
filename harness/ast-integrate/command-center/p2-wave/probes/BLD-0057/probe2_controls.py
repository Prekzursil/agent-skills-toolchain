#!/usr/bin/env python3
"""Probe 2: shared service spared; kill-mutant named failure; two counters disagree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import ramp as R  # noqa: E402

ART = REPO / "command-center" / "receipts" / "BLD-0057.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0057-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0057" or "SUCCESS:BLD-0057" not in json.dumps(doc):
        print("FAILED:BLD-0057-probe2 sentinel/unit")
        return 1
    guard = doc.get("guard") or {}
    if guard.get("action") != "REFUSE_RAISE" or guard.get("kills_shared_service") is not False:
        print("FAILED:BLD-0057-probe2 artifact guard claims")
        return 1
    if guard.get("reads_commit_charge") is not True or guard.get("reads_process_or_handle") is not True:
        print("FAILED:BLD-0057-probe2 guard does not claim both signals")
        return 1
    if doc.get("two_signals", {}).get("single_ram_reading_is_ceiling") is not False:
        print("FAILED:BLD-0057-probe2 single RAM reading claimed as ceiling")
        return 1
    if not doc.get("two_signals", {}).get("disagreement", {}).get("counters_disagree"):
        print("FAILED:BLD-0057-probe2 artifact missing disagreement")
        return 1
    tst = (doc.get("consumed_inputs") or {}).get("TST-0103") or {}
    if tst.get("re_derived") is True:
        print("FAILED:BLD-0057-probe2 TST-0103 was re-derived")
        return 1
    if doc.get("ceilings", {}).get("program_stops_first") is True and not (
        (doc.get("consumed_inputs") or {}).get("IMP-0445") or {}
    ).get("exists"):
        print("FAILED:BLD-0057-probe2 claimed program stops first without IMP-0445")
        return 1

    shared = R.run_shared_service_control(max_tagged=5)
    mutant = R.run_kill_mutant()
    disagree = R.run_signal_disagreement()
    if not disagree.get("counters_disagree"):
        disagree = R.run_signal_disagreement()

    if not shared.get("did_not_kill_shared"):
        print("FAILED:BLD-0057-probe2 real guard killed/lost shared", shared)
        return 1
    if not mutant.get("mutant_killed_shared"):
        print("FAILED:BLD-0057-probe2 kill mutant did not demonstrate failure class", mutant)
        return 1
    if not disagree.get("counters_disagree"):
        print("FAILED:BLD-0057-probe2 counters did not disagree", disagree)
        return 1
    if disagree.get("single_ram_reading_is_ceiling") is not False:
        print("FAILED:BLD-0057-probe2 RAM claimed as ceiling")
        return 1

    print(
        json.dumps(
            {
                "shared_spared": True,
                "mutant_killed_shared": True,
                "counters_disagree": True,
                "process_heavy": disagree["process_heavy"],
                "commit_heavy": disagree["commit_heavy"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:BLD-0057-probe2 shared-service spared; two independent signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
