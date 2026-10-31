#!/usr/bin/env python3
"""Population baseline: validate every receipt present in command-center/receipts
against the output_schema declared for it in the TST-1 catalog slice (TST family)
-- to determine whether strict output_schema validation fails the WHOLE program or
only shard 23. Fail-closed population census; no writes to program artifacts."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\Prekzursil\p2-g1\_reviewer23-w2")
from verify_shard23 import load_schema, REPO  # noqa: E402

from jsonschema import Draft202012Validator

with open(REPO / "command-center" / "catalog-slices" / "TST-1.json", encoding="utf-8") as f:
    slice_entries = json.load(f)
cat = {e["id"]: e for e in slice_entries}

import re
SHARD = {"TST-0113", "TST-0124", "TST-0129", "TST-0130", "TST-0136", "TST-0137",
         "TST-0138", "TST-0139", "TST-0141", "TST-0142", "TST-0143", "TST-0144"}

receipts = sorted((REPO / "command-center" / "receipts").glob("TST-*.json"))
npass = nfail = nmiss = 0
fail_ids, pass_ids = [], []
for rp in receipts:
    uid = rp.stem
    e = cat.get(uid)
    if not e or not e.get("output_schema"):
        nmiss += 1
        continue
    try:
        with open(rp, encoding="utf-8") as f:
            doc = json.load(f)
        schema = load_schema(e["output_schema"])
        Draft202012Validator.check_schema(schema)
        errs = list(Draft202012Validator(schema).iter_errors(doc))
        if errs:
            nfail += 1
            if uid not in SHARD:
                fail_ids.append((uid, errs[0].message[:110]))
        else:
            npass += 1
            pass_ids.append(uid)
    except Exception as exc:
        nfail += 1
        fail_ids.append((uid, "%s: %s" % (type(exc).__name__, str(exc)[:80])))

print("receipts scanned: %d | schema PASS: %d | schema FAIL: %d | no-schema-decl: %d" % (len(receipts), npass, nfail, nmiss))
print("PASS ids:", pass_ids)
print("non-shard FAIL sample (first 15):")
for uid, msg in fail_ids[:15]:
    print("  %s: %s" % (uid, msg))
