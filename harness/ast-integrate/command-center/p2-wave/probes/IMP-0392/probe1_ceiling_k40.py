#!/usr/bin/env python3
"""Probe 1: k=40 above-threshold case — reproduce overflow, then cap it.

Evidence is a tokenizer count of the *emitted* payload, not len//4.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.injection_budget import (  # noqa: E402
    HARD_CEILING_TOKENS,
    K_ADVERSARIAL,
    adversarial_k40,
    budget_inject,
    naive_inject,
)
from router.tokenizer import char_quarter_estimate, count_tokens  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0392-probe1 {msg}")
    return 1


def main() -> int:
    caps = adversarial_k40()
    if len(caps) != K_ADVERSARIAL:
        return fail(f"k={len(caps)} want {K_ADVERSARIAL}")
    if any(c.score < 0.5 for c in caps):
        return fail("not all 40 capabilities score above threshold")

    naive = naive_inject(caps)
    naive_measured = count_tokens(naive.payload)
    if naive_measured != naive.measured_tokens:
        return fail("naive decision count != tokenizer(payload)")
    if naive_measured <= HARD_CEILING_TOKENS:
        return fail(
            f"naive did not overflow: measured={naive_measured} ceiling={HARD_CEILING_TOKENS}"
        )
    if naive_measured == char_quarter_estimate(naive.payload):
        return fail("naive count equals len//4 — estimate, not a tokenizer measurement")
    if len(naive.selected_ids) != K_ADVERSARIAL:
        return fail("naive dropped capabilities; overflow was not reproduced")

    budgeted = budget_inject(caps)
    budgeted_measured = count_tokens(budgeted.payload)
    if budgeted_measured != budgeted.measured_tokens:
        return fail("budgeted decision count != tokenizer(payload)")
    if budgeted_measured > HARD_CEILING_TOKENS:
        return fail(
            f"ceiling missed: measured={budgeted_measured} ceiling={HARD_CEILING_TOKENS}"
        )
    if not budgeted.refused:
        return fail("k=40 did not refuse any capability; ceiling is not load-bearing")
    if len(budgeted.selected_ids) >= K_ADVERSARIAL:
        return fail("budgeted still selected all 40")
    if budgeted.counter_scope != "main-process":
        return fail(f"counter scope {budgeted.counter_scope}")
    if budgeted.running_tokens != budgeted_measured:
        return fail("running counter drifted from emitted payload")
    if not budgeted.overflow_prevented:
        return fail("overflow_prevented is false")

    report = {
        "probe": "probe1-ceiling-k40",
        "unit_id": "IMP-0392",
        "k": K_ADVERSARIAL,
        "all_above_threshold": True,
        "ceiling": HARD_CEILING_TOKENS,
        "naive": {
            "measured_tokens": naive_measured,
            "char_quarter_estimate": char_quarter_estimate(naive.payload),
            "selected": len(naive.selected_ids),
            "overflow_reproduced": True,
        },
        "budgeted": {
            "measured_tokens": budgeted_measured,
            "char_quarter_estimate": char_quarter_estimate(budgeted.payload),
            "selected": len(budgeted.selected_ids),
            "refused": len(budgeted.refused),
            "overflow_prevented": True,
            "counter_scope": budgeted.counter_scope,
            "tokenizer_id": budgeted.tokenizer_id,
        },
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:IMP-0392-probe1 k=40 naive overflows; "
        f"budgeted measured={budgeted_measured}<={HARD_CEILING_TOKENS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
