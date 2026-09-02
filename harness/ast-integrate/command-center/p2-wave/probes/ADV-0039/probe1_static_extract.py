#!/usr/bin/env python3
"""Probe 1: static extraction of outbound constructor fields vs allowlist.

Mechanically different from probe 2: AST of emit_records / RECORDED_FIELDS,
no HTTP, no serializer.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from extract import (  # noqa: E402
    FORBIDDEN_CONTROL,
    PERMITTED_CONTROL,
    UNIT,
    static_extract,
)

ART = REPO / "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"
SCHEMA = REPO / "command-center/schema/privacy-dataflow.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": UNIT, "state": "SUCCESS"},
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    live = static_extract()
    if not live["permitted_control_in_constructor"]:
        return fail("permitted control absent from constructor", live)
    if live["forbidden_control_in_constructor"]:
        return fail("forbidden control present in production constructor", live)
    if PERMITTED_CONTROL not in live["recorded_fields"]:
        return fail("allowlist missing permitted control")
    if FORBIDDEN_CONTROL not in live["sensitive_fields"]:
        return fail("sensitive set missing forbidden control")
    extra = live["extra_vs_allowlist"]
    if "join_key_name" not in extra or "join_key_scope" not in extra:
        return fail("expected extra constructor keys vs RECORDED_FIELDS", extra)
    if live["http_clients_in_router"]:
        return fail("router package unexpectedly contains HTTP client", live["http_clients_in_router"])

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if f"SUCCESS:{UNIT}" not in blob:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)
    errors = list(validator.iter_errors(doc))
    if errors:
        return fail("artifact fails schema", errors[0].message)

    ctor = doc.get("constructor_fields") or {}
    if sorted(ctor.get("production_keys") or []) != live["constructor_production_keys"]:
        return fail("constructor keys mismatch", {"art": ctor, "live": live})
    if sorted(ctor.get("extra_vs_allowlist") or []) != live["extra_vs_allowlist"]:
        return fail("extra_vs_allowlist mismatch")
    allow = doc.get("allowlist") or {}
    if sorted(allow.get("recorded_fields") or []) != sorted(live["recorded_fields"]):
        return fail("allowlist mismatch")
    targets = {t["id"]: t["verdict"] for t in (doc.get("targets") or []) if isinstance(t, dict)}
    if targets.get("constructor-keys-extracted") != "CONFIRMED":
        return fail("constructor-keys-extracted verdict", targets)
    if targets.get("extra-constructor-fields-vs-allowlist") != "CONFIRMED":
        return fail("extra-constructor-fields-vs-allowlist verdict", targets)

    cmds = [p.get("command") for p in (doc.get("named_probes") or []) if isinstance(p, dict)]
    if not any("probe1_static_extract.py" in str(c) for c in cmds):
        return fail("named probe1 command absent", cmds)

    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0039-probe1 static constructor extract vs allowlist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
