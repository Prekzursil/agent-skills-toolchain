"""Worktree isolation, pinned tree digest, and unified diffs for TST-0015.

Mutation operators rewrite files. They must never touch the shared checkout
or the committed baseline fixture. Every writable tree is a tempfile copy
marked with a sibling isolation cookie.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from difflib import unified_diff
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASELINE = HERE / "fixtures" / "baseline"
MARKER_NAME = ".tst0015-isolated"
TREE_DIRNAME = "tree"


def assert_isolated(tree: Path) -> None:
    """Refuse to mutate the shared checkout or the baseline fixture."""
    resolved = tree.resolve()
    baseline = BASELINE.resolve()
    repo = REPO.resolve()
    if resolved == baseline:
        raise RuntimeError("TST-0015 refuse: will not mutate the baseline fixture")
    if resolved == repo:
        raise RuntimeError("TST-0015 refuse: will not mutate the shared checkout")
    marker = resolved.parent / MARKER_NAME
    if not marker.is_file():
        raise RuntimeError(
            f"TST-0015 refuse: {resolved} is not a marked isolated copy"
        )
    # The isolated tree must not be inside the baseline directory.
    try:
        resolved.relative_to(baseline)
    except ValueError:
        pass
    else:
        raise RuntimeError("TST-0015 refuse: isolated tree is inside baseline")


def materialize() -> Path:
    """Copy the baseline fixture into a tempfile tree. Caller must cleanup()."""
    if not BASELINE.is_dir():
        raise FileNotFoundError(f"baseline fixture missing at {BASELINE}")
    root = Path(tempfile.mkdtemp(prefix="tst0015-"))
    (root / MARKER_NAME).write_bytes(b"isolated\n")
    dest = root / TREE_DIRNAME
    shutil.copytree(BASELINE, dest)
    assert_isolated(dest)
    return dest


def cleanup(tree: Path) -> None:
    root = tree.resolve().parent
    marker = root / MARKER_NAME
    if marker.is_file():
        shutil.rmtree(root, ignore_errors=True)


def iter_files(tree: Path) -> list[Path]:
    files = [p for p in tree.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.relative_to(tree).as_posix())
    return files


def relpaths(tree: Path) -> list[str]:
    return [p.relative_to(tree).as_posix() for p in iter_files(tree)]


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha(tree: Path) -> str:
    """Pinned SHA of a tree: sorted relpath + per-file sha256."""
    h = hashlib.sha256()
    for path in iter_files(tree):
        rel = path.relative_to(tree).as_posix().encode("utf-8")
        digest = file_digest(path).encode("ascii")
        h.update(rel)
        h.update(b"\0")
        h.update(digest)
        h.update(b"\n")
    return h.hexdigest()


def changed_relpaths(before: Path, after: Path) -> list[str]:
    a = {p: file_digest(before / p) for p in relpaths(before)}
    b = {p: file_digest(after / p) for p in relpaths(after)}
    keys = sorted(set(a) | set(b))
    return [k for k in keys if a.get(k) != b.get(k)]


def unified_file_diff(rel: str, before: bytes, after: bytes) -> str:
    try:
        old = before.decode("utf-8")
        new = after.decode("utf-8")
        text = True
    except UnicodeDecodeError:
        return (
            f"--- a/{rel}\n+++ b/{rel}\n"
            f"binary-or-undecodable bytes={len(before)}->{len(after)}\n"
        )
    diff = unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        n=3,
    )
    out = "".join(diff)
    if not out:
        # Byte change with identical universal-newline text (LF vs CRLF).
        crlf_old = before.count(b"\r\n")
        crlf_new = after.count(b"\r\n")
        out = (
            f"--- a/{rel}\n+++ b/{rel}\n"
            f"@@ bytes {len(before)} -> {len(after)}; "
            f"CRLF {crlf_old} -> {crlf_new} (text identical under universal newlines) @@\n"
        )
    return out
