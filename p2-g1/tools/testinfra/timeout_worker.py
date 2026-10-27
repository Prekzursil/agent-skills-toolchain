#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sleep", type=float, default=0.0)
    p.add_argument("--label", default="worker")
    args = p.parse_args()
    time.sleep(args.sleep)
    print(f"done {args.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
