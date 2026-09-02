"""Control suite for AUD-0054: decorator gates vs a runtime-only skip.

Probe 1 (AST of skip/skipif decorators) must see windows-only and posix-only
and must miss test_runtime_only_skip. Probe 2 (collect vs execute) must see
the runtime-only skip as collected-but-not-executed. If both probes list that
node as decorator-gated, they are not independent.
"""
from __future__ import annotations

import sys
import unittest


class PlatformGates(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("win"), "windows-only")
    def test_windows_only(self) -> None:
        self.assertTrue(sys.platform.startswith("win"))

    @unittest.skipIf(sys.platform.startswith("win"), "posix-only")
    def test_posix_only(self) -> None:
        self.assertFalse(sys.platform.startswith("win"))

    def test_runtime_only_skip(self) -> None:
        raise unittest.SkipTest("runtime-only skip; no decorator")

    def test_always_runs(self) -> None:
        self.assertTrue(True)

    @unittest.skip("unconditional; not a platform gate")
    def test_unconditional_skip(self) -> None:
        self.fail("must not run")
