"""Throwaway git shards under /tmp. Never touches the estate worktree git."""
from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


class IsolateError(RuntimeError):
    pass


def assert_isolated(path: Path) -> Path:
    cwd = path.resolve()
    shared = REPO.resolve()
    if cwd == shared or shared in cwd.parents:
        raise IsolateError(f"refusing git path inside estate worktree: {cwd}")
    tmp = Path("/tmp").resolve()
    if tmp not in cwd.parents and cwd != tmp:
        raise IsolateError(f"refusing git path outside /tmp: {cwd}")
    return cwd


def git_env(home: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("GIT_"):
            del env[key]
    env.update(
        {
            "HOME": str(home),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "WFA-0087 fixture",
            "GIT_AUTHOR_EMAIL": "wfa-0087@fixture.local",
            "GIT_COMMITTER_NAME": "WFA-0087 fixture",
            "GIT_COMMITTER_EMAIL": "wfa-0087@fixture.local",
            "GIT_AUTHOR_DATE": "2026-08-24T18:00:00 +0000",
            "GIT_COMMITTER_DATE": "2026-08-24T18:00:00 +0000",
            "EMAIL": "wfa-0087@fixture.local",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(args: list[str], cwd: Path, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    cwd = assert_isolated(cwd)
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if check and proc.returncode != 0:
        raise IsolateError(
            f"git {args} rc={proc.returncode} cwd={cwd}\n"
            f"{(proc.stdout or '') + (proc.stderr or '')}"
        )
    return proc


def write_tree(root: Path, files: dict[str, str]) -> None:
    root = assert_isolated(root)
    for rel, body in files.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8", newline="\n")


@dataclass
class Shard:
    candidate_id: str
    path: Path
    index: Path
    seed_head: str
    env: dict[str, str]

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return git(list(args), self.path, self.env, check=check)


def provision_shard(parent: Path, candidate_id: str, files: dict[str, str], env: dict[str, str]) -> Shard:
    parent = assert_isolated(parent)
    token = uuid.uuid4().hex[:10]
    path = parent / f"{candidate_id}-{token}"
    if path.exists():
        raise IsolateError(f"shard path exists: {path}")
    path.mkdir(parents=True)
    init = git(["init", "--object-format=sha1", "-b", "main"], path, env, check=False)
    if init.returncode != 0:
        git(["init", "-b", "main"], path, env)
    git(["config", "user.email", "wfa-0087@fixture.local"], path, env)
    git(["config", "user.name", "WFA-0087 fixture"], path, env)
    write_tree(path, files)
    git(["add", "-A"], path, env)
    git(["commit", "-m", f"seed: red intake {candidate_id}"], path, env)
    head = git(["rev-parse", "HEAD"], path, env).stdout.strip()
    index_raw = git(["rev-parse", "--git-path", "index"], path, env).stdout.strip()
    index = Path(index_raw)
    if not index.is_absolute():
        index = (path / index).resolve()
    else:
        index = index.resolve()
    if not index.is_file():
        raise IsolateError(f"missing index {index}")
    return Shard(candidate_id=candidate_id, path=path, index=index, seed_head=head, env=env)


def porcelain_paths(shard: Shard) -> list[str]:
    proc = shard.git("status", "--porcelain", "-uall")
    out: list[str] = []
    for line in (proc.stdout or "").splitlines():
        if not line.strip():
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        out.append(path.strip())
    return out


def staged_paths(cwd: Path, env: dict[str, str]) -> list[str]:
    proc = git(["diff", "--cached", "--name-only"], cwd, env)
    return [p for p in (proc.stdout or "").splitlines() if p.strip()]
