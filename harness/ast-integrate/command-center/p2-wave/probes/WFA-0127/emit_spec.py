#!/usr/bin/env python3
"""Write the catalog WorkflowIR artifact for WFA-0127."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import ARTIFACT_REL, REPO, SENTINEL  # noqa: E402
from ir import build_ir  # noqa: E402


def main() -> int:
    doc = build_ir()
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print(f"FAILED:WFA-0127 emit sentinel missing {SENTINEL}")
        return 1
    if '"state": "SUCCESS"' not in text and '"state":"SUCCESS"' not in text:
        # pretty-printed form
        if doc.get("state") != "SUCCESS":
            print("FAILED:WFA-0127 emit state")
            return 1
    path = REPO / ARTIFACT_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {ARTIFACT_REL} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
