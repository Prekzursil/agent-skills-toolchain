#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

p = Path(__file__).with_name("_shard00_diag.json")
rows = json.loads(p.read_text(encoding="utf-8"))
c = Counter(r.get("cls") for r in rows)
print("n", len(rows), dict(c))
for r in rows:
    bits = [
        x.strip()
        for x in (r.get("tail_last") or "").splitlines()
        if x.strip()
        and "DeprecationWarning" not in x
        and "class _Draft" not in x
        and "wrapping them" not in x
        and "Subclasses" not in x
        and "jsonschema" not in x.lower()
    ]
    last = " ; ".join(bits[-4:])[:280]
    print(
        f"{r['id']:10} {str(r.get('cls')):22} "
        f"p={len(r['probes'])} h={len(r['helpers'])} out={r['out_size']:8d} {last}"
    )
