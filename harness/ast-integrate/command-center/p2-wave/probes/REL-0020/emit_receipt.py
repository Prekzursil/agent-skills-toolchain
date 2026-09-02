#!/usr/bin/env python3
"""Emit command-center/receipts/REL-0020.json from a live drill run."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import drill as D  # noqa: E402

OUT = REPO / "command-center/receipts/REL-0020.json"
SCHEMA = REPO / "command-center/schema/lifecycle-drill-receipt.schema.json"


def dump(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


# Catalog output_schema is a generated shim whose $ref is
# https://ast-integrate.invalid/... — jsonschema follows it and raises
# RefResolutionError. G-1 is json.loads + named probes, not a remote fetch.
# This local contract still rejects empty/garbage that json.loads would accept.
LOCAL_CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "locations",
        "tests",
        "evidence",
        "controls",
        "isolation",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": "REL-0020"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:REL-0020"},
        "locations": {"type": "array", "minItems": 6},
        "tests": {"type": "array", "minItems": 4},
        "evidence": {
            "type": "object",
            "required": [
                "quoted_old_execution",
                "quoted_new_execution",
                "version_string_is_not_behaviour",
                "behavioural_old",
                "behavioural_new",
            ],
        },
    },
}


def validate_schema(doc: dict) -> None:
    import jsonschema

    jsonschema.validate(doc, LOCAL_CONTRACT)
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ]
    rejected = 0
    for g in garbage:
        try:
            jsonschema.validate(g, LOCAL_CONTRACT)
        except jsonschema.ValidationError:
            rejected += 1
    if rejected != 3:
        raise RuntimeError(f"local contract accepted garbage rejected={rejected}/3")
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        raise RuntimeError("catalog output_schema path missing on disk")


def main() -> int:
    run = D.run_all()
    if not run.get("pass"):
        print("FAILED:REL-0020 drill did not pass")
        print(json.dumps({k: run.get(k) for k in sorted(run) if k != "locations"}, default=str)[:4000])
        return 1
    doc = D.build_receipt_body(run)
    ok, why = D.receipt_honest(doc)
    if not ok:
        print(f"FAILED:REL-0020 receipt not honest: {why}")
        return 1
    validate_schema(doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dump(doc), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:REL-0020")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
