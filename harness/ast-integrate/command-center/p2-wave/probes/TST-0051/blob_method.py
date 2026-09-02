"""Blob readings: git cat-file -p is the blob; git archive is contrast only.

This delivery worktree has no .git. The method is proved on a throwaway lab
repo, matching the RELEASE-CHECKLIST trap (archive must not be the blob).
"""
from __future__ import annotations

import hashlib
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

CRLF = b"\r\n"
TARGET = "notes/sample.md"


def _describe(raw: bytes) -> dict[str, Any]:
    lf = raw.replace(CRLF, b"\n")
    return {
        "bytes": len(raw),
        "crlf": raw.count(CRLF),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "sha256_lf_norm": hashlib.sha256(lf).hexdigest(),
    }


def _git(args: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True)
    return r.returncode, r.stdout, r.stderr


def worktree_git_attempt(repo: Path) -> dict[str, Any]:
    readings = {}
    for args, label in (
        (["rev-parse", "--is-inside-work-tree"], "rev-parse"),
        (["cat-file", "-p", "HEAD:command-center/WORK-UNIT-CATALOG.json"], "git cat-file -p"),
        (["archive", "HEAD", "--", "command-center/WORK-UNIT-CATALOG.json"], "git archive"),
    ):
        rc, out, err = _git(args, repo)
        readings[label] = {
            "rc": rc,
            "stdout_bytes": len(out),
            "stderr_head": err.decode("utf-8", "replace")[:240],
        }
    return {
        "is_git_repo": (repo / ".git").exists(),
        "readings": readings,
        "note": "Worktree has no .git; blob method is proved on a throwaway lab repo.",
    }


def lab_blob_method() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tst0051-blob-") as tmp:
        repo = Path(tmp) / "blob-lab"
        repo.mkdir()
        (repo / "notes").mkdir()
        lf = b"alpha\nbeta\nomega\n"
        (repo / TARGET).write_bytes(lf)
        cmds = [
            ["git", "init", "-b", "main"],
            ["git", "config", "user.email", "tst0051@local"],
            ["git", "config", "user.name", "TST-0051"],
            ["git", "config", "core.autocrlf", "false"],
            ["git", "add", TARGET],
            ["git", "commit", "-m", "lf-blob"],
        ]
        for args in cmds:
            r = subprocess.run(args, cwd=str(repo), capture_output=True)
            if r.returncode != 0:
                return {
                    "ok": False,
                    "failed_cmd": args,
                    "stderr": (r.stderr or b"").decode("utf-8", "replace")[:400],
                    "method": "git cat-file -p on a throwaway lab repo",
                    "never_git_archive_for_blob": True,
                    "readings": {},
                    "archive_equals_blob": False,
                    "working_tree_crlf_shown": False,
                }
        rc_cat, cat, err_cat = _git(["cat-file", "-p", f"HEAD:{TARGET}"], repo)
        tarp = repo / "a.tar"
        rc_arch, _, err_arch = _git(["archive", "-o", str(tarp), "HEAD", "--", TARGET], repo)
        arch = b""
        if rc_arch == 0 and tarp.is_file():
            with tarfile.open(tarp) as tf:
                member = tf.getmember(TARGET)
                fh = tf.extractfile(member)
                arch = fh.read() if fh else b""
        (repo / TARGET).write_bytes(lf.replace(b"\n", CRLF))
        working_crlf = (repo / TARGET).read_bytes()
        return {
            "ok": True,
            "target": TARGET,
            "method": (
                "git cat-file -p on a throwaway lab repo; git archive recorded "
                "only as the contrast reading, never as the blob"
            ),
            "never_git_archive_for_blob": True,
            "readings": {
                "git cat-file -p": {
                    **_describe(cat),
                    "rc": rc_cat,
                    "stderr_head": err_cat.decode("utf-8", "replace")[:160],
                },
                "git archive": {
                    **_describe(arch),
                    "rc": rc_arch,
                    "stderr_head": err_arch.decode("utf-8", "replace")[:160],
                },
                "working-tree after CRLF rewrite": _describe(working_crlf),
            },
            "archive_equals_blob": arch == cat and bool(cat),
            "working_tree_crlf_shown": working_crlf.count(CRLF) > 0,
            "working_tree_differs_from_blob": working_crlf != cat,
        }
