#!/usr/bin/env python3
"""Extract compact fail-relevant tails to a short text file."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard18_compact.json").read_text(encoding="utf-8"))
out_lines: list[str] = []
for r in rows:
    out_lines.append(f"==== {r['id']} {r['title'][:90]}")
    out_lines.append(f"  out {r['output_path']}")
    out_lines.append(f"  py {r['py_files']}")
    out_lines.append(f"  imports {r['imports']}")
    for name, lines in (r.get("tails") or {}).items():
        out_lines.append(f"  -- {name}")
        for ln in lines[-14:]:
            out_lines.append("    " + ln[:180])
text = "\n".join(out_lines) + "\n"
dest = HERE / "_shard18_tails.txt"
dest.write_text(text, encoding="utf-8")
print(f"wrote {dest} bytes={len(text)} n={len(rows)}")
