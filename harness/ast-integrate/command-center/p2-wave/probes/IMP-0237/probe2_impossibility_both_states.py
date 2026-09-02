#!/usr/bin/env python3
"""IMP-0237 probe 2: impossible request yields proof, not an empty pass (both-states)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "research_blueprints" / "tests"))

from test_imp0237 import run_all  # noqa: E402


def main() -> int:
    result = run_all()
    imp = result["rows"]["impossibility"]
    exits = result["rows"]["exits"]
    payload = {
        "id": "impossibility-both-states",
        "pass": bool(imp["pass"] and exits["pass"]),
        "impossibility": imp,
        "distinct_exits": exits,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0237-probe2 proof-of-impossibility both-states")
        return 1
    both = imp["both_states"]
    print(
        f"obtainable_kind={imp['obtainable_kind']} "
        f"impossible_valid={imp['impossible_valid']} "
        f"miss_kind={imp['miss_kind']} "
        f"empty_search_rejected={imp['empty_search_rejected']} "
        f"exits={exits['run_returns']}"
    )
    print("SUCCESS:IMP-0237-probe2 impossible request yields proof-of-impossibility")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
