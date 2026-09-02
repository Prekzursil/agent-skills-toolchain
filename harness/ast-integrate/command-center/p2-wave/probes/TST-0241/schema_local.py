"""Compile catalog $defs/benchmark_result from disk (jsonschema 4.10).

The command-center/schema shims $ref https://ast-integrate.invalid/... which
is not a network host. A bare Draft7Validator follows that URL, raises
RefResolutionError, and never constrains the receipt. This module copies
platform/schema/receipt.schema.json $defs so every $ref stays on #/$defs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PHYSICAL = REPO / "platform" / "schema" / "receipt.schema.json"
OUT = REPO / "command-center" / "receipts" / "TST-0241.json"
DECLARED = "command-center/schema/receipt.schema.json#/$defs/benchmark_result"


def compiled_schema() -> dict[str, Any]:
    receipt = json.loads(PHYSICAL.read_text(encoding="utf-8"))
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "benchmark_result" not in defs:
        raise SystemExit("FAILED:TST-0241 physical receipt.schema.json missing $defs.benchmark_result")
    return {
        "$id": (
            "https://ast-integrate.invalid/command-center/p2-wave/"
            "probes/TST-0241/benchmark_result.local.json"
        ),
        "allOf": [{"$ref": "#/$defs/benchmark_result"}],
        "$defs": defs,
    }


def validator() -> Draft7Validator:
    return Draft7Validator(compiled_schema())


def errors(doc: Any) -> list[str]:
    out: list[str] = []
    for err in validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        print("FAILED:TST-0241-schema receipt missing")
        return 1
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    errs = errors(doc)
    if errs:
        print("FAILED:TST-0241-schema " + errs[0])
        for item in errs[:12]:
            print("  " + item)
        return 1
    print(json.dumps({"probe": "schema-local", "declared": DECLARED, "pass": True}, sort_keys=True))
    print("SUCCESS:TST-0241-schema local $defs/benchmark_result accepts the receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
