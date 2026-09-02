#!/usr/bin/env python3
"""Probe 2: required negative control + mutant sensitivity.

Catalog test: run the contradiction check against a contract clause known
to comply and confirm it returns no hit, proving the checker is not
flagging every clause. Both-states: a polarity-inverting mutant MUST hit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contradiction as C  # noqa: E402

NEED_MUTANT_RULES = {
    "MCP-LIFECYCLE-INIT-FIRST",
    "RFC8174-UPPERCASE-ONLY",
}


def main() -> int:
    result = C.evaluate()
    neg = result["negative_control"]
    mut = result["mutant_control"]
    fired = set(mut.get("fired_rule_ids") or [])
    mutant_ok = mut["pass"] and NEED_MUTANT_RULES <= fired
    print(
        json.dumps(
            {
                "probe": "probe2-negative-control",
                "unit_id": "RES-0139",
                "planned_contract_count": result["planned_contract_count"],
                "production_hit_count": result["production_hit_count"],
                "production_hits": result["production_hits"],
                "negative_control_hits": neg["hit_count"],
                "negative_control_pass": neg["pass"],
                "mutant_hit_count": mut["hit_count"],
                "mutant_fired_rule_ids": mut.get("fired_rule_ids"),
                "mutant_pass": mutant_ok,
            },
            indent=2,
        )
    )
    if not neg["pass"]:
        print("FAILED:RES-0139-probe2 complying clause was flagged (checker over-fires)")
        return 1
    if not mutant_ok:
        print("FAILED:RES-0139-probe2 mutant did not fire required rules (checker silent)")
        return 1
    print(
        "negative_control_silent_on_complying=True "
        f"mutant_fired={sorted(fired)} "
        f"production_hits={result['production_hit_count']}"
    )
    print("SUCCESS:RES-0139-probe2 negative control and mutant sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
