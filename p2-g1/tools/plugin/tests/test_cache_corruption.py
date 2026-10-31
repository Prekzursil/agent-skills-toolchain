#!/usr/bin/env python3
"""Catalog tests for IMP-0041 cache refresh, invalidation, and quarantine.

Covers: truncated, zero-byte, wrong-hash, partially written entries are
quarantined; an intact entry is NOT quarantined in the same run (negative
control); atomic write is tmp-plus-rename; a write interrupted mid-stream
leaves no readable partial entry; the consumer is served source-equal bytes
after rebuild.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "plugin-cache-reaper"))

import cache as cache_mod  # noqa: E402
from cache import PAYLOAD_NAME, PluginCache, sha256_hex  # noqa: E402

SOURCE_A = b"payload-alpha\nline2\nline3\n"
SOURCE_B = b"payload-beta-kept\nline2\n"


class CacheCorruptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cache = PluginCache(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed(self) -> str:
        return self.cache.put("broke", "1.0.0", SOURCE_A)

    def _corrupt_broken(self, mutate) -> None:
        key = self._seed()
        self.cache.put("keep", "1.0.0", SOURCE_B)
        mutate(self.cache.entry_dir(key) / PAYLOAD_NAME)

    # 1: truncated in place -> quarantined AND rebuilt
    def test_truncated_entry_quarantined_and_rebuilt(self) -> None:
        def trunc(p: Path) -> None:
            with open(p, "r+b") as fh:
                fh.truncate(5)
        self._corrupt_broken(trunc)
        report = self.cache.refresh()
        self.assertEqual([r["plugin_id"] for r in report.quarantined], ["broke"])
        self.assertEqual([r["plugin_id"] for r in report.rebuilt], ["broke"])
        # consumer served source-equal bytes
        self.assertEqual(sha256_hex(self.cache.get("broke", "1.0.0")),
                         sha256_hex(SOURCE_A))

    # 2: zero-byte payload -> quarantined
    def test_zero_byte_entry_quarantined(self) -> None:
        self._corrupt_broken(lambda p: p.write_bytes(b""))
        report = self.cache.refresh()
        self.assertEqual([r["plugin_id"] for r in report.quarantined], ["broke"])

    # 3: wrong-hash payload -> quarantined
    def test_wrong_hash_entry_quarantined(self) -> None:
        self._corrupt_broken(lambda p: p.write_bytes(b"tampered-content\n"))
        report = self.cache.refresh()
        self.assertEqual([r["plugin_id"] for r in report.quarantined], ["broke"])

    # 4: partially written payload (prefix of the stream) -> quarantined
    def test_partially_written_entry_quarantined(self) -> None:
        def partial(p: Path) -> None:
            p.write_bytes(SOURCE_A[: len(SOURCE_A) // 2])
        self._corrupt_broken(partial)
        report = self.cache.refresh()
        self.assertEqual([r["plugin_id"] for r in report.quarantined], ["broke"])
        self.assertNotIn("keep", [r["plugin_id"] for r in report.quarantined])

    # 5: NEGATIVE CONTROL - intact sibling never quarantined in the same run
    def test_intact_entry_not_quarantined_same_run(self) -> None:
        def trunc(p: Path) -> None:
            with open(p, "r+b") as fh:
                fh.truncate(5)
        self._corrupt_broken(trunc)
        report = self.cache.refresh()
        self.assertEqual([r["plugin_id"] for r in report.intact], ["keep"])
        listing = self.cache.quarantine_listing()
        self.assertEqual(len(listing), 1)
        self.assertIn("broke@1.0.0", listing[0])
        self.assertNotIn("keep@1.0.0", listing[0])

    # 6: atomic write contract is tmp sibling + os.replace, not in-place
    def test_atomic_write_contract_tmp_plus_rename(self) -> None:
        verdict = cache_mod.assert_atomic_write_contract(Path(cache_mod.__file__))
        self.assertTrue(verdict["ok"], verdict)
        self.assertTrue(verdict["uses_tmp"], verdict)
        self.assertTrue(verdict["uses_replace"], verdict)

    # 7: a write interrupted mid-stream leaves no readable partial entry
    def test_interrupted_write_leaves_no_partial_entry(self) -> None:
        real_replace = cache_mod.os.replace

        def boom(src, dst):  # noqa: ANN001
            raise RuntimeError("simulated crash mid-write")

        self.cache.put("keep", "1.0.0", SOURCE_B)
        cache_mod.os.replace = boom
        try:
            with self.assertRaises(RuntimeError):
                self.cache.put("crash", "1.0.0", SOURCE_A)
        finally:
            cache_mod.os.replace = real_replace
        entry = self.cache.entry_dir("crash@1.0.0")
        self.assertFalse((entry / PAYLOAD_NAME).is_file())
        # the crashed write must not serve partial bytes through get()
        with self.assertRaises(FileNotFoundError):
            self.cache.get("crash", "1.0.0")
        # a pre-existing intact entry survives the crashed write untouched
        self.assertEqual(self.cache.get("keep", "1.0.0"), SOURCE_B)

    # 8: rebuild serves source-equal bytes through the consumer path
    def test_rebuild_serves_source_bytes(self) -> None:
        def trunc(p: Path) -> None:
            with open(p, "r+b") as fh:
                fh.truncate(1)
        self._corrupt_broken(trunc)
        self.cache.refresh()
        served = self.cache.get("broke", "1.0.0")
        self.assertEqual(served, SOURCE_A)
        self.assertEqual(sha256_hex(served), sha256_hex(SOURCE_A))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=1)
    tests = runner.run(suite)
    ok = tests.wasSuccessful() and tests.testsRun == 8
    print(f"tests_run={tests.testsRun} failures={len(tests.failures)} "
          f"errors={len(tests.errors)} ok={ok}")
    sys.exit(0 if ok else 1)
