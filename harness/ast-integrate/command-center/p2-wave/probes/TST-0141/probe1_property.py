#!/usr/bin/env python3
"""Named probe 1: 10_000 randomized 64-taker interleavings; shrink+replay if any fail."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import N_INTERLEAVINGS, N_TAKERS, run_property_suite  # noqa: E402

ART = REPO / "command-center/receipts/TST-0141.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0141-probe1 {msg}")
    return 1


def main() -> int:
    prop = run_property_suite()
    print(json.dumps(prop, indent=2, sort_keys=True)[:6000])
    if not prop["ok"]:
        return fail(f"property suite failed: {prop.get('failures')}")
    if int(prop["n"]) < N_INTERLEAVINGS:
        return fail(f"ran {prop['n']} interleavings, need {N_INTERLEAVINGS}")
    if int(prop["n_takers"]) != N_TAKERS:
        return fail(f"n_takers={prop['n_takers']} want {N_TAKERS}")
    if int(prop["runs_completed"]) != N_INTERLEAVINGS:
        return fail(f"runs_completed={prop['runs_completed']}")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("unit_id") != "TST-0141":
            return fail(f"unit_id {doc.get('unit_id')}")
        if "SUCCESS:TST-0141" not in text:
            return fail("sentinel absent")
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"self-declared {doc.get('state')}")
        metrics = doc.get("property") or {}
        if int(metrics.get("n") or 0) < N_INTERLEAVINGS:
            return fail("receipt property.n below 10000")
    print(
        f"interleavings={prop['n']} takers={prop['n_takers']} "
        f"runs_completed={prop['runs_completed']} failures={len(prop['failures'])}"
    )
    print("SUCCESS:TST-0141-probe1 10000 randomized interleavings, zero violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
