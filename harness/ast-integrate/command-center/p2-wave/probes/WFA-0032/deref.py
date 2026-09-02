"""Dual-route dereference: filesystem path vs git loose blob.

Route B writes and reads git *loose objects* directly (zlib + 'blob <n>\\0').
That is not `git add` / `git commit`. `git cat-file blob` is an optional
cross-check that the bytes are real git objects.
"""
from __future__ import annotations

import hashlib
import subprocess
import zlib
from pathlib import Path
from typing import Any

NL = "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_store_bytes(data: bytes) -> bytes:
    return f"blob {len(data)}\0".encode("ascii") + data


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(git_blob_store_bytes(data)).hexdigest()


def write_loose_blob(git_dir: Path, data: bytes) -> str:
    store = git_blob_store_bytes(data)
    sha = hashlib.sha1(store).hexdigest()
    dest = git_dir / "objects" / sha[:2] / sha[2:]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(zlib.compress(store))
    return sha


def read_loose_blob(git_dir: Path, sha: str) -> bytes:
    dest = git_dir / "objects" / sha[:2] / sha[2:]
    if not dest.is_file():
        raise FileNotFoundError(f"missing git loose object {sha}")
    raw = zlib.decompress(dest.read_bytes())
    header, payload = raw.split(b"\0", 1)
    kind, _, size_s = header.partition(b" ")
    if kind != b"blob":
        raise ValueError(f"object {sha} is {kind!r}, not blob")
    if int(size_s) != len(payload):
        raise ValueError(f"object {sha} size mismatch")
    return payload


def git_cat_file_blob(git_dir: Path, sha: str) -> tuple[bool, bytes, str]:
    try:
        p = subprocess.run(
            ["git", "--git-dir", str(git_dir), "cat-file", "blob", sha],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, b"", f"{type(exc).__name__}: {exc}"
    if p.returncode != 0:
        err = (p.stderr or b"").decode("utf-8", "replace").strip()
        return False, b"", err or f"git-cat-file-exit-{p.returncode}"
    return True, p.stdout, ""


def line_at(text: str, line_no: int) -> str:
    lines = text.split(NL)
    if line_no < 1 or line_no > len(lines):
        raise IndexError(f"line {line_no} out of range 1..{len(lines)}")
    return lines[line_no - 1]


def deref_filesystem(path: Path, line_no: int) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "route": "filesystem",
        "ok": False,
        "path": str(path),
        "line": line_no,
    }
    try:
        data = path.read_bytes()
    except OSError as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["failing_route"] = "filesystem"
        return rec
    text = data.decode("utf-8")
    rec["file_sha256"] = sha256_bytes(data)
    rec["bytes"] = len(data)
    try:
        payload = line_at(text, line_no)
    except IndexError as exc:
        rec["error"] = str(exc)
        rec["failing_route"] = "filesystem"
        return rec
    rec["ok"] = True
    rec["line_text"] = payload
    rec["line_sha256"] = sha256_bytes(payload.encode("utf-8"))
    return rec


def deref_git_blob(git_dir: Path, sha: str, line_no: int) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "route": "git-blob",
        "ok": False,
        "git_blob_sha1": sha,
        "line": line_no,
        "git_dir": str(git_dir),
    }
    if not sha:
        rec["error"] = "no-git-blob-sha1"
        rec["failing_route"] = "git-blob"
        return rec
    try:
        data = read_loose_blob(git_dir, sha)
    except (OSError, ValueError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["failing_route"] = "git-blob"
        return rec
    git_ok, git_bytes, git_err = git_cat_file_blob(git_dir, sha)
    rec["git_cat_file_ok"] = git_ok
    rec["git_cat_file_agrees"] = bool(git_ok and git_bytes == data)
    if git_ok and git_bytes != data:
        rec["error"] = "git-cat-file-disagrees-with-loose-object-reader"
        rec["failing_route"] = "git-blob"
        return rec
    if not git_ok:
        rec["git_cat_file_error"] = git_err
    text = data.decode("utf-8")
    rec["file_sha256"] = sha256_bytes(data)
    rec["bytes"] = len(data)
    try:
        payload = line_at(text, line_no)
    except IndexError as exc:
        rec["error"] = str(exc)
        rec["failing_route"] = "git-blob"
        return rec
    rec["ok"] = True
    rec["line_text"] = payload
    rec["line_sha256"] = sha256_bytes(payload.encode("utf-8"))
    return rec


def combine_routes(fs: dict[str, Any], git: dict[str, Any]) -> dict[str, Any]:
    failing: list[str] = []
    if not fs.get("ok"):
        failing.append("filesystem")
    if not git.get("ok"):
        failing.append("git-blob")
    agree = False
    if fs.get("ok") and git.get("ok"):
        agree = (
            fs.get("line_sha256") == git.get("line_sha256")
            and fs.get("file_sha256") == git.get("file_sha256")
        )
        if not agree:
            failing.append("hash-mismatch")
    status = "RESOLVED" if (fs.get("ok") and git.get("ok") and agree) else "UNRESOLVED"
    return {
        "status": status,
        "failing_route": None if not failing else "+".join(failing),
        "routes_agree": agree,
        "content_sha256": fs.get("file_sha256") or git.get("file_sha256"),
        "line_sha256": fs.get("line_sha256") or git.get("line_sha256"),
        "filesystem": {
            k: v
            for k, v in fs.items()
            if k not in {"line_text"}
        },
        "git_blob": {
            k: v
            for k, v in git.items()
            if k not in {"line_text"}
        },
        "line_text": (fs.get("line_text") if fs.get("ok") else git.get("line_text")),
    }
