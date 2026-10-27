#!/usr/bin/env python3
"""Reproduce the AUD-0072 schema error with full path + check every unit
against its catalog output_schema using disk-only local schemas."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "DUMMY"]  # DUMMY never used

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}
UNITS = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
         "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
         "AUD-0075", "AUD-0080"]


def class_schema(schema_ref: str):
    """Return a validator schema doc for the catalog output_schema:
    - shim classes -> the $defs/<class> profile from the local platform file
      (proven byte-identical to canonical), standalone.
    - real schemas (no $ref) -> the local file as-is."""
    doc = json.loads((REPO / schema_ref).read_text(encoding="utf-8"))
    ref = doc.get("$ref") or ""
    if "#/$defs/" in ref:
        cls = ref.rsplit("/$defs/", 1)[1]
        prof = json.loads(
            (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(encoding="utf-8"))
        d = prof.get("$defs", {}).get(cls)
        if d is None:
            raise SystemExit(f"no $defs/{cls} in artifact-class-profiles")
        d = dict(d)
        d["$defs"] = prof.get("$defs", {})   # keep siblings resolvable
        d["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        return d, cls
    return doc, "(direct)"


# --- AUD-0072 full reproduction first ---
e = byid["AUD-0072"]
art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
schema = json.loads((REPO / e["output_schema"]).read_text(encoding="utf-8"))
v = Draft202012Validator(schema)
errs = sorted(v.iter_errors(art), key=lambda x: list(x.absolute_path))
print(f"AUD-0072 vs claim-record.schema.json: {len(errs)} error(s)")
for err in errs[:10]:
    print("  path:", list(err.absolute_path)[:8], "|", err.message[:160])

# --- then re-validate ALL units disk-only ---
print()
print("disk-only re-validation of all 12:")
for uid in UNITS:
    e = byid[uid]
    art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
    schema, cls = class_schema(e["output_schema"])
    v = Draft202012Validator(schema)
    errs = list(v.iter_errors(art))
    tag = "OK" if not errs else f"{len(errs)} ERR"
    print(f"  {uid} [{cls:16}] {tag}")
    for err in errs[:3]:
        print("     path:", list(err.absolute_path)[:8], "|", err.message[:140])
