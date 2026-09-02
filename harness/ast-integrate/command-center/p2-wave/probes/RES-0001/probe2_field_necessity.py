#!/usr/bin/env python3
"""Probe 2 (independent re-run): field-necessity + source_lineage FAIL-not-warn.

Re-runs the emitted checker on BOTH a known-good fixture and a known-broken
(source_lineage-stripped) copy. Must fire only on the broken one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import check as K  # noqa: E402
import schema_lib as S  # noqa: E402


def main() -> int:
    report = K.run_report()
    states = report["both_states"]
    print(
        json.dumps(
            {
                "known_good_schema_ok": states["known_good"]["schema_ok"],
                "known_good_consumers_ok": states["known_good"]["consumers_ok"],
                "stripped_schema_ok": states["source_lineage_stripped"]["schema_ok"],
                "stripped_consumers_ok": states["source_lineage_stripped"]["consumers_ok"],
                "stripped_failed_not_warned": states["source_lineage_stripped"]["failed_not_warned"],
                "silent_in_both_states": states["silent_in_both_states"],
                "stripped_schema_errors_head": states["source_lineage_stripped"]["schema_errors"],
            },
            sort_keys=True,
        )
    )
    if states["silent_in_both_states"]:
        print("FAILED:RES-0001-probe2 silent in both states")
        return 1
    if not states["ok"]:
        print("FAILED:RES-0001-probe2 both-states control")
        return 1
    nec = report["field_necessity"]
    weak = [r["field"] for r in nec["rows"] if not r["consumer_red"]]
    print(f"field_necessity ok={nec['ok']} fields={len(nec['rows'])} weak={weak}")
    if not nec["ok"]:
        print(json.dumps(nec, indent=2, sort_keys=True)[:4000])
        print("FAILED:RES-0001-probe2 field-necessity (a field nobody consumes, or a consumer silent)")
        return 1
    unused = report["unused_field_deletion"]
    print(f"unused_field_deletion ok={unused['ok']} deleted={unused['deleted_fields']}")
    if not unused["ok"]:
        print("FAILED:RES-0001-probe2 unused-field deletion evidence")
        return 1
    if len(S.REQUIRED_FIELDS) != 10:
        print(f"FAILED:RES-0001-probe2 required field count {len(S.REQUIRED_FIELDS)}")
        return 1
    print(
        "SUCCESS:RES-0001-probe2 field-necessity red on every delete; "
        "source_lineage-stripped FAIL not warn; checker fires only on broken fixture"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
