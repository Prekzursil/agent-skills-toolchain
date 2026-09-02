#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\source\ast-integrate")
SHARD = ROOT / "command-center/p2-wave/ovh-monitor/g1-shards/shard-08.txt"
CATALOG = ROOT / "command-center/WORK-UNIT-CATALOG.json"
PROBES = ROOT / "command-center/p2-wave/probes"
OUT = ROOT / "command-center/p2-wave/ovh-monitor/g1-shards/_shard08_catalog.json"

ids = [ln.strip() for ln in SHARD.read_text(encoding="utf-8").splitlines() if ln.strip()]
cat = json.loads(CATALOG.read_text(encoding="utf-8"))
by = {u.get("id"): u for u in cat.get("work_units") or [] if isinstance(u, dict)}
rows = []
for uid in ids:
    u = by.get(uid) or {}
    pdir = PROBES / uid
    probes = sorted(p.name for p in pdir.glob("probe*.py")) if pdir.is_dir() else []
    ret_path = pdir / "SUBAGENT-RETURN.json"
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = ROOT / out_rel if out_rel else None
    rows.append(
        {
            "id": uid,
            "in_catalog": uid in by,
            "title": (u.get("title") or u.get("name") or "")[:120],
            "output_path": out_rel,
            "output_exists": bool(out and out.is_file() and out.stat().st_size > 0),
            "output_bytes": out.stat().st_size if out and out.is_file() else 0,
            "sentinel": str(u.get("completion_sentinel") or "")[:160],
            "probe_dir": pdir.is_dir(),
            "probes": probes,
            "has_return": ret_path.is_file(),
            "has_manifest": man_path.is_file(),
            "deps": u.get("depends_on") or u.get("dependencies") or [],
        }
    )

OUT.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
print(f"wrote {OUT} n={len(rows)}")
for r in rows:
    print(
        f"{r['id']}\tcat={r['in_catalog']}\tout={r['output_exists']}:{r['output_bytes']}\t"
        f"probes={len(r['probes'])}\tret={r['has_return']}\tman={r['has_manifest']}\t{r['output_path']}"
    )
