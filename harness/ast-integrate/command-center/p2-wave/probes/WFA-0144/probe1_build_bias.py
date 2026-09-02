#!/usr/bin/env python3
"""Named probe 1: build-bias control (pure adoption must not BUILD).

Signal: live forge on the adoption goal returns ADOPT of the incumbent.
BUILD is proposed and loses on measured score. Zeroing KIND_COST['BUILD']
flips the winner to BUILD (two-sided). The uncovered goal does not false-
ADOPT an incomplete candidate. The unlicensed twin is ineligible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import (  # noqa: E402
    ART,
    build_bias_verdict,
    uncovered_not_false_adopt,
    zero_build_cost_mutant_fires,
)
from fixtures import ADOPTION_GOAL, UNCOVERED_GOAL  # noqa: E402
from forge import forge  # noqa: E402

UNIT = "WFA-0144"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    blob = json.dumps(doc)
    if "SUCCESS:WFA-0144" not in blob:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    live = forge(ADOPTION_GOAL)
    if not live.get("ok"):
        return fail("live adoption forge", live)
    bias = build_bias_verdict(live)
    if not bias["ok"]:
        return fail("build-bias", bias)

    mutant = zero_build_cost_mutant_fires()
    if not mutant["ok"]:
        return fail("zero-build-cost mutant did not fire", mutant)

    uncover = forge(UNCOVERED_GOAL)
    if not uncover.get("ok"):
        return fail("live uncovered forge", uncover)
    u = uncovered_not_false_adopt(uncover)
    if not u["ok"]:
        return fail("uncovered false-adopt", u)

    recorded = None
    for run in doc.get("runs") or []:
        if run.get("id") == "adoption-goal":
            recorded = run
            break
    if not recorded:
        return fail("artifact missing adoption-goal run")
    rec_kind = (recorded.get("winner") or {}).get("kind")
    if rec_kind != "ADOPT":
        return fail("artifact winner not ADOPT", rec_kind)
    if live["winner"]["variant_id"] != recorded["winner"]["variant_id"]:
        return fail(
            "live/artifact winner mismatch",
            {
                "live": live["winner"]["variant_id"],
                "artifact": recorded["winner"]["variant_id"],
            },
        )
    ctrl = doc.get("build_bias_control") or {}
    if ctrl.get("winner_kind") != "ADOPT" or not ctrl.get("build_score_lt_adopt"):
        return fail("artifact build_bias_control", ctrl)
    if not ctrl.get("zero_build_cost_mutant_fires"):
        return fail("artifact missing mutant-fires flag")

    payload = {
        "pass": True,
        "probe": "probe1-build-bias",
        "unit_id": UNIT,
        "winner_id": live["winner"]["variant_id"],
        "winner_kind": live["winner"]["kind"],
        "build_score": bias["build_score"],
        "adopt_score": bias["adopt_score"],
        "mutant_kind": mutant["mutant_kind"],
        "uncovered_kind": u["winner_kind"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"adopt={live['winner']['variant_id']} "
        f"build_score={bias['build_score']} "
        f"mutant_kind={mutant['mutant_kind']} "
        f"uncovered_kind={u['winner_kind']}"
    )
    print("SUCCESS:WFA-0144-probe1 build-bias control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
