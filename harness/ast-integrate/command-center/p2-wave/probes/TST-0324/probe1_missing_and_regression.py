#!/usr/bin/env python3
"""TST-0324 probe 1: missing inputs -> NOT-CHECKED; regression beyond margin -> FALSE."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "bench" / "tests"))

from test_condition8 import (  # noqa: E402
    test_margin_ignoring_mutant_is_caught,
    test_missing_data_is_not_checked,
    test_regression_beyond_margin_is_false,
)

ART = REPO / "command-center" / "receipts" / "TST-0324.json"
SENTINEL = "SUCCESS:TST-0324"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    missing = test_missing_data_is_not_checked()
    regression = test_regression_beyond_margin_is_false()
    mutant = test_margin_ignoring_mutant_is_caught()
    payload = {
        "pass": bool(
            missing.get("pass") and regression.get("pass") and mutant.get("pass")
        ),
        "probe": "probe1-missing-and-regression",
        "missing_data": missing,
        "regression_beyond_margin": regression,
        "margin_ignoring_mutant": mutant,
        "unit_id": "TST-0324",
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:TST-0324-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print("FAILED:TST-0324-probe1 sentinel-absent")
            return 1
    if not payload["pass"]:
        print("FAILED:TST-0324-probe1 missing-data / regression / mutant")
        return 1
    print(
        "SUCCESS:TST-0324-probe1 missing->NOT-CHECKED; "
        "primary-up-secondary-beyond-margin->FALSE; "
        "margin-ignoring mutant caught"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
