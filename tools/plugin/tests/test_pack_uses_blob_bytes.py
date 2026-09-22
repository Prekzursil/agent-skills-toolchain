"""IMP-0002: CRLF working-tree file is packed with LF git blob bytes."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

PACK = Path(__file__).resolve().parents[1] / "pack.py"
sys.path.insert(0, str(PACK.parent))
import pack as pack_mod  # noqa: E402


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def test_crlf_worktree_packed_with_lf_blob(tmp_path: Path) -> None:
    repo = tmp_path / "payload"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "imp0002@test.invalid")
    _git(repo, "config", "user.name", "IMP-0002")
    # Commit LF bytes (the blob).
    text_path = repo / "README.md"
    text_path.write_bytes(b"line1\nline2\n")
    (repo / "LICENSE").write_bytes(b"MIT\n")
    allow = {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [
            {"glob": "README.md", "reason": "docs"},
            {"glob": "LICENSE", "reason": "license"},
        ],
        "budget": {"max_bytes": 10000, "max_files": 10},
        "forbidden_classes": {"vcs": [".git", ".git/*"]},
    }
    (repo / "payload-allowlist.json").write_text(
        json.dumps(allow, indent=2) + "\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "lf-blob")

    # Worktree rewritten with CRLF (simulates Windows checkout / git archive trap).
    text_path.write_bytes(b"line1\r\nline2\r\n")
    assert b"\r\n" in text_path.read_bytes()

    blob = pack_mod.git_cat_file(repo, "HEAD", "README.md")
    assert blob == b"line1\nline2\n"
    assert b"\r\n" not in blob

    out = tmp_path / "out.zip"
    result = pack_mod.pack(
        repo=repo,
        rev="HEAD",
        allowlist=repo / "payload-allowlist.json",
        out=out,
    )
    with zipfile.ZipFile(out) as zf:
        packed = zf.read("README.md")
    assert packed == blob
    assert packed == b"line1\nline2\n"
    assert b"\r\n" not in packed
    assert result.sha256
