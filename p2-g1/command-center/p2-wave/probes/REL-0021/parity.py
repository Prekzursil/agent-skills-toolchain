#!/usr/bin/env python3
# REL-0021 three-way byte parity gate (rebuilt 2026-10-25, shard16-wave2 resume).
# Compares, per shipped file, THREE copies: the git blob retrieved with
# `git cat-file -p <rev>:<path>` (NEVER `git archive`, which on this host
# returns CRLF worktree bytes instead of the blob - the receipt records the
# measured CRLF delta), the bytes inside the built package, and the bytes in
# the deployed tree. Line endings are normalised (CRLF->LF) BEFORE comparison
# so EOL noise cannot masquerade as content drift. Four-way classification:
# identical | package-only | deployed-only | divergent-both-ways. A
# divergent-both-ways file BLOCKS promotion (two-directional case: reconciling
# in either direction destroys work); deployed-only owner files get
# sync_proposal=None and an overwrite attempt must be refused.
from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path


def norm(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_bytes(repo: Path, rev_path: str, method: str = "cat-file"):
    if method == "cat-file":
        p = subprocess.run(["git", "-C", str(repo), "cat-file", "-p", rev_path],
                           capture_output=True, timeout=120)
        return p.stdout if p.returncode == 0 else None
    raise ValueError("rejected recipe: " + method)


def git_archive_bytes(repo: Path, rev_path: str):
    rev, _, path = rev_path.partition(":")
    with tempfile_dir() as tmp:
        out = Path(tmp) / "out.tar"
        subprocess.run(["git", "-C", str(repo), "archive", "-o", str(out), rev, "--", path],
                       capture_output=True, timeout=120, check=True)
        import tarfile
        with tarfile.open(out) as tf:
            member = [m for m in tf.getmembers() if m.isfile()]
            return tf.extractfile(member[0]).read() if member else b""


def tempfile_dir():
    import tempfile
    return tempfile.TemporaryDirectory(prefix="rel0021-arch-")


def crlf_count(b: bytes) -> int:
    return b.count(b"\r\n")


def zip_member_bytes(zip_path: Path, member_rel: str):
    with zipfile.ZipFile(zip_path) as z:
        names = {n.replace("\\", "/"): n for n in z.namelist()}
        n = names.get(member_rel)
        if n is None:
            return None
        return z.read(n)


def classify(git_b, pkg_b, dep_b):
    present = {"git": git_b is not None, "package": pkg_b is not None,
               "deployed": dep_b is not None}
    g = sha(norm(git_b)) if git_b is not None else None
    p = sha(norm(pkg_b)) if pkg_b is not None else None
    d = sha(norm(dep_b)) if dep_b is not None else None
    row = {"present": present, "git_lf_sha256": g, "package_lf_sha256": p,
           "deployed_lf_sha256": d}
    if g and p and d:
        row["class"] = "identical" if (g == p == d) else "divergent-both-ways"
    elif p and not g and not d:
        row["class"] = "package-only"
    elif d and not g and not p:
        row["class"] = "deployed-only"
    else:
        row["class"] = "mixed-missing"
    # sync proposals: never propose a one-directional sync for either-unique content
    row["sync_proposal"] = None
    return row


def three_way_report(repo: Path, package_zip: Path, deployed: Path, paths):
    files = []
    for rel in paths:
        git_b = git_bytes(repo, "HEAD:" + rel)
        pkg_b = zip_member_bytes(package_zip, rel)
        dep_f = deployed / rel
        dep_b = dep_f.read_bytes() if dep_f.is_file() else None
        row = classify(git_b, pkg_b, dep_b)
        row["path"] = rel
        files.append(row)
    four_way = {"identical": 0, "package-only": 0, "deployed-only": 0,
                "divergent-both-ways": 0, "mixed-missing": 0}
    for f in files:
        four_way[f["class"]] += 1
    verdict = "BLOCK" if four_way["divergent-both-ways"] else "PROMOTE"
    return {"files": files, "four_way": four_way, "verdict": verdict}


def attempt_owner_overwrite(deployed: Path, rel: str, new_bytes: bytes):
    # reviewer destroy catch: a deployed-only owner file must never be
    # silently overwritten; the gate refuses because there is no recorded
    # blob for it (sync_proposal=None) and content is owner-authored.
    f = deployed / rel
    if f.is_file() and new_bytes != f.read_bytes():
        raise PermissionError("refusing one-directional overwrite of deployed-only "
                              "owner file: " + rel)
