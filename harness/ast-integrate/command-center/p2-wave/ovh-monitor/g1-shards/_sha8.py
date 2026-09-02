#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
repo = Path(r"C:\Users\Prekzursil\source\ast-integrate")
res = json.loads((repo / "command-center/p2-wave/ovh-monitor/g1-shards/class-schema.txt.result.json").read_text(encoding="utf-8"))
bad = 0
for row in res["verified_last_lines"]:
    p = repo / row["artifact"]
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    live = hashlib.sha256(raw).hexdigest()
    ok = live == row["sha256"] and len(raw) == row["bytes"]
    print(row["id"], "OK" if ok else "DRIFT", len(raw))
    if not ok:
        bad += 1
        print(" live", live)
        print(" want", row["sha256"])
raise SystemExit(bad)
