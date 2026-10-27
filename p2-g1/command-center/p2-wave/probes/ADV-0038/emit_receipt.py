#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0038-revocation-propagation-to-caches.json."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness as H  # noqa: E402


def main() -> int:
    return H.main()


if __name__ == "__main__":
    raise SystemExit(main())
