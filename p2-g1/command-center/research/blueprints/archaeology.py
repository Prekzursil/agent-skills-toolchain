"""Source-code archaeology: read the committed blob via git cat-file -p.

Never git archive: on a core.autocrlf worktree that recipe returns CRLF
checkout bytes, not the LF blob CI hashes.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Any

CAT_FILE = "cat-file"
ARCHIVE = "archive"


class ForbiddenRecipeError(ValueError):
    """Raised when a caller asks archaeology to use git archive as a blob read."""


def refuse_archive_recipe(recipe: str) -> None:
    tokens = recipe.replace("/", " ").replace("-", " ").split()
    if ARCHIVE in tokens or recipe.strip() == ARCHIVE:
        raise ForbiddenRecipeError(
            f"refused blob-read recipe {recipe!r}; use git {CAT_FILE} -p <rev>:<path>"
        )


def source_uses_cat_file(src: str) -> bool:
    return CAT_FILE in src and "cat-file" in src


def source_invokes_archive(src: str) -> bool:
    """True only if source constructs a git-archive subprocess argv."""
    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "ForbiddenRecipeError" in line or "refuse_archive_recipe" in line:
            continue
        if '"git"' in line and f'"{ARCHIVE}"' in line:
            return True
    return False


def _run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "IMP-0235")
    env.setdefault("GIT_AUTHOR_EMAIL", "imp-0235@invalid")
    env.setdefault("GIT_COMMITTER_NAME", "IMP-0235")
    env.setdefault("GIT_COMMITTER_EMAIL", "imp-0235@invalid")
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        env=env,
    )
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()[:400]
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return proc


def blob_bytes(repo: Path, rev: str, path: str) -> bytes:
    """Committed bytes via git cat-file -p. Does not read the worktree."""
    rel = path.replace("\\", "/")
    proc = _run_git(repo, [CAT_FILE, "-p", f"{rev}:{rel}"])
    return proc.stdout


def worktree_bytes(repo: Path, path: str) -> bytes:
    return (repo / path).read_bytes()


def _stat(data: bytes, recipe: str) -> dict[str, Any]:
    return {
        "bytes": len(data),
        "crlf_count": data.count(b"\r\n"),
        "recipe": recipe,
        "sha256": hashlib.sha256(data).hexdigest(),
    }


CONTROL_LF = b"IMP-0235 archaeology control line-01\nline-02 blob vs crlf\n"


def plant_lf_blob_crlf_worktree(repo: Path) -> dict[str, Any]:
    """Isolated git fixture: LF blob, CRLF worktree, path=control.txt."""
    repo = Path(repo)
    repo.mkdir(parents=True, exist_ok=True)
    return _plant(repo)


def _plant(repo: Path) -> dict[str, Any]:
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    _run_git(repo, ["config", "user.email", "imp-0235@invalid"])
    _run_git(repo, ["config", "user.name", "IMP-0235"])
    _run_git(repo, ["config", "core.autocrlf", "false"])
    _run_git(repo, ["config", "core.eol", "lf"])
    (repo / ".gitattributes").write_bytes(b"* -text\n")
    rel = "control.txt"
    target = repo / rel
    target.write_bytes(CONTROL_LF)
    _run_git(repo, ["add", ".gitattributes", rel])
    _run_git(repo, ["commit", "-m", "IMP-0235 LF control blob"])
    blob = blob_bytes(repo, "HEAD", rel)
    lf = CONTROL_LF
    crlf = lf.replace(b"\n", b"\r\n")
    target.write_bytes(crlf)
    tree = worktree_bytes(repo, rel)
    blob_row = _stat(blob, "git cat-file -p")
    lf_row = _stat(lf, "planted-lf")
    tree_row = _stat(tree, "worktree")
    return {
        "blob": blob_row,
        "blob_equals_lf": blob == lf,
        "blob_equals_worktree": blob == tree,
        "lf": lf_row,
        "path": rel,
        "repo": str(repo),
        "rev": "HEAD",
        "worktree": tree_row,
        "worktree_is_crlf": tree.count(b"\r\n") >= 1 and blob.count(b"\r\n") == 0,
    }
