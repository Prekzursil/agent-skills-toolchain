"""IMP-0439 — provenance hash reads the committed blob, not the working tree.

Platform-parity: on a throwaway repo that commits LF then materialises CRLF in
the working tree, the blob route yields identical digests whether you read via
``provenance_bytes`` / ``blob_hash`` or via raw ``git cat-file``. The working-tree
RAW route DIFFERS — proving the fix changed something and is not a no-op.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import render  # noqa: E402

LF_BODY = b"alpha\nbeta\ngamma\n"
CRLF_BODY = b"alpha\r\nbeta\r\ngamma\r\n"


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _repo_with_crlf_checkout(tmp_path: Path) -> tuple[Path, Path]:
    """Commit LF under command-center/, then rewrite the worktree as CRLF."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    cc = root / "command-center"
    cc.mkdir()
    target = cc / "PROGRAM-CHARTER.md"
    target.write_bytes(LF_BODY)
    _git(root, "add", "command-center/PROGRAM-CHARTER.md")
    _git(root, "commit", "-q", "-m", "lf")
    # Materialise CRLF in the working tree (Windows autocrlf shape).
    target.write_bytes(CRLF_BODY)
    return root, cc


def test_blob_route_identical_on_crlf_and_lf_checkout(tmp_path: Path) -> None:
    root, cc = _repo_with_crlf_checkout(tmp_path)
    # CRLF worktree view
    crlf_prov = render.provenance_bytes(cc, "PROGRAM-CHARTER.md")
    crlf_blob = render.blob_hash(cc, "PROGRAM-CHARTER.md")
    # Reset to LF worktree view
    (cc / "PROGRAM-CHARTER.md").write_bytes(LF_BODY)
    lf_prov = render.provenance_bytes(cc, "PROGRAM-CHARTER.md")
    lf_blob = render.blob_hash(cc, "PROGRAM-CHARTER.md")

    assert crlf_prov == LF_BODY
    assert lf_prov == LF_BODY
    assert hashlib.sha256(crlf_prov).hexdigest() == hashlib.sha256(lf_prov).hexdigest()
    assert crlf_blob == lf_blob
    assert crlf_blob == hashlib.sha256(LF_BODY).hexdigest()


def test_working_tree_raw_route_differs_from_blob_on_crlf(tmp_path: Path) -> None:
    """Control: raw working-tree hash DIFFERS from blob on a CRLF checkout."""
    _root, cc = _repo_with_crlf_checkout(tmp_path)
    wt_raw = render.working_tree_raw_hash(cc, "PROGRAM-CHARTER.md")
    blob = render.blob_hash(cc, "PROGRAM-CHARTER.md")
    recorded = hashlib.sha256(
        render.provenance_bytes(cc, "PROGRAM-CHARTER.md")
    ).hexdigest()
    assert blob == recorded
    assert wt_raw != blob, (
        "working-tree raw hash must differ from blob on CRLF checkout — "
        "otherwise the platform-parity control is silent in both states"
    )


def test_render_manifest_records_blob_digest_not_crlf(tmp_path: Path) -> None:
    _root, cc = _repo_with_crlf_checkout(tmp_path)
    # Seed the other contracted paths as absent so render_manifest only hashes ours.
    manifest = render.render_manifest(cc)
    entry = next(
        a for a in manifest["artifacts"] if a["path"].endswith("PROGRAM-CHARTER.md")
    )
    assert entry["present"] is True
    assert entry["sha256"] == hashlib.sha256(LF_BODY).hexdigest()
    assert entry["bytes"] == len(LF_BODY)


def test_dirty_derived_file_falls_back_to_lf_worktree(tmp_path: Path) -> None:
    """Just-written content that differs from HEAD must hash LF worktree, not stale blob."""
    root, cc = _repo_with_crlf_checkout(tmp_path)
    new = b"fresh-derived\ncontent\n"
    (cc / "PROGRAM-CHARTER.md").write_bytes(new)
    got = render.provenance_bytes(cc, "PROGRAM-CHARTER.md")
    assert got == new
    assert got != LF_BODY
