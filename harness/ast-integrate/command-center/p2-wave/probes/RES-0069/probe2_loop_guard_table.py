#!/usr/bin/env python3
"""Probe 2: per-engine loop-guard table + optional-guard control.

Every row must classify the infinite-loop guard as MANDATORY or OPTIONAL.
Control: at least one OPTIONAL row where an infinite loop is expressible.
Mutants that erase OPTIONAL rows or drop the table must go red.
The cross-engine overclaim must remain REFUTED.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence as E  # noqa: E402


def main() -> int:
    if not E.ART.is_file():
        print("FAILED:RES-0069-probe2 artifact missing")
        return 1
    doc = json.loads(E.ART.read_text(encoding="utf-8"))
    ok, why = E.check_loop_guard_table(doc)
    print(f"table_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0069-probe2 loop-guard table check failed")
        return 1

    no_table = copy.deepcopy(doc)
    no_table["loop_guard_table"] = []
    tok, twhy = E.check_loop_guard_table(no_table)
    print(f"empty_table_mutant_ok={tok} {twhy}")
    if tok:
        print("FAILED:RES-0069-probe2 empty table was accepted")
        return 1

    all_mandatory = copy.deepcopy(doc)
    for row in all_mandatory["loop_guard_table"]:
        row["guard_class"] = "MANDATORY"
        row["infinite_loop_expressible"] = False
    aok, awhy = E.check_loop_guard_table(all_mandatory)
    print(f"all_mandatory_mutant_ok={aok} {awhy}")
    if aok:
        print("FAILED:RES-0069-probe2 all-mandatory mutant was accepted")
        return 1

    unrefuted = copy.deepcopy(doc)
    for claim in unrefuted["claims"]:
        if claim.get("id") == "C-ALL-ENGINES-MANDATORY-GUARDS":
            claim["verdict"] = "CONFIRMED"
            break
    uok, uwhy = E.check_loop_guard_table(unrefuted)
    print(f"unrefuted_overclaim_ok={uok} {uwhy}")
    if uok:
        print("FAILED:RES-0069-probe2 unrefuted overclaim was accepted")
        return 1

    optional = [
        r["engine"]
        for r in doc["loop_guard_table"]
        if r.get("guard_class") == "OPTIONAL"
    ]
    print(f"control_optional_engines={optional}")
    print("SUCCESS:RES-0069-probe2 loop-guard table and optional-guard control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
