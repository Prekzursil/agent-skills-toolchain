#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0058.json from a live scale-model run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import model as M  # noqa: E402

OUT = REPO / "command-center/receipts/BLD-0058.json"
SCHEMA = REPO / "command-center/schema/scale-model.schema.json"
RECEIPT_SCHEMA = REPO / "command-center/schema/receipt.schema.json"


def main() -> int:
    import jsonschema

    doc = M.build()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    receipt_schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(receipt_schema).validate(doc)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if jsonschema.Draft7Validator(schema).is_valid(garbage):
        print("FAILED:BLD-0058 emit schema vacuous")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:BLD-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
