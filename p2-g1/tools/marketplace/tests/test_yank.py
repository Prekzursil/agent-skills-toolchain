#!/usr/bin/env python3
"""Catalog tests for IMP-0070 yank semantics.

A yanked version stays resolvable from an existing lockfile pin but is
never selected for a fresh install of the same range - yanking cannot
break the reproducibility of past builds.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))

from tools.marketplace.yank import PackageRelease, resolve_from_lockfile, resolve_fresh_install  # noqa: E402

RELEASES = [
    PackageRelease("1.0.0"),
    PackageRelease("1.1.0"),
    PackageRelease("1.2.0", yanked=True),
    PackageRelease("1.2.9"),
]


class YankTests(unittest.TestCase):
    # required test: yanked version still resolvable from a lockfile pin
    def test_yanked_version_still_resolvable_from_a_lockfile(self) -> None:
        self.assertEqual(resolve_from_lockfile("1.2.0", RELEASES), "1.2.0")
        self.assertEqual(resolve_from_lockfile("1.1.0", RELEASES), "1.1.0")

    def test_lockfile_pin_missing_is_none(self) -> None:
        self.assertIsNone(resolve_from_lockfile("9.9.9", RELEASES))

    # NEGATIVE CONTROL: yanked must NOT be selected for a fresh install
    def test_yanked_not_selected_for_fresh_install(self) -> None:
        self.assertNotEqual(resolve_fresh_install("^1.0.0", RELEASES), "1.2.0")
        self.assertEqual(resolve_fresh_install("^1.2.0", RELEASES), "1.2.9")
        self.assertEqual(resolve_fresh_install("=1.2.0", RELEASES), None)

    def test_all_yanked_fresh_install_is_none(self) -> None:
        only_yanked = [PackageRelease("1.0.0", yanked=True)]
        self.assertIsNone(resolve_fresh_install("*", only_yanked))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    ok = res.wasSuccessful() and res.testsRun >= 3
    print("tests_run=%d failures=%d errors=%d ok=%s"
          % (res.testsRun, len(res.failures), len(res.errors), ok))
    sys.exit(0 if ok else 1)
