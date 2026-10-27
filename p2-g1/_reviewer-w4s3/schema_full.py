#!/usr/bin/env python3
"""w4s3 reviewer phase 1b: full artifact-schema error inventory per unit.

Two instruments, identical verdicts required:
  A) catalog shim as declared (absolute file:// $ref fetches the ast-integrate
     physical profile) - the exact path a consumer following the catalog takes.
  B) the LOCAL physical profile fragment directly (no remote retrieval).
Error count + verdict must agree.
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parents[1]
IDS = ["ARC-0055", "ARC-0056", "ARC-0076", "AUD-0003", "AUD-0005", "AUD-0008",
       "AUD-0010", "AUD-0026", "AUD-0032", "AUD-0033", "AUD-0042", "AUD-0043"]

cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
byid = {u["id"]: u for u in cat["work_units"]}
profiles = json.loads((REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(encoding="utf-8"))

out = {}
for uid in IDS:
    u = byid[uid]
    art = json.loads((REPO / str(u["output_path"]).replace("\\", "/")).read_text(encoding="utf-8"))
    shim_rel = str(u["output_schema"]).replace("\\", "/")
    shim = json.loads((REPO / shim_rel).read_text(encoding="utf-8"))
    frag = str(shim.get("x-physical-definition") or "")
    # instrument B: local fragment directly
    frag_name = frag.split("#/$defs/")[-1] if "#/$defs/" in frag else None
    local_schema = None
    if frag_name and frag_name in profiles.get("$defs", {}):
        local_schema = dict(profiles["$defs"][frag_name])
        local_schema["$defs"] = profiles.get("$defs", {})
    entry = {"output_path": u["output_path"], "output_schema": shim_rel,
             "physical_fragment": frag_name}
    # instrument A: shim as declared (allows remote fetch of the absolute ref)
    try:
        vA = Draft202012Validator(shim)
        errsA = sorted({f"{list(e.absolute_path)}: {e.message[:180]}" for e in vA.iter_errors(art)})
    except Exception as e:  # noqa: BLE001
        errsA = [f"INSTRUMENT-A-ERROR {type(e).__name__}: {e}"]
    # instrument B: local physical fragment
    try:
        if local_schema is None:
            errsB = ["INSTRUMENT-B no local fragment"]
        else:
            vB = Draft202012Validator(local_schema)
            errsB = sorted({f"{list(e.absolute_path)}: {e.message[:180]}" for e in vB.iter_errors(art)})
    except Exception as e:  # noqa: BLE001
        errsB = [f"INSTRUMENT-B-ERROR {type(e).__name__}: {e}"]
    entry["instrumentA_errors"] = errsA
    entry["instrumentB_errors"] = errsB
    entry["verdict_agree"] = (len(errsA) == 0) == (len(errsB) == 0)
    entry["error_count_A"] = len(errsA)
    entry["error_count_B"] = len(errsB)
    out[uid] = entry
    print(f"{uid}: frag={frag_name} A={len(errsA)} B={len(errsB)} agree={entry['verdict_agree']}")
    for e in errsA[:6]:
        print("   ", e[:200])

(Path(__file__).parent / "schema_full.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote", Path(__file__).parent / "schema_full.json")
