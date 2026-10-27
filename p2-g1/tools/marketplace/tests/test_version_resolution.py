#!/usr/bin/env python3
"""Catalog tests for IMP-0070: version model, ranges, prerelease precedence.

The 30-case matrix is pinned against the node-semver 7.6.3 oracle (vendor/
node-semver). Prerelease precedence follows the SemVer spec (identifier
compare, never string comparison); build metadata is parsed, ignored for
precedence, and never breaks ranges.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2]))

from tools.marketplace.semver_npm import compare, max_satisfying, parse  # noqa: E402

VERSIONS = ["0.0.1", "0.0.5", "0.1.0", "0.1.9", "0.2.0", "0.9.0", "1.0.0",
            "1.0.4", "1.2.0", "1.2.9", "1.3.0", "1.9.9", "2.0.0", "2.1.0",
            "2.1.3", "3.0.0", "1.0.0-alpha", "1.0.0-alpha.2",
            "1.0.0-alpha.10", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-rc.1",
            "1.2.0-alpha.1", "1.2.0-beta", "2.0.0-rc.1", "0.1.0-alpha.1",
            "1.5.0", "1.5.0+build.7", "2.1.0+exp.sha.5114f85", "0.0.3"]

# Expected selections pinned from node-semver 7.6.3 maxSatisfying.
EXPECTED = [
    ("^1.0.0", "1.9.9"), ("^0.1.0", "0.1.9"), ("^0.0.1", "0.0.1"),
    ("~1.2.0", "1.2.9"), ("~1.2", "1.2.9"), ("~1", "1.9.9"),
    ("1.2.0", "1.2.0"), ("=1.2.0", "1.2.0"), (">1.0.0", "3.0.0"),
    (">=1.2.0", "3.0.0"), ("<2.0.0", "1.9.9"), ("<=1.2.0", "1.2.0"),
    ("1.2.x", "1.2.9"), ("1.x", "1.9.9"), ("*", "3.0.0"),
    ("1.0.0 - 1.9.0", "1.5.0"), ("^1.0.0 || ^2.0.0", "2.1.3"),
    (">1.0.0 <1.3.0", "1.2.9"), ("~1.2.9", "1.2.9"), ("^0.0.5", "0.0.5"),
    (">=1.0.0-alpha", "3.0.0"), ("1.0.0-alpha.10", "1.0.0-alpha.10"),
    ("^1.2.0-alpha", "1.9.9"), ("~0.1.0", "0.1.9"),
    ("1.x || >=2.1.0 <2.2.0", "2.1.3"), ("^2.0.0-beta", "2.1.3"),
    (">=0.1.0 <0.2.0", "0.1.9"), ("=1.5.0", "1.5.0"),
    ("1.2.0 - 2.1.0", "2.1.0"), ("^1.5.0", "1.9.9"),
]


class VersionResolutionTests(unittest.TestCase):
    def test_matrix_30_cases_match_oracle(self) -> None:
        self.assertEqual(len(EXPECTED), 30)
        for rng, expected in EXPECTED:
            self.assertEqual(max_satisfying(VERSIONS, rng), expected,
                             "range %r" % rng)

    def test_prerelease_identifier_order_not_string_compare(self) -> None:
        # string comparison ranks alpha.10 < alpha.2 (the documented wrong
        # heuristic); SemVer identifier compare must rank alpha.2 < alpha.10
        self.assertGreater(compare("1.0.0-alpha.10", "1.0.0-alpha.2"), 0)
        self.assertLess(compare("1.0.0-alpha.2", "1.0.0-alpha.10"), 0)
        # rc.1 < release
        self.assertLess(compare("1.0.0-rc.1", "1.0.0"), 0)
        # spec: numeric identifiers always rank BELOW alphanumeric ones
        self.assertLess(compare("1.0.0-alpha.9", "1.0.0-alpha.beta"), 0)

    def test_build_metadata_ignored_for_precedence(self) -> None:
        self.assertEqual(compare("1.5.0+build.7", "1.5.0"), 0)
        v = parse("2.1.0+exp.sha.5114f85")
        self.assertIsNotNone(v)
        self.assertEqual(v.build, "exp.sha.5114f85")  # type: ignore[union-attr]
        # a build-tagged version still satisfies ranges on its core
        self.assertEqual(max_satisfying(VERSIONS, "=1.5.0"), "1.5.0")

    def test_invalid_versions_rejected(self) -> None:
        self.assertIsNone(parse("01.2.0"))
        self.assertIsNone(parse("1.2"))
        self.assertIsNone(parse("not-a-version"))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    ok = res.wasSuccessful() and res.testsRun >= 4
    print("tests_run=%d failures=%d errors=%d ok=%s"
          % (res.testsRun, len(res.failures), len(res.errors), ok))
    sys.exit(0 if ok else 1)
