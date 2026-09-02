#!/usr/bin/env python3
"""Named probe 2: each of the six required elements, removed one at a time,
produces a distinct registration failure (6/6).

Both-states: the unmodified scaffold still registers. A shared generic
rejection id across mutants is a detector failure, not a pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib import SENTINEL, TOOLS, load_receipt  # noqa: E402

sys.path.insert(0, str(TOOLS))
from blueprint_contract import (  # noqa: E402
    REQUIRED_ELEMENTS,
    VIOLATION_ID,
    omit_element,
    register_blueprint,
    scaffold_blueprint,
)


def main() -> int:
    load_receipt()
    intact = scaffold_blueprint()
    good = register_blueprint(intact)
    if not good.ok:
        print("FAILED:IMP-0230-probe2 control scaffold does not register")
        print(json.dumps(good.as_dict(), indent=2))
        return 1

    rows = []
    seen: list[str] = []
    for element in REQUIRED_ELEMENTS:
        want = VIOLATION_ID[element]
        mutant = omit_element(intact, element)
        result = register_blueprint(mutant)
        ids = result.violation_ids
        if result.ok:
            print(f"FAILED:IMP-0230-probe2 omit {element} still registered")
            return 1
        if want not in ids:
            print(
                f"FAILED:IMP-0230-probe2 omit {element}: want {want} got {ids}"
            )
            return 1
        extra = [i for i in ids if i != want]
        if extra:
            print(
                f"FAILED:IMP-0230-probe2 omit {element} leaked extra ids {extra}"
            )
            return 1
        if ids.count(want) != 1:
            print(f"FAILED:IMP-0230-probe2 omit {element} duplicated {want}")
            return 1
        seen.append(want)
        rows.append(
            {
                "omitted": element,
                "registered": False,
                "violation_ids": ids,
            }
        )

    if len(seen) != 6 or len(set(seen)) != 6:
        print(f"FAILED:IMP-0230-probe2 distinct ids {seen}")
        return 1
    closed = [VIOLATION_ID[e] for e in REQUIRED_ELEMENTS]
    if sorted(seen) != sorted(closed):
        print(f"FAILED:IMP-0230-probe2 id set {seen} != {closed}")
        return 1

    still = register_blueprint(scaffold_blueprint())
    if not still.ok:
        print("FAILED:IMP-0230-probe2 control went red after mutants")
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-six-omissions",
                "unit_id": "IMP-0230",
                "control_registers": True,
                "omissions": 6,
                "distinct_violation_ids": 6,
                "ids": seen,
                "rows": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"{SENTINEL}-probe2 6/6 one-at-a-time omissions produce distinct rejections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
