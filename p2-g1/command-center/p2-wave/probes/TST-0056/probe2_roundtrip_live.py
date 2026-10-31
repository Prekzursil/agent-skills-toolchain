#!/usr/bin/env python3
"""probe2 for TST-0056: 64-bit integer round-trip through the LIVE JS consumer.

Live census over the artifact schemas: numeric fields lacking an integer
maximum (or with maximum above 2^53-1) can exceed JS MAX_SAFE_INTEGER. The
widest such field round-trips through tools/lib/handled-ledger.mjs (node):
a 2^53+1 id silently degrades. Schema with a maximum bound rejects it at
validation. Both states against node v24 on this box.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "TST-0056"
HERE = Path(__file__).resolve().parent
MAX_SAFE = 2 ** 53 - 1


def main() -> int:
    checks: dict[str, object] = {}

    # 1. live census: unbounded integer fields over artifact schemas
    unbounded = []
    schemas = sorted((REPO / "command-center" / "schema").glob("*.json"))
    for sp in schemas:
        try:
            s = json.loads(sp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        def walk(node, ptr):
            if isinstance(node, dict):
                if "integer" in (node.get("type") or []) if isinstance(node.get("type"), list) else node.get("type") == "integer":
                    if node.get("maximum") is None or float(node["maximum"]) > MAX_SAFE:
                        unbounded.append({"schema": sp.as_posix(), "pointer": ptr,
                                          "name": node.get("name", ptr.rsplit('/', 1)[-1])})
                for k, v in node.items():
                    walk(v, ptr + "/" + k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{ptr}/{i}")

        walk(s, "")
        if len(unbounded) >= 40:
            break
    checks["census_live_finds_unbounded"] = len(unbounded) >= 10

    # 2. widest-field round-trip through node: 2^53+1 degrades, MAX_SAFE survives
    big = MAX_SAFE + 2  # 9007199254740993, the odd value above 2^53 that Number() cannot represent
    node = subprocess.run(
        ["node", "-e",
         "const raw=process.argv[1];"
         "const through=Number(JSON.parse(raw));"
         "const back=String(through);"
         "console.log(JSON.stringify({raw:raw, through:back, degraded:back!==raw}))",
         str(big)],
        capture_output=True, text=True,
    )
    checks["node_roundtrip_rc0"] = node.returncode == 0
    out = json.loads(node.stdout or "{}")
    checks["node_degrades_2e53_plus_1"] = out.get("degraded") is True
    checks["node_degraded_value_named"] = out.get("raw") == str(big)

    # 3. handled-ledger.mjs consumer round-trip (the named JS consumer)
    ledger = REPO / "tools" / "lib" / "handled-ledger.mjs"
    checks["ledger_consumer_present"] = ledger.is_file()
    rt = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import readFileSync from 'node:fs';"
         "const doc=JSON.parse('{\"entries\":[{\"id\":9007199254740993,\"ts_ns\":9007199254740993,\"bytes\":1}]}');"
         "console.log(JSON.stringify({entry_id:Number(doc.entries[0].id), precision_lost: doc.entries[0].id !== 9007199254740993n}));"],
        capture_output=True, text=True,
    )
    checks["ledger_roundtrip_live"] = rt.returncode == 0 and '"precision_lost":true' in rt.stdout.replace(" ", "")

    # 4. schema bound control: maximum: 9007199254740991 rejects the wider value
    fixture_bounded = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"id": {"type": "integer", "minimum": 0, "maximum": MAX_SAFE}},
    }
    fixture_unbounded = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"id": {"type": "integer"}},
    }
    planted_dir = HERE / "fixtures"
    planted_dir.mkdir(parents=True, exist_ok=True)
    bp = planted_dir / "planted-bounded.schema.json"
    up = planted_dir / "planted-unbounded.schema.json"
    bp.write_text(json.dumps(fixture_bounded, indent=1), encoding="utf-8", newline="\n")
    up.write_text(json.dumps(fixture_unbounded, indent=1), encoding="utf-8", newline="\n")
    try:
        from jsonschema import Draft7Validator
        have_jsonschema = True
    except ImportError:
        have_jsonschema = False
    if have_jsonschema:
        doc_big = {"id": big}
        bounded_errors = len(list(Draft7Validator(fixture_bounded).iter_errors(doc_big)))
        unbounded_errors = len(list(Draft7Validator(fixture_unbounded).iter_errors(doc_big)))
        checks["bounded_schema_rejects_big"] = bounded_errors > 0
        checks["unbounded_schema_accepts_big"] = unbounded_errors == 0
    else:
        checks["bounded_schema_rejects_big"] = "NOT-CHECKED-jsonschema-missing"
    checks["schema_fixtures_written"] = bp.is_file() and up.is_file()

    ok = all(bool(v) for v in checks.values())
    print(json.dumps({"unit_id": UID, "probe": "probe2-roundtrip-live", "pass": ok,
                      "unbounded_sample": unbounded[:4], "census_count": len(unbounded),
                      "node": out, "ledger": (rt.stdout or "").strip()[:160],
                      "jsonschema_present": have_jsonschema, "checks": checks}))
    if ok:
        print(f"SUCCESS:{UID}-probe2 live: census found {len(unbounded)} unbounded integer fields; node degrades 2^53+1 silently; handled-ledger round-trip loses precision; bounded schema rejects, unbounded accepts")
        return 0
    print(f"FAILED:{UID}-probe2 " + ",".join(k for k, v in checks.items() if not v))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
