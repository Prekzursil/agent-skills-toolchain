#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0177.json from the live confirmer harness."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402


def main() -> int:
    return H.main()


if __name__ == "__main__":
    raise SystemExit(main())
