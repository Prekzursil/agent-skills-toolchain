#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

d = Path(__file__).resolve().parents[3] / "schema"
pfx = "https://ast-integrate.local/schema/"
names = [
    "source-lineage.schema.json",
    "evidence-tier.schema.json",
    "confidence-band.schema.json",
    "settling-probe.schema.json",
    "claim-edge.schema.json",
    "freshness-stamp.schema.json",
    "snapshot-sha256.schema.json",
]
for name in names:
    path = d / name
    if path.is_file() and path.stat().st_size > 0:
        print("exists", name, path.stat().st_size)
        continue
    stem = name.replace(".schema.json", "")
    if stem == "snapshot-sha256":
        doc = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": pfx + name,
            "title": stem,
            "type": "string",
            "minLength": 64,
            "maxLength": 64,
            "pattern": "^[a-f0-9]{64}$",
        }
    else:
        doc = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": pfx + name,
            "title": stem,
            "type": "object",
            "additionalProperties": True,
        }
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("wrote", name, path.stat().st_size)
