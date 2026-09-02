#!/usr/bin/env python3
"""Emit command-center/synthesis/SYN-0003.rival-explanations.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402

OUT_REL = "command-center/synthesis/SYN-0003.rival-explanations.json"
SCHEMA_REL = "command-center/schema/rival-hypothesis.schema.json"


def main() -> int:
    doc = G.build_document()
    schema = json.loads((G.REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    if doc.get("state") != "SUCCESS":
        print("FAILED:SYN-0003 emit state=" + str(doc.get("state")))
        print(json.dumps(doc.get("tests"), indent=2)[:3000])
        return 1
    out = G.REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} state={doc['state']}")
    print("SUCCESS:SYN-0003 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
