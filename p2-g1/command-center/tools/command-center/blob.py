"""Hash command-center provenance from the committed blob, not the worktree.

IMP-0439. `core.autocrlf` rewrites LF blobs to CRLF on a Windows checkout, so a
sha256 of working-tree bytes disagrees with Linux CI for the same commit. The
recipe here is `git cat-file -p <rev>:<path>` (never an archive). `git show` is
the independent re-derive used by the reviewer probe.

Fallback: LF-normalised working-tree bytes when the path is not a blob (tmp
fixtures, untracked files). That keeps REACH-6 tests that hand validate() a
throwaway REGISTER.md working, and is the only honest answer on a worktree
that is not a git repository.

IMP-0440 owns `tools/measure-guard/blobread.py`. This module does not call it.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

# Must stay equal to render.CONTRACTED_ARTIFACTS (probe 1 asserts the pair).
# Kept here rather than imported so this module cannot cycle through render.py
# -> validate.py -> blob.py.
MANIFEST_FILENAMES: tuple[str, ...] = (
    "PROGRAM-CHARTER.md",
    "OWNER-DECISIONS.md",
    "WORK-UNIT-CATALOG.json",
    "DEPENDENCY-GRAPH.json",
    "ARTIFACT-MANIFEST.json",
    "CLAIM-REGISTRY.json",
    "TEST-REGISTRY.json",
    "RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md",
    "RELEASE-CHECKLIST.md",
    "ROLLBACK-MANIFEST.md",
    "RUNBOOK.md",
    "STATUS.md",
    "events/EVENTS.jsonl",
)

DEFAULT_REV = "HEAD"


class BlobError(RuntimeError):
    """Path is not readable as a blob at the given revision."""


def _git_env(home: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env.pop("GIT_INDEX_FILE", None)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if home is not None:
        env["HOME"] = str(home)
        env["GIT_AUTHOR_NAME"] = "IMP-0439"
        env["GIT_AUTHOR_EMAIL"] = "imp-0439@invalid"
        env["GIT_COMMITTER_NAME"] = "IMP-0439"
        env["GIT_COMMITTER_EMAIL"] = "imp-0439@invalid"
    return env


def _posix(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _run_git(
    repo: Path,
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = 20,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        timeout=timeout,
        env=env if env is not None else _git_env(),
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_normalised(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


lf_normalise = lf_normalised


def working_tree_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()


def git_toplevel(start: Path) -> Path | None:
    """Containing worktree, or None when git cannot answer."""
    start = Path(start)
    if not start.exists():
        return None
    cwd = start if start.is_dir() else start.parent
    try:
        proc = _run_git(cwd, ["rev-parse", "--show-toplevel"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or b"").decode("utf-8", "replace").strip()
    return Path(text) if text else None


def blob_bytes(repo: Path, path: str, rev: str = DEFAULT_REV) -> bytes:
    """Committed bytes of `path` at `rev` via `git cat-file -p`."""
    spec = f"{rev}:{_posix(path)}"
    proc = _run_git(repo, ["cat-file", "-p", spec])
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:200]
        raise BlobError(f"{path!r} is not a blob at {rev!r}: {err}")
    return proc.stdout


def show_bytes(repo: Path, path: str, rev: str = DEFAULT_REV) -> bytes:
    """Independent re-derive: `git show <rev>:<path>`, not cat-file."""
    spec = f"{rev}:{_posix(path)}"
    proc = _run_git(repo, ["show", spec])
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()[:200]
        raise BlobError(f"{path!r} is not show-able at {rev!r}: {err}")
    return proc.stdout


def provenance_bytes(path: Path, repo: Path | None = None) -> bytes:
    """Blob bytes when the path is tracked; else LF-normalised worktree bytes."""
    path = Path(path)
    root = Path(repo).resolve() if repo is not None else git_toplevel(path)
    if root is not None:
        try:
            rel = path.resolve().relative_to(root).as_posix()
            return blob_bytes(root, rel)
        except (ValueError, BlobError, OSError):
            pass
    return lf_normalised(working_tree_bytes(path))


def _fixture_body(name: str) -> bytes:
    return f"# {name}\nfixture body for {name}\nline three\n".encode("utf-8")


def init_manifest_fixture(tmp: Path) -> Path:
    """LF-committed git repo holding all fourteen contracted artifacts."""
    repo = Path(tmp)
    repo.mkdir(parents=True, exist_ok=True)
    cc = repo / "command-center"
    (cc / "events").mkdir(parents=True, exist_ok=True)
    for name in MANIFEST_FILENAMES:
        target = cc / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_fixture_body(name))
    env = _git_env(home=repo)
    steps = (
        ["-c", "init.defaultBranch=main", "init"],
        ["-c", "core.autocrlf=false", "add", "-A"],
        [
            "-c",
            "core.autocrlf=false",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "IMP-0439 fixture",
        ],
    )
    for args in steps:
        proc = _run_git(repo, args, env=env)
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "replace")
            raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return repo


def materialise_crlf_worktree(repo: Path, paths: list[str]) -> int:
    """Rewrite listed files to CRLF without touching the index or blob."""
    n = 0
    for rel in paths:
        path = Path(repo) / rel
        lf = lf_normalised(path.read_bytes())
        crlf = lf.replace(b"\n", b"\r\n")
        path.write_bytes(crlf)
        if b"\r\n" in crlf:
            n += 1
    return n


def parity_experiment(tmp: Path) -> dict:
    """Fourteen-row table: blob identical across CRLF/LF; worktree differs."""
    repo = init_manifest_fixture(tmp)
    rels = [f"command-center/{name}" for name in MANIFEST_FILENAMES]
    lf_blob: dict[str, str] = {}
    for rel in rels:
        lf_blob[rel] = sha256_hex(blob_bytes(repo, rel))

    n_crlf = materialise_crlf_worktree(repo, rels)

    rows = []
    blob_identical = True
    wt_differs = True
    blob_eq_recorded = True
    for rel in rels:
        path = repo / rel
        raw_wt = working_tree_bytes(path)
        blob = blob_bytes(repo, rel)
        recorded = provenance_bytes(path, repo=repo)
        blob_hex = sha256_hex(blob)
        rec_hex = sha256_hex(recorded)
        wt_hex = sha256_hex(raw_wt)
        if blob_hex != lf_blob[rel]:
            blob_identical = False
        if wt_hex == blob_hex:
            wt_differs = False
        if blob_hex != rec_hex:
            blob_eq_recorded = False
        rows.append(
            {
                "path": rel,
                "present_on_disk": path.is_file(),
                "working_tree_bytes": len(raw_wt),
                "working_tree_sha256": wt_hex,
                "blob_bytes": len(blob),
                "blob_sha256": blob_hex,
                "recorded_provenance_sha256": rec_hex,
                "blob_equals_recorded": blob_hex == rec_hex,
                "working_tree_equals_blob": wt_hex == blob_hex,
                "blob_error": None,
            }
        )

    samples = {
        rels[0]: {
            "git_show": sha256_hex(show_bytes(repo, rels[0])),
            "git_cat_file": sha256_hex(blob_bytes(repo, rels[0])),
        },
        rels[2]: {
            "git_show": sha256_hex(show_bytes(repo, rels[2])),
            "git_cat_file": sha256_hex(blob_bytes(repo, rels[2])),
        },
    }
    show_matches = all(
        pair["git_show"] == pair["git_cat_file"] for pair in samples.values()
    )
    return {
        "n_entries": len(rows),
        "n_crlf_rewritten": n_crlf,
        "blob_route_identical_crlf_vs_lf": blob_identical,
        "blob_equals_recorded_for_all_14": blob_eq_recorded,
        "working_tree_route_differs_for_all_14": wt_differs,
        "independent_git_show_matches_cat_file": show_matches,
        "independent_samples": samples,
        "rows": rows,
    }
