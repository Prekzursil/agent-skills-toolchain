#!/usr/bin/env python3
"""Probe 1: 20/20 identifier renames preserve the structural fingerprint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fingerprint as F  # noqa: E402
import fixtures as X  # noqa: E402


def main() -> int:
    base_fp = F.fingerprint(X.BASE)
    rows = []
    preserved = 0
    for tag, mutant in X.rename_mutants():
        fp = F.fingerprint(mutant)
        ok = fp == base_fp
        preserved += int(ok)
        rows.append({"tag": tag, "equal": ok, "sha256": fp})
    payload = {
        "base_sha256": base_fp,
        "preserved": preserved,
        "total": 20,
        "pass": preserved == 20,
        "probe": "probe1-rename-invariance",
        "unit_id": "IMP-0170",
        "rows": rows,
    }
    print(json.dumps({k: payload[k] for k in payload if k != "rows"}, sort_keys=True))
    for r in rows:
        print(f"rename {r['tag']} equal={r['equal']}")
    if preserved != 20:
        print(f"FAILED:IMP-0170-probe1 rename invariance {preserved}/20")
        return 1
    # Extra: permuting the stage list must not change the digest either
    # (identifier-order is not mechanism). Not counted in the 20/20.
    permuted = json.loads(json.dumps(X.BASE))
    permuted["stages"] = list(reversed(permuted["stages"]))
    if F.fingerprint(permuted) != base_fp:
        print("FAILED:IMP-0170-probe1 stage-list permutation changed fingerprint")
        return 1
    print("SUCCESS:IMP-0170-probe1 20/20 renames preserve fingerprint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
