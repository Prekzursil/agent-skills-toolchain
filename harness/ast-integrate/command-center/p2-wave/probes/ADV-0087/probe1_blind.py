#!/usr/bin/env python3
"""Probe 1: catalog envelope + live schema validation for ADV-0087."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
sys.path.insert(0, str(REPO))
import p2_jsonschema_hook  # noqa: E402

UID = "ADV-0087"
REL = "command-center/adversarial/ADV-0087-judge-same-vendor-bias.json"
SENT = "SUCCESS:ADV-0087 emitted ONLY when the artifact at output_path exists, is non-empty, parses against output_schema, records BOTH named probes verbatim with their raw output, carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and records the result of every listed control/negative test. Any missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0087 <reason>."
SCHEMA_REL = 'command-center/schema/benchmark-integrity.schema.json'


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
