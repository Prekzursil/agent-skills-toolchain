#!/usr/bin/env python3
"""Named probe 2: dry-run has zero side effects, measured.

Signal 1: sha256 tree map of a workspace is identical across dry-run.
Signal 2: instrumented spawn/egress counters stay at zero.
Both-states: the same workflow in real mode changes the tree; spawn and
egress mutants increment the matching counter.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import measure_all  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0227.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0227-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0227" not in text:
        print("FAILED:IMP-0227-probe2 sentinel absent")
        return 1

    rec = measure_all()
    side = rec["side_effects"]
    mutants = rec["mutants"]
    if not side["detector_silent_on_dry"]:
        print("FAILED:IMP-0227-probe2 dry-run had side effects")
        print(json.dumps(side, indent=2, default=str)[:3000])
        return 1
    if not side["detector_fires_on_real_writes"]:
        print("FAILED:IMP-0227-probe2 real run did not change the tree (inert detector)")
        return 1
    if not mutants["spawn"]["fired"]:
        print("FAILED:IMP-0227-probe2 spawn mutant did not trip the spawn counter")
        print(json.dumps(mutants["spawn"], indent=2, default=str))
        return 1
    if not mutants["egress"]["fired"]:
        print("FAILED:IMP-0227-probe2 egress mutant did not trip the egress counter")
        print(json.dumps(mutants["egress"], indent=2, default=str))
        return 1
    if not mutants["write"]["fired"]:
        print("FAILED:IMP-0227-probe2 write mutant was not refused")
        return 1
    if side["dry_ports"]["spawns"] != 0 or side["dry_ports"]["egress"] != 0:
        print("FAILED:IMP-0227-probe2 good dry-run ports not zero", side["dry_ports"])
        return 1

    out = {
        "probe": "probe2-side-effects",
        "unit_id": "IMP-0227",
        "pass": True,
        "dry_tree_identical": side["dry_tree"]["identical"],
        "real_tree_identical": side["real_tree"]["identical"],
        "dry_spawns": side["dry_ports"]["spawns"],
        "dry_egress": side["dry_ports"]["egress"],
        "spawn_mutant_spawns": mutants["spawn"]["spawns"],
        "egress_mutant_egress": mutants["egress"]["egress"],
        "write_mutant_refused": mutants["write"]["fired"],
        "computed_not_asserted": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "dry_identical=True real_changed=True spawn_mutant="
        f"{mutants['spawn']['spawns']} egress_mutant={mutants['egress']['egress']}"
    )
    print("SUCCESS:IMP-0227-probe2 zero side effects during dry-run (measured)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
