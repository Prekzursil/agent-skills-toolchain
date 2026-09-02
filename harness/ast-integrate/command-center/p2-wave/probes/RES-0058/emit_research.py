#!/usr/bin/env python3
"""Write command-center/research/RES-0058.json from live captures + fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = REPO / "command-center/research/RES-0058.json"


def main() -> int:
    doc = E.build_document()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} claims={len(doc['claims'])} rows={len(doc['design_table'])}")
    print("SUCCESS:RES-0058")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
