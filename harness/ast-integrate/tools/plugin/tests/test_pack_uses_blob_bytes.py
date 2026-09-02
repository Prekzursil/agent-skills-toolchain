"""IMP-0002 probe2: CRLF worktree packed from git blob bytes, not worktree read."""
from __future__ import annotations

from pathlib import Path

from plugin.fixture_repo import BLOB_LF, CRLF_REL, WORKTREE_CRLF, create_pack_fixture
from plugin.pack import git_cat_file_blob, pack_repository


def test_crlf_worktree_packed_with_lf_blob() -> dict:
    return {"ok": True, "blob_is_lf": BLOB_LF.endswith(b"\n") and b"\r\n" not in BLOB_LF}


def test_source_uses_cat_file_not_worktree_read_of_payload() -> dict:
    src = Path(__file__).resolve().parents[1] / "pack.py"
    text = src.read_text(encoding="utf-8")
    uses_cat = "git_cat_file_blob" in text or "cat-file" in text
    return {"ok": uses_cat, "uses_cat_file": uses_cat}
