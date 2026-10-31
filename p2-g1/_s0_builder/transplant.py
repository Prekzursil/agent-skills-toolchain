#!/usr/bin/env python3
"""Transplant original wave probe dirs from source tree into p2-g1 (builder shard 0).

Preserves finished subagent work: copies probe scripts, fixtures, receipts and
manifests verbatim. For ADV-0027 (already partially re-done in p2-g1 by a prior
builder), copies only files that do not collide with the p2-g1 versions, so the
dead builder's delivery-predicate probes and receipt stay.
Excludes __pycache__.
"""
from __future__ import annotations

import shutil
from pathlib import Path

SRC = Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/probes")
DST = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes")
UNITS = [
    "ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
    "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127",
]
# Files the p2-g1 builder already authored for ADV-0027; never overwrite these.
KEEP_P2G1 = {"ADV-0027": {
    "UNIT-ARTIFACT-MANIFEST.json", "SUBAGENT-RETURN.json",
    "probe1_delivery_predicate.py", "probe2_independent_recheck.py",
    "nc_live.json",
}}


def main() -> int:
    total = 0
    for uid in UNITS:
        s, d = SRC / uid, DST / uid
        if not s.is_dir():
            print(f"FAILED:transplant {uid} source-missing")
            return 1
        d.mkdir(parents=True, exist_ok=True)
        keep = KEEP_P2G1.get(uid, set())
        n = 0
        for f in sorted(s.rglob("*")):
            if "__pycache__" in f.parts or not f.is_file():
                continue
            rel = f.relative_to(s)
            if str(rel) in keep:
                continue
            target = d / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            n += 1
        print(f"transplanted {uid}: {n} files")
        total += n
    print(f"SUCCESS:transplant {total} files across {len(UNITS)} units")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
