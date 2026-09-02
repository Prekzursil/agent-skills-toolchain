#!/usr/bin/env python3
"""Probe 2: all-satisfied control PASS, always-true reducer fails the harness,
coupling report records any inseparable pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import reducer as R  # noqa: E402

REPO = HERE.parents[3]


def main() -> int:
    rows = C.run_corpus(REPO, eval_fn=R.evaluate)
    pas = next(r for r in rows if r["intended_violation"] is None)
    print(
        f"test_all_satisfied_row_passes verdict={pas['verdict']} "
        f"failing={pas['failing_condition_id']} unsatisfied={pas['unsatisfied']} "
        f"isolated={pas['isolated']}"
    )
    pass_ok = pas["isolated"] is True and pas["verdict"] == "PASS"
    if not pass_ok:
        print(f"FAILED:TST-0002-probe2 pass row not PASS reason={pas['reason']}")
        return 1

    stub_rows = C.run_corpus(REPO, eval_fn=R.always_pass)
    stub_ok = C.isolation_ok(stub_rows)
    print(
        f"negative_control always-true-reducer harness_ok={stub_ok} "
        f"(must be False)"
    )
    if stub_ok:
        print("FAILED:TST-0002-probe2 always-true stub was accepted by the harness")
        return 1

    coupling = C.coupling_report(rows)
    print("coupling " + json.dumps(coupling, sort_keys=True))
    if coupling["isolated_count"] != 12 or coupling["pass_row_ok"] is not True:
        print("FAILED:TST-0002-probe2 coupling summary disagrees with isolation")
        return 1
    if coupling["inseparable_pairs"] or coupling["contract_defects"]:
        print(
            "FAILED:TST-0002-probe2 unexpected coupling; "
            "independently-addressable checks should isolate all 12"
        )
        return 1
    print(
        "SUCCESS:TST-0002-probe2 pass-row PASS, always-true stub rejected, "
        "coupling report empty"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
