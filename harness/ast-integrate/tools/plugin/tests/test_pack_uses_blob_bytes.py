"""IMP-0002 probe2: CRLF worktree packed from git blob bytes, not worktree read.

The fixture commits an LF payload file and then rewrites the *worktree* copy
with CRLF line endings.  A packer that reads the worktree would ship CRLF
bytes; one that reads ``git cat-file`` ships the committed LF blob.
"""
from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

from plugin.fixture_repo import BLOB_LF, CRLF_REL, WORKTREE_CRLF, create_pack_fixture
from plugin.pack import git_cat_file_blob, pack_repository


def _packed_member(archive: Path, rel: str) -> bytes | None:
    """Bytes of the archive member named ``rel`` (tolerating a single leading dir)."""
    with tarfile.open(archive, "r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            if name == rel or name.endswith("/" + rel):
                fh = tf.extractfile(member)
                return fh.read() if fh is not None else None
    return None


def test_crlf_worktree_packed_with_lf_blob() -> dict:
    """Pack a CRLF-worktree fixture and prove the shipped bytes are the LF blob."""
    with tempfile.TemporaryDirectory(prefix="imp0002-crlf-") as tmp:
        root = Path(tmp)
        repo = create_pack_fixture(root, crlf_worktree=True)
        worktree = (repo / CRLF_REL).read_bytes()
        blob = git_cat_file_blob(repo, CRLF_REL)
        out = root / "crlf-build.tar.gz"
        result = pack_repository(repo, out, allowlist_path=root / "payload-allowlist.json")
        packed = _packed_member(out, CRLF_REL)

    fixture_ok = worktree == WORKTREE_CRLF and blob == BLOB_LF and worktree != blob
    packed_equals_blob = packed == blob
    packed_equals_worktree = packed == worktree
    ok = bool(result.ok) and fixture_ok and packed_equals_blob and not packed_equals_worktree
    info = {
        "ok": ok,
        "member": CRLF_REL,
        "member_found": packed is not None,
        "fixture_ok": fixture_ok,
        "blob_is_lf": BLOB_LF.endswith(b"\n") and b"\r\n" not in BLOB_LF,
        "worktree_has_crlf": b"\r\n" in worktree,
        "packed_equals_blob": packed_equals_blob,
        "packed_equals_worktree": packed_equals_worktree,
        "pack_ok": bool(result.ok),
    }
    if not ok:
        raise AssertionError(f"packed bytes did not come from the git blob: {info}")
    return info


def test_source_uses_cat_file_not_worktree_read_of_payload() -> dict:
    """The packer's payload byte source must be ``git cat-file``, not a worktree read."""
    src = Path(__file__).resolve().parents[1] / "pack.py"
    text = src.read_text(encoding="utf-8")
    uses_cat = "git_cat_file_blob(" in text and "cat-file" in text
    info = {"ok": uses_cat, "uses_cat_file": uses_cat}
    if not uses_cat:
        raise AssertionError(f"pack.py does not read payload bytes via git cat-file: {info}")
    return info
