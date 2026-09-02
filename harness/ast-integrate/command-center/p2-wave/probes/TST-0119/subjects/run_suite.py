#!/usr/bin/env python3
"""Run subject tests inside an isolated (or live) subject tree."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tests import TestDetector, TestHelper, TestPredicate, TestPredicateWeak  # noqa: E402

CLASSES = {
    "completion_predicate": TestPredicate,
    "detector": TestDetector,
    "helper_util": TestHelper,
    "TestPredicateWeak": TestPredicateWeak,
}


def build_suite(target: str) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    if target in ("all", "", None):
        for cls in (TestPredicate, TestDetector, TestHelper):
            suite.addTests(loader.loadTestsFromTestCase(cls))
        return suite
    cls = CLASSES.get(target)
    if cls is None:
        raise SystemExit(f"unknown suite {target!r}")
    suite.addTests(loader.loadTestsFromTestCase(cls))
    return suite


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    result = unittest.TextTestRunner(verbosity=1).run(build_suite(target))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
