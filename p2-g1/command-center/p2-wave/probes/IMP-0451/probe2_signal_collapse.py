#!/usr/bin/env python3
"""IMP-0451 probe2 (mutation): collapsing the two independent streams into
one bit (OR or AND) must make the mixed cells indistinguishable and turn
four-cell distinctness red. The production pair stays distinct under the
same inputs - proving it really consumes two signals."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MS_PY = REPO / "tools" / "command-center" / "monitor_states.py"

spec = importlib.util.spec_from_file_location("imp0451_monitor_states", MS_PY)
M = importlib.util.module_from_spec(spec)
sys.modules["imp0451_monitor_states"] = M
spec.loader.exec_module(M)


def fail(msg):
    print("FAILED:IMP-0451-probe2 " + str(msg))
    return 1


def main() -> int:
    or_map = {
        M.CELL_ALIVE_ACTIVE: M.collapse_or(True, True),
        M.CELL_ALIVE_IDLE: M.collapse_or(True, False),
        M.CELL_DEAD_ACTIVE: M.collapse_or(False, True),
        M.CELL_DEAD_IDLE: M.collapse_or(False, False),
    }
    or_indist = M.mixed_cells_indistinguishable(or_map)
    or_distinct = M.four_verdicts_distinct(or_map)
    if not or_indist:
        return fail("OR mutant leaves mixed cells distinguishable: %s" % json.dumps(or_map))
    if or_distinct:
        return fail("OR mutant keeps four distinct verdicts: %s" % json.dumps(or_map))

    and_map = {
        M.CELL_ALIVE_ACTIVE: M.collapse_and(True, True),
        M.CELL_ALIVE_IDLE: M.collapse_and(True, False),
        M.CELL_DEAD_ACTIVE: M.collapse_and(False, True),
        M.CELL_DEAD_IDLE: M.collapse_and(False, False),
    }
    and_indist = M.mixed_cells_indistinguishable(and_map)
    and_distinct = M.four_verdicts_distinct(and_map)
    if not and_indist:
        return fail("AND mutant leaves mixed cells distinguishable: %s" % json.dumps(and_map))
    if and_distinct:
        return fail("AND mutant keeps four distinct verdicts: %s" % json.dumps(and_map))

    live = M.four_cell_live()
    if not M.four_verdicts_distinct(live["verdicts"]):
        return fail("production detector lost distinctness - regression")
    if live.get("production_mixed_indistinguishable", False):
        return fail("production mixed cells indistinguishable - regression")

    print(json.dumps({
        "probe": "probe2-signal-collapse",
        "unit_id": "IMP-0451",
        "or_mutant": or_map,
        "or_mixed_indistinguishable": or_indist,
        "or_four_distinct": or_distinct,
        "and_mutant": and_map,
        "and_mixed_indistinguishable": and_indist,
        "and_four_distinct": and_distinct,
        "production_verdicts": live["verdicts"],
        "production_four_distinct": live["four_distinct"],
        "mutation_detected": True,
        "sentinel": "SENTINEL:IMP-0451:MONITOR-STATES-DISTINGUISHED",
    }, indent=2))
    print("SUCCESS:IMP-0451-probe2 OR and AND collapses both make mixed cells indistinguishable; production pair stays distinct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
