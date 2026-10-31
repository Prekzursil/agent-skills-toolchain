#!/usr/bin/env python3
"""Reconstruct selected capability ids from an explanation JSON only."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: reconstruct.py <explanation.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    doc = json.loads(path.read_text(encoding="utf-8"))
    qid = str(doc.get("query_id") or path.stem)
    print(f"query_id={qid}")
    print(f"count={len(doc.get('selected') or [])}")
    for row in doc.get("selected") or []:
        print(str(row.get("capability_id") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
