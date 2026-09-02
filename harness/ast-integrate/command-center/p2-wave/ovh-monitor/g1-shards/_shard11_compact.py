#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / "_shard11_dump.json").read_text(encoding="utf-8"))
lines: list[str] = []
for r in data["rows"]:
    lines.append("=" * 72)
    lines.append(r["id"])
    lines.append(f"title: {r.get('title')}")
    lines.append(f"out: {r.get('output_path')} bytes={r.get('output_bytes')} sent={r.get('art_sentinel_ok')} state={r.get('art_state')}")
    lines.append(f"py: {r.get('py_files')}")
    lines.append(f"imports: {r.get('imports')}")
    for p in r.get("probes") or []:
        lines.append(f"-- {p['name']} froms={p.get('froms')} --")
        for a in p.get("asserts") or []:
            lines.append(f"  {a}")
        if not p.get("asserts"):
            for ln in (p.get("tail") or [])[-8:]:
                lines.append(f"  T|{ln}")
text = "\n".join(lines) + "\n"
dest = HERE / "_shard11_asserts.txt"
dest.write_text(text, encoding="utf-8")
print("wrote", dest, "chars", len(text))
