#!/usr/bin/env python3
"""Decisive test: do the unit RECEIPTS validate against the catalog
output_schema (class profiles)? If yes, output_schema binds receipts."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}


def class_schema(schema_ref: str):
    doc = json.loads((REPO / schema_ref).read_text(encoding="utf-8"))
    ref = doc.get("$ref") or ""
    if "#/$defs/" in ref:
        cls = ref.rsplit("/$defs/", 1)[1]
        prof = json.loads(
            (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
        d = prof.get("$defs", {}).get(cls)
        if d is None:
            return None, cls
        d = dict(d)
        d["$defs"] = prof.get("$defs", {})
        d["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        return d, cls
    return doc, "(direct)"


for uid in MY:
    e = byid[uid]
    rec = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
    schema, cls = class_schema(e["output_schema"])
    if schema is None:
        print(f"{uid} [{cls}] NO PROFILE")
        continue
    errs = list(Draft202012Validator(schema).iter_errors(rec))
    print(f"{uid} [{cls:16}] receipt: {'OK' if not errs else f'{len(errs)} ERR first=' + errs[0].message[:80]}")
