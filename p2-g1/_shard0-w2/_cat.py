#!/usr/bin/env python3
"""Shard0-w2: extract catalog entries + on-disk state for my 12 units."""
import json
import os
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
IDS = [
    "ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
    "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029", "ADV-0033",
]

data = json.loads(CATALOG.read_text(encoding="utf-8"))
units = {u.get("id"): u for u in data.get("work_units", []) if isinstance(u, dict)}
print(f"catalog total={len(data.get('work_units', []))} keys={sorted(data.keys())[:12]}")

for uid in IDS:
    u = units.get(uid)
    print("=" * 70)
    if u is None:
        print(f"{uid}: NOT-IN-CATALOG")
        continue
    keep = {
        k: u.get(k)
        for k in ("id", "output_path", "completion_sentinel", "description",
                  "dependencies", "named_probes", "probes", "gate", "owner_gate",
                  "gate_reason", "notes", "output_schema", "status")
        if k in u
    }
    print(json.dumps(keep, indent=1)[:2600])
    # on-disk state
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    if out is None:
        print("  STATE: no output_path")
    elif out.is_file():
        try:
            doc = json.loads(out.read_text(encoding="utf-8"))
            st = str(doc.get("state", "")).upper() if isinstance(doc, dict) else "(non-dict)"
            print(f"  STATE: artifact EXISTS bytes={out.stat().st_size} state={st}")
        except Exception as exc:
            print(f"  STATE: artifact EXISTS bytes={out.stat().st_size} UNPARSEABLE {type(exc).__name__}")
    else:
        print(f"  STATE: artifact MISSING ({out_rel})")
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    if pdir.is_dir():
        names = sorted(p.name for p in pdir.iterdir())
        print(f"  PROBES: {names}")
        sr = pdir / "SUBAGENT-RETURN.json"
        if sr.is_file():
            try:
                r = json.loads(sr.read_text(encoding="utf-8"))
                print(f"  RETURN.status={r.get('status') or r.get('state')}")
            except Exception as exc:
                print(f"  RETURN UNPARSEABLE {type(exc).__name__}")
        man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
        if man.is_file():
            try:
                m = json.loads(man.read_text(encoding="utf-8"))
                rows = [a for a in (m.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
                print(f"  MANIFEST rows-for-unit={len(rows)}")
            except Exception as exc:
                print(f"  MANIFEST UNPARSEABLE {type(exc).__name__}")
    else:
        print("  PROBES: (none)")
    # receipt search
    for cand in (
        REPO / "command-center" / "p2-wave" / "receipts" / f"{uid}.json",
        REPO / "command-center" / "receipts" / f"{uid}.json",
        pdir / "RECEIPT.json",
    ):
        if cand.is_file():
            print(f"  RECEIPT: {cand}")
