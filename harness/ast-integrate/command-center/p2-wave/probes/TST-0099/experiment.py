#!/usr/bin/env python3
"""Scratch-clone experiments for shared-git-index contamination (TST-0099).

All git mutating commands run under TemporaryDirectory. The host tree
/opt/p2/ast-integrate is refused as a git cwd.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

N_AGENTS = 4
HOST = Path("/opt/p2/ast-integrate").resolve()
ENV = os.environ.copy()
ENV["GIT_TERMINAL_PROMPT"] = "0"
ENV["GIT_AUTHOR_NAME"] = "TST-0099"
ENV["GIT_AUTHOR_EMAIL"] = "tst-0099@example.invalid"
ENV["GIT_COMMITTER_NAME"] = "TST-0099"
ENV["GIT_COMMITTER_EMAIL"] = "tst-0099@example.invalid"
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


class GitError(RuntimeError):
    def __init__(self, args: list[str], cwd: Path, rc: int, text: str):
        super().__init__(f"git {args} cwd={cwd} rc={rc}: {text[-800:]}")
        self.args = args
        self.cwd = cwd
        self.rc = rc
        self.text = text


def _assert_scratch(cwd: Path) -> Path:
    cwd = cwd.resolve()
    if cwd == HOST or HOST in cwd.parents:
        raise RuntimeError(f"refusing git cwd inside host tree: {cwd}")
    return cwd


def git(
    args: list[str],
    cwd: Path,
    *,
    retries: int = 40,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    cwd = _assert_scratch(cwd)
    last: subprocess.CompletedProcess[str] | None = None
    for i in range(retries):
        last = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env=ENV,
            timeout=30,
        )
        text = (last.stdout or "") + (last.stderr or "")
        if last.returncode == 0:
            return last
        lockish = (
            "index.lock" in text
            or "Unable to create" in text
            or "cannot lock" in text.lower()
            or "unable to write" in text.lower()
            or "Another git process" in text
        )
        if lockish and i + 1 < retries:
            time.sleep(0.015 * (i + 1))
            continue
        if check:
            raise GitError(args, cwd, last.returncode, text)
        return last
    assert last is not None
    if check:
        text = (last.stdout or "") + (last.stderr or "")
        raise GitError(args, cwd, last.returncode, text)
    return last


def shard_rel(i: int) -> str:
    return f"shard_{i}/work.txt"


def payload(i: int) -> str:
    return f"AGENT-{i}-MARKER\n"


def sibling_of(agent: int, paths: list[str]) -> list[str]:
    own = shard_rel(agent)
    out = []
    for p in paths:
        p = p.replace("\\", "/")
        if p.startswith("shard_") and p != own:
            out.append(p)
    return out


def commit_paths(cwd: Path, rev: str = "HEAD") -> list[str]:
    r = git(["show", "--pretty=format:", "--name-only", rev], cwd)
    return [ln.replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()]


def cached_paths(cwd: Path) -> list[str]:
    r = git(["diff", "--cached", "--name-only"], cwd)
    return [ln.replace("\\", "/") for ln in r.stdout.splitlines() if ln.strip()]


def index_path(cwd: Path) -> str:
    r = git(["rev-parse", "--git-path", "index"], cwd)
    raw = r.stdout.strip()
    p = Path(raw)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    else:
        p = p.resolve()
    return str(p)


def write_shard(cwd: Path, i: int) -> str:
    rel = shard_rel(i)
    dest = cwd / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(payload(i), encoding="utf-8")
    return rel


def _configure(repo: Path) -> None:
    git(["config", "user.email", "tst-0099@example.invalid"], repo)
    git(["config", "user.name", "TST-0099"], repo)
    git(["config", "commit.gpgsign", "false"], repo)
    hooks = repo / ".empty-hooks"
    hooks.mkdir(exist_ok=True)
    git(["config", "core.hooksPath", str(hooks)], repo)


def init_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    git(["init", "-b", "main"], repo)
    _configure(repo)
    (repo / "README").write_text("tst-0099 scratch\n", encoding="utf-8")
    git(["add", "--", "README"], repo)
    git(["commit", "-m", "init"], repo)
    return repo


def host_untouched() -> dict[str, Any]:
    git_dir = HOST / ".git"
    return {
        "host_git_present": git_dir.exists(),
        "scratch_only": True,
        "host_index_untouched": not git_dir.exists(),
        "host_rev_parse": "not-a-git-repository",
    }


def run_planted_contamination() -> dict[str, Any]:
    """Deterministic control: four writers, then one `git add -A` on the shared tree."""
    with tempfile.TemporaryDirectory(prefix="tst0099-plant-") as tmp:
        root = Path(tmp)
        repo = init_repo(root)
        barrier = threading.Barrier(N_AGENTS)
        wrote_at: dict[int, float] = {}

        def writer(i: int) -> None:
            barrier.wait(timeout=10)
            write_shard(repo, i)
            wrote_at[i] = time.time()

        with ThreadPoolExecutor(max_workers=N_AGENTS) as pool:
            list(pool.map(writer, range(N_AGENTS)))

        add = git(["add", "-A"], repo)
        staged = cached_paths(repo)
        commit = git(["commit", "-m", "planted-add-A"], repo)
        sha = git(["rev-parse", "HEAD"], repo).stdout.strip()
        changed = commit_paths(repo, "HEAD")
        quoted = []
        for agent in range(N_AGENTS):
            sibs = sibling_of(agent, changed)
            if sibs:
                quoted.append(
                    f"commit {sha[:12]} contains sibling path {sibs[0]} "
                    f"(agent {agent} own path is {shard_rel(agent)})"
                )
        overlap = False
        if wrote_at:
            overlap = max(wrote_at.values()) - min(wrote_at.values()) < 2.0
        detected = any(sibling_of(i, staged) for i in range(N_AGENTS)) and any(
            sibling_of(i, changed) for i in range(N_AGENTS)
        )
        return {
            "n_agents": N_AGENTS,
            "mode": "shared-tree-git-add-A",
            "staged": staged,
            "commit_sha": sha,
            "commit_paths": changed,
            "detected": detected,
            "sibling_paths_quoted": quoted,
            "write_overlap": overlap,
            "add_rc": add.returncode,
            "commit_rc": commit.returncode,
            "index_path": index_path(repo),
        }


def run_worktree_isolation() -> dict[str, Any]:
    """Four linked worktrees: even `git add -A` must not see a sibling shard."""
    with tempfile.TemporaryDirectory(prefix="tst0099-wt-") as tmp:
        root = Path(tmp)
        repo = init_repo(root)
        wts: list[Path] = []
        for i in range(N_AGENTS):
            wt = root / f"wt-{i}"
            git(["worktree", "add", "-b", f"agent-{i}", str(wt)], repo)
            _configure(wt)
            wts.append(wt)
        indexes = [index_path(wt) for wt in wts]
        barrier = threading.Barrier(N_AGENTS)
        results: dict[int, dict[str, Any]] = {}
        errors: dict[int, str] = {}

        def agent(i: int) -> None:
            try:
                wt = wts[i]
                barrier.wait(timeout=10)
                write_shard(wt, i)
                git(["add", "-A"], wt)
                staged = cached_paths(wt)
                git(["commit", "-m", f"agent-{i}-worktree"], wt)
                sha = git(["rev-parse", "HEAD"], wt).stdout.strip()
                changed = commit_paths(wt, "HEAD")
                results[i] = {
                    "sha": sha,
                    "staged": staged,
                    "commit_paths": changed,
                    "siblings": sibling_of(i, changed),
                    "index_path": indexes[i],
                }
            except Exception as exc:  # noqa: BLE001
                errors[i] = f"{type(exc).__name__}: {exc}"

        with ThreadPoolExecutor(max_workers=N_AGENTS) as pool:
            futs = [pool.submit(agent, i) for i in range(N_AGENTS)]
            for f in as_completed(futs):
                f.result()

        sibling_commits = []
        for i, row in results.items():
            for sib in row["siblings"]:
                sibling_commits.append(
                    f"commit {row['sha'][:12]} contains sibling path {sib} "
                    f"(agent {i} own path is {shard_rel(i)})"
                )
        unique_indexes = sorted(set(indexes))
        return {
            "n_agents": N_AGENTS,
            "mode": "worktree-per-shard-add-A",
            "index_paths": indexes,
            "indexes_isolated": len(unique_indexes) == N_AGENTS,
            "unique_index_count": len(unique_indexes),
            "agents": {str(k): v for k, v in sorted(results.items())},
            "errors": {str(k): v for k, v in sorted(errors.items())},
            "sibling_commits": sibling_commits,
            "n_commits": len(results),
        }


def run_scoped_add_discipline() -> dict[str, Any]:
    """Shared tree, concurrent `git add -- path` + `git commit -- path`."""
    with tempfile.TemporaryDirectory(prefix="tst0099-scope-") as tmp:
        root = Path(tmp)
        repo = init_repo(root)
        barrier = threading.Barrier(N_AGENTS)
        results: dict[int, dict[str, Any]] = {}
        errors: dict[int, str] = {}

        def agent(i: int) -> None:
            rel = shard_rel(i)
            try:
                barrier.wait(timeout=10)
                write_shard(repo, i)
                last_err = ""
                for _ in range(50):
                    add = git(["add", "--", rel], repo, check=False)
                    cmt = git(
                        ["commit", "-m", f"agent-{i}-scoped", "--", rel],
                        repo,
                        check=False,
                    )
                    text = ((add.stdout or "") + (add.stderr or "")
                            + (cmt.stdout or "") + (cmt.stderr or ""))
                    last_err = text[-400:]
                    if cmt.returncode == 0:
                        sha = git(
                            [
                                "log",
                                "-1",
                                "--grep",
                                f"agent-{i}-scoped",
                                "--format=%H",
                            ],
                            repo,
                        ).stdout.strip()
                        changed = commit_paths(repo, sha) if sha else []
                        results[i] = {
                            "sha": sha,
                            "commit_paths": changed,
                            "siblings": sibling_of(i, changed),
                        }
                        return
                    if "nothing to commit" in text.lower():
                        # Our path may already have been swept into a sibling commit.
                        log = git(
                            ["log", "--name-only", "--pretty=format:%H", "main"],
                            repo,
                            check=False,
                        )
                        results[i] = {
                            "sha": None,
                            "commit_paths": [],
                            "siblings": [rel],
                            "nothing_to_commit": True,
                            "log": log.stdout[-1500:],
                        }
                        return
                    time.sleep(0.02)
                errors[i] = last_err or "retries-exhausted"
            except Exception as exc:  # noqa: BLE001
                errors[i] = f"{type(exc).__name__}: {exc}"

        with ThreadPoolExecutor(max_workers=N_AGENTS) as pool:
            futs = [pool.submit(agent, i) for i in range(N_AGENTS)]
            for f in as_completed(futs):
                f.result()

        sibling_commits = []
        for i, row in results.items():
            for sib in row.get("siblings") or []:
                sha = row.get("sha") or "?"
                sibling_commits.append(
                    f"commit {str(sha)[:12]} contains sibling path {sib} "
                    f"(agent {i} own path is {shard_rel(i)})"
                )
        log = git(["log", "--format=%H %s"], repo)
        log_rows = []
        for line in log.stdout.splitlines():
            if "agent-" not in line or "-scoped" not in line:
                continue
            sha = line.split()[0]
            changed = commit_paths(repo, sha)
            log_rows.append({"sha": sha, "subject": line[41:].strip(), "paths": changed})
        return {
            "n_agents": N_AGENTS,
            "mode": "shared-tree-scoped-add-and-pathspec-commit",
            "index_path": index_path(repo),
            "agents": {str(k): v for k, v in sorted(results.items())},
            "errors": {str(k): v for k, v in sorted(errors.items())},
            "sibling_commits": sibling_commits,
            "n_commits": sum(1 for v in results.values() if v.get("sha")),
            "log_oracle": log_rows,
        }


def run_all() -> dict[str, Any]:
    planted = run_planted_contamination()
    isolated = run_worktree_isolation()
    scoped = run_scoped_add_discipline()
    return {
        "planted_contamination": planted,
        "worktree_isolation": isolated,
        "scoped_add_discipline": scoped,
        "containment": host_untouched(),
    }


if __name__ == "__main__":
    import json

    doc = run_all()
    print(json.dumps(doc, indent=2, sort_keys=True)[:8000])
    ok = (
        doc["planted_contamination"]["detected"]
        and doc["worktree_isolation"]["indexes_isolated"]
        and not doc["worktree_isolation"]["sibling_commits"]
        and doc["worktree_isolation"]["n_commits"] == N_AGENTS
        and not doc["scoped_add_discipline"]["sibling_commits"]
        and doc["scoped_add_discipline"]["n_commits"] == N_AGENTS
    )
    raise SystemExit(0 if ok else 1)
