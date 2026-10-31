#!/usr/bin/env python3
"""Run the CRCP W1 contract suite using only the Python standard library."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


def main() -> int:
    # scripts/ → tools/crcp; put package parent + package dir on path for flat imports
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "crcp"))
    suite = unittest.defaultTestLoader.discover(
        str(root / "tests"), pattern="test_*.py"
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
