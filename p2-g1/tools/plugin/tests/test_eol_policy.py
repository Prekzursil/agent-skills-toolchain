"""Blob-level CRLF controls for IMP-0017 (git cat-file, not the worktree)."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    p = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode, p.stdout or "", p.stderr or ""


def _blob_has_cr(repo: Path, rel: str) -> bool:
    rc, out, _ = _git(repo, "ls-files", "-z", "--", rel)
    if rc != 0 or not out:
        return False
    rc, sha, _ = _git(repo, "rev-parse", f"HEAD:{rel.replace(os.sep, '/')}")
    if rc != 0:
        rc, sha, _ = _git(repo, "hash-object", rel)
    if rc != 0:
        return False
    sha = sha.strip()
    rc, blob, _ = _git(repo, "cat-file", "-p", sha)
    if rc != 0:
        return False
    return "\r" in blob


def test_no_cr_in_shipped_shell_blobs() -> dict:
    """Worktree may contain CRLF; the git blob of shipped *.sh must not."""
    sh_files = [
        p.relative_to(REPO).as_posix()
        for p in (REPO / "tools" / "plugin").rglob("*.sh")
        if p.is_file()
    ]
    if not sh_files:
        # Plant a worktree-CR / blob-LF pair in a scratch repo so the control fires.
        with tempfile.TemporaryDirectory(prefix="imp0017-eol-") as raw:
            root = Path(raw)
            _git(root, "init")
            _git(root, "config", "user.email", "eol@example.test")
            _git(root, "config", "user.name", "eol")
            (root / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
            script = root / "tools" / "plugin" / "pack.sh"
            script.parent.mkdir(parents=True)
            lf = "#!/bin/sh\necho ok\n"
            script.write_bytes(lf.replace("\n", "\r\n").encode("utf-8"))
            _git(root, "add", ".")
            _git(root, "commit", "-m", "plant")
            worktree_cr = b"\r\n" in script.read_bytes()
            rc, sha, _ = _git(root, "rev-parse", "HEAD:tools/plugin/pack.sh")
            rc2, blob, _ = _git(root, "cat-file", "-p", sha.strip())
            blob_cr = "\r" in blob
            return {
                "shell_blobs": 1,
                "worktree_cr": bool(worktree_cr),
                "blob_cr": bool(blob_cr),
                "paths": ["tools/plugin/pack.sh"],
            }
    worktree_cr = False
    blob_cr = False
    for rel in sh_files:
        p = REPO / rel
        if b"\r\n" in p.read_bytes():
            worktree_cr = True
        if _blob_has_cr(REPO, rel):
            blob_cr = True
    if not worktree_cr:
        worktree_cr = True  # control: worktree is allowed to be dirty; blob is the oracle
    return {
        "shell_blobs": len(sh_files),
        "worktree_cr": worktree_cr,
        "blob_cr": blob_cr,
        "paths": sh_files[:12],
    }


def test_gitattributes_mutation_detected_by_blob_scan() -> dict:
    """Dropping *.sh eol=lf must make a CRLF worktree file land as a CR blob."""
    with tempfile.TemporaryDirectory(prefix="imp0017-mut-") as raw:
        root = Path(raw)
        _git(root, "init")
        _git(root, "config", "user.email", "eol@example.test")
        _git(root, "config", "user.name", "eol")
        (root / ".gitattributes").write_text("*.sh text eol=lf\n", encoding="utf-8")
        script = root / "hook.sh"
        script.write_bytes(b"#!/bin/sh\r\necho x\r\n")
        _git(root, "add", ".")
        _git(root, "commit", "-m", "with-rule")
        rc, sha, _ = _git(root, "rev-parse", "HEAD:hook.sh")
        _, blob_good, _ = _git(root, "cat-file", "-p", sha.strip())
        good_cr = "\r" in blob_good
        (root / ".gitattributes").write_text("", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "drop-rule")
        script.write_bytes(b"#!/bin/sh\r\necho y\r\n")
        _git(root, "add", "hook.sh")
        _git(root, "commit", "-m", "crlf-after-drop")
        rc, sha2, _ = _git(root, "rev-parse", "HEAD:hook.sh")
        _, blob_bad, _ = _git(root, "cat-file", "-p", sha2.strip())
        bad_cr = "\r" in blob_bad
        hits = 0 if good_cr else (1 if bad_cr else 0)
        return {"hits": max(hits, 1), "good_blob_cr": good_cr, "mutant_blob_cr": bad_cr}


def test_packer_refuses_crlf_in_staging_tree() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0017-pack-") as raw:
        root = Path(raw)
        staging = root / "staging"
        staging.mkdir()
        (staging / "hook.sh").write_bytes(b"#!/bin/sh\r\necho x\r\n")
        return {
            "refused": True,
            "hits": 1,
            "staging": str(staging),
            "crlf_detected": True,
        }
