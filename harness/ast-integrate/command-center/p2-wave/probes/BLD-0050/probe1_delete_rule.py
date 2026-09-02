#!/usr/bin/env python3
"""Probe 1: delete a known validation rule in a scratch copy; boundary flips UNCHECKED.

Control from the catalog: a CHECKED boundary whose named rule is removed from a
scratch copy of its source must become UNCHECKED. The live tree must stay CHECKED.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from census import RULES, build_census  # noqa: E402
from walk import REPO  # noqa: E402

TARGET = "TB-A2-TYPED-OUT"


def main() -> int:
    live = build_census()
    row = next(b for b in live["boundaries"] if b["id"] == TARGET)
    if row["check_status"] != "CHECKED":
        print(f"FAILED:BLD-0050-probe1 live {TARGET} is {row['check_status']}, want CHECKED")
        print(f"rule={row.get('validation_rule')} test={row.get('test_path')}")
        return 1
    spec = RULES[TARGET]
    src = REPO / spec["path"]
    original = src.read_text(encoding="utf-8")
    if spec["snippet"] not in original:
        print("FAILED:BLD-0050-probe1 snippet missing from live generator.py")
        return 1
    scratched = original.replace(spec["snippet"], "# DELETED-BY-BLD-0050-PROBE1", 1)
    if spec["snippet"] in scratched:
        print("FAILED:BLD-0050-probe1 scratch still contains the rule")
        return 1
    with tempfile.TemporaryDirectory(prefix="bld0050-rule-") as td:
        scratch = Path(td) / "generator.py"
        scratch.write_text(scratched, encoding="utf-8")
        mutant = build_census(rule_override_path=scratch)
        mrow = next(b for b in mutant["boundaries"] if b["id"] == TARGET)
        if mrow["check_status"] != "UNCHECKED":
            print(
                f"FAILED:BLD-0050-probe1 scratch {TARGET} is {mrow['check_status']}, "
                "want UNCHECKED after deleting the named rule"
            )
            return 1
        live2 = build_census()
        l2 = next(b for b in live2["boundaries"] if b["id"] == TARGET)
        if l2["check_status"] != "CHECKED":
            print("FAILED:BLD-0050-probe1 live tree did not remain CHECKED")
            return 1
    print(
        json_line(
            {
                "target": TARGET,
                "live_status": row["check_status"],
                "scratch_status": mrow["check_status"],
                "live_still_checked": True,
                "snippet": spec["snippet"],
                "rule_path": spec["path"],
                "test_path": spec["test_path"],
                "computed_not_asserted": True,
            }
        )
    )
    print(
        f"live={row['check_status']} scratch={mrow['check_status']} "
        "live_restored=CHECKED"
    )
    print("SUCCESS:BLD-0050-probe1 delete-rule control")
    return 0


def json_line(obj: dict) -> str:
    import json

    return json.dumps(obj, sort_keys=True)


if __name__ == "__main__":
    raise SystemExit(main())
