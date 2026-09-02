#!/usr/bin/env python3
"""shard-01 scratch: repair RES-0093 envelope to satisfy research-registry schema."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
ART = REPO / "command-center/research/RES-0093.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"

doc = json.loads(ART.read_text(encoding="utf-8"))
schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
validator = jsonschema.Draft7Validator(schema)

def errors(d):
    return list(validator.iter_errors(d))

msgs = Counter(e.message.split("'")[1] if "required property" in e.message else e.message[:60] for e in errors(doc))
print("error groups:")
for m, n in msgs.most_common(30):
    print(f"  {n} x {m}")

if "--write" not in sys.argv:
    sys.exit(0)

ROLE_MAP = {"catalog-shim": "supporting", "live-schema": "supporting"}

def measure(rel: str):
    p = REPO / rel
    if not p.is_file():
        return None
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

for row in doc.get("artifacts") or []:
    rel = row.get("path") or ""
    role = row.get("role")
    if role in ROLE_MAP:
        row["role"] = ROLE_MAP[role]
    m = measure(rel)
    if m is None:
        row.setdefault("exists", False)
        continue
    row["bytes"] = m["bytes"]
    row["sha256"] = m["sha256"]
    row["exists"] = True

rem = errors(doc)
print("after artifact fix:", len(rem))
for e in rem[:15]:
    print("  ", "/".join(str(p) for p in e.absolute_path) or "<root>", ":", e.message[:200])
