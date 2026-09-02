#!/usr/bin/env python3
"""Named probe 2: docs/policy parity, plus docs-only mutation going red."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.governance import (  # noqa: E402
    ACTIONS,
    DOCS_PATH,
    ROLES,
    mutate_docs_allow_to_deny,
    parity,
)

HERE = Path(__file__).resolve().parent
RAW = HERE / "probe2-parity.raw.json"


def main() -> int:
    live = parity()
    if not live.ok:
        print("FAILED:IMP-0111-probe2 live parity mismatches: " + "; ".join(live.mismatches))
        return 1
    expected = len(ROLES) * len(ACTIONS)
    if live.policy_cells != expected or live.docs_cells != expected:
        print(
            f"FAILED:IMP-0111-probe2 cell count policy={live.policy_cells} docs={live.docs_cells}"
        )
        return 1

    original = DOCS_PATH.read_text(encoding="utf-8")
    mutated = mutate_docs_allow_to_deny(original, role="publisher", action="publish")
    if mutated == original:
        print("FAILED:IMP-0111-probe2 mutation was a no-op")
        return 1
    red = parity(docs_text=mutated)
    if red.ok:
        print("FAILED:IMP-0111-probe2 mutated docs still matched policy")
        return 1
    after = DOCS_PATH.read_text(encoding="utf-8")
    if after != original:
        print("FAILED:IMP-0111-probe2 live GOVERNANCE.md was modified")
        return 1

    payload = {
        "probe": "probe2-docs-parity",
        "unit_id": "IMP-0111",
        "live_ok": live.ok,
        "policy_cells": live.policy_cells,
        "docs_cells": live.docs_cells,
        "negative_control_docs_only_mutation_goes_red": (not red.ok),
        "negative_control_mismatches": red.mismatches,
        "live_docs_unmodified": True,
        "pass": True,
    }
    RAW.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(
        "parity_ok=True"
        + f" cells={expected}"
        + " negative_control_red=True"
        + " live_docs_unmodified=True"
    )
    print("SUCCESS:IMP-0111-probe2 docs-policy parity and docs-only mutation control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
