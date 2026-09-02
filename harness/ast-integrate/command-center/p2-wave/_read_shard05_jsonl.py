#!/usr/bin/env python3
import json
from pathlib import Path

p = Path.home() / "p2-g1" / "_g1_shard05_measure.jsonl"
print("path", p, "exists", p.is_file(), "bytes", p.stat().st_size if p.is_file() else 0)
if not p.is_file():
    raise SystemExit(0)
for ln in p.read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    print("====", rec["id"], "ok", rec["ok"], rec.get("line"))
    for t in (rec.get("tail") or "").splitlines():
        low = t.lower()
        if any(
            k in t or k in low
            for k in (
                "FAILED",
                "Error",
                "assert",
                "ModuleNotFound",
                "probe[",
                "Traceback",
                "PermissionError",
                "FileNotFound",
            )
        ):
            print(t[:360])
