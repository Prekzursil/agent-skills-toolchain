#!/usr/bin/env python3
"""Probe 1: a constructed cycle is detected BEFORE tabulation.

Negative control (verbatim): what the check does on the state it rejects.
Mutant: skipping the cycle gate lets tabulate run on the same fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import delegate as D  # noqa: E402

ART = REPO / "command-center/design/council/CNL-0067-delegation-and-proxy-voting-without-delegation-cycles.md"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0067-probe1 {msg}")
    return 1


def spy_process(profile: dict) -> tuple[dict, int]:
    n = {"calls": 0}

    def spy(p, effective):
        n["calls"] += 1
        return D.tabulate(p, effective)

    row = D.process(profile, tabulate_fn=spy)
    return row, n["calls"]


def main() -> int:
    cycle = D.load_profile(FIX / "cycle-abc.json")
    loop = D.load_profile(FIX / "self-loop.json")
    good = D.load_profile(FIX / "good-under-cap.json")
    dangling = D.load_profile(FIX / "unknown-delegate.json")

    cyc_row, cyc_calls = spy_process(cycle)
    print("cycle-abc " + D.compact(cyc_row) + f" tabulate_calls={cyc_calls}")
    if cyc_row["status"] != D.STATUS_CYCLE:
        return fail(f"cycle-abc status={cyc_row['status']}")
    if cyc_row["tabulated"] is not False or cyc_row["winner"] is not None:
        return fail("cycle-abc tabulated or produced a winner")
    if cyc_calls != 0:
        return fail(f"cycle-abc called tabulate {cyc_calls} times")
    members = set(cyc_row["cycles"][0][:-1]) if cyc_row["cycles"] else set()
    if members != {"A", "B", "C"}:
        return fail(f"cycle members {members}")

    loop_row, loop_calls = spy_process(loop)
    print("self-loop " + D.compact(loop_row) + f" tabulate_calls={loop_calls}")
    if loop_row["status"] != D.STATUS_CYCLE or loop_calls != 0:
        return fail("self-loop was not rejected before tabulation")

    dang_row, dang_calls = spy_process(dangling)
    print("unknown-delegate " + D.compact(dang_row) + f" tabulate_calls={dang_calls}")
    if dang_row["status"] != D.STATUS_UNKNOWN or dang_calls != 0:
        return fail("dangling delegate was tabulated")

    good_row, good_calls = spy_process(good)
    print("good-under-cap " + D.compact(good_row) + f" tabulate_calls={good_calls}")
    if good_row["status"] != D.STATUS_OK or good_row["tabulated"] is not True:
        return fail("good fixture was not tabulated")
    if good_calls != 1:
        return fail(f"good fixture tabulate_calls={good_calls}")

    try:
        mutant = D.process(cycle, skip_cycle_check=True)
    except RuntimeError as exc:
        print(f"mutant-skip-cycle-check raised {exc}")
        mutant = {"status": "RAISED", "tabulated": None, "winner": None}
    else:
        print(
            f"mutant-skip-cycle-check status={mutant.get('status')} "
            f"tabulated={mutant.get('tabulated')}"
        )
    if mutant.get("status") == D.STATUS_CYCLE and mutant.get("tabulated") is False:
        return fail("skip_cycle_check still reported DELEGATION_CYCLE; gate is not live")

    if not ART.is_file():
        return fail(f"artifact missing {ART}")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("sentinel") != "SUCCESS:CNL-0067":
        return fail("sentinel mismatch")
    bs = doc.get("both_states") or {}
    if "DELEGATION_CYCLE" not in str(bs.get("verbatim_fire") or ""):
        return fail("both_states.verbatim_fire does not record DELEGATION_CYCLE")
    if "TABULATED" not in str(bs.get("verbatim_silent") or "") and "tabulated=True" not in str(
        bs.get("verbatim_silent") or ""
    ):
        live_silent = D.compact(good_row)
        if live_silent not in str(bs.get("verbatim_silent") or ""):
            return fail("both_states.verbatim_silent does not match good fixture")
    ncs = doc.get("negative_controls") or []
    if not any("DELEGATION_CYCLE" in str(n.get("observed") or "") for n in ncs):
        return fail("negative_controls missing cycle reject observation")

    print(
        "NEGATIVE-CONTROL cycle-abc: "
        "check find_cycles + CYCLE-GATE refuse tabulation; "
        f"observed {D.compact(cyc_row)}"
    )
    print("SUCCESS:CNL-0067-probe1 cycle detected before tabulation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
