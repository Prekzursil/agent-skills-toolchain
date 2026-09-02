#!/usr/bin/env python3
"""Emit command-center/research/RES-0116.json."""
from __future__ import annotations

import json
from pathlib import Path

from quotes import discards_not_promoted, quotes_ok, sentinel_ok
from register import SENTINEL, build

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/research/RES-0116.json"
OUT = REPO / OUT_REL


def main() -> int:
    doc = build()
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ok, why = sentinel_ok(doc, text)
    if not ok:
        print(f"FAILED:RES-0116-emit sentinel {why}")
        return 1
    ok, why = quotes_ok(doc)
    if not ok:
        print(f"FAILED:RES-0116-emit quotes {why}")
        return 1
    ok, why = discards_not_promoted(doc)
    if not ok:
        print(f"FAILED:RES-0116-emit discards {why}")
        return 1
    if SENTINEL not in text:
        print("FAILED:RES-0116-emit sentinel-absent")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={OUT.stat().st_size} state={doc['state']}")
    print("SUCCESS:RES-0116-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
