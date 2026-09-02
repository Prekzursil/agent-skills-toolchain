#!/usr/bin/env python3
"""Program-owned launcher: persist --payload / --path as the delivered value."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    dest = os.environ.get("ADV0118_DELIVERED")
    if not dest:
        print("ADV0118_DELIVERED unset", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser()
    p.add_argument("--payload")
    p.add_argument("--path")
    args, _rest = p.parse_known_args()
    value = args.payload if args.payload is not None else args.path
    if value is None:
        print("no --payload/--path", file=sys.stderr)
        return 2
    Path(dest).write_bytes(value.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
