#!/usr/bin/env python3
"""Emit the CNL-0038 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import analyze  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0038-executable-runtime-semantics-for-the-6-deliberative-protoc.md"


def main() -> int:
    body = analyze.note_body()
    if body.get("state") != "SUCCESS" or body.get("sentinel") != "SUCCESS:CNL-0038":
        print("FAILED:CNL-0038 emit refused non-success body")
        return 1
    if not body.get("family", {}).get("counts_agree"):
        print("FAILED:CNL-0038 emit family count disagreement")
        return 1
    if body.get("not_executable_ids") != ["P01"]:
        print("FAILED:CNL-0038 emit unexpected NOT-EXECUTABLE set", body.get("not_executable_ids"))
        return 1
    if not body.get("both_states", {}).get("pass"):
        print("FAILED:CNL-0038 emit both-states failed")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:CNL-0038")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
