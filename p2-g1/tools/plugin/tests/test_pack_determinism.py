"""Determinism unit tests imported by IMP-0002 probe1."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from plugin.fixture_repo import create_pack_fixture
from plugin.pack import pack_repository, sha256_file


def test_two_builds_identical() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0002-unit-") as tmp:
        root = Path(tmp)
        repo = create_pack_fixture(root)
        allow = root / "payload-allowlist.json"
        a = root / "a.tar"
        b = root / "b.tar"
        r1 = pack_repository(repo, a, allowlist_path=allow)
        r2 = pack_repository(repo, b, allowlist_path=allow)
        h1, h2 = sha256_file(a), sha256_file(b)
        if h1 != h2:
            raise AssertionError(f"builds diverged {h1} {h2}")
        return {"sha256": h1, "members": list(r1.members), "ok": True}


def test_real_mtimes_breaks_determinism() -> dict:
    """Negative control: packing worktree bytes with real mtimes in ustar header diverges.

    The production packer hashes blob contents, not mtimes. This control uses
    os.utime between naive tarfile.add of the worktree to prove the detector
    can see divergence when mtimes leak.
    """
    import tarfile

    with tempfile.TemporaryDirectory(prefix="imp0002-mtime-") as tmp:
        root = Path(tmp)
        repo = create_pack_fixture(root)
        src = repo / "payload" / "notes.txt"
        a = root / "naive1.tar"
        b = root / "naive2.tar"

        def naive(dest: Path) -> None:
            with tarfile.open(dest, "w") as tf:
                tf.add(src, arcname="payload/notes.txt")

        naive(a)
        os.utime(src, (1_700_000_000, 1_700_000_000))
        naive(b)
        h1, h2 = sha256_file(a), sha256_file(b)
        return {"diverged": h1 != h2, "h1": h1, "h2": h2}
