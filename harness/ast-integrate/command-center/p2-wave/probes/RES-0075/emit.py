#!/usr/bin/env python3
"""Emit command-center/research/RES-0075.json from the graded claim records."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import record as R  # noqa: E402
from contract import SENTINEL  # noqa: E402

OUT = REPO / "command-center/research/RES-0075.json"
FIXTURE = HERE / "fixtures" / "headline_only.json"


def main() -> int:
    doc = R.document()
    blob = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if SENTINEL not in blob:
        print("FAILED:RES-0075 emit sentinel missing")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(blob, encoding="utf-8")
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(R.HEADLINE_ONLY_FIXTURE, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={len(blob.encode('utf-8'))}")
    print(f"wrote {FIXTURE.relative_to(REPO).as_posix()}")
    print("SUCCESS:RES-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
