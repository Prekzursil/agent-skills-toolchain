"""File-package lockfile: per-file blob hashes, source commit, resolution order.

Byte identity is taken from `git cat-file -p <rev>:<path>`, never from
`git archive` (export conversion emits CRLF when `text eol=crlf` is set)
and never from the working tree.
"""
from __future__ import annotations

import hashlib
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from unicodedata import normalize

from fixture import GIT_ENV, git

BYTE_SOURCE = "git cat-file -p <source_commit>:<path>"
FORBIDDEN_BYTE_SOURCES = ("git archive", "working-tree")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def nfc_posix(path: str) -> str:
    return normalize("NFC", path.replace("\\", "/"))


def cat_file_bytes(repo: Path, rev: str, path: str) -> bytes:
    proc = git(repo, "cat-file", "-p", f"{rev}:{path}")
    return proc.stdout


def git_blob_sha1(repo: Path, rev: str, path: str) -> str:
    proc = git(repo, "rev-parse", f"{rev}:{path}")
    return proc.stdout.decode("ascii").strip()


def git_mode(repo: Path, rev: str, path: str) -> str:
    proc = git(repo, "ls-tree", rev, "--", path)
    line = proc.stdout.decode("utf-8", "replace").strip()
    if not line:
        raise RuntimeError(f"ls-tree empty for {path}")
    return line.split()[0]


def archive_file_bytes(repo: Path, rev: str, path: str) -> bytes:
    """Windows-trap route: git archive applies working-tree EOL conversion."""
    with tempfile.TemporaryDirectory(prefix="res0052-archive-") as td:
        tarp = Path(td) / "a.tar"
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "core.autocrlf=false",
                "archive",
                "-o",
                str(tarp),
                rev,
                "--",
                path,
            ],
            env=GIT_ENV,
            capture_output=True,
            check=True,
        )
        with tarfile.open(tarp) as tf:
            names = tf.getnames()
            for candidate in (path, "./" + path, path.replace("/", "\\")):
                if candidate in names:
                    fh = tf.extractfile(candidate)
                    if fh is None:
                        raise RuntimeError(f"archive member empty: {candidate}")
                    return fh.read()
            raise RuntimeError(f"archive missing {path}; members={names}")


def tracked_paths(repo: Path, rev: str) -> list[str]:
    proc = git(repo, "ls-tree", "-r", "--name-only", rev)
    paths = [
        nfc_posix(line)
        for line in proc.stdout.decode("utf-8").splitlines()
        if line.strip()
    ]
    return sorted(paths)


def build_lockfile(repo: Path, rev: str, name: str, version: str) -> dict[str, Any]:
    order = tracked_paths(repo, rev)
    files: list[dict[str, Any]] = []
    for path in order:
        blob = cat_file_bytes(repo, rev, path)
        files.append(
            {
                "path": path,
                "git_blob_sha1": git_blob_sha1(repo, rev, path),
                "mode": git_mode(repo, rev, path),
                "size": len(blob),
                "sha256": sha256_hex(blob),
                "crlf_in_blob": blob.count(b"\r\n"),
            }
        )
    return {
        "lockfileVersion": 1,
        "kind": "file-package",
        "package": {"name": name, "version": version},
        "source_commit": rev,
        "hash_algorithm": "sha256",
        "byte_source": BYTE_SOURCE,
        "forbidden_byte_sources": list(FORBIDDEN_BYTE_SOURCES),
        "resolution_order": order,
        "files": files,
    }


def install_from_lockfile(lock: dict[str, Any], repo: Path, dest: Path) -> dict[str, Any]:
    """Write exact cat-file bytes in lockfile resolution order."""
    dest.mkdir(parents=True, exist_ok=True)
    rev = lock["source_commit"]
    written: list[dict[str, Any]] = []
    for entry in lock["files"]:
        path = entry["path"]
        blob = cat_file_bytes(repo, rev, path)
        digest = sha256_hex(blob)
        if digest != entry["sha256"]:
            raise RuntimeError(f"install hash mismatch {path}: {digest} != {entry['sha256']}")
        if len(blob) != entry["size"]:
            raise RuntimeError(f"install size mismatch {path}")
        out = dest / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        written.append(
            {
                "path": path,
                "sha256": digest,
                "size": len(blob),
            }
        )
    return {"dest": str(dest), "files": written}


def tree_hashes(dest: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        rel = nfc_posix(str(path.relative_to(dest)))
        out[rel] = sha256_hex(path.read_bytes())
    return out


def compare_install(lock: dict[str, Any], dest: Path) -> dict[str, Any]:
    """Known-good: every lockfile path hashes to the recorded blob sha256.

    Known-broken (mutation): at least one path disagrees.
    """
    matches: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for entry in lock["files"]:
        path = entry["path"]
        live = dest / path
        row: dict[str, Any] = {
            "path": path,
            "expected_sha256": entry["sha256"],
            "expected_size": entry["size"],
        }
        if not live.is_file():
            row.update({"present": False, "live_sha256": None, "live_size": None})
            mismatches.append(row)
            continue
        data = live.read_bytes()
        live_sha = sha256_hex(data)
        row.update(
            {
                "present": True,
                "live_sha256": live_sha,
                "live_size": len(data),
            }
        )
        if live_sha == entry["sha256"] and len(data) == entry["size"]:
            matches.append(row)
        else:
            mismatches.append(row)
    extra = sorted(set(tree_hashes(dest)) - {e["path"] for e in lock["files"]})
    return {
        "match": not mismatches and not extra,
        "match_count": len(matches),
        "mismatch_count": len(mismatches),
        "matches": matches,
        "mismatches": mismatches,
        "extra_paths": extra,
    }


def three_route(repo: Path, rev: str, path: str) -> dict[str, Any]:
    cat = cat_file_bytes(repo, rev, path)
    show = git(repo, "show", f"{rev}:{path}").stdout
    arch = archive_file_bytes(repo, rev, path)
    wt_path = repo / path
    worktree = wt_path.read_bytes() if wt_path.is_file() else b""
    return {
        "path": path,
        "routes": {
            "git cat-file -p": {
                "bytes": len(cat),
                "crlf": cat.count(b"\r\n"),
                "sha256": sha256_hex(cat),
            },
            "git show <rev>:<path>": {
                "bytes": len(show),
                "crlf": show.count(b"\r\n"),
                "sha256": sha256_hex(show),
            },
            "git archive": {
                "bytes": len(arch),
                "crlf": arch.count(b"\r\n"),
                "sha256": sha256_hex(arch),
            },
            "working-tree": {
                "bytes": len(worktree),
                "crlf": worktree.count(b"\r\n"),
                "sha256": sha256_hex(worktree) if worktree else None,
            },
        },
        "cat_file_equals_show": cat == show,
        "archive_differs_from_blob": arch != cat,
        "archive_has_crlf": b"\r\n" in arch,
        "blob_has_crlf": b"\r\n" in cat,
    }
