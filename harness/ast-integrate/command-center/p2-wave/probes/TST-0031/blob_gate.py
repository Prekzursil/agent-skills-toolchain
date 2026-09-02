#!/usr/bin/env python3
"""Blob-versus-worktree EOL parity gate (TST-0031).

Formatters and hashes MUST run against the committed git blob. Authoritative
read is `git cat-file -p <rev>:<path>` (equivalent: `git show <rev>:<path>`).

`git archive` is not a blob source: with `eol=crlf` (and on Windows export)
it returns CRLF worktree-form bytes, so a green measured through it verifies
the wrong bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

UNIT = "TST-0031"
CRLF = b"\r\n"
AUTHORITATIVE_RECIPE = "git cat-file -p <rev>:<path>"
EQUIVALENT_RECIPE = "git show <rev>:<path>"
BANNED_BLOB_SOURCE = "git archive | tar -x"


class GateError(RuntimeError):
    """Blob read or gate evaluation failed."""


def run_git(repo: Path, args: list[str], *, binary: bool = True) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise GateError(f"git {' '.join(args)} rc={proc.returncode}: {err}")
    return proc.stdout if binary else proc.stdout


def read_blob(repo: Path, rev: str, rel: str) -> bytes:
    """Return committed blob bytes. Never uses git archive or the worktree."""
    spec = f"{rev}:{rel.replace(chr(92), '/')}"
    return run_git(repo, ["cat-file", "-p", spec], binary=True)


def read_show(repo: Path, rev: str, rel: str) -> bytes:
    spec = f"{rev}:{rel.replace(chr(92), '/')}"
    return run_git(repo, ["show", spec], binary=True)


def read_archive(repo: Path, rev: str, rel: str) -> bytes:
    """Export-converted bytes. Evidence only — the gate must not hash these."""
    rel = rel.replace("\\", "/")
    with tempfile.TemporaryDirectory(prefix="tst0031-archive-") as td:
        tarp = Path(td) / "a.tar"
        run_git(repo, ["archive", "-o", str(tarp), rev, "--", rel], binary=True)
        with tarfile.open(tarp, "r") as tf:
            member = tf.getmember(rel)
            fh = tf.extractfile(member)
            if fh is None:
                return b""
            return fh.read()


def worktree_bytes(repo: Path, rel: str) -> bytes | None:
    path = repo / rel
    if not path.is_file():
        return None
    return path.read_bytes()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_norm(data: bytes) -> bytes:
    return data.replace(CRLF, b"\n")


def format_ok_text_blob(blob: bytes) -> bool:
    """Canonical text blob is LF-only. Applied to BLOB bytes, never worktree."""
    return CRLF not in blob


def three_route(repo: Path, rev: str, rel: str) -> dict[str, Any]:
    cat = read_blob(repo, rev, rel)
    show = read_show(repo, rev, rel)
    arch = read_archive(repo, rev, rel)
    routes = {
        "git archive | tar -x": arch,
        "git cat-file -p": cat,
        "git show <rev>:<path>": show,
    }
    norms = [lf_norm(v) for v in routes.values()]
    return {
        "target": rel,
        "rev": rev,
        "recipe_used_by_gate": AUTHORITATIVE_RECIPE,
        "routes": {
            name: {
                "bytes": len(raw),
                "crlf": raw.count(CRLF),
                "sha256": sha256_hex(raw),
            }
            for name, raw in routes.items()
        },
        "cat_file_equals_show": cat == show,
        "archive_differs_from_blob": arch != cat,
        "identical_after_lf_normalisation": bool(norms[0])
        and all(n == norms[0] for n in norms),
    }


def evaluate(repo: Path, rev: str, rel: str) -> dict[str, Any]:
    blob = read_blob(repo, rev, rel)
    wt = worktree_bytes(repo, rel)
    blob_sha = sha256_hex(blob)
    wt_sha = sha256_hex(wt) if wt is not None else None
    fmt = format_ok_text_blob(blob)
    return {
        "path": rel,
        "rev": rev,
        "recipe": AUTHORITATIVE_RECIPE,
        "banned_recipe": BANNED_BLOB_SOURCE,
        "blob_bytes": len(blob),
        "blob_crlf": blob.count(CRLF),
        "blob_sha256": blob_sha,
        "worktree_bytes": None if wt is None else len(wt),
        "worktree_crlf": None if wt is None else wt.count(CRLF),
        "worktree_sha256": wt_sha,
        "hash_matches_worktree": wt is not None and wt_sha == blob_sha,
        "format_ok": fmt,
        "format_applied_to": "blob",
        "verdict": "PASS" if fmt else "FAIL",
    }


def init_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    for key, val in (
        ("user.email", "tst-0031@local"),
        ("user.name", "TST-0031"),
        ("core.autocrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "config", key, val], cwd=str(root), check=True
        )
    return root


def commit_bytes(repo: Path, rel: str, data: bytes, message: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    subprocess.run(["git", "add", "--", rel], cwd=str(repo), check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m", message],
        cwd=str(repo),
        check=True,
    )


def eol_divergence_fixture(root: Path) -> dict[str, Any]:
    """LF blob + eol=crlf attrs so archive returns CRLF; dirty worktree CRLF."""
    repo = init_repo(root)
    rel = "sample.txt"
    lf = (b"alpha\nbeta\n" * 50)
    commit_bytes(repo, rel, lf, "lf-blob")
    commit_bytes(
        repo,
        ".gitattributes",
        b"sample.txt text eol=crlf\n",
        "export-eol-crlf",
    )
    crlf = lf_norm(lf).replace(b"\n", CRLF)
    (repo / rel).write_bytes(crlf)
    table = three_route(repo, "HEAD", rel)
    gate = evaluate(repo, "HEAD", rel)
    return {
        "repo": str(repo),
        "path": rel,
        "lf_bytes": len(lf),
        "crlf_worktree_bytes": len(crlf),
        "three_route": table,
        "gate": gate,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TST-0031 blob hash/format gate")
    p.add_argument("--repo", required=True)
    p.add_argument("--rev", default="HEAD")
    p.add_argument("--path", required=True)
    p.add_argument("--three-route", action="store_true")
    ns = p.parse_args(argv)
    repo = Path(ns.repo).resolve()
    if ns.three_route:
        doc = three_route(repo, ns.rev, ns.path)
    else:
        doc = evaluate(repo, ns.rev, ns.path)
    print(json.dumps(doc, indent=1, sort_keys=True))
    if not ns.three_route and doc.get("verdict") != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
