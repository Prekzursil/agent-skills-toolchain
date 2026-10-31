#!/usr/bin/env python3
"""Final instrument battery (reviewer wave-3 shard-4):
A. program receipt gate (receipt_schema_gate.evaluate_gate_a default = operative
   schema layer) on all 12 receipts -> schema_errors must be []
B. class-profile strict layer over declared output_schema (DISCLOSURE ONLY,
   program-wide unenforced) -> recorded per unit
C. AUD-0072 adversarial extra: re-validate nested claims against the ARC-0085
   contract that superseded the provisional claim-record schema (independent
   re-check of the builder's claim_shape_errors=[])
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
import referencing.jsonschema as rjs

DRAFT202012 = rjs.DRAFT202012

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
MY = ["AUD-0044", "AUD-0047", "AUD-0053", "AUD-0055", "AUD-0057",
      "AUD-0064", "AUD-0066", "AUD-0069", "AUD-0071", "AUD-0072",
      "AUD-0075", "AUD-0080"]

spec = importlib.util.spec_from_file_location(
    "rsg", REPO / "platform/lib/receipt_schema_gate.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["rsg"] = mod
spec.loader.exec_module(mod)

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {e["id"]: e for e in cat["work_units"]}


def class_profile_strict(schema_ref: str, doc: dict) -> list[str]:
    """Strict declared-schema validation, p2-g1-disk resolved."""
    shim = json.loads((REPO / schema_ref).read_text(encoding="utf-8"))
    ref = shim.get("$ref") or ""
    if "#/$defs/" in ref:
        cls = ref.rsplit("/$defs/", 1)[1]
        prof = json.loads((REPO / "platform/schema/artifact-class-profiles.schema.json")
                          .read_text(encoding="utf-8"))
        defs = prof.get("$defs", {})
        d = dict(defs.get(cls) or {})
        if not d:
            return [f"no-profile:{cls}"]
        # resolve generic_report LOCALLY (registry anchored on receipt.schema.json)
        rec_schema = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
        reg = Registry().with_resource(
            rec_schema["$id"],
            Resource.from_contents(rec_schema, default_specification=DRAFT202012))
        # anchor class-profiles too, so allOf $refs resolve locally
        prof_doc = json.loads((REPO / "platform/schema/artifact-class-profiles.schema.json")
                              .read_text(encoding="utf-8"))
        reg = reg.with_resource(
            prof_doc["$id"],
            Resource.from_contents(prof_doc, default_specification=DRAFT202012))
        d_full = {"allOf": d.get("allOf", []), "$schema": d.get("$schema",
                  "https://json-schema.org/draft/2020-12/schema")}
        v = Draft202012Validator(d_full, registry=reg)
        return [f"{list(e.absolute_path)}: {e.message[:80]}" for e in v.iter_errors(doc)]
    # direct schema (claim-record)
    v = Draft202012Validator(shim)
    return [f"{list(e.absolute_path)}: {e.message[:80]}" for e in v.iter_errors(doc)]


out = {}
for uid in MY:
    e = byid[uid]
    rec = json.loads((REPO / f"command-center/receipts/{uid}.json").read_text(encoding="utf-8"))
    art = json.loads((REPO / e["output_path"]).read_text(encoding="utf-8"))
    # A. operative gate
    g = mod.evaluate_gate_a(rec, repo_root=str(REPO))
    schema_errors = g.schema_errors
    # B. strict declared-schema layer (receipt + artifact), disclosure only
    rec_strict = class_profile_strict(e["output_schema"], rec)
    art_strict = class_profile_strict(e["output_schema"], art)
    out[uid] = {
        "gate_schema_errors": schema_errors,
        "strict_receipt_errors": rec_strict,
        "strict_artifact_errors_count": len(art_strict),
        "strict_artifact_first": art_strict[:2],
    }
    print(f"{uid}: gate={len(schema_errors)}err strict_receipt={len(rec_strict)}err "
          f"strict_artifact={len(art_strict)}err")

# C. AUD-0072 nested claims vs ARC-0085
print()
arc = json.loads((REPO / "command-center/phase4/contracts/ARC-0085.json").read_text(encoding="utf-8"))
print("ARC-0085 contract keys:", list(arc.keys())[:10])
art72 = json.loads((REPO / byid["AUD-0072"]["output_path"]).read_text(encoding="utf-8"))
claims = art72.get("claims") or []
# ARC-0085 contract may itself be a schema or a different shape; inspect
print("ARC-0085 type:", type(arc).__name__)
for k, v in arc.items():
    print(f"  {k}: {type(v).__name__}" + (f" = {json.dumps(v)[:120]}" if not isinstance(v, (dict, list)) else f" keys={list(v.keys())[:12] if isinstance(v, dict) else f'len={len(v)}'}"))
# if it is a json schema, validate the nested claim rows
if arc.get("type") == "object" or "$defs" in arc or "properties" in arc:
    v8 = Draft202012Validator(arc)
    for i, row in enumerate(claims):
        errs = list(v8.iter_errors(row))
        print(f"  claim[{i}] vs ARC-0085: {'OK' if not errs else str(len(errs)) + ' ERR ' + errs[0].message[:100]}")

(  REPO / "_rev-w3-shard4/instrument-results.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8")
print("wrote instrument-results.json")
