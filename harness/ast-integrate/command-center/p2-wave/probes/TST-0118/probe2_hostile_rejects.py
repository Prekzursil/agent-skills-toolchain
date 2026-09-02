#!/usr/bin/env python3
"""Probe 2: cyclic subworkflow typed-reject (not hang); zero-producer barrier typed-reject.

Mechanically different from probe 1: planted hostile fixtures and a naive
expander watchdog, not a campaign reach-rate table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import (  # noqa: E402
    test_cyclic_subworkflow_is_rejected_not_hung,
    test_zero_producer_barrier_is_rejected,
)


def main() -> int:
    cyclic = test_cyclic_subworkflow_is_rejected_not_hung()
    barrier = test_zero_producer_barrier_is_rejected()
    print(
        json.dumps(
            {
                "probe": "probe2-hostile-typed-reject",
                "cyclic_ok": cyclic["ok"],
                "cyclic_codes": cyclic["safe"]["codes"],
                "cyclic_elapsed_ms": cyclic["safe"]["elapsed_ms"],
                "cyclic_hung": cyclic["safe"]["hung"],
                "naive_codes": cyclic["naive"]["codes"],
                "good_accepted": cyclic["good"]["accepted"],
                "barrier_ok": barrier["ok"],
                "barrier_codes": barrier["bad"]["codes"],
                "barrier_good_accepted": barrier["good"]["accepted"],
                "loop_codes": barrier["loop_no_convergence"]["codes"],
            },
            sort_keys=True,
        )
    )
    if not cyclic["ok"]:
        print("FAILED:TST-0118-probe2 cyclic subworkflow not typed-rejected or hung")
        return 1
    if not barrier["ok"]:
        print("FAILED:TST-0118-probe2 zero-producer barrier not typed-rejected")
        return 1
    print(
        "cyclic={c} naive={n} barrier={b} loop={l} good_accepted={g}".format(
            c=cyclic["safe"]["codes"],
            n=cyclic["naive"]["codes"],
            b=barrier["bad"]["codes"],
            l=barrier["loop_no_convergence"]["codes"],
            g=cyclic["good"]["accepted"],
        )
    )
    print("SUCCESS:TST-0118-probe2 cyclic and zero-producer typed rejects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
