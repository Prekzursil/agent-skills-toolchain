#!/usr/bin/env python3
import json
from pathlib import Path

p = Path(__file__).with_name("_shard04_dump.json")
d = json.loads(p.read_text(encoding="utf-8"))
for r in d["rows"]:
    art = r.get("artifact") or {}
    py = [x["name"] for x in r.get("probes") or []]
    print(
        f"{r['id']:10} sent={art.get('has_sentinel')} state={str(art.get('state')):16} "
        f"man={r['man_n']} py={py}"
    )
