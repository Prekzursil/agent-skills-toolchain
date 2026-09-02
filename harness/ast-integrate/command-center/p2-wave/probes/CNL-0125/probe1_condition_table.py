#!/usr/bin/env python3
"""Probe 1: independent recount of the 12-row table from the artifact.

Does not trust the author's answer prose. Re-tabulates condition_table,
checks verbatim spec text, and requires discharge or explicit
NOT-APPLICABLE on every row. A count disagreement blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from conditions import CONDITIONS  # noqa: E402
from table import ROWS, counts  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0125-council-result-against-the-shared-12-condition-completion-.md"
)
SCHEMA = HERE / "note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0125-probe1 {msg}")
    return 1


def main() -> int:
    live = counts()
    if live["n"] != 12:
        return fail(f"module table n={live['n']}")
    if live["cannot_satisfy"] != [9, 12]:
        return fail(f"module cannot={live['cannot_satisfy']} want [9, 12]")
    if live["n_can"] != 10:
        return fail(f"module n_can={live['n_can']}")

    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0125":
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:CNL-0125" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    table = doc.get("condition_table") or []
    if len(table) != 12:
        return fail(f"artifact table length {len(table)}")

    can, cannot, na = [], [], []
    for i, row in enumerate(table, 1):
        if int(row.get("n") or 0) != i:
            return fail(f"artifact n drift at {i}")
        want = CONDITIONS[i - 1][1]
        got = row.get("spec_verbatim")
        if got != want:
            return fail(f"C{i} verbatim mismatch {got!r}")
        app = str(row.get("applicability") or "")
        if app == "NOT-APPLICABLE":
            na.append(i)
            if not str(row.get("discharge") or "").strip():
                return fail(f"C{i} N/A without named reason")
        elif row.get("can_satisfy") is True:
            can.append(i)
        elif row.get("can_satisfy") is False:
            cannot.append(i)
        else:
            return fail(f"C{i} missing can_satisfy")
        if not str(row.get("discharge") or "").strip():
            return fail(f"C{i} missing discharge")

    print(
        json.dumps(
            {
                "recount_can": can,
                "recount_cannot": cannot,
                "recount_na": na,
                "n_can": len(can),
                "n_cannot": len(cannot),
                "module_can": live["can_satisfy"],
                "module_cannot": live["cannot_satisfy"],
            },
            sort_keys=True,
        )
    )
    if cannot != [9, 12]:
        return fail(f"recount cannot={cannot} want [9,12] (question-named)")
    if can != live["can_satisfy"] or cannot != live["cannot_satisfy"]:
        return fail("artifact recount disagrees with module table")
    if na:
        return fail(f"N/A rows {na}; this unit forbids N/A-as-pass for C9/C12")

    enum = doc.get("enumeration") or {}
    if enum.get("expected_n") != 12 or enum.get("measured_n") != 12:
        return fail(f"enumeration {enum}")
    if enum.get("agreement") is not True:
        return fail("enumeration.agreement is not true")

    if SCHEMA.is_file():
        import jsonschema

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
        if errs:
            print(errs[0].message)
            return fail("schema invalid")
        garbage = {"totally": "unrelated"}
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            return fail("schema accepted garbage (vacuous)")

    print("SUCCESS:CNL-0125-probe1 independent 12-row recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
