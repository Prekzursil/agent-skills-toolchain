#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0016-sweep-releases.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/wfa/WFA-0016-sweep-releases.json"


def main() -> int:
    doc = S.build_report()
    ctr = doc.get("controls") or {}
    required = (
        "caret_deref_refused",
        "powershell_mangle_differs",
        "empty_not_skipped",
        "zero_releases_explicit",
        "packaging_mismatch_named",
        "registry_omit_named",
    )
    missing = [k for k in required if ctr.get(k) is not True]
    if missing:
        print(f"FAILED:WFA-0016 emit controls not green: {missing}")
        print(json.dumps(ctr, indent=2, sort_keys=True))
        return 1
    if "SUCCESS:WFA-0016" not in json.dumps(doc):
        print("FAILED:WFA-0016 emit sentinel missing")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:WFA-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
