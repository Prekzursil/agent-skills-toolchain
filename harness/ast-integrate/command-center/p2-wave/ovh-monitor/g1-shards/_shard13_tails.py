#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard13_dump.json").read_text(encoding="utf-8"))
parts = []
for r in rows:
    parts.append("=" * 72)
    parts.append(r["id"] + " " + (r.get("title") or "")[:80])
    parts.append("out=" + str(r.get("output_path")))
    parts.append("files=" + " ".join(r.get("py_files") or []))
    for name, tail in (r.get("probe_tails") or {}).items():
        parts.append("--- " + name + " tail ---")
        parts.extend(tail or [])
    for name, head in (r.get("probe_heads") or {}).items():
        parts.append("--- " + name + " head ---")
        parts.extend(head or [])
text = "\n".join(parts) + "\n"
dest = HERE / "_shard13_tails.txt"
dest.write_text(text, encoding="utf-8")
print("wrote", dest, "bytes", dest.stat().st_size)
