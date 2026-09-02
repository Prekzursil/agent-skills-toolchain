#!/usr/bin/env python3
"""Compile paths from stdin JSON under whichever interpreter launched this file."""
from __future__ import annotations

import json
import py_compile
import sys


def main() -> int:
    raw = sys.stdin.read()
    files = json.loads(raw)
    ok = 0
    failed = []
    for item in files:
        try:
            py_compile.compile(item, doraise=True)
            ok += 1
        except Exception as exc:
            failed.append({"path": item, "error": str(exc)[:240]})
    sys.stdout.write(
        json.dumps({"ok": ok, "n_failed": len(failed), "failed": failed[:24]})
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
