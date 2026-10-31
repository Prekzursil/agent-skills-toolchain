#!/usr/bin/env both
"""Control experiment: strict disk-only class-profile validation of artifacts
belonging to units ALREADY closed SUCCESS by prior reviewer waves, vs mine."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
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


# previously-closed units with the same schema classes as my 12
closed = []
for uid, e in byid.items():
    rp = REPO / f"command-center/receipts/{uid}.json"
    if not rp.exists():
        continue
    try:
        rec = json.loads(rp.read_text(encoding="utf-8"))
    except Exception:
        continue
    if rec.get("state") != "SUCCESS":
        continue
    sc = e.get("output_schema") or ""
    if any(k in sc for k in ("audit-drift", "audit-finding", "audit-inventory", "audit-graph", "claim-record")):
        p = REPO / e["output_path"]
        if p.exists():
            closed.append(uid)

print(f"previously-closed SUCCESS units sharing my schema classes: {len(closed)}")
sample = closed[:12]
print("sample:", sample)
for uid in sample:
    e = byid[uid]
    art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
    schema, cls = class_schema(e["output_schema"])
    if schema is None:
        print(f"  {uid} [{cls}] NO PROFILE")
        continue
    errs = list(Draft202012Validator(schema).iter_errors(art))
    print(f"  {uid} [{cls:16}] {'OK' if not errs else f'{len(errs)} ERR'}"
          + (f" first: {errs[0].message[:100]}" if errs else ""))
