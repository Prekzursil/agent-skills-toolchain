#!/usr/bin/env python3
"""Write command-center/wfa/WFA-0098-duplicate-threshold-calibration.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from calibrate import semantic_diff_doc  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0098-duplicate-threshold-calibration.json"


def emit() -> Path:
    doc = semantic_diff_doc()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    OUT.write_bytes(text.encode("utf-8"))
    return OUT


def main() -> int:
    path = emit()
    print(f"wrote {path.relative_to(REPO).as_posix()} bytes={path.stat().st_size}")
    print("SUCCESS:WFA-0098-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
