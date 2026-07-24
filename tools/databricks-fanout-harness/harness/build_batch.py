from __future__ import annotations
import json
from pathlib import Path
def build_batch(units, name):
    return {"name": name,
            "units": [{"id":u.id,"lane":u.lane,"prompt":u.prompt,"artifact":u.artifact,
                       "timeout_s":u.timeout_s} for u in units],
            "meta": {"n": len(units)}}
def write_batch(batch, dest):
    dest = Path(dest); dest.write_text(json.dumps(batch, indent=1)+"\n", encoding="utf-8"); return dest
