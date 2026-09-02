from pathlib import Path
from datetime import datetime, timezone

cands = [
    Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards"),
    Path.home() / "p2-g1/command-center/p2-wave/ovh-monitor/g1-shards",
]
for d in cands:
    print("DIR", d, "exists", d.exists())
    if not d.exists():
        continue
    for name in ("class-other.measure.json", "class-other.measure.jsonl", "class-other.heartbeat.json"):
        p = d / name
        if p.exists():
            st = p.stat()
            print(" ", name, "size", st.st_size, "mtime", datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat())
        else:
            print(" ", name, "MISSING")
