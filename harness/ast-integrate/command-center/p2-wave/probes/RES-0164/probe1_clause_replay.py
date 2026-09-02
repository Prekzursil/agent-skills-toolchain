#!/usr/bin/env python3
"""Probe 1: catalog envelope + live schema validation for RES-0164."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
sys.path.insert(0, str(REPO))
import p2_jsonschema_hook  # noqa: E402

UID = "RES-0164"
REL = "command-center/research/prior-art/RES-0164-event-log-schema-prior-art.json"
SENT = 'SUCCESS:RES-0164'
SCHEMA_REL = 'command-center/schema/ecosystem-teardown.schema.json'


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def main() -> int:
    art = REPO / REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact-absent")
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{exc}")
    if SENT and SENT not in text:
        return fail("sentinel-absent")
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        if doc.get("unit_id") not in (UID, None, ""):
            if doc.get("unit_id") != UID and "$schema" not in doc:
                return fail(f"unit-id-mismatch:{doc.get('unit_id')}")
    schema_path = REPO / SCHEMA_REL if SCHEMA_REL else None
    if schema_path is not None and schema_path.is_file():
        import jsonschema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Validator = jsonschema.Draft202012Validator
        try:
            Validator(schema).validate(doc)
        except jsonschema.ValidationError as exc:
            return fail(f"schema-invalid:{exc.message}")
        garbage_errors = list(Validator(schema).iter_errors({}))
        if not garbage_errors:
            return fail("schema-garbage-silent")
        print(f"schema_ok=True schema_rejects_garbage=True n_garbage={len(garbage_errors)}")
    print(f"artifact={REL} bytes={art.stat().st_size} sentinel_present={bool(SENT and SENT in text)}")
    print(f"SUCCESS:{UID}-probe1 envelope+schema both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
