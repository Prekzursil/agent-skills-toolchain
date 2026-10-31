#!/usr/bin/env python3
"""w3s18 reviewer: quick status scan of my 12 units (read-only)."""
import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(r"C:/Users/Prekzursil/p2-g1")
UNITS = ["RES-0179", "RES-0180", "RES-0182", "TST-0018", "TST-0028", "TST-0032",
         "TST-0057", "TST-0060", "TST-0066", "TST-0067", "TST-0068", "TST-0070"]
byid = json.loads((BASE / "_rev-w3s18-entries.json").read_text(encoding="utf-8"))

for uid in UNITS:
    u = byid[uid]
    out = BASE / str(u["output_path"]).replace("\\", "/")
    pdir = BASE / "command-center/p2-wave/probes" / uid
    man = pdir / "UNIT-ARTIFACT-MANIFEST.json"
    ret = pdir / "SUBAGENT-RETURN.json"
    if uid.startswith("TST"):
        rcp = out
    else:
        rcp = BASE / "command-center/receipts" / f"{uid}.json"

    def st(p):
        return f"Y({p.stat().st_size}b)" if p.is_file() else "N"

    probes = [p.name for p in sorted(pdir.glob("*.py"))] if pdir.is_dir() else []
    print(f"{uid}: out={st(out)} receipt={st(rcp)} manifest={st(man)} return={st(ret)} probes={probes}")
    if rcp.is_file():
        try:
            r = json.loads(rcp.read_text(encoding="utf-8"))
            rev = r.get("reviewer") or {}
            fcls = (r.get("failure") or {}).get("classification")
            print(f"   state={r.get('state')} rev.verdict={rev.get('verdict')} rev.ind={rev.get('independent')} "
                  f"rev.id={str(rev.get('reviewer_id'))[:44]} fcls={fcls}")
        except Exception as e:
            print("   receipt parse ERR", e)
