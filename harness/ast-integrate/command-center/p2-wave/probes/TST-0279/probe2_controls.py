#!/usr/bin/env python3
"""Named probe 2: both-states, incompatible seating, live veto vs usurper.

Mechanically different from probe 1 (which only reads the enforced matrix):
  * enforcement ON vs stripped — forbidden cells must leak only when stripped
  * proposer+judge seating refused; proposer+critic seating permitted
  * guardian veto BLOCKS the motion; observer veto is refused and does not block
  * muting the veto check must turn the usurper cell green (control is live)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from runtime import (  # noqa: E402
    incompatible_trial,
    run_full_matrix,
    veto_trial,
    CouncilRuntime,
)


def _forbidden_observed(result: dict) -> dict[tuple[str, str], str]:
    return {
        (c["role"], c["action"]): c["observed"]
        for c in result["cells"]
        if c["expected"] == "REFUSED"
    }


def main() -> int:
    on = run_full_matrix(enforce=True)
    off = run_full_matrix(enforce=False)
    if not on["matrix_ok"]:
        print("FAILED:TST-0279-probe2 enforced matrix not clean")
        return 1
    if on["forbidden_leaked"] != 0:
        print("FAILED:TST-0279-probe2 enforced runtime leaked forbidden cells")
        return 1
    if off["forbidden_leaked"] != off["forbidden_total"]:
        print(
            "FAILED:TST-0279-probe2 stripped runtime did not leak every forbidden cell "
            f"leaked={off['forbidden_leaked']} total={off['forbidden_total']}"
        )
        return 1
    on_f = _forbidden_observed(on)
    off_f = _forbidden_observed(off)
    if on_f.keys() != off_f.keys():
        print("FAILED:TST-0279-probe2 forbidden-cell key set drifted")
        return 1
    diverged = sum(1 for k in on_f if on_f[k] != off_f[k])
    if diverged != len(on_f):
        print(f"FAILED:TST-0279-probe2 both-states divergence {diverged}/{len(on_f)}")
        return 1

    inc = incompatible_trial()
    if not inc["ok"]:
        print("FAILED:TST-0279-probe2 incompatible seating")
        print(json.dumps(inc, indent=2))
        return 1

    vt = veto_trial()
    if not vt["ok"]:
        print("FAILED:TST-0279-probe2 veto trial")
        print(json.dumps(vt, indent=2))
        return 1

    # Mute only the veto action: usurper must now succeed and BLOCK — proving
    # the refusal was the check, not a missing method.
    muted = CouncilRuntime(mute_checks=frozenset({"veto"}))
    muted.seat("o", "observer")
    muted.pending_motion = "motion-mute"
    muted.motion_status = "OPEN"
    leaked = muted.attempt("o", "veto")
    if leaked.observed != "PERMITTED" or muted.motion_status != "BLOCKED":
        print(
            "FAILED:TST-0279-probe2 veto-mute control did not leak "
            f"obs={leaked.observed} status={muted.motion_status}"
        )
        return 1

    summary = {
        "probe": "probe2_controls",
        "enforced_forbidden_leaked": on["forbidden_leaked"],
        "stripped_forbidden_leaked": off["forbidden_leaked"],
        "stripped_forbidden_total": off["forbidden_total"],
        "both_states_diverged": diverged,
        "incompatible_refused": inc["bad_observed"],
        "compatible_permitted": inc["good_observed"],
        "holder_veto_blocks": vt["holder_blocked"],
        "nonholder_veto_refused": vt["nonholder_observed"],
        "nonholder_motion_still_open": vt["nonholder_motion_status"] == "OPEN",
        "veto_mute_leaked": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"both_states leaked_off={off['forbidden_leaked']} leaked_on={on['forbidden_leaked']} "
        f"incompatible={inc['bad_observed']} veto_holder={vt['holder_motion_status']} "
        f"veto_usurper={vt['nonholder_motion_status']}"
    )
    print("SUCCESS:TST-0279-probe2 both-states, incompatible seating, veto effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
