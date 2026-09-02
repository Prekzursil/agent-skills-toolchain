#!/usr/bin/env python3
"""TST-0324 probe 2: genuine improvement -> TRUE with run ids; two evals agree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "bench" / "tests"))

from test_condition8 import (  # noqa: E402
    test_determinism,
    test_genuine_improvement_is_true_with_run_ids,
)

ART = REPO / "command-center" / "receipts" / "TST-0324.json"
SENTINEL = "SUCCESS:TST-0324"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    genuine = test_genuine_improvement_is_true_with_run_ids()
    deter = test_determinism()
    payload = {
        "pass": bool(genuine.get("pass") and deter.get("pass")),
        "probe": "probe2-true-and-determinism",
        "genuine_improvement": genuine,
        "determinism": deter,
        "unit_id": "TST-0324",
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0324-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0324-probe2 sentinel-absent")
            return 1
    if not payload["pass"]:
        print("FAILED:TST-0324-probe2 genuine-TRUE / determinism")
        return 1
    if genuine.get("verdict") == "TRUE" and not genuine.get("run_ids"):
        print("FAILED:TST-0324-probe2 TRUE with no run ids (prose assertion)")
        return 1
    print(
        "SUCCESS:TST-0324-probe2 genuine->TRUE with run ids; "
        "two evaluations of the same ledger agree"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
