#!/usr/bin/env python3
"""Named probe 2: adversarial classifier controls (all-client, portable-firewall)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    UNIT,
    control_table_errors,
    load_artifact,
    load_schema,
    validate_schema,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0026-probe2 {msg}")
    return 1


def has_classifier_suspect(errs: list[str]) -> bool:
    return any("classifier-suspect" in e for e in errs)


def has_portable_error(errs: list[str]) -> bool:
    return any("specific error this unit exists to prevent" in e for e in errs)


def main() -> int:
    doc = load_artifact()
    try:
        validate_schema(doc)
    except Exception as exc:
        return fail(f"schema:{exc}")

    table = copy.deepcopy(doc["control_table"])
    live_errs = control_table_errors(table)
    if live_errs:
        return fail("live table: " + "; ".join(live_errs))

    all_client = copy.deepcopy(table)
    for row in all_client:
        row["client_vs_server_enforcement"] = "CLIENT-SIDE"
        row["portable_to_local_runtime"] = True
    client_errs = control_table_errors(all_client)
    if not has_classifier_suspect(client_errs):
        return fail("all-client table was not classified suspect")

    portable_fw = copy.deepcopy(table)
    hit = False
    for row in portable_fw:
        if row.get("control_id") == "FW-EGRESS":
            row["client_vs_server_enforcement"] = "CLIENT-SIDE"
            row["portable_to_local_runtime"] = True
            hit = True
        elif row.get("client_vs_server_enforcement") == "SERVER-ENFORCED":
            # keep at least one server row so the failure is the portable-assumption
            pass
    if not hit:
        return fail("FW-EGRESS row missing")
    # Re-label firewall as SERVER-ENFORCED but portable=true: the named error.
    for row in portable_fw:
        if row.get("control_id") == "FW-EGRESS":
            row["client_vs_server_enforcement"] = "SERVER-ENFORCED"
            row["portable_to_local_runtime"] = True
    fw_errs = control_table_errors(portable_fw)
    if not has_portable_error(fw_errs):
        return fail("portable SERVER-ENFORCED firewall not rejected")

    no_just = copy.deepcopy(table)
    no_just[0]["justification"] = "short"
    just_errs = control_table_errors(no_just)
    if not any("justification too short" in e for e in just_errs):
        return fail("missing justification not rejected")

    import jsonschema

    mutant = copy.deepcopy(doc)
    mutant["claims"][0]["source_lineage"] = mutant["claims"][0]["source_lineage"][:1]
    schema = load_schema()
    single_rail_rejected = False
    try:
        jsonschema.validate(instance=mutant, schema=schema)
    except jsonschema.ValidationError:
        single_rail_rejected = True
    if not single_rail_rejected:
        return fail("schema accepted a single-rail claim")

    garbage_rejected = 0
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.validate(instance=garbage, schema=schema)
        except jsonschema.ValidationError:
            garbage_rejected += 1
    if garbage_rejected != 3:
        return fail(f"schema garbage-rejection {garbage_rejected}/3")

    server = [
        r for r in table if r.get("client_vs_server_enforcement") == "SERVER-ENFORCED"
    ]
    out = {
        "probe": "probe2-classifier-controls",
        "unit_id": UNIT,
        "live_table_ok": True,
        "all_client_suspect": True,
        "portable_firewall_refuted": True,
        "short_justification_rejected": True,
        "single_rail_rejected": True,
        "garbage_rejected": garbage_rejected,
        "server_enforced_rows": len(server),
        "reviewer_default_on_insufficient": "REFUTED",
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:RES-0026-probe2 all-client suspect; portable firewall refuted; "
        "single-rail schema-red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
