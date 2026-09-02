#!/usr/bin/env python3
"""Probe 2: BUDGET_EXHAUSTED is load-bearing; transport token count is independent.

Negative control: strip the marker from a truncated artifact and show a labelled
reader then treats the partial as complete.

Evidence 2: governor whitespace-word count vs transport UTF-8-ceil-div-4 count
on the same text; algorithms must differ and counts must be compared (they
need not be equal).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import COMPLETE_CONTROL, EXHAUST_FIXTURES  # noqa: E402
from tools.council.budget.governor import (  # noqa: E402
    BUDGET_EXHAUSTED,
    governor_token_count,
    marker_is_load_bearing,
    run_fixture,
)
from tools.council.budget.transport import transport_token_count  # noqa: E402


def main() -> int:
    failures: list[str] = []

    complete = run_fixture(
        spec=COMPLETE_CONTROL["spec"], events=COMPLETE_CONTROL["events"]
    )
    if not complete.get("complete") or BUDGET_EXHAUSTED in (complete.get("markers") or []):
        failures.append(f"complete control was not complete: {complete}")

    partial = run_fixture(
        spec=EXHAUST_FIXTURES["tokens"]["spec"],
        events=EXHAUST_FIXTURES["tokens"]["events"],
    )
    if BUDGET_EXHAUSTED not in (partial.get("markers") or []):
        failures.append("token exhaustion did not label BUDGET_EXHAUSTED")
    if partial.get("complete"):
        failures.append("token exhaustion claimed complete")

    load = marker_is_load_bearing(complete, partial)
    if not load.get("pass"):
        failures.append(f"marker not load-bearing: {load}")

    sample = "alpha bravo charlie delta echo"
    gov_n = governor_token_count(sample)
    tr_n = transport_token_count(sample)
    compared = {
        "sample": sample,
        "governor_whitespace_words": gov_n,
        "transport_utf8_ceil_div4": tr_n,
        "algorithms": {
            "governor": "str.split whitespace words",
            "transport": "utf-8 byte length ceil-div 4",
        },
        "compared": True,
        "counts_equal": gov_n == tr_n,
        "independence_shown": gov_n != tr_n,
    }
    if gov_n == tr_n:
        failures.append(
            f"transport count collided with governor ({gov_n}); independence not shown"
        )
    if gov_n != 5:
        failures.append(f"governor count {gov_n} expected 5")

    receipt = REPO / "command-center/receipts/IMP-0298.json"
    receipt_ok = receipt.is_file() and receipt.stat().st_size > 0
    if receipt_ok:
        doc = json.loads(receipt.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        if "SUCCESS:IMP-0298" not in blob:
            failures.append("receipt missing SUCCESS:IMP-0298 sentinel")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            failures.append(f"receipt self-declared {doc.get('state')}")
    else:
        failures.append("catalog receipt command-center/receipts/IMP-0298.json missing")

    payload = {
        "probe": "probe2_marker_and_transport",
        "unit_id": "IMP-0298",
        "complete_control": {
            "complete": complete.get("complete"),
            "markers": complete.get("markers"),
            "text": complete.get("text"),
        },
        "partial": {
            "complete": partial.get("complete"),
            "markers": partial.get("markers"),
            "exhausted_dimensions": partial.get("exhausted_dimensions"),
            "text": partial.get("text"),
        },
        "load_bearing": load,
        "token_count_comparison": compared,
        "receipt_present": receipt_ok,
        "failures": failures,
        "pass": not failures,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        print("FAILED:IMP-0298-probe2 " + "; ".join(failures))
        return 1
    print(
        f"marker_load_bearing=True gov_tokens={gov_n} transport_tokens={tr_n} "
        f"independent={gov_n != tr_n}"
    )
    print("SUCCESS:IMP-0298-probe2 marker-load-bearing-and-transport-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
