#!/usr/bin/env python3
"""Shard0-w2 scan: per-unit artifact structure vs delivery predicate."""
import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
IDS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018",
       "ADV-0022", "ADV-0023", "ADV-0024"]

data = json.loads(CATALOG.read_text(encoding="utf-8"))
units = {u.get("id"): u for u in data.get("work_units", []) if isinstance(u, dict)}

for uid in IDS:
    u = units[uid]
    out_rel = str(u["output_path"]).replace("\\", "/")
    sentinel = u.get("completion_sentinel") or ""
    out = REPO / out_rel
    text = out.read_text(encoding="utf-8")
    doc = json.loads(text)
    print("=" * 72)
    print(f"{uid}  {out_rel}")
    print(f"  sentinel-in-text: {sentinel in text}  bytes={out.stat().st_size}")
    print(f"  top-keys: {sorted(doc.keys())}")
    print(f"  state: {doc.get('state')}  schema_version: {doc.get('schema_version')}")
    ev = doc.get("evidence") or []
    print(f"  evidence items: {len(ev)}")
    for i, item in enumerate(ev[:3]):
        probes = item.get("probes") or []
        print(f"   ev[{i}] verdict={item.get('verdict')} probes={len(probes)} "
              f"roles={[p.get('role') for p in probes]}")
    # recorded named probe commands anywhere
    raw = text
    import re
    cmds = re.findall(r"command-center/p2-wave/probes/ADV-\d{4}/[A-Za-z0-9_./-]+\.py", raw)
    uniq = sorted(set(cmds))
    print(f"  recorded probe commands: {len(uniq)}")
    for c in uniq[:8]:
        print(f"    {c}")
    # targets/verdicts summary
    for key in ("targets", "claims", "units"):
        v = doc.get(key)
        if isinstance(v, list):
            print(f"  {key}: {len(v)} items; sample verdicts="
                  f"{[t.get('verdict') for t in v[:5]]}")
    # verdict census across evidence
    verdicts = [str(item.get("verdict")) for item in ev]
    from collections import Counter
    print(f"  evidence verdict census: {dict(Counter(verdicts))}")
    # controls / negative tests
    for key in ("controls", "negative_tests", "control_results"):
        v = doc.get(key)
        if isinstance(v, list):
            print(f"  {key}: {len(v)}")
        elif isinstance(v, dict):
            print(f"  {key}: {list(v)[:6]}")
