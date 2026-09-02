#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import fixtures as fx  # noqa: E402
from inventory_diff import diff_archives  # noqa: E402

SCHEMA = json.loads(
    (PLUGIN / "schema" / "payload-inventory.schema.json").read_text(encoding="utf-8")
)


def test_added_removed_grown_classification() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prev = fx.inventory_previous_zip(tmp / "inv-prev.zip")
        curr = fx.inventory_current_zip(tmp / "inv-curr.zip")
        inv = diff_archives(prev, curr)
        jsonschema.validate(inv, SCHEMA)
        added = {r["path"] for r in inv["added"]}
        removed = {r["path"] for r in inv["removed"]}
        grown = {r["path"] for r in inv["grown"]}
        assert added == {"new/added.txt"}, added
        assert removed == {"drop/gone.txt"}, removed
        assert grown == {"keep/grow.txt"}, grown


def test_inventory_schema_rejects_missing_grown() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prev = fx.inventory_previous_zip(tmp / "inv-prev.zip")
        curr = fx.inventory_current_zip(tmp / "inv-curr.zip")
        inv = diff_archives(prev, curr)
        bad = copy.deepcopy(inv)
        del bad["grown"]
        try:
            jsonschema.validate(bad, SCHEMA)
        except jsonschema.ValidationError:
            return
        raise AssertionError("schema accepted inventory missing grown")


if __name__ == "__main__":
    test_added_removed_grown_classification()
    test_inventory_schema_rejects_missing_grown()
    print("OK")
