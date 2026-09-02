"""git cat-file -p resolver plus an isolated fixture object store.

The worktree under test is not a git repository. Live documentation
therefore cannot be verified at a revision. Detector controls still
exercise the real `git cat-file -p <rev>:<path>` command against a
throwaway fixture repo so the meter is not a regex on the anchor shape.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_LINES = 20
GOOD_LINE = 10
OFF_BY_1000 = GOOD_LINE + 1000
TARGET_REL = "target.txt"


def _run_git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=False,
        timeout=20,
        env=env,
    )


def git_identity_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    env["GIT_AUTHOR_NAME"] = "TST-0255"
    env["GIT_AUTHOR_EMAIL"] = "tst-0255@invalid"
    env["GIT_COMMITTER_NAME"] = "TST-0255"
    env["GIT_COMMITTER_EMAIL"] = "tst-0255@invalid"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def cat_file(cwd: Path, rev: str, path: str) -> dict:
    spec = f"{rev}:{path}"
    cmd = ["git", "-C", str(cwd), "cat-file", "-p", spec]
    proc = subprocess.run(cmd, capture_output=True, timeout=20)
    stdout = proc.stdout or b""
    stderr = (proc.stderr or b"").decode("utf-8", "replace")
    return {
        "command": " ".join(cmd),
        "spec": spec,
        "returncode": int(proc.returncode),
        "stdout_bytes": stdout,
        "stderr": stderr[-500:],
    }


def line_count(blob: bytes) -> int:
    if not blob:
        return 0
    return len(blob.replace(b"\r\n", b"\n").decode("utf-8", "replace").splitlines())


def blob_line(blob: bytes, line: int) -> str | None:
    lines = blob.replace(b"\r\n", b"\n").decode("utf-8", "replace").splitlines()
    if line < 1 or line > len(lines):
        return None
    return lines[line - 1]


def worktree_stat(repo: Path, path: str, line: int) -> dict:
    p = repo / path
    if not p.is_file():
        return {"exists": False, "line_count": 0, "in_range": False}
    n = line_count(p.read_bytes())
    return {"exists": True, "line_count": n, "in_range": 1 <= line <= n}


def classify_cat_file(cat: dict, line: int) -> str:
    if cat["returncode"] != 0:
        err = (cat.get("stderr") or "").lower()
        if "not a git repository" in err:
            return "NO-GIT"
        return "MISSING"
    n = line_count(cat["stdout_bytes"])
    if line < 1 or line > n:
        return "BEYOND-EOF"
    return "OK"


def resolve_internal(cwd: Path, rev: str, path: str, line: int) -> dict:
    cat = cat_file(cwd, rev, path)
    classification = classify_cat_file(cat, line)
    row = {
        "rev": rev,
        "path": path,
        "line": line,
        "command": cat["command"],
        "git_returncode": cat["returncode"],
        "git_stderr": cat["stderr"],
        "classification": classification,
    }
    if classification == "OK":
        row["blob_line_count"] = line_count(cat["stdout_bytes"])
        row["blob_line"] = (blob_line(cat["stdout_bytes"], line) or "")[:240]
    elif classification == "BEYOND-EOF":
        row["blob_line_count"] = line_count(cat["stdout_bytes"])
    else:
        wt = worktree_stat(cwd if cwd != REPO else REPO, path, line)
        row["worktree"] = wt
    return row


def probe_git_repo(cwd: Path) -> dict:
    proc = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "command": f"git -C {cwd} rev-parse --is-inside-work-tree",
        "returncode": int(proc.returncode),
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip()[-400:],
        "inside": (proc.stdout or "").strip() == "true",
    }


@contextmanager
def fixture_git_repo() -> Iterator[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="tst0255-git-"))
    env = git_identity_env(tmp)
    try:
        lines = [f"target-line-{i:02d}" for i in range(1, FIXTURE_LINES + 1)]
        (tmp / TARGET_REL).write_text("\n".join(lines) + "\n", encoding="utf-8")
        init = _run_git(["-c", "init.defaultBranch=main", "init"], tmp, env)
        if init.returncode != 0:
            raise RuntimeError(init.stderr.decode("utf-8", "replace"))
        add = _run_git(["add", TARGET_REL], tmp, env)
        if add.returncode != 0:
            raise RuntimeError(add.stderr.decode("utf-8", "replace"))
        commit = _run_git(
            ["-c", "commit.gpgsign=false", "commit", "-m", "tst-0255 fixture"],
            tmp,
            env,
        )
        if commit.returncode != 0:
            raise RuntimeError(commit.stderr.decode("utf-8", "replace"))
        rev_p = _run_git(["rev-parse", "HEAD"], tmp, env)
        rev = (rev_p.stdout or b"").decode("utf-8").strip()
        yield {
            "root": tmp,
            "rev": rev,
            "path": TARGET_REL,
            "line_count": FIXTURE_LINES,
            "good_line": GOOD_LINE,
            "bad_line": OFF_BY_1000,
            "good_text": f"target-line-{GOOD_LINE:02d}",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def shape_only_ok(path: str, line: int) -> bool:
    """Known-broken checker: accepts any path:digits shape, ignores the blob."""
    return bool(path) and isinstance(line, int) and line >= 1
