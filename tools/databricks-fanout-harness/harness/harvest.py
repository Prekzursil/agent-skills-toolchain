"""Harvest artifacts from DBFS via `fs cat` per file (fs cp DBFS->local is a SILENT no-op).
Writes each body utf-8 and flags below the per-lane floor."""
from __future__ import annotations
from pathlib import Path
from harness.contract import floor_for, RAIL

def harvest(dbfs_dir, dest_dir, units, run_cmd) -> dict:
    dest = Path(dest_dir); dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for u in units:
        name = Path(u.artifact).name
        rc, body, _ = run_cmd(["databricks", "fs", "cat", f"{dbfs_dir}/{name}",
                               "--profile", RAIL["profile"]])
        if rc != 0:
            out[u.id] = ("absent", 0); continue
        data = body.encode("utf-8", errors="replace")
        (dest / name).write_text(body, encoding="utf-8")
        out[u.id] = (("harvested" if len(data) >= floor_for(u.lane) else "below-floor"), len(data))
    return out
