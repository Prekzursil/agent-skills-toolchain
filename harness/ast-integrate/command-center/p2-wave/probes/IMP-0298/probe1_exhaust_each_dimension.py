#!/usr/bin/env python3
"""Probe 1: exhaust each CouncilSpec budget dimension in isolation.

Every dimension's fixture must produce BUDGET_EXHAUSTED on that dimension and
must not claim complete. Unknown budget keys must fail closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import ALL_DIMENSIONS, EXHAUST_FIXTURES, TITLE_DIMENSIONS  # noqa: E402
from tools.council.budget.governor import (  # noqa: E402
    BUDGET_EXHAUSTED,
    UnknownBudgetDimensionError,
    BudgetGovernor,
    run_fixture,
)


def main() -> int:
    failures: list[str] = []
    rows: list[dict] = []

    try:
        BudgetGovernor({"budgets": {"not_a_real_dial": 3}})
        failures.append("unknown key did not fail closed")
    except UnknownBudgetDimensionError as exc:
        rows.append({"check": "unknown-key-fail-closed", "ok": True, "detail": str(exc)})

    for dim in ALL_DIMENSIONS:
        fx = EXHAUST_FIXTURES[dim]
        result = run_fixture(spec=fx["spec"], events=fx["events"])
        exhausted = result.get("exhausted_dimensions") or []
        markers = result.get("markers") or []
        ok = (
            not result.get("complete")
            and BUDGET_EXHAUSTED in markers
            and fx["expect_exhausted"] in exhausted
        )
        prefix = fx.get("expect_text_prefix")
        if prefix and not str(result.get("text") or "").startswith(prefix):
            ok = False
            failures.append(f"{dim}: truncated text {result.get('text')!r} != prefix {prefix!r}")
        rows.append(
            {
                "dimension": dim,
                "ok": ok,
                "complete": result.get("complete"),
                "markers": markers,
                "exhausted_dimensions": exhausted,
                "text": result.get("text"),
                "title_dimension": dim in TITLE_DIMENSIONS,
            }
        )
        if not ok:
            failures.append(
                f"{dim}: complete={result.get('complete')} markers={markers} exhausted={exhausted}"
            )

    payload = {
        "probe": "probe1_exhaust_each_dimension",
        "unit_id": "IMP-0298",
        "dimensions_tested": list(ALL_DIMENSIONS),
        "title_dimensions": list(TITLE_DIMENSIONS),
        "rows": rows,
        "failures": failures,
        "pass": not failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        print("FAILED:IMP-0298-probe1 " + "; ".join(failures))
        return 1
    print(
        f"exhausted={len(ALL_DIMENSIONS)} title={len(TITLE_DIMENSIONS)} "
        "unknown_key_fail_closed=True"
    )
    print("SUCCESS:IMP-0298-probe1 exhaust-each-dimension")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
