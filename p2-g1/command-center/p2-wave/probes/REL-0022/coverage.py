#!/usr/bin/env python3
# REL-0022 coverage subtraction (rebuilt 2026-10-25).
# holes = observed side effects NOT in the recorded inverse set (recovery gap)
# stale = recorded inverse entries NEVER observed (stale plan rows)
import json
from pathlib import Path


def load_recorded(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return doc["recorded_keys"] if isinstance(doc, dict) else list(doc)


def subtract(observed_keys, recorded_keys):
    holes = sorted(set(observed_keys) - set(recorded_keys))
    stale = sorted(set(recorded_keys) - set(observed_keys))
    matched = sorted(set(observed_keys) & set(recorded_keys))
    return {"holes": holes, "hole_count": len(holes),
            "stale": stale, "stale_count": len(stale),
            "matched": matched, "matched_count": len(matched)}
