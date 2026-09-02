#!/usr/bin/env python3
"""Probe 1: unique-token stage walk. Localise the first absence of the tagged dissent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure as M  # noqa: E402


def run() -> dict:
    ev = M.evaluate()
    husk = ev["matrix"]["husk"]
    preserve = ev["matrix"]["preserve"]
    mutant = ev["matrix"]["drop_majority"]
    omit = ev["matrix"]["omit"]
    ok = (
        ev["majority_control_pass"]
        and ev["majority_drop_control_fires"]
        and ev["preserve_both_survive"]
        and husk["first_dissent_token_absent"] == "artifact_manifest"
        and omit["first_dissent_token_absent"] == "synthesis"
        and preserve["dissent_token_survived_every_stage"]
        and mutant["trace_broken"]
        and not husk["trace_broken"]
    )
    return {
        "probe": "probe1_token_trace",
        "ok": ok,
        "live_policy": "husk",
        "mechanism": "unique-token substring walk of serialized stage artifacts",
        "dissent_token": ev["tokens"]["dissent"],
        "majority_token": ev["tokens"]["majority"],
        "stages": ev["stages"],
        "husk_first_token_absent": husk["first_dissent_token_absent"],
        "omit_first_token_absent": omit["first_dissent_token_absent"],
        "preserve_token_survived": preserve["dissent_token_survived_every_stage"],
        "majority_survived_husk": husk["majority_survived_every_stage"],
        "majority_drop_breaks_trace": mutant["trace_broken"],
        "husk_rows": husk["rows"],
        "preserve_rows": preserve["rows"],
        "omit_rows": omit["rows"],
        "drop_majority_rows": mutant["rows"],
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=1, sort_keys=True))
    if not payload["ok"]:
        print("FAILED:ADV-0097-probe1 token trace contract")
        return 1
    print(
        "token_drop_stage={drop} majority_ok={maj} preserve_ok={pres} "
        "majority_drop_breaks={brk}".format(
            drop=payload["husk_first_token_absent"],
            maj=payload["majority_survived_husk"],
            pres=payload["preserve_token_survived"],
            brk=payload["majority_drop_breaks_trace"],
        )
    )
    print("SUCCESS:ADV-0097-probe1 token-tagged stage walk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
