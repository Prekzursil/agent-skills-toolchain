#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard12_dump.json").read_text(encoding="utf-8"))
out_lines = []
for r in rows:
    out_lines.append("=" * 72)
    out_lines.append(r["id"])
    out_lines.append(f"title: {r.get('title')}")
    out_lines.append(f"output: {r.get('output_path')} bytes={r.get('output_bytes')}")
    out_lines.append(f"sentinel: {r.get('sentinel')}")
    out_lines.append(f"py: {r.get('py_files')}")
    out_lines.append(f"imports: {r.get('imports')}")
    out_lines.append(f"faileds: {r.get('faileds')}")
    out_lines.append("asserts:")
    for a in r.get("asserts") or []:
        out_lines.append(f"  {a}")
    tails = r.get("probe_tails") or {}
    for name, tail in tails.items():
        out_lines.append(f"-- tail {name} --")
        for ln in tail[-18:]:
            out_lines.append(f"  {ln}")
text = "\n".join(out_lines) + "\n"
dest = HERE / "_shard12_compact.txt"
dest.write_text(text, encoding="utf-8")
print("wrote", dest, "chars", len(text), "n", len(rows))
