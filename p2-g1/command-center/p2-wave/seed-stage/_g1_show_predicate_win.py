#!/usr/bin/env python3
"""Print class buckets (small ones fully) from the coordinator's classes.json."""
import json
from pathlib import Path

P = Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/ovh-monitor/g1-shards/classes.json")
d = json.loads(P.read_text(encoding="utf-8"))


def walk(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        print(prefix, len(obj))
        if len(obj) <= 12:
            print("  ", obj)


walk(d)
