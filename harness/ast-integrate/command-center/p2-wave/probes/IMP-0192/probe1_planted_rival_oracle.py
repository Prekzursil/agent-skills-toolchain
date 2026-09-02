#!/usr/bin/env python3
"""IMP-0192 probe 1: planted rival completion oracle fires (both-states)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
TESTS = TOOLS / "agentrail" / "tests"
sys.path.insert(0, str(TOOLS / "agentspec"))
sys.path.insert(0, str(TOOLS / "agentrail"))
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TESTS))

from test_no_rival_core import (  # noqa: E402
    test_planted_rival_oracle_fires,
    test_string_literal_is_not_a_declaration,
)
from workflow_foundry.control_plane import scan_path  # noqa: E402

PLANTED = (
    REPO
    / "command-center"
    / "p2-wave"
    / "probes"
    / "IMP-0192"
    / "fixtures"
    / "planted_rival_oracle.py"
)


def main() -> int:
    planted = test_planted_rival_oracle_fires()
    trap = test_string_literal_is_not_a_declaration()
    live = scan_path(PLANTED, repo=REPO)
    live_oracle = [f.as_dict() for f in live if f.plane == "completion_oracle"]
    payload = {
        "id": "planted-rival-oracle",
        "pass": bool(planted["pass"] and trap["pass"] and live_oracle),
        "planted": planted,
        "string_trap": trap,
        "live_scan_oracle_hits": live_oracle,
        "both_states": {
            "planted_fires": bool(planted["python_oracle_hits"]),
            "canonical_owner_silent": bool(planted["canonical_owner_silent"]),
            "json_fusion_fires": bool(planted["json_oracle_hits"]),
            "string_trap_silent": bool(trap["pass"]),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0192-probe1 planted rival oracle")
        return 1
    print("SUCCESS:IMP-0192-probe1 planted rival oracle detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
