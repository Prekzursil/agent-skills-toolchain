#!/usr/bin/env python3
"""Probe 1: exit-zero-alone is INCOMPLETE; each of 12 violating fixtures is rejected.

Positive control must be COMPLETE so the reducer is not a reject-everything detector.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    exit_zero_alone,
    materialize,
)
from lib.completion_reducer import (  # noqa: E402
    CONDITION_IDS,
    condition_line_table,
    reduce_completion,
)

ART = REPO / "command-center/receipts/IMP-0415.json"
SENTINEL = "SENTINEL:IMP-0415:REDUCER-TWELVE-CONDITIONS"


def failing_ids(verdict: dict) -> list[str]:
    return [
        str(r.get("id"))
        for r in (verdict.get("conditions") or [])
        if isinstance(r, dict) and r.get("result") == "FAIL"
    ]


def main() -> int:
    table = condition_line_table()
    gaps = [r for r in table if r.get("gap") or not r.get("line")]
    if len(table) != 12 or gaps:
        print(json.dumps({"pass": False, "reason": "condition-table-gap", "table": table}))
        print("FAILED:IMP-0415-probe1 condition table has a gap")
        return 1
    if [r["id"] for r in table] != list(CONDITION_IDS):
        print("FAILED:IMP-0415-probe1 condition ids drifted")
        return 1

    ez = reduce_completion(exit_zero_alone(), root=REPO)
    if ez.get("verdict") == "COMPLETE":
        print(json.dumps({"pass": False, "exit_zero": ez}, default=str)[:4000])
        print("FAILED:IMP-0415-probe1 exit-zero-alone returned COMPLETE")
        return 1
    if ez.get("verdict") != "INCOMPLETE":
        print(f"FAILED:IMP-0415-probe1 exit-zero-alone verdict={ez.get('verdict')}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="imp0415-probe1-"))
    pos_root = tmp / "positive"
    pos_record = materialize(pos_root, violate=None)
    pos = reduce_completion(pos_record, root=pos_root)
    if pos.get("verdict") != "COMPLETE":
        print(json.dumps({"pass": False, "positive": pos}, default=str)[:8000])
        print("FAILED:IMP-0415-probe1 positive control was not COMPLETE")
        return 1

    rows = []
    for n in range(1, 13):
        root = tmp / f"neg-{n:02d}"
        record = materialize(root, violate=n)
        out = reduce_completion(record, root=root)
        fails = failing_ids(out)
        want = f"C{n}"
        ok = out.get("verdict") != "COMPLETE" and want in fails
        rows.append(
            {
                "n": n,
                "id": want,
                "verdict": out.get("verdict"),
                "failing": fails,
                "rejected": ok,
                "reason": next(
                    (
                        r.get("reason")
                        for r in (out.get("conditions") or [])
                        if r.get("id") == want
                    ),
                    "",
                ),
            }
        )
        if not ok:
            print(json.dumps({"pass": False, "row": rows[-1], "full": out}, default=str)[:8000])
            print(f"FAILED:IMP-0415-probe1 condition {n} not rejected")
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:IMP-0415-probe1 self-declared {doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:IMP-0415-probe1 sentinel-absent in receipt")
            return 1
        table_live = doc.get("condition_table") or []
        if len(table_live) != 12:
            print("FAILED:IMP-0415-probe1 receipt condition_table is not 12 rows")
            return 1

    payload = {
        "pass": True,
        "probe": "probe1-twelve-violations",
        "exit_zero_verdict": ez.get("verdict"),
        "positive_verdict": pos.get("verdict"),
        "rejected": [r["n"] for r in rows if r["rejected"]],
        "rows": rows,
        "condition_table": table,
        "exit_code_alone_never_success": ez.get("exit_code_alone_never_success") is True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("exit-zero-alone=INCOMPLETE positive=COMPLETE rejected=12/12")
    print("SUCCESS:IMP-0415-probe1 twelve-violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
