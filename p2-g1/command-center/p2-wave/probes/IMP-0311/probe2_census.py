#!/usr/bin/env python3
"""Probe 2: downstream-consumer census (independent of probe 1's summary).

Starts from the planted consumers and the census detector, not from an
author narrative. Catalog negative control: a consumer that maps
NO-DECISION to FAIL must be caught. A preserving consumer must stay silent.
Production tools/council/outcomes must not itself coerce.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.census import (  # noqa: E402
    assert_coercer_caught,
    census,
    classify_file,
)
from council.outcomes.kinds import KIND_NO_DECISION  # noqa: E402

PROD = REPO / "tools" / "council" / "outcomes"
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0311-probe2 {msg}")
    return 1


def main() -> int:
    coercer = classify_file(FIX / "coercing_consumer.py")
    binary = classify_file(FIX / "binary_only_consumer.py")
    keeper = classify_file(FIX / "preserving_consumer.py")
    print(
        f"coercer classification={coercer['classification']} "
        f"hits={coercer['coercions']}"
    )
    print(
        f"binary-only classification={binary['classification']} "
        f"hits={binary['coercions']}"
    )
    print(
        f"preserver classification={keeper['classification']} "
        f"hits={keeper['coercions']}"
    )

    if coercer["classification"] != "COERCES":
        return fail("planted NO-DECISION->FAIL consumer not caught")
    if not any(
        c.get("kind") == KIND_NO_DECISION for c in coercer.get("coercions") or []
    ):
        return fail("planted coercer caught but not attributed to NO-DECISION")
    if binary["classification"] != "COERCES":
        return fail("binary-only consumer not caught")
    if keeper["classification"] != "PRESERVES":
        return fail(f"preserving consumer false-positive: {keeper}")

    planted = census([FIX / "coercing_consumer.py", FIX / "binary_only_consumer.py"])
    assert_coercer_caught(planted, "coercing_consumer.py", KIND_NO_DECISION)
    if planted["coercers"] != 2:
        return fail(f"expected 2 planted coercers, got {planted['coercers']}")

    good = census([FIX / "preserving_consumer.py"])
    if good["coercers"] != 0:
        return fail(f"preserver census not silent: {good}")
    print("negative-control both-states: coercer-caught=True preserver-silent=True")

    prod = census([PROD])
    prod_coercers = [
        r
        for r in prod["rows"]
        if r.get("classification") == "COERCES"
        and Path(r["path"]).name not in {"census.py"}
    ]
    print(
        json.dumps(
            {
                "production_scanned": prod["scanned"],
                "production_coercers": [r["path"] for r in prod_coercers],
                "production_preservers": prod["preservers"],
            },
            sort_keys=True,
        )
    )
    if prod_coercers:
        return fail(f"production coercers {prod_coercers}")

    # How each production reader handles each kind: no binary remap.
    for row in prod["rows"]:
        rel = str(row.get("path", "")).replace("\\", "/")
        print(
            f"census {rel} classification={row.get('classification')} "
            f"no_decision_ok={row.get('handles_no_decision')} "
            f"conditional_ok={row.get('handles_conditional')} "
            f"proof_ok={row.get('handles_proof')}"
        )

    print(
        json.dumps(
            {
                "probe": "probe2-consumer-census",
                "unit_id": "IMP-0311",
                "planted_coercers_caught": 2,
                "preserver_silent": True,
                "production_coercers": 0,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0311-probe2 census catches NO-DECISION->FAIL coercion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
