#!/usr/bin/env python3
"""Named probe 1: each strategy vs hand-computed sequence + order-trace audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from expectations import HAND_EXPECTED, HAND_ROSTER_SPEC, RANDOM_SEED  # noqa: E402
from tools.council.order import (  # noqa: E402
    PRODUCTION_STRATEGY_NAMES,
    Seat,
    audit_claimed,
    speaking_order,
)

ART = REPO / "command-center/receipts/IMP-0337.json"


def roster() -> tuple[Seat, ...]:
    return tuple(Seat(**row) for row in HAND_ROSTER_SPEC)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0337-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0337":
        print("FAILED:IMP-0337-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0337" not in text:
        print("FAILED:IMP-0337-probe1 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0337-probe1 self-declared", st)
        return 1

    live_names = list(PRODUCTION_STRATEGY_NAMES)
    if live_names != [
        "round-robin",
        "random",
        "priority",
        "seniority-inverted",
        "chair-recognition",
    ]:
        print("FAILED:IMP-0337-probe1 strategy set", live_names)
        return 1

    seats = roster()
    mismatches = []
    traces = []
    for (name, rnd, rec), claimed in HAND_EXPECTED.items():
        kwargs = {"round_index": rnd}
        if name == "random":
            kwargs["rng_seed"] = RANDOM_SEED
        if rec is not None:
            kwargs["recognition"] = rec
        produced = speaking_order(name, seats, **kwargs)
        audit = audit_claimed(name, seats, claimed, **kwargs)
        traces.append(audit)
        if produced != claimed or not audit["match"]:
            mismatches.append(
                {
                    "id": f"{name}/r{rnd}/rec={rec}",
                    "produced": produced,
                    "claimed": claimed,
                    "audit": audit,
                }
            )

    payload = {
        "probe": "probe1-strategy-trace",
        "unit_id": "IMP-0337",
        "n_hand_cases": len(HAND_EXPECTED),
        "mismatches": mismatches,
        "all_match": not mismatches,
        "strategies": live_names,
        "pass": not mismatches,
    }
    print(json.dumps(payload, sort_keys=True))
    if mismatches:
        print("FAILED:IMP-0337-probe1 order-trace audit disagreed with hand cases")
        return 1
    print("SUCCESS:IMP-0337-probe1 strategy sequences match hand-computed expectations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
