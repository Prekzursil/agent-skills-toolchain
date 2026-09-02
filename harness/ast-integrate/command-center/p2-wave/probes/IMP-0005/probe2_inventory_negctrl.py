#!/usr/bin/env python3
"""Named probe 2: inventory added/removed/grown + negative control + tautology review.

Independent of probe 1's zip/tar dual census. Re-derives the budget from a
measurement of the previous archive and refuses a ceiling copied from current.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN / "tests"))
sys.path.insert(0, str(PLUGIN))

import fixtures as fx  # noqa: E402
import jsonschema  # noqa: E402
from inventory_diff import diff_archives  # noqa: E402
from size_budget import (  # noqa: E402
    Budget,
    budget_copied_from_current,
    check_archive,
    derive_budget,
    formula_max_bytes,
    formula_max_file_count,
)
from test_inventory_diff import test_added_removed_grown_classification  # noqa: E402
from test_size_budget import (  # noqa: E402
    test_negative_control_raise_ceiling_goes_red,
    test_over_budget_fails,
)

ART = REPO / "command-center/receipts/IMP-0005.json"
SCHEMA = PLUGIN / "schema" / "payload-inventory.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0005-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0005" not in text:
        print("FAILED:IMP-0005-probe2 sentinel absent")
        return 1

    try:
        test_over_budget_fails()
        test_added_removed_grown_classification()
        test_negative_control_raise_ceiling_goes_red()
    except AssertionError as exc:
        print(f"FAILED:IMP-0005-probe2 catalog test {exc}")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="imp0005-p2-") as td:
        tmp = Path(td)
        prev = fx.inventory_previous_zip(tmp / "inv-prev.zip")
        curr = fx.inventory_current_zip(tmp / "inv-curr.zip")
        inv = diff_archives(prev, curr)
        jsonschema.validate(inv, schema)
        added = {r["path"] for r in inv["added"]}
        removed = {r["path"] for r in inv["removed"]}
        grown = {r["path"] for r in inv["grown"]}
        if added != {"new/added.txt"} or removed != {"drop/gone.txt"} or grown != {"keep/grow.txt"}:
            print("FAILED:IMP-0005-probe2 classification", added, removed, grown)
            return 1

        previous = fx.previous_zip(tmp / "prev.zip")
        current = fx.current_ok_zip(tmp / "curr.zip")
        bloated = fx.over_budget_zip(tmp / "over.zip")
        measured_bytes = previous.stat().st_size
        measured_count = 4  # PREVIOUS_FILES has four members including the plant
        recomputed = derive_budget(previous)
        if recomputed.derivation["measured_archive_bytes"] != measured_bytes:
            print("FAILED:IMP-0005-probe2 reviewer measurement mismatch")
            return 1
        if recomputed.max_bytes != formula_max_bytes(measured_bytes):
            print("FAILED:IMP-0005-probe2 max_bytes not from formula")
            return 1
        if recomputed.max_file_count != formula_max_file_count(
            recomputed.derivation["measured_file_count"]
        ):
            print("FAILED:IMP-0005-probe2 max_file_count not from formula")
            return 1
        if recomputed.derivation["measured_file_count"] != measured_count:
            print(
                "FAILED:IMP-0005-probe2 previous file_count "
                f"{recomputed.derivation['measured_file_count']} != {measured_count}"
            )
            return 1
        if budget_copied_from_current(recomputed, current):
            print("FAILED:IMP-0005-probe2 budget copied from current (tautological)")
            return 1
        if not check_archive(current, recomputed)["ok"]:
            print("FAILED:IMP-0005-probe2 current should be in-budget")
            return 1
        if check_archive(bloated, recomputed)["ok"]:
            print("FAILED:IMP-0005-probe2 bloated should be over-budget")
            return 1

        raised = Budget(
            max_bytes=bloated.stat().st_size + 1,
            max_file_count=10_000,
            derivation={"mutated": "ceiling-raised-above-fixture"},
        )
        raised_verdict = check_archive(bloated, raised)
        if not raised_verdict["ok"]:
            print("FAILED:IMP-0005-probe2 raised ceiling still over-budget")
            return 1

    summary = {
        "probe": "probe2-inventory-negctrl",
        "unit_id": "IMP-0005",
        "pass": True,
        "added": sorted(added),
        "removed": sorted(removed),
        "grown": sorted(grown),
        "schema_valid": True,
        "budget_from_measurement": True,
        "not_copied_from_current": True,
        "negative_control_raise_ceiling_went_red": True,
        "over_budget_test_pass": True,
        "reviewer": "IMP-0005-probe2-measurement-reviewer",
        "verdict": "PASS",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"added={sorted(added)} removed={sorted(removed)} grown={sorted(grown)} "
        "tautology_refused=True raise_ceiling_red=True"
    )
    print("SUCCESS:IMP-0005-probe2 inventory classification and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
