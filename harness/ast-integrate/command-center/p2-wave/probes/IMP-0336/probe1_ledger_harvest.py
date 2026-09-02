#!/usr/bin/env python3
"""IMP-0336 probe 1: ledger schema, harvest, and closed-disposition invariant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    evaluate_harvest,
    evaluate_invariant,
    protocol_writes_participant_output,
)


def main() -> int:
    harvest = evaluate_harvest()
    invariant = evaluate_invariant()
    writes = protocol_writes_participant_output()
    payload = {
        "probe": "probe1-ledger-harvest",
        "unit_id": "IMP-0336",
        "harvest": harvest,
        "invariant": invariant,
        "protocol_writes_participant_output": writes,
        "pass": bool(harvest["pass"] and invariant["pass"] and not writes),
    }
    # Drop bulky entry bodies from the printed harvest; keep counts and flags.
    printed = dict(payload)
    printed["harvest"] = {k: v for k, v in harvest.items() if k != "entries"}
    print(json.dumps(printed, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0336-probe1 ledger schema/harvest/invariant")
        return 1
    print(
        "harvest_entries={0} traceability={1} unmitigated={2}".format(
            harvest["entry_count"],
            invariant["traceability_count"],
            invariant["unmitigated_ids"],
        )
    )
    print("SUCCESS:IMP-0336-probe1 ledger schema, harvest, and mitigated-or-accepted invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
