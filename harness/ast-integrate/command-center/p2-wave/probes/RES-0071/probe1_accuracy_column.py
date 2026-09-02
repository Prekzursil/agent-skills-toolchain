#!/usr/bin/env python3
"""RES-0071 probe 1: per-system accuracy column + two-rail evidence + snapshot hashes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate import OUT_REL, REPO, SENTINEL, UNIT, check_path  # noqa: E402


def main() -> int:
    path = REPO / OUT_REL
    errs = check_path(path)
    payload = {
        "probe": "probe1-accuracy-column-and-two-rails",
        "unit_id": UNIT,
        "artifact": OUT_REL,
        "errors": errs,
        "pass": not errs,
        "sentinel_present": SENTINEL in path.read_text(encoding="utf-8") if path.is_file() else False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errs:
        print("FAILED:RES-0071-probe1 accuracy-column/two-rail contract")
        for e in errs:
            print(f"  {e}")
        return 1
    print("SUCCESS:RES-0071-probe1 every system has accuracy_column; two rails rehash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
