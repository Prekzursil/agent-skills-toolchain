#!/usr/bin/env python3
"""BLD-0054 probe 1: both-states per spec abuse + required live controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402


def main() -> int:
    spec = R.run_spec_abuses()
    required = R.run_required_controls()
    failed = [
        aid
        for aid, row in {**spec, **required}.items()
        if not row.get("both_states_ok")
    ]
    instant = required["instant_unanimity"]
    ideas = required["idea_count_gaming"]
    dissent = required["dissent_loss"]
    extra_ok = (
        instant["enabled"]["detail"].get("blind_reeval") is True
        and ideas["enabled"]["detail"].get("distinct_kept") is True
        and R.DISSENT_TOKEN
        in " ".join(dissent["enabled"]["detail"].get("final_dissents") or [])
    )
    payload = {
        "probe": "probe1_both_states",
        "spec_abuses_ok": all(r["both_states_ok"] for r in spec.values()),
        "required_controls_ok": all(r["both_states_ok"] for r in required.values())
        and extra_ok,
        "failed": failed,
        "instant_unanimity_live": instant["enabled"]["detail"],
        "idea_count_gaming": ideas["enabled"]["detail"],
        "dissent_loss": dissent["enabled"]["detail"],
        "rows": {k: {"both_states_ok": v["both_states_ok"], "control": v["control"]} for k, v in spec.items()},
    }
    print(json.dumps(payload, sort_keys=True))
    if failed or not extra_ok:
        print(f"FAILED:BLD-0054-probe1 failed={failed} extra_ok={extra_ok}")
        return 1
    print("SUCCESS:BLD-0054-probe1 both-states and live required controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
