#!/usr/bin/env python3
"""Probe 2: twelve single-condition negatives must all be REJECTED.

Any ACCEPT names the unenforced condition. Attribution guard: the positive
workspace must stay ACCEPTED in this same invocation, otherwise a mutant
REJECT is not attributable to its mutation. Condition independence: every
mutant except C02 (existence, which cascades into size/schema/consumer)
must unsatisfy exactly the targeted condition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import generator as G  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0416.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0416-probe2 {msg}")
    return 1


def main() -> int:
    suite = G.materialize(HERE / "fixtures", REPO)
    if not suite["positive_accepted"]:
        return fail(
            "attribution guard: positive REJECTED so mutant results are unattributable"
        )

    accepted = []
    isolation_miss = []
    for row in suite["mutations"]:
        n = row["condition"]
        cid = row["id"]
        verdict = row["reducer_verdict"]
        failing = row["failing"]
        isolated = G.independence_ok(row)
        print(
            f"cond {n:>2} {cid} {verdict:<6} failing={failing} "
            f"isolated={isolated} mutation={row['mutation']}"
        )
        if verdict == "ACCEPT":
            accepted.append(row)
        if not isolated:
            isolation_miss.append(row)
        if cid not in failing and verdict == "REJECT":
            return fail(
                f"{cid} REJECTED but targeted condition not in failing={failing}"
            )

    if accepted:
        named = [r["unenforced_condition"] for r in accepted]
        print(f"UNENFORCED {named}")
        return fail(f"reducer ACCEPTED {len(accepted)} negative(s): {named}")

    if isolation_miss:
        detail = [
            f"{r['id']}:{r['failing']}" for r in isolation_miss
        ]
        return fail(f"condition isolation missed {detail}")

    if not suite["all_twelve_rejected"]:
        return fail("all_twelve_rejected flag false")
    if not suite["exit_zero_alone_rejected"]:
        return fail("exit-zero-alone not rejected")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    table = doc.get("mutations") or []
    if len(table) != 12:
        return fail(f"receipt mutations rows={len(table)} want=12")
    for row in table:
        if row.get("reducer_verdict") != "REJECT":
            named = row.get("unenforced_condition") or row.get("id")
            return fail(f"receipt ACCEPT row without enforcement hole named? {named}")
    unenforced = doc.get("unenforced_conditions") or []
    if unenforced:
        return fail(f"receipt unenforced_conditions={unenforced}")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict not PASS")

    print("SUCCESS:IMP-0416-probe2 twelve negatives REJECTED and isolated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
