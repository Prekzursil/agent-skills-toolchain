#!/usr/bin/env python3
"""Probe 2: execute each entry point UNSET and WRONG in a scratch env."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402
import execute as X  # noqa: E402

RAW = HERE / "probe2-unset-wrong.raw.json"


def main() -> int:
    report = X.run_all()
    RAW.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ctrl = report["both_states_control"]
    print(
        "executed={0} loud_distinct={1} silent_detected={2} file_distinct={3} live_distinct={4}".format(
            report["executed"],
            ctrl["loud_distinct"],
            ctrl["silent_detected"],
            ctrl["file_distinct"],
            ctrl["live_gates_distinct"],
        )
    )
    for row in report["rows"]:
        u = row.get("unset") or {}
        w = row.get("wrong") or {}
        print(
            "row id={id} distinct={d} silent={s} unset_rc={ur} wrong_rc={wr}".format(
                id=row.get("id"),
                d=row.get("distinct"),
                s=row.get("silent_degrade"),
                ur=u.get("rc"),
                wr=w.get("rc"),
            )
        )
    if not ctrl.get("ok"):
        print("FAILED:AUD-0079-probe2 both-states control did not discriminate")
        return 1
    if report.get("value_reported"):
        print("FAILED:AUD-0079-probe2 a credential value was reported")
        return 1
    print("SUCCESS:AUD-0079-probe2 unset vs wrong scratch execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
