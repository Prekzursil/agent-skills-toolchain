#!/usr/bin/env python3
"""Fake `gh` (and generic argv sink) for ADV-0118 far-end capture."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    dest = os.environ.get("ADV0118_CAPTURE")
    if not dest:
        print("ADV0118_CAPTURE unset", file=sys.stderr)
        return 2
    argv = sys.argv[1:]
    body = None
    title = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--body", "-b") and i + 1 < len(argv):
            body = argv[i + 1]
            i += 2
            continue
        if a in ("--title", "-t") and i + 1 < len(argv):
            title = argv[i + 1]
            i += 2
            continue
        i += 1
    Path(dest).write_text(
        json.dumps(
            {"argv": argv, "body": body, "title": title, "prog": sys.argv[0]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
