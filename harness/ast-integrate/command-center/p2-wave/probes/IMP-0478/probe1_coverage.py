#!/usr/bin/env python3
"""Coverage probe: every closed taxonomy class has an actionable message.

Also the required control: a class added later is reported as unmapped, and a
traceback-only body is not counted as coverage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import error_catalog as C  # noqa: E402

LATER = "later-invented-class"


def main() -> int:
    before = C.unmapped_classes(C.CLOSED_TAXONOMY, catalog={})
    after = C.unmapped_classes(C.CLOSED_TAXONOMY, C.CATALOG)
    table = C.coverage_table()
    later_gaps = C.unmapped_classes(list(C.CLOSED_TAXONOMY) + [LATER], C.CATALOG)
    tb = C.traceback_only_fixture()
    tb_ok = (not C.is_actionable(tb)) and (LATER in later_gaps)

    payload = {
        "probe": "probe1-coverage",
        "unit_id": "IMP-0478",
        "closed_class_count": len(C.CLOSED_TAXONOMY),
        "unmapped_before": len(before),
        "unmapped_after": len(after),
        "unmapped_before_classes": before,
        "unmapped_after_classes": after,
        "later_class": LATER,
        "later_class_reported_unmapped": LATER in later_gaps,
        "traceback_only_reported_unmapped": not C.is_actionable(tb),
        "coverage_table": table,
        "pass": (
            len(after) == 0
            and len(before) == len(C.CLOSED_TAXONOMY)
            and tb_ok
            and all(row["mapped"] for row in table)
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"unmapped_before={len(before)} unmapped_after={len(after)} "
        f"later_unmapped={LATER in later_gaps} traceback_unmapped={not C.is_actionable(tb)}"
    )
    if not payload["pass"]:
        print("FAILED:IMP-0478-probe1 coverage or control")
        return 1
    print("SUCCESS:IMP-0478-probe1 zero unmapped closed classes plus later-class control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
