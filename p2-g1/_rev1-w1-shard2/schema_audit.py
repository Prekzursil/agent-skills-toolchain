#!/usr/bin/env python3
"""Full schema-error enumeration for the 12 shard-2 artifacts (adversarial evidence)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from revlib import REPO, load_catalog_entries, validate_against_schema
import jsonschema
from revlib import _retrieve  # type: ignore
from referencing import Registry

IDS = ["AUD-0033", "AUD-0043", "AUD-0047", "AUD-0053", "AUD-0057", "AUD-0066",
       "AUD-0069", "AUD-0072", "AUD-0080", "AUD-0082", "AUD-0084", "AUD-0096"]

entries = load_catalog_entries(IDS)
schema = json.loads((REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8"))
reg = Registry(retrieve=_retrieve)
cls = jsonschema.validators.validator_for(schema)
cls.check_schema(schema)


def all_errors(doc, schema_rel):
    s = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    c = jsonschema.validators.validator_for(s)
    v = c(s, registry=reg)
    out = []
    for e in v.iter_errors(doc):
        out.append({"at": [str(x) for x in e.absolute_path][:6],
                    "msg": str(e.message)[:400]})
    return out


report = {}
for uid in IDS:
    e = entries[uid]
    p = REPO / e["output_path"]
    if not p.exists():
        report[uid] = {"error": "artifact missing"}
        continue
    doc = json.loads(p.read_bytes().decode("utf-8"))
    errs = all_errors(doc, e["output_schema"])
    missing_core = sorted(set(
        m.split("'")[1] for m in (x["msg"] for x in errs)
        if m.startswith("'") and "is a required property" in m
    ))
    report[uid] = {
        "state": doc.get("state"),
        "n_errors": len(errs),
        "missing_required": missing_core,
        "errors": errs[:25],
    }
    print(uid, "errors:", len(errs), "| missing:", missing_core[:12])

out = HERE / "schema_errors.json"
out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
print("wrote", out)
