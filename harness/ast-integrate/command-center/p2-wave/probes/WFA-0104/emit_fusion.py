#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0104-fusion-conditional-hybrid.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402
from hybrid_op import emit_fusion_result  # noqa: E402

OUT = "command-center/wfa/WFA-0104-fusion-conditional-hybrid.json"


def main() -> int:
    S.write_fixtures()
    spec = S.good_spec()
    doc = emit_fusion_result(spec)
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print("SUCCESS:WFA-0104 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
