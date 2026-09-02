#!/usr/bin/env python3
"""Probe 1: re-run inventory + suite and match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import suite as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0037.json"
SCHEMA = REPO / "command-center/schema/conformance-report.schema.json"
SENTINEL = "SUCCESS:TST-0037"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0037-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    live = S.run(REPO)
    if not live["ok"]:
        return fail("live suite not ok")
    art_missing = list(
        (doc.get("answer") or {}).get("constructs_with_no_production_validator") or []
    )
    live_missing = list(live["answer"]["constructs_with_no_production_validator"])
    if art_missing != live_missing:
        return fail(f"missing-validator drift artifact={art_missing} live={live_missing}")

    art_table = {r["construct"]: r for r in doc.get("construct_table") or []}
    for row in live["table"]:
        art = art_table.get(row["construct"])
        if art is None:
            return fail(f"table missing {row['construct']}")
        for key in (
            "schema_rule",
            "conformance_case",
            "production_validator",
            "both_states",
        ):
            if art.get(key) != row.get(key):
                return fail(
                    f"{row['construct']}.{key} artifact={art.get(key)} live={row.get(key)}"
                )

    live_ids = {c["id"]: c for c in live["cases"]}
    rec_ids = {c["id"]: c for c in doc.get("suite_cases") or []}
    if set(live_ids) != set(rec_ids):
        return fail(f"case id mismatch extra={sorted(set(rec_ids)-set(live_ids))[:4]}")
    for cid, live_row in live_ids.items():
        rec = rec_ids[cid]
        if rec.get("contract_ids") != live_row["contract_ids"]:
            return fail(f"contract_ids drift {cid}")
        if rec.get("production_ids") != live_row["production_ids"]:
            return fail(f"production_ids drift {cid}")
        if rec.get("ok") is not True:
            return fail(f"recorded case not ok {cid}")

    tests = {t["id"]: t["result"] for t in doc.get("tests") or []}
    if any(v != "PASS" for v in tests.values()):
        return fail(f"recorded tests {tests}")
    print(
        json.dumps(
            {
                "cases": len(live["cases"]),
                "missing_validators": live_missing,
                "closed_node_types": live["inventory"]["closed_node_types"],
                "every_prod_schema_and_case": live["answer"][
                    "every_construct_has_schema_rule_and_conformance_case_in_production"
                ],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0037-probe1 live inventory and suite re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
