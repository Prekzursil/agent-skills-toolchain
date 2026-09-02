#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard15_dump.json").read_text(encoding="utf-8"))
out = []
for r in rows:
    miss = [
        k
        for k, v in (r.get("modules") or {}).items()
        if not v.get("hits") and k != "__future__"
    ]
    sha_ok = False
    man = r.get("manifest_rows") or []
    if man:
        sha_ok = all(x.get("sha_match") for x in man)
    out.append(
        {
            "id": r["id"],
            "title": r.get("title"),
            "output_path": r.get("output_path"),
            "sha_ok": sha_ok,
            "miss": miss,
            "named_cmds": r.get("named_cmds") or [],
            "asserts": (r.get("asserts") or [])[:20],
            "py_files": r.get("py_files") or [],
            "imports": r.get("imports") or [],
            "probe_froms": r.get("probe_froms") or {},
            "probe_names": r.get("probe_names") or {},
        }
    )
dest = HERE / "_shard15_compact.json"
dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"wrote {dest} n={len(out)}")
for r in out:
    print(f"{r['id']} sha={r['sha_ok']} miss={r['miss'][:5]} nA={len(r['asserts'])}")
