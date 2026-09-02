#!/usr/bin/env python3
"""Local 2007 census: leftover 1726 + prior 281 RETURN/MANIFEST presence."""
from __future__ import annotations

import json
from pathlib import Path

WAVE = Path(__file__).resolve().parent.parent
PROBES = WAVE / "probes"
LEFTOVER = json.loads((WAVE / "P2-CLOUD-LEFTOVER_2026-08-24.json").read_text(encoding="utf-8"))["remaining_ids"]
PRIOR = json.loads((WAVE / "P2-PRIOR-281_2026-08-24.json").read_text(encoding="utf-8"))["remaining_ids"]


def check(ids, label):
    ret = man = both = missing = 0
    miss_ids = []
    for uid in ids:
        d = PROBES / uid
        r = (d / "SUBAGENT-RETURN.json").is_file()
        m = (d / "UNIT-ARTIFACT-MANIFEST.json").is_file()
        if r:
            ret += 1
        if m:
            man += 1
        if r and m:
            both += 1
        else:
            missing += 1
            if len(miss_ids) < 12:
                miss_ids.append(uid)
    print(f"{label} n={len(ids)} return={ret} manifest={man} both={both} missing_either={missing} sample={miss_ids}")


def main():
    check(LEFTOVER, "leftover1726")
    check(PRIOR, "prior281")
    catalog = sorted(set(LEFTOVER) | set(PRIOR))
    check(catalog, "catalog2007")
    print("disjoint", len(set(LEFTOVER) & set(PRIOR)))


if __name__ == "__main__":
    main()
