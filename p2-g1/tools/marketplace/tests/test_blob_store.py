"""IMP-0121: content-addressed blob store behaviours (stdlib runner)."""
import shutil
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from blob_store import BlobStore, CorruptedBlobError, ReferencedBlobError  # noqa: E402


def _fresh():
    root = Path(tempfile.mkdtemp(prefix="testblob-"))
    return root, BlobStore(root)


def test_dedupe_and_refcount():
    root, store = _fresh()
    try:
        d1 = store.put(b"same", ref="collection:core")
        d2 = store.put(b"same", ref="version:1.0.0")
        assert d1 == d2
        assert store.refcount(d1) == 2
        files = list((root / "objects").iterdir())
        assert len(files) == 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_corrupted_object_is_detected_on_read():
    root, store = _fresh()
    try:
        d = store.put(b"payload", ref="r1")
        obj = root / "objects" / d
        obj.write_bytes(b"payload-TAMPER")
        try:
            store.get(d)
        except CorruptedBlobError:
            return
        raise AssertionError("corruption not detected")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_delete_referenced_is_refused():
    root, store = _fresh()
    try:
        d = store.put(b"payload", ref="r1")
        store.put(b"payload", ref="r2")
        try:
            store.delete(d)
        except ReferencedBlobError:
            return
        raise AssertionError("referenced delete not refused")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS:" + name)
            except Exception as exc:
                failed += 1
                print("FAIL:" + name + " " + str(exc))
    print("SUCCESS:test_blob_store" if not failed else "FAILED:test_blob_store")
    sys.exit(1 if failed else 0)
