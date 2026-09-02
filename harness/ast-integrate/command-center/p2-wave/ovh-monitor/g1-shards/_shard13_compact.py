#!/usr/bin/env python3
"""Compact shard-13 dump into per-id API/assert brief."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = json.loads((HERE / "_shard13_dump.json").read_text(encoding="utf-8"))
out = []
for r in rows:
    names = r.get("probe_names") or {}
    froms = r.get("probe_froms") or {}
    asserts = r.get("probe_asserts") or {}
    # keep only interesting names (imported modules + attrs)
    interesting = {}
    for pname, nmap in names.items():
        if not isinstance(nmap, dict):
            continue
        for mod, attrs in nmap.items():
            if mod in {"os", "sys", "json", "Path", "pathlib", "re", "hashlib", "typing", "print", "len", "str", "int", "list", "dict", "set", "tuple", "bool", "bytes", "True", "False", "None"}:
                continue
            if attrs:
                interesting.setdefault(mod, [])
                for a in attrs:
                    if a not in interesting[mod]:
                        interesting[mod].append(a)
    out.append(
        {
            "id": r["id"],
            "title": r["title"],
            "output_path": r["output_path"],
            "froms": froms,
            "interesting": interesting,
            "asserts": asserts,
            "py_files": r["py_files"],
            "modules": {k: v for k, v in (r.get("modules") or {}).items() if k not in {"__future__"}},
        }
    )
dest = HERE / "_shard13_compact.json"
dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
print("wrote", dest, "n=", len(out))
for r in out:
    mods = list((r["interesting"] or {}).keys())[:10]
    a0 = list((r["asserts"] or {}).values())
    nassert = sum(len(v or []) for v in (r["asserts"] or {}).values())
    print(f"{r['id']} files={r['py_files'][:6]} mods={mods} nassert={nassert}")
