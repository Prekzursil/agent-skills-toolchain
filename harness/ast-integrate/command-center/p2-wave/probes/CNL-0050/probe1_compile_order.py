#!/usr/bin/env python3
"""Probe 1: compile-time diverge-before-converge.

Both-states: known-good nest is accepted; planted converge-before-diverge
is rejected. Negative control recorded verbatim.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose as C  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0050-probe1 {msg}")
    return 1


def main() -> int:
    good = C.compile_expr(C.KNOWN_GOOD["expr"])
    bad = C.compile_expr(C.PLANTED_BAD["expr"])
    bad_splice = C.compile_expr(C.PLANTED_BAD_SPLICE["expr"])
    rec = C.negative_control_record()
    print(
        f"good id={C.KNOWN_GOOD['id']} accepted={good['accepted']} "
        f"stage={good['stage']} code={good['code']} n_events={len(good['events'])}"
    )
    print(rec["verbatim"])
    print(f"what_rejects: {rec['what_the_check_does_on_the_state_it_rejects']}")
    print(
        f"splice_bad id={C.PLANTED_BAD_SPLICE['id']} accepted={bad_splice['accepted']} "
        f"code={bad_splice['code']}"
    )
    print(
        json.dumps(
            {
                "fired_on_bad": (not bad["accepted"] and bad["code"] == "converge-before-diverge"),
                "silent_on_good": good["accepted"] is True,
                "splice_also_rejected": (
                    not bad_splice["accepted"]
                    and bad_splice["code"] == "converge-before-diverge"
                ),
            },
            sort_keys=True,
        )
    )
    if good["accepted"] is not True:
        return fail("known-good composition was rejected")
    if bad["accepted"] or bad["code"] != "converge-before-diverge":
        return fail("planted converge-before-diverge was not rejected at compile time")
    if bad_splice["accepted"] or bad_splice["code"] != "converge-before-diverge":
        return fail("planted splice-converge-at-head was not rejected")
    kinds = [e["kind"] for e in good["events"]]
    if kinds[0] != "diverge" or kinds[-1] != "converge":
        return fail(f"good linearization lost nest brackets: {kinds}")
    print("SUCCESS:CNL-0050-probe1 compile-time diverge-before-converge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
