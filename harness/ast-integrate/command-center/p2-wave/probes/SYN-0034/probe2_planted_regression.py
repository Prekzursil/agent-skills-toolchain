#!/usr/bin/env python3
"""Named probe 2: planted regression hits row and net; listed under positive net."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from ledger import (  # noqa: E402
    FIXTURES,
    assert_table_internally_consistent,
    evaluate,
    regressions_listed,
)

ART = REPO / "command-center/synthesis/SYN-0034.improvement-ledger.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0034-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "SYN-0034":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    planted = evaluate(FIXTURES["planted_regression"])
    assert_table_internally_consistent(planted)
    prow = planted["changes"][0]
    if prow["verdict"] != "REGRESSED":
        return fail(f"planted row {prow['verdict']}")
    if planted["net"]["verdict"] != "REGRESSED":
        return fail(f"planted net {planted['net']['verdict']}")
    if prow["delta"] is None or prow["delta"] <= 0:
        return fail(f"planted latency delta {prow['delta']} (expected increase)")

    mixed = evaluate(FIXTURES["positive_net_with_regression"])
    assert_table_internally_consistent(mixed)
    if mixed["net"]["verdict"] != "IMPROVED":
        return fail(f"mixed net {mixed['net']['verdict']} (expected IMPROVED)")
    listed = mixed["regressions_listed"]
    if "ctrl.more-errors" not in listed:
        return fail(f"regression hidden by positive net {listed}")
    if listed != regressions_listed(mixed["changes"]):
        return fail("listed set is not a function of the rows")

    live_listed = doc.get("regressions_listed")
    if not isinstance(live_listed, list):
        return fail("live regressions_listed missing")
    live_rows = doc.get("changes") or []
    expected_live = regressions_listed(live_rows)
    if live_listed != expected_live:
        return fail(
            f"live listed {live_listed} != rows {expected_live}"
        )

    payload = {
        "pass": True,
        "probe": "probe2-planted-regression",
        "unit_id": "SYN-0034",
        "planted_row": prow["verdict"],
        "planted_net": planted["net"]["verdict"],
        "planted_delta": prow["delta"],
        "mixed_net": mixed["net"]["verdict"],
        "mixed_listed": listed,
        "live_listed": live_listed,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:SYN-0034-probe2 planted regression REGRESSED in row and net; "
        "ctrl.more-errors listed while mixed net is IMPROVED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
