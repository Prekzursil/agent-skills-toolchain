#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).with_name("_shard02_dump.json")
rows = json.loads(p.read_text(encoding="utf-8"))
out_lines = []
for r in rows:
    man = r.get("man_rows")
    nman = len(man) if isinstance(man, list) else None
    np = r.get("named_probes")
    nnp = len(np) if isinstance(np, list) else None
    art = r.get("artifact") or {}
    out_lines.append(
        f"{r['id']:10} out={str(r.get('out_exists')):5} "
        f"probes={len(r.get('probes') or [])} helpers={len(r.get('helpers') or [])} "
        f"ret={r.get('ret_status')} named={nnp} man={nman} "
        f"art_bytes={art.get('bytes')} path={r.get('output_path')}"
    )
    out_lines.append(f"  probes {r.get('probes')}")
    out_lines.append(f"  helpers {r.get('helpers')}")
    out_lines.append(f"  keys {art.get('keys')}")
dest = Path(__file__).with_name("_shard02_compact.txt")
dest.write_text("\n".join(out_lines) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {dest} n={len(rows)}")
