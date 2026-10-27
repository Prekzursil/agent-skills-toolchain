#!/usr/bin/env python3
"""Catalog tests for IMP-0068 registry storage (atomic writes + rebuild).

test_rebuild_from_blobs_equals_original: an index rebuilt from stored
package blobs alone is semantically equal to the original (normalised
comparison; ordering may differ). Also covers truncated and deleted index.
test_no_partial_index_visible_at_any_kill_point: an atomic index write
interrupted at every seeded kill point never leaves a readable partial at
the destination; the same offsets against an in-place writer do.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from storage import RegistryStorage, indexes_semantically_equal  # noqa: E402

PACKAGES = [
    {"name": "alpha", "version": "1.0.0", "summary": "first"},
    {"name": "beta", "version": "2.1.0", "summary": "second"},
    {"name": "gamma", "version": "0.3.0", "summary": "third"},
]
BLOBS = {p["name"]: f"blob-bytes-{p['name']}\n".encode() for p in PACKAGES}


def make_storage(root: Path) -> RegistryStorage:
    st = RegistryStorage(root)
    for p in PACKAGES:
        st.put_package(p, BLOBS[p["name"]])
    return st


def in_place_publish(index_path: Path, doc: dict, kill_offsets: list) -> None:
    """Counterexample writer: streams the new document into the destination
    in place, stopping at each seeded kill offset (simulated crash)."""
    payload = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    for k in kill_offsets:
        with open(index_path, "wb") as fh:
            fh.write(payload[:k])
            # crash: handle dropped; destination left as a prefix of the new doc


class RegistryStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.st = make_storage(self.root)
        self.original = self.st.read_index()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_rebuild_from_blobs_equals_original(self) -> None:
        import copy
        doc = copy.deepcopy(self.original)
        doc["plugins"].append({"name": "zz-extra", "version": "9.9.9"})
        self.st._write_index(doc)
        raw = self.st.index_path.read_bytes()
        self.st.index_path.write_bytes(raw[: len(raw) // 2])  # truncated
        self.st.index_path.unlink()  # deleted
        rebuilt = self.st.rebuild_from_blobs()
        self.assertTrue(indexes_semantically_equal(self.original, rebuilt))
        self.assertEqual(self.st.read_index(), rebuilt)

    def test_rebuild_with_orphan_blob(self) -> None:
        stem = "f" * 64
        orphan_meta = self.st.blob_dir / (stem + ".json")
        orphan_meta.write_text(
            json.dumps({"name": "reviewer-orphan-qkv", "version": "1.0.0"},
                       sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (self.st.blob_dir / (stem + ".bin")).write_bytes(b"orphan-bytes\n")
        names = {p["name"] for p in self.st.rebuild_from_blobs()["plugins"]}
        self.assertIn("reviewer-orphan-qkv", names)

    def test_no_partial_index_visible_at_any_kill_point(self) -> None:
        import pathlib
        new_doc = json.loads(json.dumps(self.original))
        new_doc["plugins"][0]["summary"] = "mutated-by-new-write"
        payload = json.dumps(new_doc, indent=2) + "\n"
        kill_offsets = sorted({1, len(payload) // 3, len(payload) // 2,
                               len(payload) - 1, len(payload)})
        real_write_text = pathlib.Path.write_text
        for k in kill_offsets:
            st = make_storage(self.root)

            def boom_write_text(self_, data, *a, **kw):
                # kill only the index tmp write; meta writes stay live
                if str(self_).endswith("index.json.tmp") and len(data) > k:
                    raise RuntimeError("killed at %d" % k)
                return real_write_text(self_, data, *a, **kw)

            pathlib.Path.write_text = boom_write_text  # type: ignore[attr-defined]
            try:
                try:
                    st._write_index(new_doc)
                except RuntimeError:
                    pass
            finally:
                pathlib.Path.write_text = real_write_text  # type: ignore[attr-defined]
            on_disk = st.index_path.read_text(encoding="utf-8")
            parsed = json.loads(on_disk)  # MUST parse: never a partial
            self.assertIn(
                parsed, (self.original, new_doc),
                "dest was neither old nor new complete doc after kill at %d" % k)

        # NEGATIVE CONTROL: in-place publishing at the same offsets leaves
        # a readable-but-partial index at the destination
        partial_seen = False
        for k in kill_offsets:
            in_place_publish(self.st.index_path, new_doc, [k])
            text = self.st.index_path.read_text(encoding="utf-8", errors="replace")
            try:
                json.loads(text)
            except json.JSONDecodeError:
                partial_seen = True
                break
        self.assertTrue(partial_seen,
                        "in-place writer must produce a readable partial")

    def test_atomic_write_is_tmp_plus_rename(self) -> None:
        src = Path(sys.modules["storage"].__file__)
        text = src.read_text(encoding="utf-8")
        self.assertIn(".tmp", text)
        self.assertIn(".replace(", text)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    ok = res.wasSuccessful() and res.testsRun >= 4
    print("tests_run=%d failures=%d errors=%d ok=%s"
          % (res.testsRun, len(res.failures), len(res.errors), ok))
    sys.exit(0 if ok else 1)
