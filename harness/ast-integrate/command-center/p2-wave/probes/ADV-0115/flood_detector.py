#!/usr/bin/env python3
"""Both-states flood detector for ADV-0115.

RED when tokenizer count of the emitted payload exceeds HARD_CEILING_TOKENS.
Must fire on the naive/flood mutant and stay silent on the budgeted path.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402

from router.injection_budget import (  # noqa: E402
    HARD_CEILING_TOKENS,
    adversarial_k40,
    budget_inject,
    naive_inject,
)
from router.tokenizer import count_tokens  # noqa: E402


def detect(measured_tokens: int) -> dict:
    red = C.flood_red(measured_tokens, HARD_CEILING_TOKENS)
    return {
        "measured_tokens": int(measured_tokens),
        "ceiling": HARD_CEILING_TOKENS,
        "red": red,
        "verdict": "FLOOD" if red else "WITHIN-BUDGET",
    }


def both_states() -> dict:
    caps = adversarial_k40()
    naive = naive_inject(caps)
    budgeted = budget_inject(caps)
    naive_count = count_tokens(naive.payload)
    budgeted_count = count_tokens(budgeted.payload)
    bad = detect(naive_count)
    good = detect(budgeted_count)
    return {
        "probe": "flood-detector-both-states",
        "unit_id": C.UNIT_ID,
        "bad_state": bad,
        "good_state": good,
        "fired_on_bad_state": bad["red"] is True,
        "silent_on_good_state": good["red"] is False,
        "pass": bad["red"] is True and good["red"] is False,
    }


def main() -> int:
    report = both_states()
    print(json.dumps(report, sort_keys=True))
    if not report["pass"]:
        print(
            f"FAILED:{C.UNIT_ID}-flood-detector "
            f"bad_red={report['fired_on_bad_state']} "
            f"good_silent={report['silent_on_good_state']}"
        )
        return 1
    print(
        f"SUCCESS:{C.UNIT_ID}-flood-detector "
        f"naive={report['bad_state']['measured_tokens']} FLOOD; "
        f"budgeted={report['good_state']['measured_tokens']} WITHIN-BUDGET"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
