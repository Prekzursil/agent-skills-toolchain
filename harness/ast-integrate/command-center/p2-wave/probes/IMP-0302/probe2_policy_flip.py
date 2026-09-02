#!/usr/bin/env python3
"""Named probe 2: changing the abstention policy must flip a recorded outcome.

Negative control required by the catalog: same ballots, same threshold, same
quorum; only abstention_policy_id changes; at least one outcome flips. That is
the proof that denominator treatment is configurable rather than implicit.

Both-states on the load-bearing pair:
  majority + quorum 4 + exclude_from_denominator -> ADOPT  (3/4 > 1/2)
  majority + quorum 4 + include_in_denominator   -> REJECT (3/6 is not > 1/2)

A second control: stripping abstention_policy_id must fail artifact validation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from load import load_tally  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0302.json"
BALLOTS = ["yes", "yes", "yes", "no", "abstain", "abstain"]


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0302-probe2 {msg}")
    return 1


def main() -> int:
    tally = load_tally()
    exclude = tally.tally_motion(
        BALLOTS,
        threshold_id="majority",
        abstention_policy_id="exclude_from_denominator",
        quorum_required=4,
        seated=6,
        motion_id="neg-exclude",
    )
    include = tally.tally_motion(
        BALLOTS,
        threshold_id="majority",
        abstention_policy_id="include_in_denominator",
        quorum_required=4,
        seated=6,
        motion_id="neg-include",
    )
    if exclude.get("outcome") != "ADOPT":
        return fail(f"exclude outcome={exclude.get('outcome')} want=ADOPT")
    if include.get("outcome") != "REJECT":
        return fail(f"include outcome={include.get('outcome')} want=REJECT")
    if exclude.get("outcome") == include.get("outcome"):
        return fail("policy change did not flip the recorded outcome")
    if exclude.get("abstention_policy_id") == include.get("abstention_policy_id"):
        return fail("policy ids identical after policy change")
    if exclude.get("denominator") == include.get("denominator"):
        return fail("denominators identical; policy is not load-bearing")

    park = tally.tally_motion(
        BALLOTS,
        threshold_id="majority",
        abstention_policy_id="park_on_any_abstention",
        quorum_required=4,
        seated=6,
        motion_id="neg-park",
    )
    if park.get("outcome") != "PARKED":
        return fail(f"park outcome={park.get('outcome')} want=PARKED")

    stripped = tally.policy_without_id(exclude)
    fired = False
    try:
        tally.validate_decision_artifact(stripped)
    except ValueError:
        fired = True
    if not fired:
        return fail("missing policy id was accepted (policy is not load-bearing)")
    try:
        tally.validate_decision_artifact(exclude)
    except ValueError as exc:
        return fail(f"good artifact rejected: {exc}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("catalog receipt missing")
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0302" not in json.dumps(receipt):
        return fail("sentinel absent from receipt")
    controls = receipt.get("negative_controls") or []
    if not any(c.get("fired_on_bad_state") is True for c in controls if isinstance(c, dict)):
        return fail("receipt negative_controls missing fired_on_bad_state")

    print(
        json.dumps(
            {
                "probe": "probe2-policy-flip",
                "unit_id": "IMP-0302",
                "exclude_outcome": exclude["outcome"],
                "include_outcome": include["outcome"],
                "park_outcome": park["outcome"],
                "flipped": True,
                "missing_policy_rejected": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"exclude={exclude['outcome']} include={include['outcome']} "
        f"park={park['outcome']} flipped=True missing_policy_rejected=True"
    )
    print("SUCCESS:IMP-0302-probe2 abstention policy flip and unrecorded-policy reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
