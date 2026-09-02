#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
IDS = [
    ln.strip()
    for ln in (WAVE / "ovh-monitor" / "g1-shards" / "shard-04.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if ln.strip()
]
CAT = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY = {u["id"]: u for u in CAT["work_units"]}
rows = []
for uid in IDS:
    u = BY.get(uid) or {}
    pdir = WAVE / "probes" / uid
    out_rel = str(u.get("output_path") or "").replace("\\", "/")
    out = REPO / out_rel if out_rel else None
    files = []
    if pdir.is_dir():
        files = sorted(p.name for p in pdir.iterdir())
    ret = {}
    ret_path = pdir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret = json.loads(ret_path.read_text(encoding="utf-8"))
        except Exception as exc:
            ret = {"_err": str(exc)}
    man = {}
    man_path = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    if man_path.is_file():
        try:
            man = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception as exc:
            man = {"_err": str(exc)}
    art = None
    if out and out.is_file():
        try:
            txt = out.read_text(encoding="utf-8")
            art = {
                "bytes": out.stat().st_size,
                "state": None,
                "has_sentinel": False,
                "head": txt[:240],
            }
            try:
                doc = json.loads(txt)
                if isinstance(doc, dict):
                    art["state"] = doc.get("state") or doc.get("status") or doc.get("verdict")
                    art["keys"] = sorted(doc.keys())[:24]
            except Exception:
                art["parse"] = "fail"
            sent = str(u.get("completion_sentinel") or "")
            art["has_sentinel"] = bool(sent) and sent in txt
        except Exception as exc:
            art = {"err": str(exc)}
    probes = []
    for name in files:
        if name.endswith(".py"):
            p = pdir / name
            text = p.read_text(encoding="utf-8", errors="replace")
            probes.append(
                {
                    "name": name,
                    "lines": text.count("\n") + 1,
                    "head": "\n".join(text.splitlines()[:40]),
                }
            )
    cmds = []
    if isinstance(ret, dict):
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and item.get("command"):
                cmds.append(item["command"])
    rows.append(
        {
            "id": uid,
            "title": (u.get("title") or u.get("name") or "")[:180],
            "output_path": out_rel,
            "sentinel": (u.get("completion_sentinel") or "")[:220],
            "tests_required": u.get("tests_required") or u.get("acceptance") or [],
            "probe_files": files,
            "named_cmds": cmds[:8],
            "ret_status": (ret.get("status") or ret.get("state") if isinstance(ret, dict) else None),
            "man_n": len((man.get("artifacts") or []) if isinstance(man, dict) else []),
            "artifact": art,
            "probes": probes,
        }
    )

outp = WAVE / "ovh-monitor" / "g1-shards" / "_shard04_dump.json"
outp.write_text(json.dumps({"n": len(rows), "rows": rows}, indent=2), encoding="utf-8")
print(f"wrote {outp} n={len(rows)}")
for r in rows:
    print(f"{r['id']:10} out={bool(r['artifact'])} probes={len(r['probe_files'])} cmds={len(r['named_cmds'])} {r['title'][:70]}")
