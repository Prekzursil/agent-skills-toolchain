#!/usr/bin/env python3
"""Probe 2: bypass honesty — both-states control on the attack-class table."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract as C  # noqa: E402
import surface as S  # noqa: E402


def schema_errors(doc: dict) -> list[str]:
    schema = json.loads(C.SCHEMA.read_text(encoding="utf-8"))
    return [
        e.message
        for e in jsonschema.Draft7Validator(schema).iter_errors(doc)
    ]


def main() -> int:
    try:
        doc = C.load_artifact()
        C.validate_schema(doc)
        stats = C.check_table(doc)
        live = S.run_surface()
        if live["surviving_mitigation_count"] < 1:
            print("FAILED:RES-0039-probe2 live surface survived none")
            return 1
        stripped = C.mutant_strip_outcomes(doc)
        strip_errs = schema_errors(stripped)
        try:
            C.check_table(stripped)
            table_caught_strip = False
        except RuntimeError:
            table_caught_strip = True
        all_bad = C.mutant_all_bypassed(doc)
        try:
            C.check_table(all_bad)
            table_caught_all_bypass = False
        except RuntimeError:
            table_caught_all_bypass = True
        if not strip_errs and not table_caught_strip:
            print("FAILED:RES-0039-probe2 strip-outcomes mutant silent")
            return 1
        if not table_caught_all_bypass:
            print("FAILED:RES-0039-probe2 all-BYPASSED mutant silent")
            return 1
    except Exception as exc:
        print(f"FAILED:RES-0039-probe2 {type(exc).__name__}: {exc}")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe2-bypass-control",
                "unit_id": "RES-0039",
                "survived": stats["survived"],
                "bypassed": stats["bypassed"],
                "strip_outcomes_schema_errors": len(strip_errs),
                "strip_outcomes_caught": table_caught_strip or bool(strip_errs),
                "all_bypassed_caught": table_caught_all_bypass,
                "live_survived": live["surviving_mitigation_count"],
            },
            sort_keys=True,
        )
    )
    print(
        f"strip_caught={table_caught_strip or bool(strip_errs)} "
        f"all_bypassed_caught={table_caught_all_bypass} "
        f"survived={stats['survived']}"
    )
    print(
        "SUCCESS:RES-0039-probe2 at least one mitigation survived; "
        "strip-outcomes and all-BYPASSED mutants fire"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
