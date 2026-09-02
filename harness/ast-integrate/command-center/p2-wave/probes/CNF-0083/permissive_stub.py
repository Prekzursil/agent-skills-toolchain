#!/usr/bin/env python3
"""Permissive stub: accepts every workflow, including known-broken fixtures.

Detector control: if production validate_workflow.py behaved like this stub,
probe1 would go green while invalid definitions were silently accepted.
probe2 asserts production rejects the known-broken fixture and this stub
accepts it, so the detector is live rather than tautological.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    path = args[0] if args else ""
    print(
        json.dumps(
            {
                "ok": True,
                "path": path,
                "violation_id": None,
                "violations": [],
                "stub": "permissive-always-ok",
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
