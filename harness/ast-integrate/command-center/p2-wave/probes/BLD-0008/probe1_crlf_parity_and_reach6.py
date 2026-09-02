#!/usr/bin/env python3
"""Probe 1: CRLF==LF (or named reject) for every parser; REACH-6; BOM JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import run_matrix  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0008.json"
SCHEMA = REPO / "command-center/schema/coverage-matrix.schema.json"
SENTINEL = "SUCCESS:BLD-0008"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0008-probe1 {msg}")
    return 1


def main() -> int:
    live = run_matrix()
    parity = live["crlf_parity"]
    print("crlf_parity", json.dumps({"pass": parity["pass"], "rows": parity["rows"]}, sort_keys=True))
    if not parity["pass"]:
        return fail("CRLF/LF divergence without named rejection")
    bom = live["bom_json"]
    print("bom_json", json.dumps({k: bom[k] for k in ("outcome", "error", "pass", "keys")}, sort_keys=True))
    if not bom["pass"]:
        return fail("BOM-prefixed JSON silently produced a BOM key")
    reach = live["reach6"]
    print(
        "reach6",
        json.dumps(
            {
                "lf_ne_crlf": reach["lf_ne_crlf"],
                "blob_ne_crlf": reach["blob_ne_crlf"],
                "snapshot_present": reach["snapshot_present"],
                "pass": reach["pass"],
            },
            sort_keys=True,
        ),
    )
    if not reach["pass"]:
        return fail("REACH-6 LF vs CRLF digest split did not reproduce")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    raw = ART.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema

        jsonschema.validate(doc, schema)
    except ImportError:
        for key in schema.get("required") or []:
            if key not in doc:
                return fail(f"schema required {key}")
    if not doc.get("cells") or len(doc["cells"]) < 8:
        return fail("matrix too small")
    print("SUCCESS:BLD-0008-probe1 crlf-parity reach6 bom-json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
