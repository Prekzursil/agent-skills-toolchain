#!/usr/bin/env python3
"""IMP-0367 scenario: the full three-question sensitivity picture."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.sensitivity import compare_default, curve, load_question  # noqa: E402


def main() -> int:
    fx = HERE / "fixtures"
    out = {}
    for name in ("evidence-decisive", "n-sensitive", "default-below"):
        q = load_question(fx / f"{name}.json")
        c = curve(q)
        cd = compare_default(q)
        out[name] = {
            "n_star": c["stabilisation_point"],
            "stable": c["stable_decision"],
            "flips": c["flip_count"],
            "default_n": cd["default_n"],
            "decision_at_default": cd["decision_at_default"],
            "default_above_stable": cd["default_above_stable"],
        }
    ok = (out["evidence-decisive"]["n_star"] == 1
          and out["n-sensitive"]["n_star"] == 7
          and out["default-below"]["decision_at_default"] == "ACCEPT"
          and out["default-below"]["stable"] == "REJECT")
    print(json.dumps({"scenario": "council-sensitivity", "unit_id": "IMP-0367",
                      "pass": ok, "questions": out}, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0367-scenario curve expectations diverged")
        return 1
    print("SUCCESS:IMP-0367-scenario curves + defaults published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
