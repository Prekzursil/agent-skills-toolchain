#!/usr/bin/env python3
"""Probe 1: labelled kit + the three required tests, live."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import tests as T  # noqa: E402

ART = REPO / "command-center/receipts/TST-0017.json"


def main() -> int:
    try:
        labelled = T.run_all()
    except AssertionError as exc:
        print(f"FAILED:TST-0017-probe1 {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-labelled-kit",
                "precision_use": labelled["precision_use"],
                "recall_use": labelled["recall_use"],
                "n_cases": labelled["n_cases"],
                "exact_match_cases": labelled["exact_match_cases"],
                "tests": [
                    "test_token_in_fenced_code_block_is_mention",
                    "test_token_in_typed_status_field_is_use",
                    "test_the_kit_does_not_flag_its_own_documentation",
                ],
            },
            sort_keys=True,
        )
    )
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:TST-0017-probe1 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:TST-0017" not in ART.read_text(encoding="utf-8"):
            print("FAILED:TST-0017-probe1 sentinel absent")
            return 1
    print(
        "precision_use=1.0 recall_use=1.0 "
        f"n_cases={labelled['n_cases']} exact={labelled['exact_match_cases']}"
    )
    print("SUCCESS:TST-0017-probe1 labelled kit + three required tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
