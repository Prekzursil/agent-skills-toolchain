"""Catalog tests for IMP-0125 blob GC. Callable as functions and as a script."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MKT = HERE.parent
if str(MKT) not in sys.path:
    sys.path.insert(0, str(MKT))

from blob_gc import collect  # noqa: E402
from gc_store import (  # noqa: E402
    append_deploy_record,
    list_blob_hexes,
    put_blob,
    set_owner_token,
    write_index,
    write_lockfile,
)


def test_referenced_blob_is_never_collected() -> None:
    with tempfile.TemporaryDirectory(prefix="test-gc-ref-") as tmp:
        root = Path(tmp)
        set_owner_token(root, "t")
        indexed = put_blob(root, b"indexed-keep")
        orphan = put_blob(root, b"orphan-drop")
        write_index(root, [{"name": "k", "version": "1", "digest": "sha256:" + indexed}])
        report = collect(root, execute=True, owner_token="t")
        remaining = set(list_blob_hexes(root))
        assert indexed in remaining
        assert orphan not in remaining
        assert "sha256:" + indexed not in report["deleted"]


def test_dry_run_lists_every_candidate_with_its_proof() -> None:
    with tempfile.TemporaryDirectory(prefix="test-gc-dry-") as tmp:
        root = Path(tmp)
        set_owner_token(root, "t")
        orphan = put_blob(root, b"orphan-dry")
        indexed = put_blob(root, b"idx-dry")
        write_index(root, [{"name": "k", "version": "1", "digest": "sha256:" + indexed}])
        before = set(list_blob_hexes(root))
        dry = collect(root, execute=False)
        assert dry["mode"] == "dry-run"
        assert dry["deleted"] == []
        cand = {c["digest_hex"] for c in dry["candidates"]}
        assert cand == {orphan}
        proof = dry["candidates"][0]["proof"]
        assert proof["index_lockfile"]["zero"] is True
        assert proof["provenance"]["zero"] is True
        assert proof["index_lockfile"]["examined"] is True
        assert set(list_blob_hexes(root)) == before


def test_lockfile_only_reference_survives() -> None:
    with tempfile.TemporaryDirectory(prefix="test-gc-lock-") as tmp:
        root = Path(tmp)
        set_owner_token(root, "t")
        locked = put_blob(root, b"lock-only")
        orphan = put_blob(root, b"orphan-lock")
        write_index(root, [])
        write_lockfile(
            root,
            "x.lock.json",
            [{"name": "locked", "version": "1", "blob_digest": "sha256:" + locked}],
        )
        collect(root, execute=True, owner_token="t")
        remaining = set(list_blob_hexes(root))
        assert locked in remaining
        assert orphan not in remaining


def main() -> int:
    test_referenced_blob_is_never_collected()
    test_dry_run_lists_every_candidate_with_its_proof()
    test_lockfile_only_reference_survives()
    print("SUCCESS:test_gc")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
