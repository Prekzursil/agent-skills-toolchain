#!/usr/bin/env python3
"""Probe 2: independently re-validate CLAIM-REGISTRY with per-field missing counts.

Refuses vacuous YES on an absent or empty registry. Checks the live
receipt's census against a fresh recompute. Domain payload may live under
report/extensions after the receipt-core envelope landed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contract import (  # noqa: E402
    REQUIRED_FIELDS,
    census_registry,
    payload,
)

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center/receipts/TST-0040.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def _missing_count(block: object, field: str) -> int:
    if isinstance(block, dict):
        row = block.get(field)
        if isinstance(row, dict) and "missing" in row:
            return int(row.get("missing") or 0)
        if field in block and isinstance(block[field], int):
            return int(block[field])
    return 0


def main() -> int:
    live = census_registry(REPO)
    print(json.dumps(
        {
            "present": live["present"],
            "parseable": live["parseable"],
            "record_count": live["record_count"],
            "schema_valid_count": live["schema_valid_count"],
            "schema_invalid_count": live["schema_invalid_count"],
            "every_record_complete": live["every_record_complete"],
            "vacuous_universal_refused": live["vacuous_universal_refused"],
            "answer": live["answer"],
            "reason": live["reason"],
            "per_field_missing": {
                field: live["per_field_missing"][field]["missing"]
                for field in REQUIRED_FIELDS
            },
        },
        sort_keys=True,
    ))

    if live["answer"] == "YES" and (
        not live["present"] or live["record_count"] == 0
    ):
        print("FAILED:TST-0040-probe2 vacuous YES on empty/absent registry")
        return 1
    if not live["present"] and not live["vacuous_universal_refused"]:
        print("FAILED:TST-0040-probe2 absent registry was not flagged")
        return 1
    if live["every_record_complete"] and live["record_count"] == 0:
        print("FAILED:TST-0040-probe2 zero records marked complete")
        return 1

    if not ART.is_file():
        print("FAILED:TST-0040-probe2 live artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        print(f"FAILED:TST-0040-probe2 self-declared {state}")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0040" not in text:
        print("FAILED:TST-0040-probe2 sentinel absent")
        return 1

    body = payload(doc)
    census = doc.get("registry_census") or body.get("registry_census") or {}
    if "record_count" not in census or int(census["record_count"]) != int(
        live["record_count"]
    ):
        print(
            "FAILED:TST-0040-probe2 record_count drift "
            f"artifact={census.get('record_count')} live={live['record_count']}"
        )
        return 1
    if bool(census.get("present")) != bool(live["present"]):
        print("FAILED:TST-0040-probe2 registry present-bit drift")
        return 1
    if str(census.get("answer") or "") != str(live["answer"]):
        print(
            "FAILED:TST-0040-probe2 answer drift "
            f"artifact={census.get('answer')} live={live['answer']}"
        )
        return 1
    art_fields = census.get("per_field_missing") or {}
    for field in REQUIRED_FIELDS:
        art_missing = _missing_count(art_fields, field)
        live_missing = int(live["per_field_missing"][field]["missing"])
        if art_missing != live_missing:
            print(
                f"FAILED:TST-0040-probe2 missing-count drift {field} "
                f"artifact={art_missing} live={live_missing}"
            )
            return 1
    if census.get("every_record_complete") is True and live["record_count"] == 0:
        print("FAILED:TST-0040-probe2 artifact overclaimed empty completeness")
        return 1

    claims = doc.get("claims") or body.get("claims") or []
    universal = [
        row
        for row in claims
        if isinstance(row, dict)
        and "every claim record" in str(row.get("claim") or "").lower()
    ]
    if not universal:
        print("FAILED:TST-0040-probe2 receipt omitted the universal-record claim")
        return 1
    if live["answer"] == "NO":
        bad = [
            row
            for row in universal
            if str(row.get("verdict") or "") == "CONFIRMED"
        ]
        if bad:
            print(
                "FAILED:TST-0040-probe2 overclaim: CONFIRMED every-record "
                "while census is NO"
            )
            return 1
        if not any(str(row.get("verdict") or "") == "REFUTED" for row in universal):
            print("FAILED:TST-0040-probe2 universal claim not REFUTED")
            return 1

    settling = [
        row
        for row in claims
        if isinstance(row, dict)
        and "settling" in str(row.get("claim") or "").lower()
    ]
    if not any(str(row.get("verdict") or "") == "CONFIRMED" for row in settling):
        print("FAILED:TST-0040-probe2 settling-experiment rejection not CONFIRMED")
        return 1

    print(
        f"artifact_answer={census.get('answer')} live_answer={live['answer']} "
        f"records={live['record_count']} present={live['present']}"
    )
    print("SUCCESS:TST-0040-probe2 registry census and overclaim check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
